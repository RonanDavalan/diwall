#!/opt/diwall/venv/bin/python3
"""
shot.py — point d'entrée Playwright unique de Diwall : capture d'écran,
Set-of-Mark et exécution d'actions séquentielles (mode ReAct).

Pourquoi ce fichier existe :
    Un LLM ne voit pas le rendu d'une page web. shot.py lui donne des yeux
    (capture PNG + Set-of-Mark + arbre d'accessibilité) et des mains
    (cliquer, remplir, attendre) sur une session Playwright persistante,
    sans jamais faire transiter un credential en clair par le shell.

Entrée / sortie :
    CLI — `--url` (nouvelle session) ou `--reprendre-session` (session
    existante) + `--actions`/`--action` (JSON). Sortie : JSON structuré sur
    stdout (boussole, résultat par action, capture éventuelle).

Dépend de :
    lib/repertoire_chiffre.py (credentials), lib/journal.py (journalisation),
    lib/preflight_guide.py (verrou de lecture du guide), lib/profil_operateur.py,
    lib/vision.py (cliquer_visuel), lib/modeles.py, lib/ntfy.py (MFA/TOTP).
"""
import argparse
import getpass
import json
import os
import re
import resource
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

__version__ = "1.24.3"

# Permet d'importer lib/ depuis le même répertoire que shot.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.sanitisation import (
    _neutraliser_valeur_evaluer,
    _sanitiser_url_journal,
    sanitiser_urls_dans_chaine,
    rediger_query_params_sensibles,
    valider_actions_secrets as _valider_actions_secrets,
)

# Chantier crédibilité (05/08/2026) — trouvé par le cycle .deb réel sur une
# machine où dpkg exécute les scripts postinst avec HOME=/root : sans ce
# réglage, `playwright install chromium` (postinst / install.sh, exécutés en
# root) télécharge Chromium dans /root/.cache/ms-playwright, invisible pour
# l'opérateur réel (HOME différent, ou utilisateur système `diwall` sans
# home). Fixe l'emplacement indépendamment de qui a lancé l'installation —
# install.sh et postinst pointent tous les deux vers ce même chemin.
# setdefault : un opérateur qui a déjà positionné la variable garde la main.
#
# Restreint à une exécution réelle depuis /opt/diwall/ (08/08/2026) : sur un
# clone git ailleurs (développement, CI), ce chemin n'existe pas et
# `playwright install` y installe Chromium sous son emplacement par défaut —
# forcer ce chemin fixe fait alors chercher le navigateur là où il n'a jamais
# été installé (BrowserType.launch: Executable doesn't exist). Trouvé sur le
# tout premier run CI réel, masqué en local sur la machine de développement
# où /opt/diwall/.cache/ existe déjà pour de vraies raisons de production.
if os.path.dirname(os.path.abspath(__file__)) == "/opt/diwall":
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/diwall/.cache/ms-playwright")


def _boussole(operation_id=None):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = ""
    from lib.repertoire_chiffre import secrets_dir_info
    chemin_secrets, source_secrets = secrets_dir_info()
    b = {
        "utilisateur": os.getenv("USER", ""),
        "ip_locale": ip,
        "repertoire": os.getcwd(),
        "secrets_dir_effectif": chemin_secrets,
        "secrets_dir_source": source_secrets,
    }
    if operation_id:
        b["operation_id"] = operation_id
    return b

# ── Set-of-Mark ───────────────────────────────────────────────────────────────
# Audit 05/08/2026 (C-01) : détection « champ sensible » partagée entre les
# deux variantes SoM (standard et Shadow DOM, ci-dessous) — une seule source,
# concaténée telle quelle dans les deux blobs. Pas de f-string : les deux
# blobs JS sont truffés d'accolades qu'une interpolation .format()/f-string
# casserait sans échappement systématique de chaque '{'/'}'.
# Audit 06/08/2026 (F-16) : pwd, passwd, pass, mdp, api_key, apikey,
# credential ajoutés — un champ nommé 'pwd' ou 'mdp' (nommage francophone
# plausible sur les cibles Diwall) n'était masqué sur aucun des trois
# canaux qui dérivent de ce prédicat unique (D-13) : masquage visuel,
# exclusion SoM, rédaction a11y.
_DW_EST_SENSIBLE_JS = """
    const dwEstSensible = (el) => el.type === 'password' ||
        /password|pwd|passwd|pass|mdp|token|secret|api_key|apikey|credential|otp|totp|mfa|2fa|cvv|cvc|pan|ssn|iban/i.test(el.name || '') ||
        /password|pwd|passwd|pass|mdp|token|secret|api_key|apikey|credential|otp|totp|mfa|2fa|cvv|cvc|pan|ssn|iban/i.test(el.id || '') ||
        /password/i.test(el.autocomplete || '');
"""

# Chantier qualité 05/08/2026 : liste des sélecteurs interactifs SoM et filtre
# de visibilité, auparavant dupliqués tels quels dans 7 blobs JS distincts
# (standard, Shadow DOM, et l'injection <select> de remplir_som). Même
# principe de concaténation que _DW_EST_SENSIBLE_JS ci-dessus — pas de
# f-string, ces blobs sont truffés d'accolades.
_SOM_SELECTORS_JS = """
    const SELECTORS = [
        'a[href]', 'button', 'input:not([type="hidden"])',
        'select', 'textarea', 'summary',
        '[role="button"]', '[role="link"]', '[role="tab"]',
        '[role="checkbox"]', '[role="menuitem"]', '[role="radio"]',
        '[role="combobox"]', '[role="spinbutton"]', '[role="searchbox"]'
    ].join(',');
"""

# Filtre de visibilité commun (dialog fermé, style, taille) — le test de
# position par rapport au viewport diffère selon l'appelant (dans/hors
# viewport) et reste écrit à part dans chaque blob.
_SOM_FILTRE_VISIBLE_JS = """
        let p = el.parentElement; while (p) { if (p.tagName === 'DIALOG' && !p.hasAttribute('open')) return; p = p.parentElement; }
        const s = window.getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
"""

_SOM_INJECTER_JS = """() => {""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    const container = document.createElement('div');
    container.id = '__som__';
    container.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;pointer-events:none;z-index:2147483647;overflow:visible;';
    document.body.appendChild(container);
    const items = [];
    let num = 1;
    // v1.17.2 : purge des marquages d'un appel SoM précédent dans la même page —
    // sans ça, un élément taggé puis devenu invisible/hors-critère garde son
    // ancien data-dw-som-id, qui peut entrer en collision avec un nouveau numéro
    // et faire résoudre --som-rafraichir vers le mauvais élément (Qwen, signal 1).
    document.querySelectorAll('[data-dw-som-id]').forEach(el => el.removeAttribute('data-dw-som-id'));
    // Audit 05/08/2026 (C-01) : el.value d'un champ sensible ne doit jamais
    // atteindre elements_som — le blur CSS de _MASQUER_SECRETS_JS protège la
    // capture PNG, pas ce JSON. dwEstSensible factorisée dans _DW_EST_SENSIBLE_JS.""" + _DW_EST_SENSIBLE_JS + """
    document.querySelectorAll(SELECTORS).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        const box = document.createElement('div');
        box.style.cssText = [
            'position:fixed', 'box-sizing:border-box',
            'border:2px solid #e53e3e', 'border-radius:3px',
            `left:${Math.round(r.left)}px`, `top:${Math.round(r.top)}px`,
            `width:${Math.round(r.width)}px`, `height:${Math.round(r.height)}px`,
        ].join(';');
        const lbl = document.createElement('span');
        const topOffset = r.top < 20 ? Math.round(r.height) + 2 : -18;
        lbl.style.cssText = [
            'position:absolute', `top:${topOffset}px`, 'left:-2px',
            'background:#e53e3e', 'color:#fff',
            'font:bold 11px/1 monospace', 'padding:2px 4px',
            'border-radius:2px', 'white-space:nowrap',
        ].join(';');
        lbl.textContent = String(num);
        box.appendChild(lbl);
        container.appendChild(box);
        el.setAttribute("data-dw-som-id", String(num));
        items.push({
            id: num, tag: el.tagName,
            role: el.getAttribute('role') || el.tagName.toLowerCase(),
            texte: dwEstSensible(el) ? '' : (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 60),
            type: el.type || null,
        });
        num++;
    });
    return items;
}"""

_SOM_RETIRER_JS = "() => { const el = document.getElementById('__som__'); if (el) el.remove(); }"

_SOM_COMPTER_HORS_VIEWPORT_JS = """() => {""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    let n = 0;
    document.querySelectorAll(SELECTORS).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right >= 0 && r.bottom >= 0 && r.left <= vw && r.top <= vh) return;
        n++;
    });
    return n;
}"""

# Même filtrage que l'injection SoM, retourne les coordonnées du centre de l'élément N
_SOM_TROUVER_JS = """(id) => {""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    const items = [];
    document.querySelectorAll(SELECTORS).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        items.push(el);
    });
    const el = items[id - 1];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), tag: el.tagName};
}"""

# ── Set-of-Mark variantes Shadow DOM (--shadow-dom, v1.13.0) ─────────────────
# Identiques aux variantes standard, avec le walker queryShadowAll en préambule
# et queryShadowAll(SELECTORS, document) à la place de document.querySelectorAll.
# Les trois fonctions partagent strictement le même walker — garantie de cohérence
# de l'indexation injection / compter / trouver.
_SOM_INJECTER_JS_SHADOW = """() => {
    function queryShadowAll(selectors, root) {
        var result = [];
        try {
            root.querySelectorAll(selectors).forEach(function(el) { result.push(el); });
            root.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) {
                    queryShadowAll(selectors, el.shadowRoot).forEach(function(e) { result.push(e); });
                }
            });
        } catch(ignore) {}
        return result;
    }""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    const container = document.createElement('div');
    container.id = '__som__';
    container.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;pointer-events:none;z-index:2147483647;overflow:visible;';
    document.body.appendChild(container);
    const items = [];
    let num = 1;
    // v1.17.2 : même purge que la variante standard (voir _SOM_INJECTER_JS),
    // via queryShadowAll pour atteindre aussi les attributs posés dans un
    // shadow root lors d'un appel précédent — document.querySelectorAll seul
    // ne traverse pas la frontière shadow.
    queryShadowAll('[data-dw-som-id]', document).forEach(el => el.removeAttribute('data-dw-som-id'));
    // Audit 05/08/2026 (C-01) : même neutralisation que la variante standard,
    // dwEstSensible factorisée dans _DW_EST_SENSIBLE_JS.""" + _DW_EST_SENSIBLE_JS + """
    queryShadowAll(SELECTORS, document).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        const box = document.createElement('div');
        box.style.cssText = [
            'position:fixed', 'box-sizing:border-box',
            'border:2px solid #e53e3e', 'border-radius:3px',
            `left:${Math.round(r.left)}px`, `top:${Math.round(r.top)}px`,
            `width:${Math.round(r.width)}px`, `height:${Math.round(r.height)}px`,
        ].join(';');
        const lbl = document.createElement('span');
        const topOffset = r.top < 20 ? Math.round(r.height) + 2 : -18;
        lbl.style.cssText = [
            'position:absolute', `top:${topOffset}px`, 'left:-2px',
            'background:#e53e3e', 'color:#fff',
            'font:bold 11px/1 monospace', 'padding:2px 4px',
            'border-radius:2px', 'white-space:nowrap',
        ].join(';');
        lbl.textContent = String(num);
        box.appendChild(lbl);
        container.appendChild(box);
        el.setAttribute("data-dw-som-id", String(num));
        items.push({
            id: num, tag: el.tagName,
            role: el.getAttribute('role') || el.tagName.toLowerCase(),
            texte: dwEstSensible(el) ? '' : (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 60),
            type: el.type || null,
        });
        num++;
    });
    return items;
}"""

_SOM_COMPTER_HORS_VIEWPORT_JS_SHADOW = """() => {
    function queryShadowAll(selectors, root) {
        var result = [];
        try {
            root.querySelectorAll(selectors).forEach(function(el) { result.push(el); });
            root.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) {
                    queryShadowAll(selectors, el.shadowRoot).forEach(function(e) { result.push(e); });
                }
            });
        } catch(ignore) {}
        return result;
    }""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    let n = 0;
    queryShadowAll(SELECTORS, document).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right >= 0 && r.bottom >= 0 && r.left <= vw && r.top <= vh) return;
        n++;
    });
    return n;
}"""

_SOM_TROUVER_JS_SHADOW = """(id) => {
    function queryShadowAll(selectors, root) {
        var result = [];
        try {
            root.querySelectorAll(selectors).forEach(function(el) { result.push(el); });
            root.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) {
                    queryShadowAll(selectors, el.shadowRoot).forEach(function(e) { result.push(e); });
                }
            });
        } catch(ignore) {}
        return result;
    }""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    const items = [];
    queryShadowAll(SELECTORS, document).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        items.push(el);
    });
    const el = items[id - 1];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), tag: el.tagName};
}"""

# ── Résolution stable par attribut (v1.17.0, item 3, --som-rafraichir) ───────
# Contrairement à _SOM_TROUVER_JS (qui ré-indexe document.querySelectorAll() à
# chaque appel — un problème d'IDENTITÉ, pas de fraîcheur : si des éléments
# apparaissent/disparaissent avant lui dans l'ordre DOM, l'id N change
# silencieusement de cible), ces variantes recherchent l'élément marqué
# data-dw-som-id="N" à l'injection. Si l'élément a été retiré du DOM entre
# l'injection et le clic : null → erreur explicite, jamais un clic sur la
# mauvaise cible. Le marquage lui-même est posé inconditionnellement par
# _SOM_INJECTER_JS(_SHADOW) — ces fonctions ne sont utilisées que si
# --som-rafraichir est actif ; le comportement par défaut est inchangé.
_SOM_TROUVER_STABLE_JS = """(id) => {
    const el = document.querySelector('[data-dw-som-id="' + CSS.escape(String(id)) + '"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), tag: el.tagName};
}"""

_SOM_TROUVER_STABLE_JS_SHADOW = """(id) => {
    function queryShadowAll(selectors, root) {
        var result = [];
        try {
            root.querySelectorAll(selectors).forEach(function(el) { result.push(el); });
            root.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) {
                    queryShadowAll(selectors, el.shadowRoot).forEach(function(e) { result.push(e); });
                }
            });
        } catch(ignore) {}
        return result;
    }
    const sel = '[data-dw-som-id="' + CSS.escape(String(id)) + '"]';
    const matches = queryShadowAll(sel, document);
    const el = matches[0];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), tag: el.tagName};
}"""

