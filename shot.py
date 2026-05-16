#!/opt/diwall/venv/bin/python3
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# Permet d'importer lib/ depuis le même répertoire que shot.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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
