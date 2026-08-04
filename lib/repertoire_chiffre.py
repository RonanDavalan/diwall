"""
repertoire_chiffre.py — Phase 6 + 7 : lecture de credentials depuis le répertoire chiffré Diwall.

Résolution du chemin du répertoire chiffré (par ordre de priorité) :
  1. Variable d'environnement DIWALL_SECRETS_DIR
  2. Variable d'environnement DIWALL_CONF → fichier .diwall.conf → clé "secrets_dir"
  3. Clé "secrets_dir" dans /opt/diwall/diwall.conf (JSON)
  4. Défaut : ~/Secrets/Diwall/

Algorithme de résolution du fichier de credentials dans secrets_dir :
  1. <hostname>_<port>.json  (racine, port-aware)
  2. <hostname>.json          (racine)
  3. **/<hostname>_<port>.json (récursif, profondeur arbitraire, port-aware)
  4. **/<hostname>.json        (récursif, profondeur arbitraire)
  → ambiguïté (>1 match) : FileNotFoundError avec liste des candidats

Phase 7 (gocryptfs) : SecretsFermesError levée si le répertoire chiffré est initialisé
mais non monté. Détection via /proc/mounts — agnostique du mode d'ouverture
(Plasma Vault, script, montage manuel).
"""

import hashlib
import json
import os
from urllib.parse import urlparse

_CONF_PATH = "/opt/diwall/diwall.conf"

_CHAMPS_CHECKSUM = ("username", "password", "totp_cle")


class SecretsFermesError(Exception):
    """Le répertoire chiffré gocryptfs est initialisé mais non monté.

    Code de sortie recommandé : 42 (symétrie avec Phase 7bis, spec 32_).
    L'opérateur doit monter le répertoire chiffré via scripts/monter-repertoire-chiffre.sh ou Plasma Vault.
    """
    CODE_SORTIE = 42


class SecretsChecksumError(SecretsFermesError):
    """Le checksum SHA256 du fichier d'identifiants ne correspond pas aux données lues.

    Indique une corruption silencieuse (FUSE) ou une modification non autorisée.
    Code de sortie recommandé : 42 (hérité de SecretsFermesError).
    """


class SecretsNonConfigureError(Exception):
    """diwall.conf absent ou sans clé secrets_dir — aucune configuration du répertoire chiffré active.

    Code de sortie recommandé : 43.
    Deux solutions : diwall.conf global (sudo cp /opt/diwall/diwall-sample.conf
    /opt/diwall/diwall.conf) ou DIWALL_CONF pour une configuration par projet
    (variable d'environnement, déjà supportée par _chemin_secrets()).
    """
    CODE_SORTIE = 43


def _lire_conf() -> dict:
    conf_path = os.path.expanduser(os.environ.get("DIWALL_CONF", _CONF_PATH))
    if os.path.isfile(conf_path):
        with open(conf_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _chemin_secrets() -> str:
    if "DIWALL_SECRETS_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_SECRETS_DIR"])
    if "DIWALL_CONF" in os.environ:
        conf_path = os.path.expanduser(os.environ["DIWALL_CONF"])
        if os.path.isfile(conf_path):
            with open(conf_path, encoding="utf-8") as f:
                conf_proj = json.load(f)
            if "secrets_dir" in conf_proj:
                secrets_dir = conf_proj["secrets_dir"]
                # chemin relatif résolu par rapport au répertoire du .diwall.conf
                if not os.path.isabs(os.path.expanduser(secrets_dir)):
                    secrets_dir = os.path.join(os.path.dirname(conf_path), secrets_dir)
                return os.path.realpath(os.path.expanduser(secrets_dir))
    conf = _lire_conf()
    if "secrets_dir" in conf:
        return os.path.expanduser(conf["secrets_dir"])
    conf_path_effectif = os.path.expanduser(os.environ.get("DIWALL_CONF", _CONF_PATH))
    raise SecretsNonConfigureError(
        f"Aucune configuration du répertoire chiffré active.\n"
        f"  {conf_path_effectif} est absent ou ne contient pas de clé 'secrets_dir'.\n"
        f"  Deux solutions possibles :\n"
        f"  1. Configuration globale — créez {conf_path_effectif} depuis le modèle :\n"
        f"       sudo cp /opt/diwall/diwall-sample.conf {conf_path_effectif}\n"
        f"       sudo nano {conf_path_effectif}  # → {{\"secrets_dir\": \"~/Secrets/<PROJET>/Diwall\"}}\n"
        f"  2. Configuration par projet — pointez DIWALL_CONF vers un fichier dédié, sans "
        f"toucher à la configuration globale :\n"
        f"       DIWALL_CONF=/chemin/vers/votre-projet/diwall.conf ...  # avant shot.py/rpa.py"
    )


