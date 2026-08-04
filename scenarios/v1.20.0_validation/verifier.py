#!/usr/bin/env python3
"""Verifier — v1.20.0 (journal.py --erreurs, latences_actions).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.20.0_validation/verifier.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
SHOT = os.path.join(RACINE, "shot.py")
JOURNAL_CLI = os.path.join(RACINE, "journal.py")
PYTHON = sys.executable
GUIDE_VERSION = "1.0"  # compteur propre au guide — voir docs/GUIDE_LLM.md notice-version


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_1_journal_erreurs_filtre():
    from lib.journal import enregistrer_operation

    with tempfile.TemporaryDirectory() as tmp:
        journal_path = os.path.join(tmp, "operations.jsonl")
        env = os.environ.copy()
        env["DIWALL_JOURNAL"] = journal_path

        env_sauve = os.environ.get("DIWALL_JOURNAL")
        os.environ["DIWALL_JOURNAL"] = journal_path
        try:
            enregistrer_operation(
                outil="shot.py", version="1.20.0", cible_url="https://host-succes.example/",
                resultat="succes", actions=[],
            )
            enregistrer_operation(
                outil="shot.py", version="1.20.0", cible_url="https://host-echec.example/",
                resultat="echec", actions=[], erreur="timeout",
            )
        finally:
            if env_sauve is None:
                os.environ.pop("DIWALL_JOURNAL", None)
            else:
                os.environ["DIWALL_JOURNAL"] = env_sauve

        r_erreurs = subprocess.run(
            [PYTHON, JOURNAL_CLI, "--erreurs", "--format", "json"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        entrees_erreurs = json.loads(r_erreurs.stdout) if r_erreurs.returncode == 0 else []

        r_tout = subprocess.run(
            [PYTHON, JOURNAL_CLI, "--format", "json"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        entrees_tout = json.loads(r_tout.stdout) if r_tout.returncode == 0 else []

    return _verdict("T-1) journal.py --erreurs filtre resultat != succes (v1.20.0)", [
        ("--format json exit 0", r_erreurs.returncode == 0),
        ("sans --erreurs : les deux entrees sont presentes", len(entrees_tout) == 2),
        ("avec --erreurs : une seule entree retenue", len(entrees_erreurs) == 1),
        ("l'entree retenue est bien celle en echec",
         len(entrees_erreurs) == 1
         and entrees_erreurs[0]["cible_url"] == "https://host-echec.example/"),
        ("l'entree en succes n'apparait jamais avec --erreurs",
         all(e["resultat"] != "succes" for e in entrees_erreurs)),
    ])


def test_2_latences_actions_toujours_presente_vide():
    r = subprocess.run(
        [PYTHON, SHOT, "--url", "https://example.com", "--no-capture",
         "--guide-version", GUIDE_VERSION],
        capture_output=True, text=True, timeout=30,
    )
    sortie = json.loads(r.stdout) if r.returncode == 0 else {}

    return _verdict("T-2) latences_actions toujours presente, vide sans actions (v1.20.0)", [
        ("run reussi (example.com, aucune action)", r.returncode == 0),
        ("cle latences_actions presente", "latences_actions" in sortie),
        ("liste vide en l'absence d'actions", sortie.get("latences_actions") == []),
    ])


def test_3_latences_actions_structure():
    with tempfile.TemporaryDirectory() as tmp:
        actions_path = os.path.join(tmp, "actions.json")
        actions = [
            {"type": "evaluer", "script": "document.title"},
            {"type": "evaluer", "script": "1+1"},
        ]
        json.dump(actions, open(actions_path, "w"))

        r = subprocess.run(
            [PYTHON, SHOT, "--url", "https://example.com", "--no-capture",
             "--actions", actions_path, "--guide-version", GUIDE_VERSION],
            capture_output=True, text=True, timeout=30,
        )
        sortie = json.loads(r.stdout) if r.returncode == 0 else {}
        latences = sortie.get("latences_actions", [])

    indices_ok = [e.get("index") for e in latences] == list(range(len(actions)))
    types_ok = [e.get("type") for e in latences] == [a["type"] for a in actions]
    valeurs_ok = all(
        isinstance(e.get("latence_ms"), int) and e["latence_ms"] >= 0
        for e in latences
    )

    return _verdict("T-3) latences_actions structure — deux actions evaluer (v1.20.0)", [
        ("run reussi", r.returncode == 0),
        ("une entree par action dispatchee", len(latences) == len(actions)),
        ("index sequentiel 0..N-1", indices_ok),
        ("type reflete l'action d'origine", types_ok),
        ("latence_ms entier positif ou nul pour chaque entree", valeurs_ok),
    ])


def main():
    tests = (
        test_1_journal_erreurs_filtre,
        test_2_latences_actions_toujours_presente_vide,
        test_3_latences_actions_structure,
    )
    n_ok = 0
    for fn in tests:
        ok, lignes = fn()
        print("\n".join(lignes))
        if ok:
            n_ok += 1
    print()
    print(f"=== {n_ok}/{len(tests)} tests OK ===")
    sys.exit(0 if n_ok == len(tests) else 1)


if __name__ == "__main__":
    main()
