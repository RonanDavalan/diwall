#!/opt/diwall/venv/bin/python3
"""
rpa.py — Phase 6 : exécuteur de scénarios RPA (JSON ou YAML).

Usage :
    /opt/diwall/rpa.py --scenario /opt/diwall/scenarios/example_login.json
    /opt/diwall/rpa.py --scenario example_login        # résolu en scenarios/example_login.json
    /opt/diwall/rpa.py --scenario example_login.yaml   # PyYAML requis

Format du scénario :
    {
        "nom": "example_login",
        "url": "https://your-app.local/",
        "actions": [
            {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "password"},
            {"type": "cliquer_som", "id": 2}
        ]
    }

Le vault est résolu par lib/vault.py (DIWALL_VAULT_DIR > diwall.conf > ~/Vaults/Diwall/).
Jamais de mot de passe dans les fichiers de scénario.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.vault import lire_credential, domaine_depuis_url


def resoudre_chemin_scenario(arg: str) -> tuple:
    """Résout --scenario en cascade : chemin direct, puis scenarios/<nom>[.json|.yaml|.yml].

    Retourne (chemin_resolu, essais). Si chemin_resolu est None, essais liste les
    chemins testés pour le message d'erreur.
    """
    if os.path.isfile(arg):
        return arg, [arg]
    base = os.path.dirname(os.path.abspath(__file__))
    scenarios_dir = os.path.join(base, "scenarios")
    essais = [arg]
    candidats = [os.path.join(scenarios_dir, arg)]
    if not os.path.splitext(arg)[1]:
        candidats += [
            os.path.join(scenarios_dir, arg + ".json"),
            os.path.join(scenarios_dir, arg + ".yaml"),
            os.path.join(scenarios_dir, arg + ".yml"),
        ]
    for c in candidats:
        essais.append(c)
        if os.path.isfile(c):
            return c, essais
    return None, essais


def charger_scenario(chemin: str) -> dict:
    ext = os.path.splitext(chemin)[1].lower()
    with open(chemin, encoding="utf-8") as f:
        if ext in (".yaml", ".yml"):
            try:
                import yaml
                return yaml.safe_load(f)
            except ImportError:
                print(json.dumps({
                    "succes": False, "erreur": "dependance_manquante",
                    "message": "PyYAML requis pour les scénarios .yaml : "
                               "pip install pyyaml  (dans /opt/diwall/venv/)"
                }))
                sys.exit(1)
        else:
            return json.load(f)


def resoudre_vault(actions: list, url: str) -> list:
    """Remplace les valeurs 'depuis_vault' par les credentials lus en mémoire."""
    domaine = domaine_depuis_url(url)
    resolues = []
    for a in actions:
        a = dict(a)
        if a.get("valeur") == "depuis_vault":
            cle = a.get("vault_cle")
            if not cle:
                raise ValueError(
                    f"Action {a.get('type')!r} : 'vault_cle' requis quand valeur='depuis_vault'"
                )
            a["valeur"] = lire_credential(domaine, cle)
        resolues.append(a)
    return resolues


def main():
    p = argparse.ArgumentParser(description="Diwall RPA — exécuteur de scénarios")
    p.add_argument("--scenario", required=True, help="Chemin vers le fichier de scénario (JSON ou YAML)")
    p.add_argument("--output-dir", dest="output_dir", default="/tmp/diwall",
                   help="Répertoire de sortie des captures (défaut : /tmp/diwall)")
    p.add_argument("--som", action="store_true", help="Active le Set-of-Mark sur la capture finale")
    p.add_argument("--a11y", action="store_true", help="Inclut le snapshot A11y dans le JSON")
    p.add_argument("--timeout", type=int, default=10000, help="Timeout ms par action (défaut : 10000)")
    args = p.parse_args()

    chemin_scenario, essais = resoudre_chemin_scenario(args.scenario)
    if not chemin_scenario:
        print(json.dumps({
            "succes": False, "erreur": "fichier_introuvable",
            "message": f"Scénario introuvable : {args.scenario}",
            "chemins_testes": essais,
        }))
        sys.exit(1)

    try:
        scenario = charger_scenario(chemin_scenario)
    except Exception as e:
        print(json.dumps({
            "succes": False, "erreur": "scenario_invalide", "message": str(e),
        }))
        sys.exit(1)

    url = scenario.get("url")
    if not url:
        print(json.dumps({
            "succes": False, "erreur": "scenario_invalide",
            "message": "Champ 'url' manquant dans le scénario",
        }))
        sys.exit(1)

    actions = scenario.get("actions", [])

    try:
        actions = resoudre_vault(actions, url)
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(json.dumps({
            "succes": False, "erreur": "vault_erreur", "message": str(e),
        }))
        sys.exit(1)

    # Appel shot.py en mode séquentiel (Mode A)
    shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot.py")
    cmd = [
        sys.executable, shot,
        "--url", url,
        "--actions", json.dumps(actions),
        "--output-dir", args.output_dir,
        "--timeout", str(args.timeout),
    ]
    if args.som:
        cmd.append("--som")
    if args.a11y:
        cmd.append("--a11y")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
