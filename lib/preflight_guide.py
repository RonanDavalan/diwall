"""
preflight_guide.py — verrou de lecture obligatoire de docs/GUIDE_LLM.md
(introduit v1.18.0, jeton resynchronisé v1.19.0).

Contexte : un LLM tiers appelant shot.py/rpa.py/watch.py sans avoir lu le
guide au préalable produit des erreurs évitables (venv, permissions). La
documentation seule ne suffit pas à se faire lire spontanément (retour
terrain répété, docs/RADAR_MODELES.md) — ce module implémente le garde-fou
technique correspondant.

Jeton : GUIDE_VERSION_ATTENDUE doit toujours être synchronisé avec le
commentaire <!-- notice-version: X.Y --> en tête de docs/GUIDE_LLM.md. Toute
modification substantielle du guide incrémente les deux ensemble.

Le compteur est propre au guide et n'est pas celui de Diwall : il atteste la
lecture du guide, pas l'état du logiciel. L'aligner sur la version du logiciel
invaliderait les jetons de tous les agents à chaque version sans changement de
guide, et laisserait passer inaperçue une correction du guide entre deux
versions. Il n'est pas calendaire non plus : une date se cite sans avoir rien
lu, un numéro de révision doit être allé chercher.

Marqueur : ~/.config/diwall/guide_state.json, scope utilisateur OS — jamais
sous le répertoire chiffré (dépendance absurde à un montage gocryptfs pour un accusé de
lecture) ni sous /opt/diwall/ (permissions restreintes, mauvais propriétaire
pour un appelant hors groupe diwall).

Exception consciente à la doctrine d'additivité de Diwall : ce module casse
délibérément tout appel sans jeton valide ni marqueur à jour — c'est l'objet
même de la fonctionnalité, pas un effet de bord à minimiser.
"""
import json
import os

GUIDE_VERSION_ATTENDUE = "1.1"

_MARQUEUR_PATH = os.path.join(os.path.expanduser("~"), ".config", "diwall", "guide_state.json")


def _ecrire_marqueur():
    """Best-effort — un échec d'écriture du marqueur ne doit jamais bloquer
    un appel dont le jeton vient d'être validé explicitement."""
    try:
        repertoire = os.path.dirname(_MARQUEUR_PATH)
        os.makedirs(repertoire, mode=0o700, exist_ok=True)
        os.chmod(repertoire, 0o700)
        # Audit 06/08/2026 (F-18) : O_NOFOLLOW ajouté — même motif que D-09
        # sur _sauver_session (shot.py), jamais appliqué ici. Un lien
        # symbolique pré-placé au chemin du marqueur ne sera pas suivi.
        fd = os.open(_MARQUEUR_PATH, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"version_validee": GUIDE_VERSION_ATTENDUE}, f)
    except OSError:
        pass


def _marqueur_valide():
    try:
        with open(_MARQUEUR_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version_validee") == GUIDE_VERSION_ATTENDUE
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False


def guide_valide(guide_version_fournie):
    """True si le jeton fourni correspond à la version attendue (auquel cas
    le marqueur local est (ré)écrit), ou si un marqueur valide existe déjà
    pour la version courante du guide."""
    if guide_version_fournie == GUIDE_VERSION_ATTENDUE:
        _ecrire_marqueur()
        return True
    return _marqueur_valide()


def erreur_guide_non_lu(version_installee):
    return {
        "succes": False,
        "erreur": "guide_non_lu",
        "version_installee": version_installee,
        "guide_version_attendue": GUIDE_VERSION_ATTENDUE,
        "message": (
            "Lire docs/GUIDE_LLM.md, relever <!-- notice-version: X.Y --> en "
            "tête de fichier, relancer avec --guide-version X.Y"
        ),
    }
