#!/opt/diwall/venv/bin/python3
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse


REFERENCES_DIR = "/opt/diwall/references"
SHOT_SCRIPT = "/opt/diwall/shot.py"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3-vl:8b"

PROMPT_DEFAUT = (
    "Tu reçois deux captures d'écran : la première est la référence (état de référence), "
    "la seconde est l'état actuel. Réponds uniquement en JSON avec les champs suivants : "
    "changement_detecte (booléen), "
    "analyse (string décrivant les différences observées, ou null si aucune), "
    "priorite (string : 'haute' si erreur visible, contenu manquant ou dégradation "
    "fonctionnelle ; 'basse' si changement cosmétique mineur). "
    "Si aucune différence significative, changement_detecte doit être false."
)


def parse_args():
    p = argparse.ArgumentParser(description="Diwall watch.py — surveillance visuelle")
    p.add_argument("--url", help="URL à surveiller")
    p.add_argument("--sauver-reference", dest="sauver_reference", action="store_true",
                   help="Capture et enregistre la référence visuelle")
    p.add_argument("--comparer", action="store_true",
                   help="Compare la capture actuelle avec la référence stockée")
    p.add_argument("--liste", help="Fichier de liste d'URLs (une par ligne, # pour commentaires)")
    p.add_argument("--prompt", default=PROMPT_DEFAUT,
                   help="Prompt LLM pour la comparaison (remplace le prompt par défaut)")
    p.add_argument("--llm", choices=["local", "claude"], default="local",
                   help="Mode LLM : local (Ollama llava) ou claude (API Anthropic)")
    p.add_argument("--ntfy-url", dest="ntfy_url",
                   help="URL ntfy pour les notifications push en cas d'alerte")
    p.add_argument("--timeout", type=int, default=10000,
                   help="Timeout de capture Playwright en ms (défaut : 10000)")
    return p.parse_args()


def slug_url(url):
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path.rstrip("/")
    if parsed.query:
        slug += "_" + parsed.query
    slug = re.sub(r"[^a-zA-Z0-9._-]", "_", slug)
    return re.sub(r"_+", "_", slug).strip("_")


def repertoire_reference(url):
    d = os.path.join(REFERENCES_DIR, slug_url(url))
    os.makedirs(d, exist_ok=True)
    return d


def capturer(url, sortie, timeout):
    result = subprocess.run(
        [SHOT_SCRIPT, "--url", url, "--output", sortie, "--timeout", str(timeout)],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout) if result.stdout.strip() else {}
    if result.returncode != 0:
        raise RuntimeError(data.get("message", result.stderr.strip()))
    return data


def comparer_ollama(ref_path, actuel_path, prompt):
    import requests

    def lire_b64(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [lire_b64(ref_path), lire_b64(actuel_path)],
        "stream": False,
        "format": "json",
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    raw = resp.json().get("response", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        changement = "changement" in raw.lower() and "true" in raw.lower()
        return {"changement_detecte": changement, "analyse": raw.strip(), "priorite": "basse"}


def comparer_claude(ref_path, actuel_path, prompt):
    raise NotImplementedError("Mode claude API non implémenté (Phase 4+). Utiliser --llm local.")


def notifier_ntfy(ntfy_url, url, analyse, priorite="basse"):
    import requests
    ntfy_priority = "high" if priorite == "haute" else "default"
    try:
        requests.post(
            ntfy_url,
            data=(analyse or "Changement visuel détecté.").encode("utf-8"),
            headers={
                "Title": f"Diwall — changement détecté : {url}",
                "Priority": ntfy_priority,
            },
            timeout=10,
        )
    except Exception:
        pass


def sauver_reference(url, timeout):
    rep = repertoire_reference(url)
    sortie = os.path.join(rep, "reference.png")
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()

    data = capturer(url, sortie, timeout)

    meta = {
        "url": url,
        "horodatage": horodatage,
        "http_status": data.get("http_status"),
        "erreurs_js": data.get("erreurs_js", []),
    }
    with open(os.path.join(rep, "reference.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"succes": True, "url": url, "reference": sortie, "horodatage": horodatage}


def comparer(url, prompt, mode_llm, ntfy_url, timeout):
    rep = repertoire_reference(url)
    ref_path = os.path.join(rep, "reference.png")
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()

    if not os.path.exists(ref_path):
        return {
            "succes": False,
            "url": url,
            "erreur": "reference_absente",
            "message": f"Pas de référence pour {url} — lancer --sauver-reference d'abord.",
        }

    actuel_path = os.path.join("/tmp/diwall", f"watch_{slug_url(url)}_{int(time.time())}.png")
    data = capturer(url, actuel_path, timeout)

    if mode_llm == "local":
        analyse = comparer_ollama(ref_path, actuel_path, prompt)
    else:
        analyse = comparer_claude(ref_path, actuel_path, prompt)

    changement = analyse.get("changement_detecte", False)
    analyse_llm = analyse.get("analyse")
    priorite = analyse.get("priorite", "basse")

    if changement and ntfy_url:
        notifier_ntfy(ntfy_url, url, analyse_llm, priorite)

    return {
        "succes": True,
        "url": url,
        "changement_detecte": changement,
        "priorite": priorite,
        "capture": actuel_path,
        "reference": ref_path,
        "analyse_llm": analyse_llm,
        "http_status": data.get("http_status"),
        "erreurs_js": data.get("erreurs_js", []),
        "horodatage": horodatage,
    }


def main():
    args = parse_args()

    if args.liste:
        with open(args.liste, encoding="utf-8") as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        resultats = []
        for url in urls:
            try:
                r = comparer(url, args.prompt, args.llm, args.ntfy_url, args.timeout)
            except Exception as e:
                r = {"succes": False, "url": url, "erreur": str(e)}
            resultats.append(r)
        print(json.dumps(resultats, ensure_ascii=False))
        return

    if not args.url:
        print(json.dumps({
            "succes": False,
            "erreur": "argument_manquant",
            "message": "Fournir --url ou --liste",
        }))
        sys.exit(1)

    if args.sauver_reference:
        result = sauver_reference(args.url, args.timeout)
    elif args.comparer:
        result = comparer(args.url, args.prompt, args.llm, args.ntfy_url, args.timeout)
    else:
        print(json.dumps({
            "succes": False,
            "erreur": "mode_requis",
            "message": "Utiliser --sauver-reference ou --comparer",
        }))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
