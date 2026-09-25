#!/usr/bin/env python3
"""Vérificateur — v1.24.1 (langue déclarée par le navigateur, forme JWT du filtre evaluer).

Usage :
    /opt/diwall/venv/bin/python3 scenarios/v1.24.1_validation/verifier.py

Hors ligne : aucun modèle, aucun réseau extérieur. T-1 à T-5 n'ouvrent aucun
navigateur ; T-6 lance shot.py contre un serveur HTTP local qui enregistre
l'en-tête Accept-Language qu'il reçoit.

Les contre-tests comptent autant que le cas nominal : T-3 prouve que le filet
base64 existe réellement (un filet qui ne se déclenche jamais ne se distingue
pas d'un filet absent), T-4 que le resserrement du motif JWT n'a pas ouvert la
porte à un vrai jeton dans un script evaluer.
"""
from __future__ import annotations

import base64
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
SHOT = os.path.join(RACINE, "shot.py")
PYTHON = sys.executable
PORT = 8651

import lib.sanitisation as sanitisation  # noqa: E402
from lib.langue_navigateur import locale_navigateur  # noqa: E402


def _jeton_guide():
    """Jeton du verrou, lu dans le guide lui-même : écrit en dur ici, il serait
    faux au prochain changement de version du guide, sans que rien le signale."""
    with open(os.path.join(RACINE, "docs", "GUIDE_LLM.md"), encoding="utf-8") as f:
        m = re.search(r"<!-- notice-version: ([0-9]+\.[0-9]+) -->", f.read())
    return m.group(1)


def _b64(obj):
    brut = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(brut).rstrip(b"=").decode()


# Trois jetons de forme réelle : en-tête et charge JSON encodés, signature de
# 43 caractères (longueur d'une signature HS256 en base64url).
_SIGNATURE = "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
JWT_COURANT = f"{_b64({'alg': 'HS256', 'typ': 'JWT'})}.{_b64({'sub': '1234567890', 'name': 'John Doe', 'iat': 1516239022})}.{_SIGNATURE}"
JWT_MINIMAL = f"{_b64({'alg': 'HS256'})}.{_b64({'a': 1})}.{_SIGNATURE}"
JWT_DANS_SCRIPT = f"fetch('/api', {{headers: {{Authorization: 'Bearer {JWT_COURANT}'}}}})"
JETONS = {"JWT HS256 courant": JWT_COURANT, "JWT à charge minimale": JWT_MINIMAL, "JWT dans un script": JWT_DANS_SCRIPT}

LEGITIMES = {
    "chaînage navigator.languages.join": "navigator.language + ' | ' + navigator.languages.join(',')",
    "chaînage document.documentElement.lang": "document.documentElement.lang",
    "nom d'hôte à deux libellés longs": "https://accounts.example-company.com/login",
    "chaînage window.performance.timing": "window.performance.timing.navigationStart",
}


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


# ---------------------------------------------------------------------------


def test_1_jwt_detectes():
    return _verdict("T-1 — les trois JWT restent détectés", [
        (f"{nom} détecté", sanitisation._forme_secrete(v)) for nom, v in JETONS.items()
    ])


def test_2_legitimes_non_detectes():
    return _verdict("T-2 — les chaînes légitimes ne sont plus prises pour un secret", [
        (f"{nom} non détecté", not sanitisation._forme_secrete(v)) for nom, v in LEGITIMES.items()
    ])


def test_3_filet_base64():
    original = sanitisation._MOTIF_JWT
    sanitisation._MOTIF_JWT = re.compile(r"(?!x)x")  # ne correspond à rien
    try:
        conditions = [
            (f"{nom} détecté sans le motif JWT", sanitisation._forme_secrete(v)) for nom, v in JETONS.items()
        ]
    finally:
        sanitisation._MOTIF_JWT = original
    return _verdict("T-3 — contre-test : le filet base64 prend les JWT seul", conditions)


def test_4_validation_des_actions():
    accepte = True
    try:
        sanitisation.valider_actions_secrets([{"type": "evaluer", "script": LEGITIMES["chaînage navigator.languages.join"]}])
    except ValueError:
        accepte = False
    refuse = False
    try:
        sanitisation.valider_actions_secrets([{"type": "evaluer", "script": JWT_DANS_SCRIPT}])
    except ValueError:
        refuse = True
    return _verdict("T-4 — valider_actions_secrets", [
        ("un evaluer de navigator.languages.join(',') est accepté", accepte),
        ("un evaluer portant un JWT est toujours refusé", refuse),
    ])


def test_5_locale_navigateur():
    cas = [
        ({"LANGUAGE": "fr", "LANG": "fr_FR.UTF-8"}, "fr"),
        ({"LANG": "C"}, "en-US"),
        ({"LANG": "POSIX", "LANGUAGE": "fr"}, "fr"),
        ({"LANG": "de_DE.UTF-8"}, "de-DE"),
        ({"LANGUAGE": "es:en", "LANG": "C"}, "es"),
        ({"LANG": "fr_FR.UTF-8@euro"}, "fr-FR"),
        ({"LANG": ""}, "en-US"),
        ({}, "en-US"),
        ({"LANGUAGE": ":", "LC_ALL": "it_IT.UTF-8", "LANG": "fr_FR.UTF-8"}, "it-IT"),
        ({"LC_MESSAGES": "pt_BR.UTF-8", "LANG": "fr_FR.UTF-8"}, "pt-BR"),
        ({"LANG": "C.UTF-8"}, "en-US"),
        ({"LANG": "n'importe quoi"}, "en-US"),
    ]
    return _verdict("T-5 — locale_navigateur", [
        (f"{env} → {attendu} (obtenu : {locale_navigateur(env)})", locale_navigateur(env) == attendu)
        for env, attendu in cas
    ])


class _Enregistreur(http.server.BaseHTTPRequestHandler):
    recus: list = []

    def do_GET(self):
        _Enregistreur.recus.append(self.headers.get("Accept-Language"))
        corps = b"<!doctype html><html><head><title>v1.24.1</title></head><body>ok</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


def test_6_bout_en_bout():
    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), _Enregistreur)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("LANGUAGE", "LC_ALL", "LC_MESSAGES")}
        env["LANG"] = "de_DE.UTF-8"
        actions = [{"type": "evaluer", "script": "navigator.language"}]
        cmd = [PYTHON, SHOT, "--url", f"http://127.0.0.1:{PORT}/", "--no-capture",
               "--guide-version", _jeton_guide(), "--actions", json.dumps(actions)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90, env=env)
        try:
            sortie = json.loads(r.stdout)
        except json.JSONDecodeError:
            sortie = {}
    finally:
        serveur.shutdown()
        serveur.server_close()
    valeurs = [e.get("valeur") for e in sortie.get("evaluations") or []]
    return _verdict("T-6 — bout en bout : LANG=de_DE.UTF-8, sans LANGUAGE", [
        (f"shot.py a réussi (exit {r.returncode})", r.returncode == 0 and sortie.get("succes") is True),
        (f"Accept-Language reçu : {_Enregistreur.recus}", bool(_Enregistreur.recus) and all(
            (h or "").split(",")[0] == "de-DE" for h in _Enregistreur.recus)),
        (f"navigator.language : {valeurs}", valeurs[:1] == ["de-DE"]),
    ])


def main():
    resultats = [
        test_1_jwt_detectes(),
        test_2_legitimes_non_detectes(),
        test_3_filet_base64(),
        test_4_validation_des_actions(),
        test_5_locale_navigateur(),
        test_6_bout_en_bout(),
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
