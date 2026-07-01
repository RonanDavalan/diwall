#!/usr/bin/env python3
"""Vérificateur des scénarios de test v1.3 et v1.3.2.

Exécution :
    PYTHONPATH=~/git/Diwall/Diwall python3 verifier.py

Ou depuis le répertoire de scénarios :
    ./verifier.py

Sortie :
- ligne par scénario : OK / KO + détail.
- exit 0 si tous OK, 1 sinon.

Reproduction de §8 de _CADRE/SPECIFICATIONS/33_CONFIG_OPERATEUR.md (a–e)
et §7 de _CADRE/SPECIFICATIONS/34_CONSCIENCE_ENVIRONNEMENTALE.md (f–h).
"""
from __future__ import annotations

import getpass
import io
import os
import socket
import sys
from contextlib import redirect_stderr
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent  # .../Diwall/Diwall/
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from lib.profil_operateur import (  # noqa: E402
    charger_profil,
    LISTE_BLANCHE_AUTO_CONFIRMER,
    LISTE_ROUGE_INVIOLABLE,
)
from shot import _construire_diwall_meta  # noqa: E402
from watch import _construire_diwall_meta_watch  # noqa: E402


def _charger_capturant_stderr(chemin):
    """Charge un profil en capturant les warnings stderr."""
    buf = io.StringIO()
    with redirect_stderr(buf):
        profil = charger_profil(chemin)
    return profil, buf.getvalue()


def _verdict(nom, conditions):
    """Évalue une liste de (libelle, bool) et retourne (ok, lignes)."""
    lignes = []
    ok = True
    for libelle, condition in conditions:
        marqueur = "✓" if condition else "✗"
        lignes.append(f"    {marqueur} {libelle}")
        if not condition:
            ok = False
    statut = "OK" if ok else "KO"
    return ok, [f"[{statut}] {nom}", *lignes]


def test_a_profil_absent():
    # Forcer absence : retirer DIWALL_PROFIL, et pointer charger_profil
    # vers une résolution qui échouera (chemin=None et pas de fichier
    # operateur.$(whoami).yaml présent dans le contexte de test).
    env_sauvegarde = os.environ.pop("DIWALL_PROFIL", None)
    try:
        # On simule l'absence en passant un chemin explicite vers un
        # fichier inexistant — _chemin_profil_actif() n'est pas appelé
        # quand chemin est fourni, donc on doit utiliser un chemin
        # bidon vers /tmp pour déclencher la branche "absent + strict".
        chemin_absent = Path("/tmp/diwall_test_profil_inexistant.yaml")
        if chemin_absent.exists():
            chemin_absent.unlink()
        profil, _ = _charger_capturant_stderr(chemin_absent)
    finally:
        if env_sauvegarde is not None:
            os.environ["DIWALL_PROFIL"] = env_sauvegarde

    return _verdict("a) profil absent → comportement strict", [
        ("profil.actif == False", profil.actif is False),
        ("profil.descripteur() == '(aucun — comportement strict)'",
         profil.descripteur() == "(aucun — comportement strict)"),
        ("auto_confirmer vide", len(profil.auto_confirmer) == 0),
        ("tracabilite_modeles_active == True",
         profil.tracabilite_modeles_active is True),
        ("est_auto_confirme('ecriture_capture_tmp') == False",
         profil.est_auto_confirme("ecriture_capture_tmp") is False),
        ("est_auto_confirme('git_push') == False",
         profil.est_auto_confirme("git_push") is False),
    ])


def test_b_profil_minimal():
    profil, stderr = _charger_capturant_stderr(ICI / "test_v1_3_b_profil_minimal.yaml")
    return _verdict("b) profil minimal — un seul auto_confirmer", [
        ("profil.actif == True", profil.actif is True),
        ("auto_confirmer == {'ecriture_capture_tmp'}",
         profil.auto_confirmer == frozenset({"ecriture_capture_tmp"})),
        ("est_auto_confirme('ecriture_capture_tmp') == True",
         profil.est_auto_confirme("ecriture_capture_tmp") is True),
        ("est_auto_confirme('invocation_ollama_locale') == False",
         profil.est_auto_confirme("invocation_ollama_locale") is False),
        ("tracabilite_modeles_active == True (défaut hérité)",
         profil.tracabilite_modeles_active is True),
        ("aucun warning sur stderr", stderr == ""),
    ])


def test_c_nom_inconnu():
    profil, stderr = _charger_capturant_stderr(ICI / "test_v1_3_c_nom_inconnu.yaml")
    return _verdict("c) nom inconnu dans auto_confirmer", [
        ("profil.actif == True", profil.actif is True),
        ("warning stderr mentionne 'foo_bar_inexistant'",
         "foo_bar_inexistant" in stderr),
        ("auto_confirmer == {'ecriture_capture_tmp', 'invocation_ollama_locale'}",
         profil.auto_confirmer == frozenset({
             "ecriture_capture_tmp", "invocation_ollama_locale",
         })),
        ("'foo_bar_inexistant' absent de auto_confirmer",
         "foo_bar_inexistant" not in profil.auto_confirmer),
    ])


def test_d_tentative_liste_rouge():
    profil, stderr = _charger_capturant_stderr(
        ICI / "test_v1_3_d_tentative_liste_rouge.yaml"
    )
    return _verdict("d) tentative d'ajout d'un nom de liste rouge", [
        ("profil.actif == True", profil.actif is True),
        ("warning stderr mentionne 'git_push'", "git_push" in stderr),
        ("auto_confirmer == {'ecriture_capture_tmp'}",
         profil.auto_confirmer == frozenset({"ecriture_capture_tmp"})),
        ("'git_push' absent de auto_confirmer",
         "git_push" not in profil.auto_confirmer),
        ("est_auto_confirme('git_push') == False",
         profil.est_auto_confirme("git_push") is False),
        ("'git_push' reste dans LISTE_ROUGE_INVIOLABLE",
         "git_push" in LISTE_ROUGE_INVIOLABLE),
        ("LISTE_BLANCHE et LISTE_ROUGE disjointes",
         LISTE_BLANCHE_AUTO_CONFIRMER.isdisjoint(LISTE_ROUGE_INVIOLABLE)),
    ])


