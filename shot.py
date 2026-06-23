#!/opt/diwall/venv/bin/python3
import argparse
import getpass
import json
import os
import resource
import socket
import sys
import time
from datetime import datetime, timezone

__version__ = "1.12.0"

# Permet d'importer lib/ depuis le même répertoire que shot.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _boussole():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = ""
    return {
        "utilisateur": os.getenv("USER", ""),
        "ip_locale": ip,
        "repertoire": os.getcwd(),
    }

# ── Set-of-Mark ───────────────────────────────────────────────────────────────
_SOM_INJECTER_JS = """() => {
    const SELECTORS = [
        'a[href]', 'button', 'input:not([type="hidden"])',
        'select', 'textarea', 'summary',
        '[role="button"]', '[role="link"]', '[role="tab"]',
        '[role="checkbox"]', '[role="menuitem"]', '[role="radio"]',
        '[role="combobox"]', '[role="spinbutton"]', '[role="searchbox"]'
    ].join(',');
    const vw = window.innerWidth, vh = window.innerHeight;
    const container = document.createElement('div');
    container.id = '__som__';
    container.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;pointer-events:none;z-index:2147483647;overflow:visible;';
    document.body.appendChild(container);
    const items = [];
    let num = 1;
    document.querySelectorAll(SELECTORS).forEach(el => {
        let p = el.parentElement; while (p) { if (p.tagName === 'DIALOG' && !p.hasAttribute('open')) return; p = p.parentElement; }
        const s = window.getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
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
        items.push({
            id: num, tag: el.tagName,
            role: el.getAttribute('role') || el.tagName.toLowerCase(),
            texte: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 60),
            type: el.type || null,
        });
        num++;
    });
    return items;
}"""

_SOM_RETIRER_JS = "() => { const el = document.getElementById('__som__'); if (el) el.remove(); }"

_SOM_COMPTER_HORS_VIEWPORT_JS = """() => {
    const SELECTORS = [
        'a[href]', 'button', 'input:not([type="hidden"])',
        'select', 'textarea', 'summary',
        '[role="button"]', '[role="link"]', '[role="tab"]',
        '[role="checkbox"]', '[role="menuitem"]', '[role="radio"]',
        '[role="combobox"]', '[role="spinbutton"]', '[role="searchbox"]'
    ].join(',');
    const vw = window.innerWidth, vh = window.innerHeight;
    let n = 0;
    document.querySelectorAll(SELECTORS).forEach(el => {
        let p = el.parentElement; while (p) { if (p.tagName === 'DIALOG' && !p.hasAttribute('open')) return; p = p.parentElement; }
        const s = window.getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
        if (r.right >= 0 && r.bottom >= 0 && r.left <= vw && r.top <= vh) return;
        n++;
    });
    return n;
}"""

# Même filtrage que l'injection SoM, retourne les coordonnées du centre de l'élément N
_SOM_TROUVER_JS = """(id) => {
    const SELECTORS = [
        'a[href]', 'button', 'input:not([type="hidden"])',
        'select', 'textarea', 'summary',
        '[role="button"]', '[role="link"]', '[role="tab"]',
        '[role="checkbox"]', '[role="menuitem"]', '[role="radio"]',
        '[role="combobox"]', '[role="spinbutton"]', '[role="searchbox"]'
    ].join(',');
    const vw = window.innerWidth, vh = window.innerHeight;
    const items = [];
    document.querySelectorAll(SELECTORS).forEach(el => {
        let p = el.parentElement; while (p) { if (p.tagName === 'DIALOG' && !p.hasAttribute('open')) return; p = p.parentElement; }
        const s = window.getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
        if (r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) return;
        items.push(el);
    });
    const el = items[id - 1];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), tag: el.tagName};
}"""

