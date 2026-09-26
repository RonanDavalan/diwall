#!/usr/bin/env python3
"""Vérificateur — v1.24.4 (la garde de canal reconnaît aussi les paquets RPM
et pacman).

Usage :
    /opt/diwall/venv/bin/python3 scenarios/v1.24.4_validation/verifier.py

Hors ligne : `dpkg-query`, `rpm` et `pacman` sont de faux exécutables placés en
tête du PATH. Le contre-test compte autant que le cas nominal : la garde ne
doit refuser que si un gestionnaire déclare le paquet installé, et une machine
qui possède `rpm` sans paquet Diwall doit passer.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
GARDE = os.path.join(RACINE, "scripts", "garde_canal_deb.sh")


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def _faux(repertoire, nom, code_sortie, sortie=""):
    chemin = os.path.join(repertoire, nom)
    with open(chemin, "w") as f:
        f.write(f"#!/bin/sh\nprintf '{sortie}'\nexit {code_sortie}\n")
    os.chmod(chemin, 0o700)


def _lancer(dpkg=None, rpm=None, pacman=None, action="installer"):
    """Exécute la garde avec les faux gestionnaires demandés.

    `dpkg` vrai simule l'état installed. `rpm` et `pacman` sont un code de
    sortie de la requête, ou None pour « ne connaît pas le paquet ».
    Le PATH est réduit au répertoire des faux et à /usr/bin:/bin pour `bash`
    et `command` ; un `rpm` ou `pacman` réel de la machine est masqué par un
    faux qui échoue quand on ne le demande pas présent.
    """
    with tempfile.TemporaryDirectory() as d:
        # Toujours simulé : la machine qui rejoue la suite peut avoir le
        # paquet Debian installé, et son vrai dpkg-query répondrait.
        _faux(d, "dpkg-query", 0, "installed" if dpkg else "")
        if rpm is not None:
            _faux(d, "rpm", rpm)
        if pacman is not None:
            _faux(d, "pacman", pacman)
        chemin = d + os.pathsep + "/usr/bin" + os.pathsep + "/bin"
        # Un rpm ou pacman réel de la machine ne doit pas répondre à la place.
        if rpm is None:
            _faux(d, "rpm", 1)
        if pacman is None:
            _faux(d, "pacman", 1)
        r = subprocess.run(["bash", "-c", f"source {GARDE}; garde_canal_deb {action}"],
                           capture_output=True, text=True, env=dict(os.environ, PATH=chemin))
        return r.returncode, r.stderr


def test_1_debian_inchange():
    conditions = []
    for etat, attendu in (("installed", 1), ("config-files", 0), ("", 0)):
        with tempfile.TemporaryDirectory() as d:
            _faux(d, "dpkg-query", 0, etat)
            _faux(d, "rpm", 1)
            _faux(d, "pacman", 1)
            r = subprocess.run(["bash", "-c", f"source {GARDE}; garde_canal_deb"],
                               capture_output=True, text=True,
                               env=dict(os.environ, PATH=d + os.pathsep + "/usr/bin:/bin"))
        conditions.append((f"dpkg « {etat or 'absent'} » → exit {attendu} (reçu {r.returncode})",
                           r.returncode == attendu))
    return _verdict("T-1 — le cas Debian ne change pas", conditions)


def test_2_rpm():
    code, err = _lancer(rpm=0)
    code_desinst, err_desinst = _lancer(rpm=0, action="désinstaller")
    return _verdict("T-2 — un paquet RPM installé bloque, et le message nomme la commande de retrait", [
        (f"rpm -q réussit → exit 1 (reçu {code})", code == 1),
        ("le message cite RPM", "RPM" in err),
        ("le message donne une commande de retrait (dnf ou zypper)",
         "dnf remove diwall" in err or "zypper remove diwall" in err),
        (f"désinstaller → exit 1 (reçu {code_desinst})", code_desinst == 1),
    ])


def test_3_pacman():
    code, err = _lancer(pacman=0)
    return _verdict("T-3 — un paquet pacman installé bloque", [
        (f"pacman -Q réussit → exit 1 (reçu {code})", code == 1),
        ("le message donne « sudo pacman -R diwall »", "sudo pacman -R diwall" in err),
    ])


def test_4_absences():
    c1, _ = _lancer(rpm=1)
    c2, _ = _lancer(pacman=1)
    c3, _ = _lancer()
    c4, _ = _lancer(dpkg=0, rpm=1, pacman=1)
    return _verdict("T-4 — pas de faux positif : gestionnaire présent sans paquet Diwall, ou absent", [
        (f"rpm présent, paquet inconnu → exit 0 (reçu {c1})", c1 == 0),
        (f"pacman présent, paquet inconnu → exit 0 (reçu {c2})", c2 == 0),
        (f"aucun gestionnaire de paquets Diwall → exit 0 (reçu {c3})", c3 == 0),
        (f"les trois présents, aucun ne connaît Diwall → exit 0 (reçu {c4})", c4 == 0),
    ])


def test_5_scripts_appellent_la_garde():
    conditions = []
    for script in ("deploy.sh", "install.sh", "uninstall.sh"):
        texte = open(os.path.join(RACINE, "scripts", script), encoding="utf-8").read()
        conditions.append((f"{script} source et appelle la garde",
                           "garde_canal_deb.sh" in texte and "\ngarde_canal_deb" in texte))
    return _verdict("T-5 — les trois scripts appellent la garde", conditions)


def main():
    resultats = [test_1_debian_inchange(), test_2_rpm(), test_3_pacman(),
                 test_4_absences(), test_5_scripts_appellent_la_garde()]
    n_ok = 0
    for ok, lignes in resultats:
        print("\n".join(lignes))
        n_ok += ok
    print()
    print(f"=== {n_ok}/{len(resultats)} tests OK ===")
    sys.exit(0 if n_ok == len(resultats) else 1)


if __name__ == "__main__":
    main()
