#!/usr/bin/env python3
"""Verifier — v1.15.2 item 6 (Q2, GL2).

Proves two behaviors already present in shot.py before v1.15.2 (audit-requested
evidence, not new code):

  T-Q2-A : --no-evaluer blocks a scenario 'evaluer' action (exit 1, succes:false)
  T-Q2-B : --no-evaluer does NOT block shot.py's internal page.evaluate() calls
           (SoM injection, secret masking) — --som still works normally
  T-GL2-A: auth_status is "inactive" when the positive selector is visible AND
           the negative selector is also visible (session considered untrusted)
  T-GL2-B: auth_status is "active" when the positive selector is visible AND
           the negative selector is absent

Runs live subprocess calls against https://example.com (stable public fixture,
same target already used by scripts/preflight-publication.sh smoke tests).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.15.2_validation/verifier.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))  # .../Diwall/Diwall/
SHOT = os.path.join(RACINE, "shot.py")
PYTHON = sys.executable
URL = "https://example.com"


def _run(*args):
    result = subprocess.run(
        [PYTHON, SHOT, "--url", URL, *args],
        capture_output=True, text=True, timeout=60,
    )
    try:
        data = json.loads(result.stdout.strip().split("\n")[-1])
    except (json.JSONDecodeError, IndexError):
        data = None
    return result.returncode, data


def _verdict(nom, conditions):
    lignes = []
    ok = True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_q2_a_no_evaluer_bloque_action():
    actions = json.dumps([{"type": "evaluer", "script": "document.title"}])
    code, data = _run("--no-evaluer", "--actions", actions)
    return _verdict("T-Q2-A) --no-evaluer bloque l'action evaluer du scénario", [
        ("exit code == 1", code == 1),
        ("data non None", data is not None),
        ("succes == False", data is not None and data.get("succes") is False),
        ("message mentionne no-evaluer",
         data is not None and "no-evaluer" in (data.get("message") or "")),
    ])


def test_q2_b_no_evaluer_nimpacte_pas_som():
    # Aucune action 'evaluer' dans le scénario — seul le SoM (qui utilise
    # page.evaluate() en interne) doit continuer de fonctionner.
    code, data = _run("--no-evaluer", "--som")
    return _verdict("T-Q2-B) --no-evaluer laisse intacts les evaluate() internes (SoM)", [
        ("exit code == 0", code == 0),
        ("succes == True", data is not None and data.get("succes") is True),
        ("capture_som présent", data is not None and bool(data.get("capture_som"))),
        ("elements_som non vide",
         data is not None and len(data.get("elements_som") or []) > 0),
    ])


def test_gl2_a_negatif_supprime_positif():
    # example.com : <div><h1>...</h1>...</div> — 'h1' et 'div' visibles tous deux.
    code, data = _run("--auth-indicator", "h1", "--auth-indicator-negative", "div")
    return _verdict(
        "T-GL2-A) positif visible + négatif visible → auth_status inactive", [
            ("exit code == 0", code == 0),
            ("auth_status == 'inactive'",
             data is not None and data.get("auth_status") == "inactive"),
        ])


def test_gl2_b_positif_seul_actif():
    code, data = _run(
        "--auth-indicator", "h1",
        "--auth-indicator-negative", ".selecteur-inexistant-xyz",
    )
    return _verdict(
        "T-GL2-B) positif visible + négatif absent → auth_status active", [
            ("exit code == 0", code == 0),
            ("auth_status == 'active'",
             data is not None and data.get("auth_status") == "active"),
        ])


def main():
    tests = (
        test_q2_a_no_evaluer_bloque_action,
        test_q2_b_no_evaluer_nimpacte_pas_som,
        test_gl2_a_negatif_supprime_positif,
        test_gl2_b_positif_seul_actif,
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
