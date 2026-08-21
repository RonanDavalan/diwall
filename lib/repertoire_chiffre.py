"""
repertoire_chiffre.py — Phase 6 + 7 : lecture de credentials depuis le répertoire chiffré Diwall.

Résolution du chemin du répertoire chiffré (par ordre de priorité) :
  1. Variable d'environnement DIWALL_SECRETS_DIR
  2. Variable d'environnement DIWALL_CONF → fichier .diwall.conf → clé "secrets_dir"
  3. Clé "secrets_dir" dans /opt/diwall/diwall.conf (JSON)
  4. Défaut : ~/Vaults/Diwall/

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
import sys
from urllib.parse import urlparse

from lib.sanitisation import filtrer_noms_cles_sensibles

_CONF_PATH = "/opt/diwall/diwall.conf"

_CHAMPS_CHECKSUM = ("username", "password", "totp_cle", "origines_autorisees")


class SecretsFermesError(Exception):
    """Le répertoire chiffré gocryptfs est initialisé mais non monté.

    Code de sortie recommandé : 42 (symétrie avec Phase 7bis, spec 32_).
    L'opérateur doit monter le répertoire chiffré via scripts/monter-repertoire-chiffre.sh ou Plasma Vault.
    """
    CODE_SORTIE = 42


class SecretsChecksumError(SecretsFermesError):
    """Le checksum SHA256 du fichier d'identifiants ne correspond pas aux données lues.

    Audit 06/08/2026 (C-15b) : détecte une corruption silencieuse du
    support (FUSE), pas une modification malveillante intentionnelle — qui
    aurait recalculé le checksum en même temps que la valeur. L'ancien
    libellé (« modification non autorisée ») promettait une garantie
    d'authenticité que ce mécanisme d'intégrité ne tient pas.
    Code de sortie recommandé : 42 (hérité de SecretsFermesError).
    """


class SecretsOriginesManquantesError(SecretsFermesError):
    """Fichier --secrets sans clé 'origines_autorisees' — obligatoire depuis le 05/08/2026.

    Audit de sécurité Claude Opus 5 (C-03, _CADRE/MEMOIRE/audit-2026-08-05.md) :
    --secrets rompt le liage domaine que lire_credential assure par défaut via
    domaine_depuis_url(page.url). Décision du 05/08/2026, rupture franche
    (_CADRE/SPECIFICATIONS/25_PHASE6_RPA_IDENTIFIANTS.md) : hérite de
    SecretsFermesError, code de sortie 42 (même famille de refus).
    """


class SecretsOrigineNonAutoriseeError(SecretsFermesError):
    """Le domaine de la page courante n'est pas dans 'origines_autorisees' du fichier --secrets.

    Refus de saisie — protection contre une redirection vers un domaine tiers
    pendant qu'un fichier --secrets est actif. Même famille que SecretsFermesError.
    """


class SecretsNonConfigureError(Exception):
    """diwall.conf absent ou sans clé secrets_dir — aucune configuration du répertoire chiffré active.

    Code de sortie recommandé : 43.
    Deux solutions : diwall.conf global (sudo cp /opt/diwall/diwall-sample.conf
    /opt/diwall/diwall.conf) ou DIWALL_CONF pour une configuration par projet
    (variable d'environnement, déjà supportée par _chemin_secrets()).
    """
    CODE_SORTIE = 43


def resoudre_chemin_reel(chemin: str) -> str:
    """Résout un chemin en chemin réel : liens symboliques suivis, `~/` développé.

    Point de passage unique pour toute résolution de chemin de sécurité liée
    au répertoire chiffré. Un lien symbolique placé à l'intérieur d'un
    répertoire chiffré monté et pointant vers un fichier sur disque nu n'est
    accepté par aucun contrôle qui passe par cette fonction plutôt que par
    `os.path.abspath` (audit 06/08/2026, F-01 — trois réimplémentations
    indépendantes de `realpath` dans `lib/journal.py`, une résolution par
    `abspath` ici même qui ne suivait pas les liens, jamais harmonisées).
    """
    return os.path.realpath(os.path.expanduser(chemin))


def _lire_conf() -> dict:
    conf_path = os.path.expanduser(os.environ.get("DIWALL_CONF", _CONF_PATH))
    if os.path.isfile(conf_path):
        with open(conf_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _chemin_secrets_avec_source() -> tuple[str, str]:
    """Résout secrets_dir et sa provenance (REX #12 : la résolution est silencieuse

    sur la provenance, un projet qui invoque Diwall sans positionner
    DIWALL_SECRETS_DIR retombe sur la conf globale de la machine — partagée
    entre tous les projets — sans que rien ne le signale. La provenance est
    exposée par la boussole via secrets_dir_info() ci-dessous.
    """
    if "DIWALL_SECRETS_DIR" in os.environ:
        return resoudre_chemin_reel(os.environ["DIWALL_SECRETS_DIR"]), "env:DIWALL_SECRETS_DIR"
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
                return resoudre_chemin_reel(secrets_dir), f"conf:{conf_path}"
    conf = _lire_conf()
    if "secrets_dir" in conf:
        conf_path_effectif = os.path.expanduser(os.environ.get("DIWALL_CONF", _CONF_PATH))
        return resoudre_chemin_reel(conf["secrets_dir"]), f"conf:{conf_path_effectif}"
    conf_path_effectif = os.path.expanduser(os.environ.get("DIWALL_CONF", _CONF_PATH))
    raise SecretsNonConfigureError(
        f"Aucune configuration du répertoire chiffré active.\n"
        f"  {conf_path_effectif} est absent ou ne contient pas de clé 'secrets_dir'.\n"
        f"  Deux solutions possibles :\n"
        f"  1. Configuration globale — créez {conf_path_effectif} depuis le modèle :\n"
        f"       sudo cp /opt/diwall/diwall-sample.conf {conf_path_effectif}\n"
        f"       sudo nano {conf_path_effectif}  # → {{\"secrets_dir\": \"~/Vaults/<PROJET>/Diwall\"}}\n"
        f"  2. Configuration par projet — pointez DIWALL_CONF vers un fichier dédié, sans "
        f"toucher à la configuration globale :\n"
        f"       DIWALL_CONF=/chemin/vers/votre-projet/diwall.conf ...  # avant shot.py/rpa.py"
    )


def _chemin_secrets() -> str:
    return _chemin_secrets_avec_source()[0]


def secrets_dir_info() -> tuple[str | None, str]:
    """secrets_dir effectif et sa provenance, pour affichage boussole. Ne lève jamais.

    Provenance : "env:DIWALL_SECRETS_DIR", "env:DIWALL_CONF", "conf:<chemin>"
    (diwall.conf global ou par projet), ou "non_configure" si aucune source
    n'est active (chemin alors None).
    """
    try:
        return _chemin_secrets_avec_source()
    except SecretsNonConfigureError:
        return None, "non_configure"
    except Exception:
        # Diagnostic passif : une conf illisible/corrompue ne doit jamais
        # faire échouer une commande qui n'a besoin d'aucun credential.
        return None, "erreur_resolution"


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
    (ex. ~/Vaults/<PROJET>/<NOM>/ est sous ~/Vaults/<PROJET> monté via gocryptfs).
    Restriction aux systèmes de fichiers FUSE pour ne pas ouvrir T1 aux disques
    persistants ordinaires (ext4, btrfs, etc.).

    Agnostique du mode d'ouverture : Plasma Vault, script, montage manuel —
    tous produisent une entrée FUSE dans /proc/mounts.

    LOT 3 (CHANTIER_SANITISATION.md, G-22, audit 07/08/2026) : incapable de
    lire /proc/mounts → traité comme non monté (fail-closed). Le comportement
    précédent (True — « ne pas bloquer le run ») inversait le sens voulu :
    une incapacité à vérifier le montage n'est pas une preuve de montage.
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
        return False


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


def _verifier_cible_montee(chemin_resolu: str, description: str = "fichier secrets") -> None:
    """Lève SecretsFermesError si le répertoire de `chemin_resolu` (déjà
    résolu par `resoudre_chemin_reel`) n'est pas un point de montage FUSE
    actif — même contrôle que le montage d'un fichier `--secrets` explicite,
    factorisé pour servir aussi la résolution par nom d'hôte
    (`_resoudre_et_verifier` ci-dessous). Un lien symbolique dont la cible
    réelle vit hors de tout montage FUSE (disque nu) est refusé ici ; un lien
    qui redirige vers un *autre* répertoire monté (ex. un répertoire chiffré
    voisin dans le même coffre) reste accepté — c'est le motif d'usage réel
    observé (`__HOST_SERVICE__.json`, session 80).
    """
    repertoire = os.path.dirname(chemin_resolu)
    if not _repertoire_est_monte(repertoire):
        if not os.path.isdir(repertoire):
            raise SecretsFermesError(
                f"Répertoire du {description} introuvable — répertoire chiffré non monté ?\n"
                f"  Fichier    : {chemin_resolu}\n"
                f"  Répertoire : {repertoire}\n"
                f"  Montez le répertoire chiffré contenant ce fichier avant d'exécuter."
            )
        raise SecretsFermesError(
            f"Le répertoire du {description} n'est pas un point de montage actif.\n"
            f"  Fichier    : {chemin_resolu}\n"
            f"  Répertoire : {repertoire}\n"
            f"  Seuls les points de montage actifs sont autorisés (répertoire chiffré gocryptfs, tmpfs…).\n"
            f"  Refusé : disque nu persistant (ex. /tmp, ~/Documents)."
        )


def _resoudre_et_verifier(chemin: str) -> str:
    """Résout `chemin` en chemin réel et vérifie que sa cible reste sous un
    point de montage FUSE actif.

    Un lien symbolique placé dans le répertoire chiffré et pointant vers un
    fichier sur disque nu est ainsi refusé sur sa cible réelle, jamais ouvert
    (audit 06/08/2026, F-01) — même contrôle que
    `_verifier_montage_fichier_secrets`, appliqué ici à la résolution par nom
    d'hôte plutôt qu'à un `--secrets` explicite.
    """
    reel = resoudre_chemin_reel(chemin)
    _verifier_cible_montee(reel, "fichier de credentials")
    return reel


def _trouver_fichier_secrets(secrets_dir: str, domaine: str, port: int | None = None) -> str:
    """Résout le chemin du fichier JSON de credentials dans secrets_dir.

    Ordre : plat port-aware → plat → récursif port-aware → récursif.
    Ambiguïté (>1 match récursif) → FileNotFoundError avec liste des candidats.
    """
    # Recherche plate (prioritaire, sans parcours disque)
    if port is not None:
        chemin = os.path.join(secrets_dir, f"{domaine}_{port}.json")
        if os.path.isfile(chemin):
            return _resoudre_et_verifier(chemin)
    chemin = os.path.join(secrets_dir, f"{domaine}.json")
    if os.path.isfile(chemin):
        return _resoudre_et_verifier(chemin)

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
        return _resoudre_et_verifier(candidats[0])
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
        # Audit 06/08/2026 (F-03) : os.path.basename sur tout chemin de
        # fichier d'identifiants dans un message d'exception — le chemin
        # complet expose le nom d'utilisateur local et l'arborescence du
        # coffre ; même traitement appliqué à chaque site de ce module.
        raise SecretsChecksumError(
            f"Intégrité du fichier d'identifiants compromise : checksum invalide.\n"
            f"  Fichier   : {os.path.basename(chemin)}\n"
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
            f"Clé '{cle}' absente du répertoire chiffré '{domaine}' ({os.path.basename(chemin)})\n"
            f"Clés disponibles : {filtrer_noms_cles_sensibles(list(data.keys()))}"
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
            f"Clé(s) {manquantes} absente(s) du répertoire chiffré '{domaine}' ({os.path.basename(chemin)})\n"
            f"Clés disponibles : {filtrer_noms_cles_sensibles(list(data.keys()))}"
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


def _verifier_origines_autorisees(data: dict, chemin: str, url_page: str | None = None) -> None:
    """Audit 05/08/2026 (C-03) : liage domaine obligatoire pour --secrets.

    Sans --secrets, lire_credential lie chaque lecture au domaine réellement
    chargé (domaine_depuis_url(page.url)) : une redirection vers un domaine
    tiers fait échouer la résolution. --secrets rompt ce liage par défaut.
    Décision du 05/08/2026, rupture franche, sans période de compatibilité
    (_CADRE/SPECIFICATIONS/25_PHASE6_RPA_IDENTIFIANTS.md).
    """
    origines = data.get("origines_autorisees")
    if origines is None:
        raise SecretsOriginesManquantesError(
            f"Fichier secrets sans clé 'origines_autorisees' — obligatoire depuis le 05/08/2026.\n"
            f"  Fichier : {os.path.basename(chemin)}\n"
            f"  Ajoutez : \"origines_autorisees\": [\"hostname.exemple\"]\n"
            f"  Sans cette clé, --secrets rompt le liage domaine que lire_credential "
            f"assure par défaut — refus tant qu'elle n'est pas déclarée."
        )
    if url_page is not None:
        domaine = domaine_depuis_url(url_page)
        autorisees = {str(o).lower() for o in origines}
        if domaine not in autorisees:
            raise SecretsOrigineNonAutoriseeError(
                f"Origine '{domaine}' absente de 'origines_autorisees' du fichier secrets.\n"
                f"  Fichier     : {os.path.basename(chemin)}\n"
                f"  Autorisées  : {sorted(autorisees)}\n"
                f"  Refus de lecture — possible redirection vers un domaine tiers."
            )


def _verifier_montage_fichier_secrets(chemin: str) -> str:
    """Vérifie T1 (montage strict) pour un fichier de secrets explicite.

    Retourne le chemin réel résolu — l'appelant doit ouvrir CE chemin, pas
    le chemin d'origine, pour ne pas rouvrir entre validation et lecture la
    fenêtre que la résolution vient de fermer.

    Factorisé depuis lire_credential_fichier/verifier_cles_fichier (chantier
    qualité 05/08/2026) — bloc dupliqué verbatim entre les deux. Le répertoire
    parent doit être un point de montage actif dans /proc/mounts ; refuse
    tout fichier sur disque nu persistant (ex. /tmp) — ferme le contournement
    identifié en session 33. Fallback : si /proc/mounts est illisible, ne
    bloque pas (même logique que _repertoire_est_monte). Lève aussi
    FileNotFoundError si le fichier lui-même est absent une fois le montage
    validé.

    Audit 06/08/2026 (F-01) : la version précédente calculait le répertoire
    à contrôler avec `os.path.dirname(os.path.abspath(chemin))` —
    `abspath` ne résout pas les liens symboliques, alors que la lecture qui
    suivait, si. Un lien placé dans le répertoire chiffré monté et pointant
    vers un fichier sur disque nu était donc accepté : le contrôle validait
    le répertoire du lien, la lecture consommait sa cible. `chemin` est
    désormais résolu en premier ; le contrôle et l'ouverture portent tous
    deux sur la cible réelle.
    """
    chemin = resoudre_chemin_reel(chemin)
    _verifier_cible_montee(chemin, "fichier secrets")
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"Fichier secrets introuvable : {os.path.basename(chemin)}"
        )
    # Audit 06/08/2026 (F-07) : T1 vérifie le montage du répertoire, jamais
    # le mode du fichier lui-même. Un fichier d'identifiants laissé lisible
    # par le groupe ou par tous (constaté : 0664) était accepté sans le
    # moindre signal.
    # LOT 3 (CHANTIER_SANITISATION.md, audit 07/08/2026, « Priorité 3 ») :
    # avertissement seul remplacé par un refus — aligne ce contrôle sur la
    # même politique stricte que _verifier_origines_autorisees (même famille
    # SecretsFermesError). Le mode d'un fichier hérité d'une copie/
    # synchronisation n'est plus toléré silencieusement.
    try:
        mode = os.stat(chemin).st_mode & 0o777
        if mode & 0o077:
            raise SecretsFermesError(
                f"Fichier secrets lisible au-delà du propriétaire "
                f"({oct(mode)}) : {os.path.basename(chemin)} — "
                f"corrigez avec : chmod 600"
            )
    except OSError:
        pass
    return chemin


def lire_credential_fichier(chemin: str, cle: str, url_page: str | None = None) -> str:
    """Lit un credential depuis un fichier désigné explicitement (--secrets).

    T1 (montage strict) : voir _verifier_montage_fichier_secrets.

    url_page (audit 05/08/2026, C-03) : URL de la page courante (page.url).
    Vérifie que son domaine figure dans 'origines_autorisees' du fichier ;
    la clé elle-même est obligatoire, url_page ou non.
    """
    chemin = _verifier_montage_fichier_secrets(chemin)
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    _verifier_checksum(data, chemin)
    _verifier_origines_autorisees(data, chemin, url_page)
    if cle not in data:
        raise KeyError(
            f"Clé '{cle}' absente du fichier secrets ({os.path.basename(chemin)})\n"
            f"Clés disponibles : {filtrer_noms_cles_sensibles(list(data.keys()))}"
        )
    return data[cle]


def verifier_cles_fichier(chemin: str, cles) -> None:
    """Pré-validation fail-fast sur un fichier de secrets explicite (--secrets).

    Même vérification de montage T1 que lire_credential_fichier (voir
    _verifier_montage_fichier_secrets). Vérifie répertoire chiffré + clés +
    présence de 'origines_autorisees' (audit 05/08/2026, C-03) SANS lire les
    valeurs. Le contrôle de correspondance domaine a lieu plus tard, dans
    lire_credential_fichier, seul moment où page.url (post-navigation,
    post-redirection éventuelle) est connu.
    """
    chemin = _verifier_montage_fichier_secrets(chemin)
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    _verifier_origines_autorisees(data, chemin)
    manquantes = [c for c in cles if c not in data]
    if manquantes:
        raise KeyError(
            f"Clé(s) {manquantes} absente(s) du fichier secrets ({os.path.basename(chemin)})\n"
            f"Clés disponibles : {filtrer_noms_cles_sensibles(list(data.keys()))}"
        )


def lire_totp_fichier(chemin: str, url_page: str | None = None) -> str:
    """Génère le code TOTP depuis la seed dans un fichier secrets explicite (--secrets).

    Délègue à lire_credential_fichier (vérification montage T1 + origines_autorisees incluse).
    """
    import pyotp
    seed = lire_credential_fichier(chemin, "totp_cle", url_page)
    return pyotp.TOTP(seed).now()
