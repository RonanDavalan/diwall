"""
vector.py — Interface optionnelle vers une base vectorielle ChromaDB.

Permet à Diwall de s'interfacer avec n'importe quel écosystème RAG existant.
N'est pas un RAG embarqué — fournit les primitives d'accès pour l'utilisateur
qui souhaite connecter son propre système de mémoire vectorielle.

Résolution de DB_PATH (par ordre de priorité) :
  1. DIWALL_VECTOR_DB env var
  2. Clé "vector_db" dans le fichier lu par lib.repertoire_chiffre._lire_conf()
     (DIWALL_CONF, ou /opt/diwall/diwall.conf par défaut)
  3. _CADRE/MEMOIRE/chroma_db (si répertoire jumeau _CADRE/ présent)
  4. ~/Vaults/Diwall/chroma_db (défaut universel)

Dépendances optionnelles : chromadb, requests (non requises pour l'import).
"""

import os


def _chemin_db() -> str:
    """Résout le chemin de la base vectorielle ChromaDB."""
    if "DIWALL_VECTOR_DB" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VECTOR_DB"])

    # Audit 05/08/2026 (D-03) : une constante _CONF_PATH locale ignorait
    # DIWALL_CONF — un lecteur unique désormais, partagé avec repertoire_chiffre.
    try:
        from lib.repertoire_chiffre import _lire_conf
        conf = _lire_conf()
        if "vector_db" in conf:
            return os.path.expanduser(conf["vector_db"])
    except Exception:
        pass

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
    # L-05 (CHANTIER_SANITISATION.md, LOT 2, amendement 07/08/2026) : même
    # discipline que les autres répertoires sensibles du chantier — la base
    # vectorielle peut indexer des documents privés (_CADRE/MEMOIRE/).
    os.makedirs(DB_PATH, mode=0o700, exist_ok=True)
    os.chmod(DB_PATH, 0o700)
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
