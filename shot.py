#!/opt/diwall/venv/bin/python3
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

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


def _injecter_som(page, output_dir):
    """Injecte le Set-of-Mark, capture la vue annotée, nettoie le DOM. Retourne (chemin_som, elements_som)."""
    elements = page.evaluate(_SOM_INJECTER_JS)
    chemin_som = chemin_png(output_dir, "state_som")
    page.screenshot(path=chemin_som, full_page=False)  # fixed = viewport uniquement
    page.evaluate(_SOM_RETIRER_JS)
    return chemin_som, elements


def parse_args():
    p = argparse.ArgumentParser(description="Diwall — capture Playwright avec actions")
    p.add_argument("--url", required=True, help="URL à capturer")
    p.add_argument("--actions", help="Fichier JSON ou JSON inline d'actions séquentielles")
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
    return p.parse_args()


def chemin_png(repertoire, prefixe="capture"):
    os.makedirs(repertoire, exist_ok=True)
    return os.path.join(repertoire, f"{prefixe}_{int(time.time())}.png")


def charger_actions(source):
    if not source:
        return []
    s = source.strip()
    if s.startswith("[") or s.startswith("{"):
        return json.loads(s)
    with open(source, encoding="utf-8") as f:
        return json.load(f)


def executer_actions(page, actions, output_dir, timeout, mode_llm="local"):
    intermediaires = []
    for a in actions:
        t = a.get("type")

        if t == "naviguer":
            page.goto(a["url"], timeout=timeout)

        elif t == "attendre":
            page.wait_for_selector(a["selecteur"], timeout=timeout)

        elif t == "attendre_navigation":
            page.wait_for_load_state("networkidle", timeout=timeout)

        elif t == "remplir":
            valeur = a.get("valeur", "")
            if valeur == "depuis_vault":
                raise NotImplementedError("depuis_vault nécessite le module vault (Phase 6)")
            page.fill(a["selecteur"], valeur)

        elif t == "cliquer":
            page.click(a["selecteur"], timeout=timeout)

        elif t == "pause":
            time.sleep(a.get("ms", 500) / 1000)

        elif t == "capturer":
            nom = a.get("nom", "etape")
            p = chemin_png(output_dir, f"capture_{nom}")
            page.screenshot(path=p, full_page=True)
            intermediaires.append(p)

        elif t == "cliquer_visuel":
            description = a.get("description", "")
            if not description:
                raise ValueError("cliquer_visuel requiert un champ 'description'")

            # Capture intermédiaire pour la localisation
            tmp = chemin_png(output_dir, "vision_tmp")
            page.screenshot(path=tmp)

            from lib.vision import localiser_element
            result = localiser_element(tmp, description, mode_llm)

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

    return intermediaires


def main():
    args = parse_args()
    t0 = time.time()
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()

    try:
        actions = charger_actions(args.actions)
    except Exception as e:
        print(json.dumps({
            "succes": False,
            "erreur": "actions_invalides",
            "message": str(e),
            "horodatage": horodatage,
        }))
        sys.exit(1)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        sortie = args.output
    else:
        sortie = chemin_png(args.output_dir)

    erreurs_js = []
    http_status = None
    url_finale = args.url

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": args.largeur, "height": args.hauteur},
                ignore_https_errors=True,
            )
            page = ctx.new_page()
            page.on("pageerror", lambda err: erreurs_js.append(str(err)))

            rep = page.goto(args.url, timeout=args.timeout, wait_until="networkidle")
            if rep:
                http_status = rep.status
            url_finale = page.url

            if args.attendre_selecteur:
                page.wait_for_selector(args.attendre_selecteur, timeout=args.timeout)

            interm = executer_actions(page, actions, args.output_dir, args.timeout, args.llm)

            page.screenshot(path=sortie, full_page=True)

            capture_som, elements_som = None, []
            if args.som:
                capture_som, elements_som = _injecter_som(page, args.output_dir)

            browser.close()

        result = {
            "succes": True,
            "capture": sortie,
            "http_status": http_status,
            "url_finale": url_finale,
            "erreurs_js": erreurs_js,
            "duree_ms": int((time.time() - t0) * 1000),
            "horodatage": horodatage,
        }
        if interm:
            result["captures_intermediaires"] = interm
        if capture_som:
            result["capture_som"] = capture_som
            result["elements_som"] = elements_som
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        capture_echec = None
        try:
            from playwright.sync_api import sync_playwright
            echec = chemin_png(args.output_dir, "echec")
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True)
                pg = b.new_context(ignore_https_errors=True).new_page()
                pg.goto(args.url, timeout=5000)
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
        }
        if capture_echec:
            result["capture_echec"] = capture_echec
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
