"""
vault.py — Phase 6 + 7 : lecture de credentials depuis le vault Diwall.

Résolution du chemin vault (par ordre de priorité) :
  1. Variable d'environnement DIWALL_VAULT_DIR
  2. Variable d'environnement DIWALL_CONF → fichier .diwall.conf → clé "vault_dir"
  3. Clé "vault_dir" dans /opt/diwall/diwall.conf (JSON)
  4. Défaut : ~/Vaults/Diwall/

Algorithme de résolution du fichier de credentials dans vault_dir :
  1. <hostname>_<port>.json  (racine, port-aware)
  2. <hostname>.json          (racine)
  3. **/<hostname>_<port>.json (récursif, profondeur arbitraire, port-aware)
  4. **/<hostname>.json        (récursif, profondeur arbitraire)
  → ambiguïté (>1 match) : FileNotFoundError avec liste des candidats

Phase 7 (gocryptfs) : VaultFermeError levée si le coffre est initialisé
mais non monté. Détection via /proc/mounts — agnostique du mode d'ouverture
(Plasma Vault, script, montage manuel).
"""

import hashlib
import json
import os
from urllib.parse import urlparse

_CONF_PATH = "/opt/diwall/diwall.conf"

_CHAMPS_CHECKSUM = ("username", "password", "totp_cle")


class VaultFermeError(Exception):
    """Le coffre gocryptfs est initialisé mais non monté.

    Code de sortie recommandé : 42 (symétrie avec Phase 7bis, spec 32_).
    L'opérateur doit monter le coffre via scripts/mount-vault.sh ou Plasma Vault.
    """
    CODE_SORTIE = 42


class VaultChecksumError(VaultFermeError):
    """Le checksum SHA256 du fichier vault ne correspond pas aux données lues.

    Indique une corruption silencieuse (FUSE) ou une modification non autorisée.
    Code de sortie recommandé : 42 (hérité de VaultFermeError).
    """


class VaultNonConfigureError(Exception):
    """diwall.conf absent ou sans clé vault_dir — aucune configuration vault active.

    Code de sortie recommandé : 43.
    Créer diwall.conf depuis le modèle :
      sudo cp /opt/diwall/diwall-sample.conf /opt/diwall/diwall.conf
      sudo nano /opt/diwall/diwall.conf  # → {"vault_dir": "~/Vaults/<PROJET>/Diwall"}
    """
    CODE_SORTIE = 43


def _lire_conf() -> dict:
    if os.path.isfile(_CONF_PATH):
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _chemin_vault() -> str:
    if "DIWALL_VAULT_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VAULT_DIR"])
    if "DIWALL_CONF" in os.environ:
        conf_path = os.path.expanduser(os.environ["DIWALL_CONF"])
        if os.path.isfile(conf_path):
            with open(conf_path, encoding="utf-8") as f:
                conf_proj = json.load(f)
            if "vault_dir" in conf_proj:
                vault_dir = conf_proj["vault_dir"]
                # chemin relatif résolu par rapport au répertoire du .diwall.conf
                if not os.path.isabs(os.path.expanduser(vault_dir)):
                    vault_dir = os.path.join(os.path.dirname(conf_path), vault_dir)
                return os.path.realpath(os.path.expanduser(vault_dir))
    conf = _lire_conf()
    if "vault_dir" in conf:
        return os.path.expanduser(conf["vault_dir"])
    raise VaultNonConfigureError(
        f"Aucune configuration vault active.\n"
        f"  {_CONF_PATH} est absent ou ne contient pas de clé 'vault_dir'.\n"
        f"  Créez-le depuis le modèle :\n"
        f"    sudo cp /opt/diwall/diwall-sample.conf {_CONF_PATH}\n"
        f"    sudo nano {_CONF_PATH}  # → {{\"vault_dir\": \"~/Vaults/<PROJET>/Diwall\"}}"
    )


def _chemin_vault_crypt() -> str:
    """Chemin du répertoire chiffré gocryptfs (Phase 7).

    Résolution :
    1. Variable DIWALL_VAULT_CRYPT_DIR
    2. Clé "vault_crypt_dir" dans diwall.conf
    3. Défaut : vault_dir + ".crypt"
    """
    if "DIWALL_VAULT_CRYPT_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_VAULT_CRYPT_DIR"])
    conf = _lire_conf()
    if "vault_crypt_dir" in conf:
        return os.path.expanduser(conf["vault_crypt_dir"])
    return _chemin_vault() + ".crypt"


