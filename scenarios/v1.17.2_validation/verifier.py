#!/usr/bin/env python3
"""Verifier — v1.17.2 items 1-4 (garde-fou de montage, nettoyage SoM, WAF affiné +
overrule, correctif checkpoint FR-80).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.17.2_validation/verifier.py
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
from unittest import mock

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
SHOT = os.path.join(RACINE, "shot.py")
PYTHON = sys.executable


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_1_garde_fou_secrets():
    with tempfile.TemporaryDirectory() as tmp:
        faux_secrets = os.path.join(tmp, "faux_secrets")
        os.makedirs(faux_secrets)
        journal_path = os.path.join(faux_secrets, "operations.jsonl")
        fallback_path = os.path.join(tmp, "fallback.jsonl")
        env = os.environ.copy()
        env["DIWALL_SECRETS_DIR"] = faux_secrets
        env["DIWALL_JOURNAL"] = journal_path
        env["DIWALL_JOURNAL_FALLBACK"] = fallback_path
        result = subprocess.run(
            [PYTHON, SHOT, "--url", "https://example.com", "--no-capture"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        journal_ecrit_en_clair = os.path.isfile(journal_path)
        fallback_ecrit = os.path.isfile(fallback_path)

    return _verdict("T-1) garde-fou de montage — répertoire chiffré fermé redirige vers le fallback", [
        ("run réussit malgré le répertoire chiffré fermé (best-effort)", result.returncode == 0),
        ("aucune écriture en clair dans le faux répertoire", not journal_ecrit_en_clair),
        ("entrée présente dans le fallback local", fallback_ecrit),
    ])


def test_2_som_nettoyage():
    from shot import _SOM_INJECTER_JS, _SOM_RETIRER_JS
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        page = b.new_context().new_page()
        page.goto("https://example.com")
        page.evaluate(_SOM_INJECTER_JS)  # 1re capture : id=1 sur le seul lien visible
        page.evaluate(_SOM_RETIRER_JS)
        # Le lien original devient invisible (filtré par l'injecteur) ; un
        # nouveau lien visible apparaît et doit hériter du numéro 1.
        page.evaluate(
            "() => { "
            "document.querySelector('a[href]').style.display = 'none'; "
            "var a=document.createElement('a'); a.href='#nouveau'; "
            "a.textContent='NOUVEAU'; document.body.appendChild(a); }"
        )
        page.evaluate(_SOM_INJECTER_JS)  # 2e capture
        page.evaluate(_SOM_RETIRER_JS)
        elements_id_1 = page.evaluate(
            "() => Array.from(document.querySelectorAll('[data-dw-som-id=\"1\"]'))"
            ".map(el => el.textContent)"
        )
        b.close()

    return _verdict("T-2) nettoyage SoM — pas de collision après 2 captures", [
        ("un seul élément porte data-dw-som-id=\"1\" après la 2e capture",
         len(elements_id_1) == 1),
        ("c'est le nouvel élément, pas le fantôme de la 1re capture",
         elements_id_1 == ["NOUVEAU"]),
    ])


def test_3_waf():
    from shot import _detecter_waf, _construire_etat

    faux_positif_evite = _detecter_waf(
        200, "Ma Boutique — Accueil",
        '<html><head><script src="https://cdnjs.cloudflare.com/ajax/libs/'
        'jquery/3.6.0/jquery.min.js"></script></head><body>Bienvenue</body></html>',
    ) is False
    vrai_positif_detecte = _detecter_waf(
        200, "Just a moment...",
        '<html><body>Checking your browser before accessing the site. '
        'cf-error-details</body></html>',
    ) is True
    http_403_detecte = _detecter_waf(403, "Erreur", "") is True

    etat_bloque = _construire_etat("active", {}, None, [], waf_bloquants=1, ignorer_waf=False)
    etat_ignore = _construire_etat("active", {}, None, [], waf_bloquants=1, ignorer_waf=True)

    return _verdict("T-3) heuristique WAF affinée + overrule --ignorer-waf", [
        ("ressource CDN cloudflare ordinaire -> plus de faux-positif", faux_positif_evite),
        ("vraie page de challenge -> détection préservée", vrai_positif_detecte),
        ("HTTP 403 -> détection préservée", http_403_detecte),
        ("sans --ignorer-waf : pret_a_agir == False", etat_bloque["pret_a_agir"] is False),
        ("avec --ignorer-waf : pret_a_agir == True", etat_ignore["pret_a_agir"] is True),
        ("avec --ignorer-waf : niveau_confiance quand même dégradé",
         etat_ignore["niveau_confiance"] != "eleve"),
    ])


def test_4_checkpoint_plafond():
    if "rpa" in sys.modules:
        importlib.reload(sys.modules["rpa"])
    import rpa

    with tempfile.TemporaryDirectory() as tmp:
        cp = os.path.join(tmp, "cp.json")
        scenario = os.path.join(tmp, "s.json")
        with open(scenario, "w") as f:
            json.dump({
                "nom": "t", "url": "https://example.com",
                "actions": [{"type": "evaluer", "script": "1+1"}],
            }, f)

        sortie_plafond = {
            "succes": True,
            "respect": {"actions_executees": 8, "plafond_atteint": "max_actions_par_run"},
        }
        fake_result = mock.Mock(
            returncode=0, stdout=json.dumps(sortie_plafond) + "\n", stderr="",
        )
        argv_sauve = sys.argv
        sys.argv = ["rpa.py", "--scenario", scenario, "--checkpoint", cp]
        try:
            with mock.patch.object(rpa.subprocess, "run", return_value=fake_result):
                try:
                    rpa.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = argv_sauve

        checkpoint_survit = os.path.isfile(cp)
        n = json.load(open(cp)).get("actions_completees") if checkpoint_survit else None

    return _verdict(
        "T-4) checkpoint — plafond atteint ne supprime plus la progression (FR-80)", [
            ("checkpoint survit malgré succes:true + plafond_atteint", checkpoint_survit),
            ("actions_completees reflète la progression du run (8)", n == 8),
        ])


def main():
    tests = (
        test_1_garde_fou_secrets,
        test_2_som_nettoyage,
        test_3_waf,
        test_4_checkpoint_plafond,
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
