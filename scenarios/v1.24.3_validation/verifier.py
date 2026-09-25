#!/usr/bin/env python3
"""Vérificateur — v1.24.3 (type des résultats scalaires d'`evaluer`, garde entre
les deux canaux d'installation étendue à uninstall.sh).

Usage :
    /opt/diwall/venv/bin/python3 scenarios/v1.24.3_validation/verifier.py

Hors ligne : un serveur HTTP local sert la page de test, aucun modèle ni réseau
extérieur. Le test bout en bout lance Chromium (comme v1.24.1_validation T-6).

Les contre-tests comptent autant que le cas nominal : T-1 prouve que le
maintien du type des scalaires ne relâche pas le filtre sur les chaînes, T-3
que la garde laisse passer une machine sans paquet.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
SHOT = os.path.join(RACINE, "shot.py")
PYTHON = sys.executable
PORT = 18243

from lib.sanitisation import _neutraliser_valeur_evaluer as neutraliser  # noqa: E402


def _jeton_guide():
    with open(os.path.join(RACINE, "docs", "GUIDE_LLM.md"), encoding="utf-8") as f:
        return re.search(r"<!-- notice-version: ([0-9]+\.[0-9]+) -->", f.read()).group(1)


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def test_1_scalaires_gardent_leur_type():
    jwt = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
           "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
    aleatoire = "aB3xK9mQ2vL7nR5tY8wZ1cD4fG6hJ0pS"
    return _verdict("T-1 — un scalaire garde son type, une chaîne reste filtrée", [
        ("False reste False", neutraliser(False) is False),
        ("True reste True", neutraliser(True) is True),
        ("0 reste l'entier 0", neutraliser(0) == 0 and type(neutraliser(0)) is int),
        ("42 reste l'entier 42", neutraliser(42) == 42 and type(neutraliser(42)) is int),
        ("1.5 reste le flottant 1.5", neutraliser(1.5) == 1.5 and type(neutraliser(1.5)) is float),
        ("None reste None", neutraliser(None) is None),
        ("une chaîne ordinaire reste une chaîne", neutraliser("bonjour") == "bonjour"),
        ("un JWT est toujours filtré", neutraliser(jwt) == "<valeur_filtree>"),
        ("un jeton à haute entropie est toujours filtré", neutraliser(aleatoire) == "<valeur_filtree>"),
        ("une structure garde ses scalaires",
         neutraliser({"a": False, "b": 3, "c": jwt}) == {"a": False, "b": 3, "c": "<valeur_filtree>"}),
    ])


class _Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corps = b"<!doctype html><html><head><title>v1.24.3</title></head><body>ok</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


def test_2_bout_en_bout_stealth():
    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), _Page)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        actions = [
            {"type": "evaluer", "script": "navigator.webdriver"},
            {"type": "evaluer", "script": "1 + 1"},
            {"type": "evaluer", "script": "typeof navigator"},
        ]
        cmd = [PYTHON, SHOT, "--url", f"http://127.0.0.1:{PORT}/", "--no-capture", "--stealth",
               "--guide-version", _jeton_guide(), "--actions", json.dumps(actions)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        try:
            sortie = json.loads(r.stdout)
        except json.JSONDecodeError:
            sortie = {}
    finally:
        serveur.shutdown()
        serveur.server_close()
    valeurs = [e.get("valeur") for e in sortie.get("evaluations") or []]
    return _verdict("T-2 — bout en bout : --stealth rend navigator.webdriver en booléen", [
        (f"shot.py a réussi (exit {r.returncode})", r.returncode == 0 and sortie.get("succes") is True),
        (f"navigator.webdriver : {valeurs[:1]!r}", valeurs[:1] == [False] and valeurs[0] is False),
        (f"1 + 1 : {valeurs[1:2]!r}", valeurs[1:2] == [2]),
        (f"typeof navigator : {valeurs[2:3]!r}", valeurs[2:3] == ["object"]),
        ("boussole.stealth_actif", (sortie.get("boussole") or {}).get("stealth_actif") is True),
    ])


def test_3_garde_uninstall():
    conditions = []
    script = os.path.join(RACINE, "scripts", "uninstall.sh")
    with tempfile.TemporaryDirectory() as d:
        faux = os.path.join(d, "dpkg-query")
        for etat, refus in (("installed", True), ("config-files", False), ("", False)):
            with open(faux, "w") as f:
                f.write(f"#!/bin/sh\nprintf '{etat}'\n")
            os.chmod(faux, 0o700)
            # --dry-run : toute écriture passe par cmd(), qui se contente d'afficher.
            r = subprocess.run(["bash", script, "--dry-run", "--confirme"],
                               capture_output=True, text=True,
                               env=dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"]))
            garde = "déjà installé par le paquet Debian" in r.stderr
            if refus:
                conditions.append((f"état « {etat} » → refus, exit 1 (reçu {r.returncode})",
                                   r.returncode == 1 and garde and "DRY-RUN" not in r.stdout))
                conditions.append(("le message propose apt purge, pas de réinstallation",
                                   "sudo apt purge diwall" in r.stderr and "relancer" not in r.stderr))
            else:
                conditions.append((f"état « {etat or 'absent'} » → la garde ne bloque pas", not garde))
    texte = open(script, encoding="utf-8").read()
    premiere_ecriture = re.search(r"(?m)^\s*(cmd\s+\S|sudo\s)", texte).start()
    conditions.append(("uninstall.sh appelle la garde avant toute écriture",
                       0 <= texte.find("\ngarde_canal_deb désinstaller\n") < premiere_ecriture))
    return _verdict("T-3 — uninstall.sh refuse de supprimer une installation par paquet, et seulement elle",
                    conditions)


def main():
    resultats = [
        test_1_scalaires_gardent_leur_type(),
        test_2_bout_en_bout_stealth(),
        test_3_garde_uninstall(),
    ]
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