def _coffre_est_monte(vault_dir: str) -> bool:
    """Vérifie si vault_dir est sous un point de montage FUSE actif via /proc/mounts.

    Accepte vault_dir = point de montage exact OU sous-dossier d'un montage FUSE
    (ex. ~/Vaults/Sillage/Diwall/ est sous ~/Vaults/Sillage monté via gocryptfs).
    Restriction aux systèmes de fichiers FUSE pour ne pas ouvrir T1 aux disques
    persistants ordinaires (ext4, btrfs, etc.).

    Agnostique du mode d'ouverture : Plasma Vault, script, montage manuel —
    tous produisent une entrée FUSE dans /proc/mounts.
    Retourne True si incapable de lire /proc/mounts (ne pas bloquer le run).
    """
    chemin = os.path.realpath(os.path.expanduser(vault_dir))
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for ligne in f:
                parties = ligne.split()
                if len(parties) < 3:
                    continue
                point, fstype = parties[1], parties[2]
                if "fuse" not in fstype:
                    continue
                if chemin == point or chemin.startswith(point + "/"):
                    return True
        return False
    except OSError:
        return True


def _coffre_initialise(crypt_dir: str) -> bool:
    """Vérifie si le coffre gocryptfs a été initialisé (gocryptfs.conf présent)."""
    return os.path.isfile(
        os.path.join(os.path.expanduser(crypt_dir), "gocryptfs.conf")
    )


def _verifier_coffre(vault_dir: str) -> None:
    """Lève VaultFermeError si le coffre gocryptfs est initialisé mais non monté."""
    if not os.path.isdir(vault_dir):
        crypt_dir = _chemin_vault_crypt()
        if _coffre_initialise(crypt_dir):
            raise VaultFermeError(
                f"Le coffre Diwall est initialisé mais non monté.\n"
                f"  Chiffré : {crypt_dir}\n"
                f"  Monter  : bash scripts/mount-vault.sh  (ou via Plasma Vault)"
            )
    if os.path.isdir(vault_dir) and not _coffre_est_monte(vault_dir):
        crypt_dir = _chemin_vault_crypt()
        if _coffre_initialise(crypt_dir):
            raise VaultFermeError(
                f"Le coffre Diwall est initialisé mais non monté.\n"
                f"  Point de montage : {vault_dir}\n"
                f"  Monter : bash scripts/mount-vault.sh  (ou via Plasma Vault)"
            )


def _trouver_fichier_vault(vault_dir: str, domaine: str, port: int | None = None) -> str:
    """Résout le chemin du fichier JSON de credentials dans vault_dir.

    Ordre : plat port-aware → plat → récursif port-aware → récursif.
    Ambiguïté (>1 match récursif) → FileNotFoundError avec liste des candidats.
    """
    # Recherche plate (prioritaire, sans parcours disque)
    if port is not None:
        chemin = os.path.join(vault_dir, f"{domaine}_{port}.json")
        if os.path.isfile(chemin):
            return chemin
    chemin = os.path.join(vault_dir, f"{domaine}.json")
    if os.path.isfile(chemin):
        return chemin

    # Recherche récursive (followlinks=False pour confiner le parcours au coffre)
    cible_port = f"{domaine}_{port}.json" if port is not None else None
    cible_base = f"{domaine}.json"
    par_port: list[str] = []
    par_base: list[str] = []
    for racine, _, fichiers in os.walk(vault_dir, followlinks=False):
        if cible_port and cible_port in fichiers:
            par_port.append(os.path.join(racine, cible_port))
        if cible_base in fichiers:
            par_base.append(os.path.join(racine, cible_base))
    candidats = par_port if par_port else par_base

    if len(candidats) == 1:
        return candidats[0]
    if len(candidats) > 1:
        liste = "\n  ".join(sorted(candidats))
        raise FileNotFoundError(
            f"Ambiguïté vault pour '{domaine}' : {len(candidats)} fichiers trouvés.\n"
            f"  {liste}\n"
            f"Affinez vault_dir pour éliminer l'ambiguïté."
        )

    nom_attendu = f"{domaine}_{port}.json ou {domaine}.json" if port else f"{domaine}.json"
    raise FileNotFoundError(
        f"Vault introuvable pour '{domaine}' dans {vault_dir}\n"
        f"  Nom attendu (urlparse(url).hostname) : {nom_attendu}\n"
        f"Créez ce fichier avec les credentials JSON correspondants."
    )


