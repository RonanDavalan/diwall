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
__version__ = "1.9.2"

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _boussole():
    try:
        ip = subprocess.check_output(
            "hostname -I | cut -d' ' -f1", shell=True, text=True
        ).strip()
    except Exception:
        ip = ""
    return {
        "utilisateur": os.getenv("USER", ""),
        "ip_locale": ip,
        "repertoire": os.getcwd(),
    }
from lib.vault import domaine_depuis_url, verifier_cles, VaultFermeError

_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "scenarios", "schema.json")
_jsonschema_absent_warned = False


def _valider_schema(scenario: dict, chemin_scenario: str) -> None:
    """Valide le scénario contre scenarios/schema.json.

    Auto-active si jsonschema est installé : exit 1 et diagnostic structuré
    sur stderr si la validation échoue. Émet un warning unique sur stderr
    et continue sans valider si jsonschema est absent ou si le schéma est
    introuvable.
    """
    global _jsonschema_absent_warned
    try:
        import jsonschema
    except ImportError:
        if not _jsonschema_absent_warned:
            print(
                "⚠ jsonschema absent — validation des scénarios désactivée. "
                "Installer via : /opt/diwall/venv/bin/pip install jsonschema",
                file=sys.stderr,
            )
            _jsonschema_absent_warned = True
        return

    if not os.path.isfile(_SCHEMA_PATH):
        if not _jsonschema_absent_warned:
            print(
                f"⚠ schéma de validation introuvable ({_SCHEMA_PATH}) — "
                "validation des scénarios désactivée.",
                file=sys.stderr,
            )
            _jsonschema_absent_warned = True
        return

    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(instance=scenario, schema=schema)
    except jsonschema.ValidationError as e:
        chemin_champ = " → ".join(str(p) for p in e.absolute_path) or "(racine)"
        print(
            f"❌ Scénario invalide ({chemin_scenario}) :\n"
            f"   champ    : {chemin_champ}\n"
            f"   message  : {e.message}",
            file=sys.stderr,
        )
        sys.exit(1)


def _linter_som(actions, chemin_scenario):
    """Vérifie statiquement que les actions SoM référencent un id entier positif.

    Bloque avant le lancement de Playwright — fail-fast sur les erreurs détectables
    sans accès à la page (spec 41_ §B).
    """
    for i, a in enumerate(actions):
        if not isinstance(a, dict):
            continue
        t = a.get("type")
        if t not in ("cliquer_som", "remplir_som"):
            continue
        id_val = a.get("id")
        if not isinstance(id_val, int) or id_val < 1:
            print(json.dumps({
                "succes": False,
                "erreur": "linter_som",
                "message": (
                    f"Action #{i} ({t}) : 'id' doit être un entier positif, "
                    f"reçu : {json.dumps(id_val)}."
                ),
                "scenario": chemin_scenario,
                "boussole": _boussole(),
            }))
            sys.exit(1)


def _aplatir_actions(actions, profondeur=0):
    """Inline les sous-scénarios référencés par declencher_scenario (spec 41_ §A).

    Résolution récursive : chaque declencher_scenario est remplacé par les
    actions du sous-scénario correspondant. Profondeur max : 5 niveaux.
    Le vault et le journal restent gérés par le run parent.
    """
    if profondeur > 5:
        print(json.dumps({
            "succes": False,
            "erreur": "profondeur_max_chainages",
            "message": "Profondeur maximale de chaînage (5) atteinte — vérifier les appels circulaires.",
            "profondeur": profondeur,
            "boussole": _boussole(),
        }))
        sys.exit(1)

    resultat = []
    for a in actions:
        if not isinstance(a, dict) or a.get("type") != "declencher_scenario":
            resultat.append(a)
            continue
        nom = a.get("scenario", "")
        chemin, essais = resoudre_chemin_scenario(nom)
        if not chemin:
            print(json.dumps({
                "succes": False,
                "erreur": "fichier_introuvable",
                "message": f"Sous-scénario introuvable : {nom}",
                "chemins_testes": essais,
                "boussole": _boussole(),
            }))
            sys.exit(1)
        try:
            sous = charger_scenario(chemin)
        except Exception as e:
            print(json.dumps({
                "succes": False, "erreur": "scenario_invalide",
                "message": f"Sous-scénario {nom!r} : {e}",
                "boussole": _boussole(),
            }))
            sys.exit(1)
        resultat.extend(_aplatir_actions(sous.get("actions", []), profondeur + 1))
    return resultat


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
                               "pip install pyyaml  (dans /opt/diwall/venv/)",
                    "boussole": _boussole(),
                }))
                sys.exit(1)
        else:
            return json.load(f)