# ── Sécurité visuelle — masquage des champs sensibles ────────────────────────
_MASQUER_SECRETS_JS = """() => {
    var SENS = [
        'input[type="password"]',
        'input[autocomplete="current-password"]',
        'input[autocomplete="new-password"]',
        'input[autocomplete*="password"]'
    ].join(',');
    document.querySelectorAll(SENS).forEach(function(f) {
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


def _injecter_som(page, output_dir, nom="state_som", screenshot_timeout=120_000):
    """Injecte le Set-of-Mark, capture la vue annotée, nettoie le DOM.

    Retourne (chemin_som, elements_som, hors_vp) où hors_vp est le
    nombre d'éléments interactifs présents dans le DOM mais hors viewport.
    """
    elements = page.evaluate(_SOM_INJECTER_JS)
    chemin_som = chemin_png(output_dir, nom)
    page.evaluate(_MASQUER_SECRETS_JS)
    try:
        page.screenshot(path=chemin_som, full_page=False, timeout=screenshot_timeout)
    finally:
        page.evaluate(_RESTAURER_SECRETS_JS)
    page.evaluate(_SOM_RETIRER_JS)
    hors_vp = page.evaluate(_SOM_COMPTER_HORS_VIEWPORT_JS)
    return chemin_som, elements, hors_vp


# ── Arbre d'accessibilité (A11y) ──────────────────────────────────────────────

def _snapshot_a11y(page):
    """Retourne le snapshot ARIA de la page (format texte YAML-like, Playwright 1.9+).
    Inclut rôles, noms, URLs des liens. Retourne None si non disponible."""
    try:
        return page.aria_snapshot()
    except Exception:
        return None


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


def _nettoyer_session_ephemere(chemin_session, explicitement_demandee):
    """Désactivé (FR-74/FR-75) — ne supprime plus le fichier de session.

    Ancien comportement : supprimait --reprendre-session si --sauver-session
    était absent → FileNotFoundError sur les appels successifs. Le fichier
    appartient à l'opérateur ; shot.py n'a pas à le détruire.
    """


def _journaliser_run(result, actions, intention, cible_url, resultat, erreur=None):
    """Consigne le run dans le journal d'opérations (v1.4). Best-effort.

    N'altère jamais la sortie ni le code de retour de shot.py : toute
    erreur de journalisation est avalée par lib/journal lui-même.
    """
    try:
        from lib import journal
    except Exception:
        return
    captures = []
    if result.get("capture"):
        captures.append(result["capture"])
    for c in result.get("captures_intermediaires") or []:
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
    # Écriture atomique : évite la corruption du fichier lors d'appels rapides successifs
    chemin_tmp = chemin + ".tmp"
    with open(chemin_tmp, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    os.replace(chemin_tmp, chemin)


def _charger_session(chemin):
    """Charge une session Diwall depuis un fichier JSON.

    Émet un warning unique sur stderr si le fichier est au format legacy
    (sans diwall_meta) : la détection de dérive sera désactivée pour ce run.
    """
    global _legacy_session_warned
    with open(chemin, encoding="utf-8") as f:
        session = json.load(f)
    if "diwall_meta" not in session and not _legacy_session_warned:
        print(
            f"⚠ Session legacy détectée (sans diwall_meta) : "
            f"{chemin} — détection de dérive d'URL désactivée pour ce fichier.",
            file=sys.stderr,
        )
        _legacy_session_warned = True
    return session


def _detecter_derive_session(session, url_cible_reprise):
    """Compare l'URL au moment de la sauvegarde à l'URL au moment de la reprise.

    Retourne un dict prêt à injecter sous la clé `derive_session` du JSON
    de sortie si une divergence est détectée, ou None sinon (URLs identiques,
    session legacy, ou URL manquante).
    """
    meta = session.get("diwall_meta")
    if not meta:
        return None
    url_sauvegardee = meta.get("url_au_moment_sauvegarde")
    if not url_sauvegardee or not url_cible_reprise:
        return None
    if url_sauvegardee == url_cible_reprise:
        return None
    return {
        "url_sauvegardee": url_sauvegardee,
        "url_reprise": url_cible_reprise,
        "avertissement": _AVERTISSEMENT_DERIVE,
    }


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
    p.add_argument("--output-dir", dest="output_dir", default="/tmp/diwall",
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
    return p.parse_args()


def chemin_png(repertoire, prefixe="capture"):
    os.makedirs(repertoire, mode=0o700, exist_ok=True)
    os.chmod(repertoire, 0o700)  # corrige si le répertoire existait déjà avec de mauvaises permissions
    return os.path.join(repertoire, f"{prefixe}_{int(time.time())}.png")


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
    page.screenshot(path=chemin, full_page=False, timeout=screenshot_timeout)
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
        return data["actions"]
    return data


def executer_actions(page, actions, output_dir, timeout, mode_llm="local",
                     interval_capture_default=0, modeles_appeles=None,
                     secrets_chemin=None, screenshot_timeout=120_000):
    from playwright.sync_api import TimeoutError as PWTimeoutError

    intermediaires = []
    stream_captures = []
    evaluations = []
    stream_dir = None
    run_id = int(time.time())
    if modeles_appeles is None:
        modeles_appeles = []

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

    for idx, a in enumerate(actions):
        t = a.get("type")
        iv = _resoudre_intervalle(a)

        if t == "naviguer":
            page.goto(a["url"], timeout=timeout)

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
            if valeur == "depuis_vault":
                cle = a.get("vault_cle")
                if not cle:
                    raise ValueError("remplir depuis_vault : champ 'vault_cle' requis")
                if secrets_chemin:
                    from lib.vault import lire_credential_fichier
                    valeur = lire_credential_fichier(secrets_chemin, cle)
                else:
                    from lib.vault import lire_credential, domaine_depuis_url
                    valeur = lire_credential(domaine_depuis_url(page.url), cle)
            elif valeur == "depuis_vault_totp":
                if secrets_chemin:
                    from lib.vault import lire_totp_fichier
                    valeur = lire_totp_fichier(secrets_chemin)
                else:
                    from lib.vault import lire_totp, domaine_depuis_url
                    valeur = lire_totp(domaine_depuis_url(page.url))
            page.locator(a["selecteur"]).fill(valeur, timeout=timeout)

        elif t == "cliquer":
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
            nom = a.get("nom", "etape")
            if a.get("som"):
                p, _, _ = _injecter_som(page, output_dir, f"capture_som_{nom}",
                                        screenshot_timeout=screenshot_timeout)
            else:
                p = chemin_png(output_dir, f"capture_{nom}")
                page.evaluate(_MASQUER_SECRETS_JS)
                try:
                    page.screenshot(path=p, full_page=True, timeout=screenshot_timeout)
                finally:
                    page.evaluate(_RESTAURER_SECRETS_JS)
            intermediaires.append(p)

        elif t == "cliquer_som":
            som_id = a.get("id")
            if som_id is None:
                raise ValueError("cliquer_som requiert un champ 'id'")
            coord = page.evaluate(_SOM_TROUVER_JS, som_id)
            if coord is None:
                raise ValueError(f"cliquer_som : élément SoM {som_id!r} non trouvé sur la page")
            page.mouse.click(coord["x"], coord["y"])

        elif t == "remplir_som":
            som_id = a.get("id")
            valeur = a.get("valeur", "")
            if som_id is None:
                raise ValueError("remplir_som requiert un champ 'id'")
            if valeur == "depuis_vault":
                cle = a.get("vault_cle")
                if not cle:
                    raise ValueError("remplir_som depuis_vault : champ 'vault_cle' requis")
                if secrets_chemin:
                    from lib.vault import lire_credential_fichier
                    valeur = lire_credential_fichier(secrets_chemin, cle)
                else:
                    from lib.vault import lire_credential, domaine_depuis_url
                    valeur = lire_credential(domaine_depuis_url(page.url), cle)
            elif valeur == "depuis_vault_totp":
                if secrets_chemin:
                    from lib.vault import lire_totp_fichier
                    valeur = lire_totp_fichier(secrets_chemin)
                else:
                    from lib.vault import lire_totp, domaine_depuis_url
                    valeur = lire_totp(domaine_depuis_url(page.url))
            coord = page.evaluate(_SOM_TROUVER_JS, som_id)
            if coord is None:
                raise ValueError(f"remplir_som : élément SoM {som_id!r} non trouvé sur la page")
            if coord.get("tag", "").upper() == "SELECT":
                ok = page.evaluate("""(args) => {
                    const SELECTORS = [
                        'a[href]','button','input:not([type="hidden"])',
                        'select','textarea','summary',
                        '[role="button"]','[role="link"]','[role="tab"]',
                        '[role="checkbox"]','[role="menuitem"]','[role="radio"]',
                        '[role="combobox"]','[role="spinbutton"]','[role="searchbox"]'
                    ].join(',');
                    const vw = window.innerWidth, vh = window.innerHeight;
                    const items = [];
                    document.querySelectorAll(SELECTORS).forEach(el => {
                        let p = el.parentElement; while (p) { if (p.tagName === 'DIALOG' && !p.hasAttribute('open')) return; p = p.parentElement; }
                        const s = window.getComputedStyle(el);
                        if (s.display==='none'||s.visibility==='hidden'||s.opacity==='0') return;
                        const r = el.getBoundingClientRect();
                        if (r.width<2||r.height<2) return;
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
            page.screenshot(path=tmp, timeout=screenshot_timeout)

            from lib.vision import localiser_element
            result = localiser_element(tmp, description, mode_llm)

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
                from lib.vault import lire_credential_fichier
                topic = lire_credential_fichier(secrets_chemin, "ntfy_topic")
            else:
                from lib.vault import lire_credential, domaine_depuis_url
                topic = lire_credential(domaine_depuis_url(page.url), "ntfy_topic")
            ntfy_lib.publier_attente(topic, page.url)
            code = ntfy_lib.attendre_code(topic, timeout_s=timeout_mfa)
            coord = page.evaluate(_SOM_TROUVER_JS, id_som)
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

    return intermediaires, stream_captures, evaluations, modeles_appeles


def main():
    import importlib.util
    if importlib.util.find_spec("playwright") is None:
        sys.stderr.write(
            "Diwall : module 'playwright' introuvable dans cet interpréteur.\n"
            "  Exécutez via le venv : /opt/diwall/venv/bin/python depuis /opt/diwall\n"
        )
        sys.exit(3)

    # Interdire les core dumps pour ce processus : si Playwright crashe
    # pendant qu'un credential est en mémoire, le noyau ne peut pas écrire
    # un dump contenant le secret (spec 36_ §2.5).
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, resource.error):
        pass  # best-effort — certains environnements refusent, ce n'est pas bloquant

    args = parse_args()
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
            "boussole": _boussole(),
        }))
        sys.exit(1)

    # ── Chargement des actions ────────────────────────────────────────────────
    if args.reprendre_session:
        try:
            if args.action:
                parsed = json.loads(args.action)
                # Accepte un objet unique {"type":...} OU un tableau [{...},{...}]
                actions = parsed if isinstance(parsed, list) else [parsed]
            elif args.actions:
                # FR-54 : --actions (fichier) désormais supporté en Mode B
                actions = charger_actions(args.actions)
            else:
                actions = []
        except (json.JSONDecodeError, Exception) as e:
            print(json.dumps({
                "succes": False, "erreur": "action_invalide",
                "message": str(e), "horodatage": horodatage,
                "boussole": _boussole(),
            }))
            sys.exit(1)
    else:
        try:
            actions = charger_actions(args.actions)
        except Exception as e:
            print(json.dumps({
                "succes": False, "erreur": "actions_invalides",
                "message": str(e), "horodatage": horodatage,
                "boussole": _boussole(),
            }))
            sys.exit(1)

    # ── Validation --no-capture ──────────────────────────────────────────────
    if args.no_capture and args.som:
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--no-capture est incompatible avec --som : SoM requiert un PNG",
            "horodatage": horodatage, "boussole": _boussole(),
        }))
        sys.exit(1)
    if args.no_capture and any(a.get("type") == "capturer" for a in actions):
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--no-capture est incompatible avec l'action 'capturer' dans le scénario",
            "horodatage": horodatage, "boussole": _boussole(),
        }))
        sys.exit(1)

    # ── Chemin de sortie ──────────────────────────────────────────────────────
    if args.output:
        sortie = args.output if os.path.splitext(args.output)[1] else args.output + ".png"
        os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
    else:
        sortie = chemin_png(args.output_dir)

    erreurs_js = []
    http_status = None
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
                ctx = browser.new_context(
                    storage_state=session["storage_state"],
                    viewport=viewport,
                    ignore_https_errors=True,
                )
                url_cible = args.url if args.url else session["url"]
            else:
                ctx = browser.new_context(
                    viewport={"width": args.largeur, "height": args.hauteur},
                    ignore_https_errors=True,
                )
                url_cible = args.url

            page = ctx.new_page()
            page.on("pageerror", lambda err: erreurs_js.append(str(err)))

            # ── Navigation ────────────────────────────────────────────────────
            rep = page.goto(url_cible, timeout=args.timeout, wait_until="networkidle")
            if rep:
                http_status = rep.status
            url_finale = page.url

            # ── Détection de dérive de session (lot 8.5) ──────────────────────
            # Comparaison sur l'URL effective après navigation (post-normalisation)
            # afin d'éviter les faux positifs liés au slash terminal ou aux
            # redirections HTTP transparentes.
            if args.reprendre_session and session is not None:
                derive_session = _detecter_derive_session(session, url_finale)

            if args.attendre_selecteur:
                page.wait_for_selector(args.attendre_selecteur, timeout=args.timeout)

            # ── Actions ───────────────────────────────────────────────────────
            interm, stream_captures, evaluations, modeles_appeles = executer_actions(
                page, actions, args.output_dir, args.timeout, args.llm,
                interval_capture_default=args.interval_capture,
                modeles_appeles=modeles_appeles,
                secrets_chemin=getattr(args, "secrets", None),
                screenshot_timeout=args.screenshot_timeout,
            )
            url_finale = page.url  # mise à jour après actions

            # ── Capture finale ────────────────────────────────────────────────
            if not args.no_capture:
                page.evaluate(_MASQUER_SECRETS_JS)
                try:
                    page.screenshot(path=sortie, full_page=True, timeout=args.screenshot_timeout)
                finally:
                    page.evaluate(_RESTAURER_SECRETS_JS)

            # ── SoM ───────────────────────────────────────────────────────────
            capture_som, elements_som, hors_vp_som = None, [], 0
            if args.som and not args.no_capture:
                capture_som, elements_som, hors_vp_som = _injecter_som(
                    page, args.output_dir, screenshot_timeout=args.screenshot_timeout)

            # ── A11y ──────────────────────────────────────────────────────────
            a11y_tree = _snapshot_a11y(page) if args.a11y else None

            # ── Auth status ───────────────────────────────────────────────────
            auth_status = None
            if args.auth_indicator:
                try:
                    visible = page.locator(args.auth_indicator).is_visible()
                    auth_status = "active" if visible else "inactive"
                except Exception:
                    auth_status = "inactive"

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

            browser.close()

        result = {
            "succes": True,
            "http_status": http_status,
            "url_finale": url_finale,
            "erreurs_js": erreurs_js,
            "duree_ms": int((time.time() - t0) * 1000),
            "horodatage": horodatage,
            "diwall_meta": _construire_diwall_meta(
                profil, horodatage, modeles_appeles, url_finale,
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
            result["evaluations"] = evaluations
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
        if derive_session:
            result["derive_session"] = derive_session
        result["boussole"] = _boussole()
        print(json.dumps(result, ensure_ascii=False))
        _journaliser_run(result, actions, args.intention, url_finale, "succes")
        _nettoyer_session_ephemere(
            getattr(args, "reprendre_session", None),
            explicitement_demandee=bool(args.sauver_session),
        )

    except Exception as e:
        # Coffre fermé : erreur distincte, pas de tentative Playwright (inutile),
        # code de sortie 42 par symétrie avec Phase 7bis.
        from lib.vault import VaultFermeError
        if isinstance(e, VaultFermeError):
            result = {
                "succes": False,
                "erreur": "vault_ferme",
                "message": str(e),
                "code_sortie_recommande": VaultFermeError.CODE_SORTIE,
                "http_status": http_status,
                "duree_ms": int((time.time() - t0) * 1000),
                "horodatage": horodatage,
                "diwall_meta": _construire_diwall_meta(
                    profil, horodatage, modeles_appeles, url_cible,
                ),
                "boussole": _boussole(),
            }
            print(json.dumps(result, ensure_ascii=False))
            _journaliser_run(result, actions, args.intention, url_cible, "echec",
                             erreur=f"VaultFermeError: {e}")
            sys.exit(VaultFermeError.CODE_SORTIE)

        capture_echec = None
        try:
            from playwright.sync_api import sync_playwright
            echec = chemin_png(args.output_dir, "echec")
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True)
                pg = b.new_context(ignore_https_errors=True).new_page()
                pg.goto(url_cible, timeout=5000)
                pg.screenshot(path=echec)
                b.close()
            capture_echec = echec
        except Exception:
            pass

        result = {
            "succes": False,
            "erreur": type(e).__name__,
            "message": str(e),
            "http_status": http_status,
            "duree_ms": int((time.time() - t0) * 1000),
            "horodatage": horodatage,
            "diwall_meta": _construire_diwall_meta(
                profil, horodatage, modeles_appeles, url_finale,
            ),
        }
        if capture_echec:
            result["capture_echec"] = capture_echec
        result["boussole"] = _boussole()
        print(json.dumps(result, ensure_ascii=False))
        _journaliser_run(result, actions, args.intention, url_cible, "echec",
                         erreur=f"{type(e).__name__}: {e}")
        _nettoyer_session_ephemere(
            getattr(args, "reprendre_session", None),
            explicitement_demandee=bool(getattr(args, "sauver_session", None)),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