# ── Résolution SoM hybride (défaut v1.24.0) ─────────────────────────────────
# Combine en UN seul appel de page les deux résolutions :
#   - voie brute  : le N-ième élément de la ré-indexation document.querySelectorAll
#                   (identique à _SOM_TROUVER_JS — même traversée, même ordre) ;
#   - voie stable : l'élément marqué data-dw-som-id="N" par _SOM_INJECTER_JS.
# Retourne les coordonnées de la voie stable si le marqueur existe, sinon celles
# de la voie brute (repli — comportement d'avant v1.24.0, aucune régression).
# `resolution` = "stable" | "brut_sans_reference" ; `derive` = true quand les
# deux voies sont calculables ET désignent des éléments différents (elStable !==
# elBrut, comparaison d'identité dans le contexte de page, aucune écriture DOM).
# --som-brut court-circuite ce résolveur et rétablit _SOM_TROUVER_JS pur.
# Contexte : ROBUSTESSE_SCENARIOS_ET_SESSIONS.md §2 (révision 08/09/2026).
_SOM_TROUVER_HYBRIDE_JS = """(id) => {""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    const items = [];
    document.querySelectorAll(SELECTORS).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        items.push(el);
    });
    const elBrut = items[id - 1] || null;
    const elStable = document.querySelector('[data-dw-som-id="' + CSS.escape(String(id)) + '"]');
    const cible = elStable || elBrut;
    if (!cible) return null;
    const r = cible.getBoundingClientRect();
    return {
        x: Math.round(r.left + r.width / 2),
        y: Math.round(r.top + r.height / 2),
        tag: cible.tagName,
        resolution: elStable ? "stable" : "brut_sans_reference",
        derive: !!(elStable && elBrut && elStable !== elBrut),
    };
}"""

_SOM_TROUVER_HYBRIDE_JS_SHADOW = """(id) => {
    function queryShadowAll(selectors, root) {
        var result = [];
        try {
            root.querySelectorAll(selectors).forEach(function(el) { result.push(el); });
            root.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) {
                    queryShadowAll(selectors, el.shadowRoot).forEach(function(e) { result.push(e); });
                }
            });
        } catch(ignore) {}
        return result;
    }""" + _SOM_SELECTORS_JS + """
    const vw = window.innerWidth, vh = window.innerHeight;
    const items = [];
    queryShadowAll(SELECTORS, document).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        items.push(el);
    });
    const elBrut = items[id - 1] || null;
    const matchesStable = queryShadowAll('[data-dw-som-id="' + CSS.escape(String(id)) + '"]', document);
    const elStable = matchesStable[0] || null;
    const cible = elStable || elBrut;
    if (!cible) return null;
    const r = cible.getBoundingClientRect();
    return {
        x: Math.round(r.left + r.width / 2),
        y: Math.round(r.top + r.height / 2),
        tag: cible.tagName,
        resolution: elStable ? "stable" : "brut_sans_reference",
        derive: !!(elStable && elBrut && elStable !== elBrut),
    };
}"""

# ── Sécurité visuelle — masquage des champs sensibles ────────────────────────
# Audit 05/08/2026 (D-13) : cette liste de sélecteurs divergeait de
# dwEstSensible (totp absent ici, id jamais consulté par aucune des deux) —
# deux définitions de « champ sensible » pour un même produit. Dérivée du
# même prédicat unique désormais.
_MASQUER_SECRETS_JS = """() => {""" + _DW_EST_SENSIBLE_JS + """
    document.querySelectorAll('input, textarea').forEach(function(f) {
        if (!dwEstSensible(f)) return;
        f.setAttribute('data-dw-blur', f.style.filter || '');
        f.style.filter = 'blur(8px)';
    });
}"""

_RESTAURER_SECRETS_JS = """() => {
    document.querySelectorAll('[data-dw-blur]').forEach(function(f) {
        f.style.filter = f.getAttribute('data-dw-blur') || '';
        f.removeAttribute('data-dw-blur');
    });
}"""


# Audit 06/08/2026 (F-09) : accumulateur des échecs de masquage de capture,
# vidé en tête de main(). _prendre_capture est appelée depuis plusieurs
# fonctions imbriquées (executer_actions, _injecter_som, _capture_periodique)
# sans acheminement direct vers la boussole assemblée dans main() — ce
# compteur évite de threader une valeur de retour à travers chaque
# signature intermédiaire, même motif que valeurs_secrets_resolues.
_CAPTURES_MASQUAGE_ECHOUE = []


def _prendre_capture(page, path, full_page=True, screenshot_timeout=120_000):
    """Point unique pour toute capture PNG — masquage des secrets garanti.

    Audit 06/08/2026 (F-09) : si le masquage échoue (page.evaluate lève), la
    version précédente prenait quand même la capture, sans masquage et sans
    signal — même défaut que E-07 a corrigé pour _snapshot_a11y, jamais
    appliqué symétriquement au canal image, qui est pourtant celui que le
    masquage existe pour protéger. Repli sûr ici : ne pas prendre la
    capture, signaler l'échec pour que l'appelant le porte en boussole.
    """
    try:
        page.evaluate(_MASQUER_SECRETS_JS)
    except Exception:
        _CAPTURES_MASQUAGE_ECHOUE.append(path)
        return
    try:
        page.screenshot(path=path, full_page=full_page, timeout=screenshot_timeout)
        # Audit 06/08/2026 (F-05) : page.screenshot() écrit à l'umask du
        # processus (0664 constaté) — la confidentialité reposait entièrement
        # sur le mode du répertoire parent, aucune défense en profondeur.
        # Incohérent avec _sauver_session (0600 explicite) et archiver_preuves
        # (chmod 0600 sur la copie) : même discipline appliquée ici.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            page.evaluate(_RESTAURER_SECRETS_JS)
        except Exception:
            pass


# Audit 06/08/2026 (F-02) : extraite vers lib/securite_url.py — c'était la
# seule des deux copies (shot.py/rpa.py) à contrôler le userinfo. Alias
# conservé pour ne pas toucher les appelants existants dans ce fichier.
from lib.securite_url import valider_schema_url as _valider_schema_url
from lib.langue_navigateur import locale_navigateur

# ── Détection passive de WAF (v1.16.0, item C) ────────────────────────────────
# Signal non fatal — jamais d'exception. Diwall perçoit la friction, il ne
# l'arbitre pas : décision session 47 (« Diwall est un outil de perception,
# pas un arbitre moral de l'accès »). Heuristique par mots-clés — faux positifs
# possibles, à traiter comme un signal rapide, jamais comme un verdict certain.
_WAF_MOTS_CLES_GENERIQUES = ("cloudflare", "akamai")
_WAF_MOTS_CLES_CHALLENGE = (
    "captcha", "access denied", "attention required",
    "checking your browser", "just a moment", "cf-error-details",
    "sorry, you have been blocked", "request blocked",
)


def _detecter_waf(http_status, titre_page, html_snippet):
    """True si un blocage WAF est probable — 403/429, ou mot-clé de blocage.

    v1.17.2 : les noms de fournisseur génériques (cloudflare, akamai) ne sont
    matchés que sur le titre de page — les matcher contre le HTML brut entier
    produisait un faux-positif systématique sur toute page chargeant une
    ressource CDN ordinaire (ex. <script src="cdnjs.cloudflare.com/...">),
    sans rapport avec un blocage réel. Les expressions propres à une page de
    challenge (captcha, "just a moment"...) restent matchées sur le HTML brut.
    """
    if http_status in (403, 429):
        return True
    titre = (titre_page or "").lower()
    if any(mot in titre for mot in _WAF_MOTS_CLES_GENERIQUES):
        return True
    texte = f"{titre_page or ''} {html_snippet or ''}".lower()
    return any(mot in texte for mot in _WAF_MOTS_CLES_CHALLENGE)


# ── Statistiques DOM structurelles (--no-capture) ────────────────────────────
_DOM_STATS_JS = """() => {
    var q = function(s) { return document.querySelectorAll(s).length; };
    return {
        boutons:            q('button, [role="button"], [role="menuitem"]'),
        inputs:             q('input:not([type="hidden"]), textarea'),
        listes_deroulantes: q('select'),
        formulaires:        q('form'),
        liens:              q('a[href]'),
        dialogues:          q('dialog')
    };
}"""


def _injecter_som(page, output_dir, nom="state_som", screenshot_timeout=120_000, shadow_dom=False):
    """Injecte le Set-of-Mark, capture la vue annotée, nettoie le DOM.

    Retourne (chemin_som, elements_som, hors_vp) où hors_vp est le
    nombre d'éléments interactifs présents dans le DOM mais hors viewport.
    """
    som_injecter = _SOM_INJECTER_JS_SHADOW if shadow_dom else _SOM_INJECTER_JS
    som_compter  = _SOM_COMPTER_HORS_VIEWPORT_JS_SHADOW if shadow_dom else _SOM_COMPTER_HORS_VIEWPORT_JS
    elements = page.evaluate(som_injecter)
    chemin_som = chemin_png(output_dir, nom)
    _prendre_capture(page, chemin_som, full_page=False, screenshot_timeout=screenshot_timeout)
    page.evaluate(_SOM_RETIRER_JS)
    hors_vp = page.evaluate(som_compter)
    return chemin_som, elements, hors_vp


# ── Arbre d'accessibilité (A11y) ──────────────────────────────────────────────

# Audit 05/08/2026 (D-01, correctif ciblé) : page.aria_snapshot() inclut la
# valeur des champs de saisie, y compris type="password" — vérifié en réel
# contre une cible authentifiée (mot de passe publié en clair dans a11y_tree).
# Réutilise dwEstSensible (_DW_EST_SENSIBLE_JS), même prédicat que le SoM
# (C-01) et le masquage visuel (D-13) — une seule définition de « champ
# sensible » pour les trois canaux.
_DW_VALEURS_SENSIBLES_JS = """() => {""" + _DW_EST_SENSIBLE_JS + """
    const valeurs = [];
    document.querySelectorAll('input, textarea').forEach((el) => {
        if (dwEstSensible(el) && el.value) valeurs.push(el.value);
    });
    return valeurs;
}"""


def _snapshot_a11y(page):
    """Retourne (texte, redaction_echouee) : le snapshot ARIA de la page
    (format texte YAML-like, Playwright 1.9+, rôles/noms/URLs des liens),
    et un booléen signalant si la rédaction ciblée n'a pas pu s'exécuter.
    texte est None si le snapshot lui-même n'est pas disponible, ou si la
    rédaction a échoué.

    Audit 05/08/2026 (D-01, correctif ciblé) : les valeurs des champs
    sensibles actuellement présents dans le DOM (autofill navigateur,
    session persistante — donc pas nécessairement saisis par Diwall) sont
    rédigées du texte avant retour. Complète le correctif de fond
    (_rediger_valeurs_secrets), qui ne connaît que ce que Diwall a lui-même
    résolu via _resoudre_valeur_secrets.

    Audit 06/08/2026 (E-07) : si `page.evaluate` échoue (navigation en
    cours, contexte détruit, CSP particulière), la version précédente
    retournait le snapshot intact, non rédigé — un repli qui publiait
    exactement ce que cette fonction existe pour protéger. Le repli sûr
    ici est l'inverse : ne rien publier, avec un signal explicite pour que
    l'appelant le porte dans la boussole plutôt que de le passer sous
    silence.
    """
    try:
        texte = page.aria_snapshot()
    except Exception:
        return None, False
    if not texte:
        return texte, False
    try:
        for v in page.evaluate(_DW_VALEURS_SENSIBLES_JS):
            if v:
                texte = texte.replace(v, "<secret_redige>")
    except Exception:
        return None, True
    return texte, False


# ── Persistance de session (ReAct) ────────────────────────────────────────────

_AVERTISSEMENT_DERIVE = (
    "URL au moment de la reprise diverge de l'URL au moment de la sauvegarde. "
    "L'état DOM (cases cochées, champs saisis, modals ouverts) n'a pas été préservé. "
    "Si le scénario présuppose un état DOM hérité de la session précédente, il échouera "
    "silencieusement. Voir _CADRE/SPECIFICATIONS/26_GUIDE_CLAUDE_SESSION_DIWALL.md."
)

_legacy_session_warned = False


def _construire_diwall_meta(profil, horodatage, modeles_appeles, url_finale):
    """Construit le bloc diwall_meta v1.3 pour la sortie JSON.

    Renvoie un dict prêt à injecter sous la clé `diwall_meta` du
    JSON de sortie. Si la traçabilité modèles est désactivée dans
    le profil, la clé `modeles_utilises` est omise (§5.4 spec 33_).
    """
    meta = {
        "version_shot": __version__,
        "horodatage_iso": horodatage,
        "hostname_executant": socket.gethostname(),
        "utilisateur_executant": getpass.getuser(),
        "profil_actif": profil.descripteur(),
        "url_au_moment_capture": url_finale,
    }
    if not profil.tracabilite_modeles_active:
        return meta

    from lib.modeles import collecter_modele_ollama, collecter_modele_claude
    modeles_utilises = []
    for entree in modeles_appeles:
        tag = entree["_tag"]
        role = entree["role"]
        if entree["mode_llm"] == "local":
            modeles_utilises.append(collecter_modele_ollama(
                tag, role,
                inclure_hash=profil.tracabilite_inclure_hash,
            ))
        else:
            modeles_utilises.append(collecter_modele_claude(tag, role))
    meta["modeles_utilises"] = modeles_utilises
    return meta


