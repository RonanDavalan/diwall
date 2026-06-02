"""
vault.py — Phase 6 + 7 : lecture de credentials depuis le vault Diwall.

Résolution du chemin vault (par ordre de priorité) :
  1. Variable d'environnement DIWALL_VAULT_DIR
  2. Clé "vault_dir" dans /opt/diwall/diwall.conf (JSON)
  3. Défaut : ~/Vaults/Diwall/

Format d'un fichier vault : <vault_dir>/<hostname>.json
  {"password": "...", "username": "admin", ...}

Phase 7 (gocryptfs) : VaultFermeError levée si le coffre est initialisé
mais non monté. Détection via /proc/mounts — agnostique du mode d'ouverture
(Plasma Vault, script, montage manuel).
"""

import json
import os
from urllib.parse import urlparse

_CONF_PATH = "/opt/diwall/diwall.conf"
_VAULT_DEFAULT = os.path.expanduser("~/Vaults/Diwall")


class VaultFermeError(Exception):
    """Le coffre gocryptfs est initialisé mais non monté.

    Code de sortie recommandé : 42 (symétrie avec Phase 7bis, spec 32_).
    L'opérateur doit monter le coffre via scripts/mount-vault.sh ou Plasma Vault.
    """
    CODE_SORTIE = 42


def _lire_conf() -> dict:
    if os.path.isfile(_CONF_PATH):
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _chemin_vault() -> str:
    if "DIWALL_VAULT_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VAULT_DIR"])
    conf = _lire_conf()
    if "vault_dir" in conf:
        return os.path.expanduser(conf["vault_dir"])
    return _VAULT_DEFAULT


def _chemin_vault_crypt() -> str:
    """Chemin du répertoire chiffré gocryptfs (Phase 7).

    Résolution :
    1. Variable DIWALL_VAULT_CRYPT_DIR
    2. Clé "vault_crypt_dir" dans diwall.conf
    3. Défaut : vault_dir + ".crypt"  (ex. ~/Vaults/Sillage/Diwall.crypt)
    """
    if "DIWALL_VAULT_CRYPT_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VAULT_CRYPT_DIR"])
    conf = _lire_conf()
    if "vault_crypt_dir" in conf:
        return os.path.expanduser(conf["vault_crypt_dir"])
    return _chemin_vault() + ".crypt"


def _coffre_est_monte(vault_dir: str) -> bool:
    """Vérifie si vault_dir est un point de montage FUSE actif via /proc/mounts.

    Agnostique du mode d'ouverture : Plasma Vault, script, montage manuel —
    tous produisent une entrée dans /proc/mounts.
    Retourne True si incapable de lire /proc/mounts (ne pas bloquer le run).
    """
    chemin = os.path.realpath(os.path.expanduser(vault_dir))
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            return any(chemin in ligne for ligne in f)
    except OSError:
        return True


def _coffre_initialise(crypt_dir: str) -> bool:
    """Vérifie si le coffre gocryptfs a été initialisé (gocryptfs.conf présent)."""
    return os.path.isfile(
        os.path.join(os.path.expanduser(crypt_dir), "gocryptfs.conf")
    )


def domaine_depuis_url(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    return hostname.lower()


def lire_credential(domaine: str, cle: str) -> str:
    """Lit un credential depuis le vault.

    Cascade de détection (Phase 7) :
    1. vault_dir inexistant → FileNotFoundError (vault jamais créé)
    2. coffre initialisé + non monté → VaultFermeError(42)
    3. vault_dir existe + fichier .json absent → FileNotFoundError
    4. clé absente → KeyError
    """
    vault_dir = _chemin_vault()

    # Phase 7 : détecter un coffre fermé avant d'essayer de lire
    if not os.path.isdir(vault_dir):
        crypt_dir = _chemin_vault_crypt()
        if _coffre_initialise(crypt_dir):
            raise VaultFermeError(
                f"Le coffre Diwall est initialisé mais non monté.\n"
                f"  Chiffré : {crypt_dir}\n"
                f"  Monter  : bash scripts/mount-vault.sh  "
                f"(ou via Plasma Vault)"
            )

    if os.path.isdir(vault_dir) and not _coffre_est_monte(vault_dir):
        crypt_dir = _chemin_vault_crypt()
        if _coffre_initialise(crypt_dir):
            raise VaultFermeError(
                f"Le coffre Diwall est initialisé mais non monté.\n"
                f"  Point de montage : {vault_dir}\n"
                f"  Monter : bash scripts/mount-vault.sh  (ou via Plasma Vault)"
            )

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
    """Pré-validation fail-fast : vérifie coffre + clés SANS lire les valeurs.

    Cascade identique à lire_credential :
    VaultFermeError(42) → FileNotFoundError → KeyError
    """
    vault_dir = _chemin_vault()

    if not os.path.isdir(vault_dir):
        crypt_dir = _chemin_vault_crypt()
        if _coffre_initialise(crypt_dir):
            raise VaultFermeError(
                f"Le coffre Diwall est initialisé mais non monté.\n"
                f"  Monter : bash scripts/mount-vault.sh  (ou via Plasma Vault)"
            )

    if os.path.isdir(vault_dir) and not _coffre_est_monte(vault_dir):
        crypt_dir = _chemin_vault_crypt()
        if _coffre_initialise(crypt_dir):
            raise VaultFermeError(
                f"Le coffre Diwall est initialisé mais non monté.\n"
                f"  Monter : bash scripts/mount-vault.sh  (ou via Plasma Vault)"
            )

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


def lire_totp(domaine: str) -> str:
    """Génère le code TOTP courant depuis la seed stockée dans le vault.

    Lit la clé 'totp_cle' (seed base32) pour le domaine et retourne le
    code à 6 chiffres valable pour la fenêtre de 30 secondes courante.
    Requiert pyotp>=2.9 (requirements.txt).
    """
    import pyotp
    seed = lire_credential(domaine, "totp_cle")
    return pyotp.TOTP(seed).now()
