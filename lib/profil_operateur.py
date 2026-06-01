"""Lecture du profil opérateur Diwall (v1.3).

Implémente la résolution et le chargement des profils YAML décrits
dans `_CADRE/SPECIFICATIONS/33_CONFIG_OPERATEUR.md`.

Aucun effet de bord. Lecture seule. Les listes rouges (verrous
inviolables §3.1) sont codées en dur et ne sont jamais lues depuis
un YAML : leur présence dans un profil serait une false affordance.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


LISTE_BLANCHE_AUTO_CONFIRMER = frozenset({
    "ecriture_capture_tmp",
    "montage_coffre_visuel",
    "lecture_reference_chiffree",
    "ecriture_journal_diwall",
    "invocation_ollama_locale",
})

LISTE_ROUGE_INVIOLABLE = frozenset({
    "git_push",
    "ecrasement_reference_pixel",
    "rotation_credential",
    "suppression_projet_coffre",
    "lecture_credential_en_clair_dans_journal",
})

_DIWALL_RACINE = Path(__file__).resolve().parent.parent
_CONF_D = _DIWALL_RACINE / "diwall.conf.d"
_CONF_SYSTEME = Path("/opt/diwall/diwall.conf")


@dataclass(frozen=True)
class ProfilOperateur:
    nom_profil: str
    auto_confirmer: frozenset[str]
    tracabilite_modeles_active: bool
    tracabilite_inclure_hash: bool
    chemin_charge: Optional[Path]

    @property
    def actif(self) -> bool:
        return self.chemin_charge is not None

    def est_auto_confirme(self, nom: str) -> bool:
        return nom in self.auto_confirmer

    def descripteur(self) -> str:
        if self.chemin_charge is None:
            return "(aucun — comportement strict)"
        return self.chemin_charge.name


_PROFIL_STRICT = ProfilOperateur(
    nom_profil="strict_defaut",
    auto_confirmer=frozenset(),
    tracabilite_modeles_active=True,
    tracabilite_inclure_hash=True,
    chemin_charge=None,
)


def _chemin_profil_actif() -> Optional[Path]:
    chemin_env = os.environ.get("DIWALL_PROFIL")
    if chemin_env:
        return Path(chemin_env).expanduser()

    candidat_user = _CONF_D / f"operateur.{_whoami()}.yaml"
    if candidat_user.is_file():
        return candidat_user

    if _CONF_SYSTEME.is_file():
        try:
            with _CONF_SYSTEME.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            chemin = data.get("profil_par_defaut")
            if chemin:
                return Path(chemin).expanduser()
        except (OSError, yaml.YAMLError) as exc:
            print(
                f"⚠ Diwall : lecture de {_CONF_SYSTEME} impossible ({exc}). "
                f"Fallback comportement strict.",
                file=sys.stderr,
            )

    return None


def _whoami() -> str:
    return os.environ.get("USER") or os.environ.get("LOGNAME") or "inconnu"


def _construire_depuis_yaml(chemin: Path, data: dict) -> ProfilOperateur:
    auto = data.get("auto_confirmer") or []
    if not isinstance(auto, list):
        raise ValueError(
            f"{chemin} : clé 'auto_confirmer' doit être une liste, "
            f"reçu {type(auto).__name__}."
        )

    noms_valides = set()
    noms_inconnus = []
    for nom in auto:
        if not isinstance(nom, str):
            noms_inconnus.append(repr(nom))
            continue
        if nom in LISTE_BLANCHE_AUTO_CONFIRMER:
            noms_valides.add(nom)
        else:
            noms_inconnus.append(nom)
    if noms_inconnus:
        print(
            f"⚠ Diwall : noms ignorés dans 'auto_confirmer' de "
            f"{chemin.name} : {', '.join(noms_inconnus)}. "
            f"Liste blanche reconnue : "
            f"{', '.join(sorted(LISTE_BLANCHE_AUTO_CONFIRMER))}.",
            file=sys.stderr,
        )

    trac = data.get("tracabilite_modeles") or {}
    if not isinstance(trac, dict):
        raise ValueError(
            f"{chemin} : clé 'tracabilite_modeles' doit être un dict, "
            f"reçu {type(trac).__name__}."
        )
    trac_active = bool(trac.get("active", True))
    trac_hash = bool(trac.get("inclure_hash_ollama", True))

    nom_profil = data.get("nom_profil")
    if not isinstance(nom_profil, str) or not nom_profil:
        nom_profil = chemin.stem

    return ProfilOperateur(
        nom_profil=nom_profil,
        auto_confirmer=frozenset(noms_valides),
        tracabilite_modeles_active=trac_active,
        tracabilite_inclure_hash=trac_hash,
        chemin_charge=chemin,
    )


def charger_profil(chemin: Optional[Path] = None) -> ProfilOperateur:
    """Retourne le profil opérateur résolu selon §4.3.

    - chemin explicite (test/superviseur), priorité absolue.
    - sinon résolution standard : DIWALL_PROFIL → operateur.$(whoami).yaml
      → /opt/diwall/diwall.conf → strict.
    - YAML invalide → exit 1 (§4.4).
    - fichier absent → warning + strict (§4.4).
    """
    cible = chemin if chemin is not None else _chemin_profil_actif()
    if cible is None:
        return _PROFIL_STRICT

    cible = cible.expanduser()
    if not cible.is_file():
        print(
            f"⚠ Diwall : profil référencé absent : {cible}. "
            f"Fallback comportement strict.",
            file=sys.stderr,
        )
        return _PROFIL_STRICT

    try:
        with cible.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        print(
            f"✖ Diwall : YAML invalide dans {cible} : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    except OSError as exc:
        print(
            f"⚠ Diwall : lecture de {cible} impossible ({exc}). "
            f"Fallback comportement strict.",
            file=sys.stderr,
        )
        return _PROFIL_STRICT

    if not isinstance(data, dict):
        print(
            f"✖ Diwall : {cible} ne contient pas un mapping YAML "
            f"(reçu {type(data).__name__}).",
            file=sys.stderr,
        )
        sys.exit(1)

    return _construire_depuis_yaml(cible, data)