def _verifier_checksum(data: dict, chemin: str) -> None:
    """Vérifie le checksum SHA256 si la clé 'checksum' est présente dans data.

    Le checksum couvre les champs sensibles (username, password, totp_cle)
    sérialisés JSON en ordre lexicographique, encodés UTF-8.
    Aucune action si 'checksum' absent (opt-in strict).
    """
    attendu = data.get("checksum")
    if not attendu:
        return
    champs = {k: data[k] for k in sorted(_CHAMPS_CHECKSUM) if k in data}
    calcule = "sha256:" + hashlib.sha256(
        json.dumps(champs, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if calcule != attendu:
        raise VaultChecksumError(
            f"Intégrité vault compromise : checksum invalide.\n"
            f"  Fichier   : {chemin}\n"
            f"  Attendu   : {attendu}\n"
            f"  Calculé   : {calcule}\n"
            f"Possible corruption FUSE silencieuse. Vérifiez le fichier vault."
        )


def domaine_depuis_url(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    return hostname.lower()


def port_depuis_url(url: str) -> int | None:
    """Extrait le port explicite de l'URL (absent → None)."""
    return urlparse(url).port


def lire_credential(domaine: str, cle: str, port: int | None = None) -> str:
    """Lit un credential depuis le vault.

    Cascade de détection (Phase 7) :
    1. vault_dir inexistant → FileNotFoundError (vault jamais créé)
    2. coffre initialisé + non monté → VaultFermeError(42)
    3. fichier .json absent → FileNotFoundError
    4. clé absente → KeyError
    """
    vault_dir = _chemin_vault()
    _verifier_coffre(vault_dir)
    chemin = _trouver_fichier_vault(vault_dir, domaine, port)
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    _verifier_checksum(data, chemin)
    if cle not in data:
        raise KeyError(
            f"Clé '{cle}' absente du vault '{domaine}' ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )
    return data[cle]


def verifier_cles(domaine: str, cles, port: int | None = None) -> None:
    """Pré-validation fail-fast : vérifie coffre + clés SANS lire les valeurs.

    Cascade identique à lire_credential :
    VaultFermeError(42) → FileNotFoundError → KeyError
    """
    vault_dir = _chemin_vault()
    _verifier_coffre(vault_dir)
    chemin = _trouver_fichier_vault(vault_dir, domaine, port)
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


def lire_credential_fichier(chemin: str, cle: str) -> str:
    """Lit un credential depuis un fichier désigné explicitement (--secrets).

    T1 (montage strict) : le répertoire parent doit être un point de montage
    actif dans /proc/mounts. Refuse tout fichier sur disque nu persistant
    (ex. /tmp) — ferme le contournement identifié en session 33.
    Fallback : si /proc/mounts est illisible, ne bloque pas (même logique
    que _coffre_est_monte).
    """
    repertoire = os.path.dirname(os.path.abspath(chemin))
    if not _coffre_est_monte(repertoire):
        if not os.path.isdir(repertoire):
            raise VaultFermeError(
                f"Répertoire du fichier secrets introuvable — coffre non monté ?\n"
                f"  Fichier    : {chemin}\n"
                f"  Répertoire : {repertoire}\n"
                f"  Montez le coffre contenant ce fichier avant d'exécuter."
            )
        raise VaultFermeError(
            f"Le répertoire du fichier secrets n'est pas un point de montage actif.\n"
            f"  Fichier    : {chemin}\n"
            f"  Répertoire : {repertoire}\n"
            f"  Seuls les points de montage actifs sont autorisés (coffre gocryptfs, tmpfs…).\n"
            f"  Refusé : disque nu persistant (ex. /tmp, ~/Documents)."
        )
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"Fichier secrets introuvable : {chemin}"
        )
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    _verifier_checksum(data, chemin)
    if cle not in data:
        raise KeyError(
            f"Clé '{cle}' absente du fichier secrets ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )
    return data[cle]


def verifier_cles_fichier(chemin: str, cles) -> None:
    """Pré-validation fail-fast sur un fichier de secrets explicite (--secrets).

    Même vérification de montage T1 que lire_credential_fichier.
    Vérifie coffre + clés SANS lire les valeurs.
    """
    repertoire = os.path.dirname(os.path.abspath(chemin))
    if not _coffre_est_monte(repertoire):
        if not os.path.isdir(repertoire):
            raise VaultFermeError(
                f"Répertoire du fichier secrets introuvable — coffre non monté ?\n"
                f"  Fichier    : {chemin}\n"
                f"  Répertoire : {repertoire}\n"
                f"  Montez le coffre contenant ce fichier avant d'exécuter."
            )
        raise VaultFermeError(
            f"Le répertoire du fichier secrets n'est pas un point de montage actif.\n"
            f"  Fichier    : {chemin}\n"
            f"  Répertoire : {repertoire}\n"
            f"  Seuls les points de montage actifs sont autorisés (coffre gocryptfs, tmpfs…).\n"
            f"  Refusé : disque nu persistant (ex. /tmp, ~/Documents)."
        )
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"Fichier secrets introuvable : {chemin}"
        )
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    manquantes = [c for c in cles if c not in data]
    if manquantes:
        raise KeyError(
            f"Clé(s) {manquantes} absente(s) du fichier secrets ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )


def lire_totp_fichier(chemin: str) -> str:
    """Génère le code TOTP depuis la seed dans un fichier secrets explicite (--secrets).

    Délègue à lire_credential_fichier (vérification montage T1 incluse).
    """
    import pyotp
    seed = lire_credential_fichier(chemin, "totp_cle")
    return pyotp.TOTP(seed).now()
