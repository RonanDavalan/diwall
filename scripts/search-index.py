#!/usr/bin/env python3
"""
search-index.py — interroge la mémoire vectorielle Diwall.

Usage depuis ~/git/Diwall/Diwall/ :
    /opt/diwall/venv/bin/python scripts/search-index.py "comment déployer sur vps"
    /opt/diwall/venv/bin/python scripts/search-index.py "permission lib/" --n 5
    /opt/diwall/venv/bin/python scripts/search-index.py "vault gocryptfs" --collection diwall

Retourne les passages les plus proches par similarité cosinus.
À utiliser en Porte d'Amorçage avant d'agir sur une tâche système connue.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.vector import DB_PATH, search


def main():
    parser = argparse.ArgumentParser(
        description="Interroge la mémoire vectorielle Diwall."
    )
    parser.add_argument("query", help="Question ou mots-clés en langage naturel")
    parser.add_argument("--n", type=int, default=3, help="Nombre de résultats (défaut : 3)")
    parser.add_argument("--collection", default="diwall")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    try:
        results = search(args.query, n=args.n, collection_name=args.collection, db_path=args.db)
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        print("La base n'existe peut-être pas encore. Lancez d'abord build-index.py.", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("Aucun résultat.")
        return

    SEP = "=" * 62
    LINE = "-" * 62
    for i, r in enumerate(results, 1):
        print(f"\n{SEP}")
        print(f"[{i}] score={r['score']}  ←  {r['source']}")
        if r["section"]:
            print(f"    ## {r['section']}")
        print(LINE)
        print(r["extrait"])
        if len(r["extrait"]) == 500:
            print("  [...]")

    print(f"\n{SEP}")
    print(f"{len(results)} résultat(s) — requête : « {args.query} »")


if __name__ == "__main__":
    main()