def _chemin_secrets_crypt() -> str:
    """Chemin du répertoire chiffré gocryptfs (Phase 7).

    Résolution :
    1. Variable DIWALL_SECRETS_CRYPT_DIR
    2. Clé "secrets_crypt_dir" dans diwall.conf
    3. Défaut : secrets_dir + ".crypt"
    """
    if "DIWALL_SECRETS_CRYPT_DIR" in os.environ:
        return os.path.expanduser(os.environ["DIWALL_SECRETS_CRYPT_DIR"])
    conf = _lire_conf()
    if "secrets_crypt_dir" in conf:
        return os.path.expanduser(conf["secrets_crypt_dir"])
    return _chemin_secrets() + ".crypt"


def _repertoire_est_monte(secrets_dir: str) -> bool:
    """Vérifie si secrets_dir est sous un point de montage FUSE actif via /proc/mounts.

    Accepte secrets_dir = point de montage exact OU sous-dossier d'un montage FUSE
    (ex. ~/Secrets/<PROJET>/<NOM>/ est sous ~/Secrets/<PROJET> monté via gocryptfs).
    Restriction aux systèmes de fichiers FUSE pour ne pas ouvrir T1 aux disques
    persistants ordinaires (ext4, btrfs, etc.).

    Agnostique du mode d'ouverture : Plasma Vault, script, montage manuel —
    tous produisent une entrée FUSE dans /proc/mounts.
    Retourne True si incapable de lire /proc/mounts (ne pas bloquer le run).
    """
    chemin = os.path.realpath(os.path.expanduser(secrets_dir))
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


def _repertoire_initialise(crypt_dir: str) -> bool:
    """Vérifie si le répertoire chiffré gocryptfs a été initialisé (gocryptfs.conf présent)."""
    return os.path.isfile(
        os.path.join(os.path.expanduser(crypt_dir), "gocryptfs.conf")
    )


def _verifier_repertoire(secrets_dir: str) -> None:
    """Lève SecretsFermesError si le répertoire chiffré gocryptfs est initialisé mais non monté."""
    if not os.path.isdir(secrets_dir):
        crypt_dir = _chemin_secrets_crypt()
        if _repertoire_initialise(crypt_dir):
            raise SecretsFermesError(
                f"Le répertoire chiffré Diwall est initialisé mais non monté.\n"
                f"  Chiffré : {crypt_dir}\n"
                f"  Monter  : bash scripts/monter-repertoire-chiffre.sh  (ou via Plasma Vault)"
            )
    if os.path.isdir(secrets_dir) and not _repertoire_est_monte(secrets_dir):
        crypt_dir = _chemin_secrets_crypt()
        if _repertoire_initialise(crypt_dir):
            raise SecretsFermesError(
                f"Le répertoire chiffré Diwall est initialisé mais non monté.\n"
                f"  Point de montage : {secrets_dir}\n"
                f"  Monter : bash scripts/monter-repertoire-chiffre.sh  (ou via Plasma Vault)"
            )


