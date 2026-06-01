"""
vault.py — Phase 6 : lecture de credentials depuis le vault Diwall.

Résolution du chemin vault (par ordre de priorité) :
  1. Variable d'environnement DIWALL_VAULT_DIR
  2. Clé "vault_dir" dans /opt/diwall/diwall.conf (JSON)
  3. Défaut : ~/Vaults/Diwall/

Format d'un fichier vault : <vault_dir>/<hostname>.json
  {"password": "...", "username": "admin", ...}
"""

import json
import os
from urllib.parse import urlparse

_CONF_PATH = "/opt/diwall/diwall.conf"
_VAULT_DEFAULT = os.path.expanduser("~/Vaults/Diwall")


def _chemin_vault() -> str:
    if "DIWALL_VAULT_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VAULT_DIR"])
    if os.path.isfile(_CONF_PATH):
        with open(_CONF_PATH, encoding="utf-8") as f:
            conf = json.load(f)
        if "vault_dir" in conf:
            return os.path.expanduser(conf["vault_dir"])
    return _VAULT_DEFAULT


def domaine_depuis_url(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    return hostname.lower()


def lire_credential(domaine: str, cle: str) -> str:
    vault_dir = _chemin_vault()
    chemin = os.path.join(vault_dir, f"{domaine}.json")
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"Vault introuvable pour le domaine '{domaine}' : {chemin}\n"
            f"Créez ce fichier avec les credentials JSON correspondants."
        )
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    if cle not in data:
        raise KeyError(
            f"Clé '{cle}' absente du vault '{domaine}' ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )
    return data[cle]


def verifier_cles(domaine: str, cles) -> None:
    """Pré-validation fail-fast : vérifie que le coffre du domaine existe et
    contient les clés demandées, SANS retourner ni exposer les valeurs.

    Permet à un appelant (rpa.py) de diagnostiquer tôt un coffre/clé
    absent sans jamais charger un credential en clair pour le transmettre.
    Lève FileNotFoundError (coffre absent) ou KeyError (clé manquante).
    """
    vault_dir = _chemin_vault()
    chemin = os.path.join(vault_dir, f"{domaine}.json")
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"Vault introuvable pour le domaine '{domaine}' : {chemin}\n"
            f"Créez ce fichier avec les credentials JSON correspondants."
        )
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    manquantes = [c for c in cles if c not in data]
    if manquantes:
        raise KeyError(
            f"Clé(s) {manquantes} absente(s) du vault '{domaine}' ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )
