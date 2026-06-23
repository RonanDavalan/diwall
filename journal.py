#!/opt/diwall/venv/bin/python3
"""
journal.py — lecture / interrogation du journal d'opérations Diwall (v1.4).

Répond à : « qu'ai-je fait sur cette cible ? », « cet objet a-t-il déjà
été supprimé/créé ? ». Lit le journal courant ET les fichiers tournés par
logrotate (operations.jsonl, .1, .2.gz, …).

Exemples :
    journal.py --cible target.local
    journal.py --cible my-app.local --mutatif
    journal.py --depuis 2026-05-30 --intention suppression

Spécification : _CADRE/SPECIFICATIONS/35_JOURNAL_OPERATIONS.md §étape 6.
"""
__version__ = "1.12.0"

import argparse
import glob
import gzip
import json
import os
import sys


def _journal_path():
    return os.environ.get("DIWALL_JOURNAL", "/var/log/diwall/operations.jsonl")


def _skills_dir():
    return os.environ.get("DIWALL_SKILLS_DIR", "/opt/diwall/skills")


def _fichiers():
    """Journal courant + fichiers tournés (logrotate), du plus ancien au plus récent."""
    base = _journal_path()
    tournes = sorted(glob.glob(base + ".*"), reverse=True)  # .2.gz, .1 … avant le courant
    return [p for p in [*tournes, base] if os.path.isfile(p)]


def _lire_entrees():
    entrees = []
    for p in _fichiers():
        opener = gzip.open if p.endswith(".gz") else open
        try:
            with opener(p, "rt", encoding="utf-8") as f:
                for ligne in f:
                    ligne = ligne.strip()
                    if not ligne:
                        continue
                    try:
                        entrees.append(json.loads(ligne))
                    except json.JSONDecodeError:
                        continue  # ligne corrompue ignorée, lecture robuste
        except OSError:
            continue
    entrees.sort(key=lambda e: e.get("ts", ""))
    return entrees


def _garde(e, args):
    if args.cible and args.cible not in (e.get("cible_url") or ""):
        return False
    if args.mutatif and not e.get("mutatif"):
        return False
    if args.intention and args.intention.lower() not in (e.get("intention") or "").lower():
        return False
    ts = e.get("ts", "")
    if args.depuis and ts < args.depuis:
        return False
    if args.jusqu and ts > args.jusqu:
        return False
    return True


def _avertir_fallback():
    """Avertit si des entrées non migrées existent dans le fichier de secours."""
    fb = os.environ.get(
        "DIWALL_JOURNAL_FALLBACK",
        "/tmp/diwall/operations.fallback.jsonl",
    )
    if os.path.isfile(fb) and os.path.getsize(fb) > 0:
        print(
            f"⚠  Entrées non consolidées dans {fb}\n"
            f"   Consolider : cat {fb} >> {_journal_path()}\n",
            file=sys.stderr,
        )


def main():
    p = argparse.ArgumentParser(description="Diwall — lecture du journal d'opérations")
    p.add_argument("--cible", help="Filtre sous-chaîne sur cible_url")
    p.add_argument("--depuis", help="Horodatage ISO minimum (ex. 2026-05-30)")
    p.add_argument("--jusqu", help="Horodatage ISO maximum")
    p.add_argument("--mutatif", action="store_true", help="Uniquement les runs mutatifs")
    p.add_argument("--intention", help="Filtre sous-chaîne sur intention")
    p.add_argument("--format", choices=["texte", "json"], default="texte")
    p.add_argument("--limite", type=int, default=0,
                   help="N dernières entrées (0 = toutes)")
    p.add_argument("--exporter-skill", metavar="OPERATION_ID",
                   help="Exporte le run réussi en fichier skill dans skills/")
    p.add_argument("--nom", help="Nom du skill à créer (requis avec --exporter-skill)")
    args = p.parse_args()

    # ── Export skill ──────────────────────────────────────────────────────────
    if args.exporter_skill:
        _avertir_fallback()
        entrees = _lire_entrees()
        cible = next(
            (e for e in entrees if e.get("operation_id") == args.exporter_skill),
            None,
        )
        if not cible:
            print(
                f"Erreur : operation_id '{args.exporter_skill}' introuvable.",
                file=sys.stderr,
            )
            sys.exit(1)
        if "actions_raw" not in cible:
            print(
                "Erreur : actions_raw absent — run antérieur à v1.6 ou run sans actions.",
                file=sys.stderr,
            )
            sys.exit(1)
        nom = args.nom
        if not nom:
            print("Erreur : --nom est requis avec --exporter-skill.", file=sys.stderr)
            sys.exit(1)
        skill = {
            "nom": nom,
            "url": cible.get("cible_url", ""),
            "actions": cible["actions_raw"],
        }
        if cible.get("intention"):
            skill["description"] = cible["intention"]
        skills_dir = _skills_dir()
        os.makedirs(skills_dir, exist_ok=True)
        chemin = os.path.join(skills_dir, f"{nom}.json")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Skill exporté : {chemin}")
        return

    _avertir_fallback()
    filtrees = [e for e in _lire_entrees() if _garde(e, args)]
    if args.limite > 0:
        filtrees = filtrees[-args.limite:]

    if args.format == "json":
        print(json.dumps(filtrees, ensure_ascii=False, indent=2))
        return

    if not filtrees:
        print("(aucune opération correspondante)")
        return

    for e in filtrees:
        marque = "✏ MUTATIF" if e.get("mutatif") else "· lecture"
        print(f"{e.get('ts', '?')}  [{e.get('resultat', '?')}] {marque}  "
              f"{e.get('outil', '?')}  {e.get('cible_url', '')}")
        if e.get("intention"):
            print(f"      intention : {e['intention']}")
        if e.get("actions"):
            print(f"      actions   : {', '.join(e['actions'])}")
        if e.get("captures"):
            print(f"      preuves   : {len(e['captures'])} → {e['captures'][0]}")
        if e.get("erreur"):
            print(f"      erreur    : {e['erreur']}")
    print(f"\n{len(filtrees)} opération(s).")


if __name__ == "__main__":
    main()