def _trouver_fichier_secrets(secrets_dir: str, domaine: str, port: int | None = None) -> str:
    """Résout le chemin du fichier JSON de credentials dans secrets_dir.

    Ordre : plat port-aware → plat → récursif port-aware → récursif.
    Ambiguïté (>1 match récursif) → FileNotFoundError avec liste des candidats.
    """
    # Recherche plate (prioritaire, sans parcours disque)
    if port is not None:
        chemin = os.path.join(secrets_dir, f"{domaine}_{port}.json")
        if os.path.isfile(chemin):
            return chemin
    chemin = os.path.join(secrets_dir, f"{domaine}.json")
    if os.path.isfile(chemin):
        return chemin

    # Recherche récursive (followlinks=False pour confiner le parcours au répertoire chiffré)
    cible_port = f"{domaine}_{port}.json" if port is not None else None
    cible_base = f"{domaine}.json"
    par_port: list[str] = []
    par_base: list[str] = []
    for racine, _, fichiers in os.walk(secrets_dir, followlinks=False):
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
            f"Ambiguïté d'identifiants pour '{domaine}' : {len(candidats)} fichiers trouvés.\n"
            f"  {liste}\n"
            f"Affinez secrets_dir pour éliminer l'ambiguïté."
        )

    nom_attendu = f"{domaine}_{port}.json ou {domaine}.json" if port else f"{domaine}.json"
    raise FileNotFoundError(
        f"Identifiants introuvables pour '{domaine}' dans {secrets_dir}\n"
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
        raise SecretsChecksumError(
            f"Intégrité du fichier d'identifiants compromise : checksum invalide.\n"
            f"  Fichier   : {chemin}\n"
            f"  Attendu   : {attendu}\n"
            f"  Calculé   : {calcule}\n"
            f"Possible corruption FUSE silencieuse. Vérifiez le fichier d'identifiants."
        )


def domaine_depuis_url(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    return hostname.lower()


def port_depuis_url(url: str) -> int | None:
    """Extrait le port explicite de l'URL (absent → None)."""
    return urlparse(url).port


def lire_credential(domaine: str, cle: str, port: int | None = None) -> str:
    """Lit un credential depuis le répertoire chiffré.

    Cascade de détection (Phase 7) :
    1. secrets_dir inexistant → FileNotFoundError (répertoire chiffré jamais créé)
    2. répertoire chiffré initialisé + non monté → SecretsFermesError(42)
    3. fichier .json absent → FileNotFoundError
    4. clé absente → KeyError
    """
    secrets_dir = _chemin_secrets()
    _verifier_repertoire(secrets_dir)
    chemin = _trouver_fichier_secrets(secrets_dir, domaine, port)
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    _verifier_checksum(data, chemin)
    if cle not in data:
        raise KeyError(
            f"Clé '{cle}' absente du répertoire chiffré '{domaine}' ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )
    return data[cle]


def verifier_cles(domaine: str, cles, port: int | None = None) -> None:
    """Pré-validation fail-fast : vérifie répertoire chiffré + clés SANS lire les valeurs.

    Cascade identique à lire_credential :
    SecretsFermesError(42) → FileNotFoundError → KeyError
    """
    secrets_dir = _chemin_secrets()
    _verifier_repertoire(secrets_dir)
    chemin = _trouver_fichier_secrets(secrets_dir, domaine, port)
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    manquantes = [c for c in cles if c not in data]
    if manquantes:
        raise KeyError(
            f"Clé(s) {manquantes} absente(s) du répertoire chiffré '{domaine}' ({chemin})\n"
            f"Clés disponibles : {list(data.keys())}"
        )


def lire_totp(domaine: str) -> str:
    """Génère le code TOTP courant depuis la seed stockée dans le répertoire chiffré.

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
    que _repertoire_est_monte).
    """
    repertoire = os.path.dirname(os.path.abspath(chemin))
    if not _repertoire_est_monte(repertoire):
        if not os.path.isdir(repertoire):
            raise SecretsFermesError(
                f"Répertoire du fichier secrets introuvable — répertoire chiffré non monté ?\n"
                f"  Fichier    : {chemin}\n"
                f"  Répertoire : {repertoire}\n"
                f"  Montez le répertoire chiffré contenant ce fichier avant d'exécuter."
            )
        raise SecretsFermesError(
            f"Le répertoire du fichier secrets n'est pas un point de montage actif.\n"
            f"  Fichier    : {chemin}\n"
            f"  Répertoire : {repertoire}\n"
            f"  Seuls les points de montage actifs sont autorisés (répertoire chiffré gocryptfs, tmpfs…).\n"
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
    Vérifie répertoire chiffré + clés SANS lire les valeurs.
    """
    repertoire = os.path.dirname(os.path.abspath(chemin))
    if not _repertoire_est_monte(repertoire):
        if not os.path.isdir(repertoire):
            raise SecretsFermesError(
                f"Répertoire du fichier secrets introuvable — répertoire chiffré non monté ?\n"
                f"  Fichier    : {chemin}\n"
                f"  Répertoire : {repertoire}\n"
                f"  Montez le répertoire chiffré contenant ce fichier avant d'exécuter."
            )
        raise SecretsFermesError(
            f"Le répertoire du fichier secrets n'est pas un point de montage actif.\n"
            f"  Fichier    : {chemin}\n"
            f"  Répertoire : {repertoire}\n"
            f"  Seuls les points de montage actifs sont autorisés (répertoire chiffré gocryptfs, tmpfs…).\n"
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