def main():
    p = argparse.ArgumentParser(description="Diwall RPA — exécuteur de scénarios")
    p.add_argument("--scenario", required=True, help="Chemin vers le fichier de scénario (JSON ou YAML)")
    p.add_argument("--output-dir", dest="output_dir", default="/tmp/diwall",
                   help="Répertoire de sortie des captures (défaut : /tmp/diwall)")
    p.add_argument("--som", action="store_true", help="Active le Set-of-Mark sur la capture finale")
    p.add_argument("--a11y", action="store_true", help="Inclut le snapshot A11y dans le JSON")
    p.add_argument("--timeout", type=int, default=10000, help="Timeout ms par action (défaut : 10000)")
    p.add_argument("--intention", default=None,
                   help="Libellé métier du run pour le journal d'opérations (v1.4). "
                        "À défaut, le champ 'intention' du scénario est utilisé.")
    p.add_argument("--no-capture", dest="no_capture", action="store_true",
                   help="Skip la capture PNG finale et les écritures disque (v1.9). "
                        "Transmis à shot.py.")
    args = p.parse_args()

    chemin_scenario, essais = resoudre_chemin_scenario(args.scenario)
    if not chemin_scenario:
        print(json.dumps({
            "succes": False, "erreur": "fichier_introuvable",
            "message": f"Scénario introuvable : {args.scenario}",
            "chemins_testes": essais,
            "boussole": _boussole(),
        }))
        sys.exit(1)

    try:
        scenario = charger_scenario(chemin_scenario)
    except Exception as e:
        print(json.dumps({
            "succes": False, "erreur": "scenario_invalide", "message": str(e),
            "boussole": _boussole(),
        }))
        sys.exit(1)

    # Validation contre scenarios/schema.json (lot 9.2). Bloquant si jsonschema
    # est installé et le schéma rejette ; warning unique sinon.
    _valider_schema(scenario, chemin_scenario)

    # Chaînage : inline les sous-scénarios avant toute autre opération (v1.9.2).
    actions_brutes = scenario.get("actions", [])
    actions = _aplatir_actions(actions_brutes)

    # Linter SoM : vérifie les id entiers avant Playwright (v1.9.2).
    _linter_som(actions, chemin_scenario)

    url = scenario.get("url")
    if not url:
        print(json.dumps({
            "succes": False, "erreur": "scenario_invalide",
            "message": "Champ 'url' manquant dans le scénario",
            "boussole": _boussole(),
        }))
        sys.exit(1)

    # Pré-validation du coffre (fail-fast) SANS résoudre les valeurs : on
    # vérifie l'existence du coffre et des clés référencées, puis on passe
    # les actions avec 'depuis_vault' INTACT à shot.py, qui résout lui-même
    # au moment de remplir. Le credential ne transite jamais par la ligne
    # de commande (§6.1 spec 35_).
    try:
        cles = []
        for a in actions:
            if a.get("valeur") == "depuis_vault":
                cle = a.get("vault_cle")
                if not cle:
                    raise ValueError(
                        f"Action {a.get('type')!r} : 'vault_cle' requis "
                        f"quand valeur='depuis_vault'"
                    )
                cles.append(cle)
        if cles:
            verifier_cles(domaine_depuis_url(url), cles)
    except VaultFermeError as e:
        print(json.dumps({
            "succes": False, "erreur": "vault_ferme",
            "message": str(e),
            "code_sortie_recommande": VaultFermeError.CODE_SORTIE,
            "boussole": _boussole(),
        }))
        sys.exit(VaultFermeError.CODE_SORTIE)
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(json.dumps({
            "succes": False, "erreur": "vault_erreur", "message": str(e),
            "boussole": _boussole(),
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
    if args.no_capture:
        cmd.append("--no-capture")
    auth_indicator = scenario.get("auth_indicator")
    if auth_indicator:
        cmd += ["--auth-indicator", auth_indicator]
    # Journal d'opérations (v1.4) : transmettre l'intention à shot.py, qui
    # journalise le run. L'argument CLI prime sur le champ 'intention' du
    # scénario. rpa.py ne journalise pas lui-même (un seul run = celui de
    # shot.py), pour éviter le double comptage.
    intention = args.intention or scenario.get("intention")
    if intention:
        cmd += ["--intention", intention]

    # Pré-collecte des assertions : clé 'attendu' sur les actions 'evaluer'.
    # Lue côté rpa.py uniquement ; shot.py l'ignore (clé inconnue).
    attentes = []
    for i, a in enumerate(actions):
        if "attendu" not in a:
            continue
        if a.get("type") != "evaluer":
            print(
                f"avertissement : clé 'attendu' ignorée sur action #{i} "
                f"(type {a.get('type')!r}, valide uniquement sur 'evaluer')",
                file=sys.stderr,
            )
            continue
        attentes.append((i, a["attendu"]))

    # Propagation v1.3 du profil opérateur : on transmet explicitement
    # l'environnement (notamment DIWALL_PROFIL) au subprocess shot.py.
    # Conforme à _CADRE/SPECIFICATIONS/33_CONFIG_OPERATEUR.md §4.3 :
    # la résolution du profil actif lit DIWALL_PROFIL en premier.
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=os.environ.copy(),
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Parse une seule fois pour signalements structurés et assertions
    try:
        sortie = json.loads(result.stdout)
    except json.JSONDecodeError:
        sortie = None

    # Signalement de dérive de session (lot 8.5) — informatif, n'interrompt pas
    if sortie and "derive_session" in sortie:
        d = sortie["derive_session"]
        print(
            f"⚠ dérive de session détectée : "
            f"URL sauvegardée {d.get('url_sauvegardee')!r} "
            f"≠ URL reprise {d.get('url_reprise')!r}. "
            f"L'état DOM n'est pas préservé entre sauvegarde et reprise. "
            f"Voir _CADRE/SPECIFICATIONS/26_GUIDE_CLAUDE_SESSION_DIWALL.md.",
            file=sys.stderr,
        )

    if result.returncode != 0 or not attentes:
        sys.exit(result.returncode)

    if sortie is None:
        # shot.py a réussi mais le JSON est illisible : on ne juge pas.
        sys.exit(result.returncode)

    evaluations = {e["index"]: e for e in sortie.get("evaluations", [])}
    for idx, attendu in attentes:
        ev = evaluations.get(idx)
        if ev is None:
            print(
                f"Assertion impossible action #{idx} : aucune évaluation retournée par shot.py",
                file=sys.stderr,
            )
            sys.exit(1)
        if ev.get("valeur") != attendu:
            print(
                f"Assertion échouée action #{idx} (evaluer) :\n"
                f"  script  : {ev.get('script')}\n"
                f"  attendu : {json.dumps(attendu, ensure_ascii=False)}\n"
                f"  obtenu  : {json.dumps(ev.get('valeur'), ensure_ascii=False)}",
                file=sys.stderr,
            )
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
