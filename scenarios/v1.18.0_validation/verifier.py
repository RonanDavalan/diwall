#!/usr/bin/env python3
"""Verifier — v1.18.0 items 1-5 (verrou de lecture + --version, mode_conseille,
iframe_chemin, fixtures d'interoperabilite, monitor-verifier.sh).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.18.0_validation/verifier.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
SHOT = os.path.join(RACINE, "shot.py")
RPA = os.path.join(RACINE, "rpa.py")
WATCH = os.path.join(RACINE, "watch.py")
MONITOR = os.path.join(RACINE, "scripts", "monitor-verifier.sh")
FIXTURE_DIR = os.path.join(RACINE, "scenarios", "interoperabilite", "fixture")
PYTHON = sys.executable
GUIDE_LLM_MD = os.path.join(RACINE, "docs", "GUIDE_LLM.md")
with open(GUIDE_LLM_MD, encoding="utf-8") as _f:
    GUIDE_VERSION = re.search(r"<!-- notice-version: ([0-9]+\.[0-9]+) -->", _f.read()).group(1)


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_1_version():
    resultats = {}
    for outil, script in (("shot.py", SHOT), ("rpa.py", RPA), ("watch.py", WATCH)):
        t0 = time.time()
        r = subprocess.run([PYTHON, script, "--version"], capture_output=True, text=True, timeout=10)
        duree = time.time() - t0
        try:
            payload = json.loads(r.stdout.strip())
        except json.JSONDecodeError:
            payload = {}
        resultats[outil] = (r.returncode, payload, duree)

    return _verdict("T-1) --version — zéro Playwright, exit 0, quasi instantané", [
        (f"{o} : exit 0, JSON {{outil, version}}, < 3s",
         resultats[o][0] == 0 and resultats[o][1].get("outil") == o
         and "version" in resultats[o][1] and resultats[o][2] < 3.0)
        for o in ("shot.py", "rpa.py", "watch.py")
    ])


def test_2_guide_version_gate():
    with tempfile.TemporaryDirectory() as tmp_home:
        env = os.environ.copy()
        env["HOME"] = tmp_home
        # Isole ~/.config/diwall/ (marqueur) sans casser la résolution du
        # cache navigateur Playwright, qui vit sous ~/.cache/ms-playwright/
        # du VRAI HOME — sans ce override, Playwright cherche les binaires
        # sous le faux HOME et échoue avec "Executable doesn't exist".
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/.cache/ms-playwright")

        # Sans jeton, sans marqueur : refus.
        r1 = subprocess.run(
            [PYTHON, SHOT, "--url", "https://example.com", "--no-capture"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        try:
            payload1 = json.loads(r1.stderr.strip() or r1.stdout.strip())
        except json.JSONDecodeError:
            payload1 = {}

        # Jeton incorrect : refus.
        r2 = subprocess.run(
            [PYTHON, SHOT, "--url", "https://example.com", "--no-capture", "--guide-version", "0.0"],
            capture_output=True, text=True, timeout=10, env=env,
        )

        # Jeton correct : accepté, marqueur écrit.
        r3 = subprocess.run(
            [PYTHON, SHOT, "--url", "https://example.com", "--no-capture",
             "--guide-version", GUIDE_VERSION],
            capture_output=True, text=True, timeout=30, env=env,
        )
        marqueur = os.path.join(tmp_home, ".config", "diwall", "guide_state.json")
        marqueur_existe = os.path.isfile(marqueur)
        marqueur_perms_ok = (oct(os.stat(marqueur).st_mode)[-3:] == "600") if marqueur_existe else False

        # Appel suivant sans jeton : accepté grâce au marqueur.
        r4 = subprocess.run(
            [PYTHON, SHOT, "--url", "https://example.com", "--no-capture"],
            capture_output=True, text=True, timeout=30, env=env,
        )

    return _verdict("T-2) verrou --guide-version + marqueur ~/.config/diwall/", [
        ("sans jeton ni marqueur -> exit 1", r1.returncode == 1),
        ("erreur structurée guide_non_lu", payload1.get("erreur") == "guide_non_lu"),
        ("jeton incorrect -> exit 1", r2.returncode == 1),
        (f"jeton correct ({GUIDE_VERSION}) -> exit 0", r3.returncode == 0),
        ("marqueur créé après jeton correct", marqueur_existe),
        ("marqueur en permissions 600", marqueur_perms_ok),
        ("appel suivant sans jeton -> exit 0 (marqueur réutilisé)", r4.returncode == 0),
    ])


def test_3_iframe_chemin():
    import jsonschema
    schema = json.load(open(os.path.join(RACINE, "scenarios", "schema.json")))

    def valide(action):
        try:
            jsonschema.validate(
                {"url": "https://x", "actions": [action]}, schema,
            )
            return True
        except jsonschema.ValidationError:
            return False

    schema_chemin_seul = valide({
        "type": "cliquer_iframe", "iframe_chemin": ["iframe#a", "iframe#b"], "selecteur": "#btn",
    })
    schema_les_deux_rejete = not valide({
        "type": "cliquer_iframe", "iframe_selecteur": "iframe#a",
        "iframe_chemin": ["iframe#a", "iframe#b"], "selecteur": "#btn",
    })
    schema_aucun_rejete = not valide({"type": "cliquer_iframe", "selecteur": "#btn"})

    # Descente réelle à deux niveaux contre la fixture locale.
    serveur = subprocess.Popen(
        [PYTHON, "-m", "http.server", "18642", "--directory", FIXTURE_DIR],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.5)
        # Pas d'isolation HOME ici (déjà couverte par T-2) : --guide-version
        # explicite suffit à passer le verrou sans risquer de casser la
        # résolution du cache navigateur Playwright (~/.cache/ms-playwright/).
        actions = json.dumps([
            {"type": "cliquer_iframe",
             "iframe_chemin": ["iframe#wrapper", "iframe#paiement"],
             "selecteur": "#btn-confirm"},
        ])
        r = subprocess.run(
            [PYTHON, SHOT, "--url", "http://localhost:18642/index.html",
             "--actions", actions, "--no-capture", "--guide-version", GUIDE_VERSION],
            capture_output=True, text=True, timeout=30,
        )
        clic_reussi = r.returncode == 0
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)

    return _verdict("T-3) iframe_chemin — schéma + descente réelle à deux niveaux", [
        ("schéma : iframe_chemin seul valide", schema_chemin_seul),
        ("schéma : les deux clés ensemble rejetées", schema_les_deux_rejete),
        ("schéma : aucune des deux clés rejetée", schema_aucun_rejete),
        ("clic réel à travers 2 niveaux d'iframe réussit", clic_reussi),
    ])


def test_4_mode_conseille():
    from lib.journal import dernier_diagnostic_host, enregistrer_operation
    from shot import _traduire_diagnostic_en_conseil

    with tempfile.TemporaryDirectory() as tmp:
        journal_path = os.path.join(tmp, "operations.jsonl")
        env_sauve = os.environ.get("DIWALL_JOURNAL")
        os.environ["DIWALL_JOURNAL"] = journal_path
        try:
            # Aucune entrée pour cet host.
            absent = dernier_diagnostic_host("jamais-diagnostique.example") is None

            # Page "simple" : pas de framework, pas de shadow root -> pas de conseil.
            enregistrer_operation(
                outil="rpa.py", version="1.18.0", cible_url="https://simple.example/",
                resultat="succes", actions=[], source_scenario="diagnostic_dom.json",
                evaluations=[
                    {"script": "s0", "valeur": "[]"}, {"script": "s1", "valeur": "[]"},
                    {"script": "s2", "valeur": "[]"},
                    {"script": "s3", "valeur": json.dumps({"React": False, "Vue": False, "Angular": False})},
                    {"script": "s4", "valeur": "0"},
                    {"script": "s5", "valeur": "{}"},
                ],
            )
            evals_simple = dernier_diagnostic_host("simple.example")
            conseil_simple = _traduire_diagnostic_en_conseil(evals_simple) if evals_simple else "ERREUR_LECTURE"

            # Page riche : React détecté + 2 shadow roots -> conseil.
            enregistrer_operation(
                outil="rpa.py", version="1.18.0", cible_url="https://riche.example/",
                resultat="succes", actions=[], source_scenario="diagnostic_dom.json",
                evaluations=[
                    {"script": "s0", "valeur": "[]"}, {"script": "s1", "valeur": "[]"},
                    {"script": "s2", "valeur": "[]"},
                    {"script": "s3", "valeur": json.dumps({"React": True, "Vue": False, "Angular": False})},
                    {"script": "s4", "valeur": "2"},
                    {"script": "s5", "valeur": "{}"},
                ],
            )
            evals_riche = dernier_diagnostic_host("riche.example")
            conseil_riche = _traduire_diagnostic_en_conseil(evals_riche) if evals_riche else None
        finally:
            if env_sauve is None:
                os.environ.pop("DIWALL_JOURNAL", None)
            else:
                os.environ["DIWALL_JOURNAL"] = env_sauve

    return _verdict("T-4) mode_conseille — lecture journal + traduction", [
        ("host jamais diagnostiqué -> None (pas de spéculation)", absent),
        ("page simple diagnostiquée -> pas de conseil (None)", conseil_simple is None),
        ("page riche diagnostiquée -> conseil retourné", conseil_riche is not None),
        ("conseil riche : shadow_dom recommandé", conseil_riche and conseil_riche.get("shadow_dom") is True),
        ("conseil riche : som_rafraichir recommandé (framework)",
         conseil_riche and conseil_riche.get("som_rafraichir") is True),
        ("conseil riche : raisons cite react + shadow_roots",
         conseil_riche and "react" in conseil_riche["raisons"][0].lower()
         and any("shadow_roots:2" in r for r in conseil_riche["raisons"])),
    ])


def test_5_monitor_verifier():
    with tempfile.TemporaryDirectory() as tmp:
        ref_stable = os.path.join(tmp, "ref_stable.json")
        ref_regression = os.path.join(tmp, "ref_regression.json")
        env = os.environ.copy()
        env["DIWALL_RPA"] = RPA
        env["DIWALL_PYTHON"] = PYTHON

        r_ref = subprocess.run(
            [PYTHON, RPA, "--scenario", "diagnostic_dom.json", "--url", "https://example.com",
             "--sauver-verifier-reference", ref_stable],
            capture_output=True, text=True, timeout=30, cwd=RACINE, env=env,
        )
        ref_creee = r_ref.returncode == 0 and os.path.isfile(ref_stable)

        data = json.load(open(ref_stable))
        data["http_status"] = 999
        json.dump(data, open(ref_regression, "w"))

        r_stable = subprocess.run(
            ["bash", MONITOR, "--scenario", "diagnostic_dom.json", "--reference", ref_stable],
            capture_output=True, text=True, timeout=30, cwd=RACINE, env=env,
        )
        r_regression = subprocess.run(
            ["bash", MONITOR, "--scenario", "diagnostic_dom.json", "--reference", ref_regression],
            capture_output=True, text=True, timeout=30, cwd=RACINE, env=env,
        )

    return _verdict("T-5) monitor-verifier.sh — un passage, stable/régression", [
        ("référence structurelle créée", ref_creee),
        ("cas stable -> exit 0, silence stdout", r_stable.returncode == 0 and r_stable.stdout.strip() == ""),
        ("cas régression -> exit 1", r_regression.returncode == 1),
        ("cas régression -> verdict sur stderr", "regression" in r_regression.stderr),
    ])


def main():
    tests = (
        test_1_version,
        test_2_guide_version_gate,
        test_3_iframe_chemin,
        test_4_mode_conseille,
        test_5_monitor_verifier,
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