def _traduire_diagnostic_en_conseil(evaluations_journal):
    """v1.18.0 — traduit les `evaluations` (format journal) de la dernière
    exécution de scenarios/diagnostic_dom.json sur ce host en recommandation
    `mode_conseille`. Couplage assumé aux index fixes 3 (frameworks JS) et 4
    (nombre de shadow roots) de ce scénario précis — fragile si son ordre
    d'actions change, mais évite de parser le contenu des scripts (encore
    plus fragile). Best-effort : toute erreur retourne None plutôt que de
    faire échouer le calcul de l'etat.
    """
    try:
        valeurs = [e.get("valeur_retournee") for e in evaluations_journal]
        frameworks = json.loads(valeurs[3] or "{}")
        shadow_roots = int(json.loads(valeurs[4] or "0"))
    except (IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None

    noms_frameworks = [k for k in ("React", "Vue", "Angular") if frameworks.get(k)]
    if not noms_frameworks and shadow_roots == 0:
        return None  # page structurellement simple — rien à recommander

    raisons = []
    if noms_frameworks:
        raisons.append(f"framework_detecte:{','.join(noms_frameworks)}")
    if shadow_roots > 0:
        raisons.append(f"shadow_roots:{shadow_roots}")

    return {
        "mode": "full",
        "shadow_dom": shadow_roots > 0,
        "som_rafraichir": bool(noms_frameworks),
        "raisons": raisons,
    }


def _calculer_mode_conseille(url_finale):
    """v1.18.0 — interroge le journal pour la dernière exécution de
    diagnostic_dom.json sur le host de `url_finale`. Jamais de spéculation :
    absent si aucune donnée réelle n'existe pour ce host. Best-effort,
    isolé de tout le reste — son échec ne dégrade jamais la sortie JSON.
    """
    try:
        from lib import journal
        from urllib.parse import urlparse as _urlparse
        host = _urlparse(url_finale or "").hostname
        if not host:
            return None
        evaluations_journal = journal.dernier_diagnostic_host(host)
        if not evaluations_journal:
            return None
        return _traduire_diagnostic_en_conseil(evaluations_journal)
    except Exception:
        return None


def _construire_etat(auth_status, respect, derive_session, erreurs_js,
                     waf_bloquants=None, erreurs_console=None, ignorer_waf=False,
                     mode_conseille=None):
    """Synthèse déterministe de l'état opérationnel (v1.16.0, item A).

    Calculée uniquement à partir de signaux déjà présents dans le run — aucun
    appel réseau ni navigateur supplémentaire. Isolée à dessein : appelée
    dans un bloc protégé, son échec ne doit jamais dégrader le reste de la
    sortie JSON.

    Portée assumée : « pret_a_agir » ne vérifie pas la conformité de l'URL ou
    du titre à une attente métier (Diwall n'a aucune référence externe pour
    cela — c'est le rôle des assertions `evaluer` + `contient`/`motif`/`attendu`
    de rpa.py). Il agrège uniquement les signaux que shot.py peut déterminer
    par lui-même : authentification, dérive de session, plafond de
    navigation, friction réseau/applicative (WAF, erreurs JS/console).

    `ignorer_waf` (v1.17.2) : quand actif, un blocage WAF dégrade toujours
    `niveau_confiance` mais ne force plus `pret_a_agir` à `False` à lui seul —
    évite qu'un faux-positif résiduel bloque l'agent de façon binaire sur une
    page saine (Z.ai, signal 3).
    """
    raisons = []
    pret = True
    niveau = "eleve"

    if auth_status is not None:
        if auth_status == "active":
            raisons.append("session authentifiée active")
        else:
            raisons.append("session non authentifiée (auth_status: inactive)")
            pret = False
            niveau = "faible"

    if derive_session:
        raisons.append(
            "dérive de session détectée — URL divergente depuis la sauvegarde"
        )
        pret = False
        niveau = "faible"

    if respect and respect.get("plafond_atteint"):
        raisons.append(f"plafond de navigation atteint ({respect['plafond_atteint']})")
        pret = False
        if niveau == "eleve":
            niveau = "modere"

    if erreurs_js:
        raisons.append(f"{len(erreurs_js)} erreur(s) JS non interceptée(s)")
        if niveau == "eleve":
            niveau = "modere"

    if erreurs_console:
        raisons.append(f"{len(erreurs_console)} message(s) d'erreur en console")
        if niveau == "eleve":
            niveau = "modere"

    if waf_bloquants:
        if ignorer_waf:
            raisons.append(
                "blocage WAF détecté, ignoré sur demande explicite (--ignorer-waf)"
            )
            if niveau == "eleve":
                niveau = "modere"
        else:
            raisons.append("blocage WAF détecté (signal non fatal, à interpréter)")
            pret = False
            niveau = "faible"

    if not raisons:
        raisons.append("aucun signal de friction détecté")

    etat = {"pret_a_agir": pret, "niveau_confiance": niveau, "raisons": raisons}
    if mode_conseille:
        etat["mode_conseille"] = mode_conseille
        resume = f"mode_conseille disponible : {mode_conseille['mode']} recommandé"
        if mode_conseille["raisons"]:
            resume += f" ({', '.join(mode_conseille['raisons'])})"
        raisons.append(resume)
    return etat


def _nettoyer_session_ephemere(chemin_session, explicitement_demandee):
    """Désactivé (FR-74/FR-75) — ne supprime plus le fichier de session.

    Ancien comportement : supprimait --reprendre-session si --sauver-session
    était absent → FileNotFoundError sur les appels successifs. Le fichier
    appartient à l'opérateur ; shot.py n'a pas à le détruire.
    """


def _journaliser_run(result, actions, intention, cible_url, resultat, erreur=None,
                     operation_id=None, source_scenario=None, chainage=None,
                     secret_resolu=False, secrets_chemin=None):
    """Consigne le run dans le journal d'opérations (v1.4). Best-effort.

    N'altère jamais la sortie ni le code de retour de shot.py : toute
    erreur de journalisation est avalée par lib/journal lui-même.

    `operation_id` (v1.16.0, item B) : transmis tel quel — le journal réutilise
    l'identité de run générée par shot.py au lieu d'en régénérer une nouvelle.

    `chainage` (v1.19.0) : transmis tel quel depuis rpa.py (--chainage), qui
    l'a construit lors de l'aplatissement des `declencher_scenario`. Absent
    sur un run sans chaînage — additif strict.

    `secret_resolu`, `secrets_chemin` (audit 06/08/2026, E-02) : transmis à
    `journal.enregistrer_operation` — second signal d'authentification pour
    l'archivage des preuves, indépendant de `--auth-indicator`.
    """
    try:
        from lib import journal
    except Exception:
        return
    captures = []
    if result.get("capture"):
        captures.append(result["capture"])
    # Audit 06/08/2026 (F-04) : deux structures inversées. captures_intermediaires
    # (action "capturer") est une liste de CHAÎNES — la version précédente
    # cherchait un dict avec clé "chemin" dessus, condition toujours fausse
    # sur cette liste. stream_captures (captures périodiques pendant une
    # attente) EST une liste de dicts {"chemin": ...} et n'était jamais
    # parcourue du tout. La capture authentifiée la plus utile
    # (ex. capture_som_apres_login) passait par captures_intermediaires et
    # ne quittait donc jamais /tmp/diwall/, hors du dispositif D-02/E-02.
    for chemin in result.get("captures_intermediaires") or []:
        if isinstance(chemin, str) and chemin:
            captures.append(chemin)
    for c in result.get("stream_captures") or []:
        chemin = c.get("chemin") if isinstance(c, dict) else None
        if chemin:
            captures.append(chemin)
    if result.get("capture_echec"):
        captures.append(result["capture_echec"])
    journal.enregistrer_operation(
        outil="shot.py",
        version=__version__,
        cible_url=cible_url,
        resultat=resultat,
        actions=actions,
        diwall_meta=result.get("diwall_meta"),
        intention=intention,
        captures=captures,
        erreur=erreur,
        evaluations=result.get("evaluations"),
        operation_id=operation_id,
        respect=result.get("respect"),
        source_scenario=source_scenario,
        chainage=chainage,
        auth_status=result.get("auth_status"),
        secret_resolu=secret_resolu,
        secrets_chemin=secrets_chemin,
    )


def _sauver_session(ctx, page, chemin, viewport):
    """Sauvegarde cookies + localStorage + URL courante dans un fichier JSON.

    Format v1.2 enrichi de diwall_meta pour la détection de dérive (lot 8.5).
    Les clés url et viewport au niveau racine restent présentes pour la
    rétrocompatibilité du chargement.
    """
    horodatage_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    session = {
        "url": page.url,
        "viewport": viewport,
        "storage_state": ctx.storage_state(),
        "diwall_meta": {
            "url_au_moment_sauvegarde": page.url,
            "horodatage_iso": horodatage_iso,
            "version_shot": __version__,
        },
    }
    # Écriture atomique : évite la corruption du fichier lors d'appels rapides successifs.
    # Audit 05/08/2026 (C-02) : storage_state est l'équivalent fonctionnel des
    # identifiants après authentification — os.open à mode explicite 0o600,
    # comme le marqueur de guide (preflight_guide.py), plutôt que l'umask du
    # processus (0644 en configuration Debian par défaut).
    # Audit 05/08/2026 (D-09) : chemin_tmp est prévisible (<cible>.tmp). Sans
    # O_EXCL, un fichier ou un lien symbolique pré-existant à ce chemin serait
    # réutilisé avec ses permissions/sa cible actuelles ; O_NOFOLLOW refuse
    # explicitement de suivre un lien. Un .tmp résiduel d'un run précédent est
    # retiré avant l'ouverture — sinon O_EXCL échouerait systématiquement.
    chemin_tmp = chemin + ".tmp"
    try:
        os.unlink(chemin_tmp)
    except FileNotFoundError:
        pass
    fd = os.open(chemin_tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    os.replace(chemin_tmp, chemin)  # rename : chemin hérite du mode 0o600 du .tmp


def _charger_session(chemin):
    """Charge une session Diwall depuis un fichier JSON.

    Émet un warning unique sur stderr si le fichier est au format legacy
    (sans diwall_meta) : la détection de dérive sera désactivée pour ce run.
    """
    global _legacy_session_warned
    # G-31 (CHANTIER_SANITISATION.md, LOT 5) : O_NOFOLLOW — même discipline
    # que l'écriture (_sauver_session, ligne ci-dessus), ferme la fenêtre où
    # le fichier de session serait remplacé par un lien symbolique avant lecture.
    fd = os.open(chemin, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, encoding="utf-8") as f:
        session = json.load(f)
    if "diwall_meta" not in session and not _legacy_session_warned:
        print(
            f"⚠ Session legacy détectée (sans diwall_meta) : "
            f"{chemin} — détection de dérive d'URL désactivée pour ce fichier.",
            file=sys.stderr,
        )
        _legacy_session_warned = True
    return session


def _normaliser_url_derive(url):
    """Normalise une URL pour la comparaison de dérive de session : schéma +
    hôte + port + chemin, plus la query normalisée (paramètres triés, query
    vide traitée comme absente) — fragment ignoré.

    Audit 06/08/2026 (E-03) : distincte de `_sanitiser_url_journal`, qui
    supprime la query entièrement pour la confidentialité du journal — un
    choix légitime là, mais qui rendait la détection de dérive aveugle à
    toute expiration de session dont l'unique signal est un paramètre de
    query (ex. `/?vue=login` remplaçant `/?vue=domaine`).
    """
    if not url:
        return url
    try:
        from urllib.parse import parse_qsl, urlencode
        p = urlparse(url)
        netloc_sans_userinfo = p.hostname or ""
        if p.port:
            netloc_sans_userinfo += f":{p.port}"
        query_triee = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
        base = f"{p.scheme}://{netloc_sans_userinfo}{p.path}"
        return f"{base}?{query_triee}" if query_triee else base
    except Exception:
        return "[url non parseable]"


def _detecter_derive_session(session, url_cible_reprise):
    """Compare l'URL au moment de la sauvegarde à l'URL au moment de la reprise.

    Retourne un dict prêt à injecter sous la clé `derive_session` du JSON
    de sortie si une divergence est détectée, ou None sinon (URLs identiques,
    session legacy, ou URL manquante).

    Audit 05/08/2026 (D-05), affiné 06/08/2026 (E-03) : comparaison sur des
    URL normalisées (schéma + hôte + port + chemin + query triée, via
    _normaliser_url_derive), plutôt que sur la chaîne brute ni sur la query
    entièrement écartée. Sans normalisation de query, une différence
    purement cosmétique (`.../?` vs `.../`) déclenchait une fausse dérive ;
    sans la conserver du tout, une expiration réelle signalée uniquement par
    la query (`/?vue=login` remplaçant `/?vue=domaine`) passait inaperçue —
    et `GUIDE_LLM_SESSIONS.md` prescrit de rejouer l'authentification
    complète dès que ce signal est vrai.
    """
    meta = session.get("diwall_meta")
    if not meta:
        return None
    url_sauvegardee = meta.get("url_au_moment_sauvegarde")
    if not url_sauvegardee or not url_cible_reprise:
        return None
    if _normaliser_url_derive(url_sauvegardee) == _normaliser_url_derive(url_cible_reprise):
        return None
    return {
        "url_sauvegardee": url_sauvegardee,
        "url_reprise": url_cible_reprise,
        "avertissement": _AVERTISSEMENT_DERIVE,
    }


# Défaut de --output-dir — référencé aussi dans main() pour l'isolation par
# operation_id (v1.16.0, item B) : seul le défaut est isolé automatiquement,
# un --output-dir explicite reste respecté tel quel.
_OUTPUT_DIR_DEFAUT = "/tmp/diwall"


def parse_args():
    p = argparse.ArgumentParser(description="Diwall — capture Playwright avec actions")
    # Mode A (séquentiel) : --url requis. Mode B (ReAct) : --reprendre-session à la place.
    p.add_argument("--url", default=None, help="URL à capturer (Mode A) ou navigation initiale (Mode B)")
    p.add_argument("--actions", help="Fichier JSON ou JSON inline d'actions séquentielles (Mode A)")
    p.add_argument("--action", default=None,
                   help="Action unique JSON pour le pas ReAct (Mode B, ex: '{\"type\":\"cliquer_som\",\"id\":4}')")
    p.add_argument("--reprendre-session", dest="reprendre_session", default=None,
                   metavar="FICHIER", help="Reprend une session sauvegardée (Mode B ReAct)")
    p.add_argument("--sauver-session", dest="sauver_session", default=None,
                   metavar="FICHIER", help="Sauvegarde l'état navigateur après les actions")
    p.add_argument("--output", help="Chemin de sortie PNG (auto-généré si absent)")
    p.add_argument("--attendre-selecteur", dest="attendre_selecteur",
                   help="Sélecteur CSS à attendre avant la capture finale")
    p.add_argument("--timeout", type=int, default=10000,
                   help="Timeout en ms pour chaque opération (défaut : 10000)")
    p.add_argument("--screenshot-timeout", dest="screenshot_timeout", type=int, default=120_000,
                   help="Timeout ms pour page.screenshot() (défaut : 120000). "
                        "Distinct de --timeout (actions Playwright).")
    p.add_argument("--wait-until", dest="wait_until",
                   choices=["networkidle", "load", "domcontentloaded"],
                   default="networkidle",
                   help="Condition d'arrêt de la navigation initiale (v1.22.0, défaut : "
                        "networkidle, inchangé). Utiliser 'load' sur une cible qui "
                        "n'atteint jamais le silence réseau (page à statistiques live, "
                        "polling continu) : le timeout n'est alors pas une question de "
                        "durée. N'affecte pas l'action 'naviguer'.")
    p.add_argument("--output-dir", dest="output_dir", default=_OUTPUT_DIR_DEFAUT,
                   help="Répertoire de sortie des captures auto (défaut : /tmp/diwall)")
    p.add_argument("--largeur", type=int, default=1280, help="Largeur viewport px (défaut : 1280)")
    p.add_argument("--hauteur", type=int, default=720, help="Hauteur viewport px (défaut : 720)")
    p.add_argument("--llm", choices=["local", "claude"], default="local",
                   help="Mode LLM pour cliquer_visuel : local (Ollama) ou claude (API)")
    p.add_argument("--som", action="store_true",
                   help="Active le Set-of-Mark : capture annotée + liste elements_som dans le JSON")
    p.add_argument("--a11y", action="store_true",
                   help="Inclut le snapshot d'accessibilité (a11y_tree) dans le JSON")
    p.add_argument("--interval-capture", dest="interval_capture", type=int, default=0,
                   help="Intervalle en secondes (>0) pour captures périodiques pendant pause/"
                        "attendre/attendre_navigation. Défaut 0 = désactivé. Override par-action "
                        "possible via la clé 'interval_capture' du scénario.")
    p.add_argument("--intention", default=None,
                   help="Libellé métier du run, consigné dans le journal d'opérations "
                        "(v1.4). Ex. : \"Suppression clone __DOMAINE_CLIENT__ 2026-05-30\".")
    p.add_argument("--auth-indicator", dest="auth_indicator", default=None,
                   help="Sélecteur CSS visible uniquement en session authentifiée (v1.9). "
                        "Ajoute auth_status (\"active\"|\"inactive\") à la racine du JSON.")
    p.add_argument("--no-capture", dest="no_capture", action="store_true",
                   help="Skip la capture PNG finale, l'injection SoM et les écritures disque (v1.9). "
                        "Incompatible avec --som et l'action capturer.")
    p.add_argument("--secrets", default=None,
                   help="Chemin absolu vers un fichier JSON de credentials (v1.10). "
                        "Court-circuite la résolution par hostname pour tout le run. "
                        "Le répertoire parent doit être un point de montage actif (T1).")
    p.add_argument("--shadow-dom", dest="shadow_dom", action="store_true",
                   help="Active la traversée récursive des Shadow Roots ouverts pour le SoM "
                        "(v1.13.0). Désactivé par défaut. À utiliser sur Angular, Lit, Stencil. "
                        "Sans effet sur les Shadow Roots fermés (limitation navigateur).")
    p.add_argument("--som-brut", dest="som_brut", action="store_true",
                   help="Force la résolution SoM par ré-indexation brute pure de "
                        "cliquer_som/remplir_som (comportement d'avant v1.24.0). Depuis "
                        "v1.24.0 le défaut est la résolution hybride : voie stable par "
                        "attribut data-dw-som-id si un marqueur existe, repli sur "
                        "ré-indexation brute sinon, avec détection de divergence "
                        "(boussole som_resolution / som_derive_detectee).")
    p.add_argument("--som-rafraichir", dest="som_rafraichir", action="store_true",
                   help="Alias historique sans effet depuis v1.24.0 (v1.17.0). La "
                        "résolution hybride avec repli est désormais le défaut ; il n'y "
                        "a plus rien à activer. Accepté silencieusement pour compatibilité "
                        "des appelants et scénarios existants.")
    p.add_argument("--ignorer-waf", dest="ignorer_waf", action="store_true",
                   help="Un blocage WAF détecté dégrade niveau_confiance mais ne force plus "
                        "pret_a_agir à false à lui seul (v1.17.2). À utiliser quand un "
                        "faux-positif résiduel de _detecter_waf bloque l'agent sur une page "
                        "saine. Opt-in : comportement par défaut (blocage) inchangé sans ce flag.")
    p.add_argument("--auth-indicator-negative", dest="auth_indicator_negative", default=None,
                   help="Sélecteur CSS dont la présence indique l'ABSENCE d'authentification "
                        "(v1.14.0). À utiliser avec --auth-indicator pour les interfaces à "
                        "sélecteur positif ambigu (ex. menu persistant sur la page de login).")
    p.add_argument("--mode", choices=["fast", "full"], default=None,
                   help="Raccourci de mode : fast = --no-capture --a11y | "
                        "full = comportement par défaut (v1.14.0).")
    p.add_argument("--stealth", action="store_true",
                   help="Active le mode furtif via playwright-stealth (v1.15.0). "
                        "Supprime navigator.webdriver et normalise les attributs techniques. "
                        "Ne change pas l'IP ni l'opérateur — restauration d'équité de traitement.")
    p.add_argument("--ignore-tls-errors", dest="ignore_tls_errors", action="store_true",
                   help="Accepte les certificats TLS invalides (LAN dev/Step-CA uniquement). "
                        "Ajoute tls_errors_ignored:true dans la boussole. (v1.15.1)")
    p.add_argument("--http-credentials", dest="http_credentials", action="store_true",
                   help="Résout http_username/http_password depuis le répertoire chiffré (clés fixes, "
                        "précédent ntfy_topic) et les injecte au contexte navigateur pour "
                        "répondre à un challenge HTTP Basic Auth (v1.21.0). Identifiants "
                        "scopés à l'origine de la cible (jamais envoyés à un tiers chargé "
                        "dans la même page). N'active jamais le contournement d'un vrai "
                        "blocage — seule l'authentification réseau standard.")
    p.add_argument("--no-evaluer", dest="no_evaluer", action="store_true",
                   help="Désactive l'action 'evaluer' — recommandé en production sur cibles "
                        "avec formulaires sensibles. (v1.15.1)")
    p.add_argument("--no-filtre-evaluer", dest="no_filtre_evaluer", action="store_true",
                   help="Désactive la neutralisation stdout des valeurs 'evaluer', URLs et "
                        "messages d'erreur (LOT 1, CHANTIER_SANITISATION.md) — run de debug "
                        "explicite uniquement. Actif (filtre ON) par défaut. Pose "
                        "boussole.filtre_evaluer_actif: false dans la sortie quand désactivé.")
    p.add_argument("--version", action="store_true",
                   help="Affiche la version installée et quitte immédiatement, sans Playwright (v1.18.0).")
    p.add_argument("--guide-version", dest="guide_version", default=None,
                   help="Jeton de lecture de docs/GUIDE_LLM.md — requis sauf marqueur local valide "
                        "(v1.18.0). Valeur : <!-- notice-version: X.Y --> en tête de ce fichier.")
    p.add_argument("--source-scenario", dest="source_scenario", default=None,
                   help="Nom de fichier du scénario (sans chemin), transmis par rpa.py (v1.18.0). "
                        "Plomberie interne pour mode_conseille — pas un paramètre destiné à un "
                        "appel shot.py direct.")
    p.add_argument("--chainage", dest="chainage", default=None,
                   help="Arbre de chaînage (JSON), transmis par rpa.py quand le scénario utilise "
                        "declencher_scenario (v1.19.0). Plomberie interne pour la traçabilité du "
                        "journal — pas un paramètre destiné à un appel shot.py direct.")
    return p.parse_args()


def chemin_png(repertoire, prefixe="capture"):
    # G-14 (résidu, CHANTIER_SANITISATION.md, LOT 5) : le plan demandait
    # d'ajouter os.chmod(os.path.dirname(repertoire), 0o700) ici, comme
    # _preparer_stream_dir le fait sur son propre parent. Écart volontaire,
    # vérifié le 07/08/2026 : les 5 call sites de chemin_png() passent tous
    # directement output_dir/args.output_dir — dont le parent immédiat est
    # _OUTPUT_DIR_DEFAUT ("/tmp/diwall"), le répertoire RACINE partagé entre
    # tous les runs et tous les comptes de service du groupe diwall
    # (GUIDE_LLM.md : "sudo usermod -aG diwall <account>"). Contrairement à
    # _preparer_stream_dir (dont le parent chmodé est un sous-dossier "stream"
    # interne au run, jamais partagé), chmod 0700 ici casserait la création de
    # sous-répertoires par tout autre compte du groupe. Le répertoire feuille
    # (ci-dessous) est déjà 0700 depuis un audit antérieur — seuls les NOMS
    # des répertoires d'autres runs resteraient visibles au groupe, jamais le
    # contenu des PNG. Non appliqué ; signalé pour arbitrage.
    os.makedirs(repertoire, mode=0o700, exist_ok=True)
    os.chmod(repertoire, 0o700)  # corrige si le répertoire existait déjà avec de mauvaises permissions
    # time_ns() : résolution nanoseconde — élimine la collision de deux runs
    # lancés dans la même seconde (v1.15.2, item 8 / K1').
    return os.path.join(repertoire, f"{prefixe}_{time.time_ns()}.png")


def _preparer_stream_dir(output_dir, run_id):
    """Crée /tmp/diwall/stream/<run_id>/ en mode 700. Idempotent."""
    stream_dir = os.path.join(output_dir, "stream", str(run_id))
    os.makedirs(stream_dir, mode=0o700, exist_ok=True)
    os.chmod(stream_dir, 0o700)
    parent = os.path.dirname(stream_dir)
    os.chmod(parent, 0o700)
    return stream_dir


def _capture_periodique(page, stream_dir, action_index, t_ms, screenshot_timeout=120_000):
    """Prend une capture intermédiaire pendant une attente. Retourne le dict descriptif."""
    chemin = os.path.join(stream_dir, f"{action_index}_{t_ms}.png")
    _prendre_capture(page, chemin, full_page=False, screenshot_timeout=screenshot_timeout)
    return {"action_index": action_index, "t_ms": t_ms, "chemin": chemin}


def charger_actions(source):
    if not source:
        return []
    s = source.strip()
    if s.startswith("[") or s.startswith("{"):
        data = json.loads(s)
    else:
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
    # Auto-détecte le format scénario {nom, url, actions:[…]} vs tableau direct
    if isinstance(data, dict) and "actions" in data:
        actions = data["actions"]
    else:
        actions = data
    _valider_actions_secrets(actions)
    # G-29 (CHANTIER_SANITISATION.md, LOT 5) : rpa.py valide tout scénario
    # chargé contre scenarios/schema.json avant Playwright ; shot.py invoqué
    # directement (--actions, hors rpa.py) ne validait rien. "url" n'est pas
    # toujours présent dans le fichier chargé par shot.py (il vient souvent
    # de --url CLI, séparément) — un placeholder suffit : jsonschema ne
    # vérifie pas le format "uri" sans FormatChecker explicite (même
    # comportement que rpa.py, qui ne le fournit pas non plus) ; seule la
    # structure de 'actions' importe ici.
    from lib.validation_scenario import valider_schema_scenario
    valider_schema_scenario({"url": "https://placeholder.invalid/", "actions": actions})
    return actions


def _resoudre_frame_locator(page, a, type_action):
    """Résout 'iframe_selecteur' (frame unique) ou 'iframe_chemin' (descente
    imbriquée, v1.18.0) en un objet FrameLocator Playwright. Exactement un
    des deux requis — même discipline que 'defiler' (px xor selecteur).
    Le schéma (scenarios/schema.json) impose déjà cette contrainte quand
    rpa.py valide le scénario ; ce contrôle défensif couvre aussi les appels
    shot.py directs (--actions) qui ne passent pas par le validateur JSON
    Schema de rpa.py.
    """
    iframe_sel = a.get("iframe_selecteur")
    iframe_chemin = a.get("iframe_chemin")
    if iframe_sel and iframe_chemin:
        raise ValueError(
            f"{type_action} : 'iframe_selecteur' et 'iframe_chemin' sont mutuellement exclusifs"
        )
    if iframe_chemin is not None:
        if not isinstance(iframe_chemin, list) or not iframe_chemin:
            raise ValueError(
                f"{type_action} : 'iframe_chemin' doit être un tableau non vide de sélecteurs CSS"
            )
        locator = page.frame_locator(iframe_chemin[0])
        for niveau in iframe_chemin[1:]:
            locator = locator.frame_locator(niveau)
        return locator
    if not iframe_sel:
        raise ValueError(f"{type_action} requiert 'iframe_selecteur' ou 'iframe_chemin'")
    return page.frame_locator(iframe_sel)


def _resoudre_valeur_secrets(a, valeur, page, secrets_chemin, type_action, valeurs_resolues=None):
    """Résout 'depuis_secrets'/'depuis_secrets_totp' en credential réel lu
    depuis le répertoire chiffré. Factorisé depuis remplir/remplir_som/
    remplir_iframe (chantier qualité 05/08/2026) — même bloc de résolution
    dupliqué trois fois à l'identique, même catégorie de défaut que C-01
    (dwEstSensible, corrigé en session 76) : trois copies d'un code de
    résolution de credentials sont trois endroits à corriger en cas de bug.

    `valeurs_resolues` (audit 05/08/2026, D-01, correctif de fond) : si
    fourni, chaque valeur réellement résolue y est ajoutée — point de
    passage unique qui alimente la redaction de la sortie JSON finale,
    quel que soit le canal par lequel une valeur injectée ressortirait
    (a11y_tree aujourd'hui, un canal encore inconnu demain).
    """
    if valeur == "depuis_secrets":
        cle = a.get("secret_cle")
        if not cle:
            raise ValueError(f"{type_action} depuis_secrets : champ 'secret_cle' requis")
        if secrets_chemin:
            from lib.repertoire_chiffre import lire_credential_fichier
            resultat = lire_credential_fichier(secrets_chemin, cle, page.url)
        else:
            from lib.repertoire_chiffre import lire_credential, domaine_depuis_url
            resultat = lire_credential(domaine_depuis_url(page.url), cle)
        if valeurs_resolues is not None and resultat:
            valeurs_resolues.add(resultat)
        return resultat
    if valeur == "depuis_secrets_totp":
        if secrets_chemin:
            from lib.repertoire_chiffre import lire_totp_fichier
            resultat = lire_totp_fichier(secrets_chemin, page.url)
        else:
            from lib.repertoire_chiffre import lire_totp, domaine_depuis_url
            resultat = lire_totp(domaine_depuis_url(page.url))
        if valeurs_resolues is not None and resultat:
            valeurs_resolues.add(resultat)
        return resultat
    return valeur


# Audit 06/08/2026 (F-08) : compteur d'occurrences rédigées par
# _rediger_valeurs_secrets, vidé en tête de main() — même motif que
# _CAPTURES_MASQUAGE_ECHOUE (F-09). Sur une liste de comptes, l'identifiant
# masqué redevient identifiable *parce qu'il est le seul masqué* — la
# décision retenue n'est pas de revenir sur le seuil de rédaction (un faux
# positif reste préférable à une fuite), mais de signaler qu'une vue trouée
# est en cours de lecture plutôt que de laisser le lecteur le découvrir par
# élimination.
_CHAMPS_REDIGES = [0]


def _rediger_valeurs_secrets(obj, valeurs):
    """Parcourt récursivement obj (dict/list/str) et remplace, dans toute
    chaîne, chaque occurrence exacte d'une valeur de `valeurs` par un
    marqueur neutre.

    Audit 05/08/2026 (D-01, correctif de fond) : point de passage unique
    appliqué juste avant json.dumps(result) — invariant plutôt que
    protection par canal (a11y_tree aujourd'hui, un canal encore inconnu
    demain). Aucun seuil de longueur (décision Ronan, 05/08/2026) :
    correspondance exacte systématique, un faux positif de redaction étant
    strictement préférable à une fuite.
    """
    if not valeurs:
        return obj
    if isinstance(obj, str):
        for v in valeurs:
            if v and v in obj:
                _CHAMPS_REDIGES[0] += obj.count(v)
                obj = obj.replace(v, "<secret_redige>")
        return obj
    if isinstance(obj, dict):
        return {k: _rediger_valeurs_secrets(v, valeurs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rediger_valeurs_secrets(v, valeurs) for v in obj]
    return obj


def executer_actions(page, actions, output_dir, timeout, mode_llm="local",
                     interval_capture_default=0, modeles_appeles=None,
                     secrets_chemin=None, screenshot_timeout=120_000, shadow_dom=False,
                     min_action_delay_ms=0, max_pages_par_run=0, max_actions_par_run=0,
                     t_debut=None, no_evaluer=False, operation_id=None, progress=None,
                     som_rafraichir=False, valeurs_secrets_resolues=None,
                     som_brut=False):
    from playwright.sync_api import TimeoutError as PWTimeoutError, Error as PWError

    # v1.24.0 — résolution SoM hybride par défaut : voie stable (data-dw-som-id)
    # si un marqueur existe, repli sur ré-indexation brute sinon, avec détection
    # de divergence (ROBUSTESSE_SCENARIOS_ET_SESSIONS.md §2). --som-brut force la
    # ré-indexation brute pure. --som-rafraichir (v1.17.0) est conservé comme
    # paramètre inerte : il sélectionnait _SOM_TROUVER_STABLE_JS, qui ne
    # résolvait rien sans capture SoM préalable dans le même scénario.
    if som_brut:
        _som_trouver = _SOM_TROUVER_JS_SHADOW if shadow_dom else _SOM_TROUVER_JS
    else:
        _som_trouver = _SOM_TROUVER_HYBRIDE_JS_SHADOW if shadow_dom else _SOM_TROUVER_HYBRIDE_JS
    # Boussole SoM (jamais silencieuse — même discipline que repli_js_utilise) :
    # som_resolution reflète la voie de la DERNIÈRE action SoM résolue ;
    # som_derives collecte tout id où voie stable et voie brute divergent.
    som_resolution = "brut" if som_brut else None
    som_derives = []

    def _resoudre_som(som_id):
        nonlocal som_resolution
        coord = page.evaluate(_som_trouver, som_id)
        if coord is not None:
            som_resolution = coord.get("resolution", "brut")
            if coord.get("derive"):
                som_derives.append(som_id)
        return coord

    intermediaires = []
    stream_captures = []
    # Audit 05/08/2026 (D-01, correctif de fond) : valeurs réellement résolues
    # par _resoudre_valeur_secrets durant ce run — l'appelant fournit
    # l'ensemble (créé avant l'appel) pour que les valeurs résolues restent
    # accessibles même si une exception interrompt executer_actions avant son
    # retour normal ; rédigées de la sortie JSON finale quel que soit le
    # canal où elles réapparaîtraient.
    if valeurs_secrets_resolues is None:
        valeurs_secrets_resolues = set()
    evaluations = []
    latences_actions = []
    stream_dir = None
    # run_id dérivé de operation_id (v1.16.0, item B) — jamais supprimé,
    # conserve son rôle historique (nom du sous-répertoire stream/).
    # Repli sur l'ancien comportement si appelé sans operation_id (compatibilité).
    run_id = operation_id or int(time.time())
    if modeles_appeles is None:
        modeles_appeles = []
    pages_visitees = 0
    actions_executees = 0
    plafond_atteint = None
    waf_bloquants = 0
    # v1.22.0, Axe B — dernier code HTTP capturé sur une action naviguer,
    # remonté en boussole à côté de session_derive. None si aucune action
    # naviguer n'a eu lieu (le code de la navigation initiale, capturé par
    # l'appelant, fait alors foi).
    dernier_code_http = None
    # v1.22.0, Axe A — reflète une escalade JS réellement survenue, jamais le
    # seul flag posé sur l'action (même discipline que stealth_actif corrigé
    # en v1.16.0/FR-79 : ne jamais confondre l'intention et l'application réelle).
    repli_js_utilise = False
    # Audit 06/08/2026 (F-17) : même discipline — reflète un appel réel au
    # mode claude de cliquer_visuel (capture envoyée hors machine, API
    # Anthropic), jamais le seul flag --llm claude qui peut n'avoir jamais
    # déclenché l'action.
    vision_externe_utilise = False
    if t_debut is None:
        t_debut = time.time()

    def _resoudre_intervalle(action):
        """Retourne (secondes>0) si capture périodique active, sinon 0."""
        val = action.get("interval_capture", interval_capture_default)
        try:
            iv = int(val)
        except (TypeError, ValueError):
            return 0
        return iv if iv > 0 else 0

    def _stream_dir_lazy():
        nonlocal stream_dir
        if stream_dir is None:
            stream_dir = _preparer_stream_dir(output_dir, run_id)
        return stream_dir

    # Indice d'agressivité (v1.16.0, item E) — réutilise la taxonomie
    # ACTIONS_ECRITURE déjà arbitrée pour est_mutatif (lib/journal.py),
    # source unique, pas de seconde liste à maintenir en synchronisation.
    from lib.journal import ACTIONS_ECRITURE
    actions_ecriture = 0

    for idx, a in enumerate(actions):
        t = a.get("type")
        iv = _resoudre_intervalle(a)
        _t0_latence = time.time()

        actions_executees += 1
        if max_actions_par_run > 0 and actions_executees > max_actions_par_run:
            plafond_atteint = "max_actions_par_run"
            actions_executees -= 1
            break
        if t in ACTIONS_ECRITURE:
            actions_ecriture += 1

        if t == "naviguer":
            pages_visitees += 1
            if max_pages_par_run > 0 and pages_visitees > max_pages_par_run:
                plafond_atteint = "max_pages_par_run"
                pages_visitees -= 1
                actions_executees -= 1
                break
            _valider_schema_url(a.get("url", ""))
            rep_nav = page.goto(a["url"], timeout=timeout)
            try:
                statut_nav = rep_nav.status if rep_nav else None
                dernier_code_http = statut_nav
                if _detecter_waf(statut_nav, page.title(), page.content()[:5000]):
                    waf_bloquants += 1
            except Exception:
                pass  # détection best-effort — ne doit jamais casser la navigation

        elif t == "attendre":
            if "selecteur" not in a:
                raise ValueError(
                    "attendre requiert un champ 'selecteur' (CSS). "
                    "Pour un délai fixe : {\"type\":\"pause\",\"ms\":N}"
                )
            if iv <= 0:
                page.wait_for_selector(a["selecteur"], timeout=timeout)
            else:
                t0 = time.time()
                deadline = t0 + timeout / 1000.0
                prochain_capture = t0 + iv
                while True:
                    restant_s = deadline - time.time()
                    if restant_s <= 0:
                        page.wait_for_selector(a["selecteur"], timeout=1)  # déclenche TimeoutError
                    fenetre_s = min(restant_s, max(prochain_capture - time.time(), 0.01))
                    try:
                        page.wait_for_selector(a["selecteur"], timeout=int(fenetre_s * 1000) or 1)
                        break
                    except PWTimeoutError:
                        now = time.time()
                        if now >= deadline:
                            raise
                        if now >= prochain_capture:
                            stream_captures.append(_capture_periodique(
                                page, _stream_dir_lazy(), idx, int((now - t0) * 1000),
                                screenshot_timeout=screenshot_timeout))
                            prochain_capture = now + iv

        elif t == "attendre_navigation":
            if iv <= 0:
                page.wait_for_load_state("networkidle", timeout=timeout)
            else:
                t0 = time.time()
                deadline = t0 + timeout / 1000.0
                prochain_capture = t0 + iv
                while True:
                    restant_s = deadline - time.time()
                    if restant_s <= 0:
                        page.wait_for_load_state("networkidle", timeout=1)
                    fenetre_s = min(restant_s, max(prochain_capture - time.time(), 0.01))
                    try:
                        page.wait_for_load_state("networkidle", timeout=int(fenetre_s * 1000) or 1)
                        break
                    except PWTimeoutError:
                        now = time.time()
                        if now >= deadline:
                            raise
                        if now >= prochain_capture:
                            stream_captures.append(_capture_periodique(
                                page, _stream_dir_lazy(), idx, int((now - t0) * 1000),
                                screenshot_timeout=screenshot_timeout))
                            prochain_capture = now + iv

        elif t == "remplir":
            valeur = a.get("valeur", "")
            valeur = _resoudre_valeur_secrets(a, valeur, page, secrets_chemin, "remplir", valeurs_secrets_resolues)
            page.locator(a["selecteur"]).fill(valeur, timeout=timeout)

        elif t == "cliquer":
            if a.get("repli_js"):
                # v1.22.0, Axe A — escalade à deux niveaux, distincte de
                # force: true (force-click natif Playwright, déjà insuffisant
                # seul — FR-81) : force-click d'abord, clic JS ensuite
                # seulement si le premier échoue par inaccessibilité/obstruction.
                # --no-evaluer est garanti inactif ici (rejet précoce plus haut).
                # PWError (classe mère) est capté, pas seulement PWTimeoutError :
                # vérifié empiriquement (fixture dialog_ferme.html) qu'un clic
                # avec force=True sur un élément sans boîte de mise en page
                # (<dialog> non ouvert) lève "Element is not visible", une
                # Error simple, jamais un TimeoutError — un except trop étroit
                # aurait laissé passer exactement le cas réel FN14.
                try:
                    page.locator(a["selecteur"]).click(
                        timeout=timeout,
                        force=bool(a.get("force", False)),
                    )
                except PWError:
                    page.eval_on_selector(a["selecteur"], "el => el.click()")
                    repli_js_utilise = True
            else:
                page.locator(a["selecteur"]).click(
                    timeout=timeout,
                    force=bool(a.get("force", False)),
                )

        elif t == "pause":
            duree_s = a.get("ms", 500) / 1000.0
            if iv <= 0:
                time.sleep(duree_s)
            else:
                t0 = time.time()
                deadline = t0 + duree_s
                prochain_capture = t0 + iv
                while True:
                    now = time.time()
                    if now >= deadline:
                        break
                    if now >= prochain_capture:
                        stream_captures.append(_capture_periodique(
                            page, _stream_dir_lazy(), idx, int((now - t0) * 1000)))
                        prochain_capture = now + iv
                    time.sleep(min(0.05, max(deadline - time.time(), 0)))

        elif t == "capturer":
            # Audit 05/08/2026 (D-07) : 'nom' concaténé sans filtrage permettait
            # une traversée de chemin (../../.., écrit hors du répertoire de
            # run isolé en 0700). Restreint à un jeu de caractères sûr.
            nom = re.sub(r"[^A-Za-z0-9_-]", "_", a.get("nom", "etape"))[:60]
            if a.get("som"):
                p, _, _ = _injecter_som(page, output_dir, f"capture_som_{nom}",
                                        screenshot_timeout=screenshot_timeout,
                                        shadow_dom=shadow_dom)
            else:
                p = chemin_png(output_dir, f"capture_{nom}")
                _prendre_capture(page, p, full_page=True, screenshot_timeout=screenshot_timeout)
            intermediaires.append(p)

        elif t == "cliquer_som":
            som_id = a.get("id")
            if som_id is None:
                raise ValueError("cliquer_som requiert un champ 'id'")
            coord = _resoudre_som(som_id)
            if coord is None:
                raise ValueError(f"cliquer_som : élément SoM {som_id!r} non trouvé sur la page")
            page.mouse.click(coord["x"], coord["y"])

        elif t == "remplir_som":
            som_id = a.get("id")
            valeur = a.get("valeur", "")
            if som_id is None:
                raise ValueError("remplir_som requiert un champ 'id'")
            valeur = _resoudre_valeur_secrets(a, valeur, page, secrets_chemin, "remplir_som", valeurs_secrets_resolues)
            coord = _resoudre_som(som_id)
            if coord is None:
                raise ValueError(f"remplir_som : élément SoM {som_id!r} non trouvé sur la page")
            if coord.get("tag", "").upper() == "SELECT":
                ok = page.evaluate("""(args) => {""" + _SOM_SELECTORS_JS + """
                    const vw = window.innerWidth, vh = window.innerHeight;
                    const items = [];
                    document.querySelectorAll(SELECTORS).forEach(el => {""" + _SOM_FILTRE_VISIBLE_JS + """
                        if (r.right<0||r.bottom<0||r.left>vw||r.top>vh) return;
                        items.push(el);
                    });
                    const el = items[args.id - 1];
                    if (!el || el.tagName !== 'SELECT') return false;
                    el.value = args.valeur;
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                    return true;
                }""", {"id": som_id, "valeur": str(valeur)})
                if not ok:
                    raise ValueError(f"remplir_som SELECT : élément SoM {som_id!r} introuvable")
            else:
                page.mouse.click(coord["x"], coord["y"])
                page.evaluate(
                    "() => { const el = document.activeElement;"
                    " if (el && 'value' in el) {"
                    "   el.value = '';"
                    "   el.dispatchEvent(new Event('input', {bubbles: true})); } }"
                )
                page.keyboard.type(valeur)

        elif t == "evaluer":
            if no_evaluer:
                raise ValueError("evaluer bloqué — --no-evaluer est actif sur ce run")
            script = a.get("script")
            if not script:
                raise ValueError("evaluer requiert un champ 'script' (chaîne JS pour page.evaluate)")
            valeur = page.evaluate(script)
            entree = {"index": idx, "script": script}
            try:
                json.dumps(valeur)
                entree["valeur"] = valeur
            except (TypeError, ValueError):
                entree["valeur"] = str(valeur)
                entree["serialisation"] = "str"
            evaluations.append(entree)

        elif t == "cliquer_visuel":
            description = a.get("description", "")
            if not description:
                raise ValueError("cliquer_visuel requiert un champ 'description'")

            # Capture intermédiaire pour la localisation
            tmp = chemin_png(output_dir, "vision_tmp")
            _prendre_capture(page, tmp, full_page=False, screenshot_timeout=screenshot_timeout)

            from lib.vision import localiser_element
            result = localiser_element(tmp, description, mode_llm)
            if mode_llm == "claude":
                vision_externe_utilise = True

            tag_modele = result.get("modele")
            if tag_modele and not any(
                m.get("_tag") == tag_modele for m in modeles_appeles
            ):
                modeles_appeles.append({
                    "_tag": tag_modele,
                    "mode_llm": mode_llm,
                    "role": "localisation_clic",
                })

            try:
                os.unlink(tmp)
            except OSError:
                pass

            if not result.get("found"):
                raise ValueError(
                    f"Élément non trouvé : {description!r} — "
                    f"{result.get('erreur', 'element_non_trouve')}"
                )

            page.mouse.click(result["x"], result["y"])

        elif t == "cliquer_iframe":
            # v1.17.0, item 4 — primitive scopée pour iframes cross-origin.
            # page.frame_locator() franchit la frontière Same-Origin Policy via
            # CDP (contrairement à une injection JS page-level, qui ne peut pas
            # atteindre le contenu d'un iframe cross-origin). Pas de numérotation
            # SoM à l'intérieur du frame — ciblage par sélecteur CSS explicite
            # uniquement (limite documentée, GUIDE_LLM_INTERACTIONS.md).
            if "selecteur" not in a:
                raise ValueError("cliquer_iframe requiert un champ 'selecteur' (cible dans le frame)")
            frame_locator = _resoudre_frame_locator(page, a, "cliquer_iframe")
            frame_locator.locator(a["selecteur"]).click(
                timeout=timeout, force=bool(a.get("force", False)),
            )

        elif t == "remplir_iframe":
            if "selecteur" not in a:
                raise ValueError("remplir_iframe requiert un champ 'selecteur' (cible dans le frame)")
            frame_locator = _resoudre_frame_locator(page, a, "remplir_iframe")
            valeur = a.get("valeur", "")
            valeur = _resoudre_valeur_secrets(a, valeur, page, secrets_chemin, "remplir_iframe", valeurs_secrets_resolues)
            frame_locator.locator(a["selecteur"]).fill(valeur, timeout=timeout)

        elif t == "defiler":
            px = a.get("px")
            sel = a.get("selecteur")
            if sel:
                page.evaluate(
                    "(s) => document.querySelector(s)?.scrollIntoView({block:'center',inline:'nearest'})",
                    sel,
                )
            elif px is not None:
                page.evaluate("(n) => window.scrollBy(0, n)", int(px))
            else:
                raise ValueError("defiler requiert 'px' (pixels relatifs) ou 'selecteur' (CSS scrollIntoView)")

        elif t == "attendre_mfa_ntfy":
            id_som = a.get("id_som")
            if id_som is None:
                raise ValueError("attendre_mfa_ntfy requiert un champ 'id_som'")
            timeout_mfa = int(a.get("timeout", 120))
            from lib import ntfy as ntfy_lib
            if secrets_chemin:
                from lib.repertoire_chiffre import lire_credential_fichier
                topic = lire_credential_fichier(secrets_chemin, "ntfy_topic", page.url)
            else:
                from lib.repertoire_chiffre import lire_credential, domaine_depuis_url
                topic = lire_credential(domaine_depuis_url(page.url), "ntfy_topic")
            ntfy_lib.publier_attente(topic, page.url)
            code = ntfy_lib.attendre_code(topic, timeout_s=timeout_mfa)
            # G-27 (CHANTIER_SANITISATION.md, LOT 5) : le code TOTP tapé au
            # clavier n'était jamais ajouté à valeurs_secrets_resolues — s'il
            # réapparaît ailleurs dans le résultat (evaluer, message d'erreur),
            # _rediger_valeurs_secrets ne le rédigeait pas.
            valeurs_secrets_resolues.add(str(code))
            coord = _resoudre_som(id_som)
            if coord is None:
                raise ValueError(f"attendre_mfa_ntfy : élément SoM {id_som!r} non trouvé")
            page.mouse.click(coord["x"], coord["y"])
            page.keyboard.press("Control+a")
            page.keyboard.type(str(code))

        elif t == "attendre_url":
            motif = a.get("motif", "")
            if not motif:
                raise ValueError(
                    "attendre_url requiert un champ 'motif' (sous-chaîne de l'URL attendue). "
                    "Exemple : {\"type\":\"attendre_url\",\"motif\":\"/dashboard\"}. "
                    "Attention : correspondance partielle — si l'URL courante contient déjà "
                    "le motif, l'action retourne immédiatement. Utiliser 'attendre_changement':true "
                    "pour attendre une navigation effective avant de tester le motif (FR-55)."
                )
            # FR-55 : si attendre_changement=true, attendre que l'URL quitte l'URL courante
            if a.get("attendre_changement", False):
                url_avant = page.url
                page.wait_for_function(
                    "url => window.location.href !== url",
                    arg=url_avant,
                    timeout=timeout,
                )
            page.wait_for_url(f"**{motif}**", timeout=timeout)

        elif t == "attendre_selecteur_present":
            if "selecteur" not in a:
                raise ValueError(
                    "attendre_selecteur_present requiert un champ 'selecteur' (CSS). "
                    "Attend que l'élément devienne visible (state=visible)."
                )
            page.wait_for_selector(a["selecteur"], state="visible", timeout=timeout)

        elif t == "attendre_absence":
            if "selecteur" not in a:
                raise ValueError(
                    "attendre_absence requiert un champ 'selecteur' (CSS). "
                    "Attend que l'élément disparaisse du DOM (state=detached)."
                )
            delai_initial = a.get("delai_initial_ms", 0)
            if delai_initial > 0:
                time.sleep(delai_initial / 1000.0)
            page.wait_for_selector(a["selecteur"], state="detached", timeout=timeout)

        elif t == "attendre_reseau_calme":
            # timeout_ms = durée max avant abandon (distinct des 500ms de silence interne networkidle)
            timeout_ms_local = int(a.get("timeout_ms", timeout))
            page.wait_for_load_state("networkidle", timeout=timeout_ms_local)

        elif t == "nettoyer_overlay":
            selecteur = a.get("selecteur")
            if not selecteur:
                raise ValueError(
                    "nettoyer_overlay requiert un champ 'selecteur' (CSS). "
                    "Pas d'auto-détection — déclarer explicitement les éléments à masquer. "
                    "Exemple : {\"type\":\"nettoyer_overlay\",\"selecteur\":\".cookie-banner\"}"
                )
            page.evaluate(
                """(sel) => {
                    document.querySelectorAll(sel).forEach(el => {
                        el.style.setProperty('visibility', 'hidden', 'important');
                    });
                }""",
                selecteur,
            )

        else:
            raise ValueError(f"Type d'action inconnu : {t!r}")

        # Profilage latence par action (v1.20.0) — même point d'atteinte que le
        # marqueur de progression ci-dessous : uniquement si l'action s'est
        # terminée sans exception et sans plafond de navigation atteint avant
        # dispatch. Coût de mesure nul (un time.time() déjà en cours).
        latences_actions.append({
            "index": idx,
            "type": t,
            "latence_ms": int((time.time() - _t0_latence) * 1000),
        })

        # Point de progression (v1.17.0, item 2) — atteint uniquement si l'action
        # ci-dessus s'est terminée sans exception. `progress` (dict mutable
        # fourni par l'appelant) reste donc figé sur le dernier état réussi si
        # une action suivante lève — support des checkpoints rpa.py.
        if progress is not None:
            progress["actions_executees"] = actions_executees
            progress["pages_visitees"] = pages_visitees

        if min_action_delay_ms > 0:
            time.sleep(min_action_delay_ms / 1000.0)

    respect = {
        "pages_visitees": pages_visitees,
        "actions_executees": actions_executees,
        "duree_totale_ms": int((time.time() - t_debut) * 1000),
    }
    if plafond_atteint:
        respect["plafond_atteint"] = plafond_atteint
    if waf_bloquants:
        respect["waf_bloquants"] = waf_bloquants
    if actions_executees > 0:
        respect["indice_agressivite"] = round(actions_ecriture / actions_executees, 3)
    # v1.24.0 — voie de résolution SoM réellement empruntée par la dernière
    # action SoM du run, et ids où stable/brut ont divergé. Absent si aucune
    # action SoM n'a été résolue (rien à signaler).
    if som_resolution is not None:
        respect["som_resolution"] = som_resolution
    if som_derives:
        respect["som_derive_detectee"] = som_derives
    return (intermediaires, stream_captures, evaluations, modeles_appeles, respect,
            latences_actions, dernier_code_http, repli_js_utilise,
            vision_externe_utilise)


# Audit 05/08/2026 (D-10) : constaté en production — diwall.conf
# absent, les plafonds valaient 0 (donc inactifs, max_* > 0 conditionne tout
# contrôle) et les runs s'exécutaient sans aucune limite ni délai minimal.
# La protection ne doit pas dépendre de la présence d'un fichier optionnel —
# mêmes valeurs que celles déjà proposées par diwall-sample.conf.
_NAVIGATION_DEFAUT = {
    "min_action_delay_ms": 800,
    "max_pages_par_run": 10,
    "max_actions_par_run": 30,
}


def _conf_navigation():
    """Lit les paramètres [navigation] depuis le fichier résolu par
    lib.repertoire_chiffre._lire_conf() (DIWALL_CONF, ou /opt/diwall/diwall.conf
    par défaut). Valeurs par défaut non nulles si absentes ou si diwall.conf
    lui-même est absent (D-10)."""
    try:
        from lib.repertoire_chiffre import _lire_conf
        conf = _lire_conf()
        nav = conf.get("navigation", {})
        return {
            "min_action_delay_ms": int(nav.get("min_action_delay_ms", _NAVIGATION_DEFAUT["min_action_delay_ms"])),
            "max_pages_par_run": int(nav.get("max_pages_par_run", _NAVIGATION_DEFAUT["max_pages_par_run"])),
            "max_actions_par_run": int(nav.get("max_actions_par_run", _NAVIGATION_DEFAUT["max_actions_par_run"])),
        }
    except Exception:
        return dict(_NAVIGATION_DEFAUT)


def main():
    args = parse_args()
    _CAPTURES_MASQUAGE_ECHOUE.clear()  # F-09 — état propre à chaque run
    _CHAMPS_REDIGES[0] = 0  # F-08 — état propre à chaque run

    # LOT 1e (CHANTIER_SANITISATION.md §1e) : --no-filtre-evaluer désactive la
    # neutralisation stdout du LOT 1 pour un run de debug explicite. Défaut :
    # filtre actif. Wrappers utilisés à la place d'un appel direct partout où
    # le LOT 1 a inséré une neutralisation, pour que le seul point de bascule
    # soit ce flag.
    _filtre_evaluer_actif = not args.no_filtre_evaluer

    def _filtrer_evaluer(valeur):
        return _neutraliser_valeur_evaluer(valeur) if _filtre_evaluer_actif else valeur

    def _filtrer_url(url):
        return _sanitiser_url_journal(url) if _filtre_evaluer_actif else url

    def _filtrer_url_query(url):
        return rediger_query_params_sensibles(url) if _filtre_evaluer_actif else url

    def _filtrer_chaine(texte):
        return sanitiser_urls_dans_chaine(texte) if _filtre_evaluer_actif else texte

    # ── --version (v1.18.0) : zéro Playwright, zéro autre argument requis ─────
    if args.version:
        print(json.dumps({"outil": "shot.py", "version": __version__}))
        sys.exit(0)

    import importlib.util
    if importlib.util.find_spec("playwright") is None:
        sys.stderr.write(
            "Diwall : module 'playwright' introuvable dans cet interpréteur.\n"
            "  Exécutez via le venv : /opt/diwall/venv/bin/python depuis /opt/diwall\n"
        )
        sys.exit(3)

    # ── Verrou de lecture obligatoire (v1.18.0) ────────────────────────────────
    # Avant tout autre traitement — y compris la validation --url. Exception
    # consciente à la doctrine d'additivité de Diwall (seule du projet) :
    # la documentation seule a échoué à se faire lire spontanément (retour
    # terrain répété, cf. docs/RADAR_MODELES.md).
    from lib.preflight_guide import guide_valide, erreur_guide_non_lu
    if not guide_valide(args.guide_version):
        print(json.dumps(erreur_guide_non_lu(__version__)), file=sys.stderr)
        sys.exit(1)

    # Interdire les core dumps pour ce processus : si Playwright crashe
    # pendant qu'un credential est en mémoire, le noyau ne peut pas écrire
    # un dump contenant le secret (spec 36_ §2.5).
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, resource.error):
        pass  # best-effort — certains environnements refusent, ce n'est pas bloquant

    # ── Identité de run unifiée (v1.16.0, item B) ─────────────────────────────
    # Générée avant toute autre chose : disponible dans la boussole de TOUTE
    # sortie JSON, y compris les échecs de validation précoces.
    operation_id = uuid.uuid4().hex[:12]

    # ── Résolution de --mode (avant toute validation) ─────────────────────────
    if args.mode == "fast":
        args.no_capture = True
        args.a11y = True
    # --mode full : aucun changement (comportement courant)

    # Isolation des temporaires par operation_id — uniquement si --output-dir
    # n'a pas été explicitement surchargé (le choix de l'opérateur est respecté).
    if args.output_dir == _OUTPUT_DIR_DEFAUT:
        args.output_dir = os.path.join(args.output_dir, operation_id)

    conf_nav = _conf_navigation()
    t0 = time.time()
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()

    from lib.profil_operateur import charger_profil
    profil = charger_profil()
    modeles_appeles = []

    # ── Validation ────────────────────────────────────────────────────────────
    if not args.url and not args.reprendre_session:
        print(json.dumps({
            "succes": False, "erreur": "argument_manquant",
            "message": "--url ou --reprendre-session est requis",
            "horodatage": horodatage,
            "boussole": _boussole(operation_id),
        }))
        sys.exit(1)

    # ── Chargement des actions ────────────────────────────────────────────────
    if args.reprendre_session:
        try:
            if args.action:
                parsed = json.loads(args.action)
                # Accepte un objet unique {"type":...} OU un tableau [{...},{...}]
                actions = parsed if isinstance(parsed, list) else [parsed]
                _valider_actions_secrets(actions)
            elif args.actions:
                # FR-54 : --actions (fichier) désormais supporté en Mode B
                actions = charger_actions(args.actions)
            else:
                actions = []
        except (json.JSONDecodeError, Exception) as e:
            print(json.dumps({
                "succes": False, "erreur": "action_invalide",
                "message": _filtrer_chaine(str(e)), "horodatage": horodatage,
                "boussole": _boussole(operation_id),
            }))
            sys.exit(1)
    else:
        try:
            actions = charger_actions(args.actions)
        except Exception as e:
            print(json.dumps({
                "succes": False, "erreur": "actions_invalides",
                "message": _filtrer_chaine(str(e)), "horodatage": horodatage,
                "boussole": _boussole(operation_id),
            }))
            sys.exit(1)

    # v1.19.0 — arbre de chaînage transmis par rpa.py (--chainage), plomberie
    # interne pour le journal. Best-effort : un JSON malformé ne bloque jamais
    # le run, exactement comme mode_conseille.
    try:
        chainage = json.loads(args.chainage) if args.chainage else None
    except (json.JSONDecodeError, TypeError):
        chainage = None

    # ── Validation schéma URL principale ────────────────────────────────────
    try:
        _valider_schema_url(args.url)
    except ValueError as e:
        print(json.dumps({
            "succes": False, "erreur": "url_scheme_interdit",
            "message": _filtrer_chaine(str(e)), "horodatage": horodatage, "boussole": _boussole(operation_id),
        }))
        sys.exit(2)

    # ── Validation --no-capture ──────────────────────────────────────────────
    if args.no_capture and args.som:
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--no-capture est incompatible avec --som : SoM requiert un PNG",
            "horodatage": horodatage, "boussole": _boussole(operation_id),
        }))
        sys.exit(1)
    if args.no_capture and any(a.get("type") == "capturer" for a in actions):
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--no-capture est incompatible avec l'action 'capturer' dans le scénario",
            "horodatage": horodatage, "boussole": _boussole(operation_id),
        }))
        sys.exit(1)

    # ── Validation --auth-indicator-negative (v1.15.2, item 2 / GL1) ─────────
    # Sans --auth-indicator, le bloc de vérification d'authentification est
    # entièrement sauté (voir main() plus bas) : --auth-indicator-negative
    # serait silencieusement ignoré. Rejet précoce, avant tout lancement de
    # Chromium — design orienté agent, zéro navigateur pour rien.
    if args.auth_indicator_negative and not args.auth_indicator:
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--auth-indicator-negative requiert --auth-indicator "
                       "(sans lui, l'indicateur négatif est ignoré silencieusement)",
            "horodatage": horodatage, "boussole": _boussole(operation_id),
        }))
        sys.exit(2)

    # ── Validation repli_js + --no-evaluer (v1.22.0, Axe A) ──────────────────
    # repli_js exécute du JS (element.click()) — --no-evaluer l'interdit sur ce
    # run. Rejet précoce, avant tout lancement de Chromium, même discipline que
    # --auth-indicator-negative ci-dessus : un abandon silencieux laisserait
    # l'agent face à l'échec du clic standard sans comprendre pourquoi son
    # repli_js n'a rien fait.
    if args.no_evaluer and any(
        a.get("type") == "cliquer" and a.get("repli_js") for a in actions
    ):
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "repli_js requiert que --no-evaluer soit inactif "
                       "(repli_js exécute du JS, --no-evaluer l'interdit sur ce run)",
            "horodatage": horodatage, "boussole": _boussole(operation_id),
        }))
        sys.exit(2)

    # ── Chemin de sortie ──────────────────────────────────────────────────────
    if args.output:
        sortie = args.output if os.path.splitext(args.output)[1] else args.output + ".png"
        # G-13 (CHANTIER_SANITISATION.md, LOT 5) : mode explicite plutôt que
        # l'umask par défaut — ne recrée pas un répertoire déjà existant
        # (mode appliqué à la création uniquement, chemin choisi par
        # l'opérateur : jamais de chmod rétroactif sur un répertoire
        # préexistant comme son $HOME). Limite connue, testée le 07/08/2026 :
        # si --output force la création de plusieurs niveaux imbriqués à la
        # fois, seul le niveau feuille reçoit ce mode (comportement natif
        # d'os.makedirs) — les intermédiaires nouvellement créés héritent de
        # l'umask. Sévérité réduite : seuls les noms des répertoires
        # resteraient visibles au groupe, jamais le contenu du PNG.
        os.makedirs(os.path.dirname(sortie) or ".", mode=0o700, exist_ok=True)
    else:
        sortie = chemin_png(args.output_dir)

    erreurs_js = []
    erreurs_console = []
    # v1.17.0, item 2 — rempli par executer_actions() au fil des actions
    # réussies ; lu dans le except si une action échoue en cours de route
    # (support des checkpoints rpa.py).
    progress = {}
    # Audit 05/08/2026 (D-01, correctif de fond) : créé ici, avant le bloc
    # try qui englobe executer_actions, pour rester lisible depuis le
    # handler d'erreur si une exception interrompt le run après qu'un
    # secret a déjà été résolu.
    valeurs_secrets_resolues = set()
    http_status = None
    # v1.22.0, Axe D — condition d'arrêt réellement appliquée à la navigation
    # initiale, posée seulement si elle diffère du défaut et que la navigation
    # a abouti. Initialisée ici pour rester lisible depuis le handler d'erreur.
    wait_until_applique = None
    url_finale = args.url or ""
    url_cible = url_finale  # pour le handler d'erreur

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)

            # ── Contexte navigateur ───────────────────────────────────────────
            derive_session = None
            session = None
            if args.reprendre_session:
                session = _charger_session(args.reprendre_session)
                viewport = session.get("viewport", {"width": args.largeur, "height": args.hauteur})
                url_cible = args.url if args.url else session["url"]
                if not args.url:
                    # Audit 06/08/2026 (F-15) : args.url est déjà validé plus
                    # haut (schéma + userinfo), mais quand --reprendre-session
                    # est utilisé sans --url, url_cible vient de session["url"]
                    # — seul chemin de navigation qui échappait au contrôle.
                    try:
                        _valider_schema_url(url_cible)
                    except ValueError as e:
                        print(json.dumps({
                            "succes": False, "erreur": "url_scheme_interdit",
                            "message": _filtrer_chaine(str(e)), "horodatage": horodatage,
                            "boussole": _boussole(operation_id),
                        }))
                        sys.exit(2)
            else:
                viewport = {"width": args.largeur, "height": args.hauteur}
                url_cible = args.url

            # ── Identifiants HTTP Basic Auth (v1.21.0) ─────────────────────────
            # Résolus avant new_context() — le challenge Basic Auth se joue au
            # niveau du protocole, avant tout rendu de page. 'origin' est
            # obligatoire : sans lui, Chromium peut renvoyer ces identifiants à
            # toute origine tierce chargée dans le même contexte (CDN, tracker,
            # redirection) — fuite réelle, pas théorique (Playwright 1.61.0
            # vérifié supporter {username, password, origin, send}).
            # 'send: "unauthorized"' : envoi uniquement après un vrai 401, jamais
            # préventif. Repli documenté si un reverse-proxy n'émet pas de 401
            # propre : 'send: "always"', qui reste scopé par 'origin' — jamais un
            # header Authorization fait main, qui contournerait ce scoping.
            new_context_kwargs = {}
            if args.http_credentials:
                from urllib.parse import urlparse
                secrets_chemin = getattr(args, "secrets", None)
                # Clés dédiées http_username/http_password en priorité — nécessaires
                # si la même cible a aussi un login applicatif distinct (Basic Auth
                # réseau devant un formulaire web, ex. Caddy devant Grafana). Repli
                # sur username/password (v1.21.0, trouvé en test réel contre une
                # cible Basic Auth réelle) : la plupart des fichiers d'identifiants
                # existants n'ont qu'une paire de clés, pas de raison de forcer un
                # renommage pour le cas le plus courant.
                if secrets_chemin:
                    from lib.repertoire_chiffre import lire_credential_fichier
                    # Audit 05/08/2026 (C-03), site retrouvé lors de la revue de
                    # couverture du 05/08/2026 : url_cible plutôt que page.url —
                    # ce bloc s'exécute avant new_context(), page n'existe pas
                    # encore. url_cible est la même source que 'origin' ci-dessous.
                    try:
                        http_username = lire_credential_fichier(secrets_chemin, "http_username", url_cible)
                        http_password = lire_credential_fichier(secrets_chemin, "http_password", url_cible)
                    except KeyError:
                        http_username = lire_credential_fichier(secrets_chemin, "username", url_cible)
                        http_password = lire_credential_fichier(secrets_chemin, "password", url_cible)
                else:
                    from lib.repertoire_chiffre import lire_credential, domaine_depuis_url
                    _domaine = domaine_depuis_url(url_cible)
                    try:
                        http_username = lire_credential(_domaine, "http_username")
                        http_password = lire_credential(_domaine, "http_password")
                    except KeyError:
                        http_username = lire_credential(_domaine, "username")
                        http_password = lire_credential(_domaine, "password")
                _parsed = urlparse(url_cible)
                new_context_kwargs["http_credentials"] = {
                    "username": http_username,
                    "password": http_password,
                    "origin": f"{_parsed.scheme}://{_parsed.netloc}",
                    "send": "unauthorized",
                }

            # Langue déclarée : sans `locale`, Chromium n'envoie aucun
            # Accept-Language alors que navigator.language en porte une — le
            # serveur et la page voient deux identités différentes.
            new_context_kwargs["locale"] = locale_navigateur(os.environ)

            if args.reprendre_session:
                ctx = browser.new_context(
                    storage_state=session["storage_state"],
                    viewport=viewport,
                    ignore_https_errors=args.ignore_tls_errors,
                    **new_context_kwargs,
                )
            else:
                ctx = browser.new_context(
                    viewport=viewport,
                    ignore_https_errors=args.ignore_tls_errors,
                    **new_context_kwargs,
                )

            page = ctx.new_page()
            # Correctif compatibilité playwright-stealth 2.x (v1.16.0) : l'API
            # 1.x (fonction stealth_sync) a été retirée au profit d'une classe
            # Stealth().apply_stealth_sync(page). L'ancien appel échouait à
            # l'import et --stealth se dégradait silencieusement en no-op —
            # navigator.webdriver restait exposé malgré le flag actif, et la
            # boussole affichait quand même stealth_actif: true (voir plus bas).
            stealth_applique = False
            if args.stealth:
                try:
                    from playwright_stealth import Stealth
                    Stealth().apply_stealth_sync(page)
                    stealth_applique = True
                except Exception as e:
                    sys.stderr.write(
                        f"playwright-stealth indisponible ou incompatible — "
                        f"--stealth ignoré ({type(e).__name__}: {e})\n"
                    )
            page.on("pageerror", lambda err: erreurs_js.append(str(err)))
            # v1.16.0, item D — messages de console de niveau erreur, distincts
            # des exceptions non interceptées (erreurs_js/pageerror). Complète
            # sans remplacer : un site peut avoir des erreurs console (requêtes
            # réseau échouées, avertissements applicatifs) sans lever d'exception JS.
            page.on("console", lambda msg: (
                erreurs_console.append(msg.text) if msg.type == "error" else None
            ))

            # ── Navigation ────────────────────────────────────────────────────
            # v1.22.0, Axe D — la condition d'arrêt est paramétrable, défaut
            # networkidle inchangé. Ne s'applique qu'ici : l'action `naviguer`
            # de executer_actions() garde le défaut Playwright ("load"), sans
            # override — asymétrie assumée, aucun second cas d'usage réel ne
            # justifie de l'étendre à ce stade.
            rep = page.goto(url_cible, timeout=args.timeout, wait_until=args.wait_until)
            if rep:
                http_status = rep.status
            url_finale = page.url
            # Signal boussole posé après coup, sur navigation réellement aboutie
            # par une condition différente du défaut — jamais sur le seul flag CLI
            # (précédent stealth_actif, corrigé en v1.16.0).
            if args.wait_until != "networkidle":
                wait_until_applique = args.wait_until

            # ── Détection WAF sur la navigation initiale (v1.16.0, item C) ────
            waf_initial = False
            try:
                waf_initial = _detecter_waf(http_status, page.title(), page.content()[:5000])
            except Exception:
                pass

            # ── Challenge HTTP Basic Auth non résolu (v1.21.0) ────────────────
            # Signal distinct du WAF — c'est une authentification réseau, pas un
            # blocage anti-bot. Pointe explicitement vers --http-credentials
            # plutôt que de laisser l'agent face à un 401 opaque.
            http_auth_requise = (http_status == 401)

            # ── Détection de dérive de session (lot 8.5) ──────────────────────
            # Comparaison sur l'URL effective après navigation (post-normalisation)
            # afin d'éviter les faux positifs liés au slash terminal ou aux
            # redirections HTTP transparentes.
            if args.reprendre_session and session is not None:
                derive_session = _detecter_derive_session(session, url_finale)

            if args.attendre_selecteur:
                page.wait_for_selector(args.attendre_selecteur, timeout=args.timeout)

            # ── Actions ───────────────────────────────────────────────────────
            # v1.17.0, item 2 — try/except localisé à ce seul appel : si une
            # action échoue en cours de route, ctx/page sont encore vivants ici
            # (avant la fermeture implicite par la sortie du bloc `with`) —
            # dernière occasion de sauvegarder la session pour un checkpoint.
            try:
                (interm, stream_captures, evaluations, modeles_appeles, respect,
                 latences_actions, dernier_code_http_actions, repli_js_utilise,
                 vision_externe_utilise) = executer_actions(
                    page, actions, args.output_dir, args.timeout, args.llm,
                    interval_capture_default=args.interval_capture,
                    modeles_appeles=modeles_appeles,
                    secrets_chemin=getattr(args, "secrets", None),
                    screenshot_timeout=args.screenshot_timeout,
                    shadow_dom=args.shadow_dom,
                    min_action_delay_ms=conf_nav["min_action_delay_ms"],
                    max_pages_par_run=conf_nav["max_pages_par_run"],
                    max_actions_par_run=conf_nav["max_actions_par_run"],
                    t_debut=t0,
                    no_evaluer=args.no_evaluer,
                    operation_id=operation_id,
                    progress=progress,
                    som_rafraichir=args.som_rafraichir,
                    valeurs_secrets_resolues=valeurs_secrets_resolues,
                    som_brut=args.som_brut,
                )
            except Exception:
                if args.sauver_session:
                    try:
                        _sauver_session(ctx, page, args.sauver_session,
                                        {"width": args.largeur, "height": args.hauteur})
                    except Exception:
                        pass  # best-effort — ne jamais masquer l'erreur originale
                raise
            if waf_initial:
                respect["waf_bloquants"] = respect.get("waf_bloquants", 0) + 1
            url_finale = page.url  # mise à jour après actions

            # ── Capture finale ────────────────────────────────────────────────
            if not args.no_capture:
                _prendre_capture(page, sortie, full_page=True, screenshot_timeout=args.screenshot_timeout)

            # ── SoM ───────────────────────────────────────────────────────────
            capture_som, elements_som, hors_vp_som = None, [], 0
            if args.som and not args.no_capture:
                capture_som, elements_som, hors_vp_som = _injecter_som(
                    page, args.output_dir, screenshot_timeout=args.screenshot_timeout,
                    shadow_dom=args.shadow_dom)

            # ── A11y ──────────────────────────────────────────────────────────
            a11y_tree, a11y_redaction_echouee = (
                _snapshot_a11y(page) if args.a11y else (None, False)
            )

            # ── Auth status ───────────────────────────────────────────────────
            auth_status = None
            if args.auth_indicator:
                try:
                    visible = page.locator(args.auth_indicator).is_visible()
                    if visible and args.auth_indicator_negative:
                        neg_visible = page.locator(args.auth_indicator_negative).is_visible()
                        visible = not neg_visible
                    auth_status = "active" if visible else "inactive"
                except Exception:
                    auth_status = "inactive"

            # Audit 05/08/2026 (D-05) : un indicateur d'authentification actif
            # annule une dérive de session résiduelle — les deux signaux ne
            # doivent jamais se contredire dans le même objet de sortie.
            if auth_status == "active" and derive_session:
                derive_session = None

            # ── Sauvegarde session ────────────────────────────────────────────
            session_file = None
            if args.sauver_session:
                _sauver_session(ctx, page, args.sauver_session,
                                {"width": args.largeur, "height": args.hauteur})
                session_file = args.sauver_session

            # ── Stats DOM (--no-capture) ──────────────────────────────────────
            dom_stats = None
            if args.no_capture:
                try:
                    dom_stats = page.evaluate(_DOM_STATS_JS)
                except Exception:
                    pass

            # ── Titre de page (boussole enrichie) ─────────────────────────────
            titre_page = ""
            try:
                titre_page = page.title()
            except Exception:
                pass

            browser.close()

        # LOT 1 (CHANTIER_SANITISATION.md §1b) : calculée une seule fois, à la
        # sortie de la session Playwright, réutilisée pour tous les champs
        # stdout qui exposent cette URL — le journal applique déjà ce filtre
        # depuis lib/journal.py, stdout ne le faisait pas (G-01 à G-08).
        url_finale_sanitisee = _filtrer_url(url_finale)

        result = {
            "succes": True,
            "http_status": http_status,
            "url_finale": url_finale_sanitisee,
            "erreurs_js": [_filtrer_evaluer(x) for x in erreurs_js],
            "erreurs_console": [_filtrer_evaluer(x) for x in erreurs_console],
            "duree_ms": int((time.time() - t0) * 1000),
            "horodatage": horodatage,
            "diwall_meta": _construire_diwall_meta(
                profil, horodatage, modeles_appeles, url_finale_sanitisee,
            ),
        }
        if not args.no_capture:
            result["capture"] = sortie
        if args.no_capture and dom_stats is not None:
            result["dom_stats"] = dom_stats
        if auth_status is not None:
            result["auth_status"] = auth_status
        if interm:
            result["captures_intermediaires"] = interm
        if stream_captures:
            result["stream_captures"] = stream_captures
        if evaluations:
            result["evaluations"] = [
                {**e, "valeur": _filtrer_evaluer(e.get("valeur"))}
                for e in evaluations
            ]
        if capture_som:
            result["capture_som"] = capture_som
            result["elements_som"] = elements_som
            if hors_vp_som > 0:
                result["som_hors_viewport"] = hors_vp_som
                result["avertissement_scroll"] = (
                    f"{hors_vp_som} élément(s) interactif(s) hors viewport "
                    "— utilisez defiler avant cliquer_som"
                )
        if a11y_tree is not None:
            result["a11y_tree"] = a11y_tree
        if session_file:
            result["session_file"] = session_file
        # Note derive_session (§1b) : url_sauvegardee/url_reprise gardent leur
        # query brute côté fichier de session (jamais touché ici) — le signal
        # de dérive (`?vue=login` remplaçant `?vue=domaine`) en dépend
        # (_detecter_derive_session, D-05/E-03). Seule la sortie stdout est
        # rédigée : rediger_query_params_sensibles rédige la valeur des
        # paramètres sensibles (token, code, state...) et conserve le nom du
        # paramètre et le signal fonctionnel — _sanitiser_url_journal, qui
        # supprime toute la query, casserait ce signal (variante FR-55).
        # Rédigé une seule fois : réutilisé aux deux points de sortie stdout
        # (result["derive_session"] et boussole.session_derive plus bas), pour
        # ne pas laisser fuir en clair sous une clé la valeur rédigée sous l'autre.
        derive_session_sanitisee = None
        if derive_session:
            derive_session_sanitisee = {
                **derive_session,
                "url_sauvegardee": _filtrer_url_query(derive_session["url_sauvegardee"]),
                "url_reprise": _filtrer_url_query(derive_session["url_reprise"]),
            }
            result["derive_session"] = derive_session_sanitisee
        result["boussole"] = _boussole(operation_id)
        if not _filtre_evaluer_actif:
            result["boussole"]["filtre_evaluer_actif"] = False
        result["boussole"]["url_courante"] = url_finale_sanitisee
        result["boussole"]["titre_page"] = titre_page
        # v1.22.0, Axe B — toujours présent (contrairement à session_derive,
        # conditionnel à --reprendre-session) : reflète la dernière navigation
        # du run (une action naviguer si le scénario en contient une, sinon la
        # navigation initiale). Sur un run multi-navigations, ne présume pas
        # laquelle explique une dérive éventuelle — voir GUIDE_LLM_SESSIONS.md.
        result["boussole"]["dernier_code_http"] = (
            dernier_code_http_actions if dernier_code_http_actions is not None else http_status
        )
        if args.shadow_dom:
            result["boussole"]["shadow_dom_actif"] = True
        # v1.24.0 — résolution SoM hybride par défaut ; la voie réellement
        # empruntée est portée par boussole.respect.som_resolution (et
        # som_derive_detectee en cas de divergence stable/brut). Ce drapeau
        # signale seulement l'échappatoire explicite vers la ré-indexation brute.
        if args.som_brut:
            result["boussole"]["som_brut_actif"] = True
        if stealth_applique:
            result["boussole"]["stealth_actif"] = True
        # v1.21.0 — jamais conditionné au seul flag CLI (précédent stealth_actif
        # corrigé en v1.16.0/FR-79) : le flag doit être actif ET la navigation
        # initiale ne doit pas s'être terminée en 401, preuve que les
        # identifiants ont réellement résolu le challenge.
        if args.http_credentials and not http_auth_requise:
            result["boussole"]["http_credentials_actif"] = True
        if http_auth_requise:
            result["boussole"]["http_auth_requise"] = True
        if args.ignore_tls_errors:
            result["boussole"]["tls_errors_ignored"] = True
        if args.ignorer_waf:
            result["boussole"]["waf_ignore_actif"] = True
        if repli_js_utilise:
            result["boussole"]["repli_js_utilise"] = True
        if vision_externe_utilise:
            result["boussole"]["vision_externe"] = True
        # v1.22.0, Axe D — porte la valeur employée, pas un booléen : un agent
        # qui relit une sortie doit savoir sous quelle condition la page a été
        # jugée prête. Absente quand la navigation a suivi le défaut.
        if wait_until_applique is not None:
            result["boussole"]["wait_until"] = wait_until_applique
        result["respect"] = respect
        result["boussole"]["respect"] = respect
        result["latences_actions"] = latences_actions
        if args.reprendre_session and derive_session_sanitisee is not None:
            result["boussole"]["session_derive"] = derive_session_sanitisee
        if auth_status is not None:
            result["boussole"]["auth_status"] = auth_status
        if hors_vp_som > 0:
            result["boussole"]["som_hors_viewport"] = hors_vp_som
        if a11y_redaction_echouee:
            result["boussole"]["a11y_redaction_echouee"] = True
        if _CAPTURES_MASQUAGE_ECHOUE:
            result["boussole"]["capture_masquage_echoue"] = True
        try:
            result["etat"] = _construire_etat(
                auth_status, respect, derive_session, erreurs_js,
                waf_bloquants=respect.get("waf_bloquants"),
                erreurs_console=erreurs_console,
                ignorer_waf=args.ignorer_waf,
                mode_conseille=_calculer_mode_conseille(url_finale_sanitisee),
            )
        except Exception:
            pass  # etat est un confort de lecture, jamais un bloquant (item A)
        result = _rediger_valeurs_secrets(result, valeurs_secrets_resolues)
        if _CHAMPS_REDIGES[0]:
            result["boussole"]["champs_rediges"] = _CHAMPS_REDIGES[0]
        print(json.dumps(result, ensure_ascii=False))
        _journaliser_run(result, actions, args.intention, url_finale_sanitisee, "succes",
                         operation_id=operation_id, source_scenario=args.source_scenario,
                         chainage=chainage, secret_resolu=bool(valeurs_secrets_resolues),
                         secrets_chemin=getattr(args, "secrets", None))
        _nettoyer_session_ephemere(
            getattr(args, "reprendre_session", None),
            explicitement_demandee=bool(args.sauver_session),
        )

    except Exception as e:
        # Répertoire chiffré fermé : erreur distincte, pas de tentative Playwright (inutile),
        # code de sortie 42 par symétrie avec Phase 7bis.
        from lib.repertoire_chiffre import SecretsFermesError
        if isinstance(e, SecretsFermesError):
            # LOT 1 (§1b) : cette branche reçoit url_cible (args.url d'origine),
            # pas url_finale — calculée localement, pas de variable de la
            # branche succès (qui peut ne pas exister si l'échec est survenu
            # avant sa construction).
            url_cible_sanitisee = _filtrer_url(url_cible)
            result = {
                "succes": False,
                "erreur": "secrets_fermes",
                "message": _filtrer_chaine(str(e)),
                "code_sortie_recommande": SecretsFermesError.CODE_SORTIE,
                "http_status": http_status,
                "duree_ms": int((time.time() - t0) * 1000),
                "horodatage": horodatage,
                "diwall_meta": _construire_diwall_meta(
                    profil, horodatage, modeles_appeles, url_cible_sanitisee,
                ),
                "boussole": _boussole(operation_id),
            }
            if not _filtre_evaluer_actif:
                result["boussole"]["filtre_evaluer_actif"] = False
            result = _rediger_valeurs_secrets(result, valeurs_secrets_resolues)
            if _CHAMPS_REDIGES[0]:
                result["boussole"]["champs_rediges"] = _CHAMPS_REDIGES[0]
            print(json.dumps(result, ensure_ascii=False))
            # Audit 06/08/2026 (F-03) : erreur= reprend result["message"], déjà
            # rédigé ci-dessus par _rediger_valeurs_secrets (credentials) et
            # sanitiser_urls_dans_chaine (URLs, LOT 1 §1b) — reconstruire
            # séparément depuis str(e) aurait écrit sur le canal persistant
            # (journal) une valeur que le canal éphémère (stdout) venait de
            # rédiger, exactement l'asymétrie que ces correctifs ferment.
            _journaliser_run(result, actions, args.intention, url_cible, "echec",
                             erreur=f"SecretsFermesError: {result['message']}", operation_id=operation_id,
                             source_scenario=args.source_scenario, chainage=chainage,
                             secret_resolu=bool(valeurs_secrets_resolues),
                             secrets_chemin=getattr(args, "secrets", None))
            sys.exit(SecretsFermesError.CODE_SORTIE)

        capture_echec = None
        try:
            from playwright.sync_api import sync_playwright
            echec = chemin_png(args.output_dir, "echec")
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True)
                pg = b.new_context(
                    ignore_https_errors=args.ignore_tls_errors,
                    locale=locale_navigateur(os.environ),
                ).new_page()
                pg.goto(url_cible, timeout=5000)
                _prendre_capture(pg, echec, full_page=False)
                b.close()
            capture_echec = echec
        except Exception:
            pass

        # LOT 1 (§1b) : recalculée localement, ne réutilise pas la variable de
        # la branche succès — l'exception peut survenir avant sa construction,
        # avant la sortie du bloc `with sync_playwright()`.
        url_finale_sanitisee = _filtrer_url(url_finale)

        result = {
            "succes": False,
            "erreur": type(e).__name__,
            "message": _filtrer_chaine(str(e)),
            "http_status": http_status,
            "duree_ms": int((time.time() - t0) * 1000),
            "horodatage": horodatage,
            "diwall_meta": _construire_diwall_meta(
                profil, horodatage, modeles_appeles, url_finale_sanitisee,
            ),
        }
        if capture_echec:
            result["capture_echec"] = capture_echec
        # v1.17.0, item 2 — progression partielle pour les checkpoints rpa.py.
        # Absent si l'échec est survenu avant tout appel executer_actions()
        # (ex. répertoire chiffré fermé, URL invalide) : progress reste vide dans ce cas.
        if progress.get("actions_executees") is not None:
            result["actions_executees_avant_echec"] = progress["actions_executees"]
            result["pages_visitees_avant_echec"] = progress.get("pages_visitees", 0)
        result["boussole"] = _boussole(operation_id)
        if not _filtre_evaluer_actif:
            result["boussole"]["filtre_evaluer_actif"] = False
        result = _rediger_valeurs_secrets(result, valeurs_secrets_resolues)
        if _CHAMPS_REDIGES[0]:
            result["boussole"]["champs_rediges"] = _CHAMPS_REDIGES[0]
        print(json.dumps(result, ensure_ascii=False))
        # Audit 06/08/2026 (F-03) : erreur= reprend result["message"] déjà
        # rédigé par _rediger_valeurs_secrets (credentials) et
        # sanitiser_urls_dans_chaine (URLs, LOT 1 §1b) — voir le commentaire
        # jumeau sur la branche SecretsFermesError.
        _journaliser_run(result, actions, args.intention, url_cible, "echec",
                         erreur=f"{result['erreur']}: {result['message']}", operation_id=operation_id,
                         source_scenario=args.source_scenario, chainage=chainage,
                         secret_resolu=bool(valeurs_secrets_resolues),
                         secrets_chemin=getattr(args, "secrets", None))
        _nettoyer_session_ephemere(
            getattr(args, "reprendre_session", None),
            explicitement_demandee=bool(getattr(args, "sauver_session", None)),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
