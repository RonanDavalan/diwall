#!/usr/bin/env python3
"""
build-index.py — indexe _CADRE/ dans ChromaDB (mémoire vectorielle Niveau A).

Usage depuis ~/git/Diwall/Diwall/ :
    /opt/diwall/venv/bin/python scripts/build-index.py --source ../_CADRE/
    /opt/diwall/venv/bin/python scripts/build-index.py --source ../_CADRE/ --rebuild

L'index est stocké dans /opt/diwall/vector_db/ (hors git).
"""

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.vector import DB_PATH, OllamaEmbeddings

import chromadb


# Répertoires exclus de l'indexation (données nominales ou dérivées)
EXCLUDE_DIRS = {"instance", "__pycache__", ".git", "captures", "archives", "vector_db"}
# Fichiers exclus (placeholders non remplis ou données sensibles)
EXCLUDE_FILES = {"INSTANCE_PROJET.md"}

BATCH_SIZE = 50
MIN_CHUNK_LEN = 80


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Découpe un .md en chunks par section ##. Chaque section = un chunk."""
    chunks = []
    current_section = ""
    current_lines: list[str] = []

    def flush():
        body = "\n".join(current_lines).strip()
        if len(body) >= MIN_CHUNK_LEN:
            chunks.append({
                "section": current_section,
                "text": body,
                "source": source,
            })

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()

    # Fichier sans section ## : tout le contenu comme chunk unique
    if not chunks:
        body = text.strip()
        if len(body) >= MIN_CHUNK_LEN:
            chunks.append({"section": "", "text": body, "source": source})

    return chunks


def iter_md_files(source_dir: str):
    """Parcourt récursivement les .md en respectant les exclusions."""
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for fname in sorted(files):
            if fname.endswith(".md") and fname not in EXCLUDE_FILES:
                yield os.path.join(root, fname)


def doc_id(source: str, section: str) -> str:
    """ID stable pour upsert incrémental."""
    return hashlib.sha256(f"{source}::{section}".encode()).hexdigest()[:20]


def main():
    parser = argparse.ArgumentParser(description="Indexe _CADRE/ dans ChromaDB.")
    parser.add_argument(
        "--source",
        default=os.path.expanduser("~/git/Diwall/_CADRE"),
        help="Répertoire _CADRE/ à indexer",
    )
    parser.add_argument("--collection", default="diwall")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Supprimer et reconstruire la collection depuis zéro",
    )
    args = parser.parse_args()

    source = os.path.abspath(args.source)
    if not os.path.isdir(source):
        print(f"Erreur : {source} n'existe pas ou n'est pas un répertoire.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.db, exist_ok=True)
    client = chromadb.PersistentClient(path=args.db)

    if args.rebuild:
        try:
            client.delete_collection(args.collection)
            print(f"Collection '{args.collection}' supprimée (rebuild demandé).")
        except Exception:
            pass

    col = client.get_or_create_collection(
        name=args.collection,
        embedding_function=OllamaEmbeddings(),
        metadata={"hnsw:space": "cosine"},
    )

    print(f"Source  : {source}")
    print(f"Base    : {args.db}")
    print(f"Collection : {args.collection}")
    print()

    all_chunks: list[dict] = []
    for md_path in iter_md_files(source):
        rel = os.path.relpath(md_path, source)
        try:
            with open(md_path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            print(f"  Ignoré ({e}): {rel}", file=sys.stderr)
            continue
        chunks = chunk_markdown(text, rel)
        all_chunks.extend(chunks)
        print(f"  {rel:<55} {len(chunks):>2} chunk(s)")

    if not all_chunks:
        print("\nAucun chunk trouvé — vérifiez le répertoire source.")
        sys.exit(0)

    print(f"\nEmbedding et upsert de {len(all_chunks)} chunks...")
    ids = [doc_id(c["source"], c["section"]) for c in all_chunks]
    docs = [c["text"] for c in all_chunks]
    metas = [{"source": c["source"], "section": c["section"]} for c in all_chunks]

    for i in range(0, len(all_chunks), BATCH_SIZE):
        col.upsert(
            ids=ids[i : i + BATCH_SIZE],
            documents=docs[i : i + BATCH_SIZE],
            metadatas=metas[i : i + BATCH_SIZE],
        )
        done = min(i + BATCH_SIZE, len(all_chunks))
        print(f"  Batch {i // BATCH_SIZE + 1} : {done}/{len(all_chunks)}")

    print(f"\nTotal : {len(all_chunks)} chunks dans la collection '{args.collection}'.")
    print(f"Requête test : /opt/diwall/venv/bin/python scripts/search-index.py \"déployer sur vps\"")


if __name__ == "__main__":
    main()
