"""Collecte des métadonnées modèles pour `diwall_meta.modeles_utilises` (v1.3).

Implémente §5.3 de `_CADRE/SPECIFICATIONS/33_CONFIG_OPERATEUR.md` :
- pour un modèle Ollama, interroge l'API HTTP locale `POST /api/show`
  pour récupérer `details.quantization_level` et le `digest`,
- pour un modèle Anthropic (mode --llm claude), produit une entrée
  statique sans quantization ni hash (champs `null`),
- cache mémoire par (endpoint, tag) pour la durée du processus,
  conforme §5.5 (un appel HTTP par modèle, < 50 ms total attendu).

Lecture seule, aucun effet de bord disque.
"""
from __future__ import annotations

import sys
from typing import Optional

import requests


_ENDPOINT_OLLAMA_DEFAUT = "http://localhost:11434"
_ENDPOINT_CLAUDE = "api.anthropic.com"
_TIMEOUT_SHOW_S = 5

_CACHE_SHOW: dict[tuple[str, str], dict] = {}
_CACHE_TAGS: dict[str, dict[str, str]] = {}


def _separer_tag_ollama(tag: str) -> tuple[str, str]:
    if ":" in tag:
        nom, version = tag.split(":", 1)
        return nom, version
    return tag, "latest"


def _interroger_api_show(endpoint: str, tag: str) -> Optional[dict]:
    cle = (endpoint, tag)
    if cle in _CACHE_SHOW:
        return _CACHE_SHOW[cle]
    try:
        resp = requests.post(
            f"{endpoint.rstrip('/')}/api/show",
            json={"name": tag},
            timeout=_TIMEOUT_SHOW_S,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(
            f"⚠ Diwall : API Ollama indisponible pour /api/show de "
            f"{tag} sur {endpoint} ({exc}). Métadonnées partielles.",
            file=sys.stderr,
        )
        _CACHE_SHOW[cle] = {}
        return None
    _CACHE_SHOW[cle] = data
    return data


def _interroger_api_tags(endpoint: str) -> dict[str, str]:
    """Retourne le dict {nom_tag: digest} pour tous les modèles installés.

    `/api/show` n'expose pas le digest (constaté Ollama 0.5+) ; c'est
    `/api/tags` qui le fournit. Un seul appel par endpoint, caché.
    """
    if endpoint in _CACHE_TAGS:
        return _CACHE_TAGS[endpoint]
    try:
        resp = requests.get(
            f"{endpoint.rstrip('/')}/api/tags",
            timeout=_TIMEOUT_SHOW_S,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(
            f"⚠ Diwall : API Ollama indisponible pour /api/tags sur "
            f"{endpoint} ({exc}). Hashes modèles non collectés.",
            file=sys.stderr,
        )
        _CACHE_TAGS[endpoint] = {}
        return {}
    index = {
        m.get("name"): m.get("digest")
        for m in (data.get("models") or [])
        if m.get("name")
    }
    _CACHE_TAGS[endpoint] = index
    return index


def collecter_modele_ollama(
    tag: str,
    role: str,
    endpoint: str = _ENDPOINT_OLLAMA_DEFAUT,
    inclure_hash: bool = True,
) -> dict:
    """Construit une entrée `modeles_utilises[]` pour un modèle Ollama.

    Si l'API Ollama est injoignable, les champs `quantization` et
    `hash_tag_ollama` sont mis à `null` plutôt que d'omettre l'entrée
    ou de lever : la traçabilité partielle est meilleure que pas de
    traçabilité.
    """
    nom, version = _separer_tag_ollama(tag)
    entree = {
        "nom": nom,
        "version": version,
        "quantization": None,
        "hash_tag_ollama": None,
        "role": role,
    }
    if endpoint != _ENDPOINT_OLLAMA_DEFAUT:
        entree["endpoint"] = endpoint

    data = _interroger_api_show(endpoint, tag)
    if data:
        details = data.get("details") or {}
        entree["quantization"] = details.get("quantization_level")

    if inclure_hash:
        index = _interroger_api_tags(endpoint)
        digest = index.get(tag)
        if digest:
            entree["hash_tag_ollama"] = digest

    return entree


def collecter_modele_claude(model_id: str, role: str) -> dict:
    """Construit une entrée `modeles_utilises[]` pour un modèle Anthropic.

    Aucun appel réseau : les métadonnées riches (quantization, digest)
    n'ont pas d'équivalent côté API Anthropic.
    """
    return {
        "nom": model_id,
        "version": None,
        "quantization": None,
        "hash_tag_ollama": None,
        "role": role,
        "endpoint": _ENDPOINT_CLAUDE,
    }


def reinitialiser_cache() -> None:
    """Vide les caches mémoire. Utile pour les tests."""
    _CACHE_SHOW.clear()
    _CACHE_TAGS.clear()
