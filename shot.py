#!/opt/diwall/venv/bin/python3
import argparse
import getpass
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone

__version__ = "1.3.2"

# Permet d'importer lib/ depuis le même répertoire que shot.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


def _injecter_som(page, output_dir):
    """Injecte le Set-of-Mark, capture la vue annotée, nettoie le DOM. Retourne (chemin_som, elements_som)."""
    elements = page.evaluate(_SOM_INJECTER_JS)
    chemin_som = chemin_png(output_dir, "state_som")
    page.screenshot(path=chemin_som, full_page=False)  # fixed = viewport uniquement
    page.evaluate(_SOM_RETIRER_JS)
    return chemin_som, elements


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
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


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
                        "(v1.4). Ex. : \"Suppression clone allsys.online 2026-05-30\".")
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


def _capture_periodique(page, stream_dir, action_index, t_ms):
    """Prend une capture intermédiaire pendant une attente. Retourne le dict descriptif."""
    chemin = os.path.join(stream_dir, f"{action_index}_{t_ms}.png")
    page.screenshot(path=chemin, full_page=False)
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
                     interval_capture_default=0, modeles_appeles=None):
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
                                page, _stream_dir_lazy(), idx, int((now - t0) * 1000)))
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
                                page, _stream_dir_lazy(), idx, int((now - t0) * 1000)))
                            prochain_capture = now + iv

        elif t == "remplir":
            valeur = a.get("valeur", "")
            if valeur == "depuis_vault":
                from lib.vault import lire_credential, domaine_depuis_url
                cle = a.get("vault_cle")
                if not cle:
                    raise ValueError("remplir depuis_vault : champ 'vault_cle' requis")
                valeur = lire_credential(domaine_depuis_url(page.url), cle)
            page.locator(a["selecteur"]).fill(valeur, timeout=timeout)

        elif t == "cliquer":
            page.locator(a["selecteur"]).click(timeout=timeout)

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
                page.evaluate(_SOM_INJECTER_JS)
                p = chemin_png(output_dir, f"capture_som_{nom}")
                page.screenshot(path=p, full_page=False)
                page.evaluate(_SOM_RETIRER_JS)
            else:
                p = chemin_png(output_dir, f"capture_{nom}")
                page.screenshot(path=p, full_page=True)
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
                from lib.vault import lire_credential, domaine_depuis_url
                cle = a.get("vault_cle")
                if not cle:
                    raise ValueError("remplir_som depuis_vault : champ 'vault_cle' requis")
                valeur = lire_credential(domaine_depuis_url(page.url), cle)
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
                page.keyboard.press("Control+a")
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
            page.screenshot(path=tmp)

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

        else:
            raise ValueError(f"Type d'action inconnu : {t!r}")

    return intermediaires, stream_captures, evaluations, modeles_appeles


def main():
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
        }))
        sys.exit(1)

    # ── Chargement des actions ────────────────────────────────────────────────
    if args.reprendre_session:
        try:
            if args.action:
                parsed = json.loads(args.action)
                # Accepte un objet unique {"type":...} OU un tableau [{...},{...}]
                actions = parsed if isinstance(parsed, list) else [parsed]
            else:
                actions = []
        except json.JSONDecodeError as e:
            print(json.dumps({
                "succes": False, "erreur": "action_invalide",
                "message": str(e), "horodatage": horodatage,
            }))
            sys.exit(1)
    else:
        try:
            actions = charger_actions(args.actions)
        except Exception as e:
            print(json.dumps({
                "succes": False, "erreur": "actions_invalides",
                "message": str(e), "horodatage": horodatage,
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
            )
            url_finale = page.url  # mise à jour après actions

            # ── Capture finale ────────────────────────────────────────────────
            page.screenshot(path=sortie, full_page=True)

            # ── SoM ───────────────────────────────────────────────────────────
            capture_som, elements_som = None, []
            if args.som:
                capture_som, elements_som = _injecter_som(page, args.output_dir)

            # ── A11y ──────────────────────────────────────────────────────────
            a11y_tree = _snapshot_a11y(page) if args.a11y else None

            # ── Sauvegarde session ────────────────────────────────────────────
            session_file = None
            if args.sauver_session:
                _sauver_session(ctx, page, args.sauver_session,
                                {"width": args.largeur, "height": args.hauteur})
                session_file = args.sauver_session

            browser.close()

        result = {
            "succes": True,
            "capture": sortie,
            "http_status": http_status,
            "url_finale": url_finale,
            "erreurs_js": erreurs_js,
            "duree_ms": int((time.time() - t0) * 1000),
            "horodatage": horodatage,
            "diwall_meta": _construire_diwall_meta(
                profil, horodatage, modeles_appeles, url_finale,
            ),
        }
        if interm:
            result["captures_intermediaires"] = interm
        if stream_captures:
            result["stream_captures"] = stream_captures
        if evaluations:
            result["evaluations"] = evaluations
        if capture_som:
            result["capture_som"] = capture_som
            result["elements_som"] = elements_som
        if a11y_tree is not None:
            result["a11y_tree"] = a11y_tree
        if session_file:
            result["session_file"] = session_file
        if derive_session:
            result["derive_session"] = derive_session
        print(json.dumps(result, ensure_ascii=False))
        _journaliser_run(result, actions, args.intention, url_finale, "succes")

    except Exception as e:
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
        print(json.dumps(result, ensure_ascii=False))
        _journaliser_run(result, actions, args.intention, url_cible, "echec",
                         erreur=f"{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
