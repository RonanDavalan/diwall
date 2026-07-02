#!/usr/bin/env python3
"""Verifier — v1.17.0 items 1-4 (replay-verifier, checkpoint, SoM stable,
iframes cross-frame).

Live tests target https://example.com and
https://the-internet.herokuapp.com/iframe (stable public QA fixture,
purpose-built for iframe testing).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.17.0_validation/verifier.py
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
RPA = os.path.join(RACINE, "rpa.py")
PYTHON = sys.executable


def _run_shot(*args, url="https://example.com"):
    result = subprocess.run(
        [PYTHON, SHOT, "--url", url, *args],
        capture_output=True, text=True, timeout=60,
    )
    try:
        data = json.loads(result.stdout.strip().split("\n")[-1])
    except (json.JSONDecodeError, IndexError):
        data = None
    return result.returncode, data


def _run_rpa(*args):
    result = subprocess.run(
        [PYTHON, RPA, *args], capture_output=True, text=True, timeout=60,
    )
    lignes = result.stdout.strip().split("\n") if result.stdout.strip() else []
    try:
        data = json.loads(lignes[-1])
    except (json.JSONDecodeError, IndexError):
        data = None
    return result.returncode, data, result.stderr


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_1_replay_verifier():
    scenario = os.path.join(ICI, "..", "exemples", "sondage_fast.json")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        ref = f.name
    code_save, _, _ = _run_rpa("--scenario", scenario, "--no-capture",
                                "--sauver-verifier-reference", ref)
    code_stable, _, err_stable = _run_rpa("--scenario", scenario, "--no-capture",
                                           "--replay-verifier", ref)
    verdict_stable = json.loads(err_stable.strip().split("\n")[-1]) if err_stable else {}
    os.unlink(ref)
    return _verdict("T-1) --replay-verifier : sauvegarde puis comparaison stable", [
        ("sauvegarde exit 0", code_save == 0),
        ("comparaison exit 0", code_stable == 0),
        ("verdict == 'stable'", verdict_stable.get("verdict") == "stable"),
    ])


def test_2_checkpoint_cycle():
    with tempfile.TemporaryDirectory() as tmp:
        cp = os.path.join(tmp, "cp.json")
        scenario_echec = os.path.join(tmp, "s1.json")
        with open(scenario_echec, "w") as f:
            json.dump({
                "nom": "cp", "url": "https://example.com",
                "actions": [
                    {"type": "evaluer", "script": "1+1"},
                    {"type": "cliquer", "selecteur": ".nexiste-pas"},
                ],
            }, f)
        code1, _, _ = _run_rpa("--scenario", scenario_echec, "--no-capture",
                                "--checkpoint", cp, "--timeout", "1500")
        cp_existe_apres_echec = os.path.isfile(cp)
        n_apres_echec = json.load(open(cp)).get("actions_completees") if cp_existe_apres_echec else None

        scenario_ok = os.path.join(tmp, "s2.json")
        with open(scenario_ok, "w") as f:
            json.dump({
                "nom": "cp", "url": "https://example.com",
                "actions": [
                    {"type": "evaluer", "script": "1+1"},
                    {"type": "evaluer", "script": "2+2"},
                ],
            }, f)
        code2, data2, _ = _run_rpa("--scenario", scenario_ok, "--no-capture",
                                    "--checkpoint", cp, "--timeout", "5000")
        cp_supprime_apres_succes = not os.path.isfile(cp)

    return _verdict("T-2) checkpoint — échec partiel, reprise, résolution", [
        ("run 1 échoue (exit != 0)", code1 != 0),
        ("checkpoint créé après échec", cp_existe_apres_echec),
        ("actions_completees == 1", n_apres_echec == 1),
        ("run 2 (reprise) réussit", code2 == 0),
        ("une seule évaluation dans le run 2 (reprise effective)",
         data2 is not None and len(data2.get("evaluations", [])) == 1),
        ("checkpoint supprimé après succès complet", cp_supprime_apres_succes),
    ])


def test_3_som_stable():
    from shot import _SOM_INJECTER_JS, _SOM_TROUVER_JS, _SOM_TROUVER_STABLE_JS
    from playwright.sync_api import sync_playwright

    _VERITE_TERRAIN = (
        "() => { const el = document.querySelector("
        "'a[href=\"https://iana.org/domains/example\"]');"
        " if (!el) return null; const r = el.getBoundingClientRect();"
        " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; }"
    )

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        page = b.new_context().new_page()
        page.goto("https://example.com")
        page.evaluate(_SOM_INJECTER_JS)  # id=1 == le seul lien ("Learn more")
        page.evaluate(
            "() => { var a=document.createElement('a'); a.href='#fake'; "
            "a.textContent='FAKE'; document.body.prepend(a); }"
        )
        # Vérité terrain indépendante : où est RÉELLEMENT le lien original
        # après l'injection (le reflow déplace légitimement ses coordonnées —
        # ce qui compte est l'IDENTITÉ de l'élément retourné, pas des
        # coordonnées figées).
        verite = page.evaluate(_VERITE_TERRAIN)
        ancien = page.evaluate(_SOM_TROUVER_JS, 1)
        stable = page.evaluate(_SOM_TROUVER_STABLE_JS, 1)
        # Retire précisément l'élément marqué id=1 (pas le lien parasite non marqué).
        page.evaluate(
            "() => document.querySelector('[data-dw-som-id=\"1\"]')?.remove()"
        )
        apres_suppression = page.evaluate(_SOM_TROUVER_STABLE_JS, 1)
        b.close()

    return _verdict("T-3) --som-rafraichir — résolution stable par identité, pas par index", [
        ("ancien mécanisme dérive vers le mauvais élément (≠ vérité terrain)",
         (ancien or {}).get("x") != verite["x"] or (ancien or {}).get("y") != verite["y"]),
        ("mécanisme stable pointe le vrai élément (== vérité terrain)",
         (stable or {}).get("x") == verite["x"] and (stable or {}).get("y") == verite["y"]),
        ("élément retiré du DOM -> échec honnête (null), jamais une mauvaise cible",
         apres_suppression is None),
    ])


def test_4_iframe():
    code, data = _run_shot(
        "--no-capture",
        "--actions", json.dumps([
            {"type": "attendre_selecteur_present", "selecteur": "#mce_0_ifr"},
            {"type": "cliquer_iframe", "iframe_selecteur": "#mce_0_ifr",
             "selecteur": "#tinymce", "force": True},
        ]),
        "--timeout", "10000",
        url="https://the-internet.herokuapp.com/iframe",
    )
    return _verdict("T-4) cliquer_iframe résout et clique dans un iframe", [
        ("exit code == 0", code == 0),
        ("succes == True", data is not None and data.get("succes") is True),
        ("indice_agressivite == 0.5 (1 écriture / 2 actions)",
         data is not None
         and data.get("citoyennete", {}).get("indice_agressivite") == 0.5),
    ])


def main():
    tests = (
        test_1_replay_verifier,
        test_2_checkpoint_cycle,
        test_3_som_stable,
        test_4_iframe,
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