def test_e_tracabilite_desactivee():
    profil, _ = _charger_capturant_stderr(
        ICI / "test_v1_3_e_tracabilite_desactivee.yaml"
    )
    # Simuler une trace de modèle pour vérifier qu'elle est bien omise.
    modeles_appeles_simules = [{
        "_tag": "qwen3-vl:4b",
        "mode_llm": "local",
        "role": "localisation_clic",
    }]
    meta = _construire_diwall_meta(
        profil, "2026-06-02T12:00:00+02:00",
        modeles_appeles_simules, "https://example.com",
    )
    return _verdict("e) traçabilité désactivée → modeles_utilises omis", [
        ("profil.actif == True", profil.actif is True),
        ("tracabilite_modeles_active == False",
         profil.tracabilite_modeles_active is False),
        ("'modeles_utilises' absent du diwall_meta",
         "modeles_utilises" not in meta),
        ("'version_shot' présent", "version_shot" in meta),
        ("'profil_actif' présent", "profil_actif" in meta),
        ("'horodatage_iso' présent", "horodatage_iso" in meta),
        ("'url_au_moment_capture' présent",
         "url_au_moment_capture" in meta),
    ])


def _profil_strict():
    """Profil absent → comportement strict, sans toucher durablement à l'env."""
    chemin_absent = Path("/tmp/diwall_test_profil_inexistant.yaml")
    if chemin_absent.exists():
        chemin_absent.unlink()
    env_sauvegarde = os.environ.pop("DIWALL_PROFIL", None)
    try:
        profil, _ = _charger_capturant_stderr(chemin_absent)
    finally:
        if env_sauvegarde is not None:
            os.environ["DIWALL_PROFIL"] = env_sauvegarde
    return profil


def test_f_meta_env_shot():
    profil = _profil_strict()
    meta = _construire_diwall_meta(
        profil, "2026-06-01T22:00:00+02:00", [], "https://example.com",
    )
    return _verdict("f) shot.py — champs d'environnement dans diwall_meta", [
        ("'hostname_executant' présent", "hostname_executant" in meta),
        ("'utilisateur_executant' présent", "utilisateur_executant" in meta),
        ("hostname_executant == socket.gethostname()",
         meta.get("hostname_executant") == socket.gethostname()),
        ("utilisateur_executant == getpass.getuser()",
         meta.get("utilisateur_executant") == getpass.getuser()),
        ("hostname_executant non vide", bool(meta.get("hostname_executant"))),
        ("utilisateur_executant non vide",
         bool(meta.get("utilisateur_executant"))),
    ])


def test_g_meta_env_watch():
    profil = _profil_strict()
    meta = _construire_diwall_meta_watch(
        profil, "2026-06-01T22:00:00+02:00", [], "https://example.com",
    )
    return _verdict("g) watch.py — champs d'environnement dans diwall_meta", [
        ("'hostname_executant' présent", "hostname_executant" in meta),
        ("'utilisateur_executant' présent", "utilisateur_executant" in meta),
        ("hostname_executant == socket.gethostname()",
         meta.get("hostname_executant") == socket.gethostname()),
        ("utilisateur_executant == getpass.getuser()",
         meta.get("utilisateur_executant") == getpass.getuser()),
    ])


def test_h_env_independant_tracabilite():
    # Profil tracabilite_modeles.active: false (réutilise le yaml e) :
    # les champs d'environnement doivent rester présents malgré l'omission
    # de modeles_utilises.
    profil, _ = _charger_capturant_stderr(
        ICI / "test_v1_3_e_tracabilite_desactivee.yaml"
    )
    modeles_simules = [{
        "_tag": "qwen3-vl:2b", "mode_llm": "local", "role": "localisation_clic",
    }]
    meta = _construire_diwall_meta(
        profil, "2026-06-01T22:00:00+02:00", modeles_simules,
        "https://example.com",
    )
    return _verdict(
        "h) champs d'environnement indépendants de la traçabilité modèles", [
            ("tracabilite_modeles_active == False",
             profil.tracabilite_modeles_active is False),
            ("'modeles_utilises' absent (traçabilité off)",
             "modeles_utilises" not in meta),
            ("'hostname_executant' présent malgré traçabilité off",
             "hostname_executant" in meta),
            ("'utilisateur_executant' présent malgré traçabilité off",
             "utilisateur_executant" in meta),
        ])


def main():
    tests = (
        test_a_profil_absent,
        test_b_profil_minimal,
        test_c_nom_inconnu,
        test_d_tentative_liste_rouge,
        test_e_tracabilite_desactivee,
        test_f_meta_env_shot,
        test_g_meta_env_watch,
        test_h_env_independant_tracabilite,
    )
    n_ok = 0
    for fn in tests:
        ok, lignes = fn()
        print("\n".join(lignes))
        if ok:
            n_ok += 1

    print()
    if n_ok == len(tests):
        print(f"=== {n_ok}/{len(tests)} scénarios OK ===")
        sys.exit(0)
    print(f"=== {n_ok}/{len(tests)} OK — au moins un scénario KO ===")
    sys.exit(1)


if __name__ == "__main__":
    main()
