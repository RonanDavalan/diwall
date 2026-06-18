#!/usr/bin/env python3
"""Vérificateur lib/journal.py — lot v1.4, étapes 1-3 (offline).

Exécution :
    PYTHONPATH=/home/ron/git/Diwall/Diwall python3 verifier.py

Reproduit T1, T2, T3 de §10 de
_CADRE/SPECIFICATIONS/35_JOURNAL_OPERATIONS.md.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent.parent  # .../Diwall/Diwall/
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

# Journal et preuves redirigés vers un répertoire temporaire pour les tests.
_TMP = tempfile.mkdtemp(prefix="diwall_journal_test_")
os.environ["DIWALL_JOURNAL"] = os.path.join(_TMP, "operations.jsonl")
os.environ["DIWALL_PREUVES"] = os.path.join(_TMP, "preuves")

from lib import journal  # noqa: E402

META = {
    "hostname_executant": "neo",
    "utilisateur_executant": "ron",
    "profil_actif": "(aucun — comportement strict)",
    "modeles_utilises": [],
}


def _verdict(nom, conditions):
    lignes = []
    ok = True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


def _entrees():
    p = os.environ["DIWALL_JOURNAL"]
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_t1_mutatif_preuves():
    cap = os.path.join(_TMP, "capture_fake.png")
    with open(cap, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n fake")
    actions = [
        {"type": "cliquer_som", "id": 10},
        {"type": "remplir_som", "id": 19, "valeur": "supprimer"},
        {"type": "cliquer", "selecteur": "#btn-lot-confirmer"},
    ]
    journal.enregistrer_operation(
        outil="shot.py", version="1.4.0",
        cible_url="https://target.local/?vue=domaine&domaine=__DOMAINE_CLIENT__",
        resultat="succes", actions=actions, diwall_meta=META,
        intention="Suppression clone __DOMAINE_CLIENT__ 2026-05-30", captures=[cap],
    )
    e = _entrees()[-1]
    preuves = e.get("captures") or []
    preuves_ok = bool(preuves) and all(
        os.environ["DIWALL_PREUVES"] in c and os.path.isfile(c) for c in preuves
    )
    return _verdict("T1) run mutatif → mutatif=true + preuves archivées", [
        ("mutatif == True", e.get("mutatif") is True),
        ("intention présente", (e.get("intention") or "").startswith("Suppression")),
        ("captures archivées sous preuves/ et existantes", preuves_ok),
        ("hostname/utilisateur repris de diwall_meta",
         e.get("hostname_executant") == "neo" and e.get("utilisateur_executant") == "ron"),
        ("actions résumées présentes", "cliquer_som#10" in (e.get("actions") or [])),
    ])


def test_t2_lecture_pas_archivage():
    cap = os.path.join(_TMP, "capture_lecture.png")
    with open(cap, "wb") as f:
        f.write(b"\x89PNG fake2")
    actions = [
        {"type": "capturer", "nom": "vue"},
        {"type": "attendre", "selecteur": "button"},
        {"type": "pause", "ms": 100},
    ]
    journal.enregistrer_operation(
        outil="shot.py", version="1.4.0", cible_url="https://target.local/",
        resultat="succes", actions=actions, diwall_meta=META, captures=[cap],
    )
    e = _entrees()[-1]
    pas_archive = all(
        os.environ["DIWALL_PREUVES"] not in c for c in (e.get("captures") or [])
    )
    return _verdict("T2) run lecture → mutatif=false, pas d'archivage", [
        ("mutatif == False", e.get("mutatif") is False),
        ("captures non archivées sous preuves/", pas_archive),
    ])


def test_t3_securite_zero_credential():
    actions = [
        {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "password"},
        # Simule le chemin rpa.py : vault résolu en amont, valeur en clair.
        {"type": "remplir", "selecteur": "#pwd", "valeur": "S3CR3T_RESOLU_simule"},
        {"type": "cliquer_som", "id": 2},
    ]
    journal.enregistrer_operation(
        outil="shot.py", version="1.4.0",
        cible_url="https://target.local/?vue=login",
        resultat="succes", actions=actions, diwall_meta=META, intention="Login",
    )
    e = _entrees()[-1]
    raw = json.dumps(e, ensure_ascii=False)
    resume = (e.get("actions") or [""])[0]
    return _verdict("T3) sécurité — credentials masqués (vault + défense en profondeur)", [
        ("résumé vault = 'remplir_som#1=<vault:password>'",
         resume == "remplir_som#1=<vault:password>"),
        ("'depuis_vault' absent de la ligne", "depuis_vault" not in raw),
        ("'vault_cle' (clé brute) absente de la ligne", "vault_cle" not in raw),
        ("valeur de saisie résolue masquée (défense en profondeur)",
         "S3CR3T_RESOLU" not in raw),
    ])


def main():
    tests = (
        test_t1_mutatif_preuves,
        test_t2_lecture_pas_archivage,
        test_t3_securite_zero_credential,
    )
    n_ok = 0
    for fn in tests:
        ok, lignes = fn()
        print("\n".join(lignes))
        if ok:
            n_ok += 1
    print()
    print(f"=== {n_ok}/{len(tests)} scénarios OK ===")
    sys.exit(0 if n_ok == len(tests) else 1)


if __name__ == "__main__":
    main()
