#!/usr/bin/env python3
"""Verifier — v1.21.0 (--http-credentials, HTTP Basic Auth).

Usage:
    /opt/diwall/venv/bin/python3 scenarios/v1.21.0_validation/verifier.py

T-2 et T-3 nécessitent un répertoire chiffré gocryptfs monté (secrets_dir de diwall.conf,
ou --secrets déduit dynamiquement) — _repertoire_est_monte() (lib/repertoire_chiffre.py)
restreint T1 aux montages FUSE, tmpfs (/tmp) est refusé malgré la mention
dans le message d'erreur (vérifié en conditions réelles, 15/07/2026).
Si aucun répertoire chiffré n'est monté, T-2 et T-3 sont signalés SKIP, pas KO.
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
FIXTURE_SERVEUR = os.path.join(
    RACINE, "scenarios", "interoperabilite", "fixture", "serveur_basicauth.py"
)
PYTHON = sys.executable
GUIDE_VERSION = "1.0"  # compteur propre au guide — voir docs/GUIDE_LLM.md notice-version
PORT = 8643
URL_FIXTURE = f"http://127.0.0.1:{PORT}/"
UTILISATEUR = "diwall_fixture"
MOT_DE_PASSE = "diwall_fixture_password"


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def _demarrer_fixture():
    proc = subprocess.Popen(
        [PYTHON, FIXTURE_SERVEUR, str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            urllib.request.urlopen(URL_FIXTURE, timeout=0.5)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return proc
        except Exception:
            pass
        time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("fixture Basic Auth n'a pas démarré à temps")


def _repertoire_monte_disponible():
    """Détecte un répertoire chiffré gocryptfs déjà monté, sans dépendre d'un chemin
    personnel — parcourt /proc/mounts. Restriction à 'fuse.gocryptfs'
    précisément (pas juste 'fuse' comme lib.repertoire_chiffre._repertoire_est_monte(),
    qui accepterait à tort des pseudo-fs kernel type fusectl,
    /sys/fs/fuse/connections — non écrivables, jamais un vrai répertoire chiffré)."""
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for ligne in f:
                parties = ligne.split()
                if len(parties) >= 3 and parties[2] == "fuse.gocryptfs":
                    return parties[1]
    except OSError:
        pass
    return None


def test_1_401_sans_flag():
    """Sans --http-credentials : 401 propre, signal distinct, jamais de
    faux http_credentials_actif (portable — aucun répertoire chiffré requis)."""
    r = subprocess.run(
        [PYTHON, SHOT, "--url", URL_FIXTURE, "--no-capture",
         "--guide-version", GUIDE_VERSION],
        capture_output=True, text=True, timeout=30,
    )
    sortie = json.loads(r.stdout) if r.returncode == 0 else {}
    boussole = sortie.get("boussole", {})

    return _verdict("T-1) 401 sans --http-credentials — signal distinct (v1.21.0)", [
        ("run reussi (401 est un http_status, pas un echec Diwall)", r.returncode == 0),
        ("http_status == 401", sortie.get("http_status") == 401),
        ("boussole.http_auth_requise == True", boussole.get("http_auth_requise") is True),
        ("boussole.http_credentials_actif absent (jamais de faux positif)",
         "http_credentials_actif" not in boussole),
    ])


def test_2_succes_avec_flag(secrets_dir):
    """Avec --http-credentials et les bons identifiants : challenge résolu,
    boussole.http_credentials_actif reflète un succès réel (pas juste le flag)."""
    if secrets_dir is None:
        return None, ["[SKIP] T-2) succès avec --http-credentials — aucun répertoire chiffré monté"]

    chemin = os.path.join(secrets_dir, "_test_v1210_fixture_secrets.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"http_username": UTILISATEUR, "http_password": MOT_DE_PASSE}, f)
    try:
        r = subprocess.run(
            [PYTHON, SHOT, "--url", URL_FIXTURE, "--no-capture", "--http-credentials",
             "--secrets", chemin, "--guide-version", GUIDE_VERSION],
            capture_output=True, text=True, timeout=30,
        )
        sortie = json.loads(r.stdout) if r.returncode == 0 else {}
        boussole = sortie.get("boussole", {})
    finally:
        os.remove(chemin)

    return _verdict("T-2) succès avec --http-credentials + bons identifiants (v1.21.0)", [
        ("run reussi", r.returncode == 0),
        ("http_status == 200", sortie.get("http_status") == 200),
        ("boussole.http_credentials_actif == True", boussole.get("http_credentials_actif") is True),
        ("boussole.http_auth_requise absent (challenge resolu)",
         "http_auth_requise" not in boussole),
    ])


def test_3_mauvais_identifiants(secrets_dir):
    """Flag actif mais mauvais mot de passe : le challenge n'est PAS résolu —
    http_credentials_actif doit rester absent (précédent stealth_actif, v1.16.0)."""
    if secrets_dir is None:
        return None, ["[SKIP] T-3) mauvais identifiants — aucun répertoire chiffré monté"]

    chemin = os.path.join(secrets_dir, "_test_v1210_fixture_secrets_faux.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"http_username": UTILISATEUR, "http_password": "mauvais_mot_de_passe"}, f)
    try:
        r = subprocess.run(
            [PYTHON, SHOT, "--url", URL_FIXTURE, "--no-capture", "--http-credentials",
             "--secrets", chemin, "--guide-version", GUIDE_VERSION],
            capture_output=True, text=True, timeout=30,
        )
        sortie = json.loads(r.stdout) if r.returncode == 0 else {}
        boussole = sortie.get("boussole", {})
    finally:
        os.remove(chemin)

    return _verdict("T-3) flag actif + mauvais identifiants — jamais de faux positif (v1.21.0)", [
        ("run reussi (401 n'est pas un echec Diwall)", r.returncode == 0),
        ("http_status == 401", sortie.get("http_status") == 401),
        ("boussole.http_credentials_actif absent malgre le flag actif",
         "http_credentials_actif" not in boussole),
        ("boussole.http_auth_requise == True", boussole.get("http_auth_requise") is True),
    ])


def main():
    proc = _demarrer_fixture()
    secrets_dir = _repertoire_monte_disponible()
    try:
        resultats = [test_1_401_sans_flag()]
        for fn in (test_2_succes_avec_flag, test_3_mauvais_identifiants):
            resultats.append(fn(secrets_dir))
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    n_ok, n_total = 0, 0
    for ok, lignes in resultats:
        print("\n".join(lignes))
        if ok is None:
            continue
        n_total += 1
        if ok:
            n_ok += 1
    print()
    print(f"=== {n_ok}/{n_total} tests OK ({len(resultats) - n_total} SKIP) ===")
    sys.exit(0 if n_ok == n_total else 1)


if __name__ == "__main__":
    main()
