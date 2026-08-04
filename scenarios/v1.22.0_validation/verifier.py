#!/usr/bin/env python3
"""Verifier — v1.22.0 (repli_js, dernier_code_http, VaultNonConfigureError, --wait-until).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.22.0_validation/verifier.py

Fixture repli_js : scenarios/interoperabilite/fixture/dialog_ferme.html —
un <dialog> jamais ouvert (ni "open" ni showModal()) est display:none par la
feuille de style utilisateur-agent, sans JS. Vérifié empiriquement (19/07/2026,
Playwright 1.61.0) : un clic natif, même force:true, lève "Element is not
visible" (playwright.sync_api.Error, PAS un TimeoutError — un except trop
étroit dans shot.py aurait laissé passer ce cas réel, corrigé avant ce test).
Un clic JS (element.click()) sur le même sélecteur réussit sans réserve.
Reproduit fidèlement FN14 (docs/GUIDE_LLM_INTERACTIONS.md) de façon
déterministe, sans dépendre de la cause exacte (root cause non tranchée).

Fixture --wait-until : scenarios/interoperabilite/fixture/polling_continu.html —
une page qui interroge le serveur toutes les 200 ms, donc sous le seuil de
500 ms de silence réseau qu'exige `networkidle`. T-4a prouve que le défaut
échoue réellement sur cette page, T-4b que `--wait-until load` aboutit par le
chemin normal, T-4c que le comportement d'une cible saine est inchangé.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
SHOT = os.path.join(RACINE, "shot.py")
RPA = os.path.join(RACINE, "rpa.py")
FIXTURE_DIR = os.path.join(RACINE, "scenarios", "interoperabilite", "fixture")
PYTHON = sys.executable
GUIDE_VERSION = "4.1"
PORT = 8645
URL_DIALOG_FERME = f"http://127.0.0.1:{PORT}/dialog_ferme.html"
URL_INDEX = f"http://127.0.0.1:{PORT}/index.html"
URL_INEXISTANTE = f"http://127.0.0.1:{PORT}/chemin_absent_v1220.html"
URL_POLLING = f"http://127.0.0.1:{PORT}/polling_continu.html"


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def _demarrer_serveur_fixture():
    proc = subprocess.Popen(
        [PYTHON, "-m", "http.server", str(PORT), "--directory", FIXTURE_DIR],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            urllib.request.urlopen(URL_INDEX, timeout=0.5)
            return proc
        except Exception:
            pass
        time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("serveur de fixture n'a pas démarré à temps")


def _lancer_shot(url, actions=None, no_evaluer=False, wait_until=None, timeout_ms=None):
    cmd = [PYTHON, SHOT, "--url", url, "--no-capture", "--guide-version", GUIDE_VERSION]
    if actions is not None:
        cmd += ["--actions", json.dumps(actions)]
    if no_evaluer:
        cmd.append("--no-evaluer")
    if wait_until is not None:
        cmd += ["--wait-until", wait_until]
    if timeout_ms is not None:
        cmd += ["--timeout", str(timeout_ms)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        sortie = json.loads(r.stdout)
    except json.JSONDecodeError:
        sortie = {}
    return r, sortie


def test_1_repli_js_recupere():
    """repli_js: true récupère un clic natif échoué (force compris) via JS."""
    r, sortie = _lancer_shot(URL_DIALOG_FERME, actions=[
        {"type": "cliquer", "selecteur": "#btn-dans-dialog-ferme", "repli_js": True},
    ])
    boussole = sortie.get("boussole", {})
    return _verdict("T-1) repli_js récupère un clic natif échoué (v1.22.0)", [
        ("run réussi", sortie.get("succes") is True),
        ("boussole.repli_js_utilise == True", boussole.get("repli_js_utilise") is True),
    ])


def test_1b_sans_repli_js_echoue():
    """Contre-épreuve : sans repli_js, le même clic échoue réellement — prouve
    que le fixture teste un vrai échec natif, pas un placebo."""
    r, sortie = _lancer_shot(URL_DIALOG_FERME, actions=[
        {"type": "cliquer", "selecteur": "#btn-dans-dialog-ferme"},
    ])
    boussole = sortie.get("boussole", {})
    return _verdict("T-1b) sans repli_js, le clic natif échoue vraiment (contre-épreuve)", [
        ("run en échec (succes: false)", sortie.get("succes") is False),
        ("boussole.repli_js_utilise absent", "repli_js_utilise" not in boussole),
    ])


def test_2_rejet_no_evaluer():
    """repli_js: true + --no-evaluer : rejet précoce, exit 2, jamais un
    abandon silencieux (repli_js exécute du JS, --no-evaluer l'interdit)."""
    r, sortie = _lancer_shot(URL_DIALOG_FERME, actions=[
        {"type": "cliquer", "selecteur": "#btn-dans-dialog-ferme", "repli_js": True},
    ], no_evaluer=True)
    return _verdict("T-2) rejet repli_js + --no-evaluer (v1.22.0)", [
        ("exit 2", r.returncode == 2),
        ("erreur == arguments_incompatibles", sortie.get("erreur") == "arguments_incompatibles"),
    ])


def test_3a_dernier_code_http_sans_naviguer():
    """dernier_code_http toujours présent — sans action naviguer, reflète la
    navigation initiale."""
    r, sortie = _lancer_shot(URL_INDEX)
    boussole = sortie.get("boussole", {})
    return _verdict("T-3a) dernier_code_http == navigation initiale (v1.22.0)", [
        ("run réussi", sortie.get("succes") is True),
        ("boussole.dernier_code_http == 200", boussole.get("dernier_code_http") == 200),
    ])


def test_3b_dernier_code_http_avec_naviguer():
    """Une action naviguer vers une page 404 doit mettre à jour
    dernier_code_http — preuve qu'il reflète la DERNIÈRE navigation, pas
    seulement la navigation initiale (nuance documentée dans
    GUIDE_LLM_SESSIONS.md)."""
    r, sortie = _lancer_shot(URL_INDEX, actions=[
        {"type": "naviguer", "url": URL_INEXISTANTE},
    ])
    boussole = sortie.get("boussole", {})
    return _verdict("T-3b) dernier_code_http reflète la dernière navigation (v1.22.0)", [
        ("run réussi (404 n'est pas un échec Diwall)", sortie.get("succes") is True),
        ("boussole.dernier_code_http == 404", boussole.get("dernier_code_http") == 404),
    ])


def test_4a_networkidle_echoue_sur_polling():
    """Contre-épreuve de l'Axe D : sur une page à polling continu, le défaut
    networkidle ne peut pas aboutir — la fenêtre de silence réseau n'existe
    jamais. Prouve que la fixture teste un vrai blocage, pas un placebo, et
    que --timeout n'est pas le levier (5 s ici, le résultat serait identique
    à 45 s : c'est ce qui a été constaté en conditions réelles)."""
    r, sortie = _lancer_shot(URL_POLLING, timeout_ms=5000)
    return _verdict("T-4a) networkidle échoue sur page à polling continu (contre-épreuve)", [
        ("run en échec (succes: false)", sortie.get("succes") is False),
        ("boussole.wait_until absent (défaut employé)",
         "wait_until" not in sortie.get("boussole", {})),
    ])


def test_4b_wait_until_load_reussit():
    """--wait-until load aboutit sur la même page, par le chemin normal — pas
    par le fallback capture_echec, qui ne produit ni SoM ni a11y exploitables.
    L'a11y_tree présent est la preuve que la reconnaissance a bien eu lieu."""
    r, sortie = _lancer_shot(URL_POLLING, wait_until="load", timeout_ms=5000)
    boussole = sortie.get("boussole", {})
    return _verdict("T-4b) --wait-until load aboutit sur la même page (v1.22.0)", [
        ("run réussi", sortie.get("succes") is True),
        ("boussole.wait_until == 'load'", boussole.get("wait_until") == "load"),
        ("boussole.dernier_code_http == 200", boussole.get("dernier_code_http") == 200),
    ])


def test_4c_defaut_inchange():
    """Non-régression : sans le flag, une cible saine se comporte exactement
    comme avant l'Axe D — navigation en networkidle, aucune clé ajoutée."""
    r, sortie = _lancer_shot(URL_INDEX)
    return _verdict("T-4c) défaut networkidle inchangé sur cible saine (non-régression)", [
        ("run réussi", sortie.get("succes") is True),
        ("boussole.wait_until absent", "wait_until" not in sortie.get("boussole", {})),
    ])


def _lancer_rpa(scenario_dict, wait_until=None, timeout_ms=None):
    """rpa.py sur un scénario temporaire — le chemin réel d'automatisation,
    distinct de l'appel shot.py direct."""
    chemin = os.path.join(ICI, "_tmp_scenario_wait_until.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(scenario_dict, f)
    cmd = [PYTHON, RPA, "--scenario", chemin, "--guide-version", GUIDE_VERSION]
    if wait_until is not None:
        cmd += ["--wait-until", wait_until]
    if timeout_ms is not None:
        cmd += ["--timeout", str(timeout_ms)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        try:
            sortie = json.loads(r.stdout.strip().split("\n")[-1])
        except (json.JSONDecodeError, IndexError):
            sortie = {}
        return r, sortie
    finally:
        if os.path.isfile(chemin):
            os.remove(chemin)


def test_5a_rpa_propage_le_flag():
    """rpa.py propage --wait-until au subprocess shot.py. Sans cette
    propagation, le flag ne servirait qu'en reconnaissance directe : la cible
    qui a motivé l'Axe D s'administre par scénario, pas en shot.py direct."""
    scenario = {"url": URL_POLLING, "actions": [
        {"type": "evaluer", "script": "document.getElementById('titre').textContent"},
    ]}
    r, sortie = _lancer_rpa(scenario, wait_until="load", timeout_ms=5000)
    return _verdict("T-5a) rpa.py propage --wait-until à shot.py (v1.22.0)", [
        ("run réussi", sortie.get("succes") is True),
        ("boussole.wait_until == 'load'", sortie.get("boussole", {}).get("wait_until") == "load"),
    ])


def test_5b_rpa_propriete_scenario():
    """La propriété racine `wait_until` du scénario a le même effet que le
    flag — un scénario reste autoportant, sans dépendre d'une invocation
    correcte en ligne de commande."""
    scenario = {"url": URL_POLLING, "wait_until": "load", "actions": [
        {"type": "evaluer", "script": "document.getElementById('titre').textContent"},
    ]}
    r, sortie = _lancer_rpa(scenario, timeout_ms=5000)
    return _verdict("T-5b) propriété racine wait_until du scénario (v1.22.0)", [
        ("run réussi", sortie.get("succes") is True),
        ("boussole.wait_until == 'load'", sortie.get("boussole", {}).get("wait_until") == "load"),
    ])


def test_5c_rpa_sans_flag_echoue():
    """Contre-épreuve : sans flag ni propriété, rpa.py garde le défaut et
    échoue sur la même cible — le défaut n'a pas bougé côté scénarios."""
    scenario = {"url": URL_POLLING, "actions": [
        {"type": "evaluer", "script": "document.getElementById('titre').textContent"},
    ]}
    r, sortie = _lancer_rpa(scenario, timeout_ms=5000)
    return _verdict("T-5c) rpa.py sans flag garde le défaut networkidle (contre-épreuve)", [
        ("run en échec (succes: false)", sortie.get("succes") is False),
        ("boussole.wait_until absent", "wait_until" not in sortie.get("boussole", {})),
    ])


def main():
    proc = _demarrer_serveur_fixture()
    try:
        resultats = [
            test_1_repli_js_recupere(),
            test_1b_sans_repli_js_echoue(),
            test_2_rejet_no_evaluer(),
            test_3a_dernier_code_http_sans_naviguer(),
            test_3b_dernier_code_http_avec_naviguer(),
            test_4a_networkidle_echoue_sur_polling(),
            test_4b_wait_until_load_reussit(),
            test_4c_defaut_inchange(),
            test_5a_rpa_propage_le_flag(),
            test_5b_rpa_propriete_scenario(),
            test_5c_rpa_sans_flag_echoue(),
        ]
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    n_ok = 0
    for ok, lignes in resultats:
        print("\n".join(lignes))
        if ok:
            n_ok += 1
    print()
    print(f"=== {n_ok}/{len(resultats)} tests OK ===")
    sys.exit(0 if n_ok == len(resultats) else 1)


if __name__ == "__main__":
    main()
