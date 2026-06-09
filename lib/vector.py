"""
vector.py — Interface optionnelle vers une base vectorielle ChromaDB.

Permet à Diwall de s'interfacer avec n'importe quel écosystème RAG existant.
N'est pas un RAG embarqué — fournit les primitives d'accès pour l'utilisateur
qui souhaite connecter son propre système de mémoire vectorielle.

Résolution de DB_PATH (par ordre de priorité) :
  1. DIWALL_VECTOR_DB env var
  2. Clé "vector_db" dans /opt/diwall/diwall.conf
  3. _CADRE/MEMOIRE/chroma_db (si répertoire jumeau _CADRE/ présent)
  4. ~/Vaults/Diwall/chroma_db (défaut universel)

Dépendances optionnelles : chromadb, requests (non requises pour l'import).
"""

import os

_CONF_PATH = "/opt/diwall/diwall.conf"


def _chemin_db() -> str:
    """Résout le chemin de la base vectorielle ChromaDB."""
    if "DIWALL_VECTOR_DB" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VECTOR_DB"])

    if os.path.isfile(_CONF_PATH):
        import json
        with open(_CONF_PATH, encoding="utf-8") as f:
            conf = json.load(f)
        if "vector_db" in conf:
            return os.path.expanduser(conf["vector_db"])

    # Répertoire jumeau _CADRE/ (contexte de développement, sibling du dépôt)
    _repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _cadre_dir = os.path.normpath(os.path.join(_repo_dir, "..", "_CADRE"))
    if os.path.isdir(_cadre_dir):
        return os.path.join(_cadre_dir, "MEMOIRE", "chroma_db")

    return os.path.expanduser("~/Vaults/Diwall/chroma_db")


DB_PATH     = _chemin_db()
OLLAMA_URL  = os.environ.get("DIWALL_OLLAMA_URL",  "http://localhost:11434")
EMBED_MODEL = os.environ.get("DIWALL_EMBED_MODEL", "nomic-embed-text")


def get_client():
    """Retourne un client ChromaDB persistant. Requiert le paquet chromadb."""
    import chromadb
    os.makedirs(DB_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=DB_PATH)


def embed(texts: list[str]) -> list[list[float]]:
    """Génère les embeddings via Ollama (nomic-embed-text par défaut)."""
    import requests
    resp = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]
