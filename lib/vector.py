"""
Mémoire vectorielle Diwall — module partagé.
Stack : ChromaDB (local, persistant) + Ollama nomic-embed-text (souverain).
"""

import os
import requests
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get(
    "DIWALL_DB_PATH",
    os.path.normpath(os.path.join(_REPO_DIR, "..", "_CADRE", "MEMOIRE", "chroma_db"))
)
COLLECTION_DEFAULT = "diwall"
OLLAMA_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"


class OllamaEmbeddings(EmbeddingFunction):
    def __init__(self, model: str = EMBED_MODEL, url: str = OLLAMA_URL):
        self._model = model
        self._url = url

    def __call__(self, input: Documents) -> Embeddings:
        resp = requests.post(
            self._url,
            json={"model": self._model, "input": input},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


def get_collection(
    name: str = COLLECTION_DEFAULT,
    db_path: str = DB_PATH,
) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=db_path)
    return client.get_or_create_collection(
        name=name,
        embedding_function=OllamaEmbeddings(),
        metadata={"hnsw:space": "cosine"},
    )


def search(
    query: str,
    n: int = 3,
    collection_name: str = COLLECTION_DEFAULT,
    db_path: str = DB_PATH,
    type_filter: str | None = None,
) -> list[dict]:
    """Interroge la base vectorielle et retourne les passages les plus proches."""
    col = get_collection(collection_name, db_path)
    where = {"type": type_filter} if type_filter else None
    results = col.query(query_texts=[query], n_results=n, where=where)
    out = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        out.append({
            "score": round(1 - dist, 3),
            "source": meta.get("source", "?"),
            "section": meta.get("section", ""),
            "type": meta.get("type", ""),
            "extrait": doc[:500],
        })
    return out
