"""
Mémoire vectorielle Diwall — module partagé.
Stack : ChromaDB (local, persistant) + Ollama nomic-embed-text (souverain).
"""

import requests
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings

DB_PATH = "/opt/diwall/vector_db"
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
) -> list[dict]:
    """Interroge la base vectorielle et retourne les passages les plus proches."""
    col = get_collection(collection_name, db_path)
    results = col.query(query_texts=[query], n_results=n)
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
            "extrait": doc[:500],
        })
    return out
