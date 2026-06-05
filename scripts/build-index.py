#!/usr/bin/env python3
"""
build-index.py — indexe _CADRE/ dans ChromaDB (mémoire vectorielle).

Usage depuis ~/git/Diwall/Diwall/ :
    /opt/diwall/venv/bin/python scripts/build-index.py
    /opt/diwall/venv/bin/python scripts/build-index.py --rebuild
    /opt/diwall/venv/bin/python scripts/build-index.py --source /autre/_CADRE/
"""

import argparse
import hashlib
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.vector import DB_PATH, OllamaEmbeddings

import chromadb


EXCLUDE_DIRS = {"instance", "__pycache__", ".git", "captures", "archives", "chroma_db", "vector_db"}
EXCLUDE_FILES = {"INSTANCE_PROJET.md"}
BATCH_SIZE = 50
MIN_CHUNK_LEN = 80


def _cadre_default() -> str:
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(scripts_dir)
    return os.path.normpath(os.path.join(repo_dir, "..", "_CADRE"))


def _cache_path(db: str) -> str:
    return os.path.join(os.path.dirname(db), ".chroma_cache.db")


def init_cache(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS file_cache (filepath TEXT PRIMARY KEY, sha256 TEXT)"
    )
    conn.commit()
    return conn


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def infer_type(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    top = parts[0] if parts else ""
    filename = parts[-1] if parts else ""
    if top == "MEMOIRE" and filename.startswith("ADDENDUM_"):
        return "memoire"
    return "gouvernance"


def chunk_markdown(text: str, source: str, doc_type: str) -> list[dict]:
    """Découpe un .md en chunks par section ##."""
    chunks = []
    current_section = ""
    current_lines: list[str] = []

    def flush():
        body = "\n".join(current_lines).strip()
        if len(body) >= MIN_CHUNK_LEN:
            chunks.append({"section": current_section, "text": body,
                           "source": source, "type": doc_type})

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()

    if not chunks:
        body = text.strip()
        if len(body) >= MIN_CHUNK_LEN:
            chunks.append({"section": "", "text": body, "source": source, "type": doc_type})

    return chunks


def iter_md_files(source_dir: str):
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for fname in sorted(files):
            if fname.endswith(".md") and fname not in EXCLUDE_FILES:
                yield os.path.join(root, fname)


def doc_id(source: str, idx: int) -> str:
    return hashlib.sha256(f"{source}::{idx}".encode()).hexdigest()[:20]


def main():
    parser = argparse.ArgumentParser(description="Indexe _CADRE/ dans ChromaDB.")
    parser.add_argument("--source", default=_cadre_default(), help="Répertoire _CADRE/")
    parser.add_argument("--collection", default="diwall")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--rebuild", action="store_true",
                        help="Supprimer et reconstruire depuis zéro")
    args = parser.parse_args()

    source = os.path.abspath(args.source)
    if not os.path.isdir(source):
        print(f"Erreur : {source} n'existe pas.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.db, exist_ok=True)
    client = chromadb.PersistentClient(path=args.db)

    cache_file = _cache_path(args.db)
    cache = init_cache(cache_file)

    if args.rebuild:
        try:
            client.delete_collection(args.collection)
            print(f"Collection '{args.collection}' supprimée (rebuild).")
        except Exception:
            pass
        cache.execute("DELETE FROM file_cache")
        cache.commit()

    col = client.get_or_create_collection(
        name=args.collection,
        embedding_function=OllamaEmbeddings(),
        metadata={"hnsw:space": "cosine"},
    )

    print(f"Source  : {source}")
    print(f"Base    : {args.db}")
    print(f"Cache   : {cache_file}")
    print(f"Collection : {args.collection}")
    print()

    total, skipped, updated = 0, 0, 0

    for md_path in iter_md_files(source):
        rel = os.path.relpath(md_path, source)
        total += 1

        empreinte = file_sha256(md_path)
        row = cache.execute(
            "SELECT sha256 FROM file_cache WHERE filepath = ?", (md_path,)
        ).fetchone()

        if row and row[0] == empreinte and not args.rebuild:
            skipped += 1
            continue

        try:
            with open(md_path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            print(f"  Ignoré ({e}): {rel}", file=sys.stderr)
            continue

        doc_type = infer_type(rel)
        chunks = chunk_markdown(text, rel, doc_type)
        updated += 1
        print(f"  {rel:<55} {len(chunks):>2} chunk(s)  [{doc_type}]")

        if not chunks:
            continue

        try:
            col.delete(where={"source": rel})
        except Exception:
            pass

        ids = [doc_id(rel, i) for i in range(len(chunks))]
        docs = [c["text"] for c in chunks]
        metas = [{"source": c["source"], "section": c["section"], "type": c["type"]}
                 for c in chunks]

        for i in range(0, len(chunks), BATCH_SIZE):
            col.upsert(
                ids=ids[i:i + BATCH_SIZE],
                documents=docs[i:i + BATCH_SIZE],
                metadatas=metas[i:i + BATCH_SIZE],
            )

        cache.execute(
            "INSERT OR REPLACE INTO file_cache (filepath, sha256) VALUES (?, ?)",
            (md_path, empreinte),
        )
        cache.commit()

    cache.close()
    print(f"\nTotal : {total} fichier(s) — {updated} mis à jour, {skipped} inchangé(s).")
    if updated:
        print(f"Requête test : /opt/diwall/venv/bin/python scripts/search-index.py \"déployer sur vps\"")


if __name__ == "__main__":
    main()
