#!/usr/bin/env python3
"""Vérificateur — v1.24.2 (filtre de secrets sur les chaînes structurées,
diwall-watch --llm claude, garde entre les deux canaux d'installation).

Usage :
    /opt/diwall/venv/bin/python3 scenarios/v1.24.2_validation/verifier.py

Hors ligne : aucun modèle, aucun réseau, aucune clé d'API. Le mode claude de
watch.py est exercé contre un faux module `anthropic` placé en tête du
PYTHONPATH, qui enregistre la requête au lieu de l'envoyer. Le module réel
n'est pas nécessaire — et s'il est installé, le faux passe devant.

Les contre-tests comptent autant que le cas nominal : T-2 prouve que le
relâchement du filtre ne laisse pas passer les jetons (mesure sur 100 000
tirages), T-3 que les formes qu'on ne sait pas distinguer d'une clé restent
masquées, T-6 que la garde laisse passer une machine sans paquet.
"""
from __future__ import annotations

import base64
import json
import os
import random
import string
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)
WATCH = os.path.join(RACINE, "watch.py")
PYTHON = sys.executable

import lib.sanitisation as sanitisation  # noqa: E402
from lib.vision import CLAUDE_MODEL  # noqa: E402


def _jeton_guide():
    import re
    with open(os.path.join(RACINE, "docs", "GUIDE_LLM.md"), encoding="utf-8") as f:
        return re.search(r"<!-- notice-version: ([0-9]+\.[0-9]+) -->", f.read()).group(1)


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


# Relevées sur le site construit, docs/ et le code le 25/09/2026 : toutes
# masquées par la règle de v1.24.1.
STRUCTUREES = [
    "fr/guides/ecrire-un-scenario/",
    "href=/fr/architecture/confiance/",
    "_CADRE/SPECIFICATIONS/CHANTIER_SANITISATION",
    "id=session-10--03-juin-2026--v170",
    "/opt/diwall/scenarios/diagnostic_dom",
    "test_3b_dernier_code_http_avec_naviguer",
    "_SOM_COMPTER_HORS_VIEWPORT_JS_SHADOW",
    "com/RonanDavalan/diwall/releases",
    "scenarios/interoperabilite/fixture/polling_continu",
    "getElementsByClassName/querySelectorAll",
    # FR-88 : sélecteur d'attribut non quoté signalé par Sillage le 22/08/2026.
    "[data-sillage=btn-soumettre-sonde]",
]

_ALNUM = string.ascii_letters + string.digits
_B64URL = _ALNUM + "-_"
_B64 = _ALNUM + "+/"


def _tirage(rng, n, alphabet=_ALNUM):
    return "".join(rng.choice(alphabet) for _ in range(n))


FORMES_SECRETES = {
    "base64 64": lambda r: base64.b64encode(r.randbytes(48)).decode(),
    "base64url 43": lambda r: base64.urlsafe_b64encode(r.randbytes(32)).decode().rstrip("="),
    "préfixe ghp_": lambda r: "ghp_" + _tirage(r, 36),
    "préfixe sk_live_": lambda r: "sk_live_" + _tirage(r, 24),
    "préfixe sk-ant-api03-": lambda r: "sk-ant-api03-" + _tirage(r, 93, _B64URL),
    "clé AWS 40": lambda r: _tirage(r, 40, _B64),
    "préfixe xoxb-": lambda r: f"xoxb-{_tirage(r, 12, string.digits)}-{_tirage(r, 13, string.digits)}-{_tirage(r, 24)}",
    "alphanumérique 32": lambda r: _tirage(r, 32),
}


def test_1_structurees_liberees():
    return _verdict("T-1 — chemins, ancres et identifiants ne sont plus pris pour un secret", [
        (s, not sanitisation._forme_secrete(s)) for s in STRUCTUREES
    ])


