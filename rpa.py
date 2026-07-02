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
__version__ = "1.17.1"

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
from lib.vault import domaine_depuis_url, verifier_cles, verifier_cles_fichier, VaultFermeError

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
        hint = ""
        if not e.absolute_path and "is not of type" in e.message:
            hint = '\n   attendu  : objet {"actions": [{"type": "...", ...}, ...]}'
        elif (
            "is not valid under any of the given schemas" in e.message
            and isinstance(e.instance, dict)
            and e.instance.get("type") == "attendre"
            and "ms" in e.instance
        ):
            hint = (
                "\n   → `attendre` attend un sélecteur CSS (`selecteur`)."
                " Pour un délai fixe, utilisez `pause`."
            )
        print(
            f"❌ Scénario invalide ({chemin_scenario}) :\n"
            f"   champ    : {chemin_champ}\n"
            f"   message  : {e.message}{hint}",
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


# ── Replay verifier — comparaison structurelle sans vision (v1.17.0, item 1) ──

def _extraire_surface_verifiable(sortie):
    """Sous-ensemble structurel comparable d'un JSON de sortie shot.py.

    Exclut délibérément les champs volatils (timestamps, operation_id,
    duree_ms, boussole.ip_locale…) — seule la structure fonctionnelle du run
    est comparée, pas son empreinte d'exécution.
    """
    surface = {"http_status": sortie.get("http_status")}
    if sortie.get("dom_stats") is not None:
        surface["dom_stats"] = sortie["dom_stats"]
    if sortie.get("evaluations"):
        surface["evaluations"] = [
            {"script": e.get("script"), "valeur": e.get("valeur")}
            for e in sortie["evaluations"]
        ]
    if sortie.get("elements_som") is not None:
        surface["elements_som_count"] = len(sortie["elements_som"])
    return surface


def _comparer_surface_verifiable(reference, actuelle):
    """Compare chaque clé de `reference` à `actuelle`. Retourne la liste des diffs."""
    diffs = []
    for cle, val_ref in reference.items():
        val_actuelle = actuelle.get(cle)
        if val_actuelle != val_ref:
            diffs.append({"champ": cle, "reference": val_ref, "obtenu": val_actuelle})
    return diffs


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
    p.add_argument("--url", default=None,
                   help="Remplace l'URL du scénario à l'exécution sans modifier le fichier (v1.9.4).")
    p.add_argument("--secrets", default=None,
                   help="Chemin absolu vers un fichier JSON de credentials (v1.10). "
                        "Court-circuite la résolution par hostname. "
                        "Le répertoire parent doit être un point de montage actif (T1). "
                        "Propagé à shot.py pour tout le run.")
    p.add_argument("--shadow-dom", dest="shadow_dom", action="store_true",
                   help="Active la traversée Shadow DOM pour le SoM (v1.13.0). Propagé à shot.py.")
    p.add_argument("--som-rafraichir", dest="som_rafraichir", action="store_true",
                   help="Résolution SoM stable par attribut, anti-dérive d'identité (v1.17.0). "
                        "Propagé à shot.py.")
    p.add_argument("--auth-indicator-negative", dest="auth_indicator_negative", default=None,
                   help="Sélecteur CSS dont la présence indique l'ABSENCE d'auth (v1.14.0). "
                        "Propagé à shot.py.")
    p.add_argument("--mode", choices=["fast", "full"], default=None,
                   help="Raccourci de mode : fast = --no-capture --a11y | full = défaut (v1.14.0). "
                        "Propagé à shot.py.")
    p.add_argument("--stealth", action="store_true",
                   help="Active le mode furtif playwright-stealth (v1.15.0). Propagé à shot.py.")
    p.add_argument("--ignore-tls-errors", dest="ignore_tls_errors", action="store_true",
                   help="Accepte les certificats TLS invalides (LAN dev/Step-CA). Propagé à shot.py. (v1.15.1)")
    p.add_argument("--no-evaluer", dest="no_evaluer", action="store_true",
                   help="Désactive l'action evaluer sur ce run. Propagé à shot.py. (v1.15.1)")
    p.add_argument("--sauver-verifier-reference", dest="sauver_verifier_reference", default=None,
                   metavar="FICHIER",
                   help="Écrit un sous-ensemble structurel (http_status, dom_stats, "
                        "evaluations, nombre d'elements_som) de la sortie de ce run dans "
                        "FICHIER, pour comparaison future via --replay-verifier. (v1.17.0)")
    p.add_argument("--replay-verifier", dest="replay_verifier", default=None,
                   metavar="FICHIER",
                   help="Compare la sortie de ce run à la référence structurelle FICHIER "
                        "(produite par --sauver-verifier-reference). Verdict stable/regression, "
                        "exit 1 si régression. (v1.17.0)")
    p.add_argument("--checkpoint", dest="checkpoint", default=None,
                   metavar="FICHIER",
                   help="Reprend un scénario long depuis le dernier point de progression "
                        "enregistré dans FICHIER (session + index d'action). Crée FICHIER "
                        "au premier run, le supprime à la fin réussie du scénario. (v1.17.0)")
    args = p.parse_args()

    if args.sauver_verifier_reference and args.replay_verifier:
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--sauver-verifier-reference et --replay-verifier sont mutuellement "
                       "exclusifs — un run sauvegarde OU compare, jamais les deux.",
            "boussole": _boussole(),
        }))
        sys.exit(2)

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

    if args.url:
        scenario["url"] = args.url

    url = scenario.get("url")
    if not url:
        print(json.dumps({
            "succes": False, "erreur": "scenario_invalide",
            "message": "Champ 'url' manquant dans le scénario",
            "boussole": _boussole(),
        }))
        sys.exit(1)

    from urllib.parse import urlparse as _urlparse
    _scheme = _urlparse(url).scheme.lower()
    if _scheme not in {"http", "https"}:
        print(json.dumps({
            "succes": False, "erreur": "url_scheme_interdit",
            "message": f"URL scheme '{_scheme}' interdit — seuls http et https sont acceptés. URL: {url}",
            "boussole": _boussole(),
        }))
        sys.exit(2)

    # ── Checkpoint (v1.17.0, item 2) ──────────────────────────────────────────
    # Reprise = session + index d'action déjà exécutée. L'état DOM (modale
    # ouverte, champ à moitié rempli) ne survit jamais entre deux invocations —
    # seule une frontière entre deux actions complètes est un point de reprise
    # valide (contrainte héritée de Qwen Q3, v1.15.2).
    checkpoint_session_file = f"{args.checkpoint}.session.json" if args.checkpoint else None
    reprise_checkpoint = bool(args.checkpoint and os.path.isfile(args.checkpoint))
    if reprise_checkpoint:
        with open(args.checkpoint, encoding="utf-8") as f:
            _cp = json.load(f)
        n_completees = _cp.get("actions_completees", 0)
        actions = actions[n_completees:]
        if not actions:
            print(json.dumps({
                "succes": True,
                "message": "checkpoint déjà complet — rien à exécuter",
                "boussole": _boussole(),
            }))
            os.remove(args.checkpoint)
            sys.exit(0)

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
            if args.secrets:
                verifier_cles_fichier(args.secrets, cles)
            else:
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

    # Appel shot.py en mode séquentiel (Mode A), ou en reprise de session
    # (Mode B) si un checkpoint est en cours (v1.17.0, item 2).
    shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot.py")
    cmd = [sys.executable, shot]
    if reprise_checkpoint:
        cmd += ["--reprendre-session", checkpoint_session_file,
                "--sauver-session", checkpoint_session_file]
    else:
        cmd += ["--url", url]
        if args.checkpoint:
            cmd += ["--sauver-session", checkpoint_session_file]
    cmd += [
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
    if args.secrets:
        cmd += ["--secrets", args.secrets]
    auth_indicator = scenario.get("auth_indicator")
    auth_indicator_negative = args.auth_indicator_negative or scenario.get("auth_indicator_negative")
    # v1.15.2, item 2 / GL1 : même garde-fou que shot.py, avant tout subprocess.
    if auth_indicator_negative and not auth_indicator:
        print(json.dumps({
            "succes": False, "erreur": "arguments_incompatibles",
            "message": "--auth-indicator-negative requiert un auth_indicator "
                       "(clé 'auth_indicator' du scénario) — sans lui, l'indicateur "
                       "négatif est ignoré silencieusement",
            "boussole": _boussole(),
        }))
        sys.exit(2)
    if auth_indicator:
        cmd += ["--auth-indicator", auth_indicator]
    if args.shadow_dom or scenario.get("shadow_dom"):
        cmd.append("--shadow-dom")
    if args.som_rafraichir or scenario.get("som_rafraichir"):
        cmd.append("--som-rafraichir")
    if auth_indicator_negative:
        cmd += ["--auth-indicator-negative", auth_indicator_negative]
    if args.mode:
        cmd += ["--mode", args.mode]
    if args.stealth:
        cmd.append("--stealth")
    if args.ignore_tls_errors:
        cmd.append("--ignore-tls-errors")
    if args.no_evaluer:
        cmd.append("--no-evaluer")
    # Journal d'opérations (v1.4) : transmettre l'intention à shot.py, qui
    # journalise le run. L'argument CLI prime sur le champ 'intention' du
    # scénario. rpa.py ne journalise pas lui-même (un seul run = celui de
    # shot.py), pour éviter le double comptage.
    intention = args.intention or scenario.get("intention")
    if intention:
        cmd += ["--intention", intention]

    # Pré-collecte des assertions : clés 'attendu', 'contient', 'motif' sur 'evaluer'.
    # Lues côté rpa.py uniquement ; shot.py les ignore (clés inconnues).
    _CLES_ASSERTION = ("attendu", "contient", "motif")
    attentes = []
    for i, a in enumerate(actions):
        cles = [k for k in _CLES_ASSERTION if k in a]
        if not cles:
            continue
        if a.get("type") != "evaluer":
            print(
                f"avertissement : clé(s) d'assertion {cles!r} ignorée(s) sur action #{i} "
                f"(type {a.get('type')!r}, valide uniquement sur 'evaluer')",
                file=sys.stderr,
            )
            continue
        if len(cles) > 1:
            print(
                f"❌ Action #{i} : clés d'assertion en conflit : {cles}. "
                f"Une seule autorisée parmi {list(_CLES_ASSERTION)}.",
                file=sys.stderr,
            )
            sys.exit(1)
        attentes.append((i, a))

    # Propagation v1.3 du profil opérateur : on transmet explicitement
    # l'environnement (notamment DIWALL_PROFIL) au subprocess shot.py.
    # Conforme à _CADRE/SPECIFICATIONS/33_CONFIG_OPERATEUR.md §4.3 :
    # la résolution du profil actif lit DIWALL_PROFIL en premier.
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=os.environ.copy(),
    )
    # Transmettre uniquement la dernière ligne de la sortie de shot.py (le JSON),
    # même en cas de pollution accidentelle de stdout par une bibliothèque tierce.
    json_line = result.stdout.rstrip("\n").split("\n")[-1] if result.stdout.strip() else ""
    print(json_line)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Parse une seule fois pour signalements structurés et assertions
    try:
        sortie = json.loads(json_line)
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

    # ── Mise à jour du checkpoint (v1.17.0, item 2) ───────────────────────────
    if args.checkpoint and sortie is not None:
        if result.returncode == 0:
            # Tronçon restant entièrement exécuté — plus rien à reprendre.
            if os.path.isfile(args.checkpoint):
                os.remove(args.checkpoint)
        else:
            delta = sortie.get("actions_executees_avant_echec")
            if delta is not None:
                n_avant = 0
                if reprise_checkpoint:
                    with open(args.checkpoint, encoding="utf-8") as f:
                        n_avant = json.load(f).get("actions_completees", 0)
                with open(args.checkpoint, "w", encoding="utf-8") as f:
                    json.dump({
                        "actions_completees": n_avant + delta,
                        "session_file": checkpoint_session_file,
                    }, f, ensure_ascii=False, indent=2)
                print(
                    f"⚠ checkpoint mis à jour : {n_avant + delta} action(s) "
                    f"préservée(s) — relancer la même commande pour reprendre.",
                    file=sys.stderr,
                )
            # Sinon (échec avant tout executer_actions, ex. vault fermé) :
            # le checkpoint existant reste inchangé, nouvelle tentative identique.

    # Replay verifier (v1.17.0, item 1) — uniquement si shot.py a réussi :
    # rien de significatif à sauvegarder/comparer sur un run en échec.
    if sortie is not None and result.returncode == 0:
        if args.sauver_verifier_reference:
            surface = _extraire_surface_verifiable(sortie)
            with open(args.sauver_verifier_reference, "w", encoding="utf-8") as f:
                json.dump(surface, f, ensure_ascii=False, indent=2)
            print(f"✓ référence structurelle enregistrée : {args.sauver_verifier_reference}",
                  file=sys.stderr)
        elif args.replay_verifier:
            try:
                with open(args.replay_verifier, encoding="utf-8") as f:
                    reference = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(json.dumps({
                    "succes": False, "erreur": "reference_illisible", "message": str(e),
                    "boussole": _boussole(),
                }))
                sys.exit(1)
            actuelle = _extraire_surface_verifiable(sortie)
            diffs = _comparer_surface_verifiable(reference, actuelle)
            verdict = "regression" if diffs else "stable"
            print(json.dumps({
                "type_comparaison": "replay_verifier",
                "verdict": verdict,
                "diffs": diffs,
            }, ensure_ascii=False), file=sys.stderr)
            if diffs:
                sys.exit(1)

    if result.returncode != 0 or not attentes:
        sys.exit(result.returncode)

    if sortie is None:
        # shot.py a réussi mais le JSON est illisible : on ne juge pas.
        sys.exit(result.returncode)

    evaluations = {e["index"]: e for e in sortie.get("evaluations", [])}
    for idx, action in attentes:
        ev = evaluations.get(idx)
        if ev is None:
            print(
                f"Assertion impossible action #{idx} : aucune évaluation retournée par shot.py",
                file=sys.stderr,
            )
            sys.exit(1)

        valeur_obtenue = ev.get("valeur")

        if "attendu" in action:
            if valeur_obtenue != action["attendu"]:
                print(
                    f"Assertion échouée action #{idx} (evaluer) :\n"
                    f"  script  : {ev.get('script')}\n"
                    f"  attendu : {json.dumps(action['attendu'], ensure_ascii=False)}\n"
                    f"  obtenu  : {json.dumps(valeur_obtenue, ensure_ascii=False)}",
                    file=sys.stderr,
                )
                sys.exit(1)

        elif "contient" in action:
            if not isinstance(valeur_obtenue, str):
                print(
                    f"Assertion impossible action #{idx} (evaluer) :\n"
                    f"  script   : {ev.get('script')}\n"
                    f"  clé      : \"contient\"\n"
                    f"  problème : valeur retournée de type "
                    f"{type(valeur_obtenue).__name__} ({valeur_obtenue!r}), pas str.\n"
                    f"             Utilisez \"attendu\" pour comparer int ou bool.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if action["contient"] not in valeur_obtenue:
                print(
                    f"Assertion échouée action #{idx} (evaluer) :\n"
                    f"  script   : {ev.get('script')}\n"
                    f"  contient : {json.dumps(action['contient'], ensure_ascii=False)}\n"
                    f"  obtenu   : {json.dumps(valeur_obtenue, ensure_ascii=False)}",
                    file=sys.stderr,
                )
                sys.exit(1)

        elif "motif" in action:
            import re
            if not isinstance(valeur_obtenue, str):
                print(
                    f"Assertion impossible action #{idx} (evaluer) :\n"
                    f"  script   : {ev.get('script')}\n"
                    f"  clé      : \"motif\"\n"
                    f"  problème : valeur retournée de type "
                    f"{type(valeur_obtenue).__name__} ({valeur_obtenue!r}), pas str.\n"
                    f"             Utilisez \"attendu\" pour comparer int ou bool.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not re.search(action["motif"], valeur_obtenue):
                print(
                    f"Assertion échouée action #{idx} (evaluer) :\n"
                    f"  script : {ev.get('script')}\n"
                    f"  motif  : {json.dumps(action['motif'], ensure_ascii=False)}\n"
                    f"  obtenu : {json.dumps(valeur_obtenue, ensure_ascii=False)}",
                    file=sys.stderr,
                )
                sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
