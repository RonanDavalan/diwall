#!/usr/bin/env python3
"""Verifier — v1.19.0 (mode_conseille filtered to successful diagnostics,
chainage traceability for declencher_scenario).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.19.0_validation/verifier.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
RPA = os.path.join(RACINE, "rpa.py")
JOURNAL_CLI = os.path.join(RACINE, "journal.py")
PYTHON = sys.executable
GUIDE_VERSION = "3.7"


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_1_mode_conseille_filtre_succes():
    from lib.journal import dernier_diagnostic_host, enregistrer_operation
    from shot import _traduire_diagnostic_en_conseil

    def evals(framework, shadow_roots):
        return [
            {"script": "s0", "valeur": "[]"}, {"script": "s1", "valeur": "[]"},
            {"script": "s2", "valeur": "[]"},
            {"script": "s3", "valeur": json.dumps({
                "React": framework == "React", "Vue": framework == "Vue", "Angular": False,
            })},
            {"script": "s4", "valeur": str(shadow_roots)},
            {"script": "s5", "valeur": "{}"},
        ]

    with tempfile.TemporaryDirectory() as tmp:
        journal_path = os.path.join(tmp, "operations.jsonl")
        env_sauve = os.environ.get("DIWALL_JOURNAL")
        os.environ["DIWALL_JOURNAL"] = journal_path
        try:
            # Diagnostic reussi, plus ancien : React + 2 shadow roots.
            enregistrer_operation(
                outil="rpa.py", version="1.19.0", cible_url="https://host-mixte.example/",
                resultat="succes", actions=[], source_scenario="diagnostic_dom.json",
                evaluations=evals("React", 2),
            )
            # Diagnostic en ECHEC, plus recent, MEME host, evaluations presentes
            # (partielles avant l'echec) : Vue + 0 shadow roots. Sans le filtre
            # v1.19.0, c'est cette entree (la plus recente avec evaluations)
            # qui serait retenue par erreur.
            enregistrer_operation(
                outil="rpa.py", version="1.19.0", cible_url="https://host-mixte.example/",
                resultat="echec", actions=[], source_scenario="diagnostic_dom.json",
                erreur="timeout", evaluations=evals("Vue", 0),
            )
            retenu = dernier_diagnostic_host("host-mixte.example")
            conseil = _traduire_diagnostic_en_conseil(retenu) if retenu else None

            # Host dont l'UNIQUE diagnostic est en echec -> aucune donnee reelle -> None.
            enregistrer_operation(
                outil="rpa.py", version="1.19.0", cible_url="https://host-echec-seul.example/",
                resultat="echec", actions=[], source_scenario="diagnostic_dom.json",
                erreur="timeout", evaluations=evals("React", 3),
            )
            retenu_echec_seul = dernier_diagnostic_host("host-echec-seul.example")
        finally:
            if env_sauve is None:
                os.environ.pop("DIWALL_JOURNAL", None)
            else:
                os.environ["DIWALL_JOURNAL"] = env_sauve

    return _verdict("T-1) mode_conseille filtre resultat==succes (v1.19.0)", [
        ("entree en echec (plus recente) ignoree malgre des evaluations presentes",
         retenu is not None and conseil is not None
         and "react" in conseil["raisons"][0].lower()),
        ("le conseil ne cite jamais Vue (entree echec correctement ecartee)",
         conseil is not None and "vue" not in json.dumps(conseil).lower()),
        ("host dont l'unique diagnostic est en echec -> None (jamais de speculation)",
         retenu_echec_seul is None),
    ])


def test_2_chainage_unitaire():
    import rpa

    with tempfile.TemporaryDirectory() as tmp:
        sous_sous = os.path.join(tmp, "profondeur2.json")
        sous = os.path.join(tmp, "profondeur1.json")
        json.dump({"actions": [{"type": "evaluer", "script": "1"}]}, open(sous_sous, "w"))
        json.dump({"actions": [
            {"type": "evaluer", "script": "2"},
            {"type": "declencher_scenario", "scenario": sous_sous},
        ]}, open(sous, "w"))

        actions_racine = [
            {"type": "evaluer", "script": "0"},
            {"type": "declencher_scenario", "scenario": sous},
            {"type": "evaluer", "script": "3"},
        ]
        aplaties, chainage = rpa._aplatir_actions(actions_racine)

        sans_chainage, chainage_vide = rpa._aplatir_actions(
            [{"type": "evaluer", "script": "0"}]
        )

    entree_p1 = next((c for c in chainage if c["profondeur"] == 1), None)
    entree_p2 = next((c for c in chainage if c["profondeur"] == 2), None)

    return _verdict("T-2) _aplatir_actions — arbre de chainage (v1.19.0)", [
        ("4 actions aplaties (0, 2, 1, 3 — le sous-sous-scenario est inline)",
         len(aplaties) == 4),
        ("2 entrees de chainage (profondeur 1 et 2)", len(chainage) == 2),
        ("profondeur 1 couvre les actions 1-2 (script '2' + sous-sous inline)",
         entree_p1 is not None and entree_p1["action_debut"] == 1
         and entree_p1["action_fin"] == 2),
        ("profondeur 2 couvre l'action 2 seule (offset du parent applique)",
         entree_p2 is not None and entree_p2["action_debut"] == 2
         and entree_p2["action_fin"] == 2),
        ("scenario sans declencher_scenario -> chainage vide", chainage_vide == []),
    ])


def test_3_chainage_journal_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        sous = os.path.join(tmp, "sous.json")
        parent = os.path.join(tmp, "parent.json")
        journal_path = os.path.join(tmp, "operations.jsonl")
        json.dump({"actions": [
            {"type": "evaluer", "script": "document.title"},
        ]}, open(sous, "w"))
        json.dump({
            "url": "https://example.com",
            "actions": [
                {"type": "declencher_scenario", "scenario": sous},
            ],
        }, open(parent, "w"))

        env = os.environ.copy()
        env["DIWALL_JOURNAL"] = journal_path

        r = subprocess.run(
            [PYTHON, RPA, "--scenario", parent, "--no-capture",
             "--guide-version", GUIDE_VERSION],
            capture_output=True, text=True, timeout=30, env=env,
        )
        run_ok = r.returncode == 0

        entrees = []
        if os.path.isfile(journal_path):
            with open(journal_path, encoding="utf-8") as f:
                entrees = [json.loads(l) for l in f if l.strip()]
        chainage_journal = entrees[-1].get("chainage") if entrees else None

        # journal.py (lecteur racine) doit rendre l'arbre indente.
        r_lecture = subprocess.run(
            [PYTHON, JOURNAL_CLI, "--limite", "1"],
            capture_output=True, text=True, timeout=10, env=env,
        )

    return _verdict("T-3) chainage bout-en-bout — rpa.py -> journal -> journal.py", [
        ("run reussi (sous-scenario inline sur example.com)", run_ok),
        ("chainage present dans l'entree du journal", chainage_journal is not None),
        ("chainage racine (profondeur 0) present",
         chainage_journal is not None
         and any(c["profondeur"] == 0 for c in chainage_journal)),
        ("chainage sous-scenario (profondeur 1) present",
         chainage_journal is not None
         and any(c["profondeur"] == 1 and c["scenario"] == sous for c in chainage_journal)),
        ("journal.py --limite 1 affiche l'arbre de chainage", "chainage" in r_lecture.stdout),
    ])


def main():
    tests = (
        test_1_mode_conseille_filtre_succes,
        test_2_chainage_unitaire,
        test_3_chainage_journal_end_to_end,
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
