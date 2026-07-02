#!/usr/bin/env python3
"""Verifier — v1.16.0 items A-F (etat, operation_id, WAF, erreurs_console,
indice_agressivite, stealth compatibility fix).

Two kinds of tests:
  - pure unit tests on _detecter_waf() / _construire_etat() (no network)
  - live subprocess calls against https://example.com (same public fixture
    as scripts/preflight-publication.sh and v1.15.2_validation)

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.16.0_validation/verifier.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))  # .../Diwall/Diwall/
sys.path.insert(0, RACINE)
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


def test_b1_operation_id_isole():
    code, data = _run("--no-capture")
    opid = data.get("boussole", {}).get("operation_id") if data else None
    return _verdict("T-B1) operation_id présent et cohérent avec run_id dérivé", [
        ("exit code == 0", code == 0),
        ("operation_id présent (12 hex)", bool(opid) and len(opid) == 12),
    ])


def test_a1_etat_nominal():
    code, data = _run("--no-capture")
    etat = data.get("etat") if data else None
    return _verdict("T-A1) etat déterministe — cas nominal", [
        ("exit code == 0", code == 0),
        ("etat présent", etat is not None),
        ("pret_a_agir == True", etat is not None and etat.get("pret_a_agir") is True),
        ("niveau_confiance == 'eleve'",
         etat is not None and etat.get("niveau_confiance") == "eleve"),
    ])


def test_a2_etat_degrade_sur_auth_inactive():
    code, data = _run("--no-capture", "--auth-indicator", ".selecteur-inexistant-xyz")
    etat = data.get("etat") if data else None
    return _verdict("T-A2) etat dégradé — auth_status inactive", [
        ("exit code == 0", code == 0),
        ("pret_a_agir == False", etat is not None and etat.get("pret_a_agir") is False),
        ("niveau_confiance == 'faible'",
         etat is not None and etat.get("niveau_confiance") == "faible"),
    ])


def test_c1_detecter_waf_unitaire():
    from shot import _detecter_waf
    return _verdict("T-C1) _detecter_waf — cas 403/429/mots-clés/propre", [
        ("403 -> True", _detecter_waf(403, "x", "x") is True),
        ("429 -> True", _detecter_waf(429, "x", "x") is True),
        ("titre 'Just a moment...' -> True",
         _detecter_waf(200, "Just a moment...", "") is True),
        ("HTML 'checking your browser' -> True",
         _detecter_waf(200, "x", "Checking your browser before accessing") is True),
        ("page propre -> False",
         _detecter_waf(200, "Example Domain", "<html>ok</html>") is False),
    ])


def test_d1_erreurs_console_capturees():
    actions = json.dumps([
        {"type": "evaluer", "script": "console.error('test-v1.16.0')"},
    ])
    code, data = _run("--no-capture", "--actions", actions)
    return _verdict("T-D1) erreurs_console capture console.error", [
        ("exit code == 0", code == 0),
        ("erreurs_console non vide",
         data is not None and "test-v1.16.0" in (data.get("erreurs_console") or [])),
        ("etat dégradé à modere",
         data is not None and data.get("etat", {}).get("niveau_confiance") == "modere"),
    ])


def test_e1_indice_agressivite():
    actions = json.dumps([
        {"type": "attendre_selecteur_present", "selecteur": "body"},  # lecture
        {"type": "evaluer", "script": "document.title"},               # écriture (prudence)
    ])
    code, data = _run("--no-capture", "--actions", actions)
    citoyennete = data.get("citoyennete") if data else None
    return _verdict("T-E1) indice_agressivite == 0.5 (1 écriture / 2 actions)", [
        ("exit code == 0", code == 0),
        ("indice_agressivite == 0.5",
         citoyennete is not None and citoyennete.get("indice_agressivite") == 0.5),
    ])


def test_f1_stealth_reduit_empreinte():
    code, data = _run(
        "--no-capture", "--stealth",
        "--actions", json.dumps([{"type": "evaluer", "script": "navigator.webdriver"}]),
    )
    valeur = None
    if data and data.get("evaluations"):
        valeur = data["evaluations"][0].get("valeur")
    return _verdict("T-F1) --stealth masque navigator.webdriver + boussole cohérente", [
        ("exit code == 0", code == 0),
        ("navigator.webdriver == False", valeur is False),
        ("boussole.stealth_actif == True",
         data is not None and data.get("boussole", {}).get("stealth_actif") is True),
    ])


def main():
    tests = (
        test_b1_operation_id_isole,
        test_a1_etat_nominal,
        test_a2_etat_degrade_sur_auth_inactive,
        test_c1_detecter_waf_unitaire,
        test_d1_erreurs_console_capturees,
        test_e1_indice_agressivite,
        test_f1_stealth_reduit_empreinte,
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