def test_2_jetons_toujours_detectes():
    rng = random.Random(20260925)
    conditions = []
    for nom, gen in FORMES_SECRETES.items():
        echappes = sum(not sanitisation._forme_secrete(gen(rng)) for _ in range(12_500))
        # Seuil : 1 pour 5 000. Mesuré le 25/09/2026 : 0 à 2 pour 20 000,
        # uniquement sur des jetons sans aucun chiffre et d'allure camelCase.
        conditions.append((f"{nom} : {echappes} échappé(s) sur 12 500", echappes <= 2))
    return _verdict("T-2 — les jetons de formes réelles restent détectés", conditions)


def test_3_formes_indistinguables_masquees():
    cle_hex = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    return _verdict("T-3 — empreinte hexadécimale et JWT restent masqués (forme d'une clé)", [
        ("hexadécimal 64 (clé ou sha256, même forme)", sanitisation._forme_secrete(cle_hex)),
        ("JWT", sanitisation._forme_secrete(
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")),
        ("jeton collé dans un chemin", sanitisation._forme_secrete(
            "/api/v1/users/" + base64.urlsafe_b64encode(bytes(range(40, 72))).decode())),
    ])


_FAUX_ANTHROPIC = '''
import json, os
class AnthropicError(Exception): pass
class AuthenticationError(AnthropicError): pass
class APIConnectionError(AnthropicError): pass
class _Bloc:
    def __init__(self, texte): self.type, self.text = "text", texte
class _Message:
    def __init__(self, stop, texte): self.stop_reason, self.content = stop, [_Bloc(texte)]
class _Messages:
    def create(self, **kw):
        mode = os.environ.get("FAUX_ANTHROPIC_MODE", "ok")
        if mode == "auth":
            raise AuthenticationError("401")
        contenu = kw["messages"][0]["content"]
        trace = {"model": kw["model"],
                 "images": [len(b["source"]["data"]) for b in contenu if b["type"] == "image"],
                 "textes": [b["text"] for b in contenu if b["type"] == "text"]}
        with open(os.environ["FAUX_ANTHROPIC_TRACE"], "w") as f:
            json.dump(trace, f)
        if mode == "refus":
            return _Message("refusal", "")
        return _Message("end_turn", 'Voici : {"changement_detecte": true, "analyse": "bandeau rouge", "priorite": "haute"}')
class Anthropic:
    def __init__(self, **kw): self.messages = _Messages()
'''


def _pngs(dossier):
    from PIL import Image
    ref, cap = os.path.join(dossier, "ref.png"), os.path.join(dossier, "cap.png")
    Image.new("RGB", (400, 300), (255, 255, 255)).save(ref)
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    img.paste((200, 0, 0), (0, 0, 400, 60))
    img.save(cap)
    return ref, cap


def _watch(dossier, ref, cap, mode):
    env = dict(os.environ, FAUX_ANTHROPIC_MODE=mode, PYTHONPATH=os.path.join(dossier, "faux"),
               FAUX_ANTHROPIC_TRACE=os.path.join(dossier, "trace.json"))
    env.pop("ANTHROPIC_API_KEY", None)
    r = subprocess.run(
        [PYTHON, WATCH, "--url", "http://127.0.0.1/", "--comparer-pixel", ref,
         "--capture", cap, "--llm-en-complement", "--llm", "claude",
         "--guide-version", _jeton_guide()],
        capture_output=True, text=True, env=env, timeout=120,
    )
    try:
        sortie = json.loads(r.stdout[r.stdout.find("{"):])
    except ValueError:
        sortie = {}
    return r, sortie


def test_4_comparer_claude_bout_en_bout():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "faux", "anthropic"))
        with open(os.path.join(d, "faux", "anthropic", "__init__.py"), "w") as f:
            f.write(_FAUX_ANTHROPIC)
        ref, cap = _pngs(d)
        r, sortie = _watch(d, ref, cap, "ok")
        trace = json.load(open(os.path.join(d, "trace.json"))) if os.path.exists(os.path.join(d, "trace.json")) else {}
        modeles = (sortie.get("diwall_meta") or {}).get("modeles_utilises") or []
        return _verdict("T-4 — diwall-watch --llm claude envoie les deux captures et lit la réponse", [
            # Bandeau rouge sur 20 % de l'image : verdict « regression », dont
            # le code de sortie est 1 par construction de --comparer-pixel.
            (f"verdict regression, exit 1 (reçu {sortie.get('verdict')}, {r.returncode})",
             sortie.get("verdict") == "regression" and r.returncode == 1),
            (f"modèle {CLAUDE_MODEL}", trace.get("model") == CLAUDE_MODEL),
            ("deux images, référence puis actuelle", len(trace.get("images", [])) == 2
             and trace.get("textes", [""])[0].startswith("Capture de référence")),
            ("analyse lue dans la réponse JSON", sortie.get("analyse_llm") == "bandeau rouge"),
            ("modèle tracé dans diwall_meta", any(CLAUDE_MODEL in json.dumps(m) for m in modeles)),
            ("aucune trace Python", "Traceback" not in r.stderr),
        ])


def test_5_erreurs_lisibles():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "faux", "anthropic"))
        with open(os.path.join(d, "faux", "anthropic", "__init__.py"), "w") as f:
            f.write(_FAUX_ANTHROPIC)
        ref, cap = _pngs(d)
        _, refus = _watch(d, ref, cap, "refus")
        _, auth = _watch(d, ref, cap, "auth")
        sys.path.insert(0, RACINE)
        import watch  # noqa: E402
        import builtins
        vrai_import = builtins.__import__

        def sans_anthropic(nom, *a, **k):
            if nom == "anthropic":
                raise ImportError(nom)
            return vrai_import(nom, *a, **k)

        builtins.__import__ = sans_anthropic
        try:
            watch.comparer_claude(ref, cap, "p")
            message_absent = ""
        except RuntimeError as e:
            message_absent = str(e)
        finally:
            builtins.__import__ = vrai_import
        return _verdict("T-5 — refus, identifiants absents, module absent : message clair, jamais de trace", [
            ("refus du modèle signalé", "refusé" in str(refus.get("analyse_llm"))),
            ("identifiants absents signalés", "ANTHROPIC_API_KEY" in str(auth.get("analyse_llm"))),
            ("module absent : commande d'installation donnée",
             "/opt/diwall/venv/bin/pip install anthropic" in message_absent),
        ])


def test_6_garde_canal():
    garde = os.path.join(RACINE, "scripts", "garde_canal_deb.sh")
    conditions = []
    with tempfile.TemporaryDirectory() as d:
        faux = os.path.join(d, "dpkg-query")
        for etat, attendu in (("installed", 1), ("config-files", 0), ("", 0)):
            with open(faux, "w") as f:
                f.write(f"#!/bin/sh\nprintf '{etat}'\n")
            os.chmod(faux, 0o700)
            r = subprocess.run(["bash", "-c", f"source {garde}; garde_canal_deb"],
                               capture_output=True, text=True,
                               env=dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"]))
            conditions.append((f"état « {etat or 'absent'} » → exit {attendu} (reçu {r.returncode})",
                               r.returncode == attendu))
    for script in ("deploy.sh", "install.sh"):
        texte = open(os.path.join(RACINE, "scripts", script), encoding="utf-8").read()
        premiere_ecriture = min(i for i in (texte.find("sudo "), texte.find("mkdir")) if i >= 0)
        conditions.append((f"{script} appelle la garde avant toute écriture",
                           0 <= texte.find("\ngarde_canal_deb\n") < premiere_ecriture))
    return _verdict("T-6 — la garde refuse d'écraser une installation par paquet, et seulement elle", conditions)


def main():
    resultats = [
        test_1_structurees_liberees(),
        test_2_jetons_toujours_detectes(),
        test_3_formes_indistinguables_masquees(),
        test_4_comparer_claude_bout_en_bout(),
        test_5_erreurs_lisibles(),
        test_6_garde_canal(),
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
