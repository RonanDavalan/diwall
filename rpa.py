#!/opt/diwall/venv/bin/python3
"""
rpa.py — exécuteur de scénarios RPA Diwall (JSON ou YAML).

Pourquoi ce fichier existe :
    Un scénario RPA doit être validé (schéma, secrets jamais en clair,
    assertions) et rejoué de façon fiable avant que le résultat n'atteigne
    l'appelant. rpa.py fait cette pré-validation puis délègue l'exécution
    Playwright à shot.py en sous-processus — il n'exécute jamais d'action
    navigateur lui-même.

Usage :
    /opt/diwall/rpa.py --scenario /opt/diwall/scenarios/example_login.json
    /opt/diwall/rpa.py --scenario example_login        # résolu en scenarios/example_login.json
    /opt/diwall/rpa.py --scenario example_login.yaml   # PyYAML requis

Format du scénario :
    {
        "nom": "example_login",
        "url": "https://your-app.local/",
        "actions": [
            {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "password"},
            {"type": "cliquer_som", "id": 2}
        ]
    }

Entrée / sortie :
    CLI — `--scenario` (chemin ou nom résolu). Sortie : JSON structuré sur
    stdout (boussole, résultat, éventuelles erreurs d'assertion), codes de
    sortie non nuls sur échec.

Dépend de :
    shot.py (exécution effective, sous-processus), lib/repertoire_chiffre.py
    (résolution du répertoire chiffré : DIWALL_SECRETS_DIR > diwall.conf >
    ~/Vaults/Diwall/). Jamais de mot de passe dans les fichiers de scénario.
"""
__version__ = "1.23.0"

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


def _sortir_erreur(erreur, message=None, exit_code=1, **extra):
    """Émet un JSON d'erreur structuré (succes: false) sur stdout, puis quitte.

    Factorisé (chantier qualité 05/08/2026) — motif répété une quinzaine de
    fois dans ce fichier : succes=False + erreur + boussole avant sys.exit.
    Les champs propres à un site d'appel (scenario, chemins_testes,
    profondeur, code_sortie_recommande…) passent par **extra.
    """
    payload = {"succes": False, "erreur": erreur}
    if message is not None:
        payload["message"] = message
    payload.update(extra)
    payload["boussole"] = _boussole()
    print(json.dumps(payload))
    sys.exit(exit_code)


from lib.repertoire_chiffre import domaine_depuis_url, verifier_cles, verifier_cles_fichier, SecretsFermesError

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
            _sortir_erreur(
                "linter_som",
                message=(
                    f"Action #{i} ({t}) : 'id' doit être un entier positif, "
                    f"reçu : {json.dumps(id_val)}."
                ),
                scenario=chemin_scenario,
            )


def _aplatir_actions(actions, profondeur=0):
    """Inline les sous-scénarios référencés par declencher_scenario (spec 41_ §A).

    Résolution récursive : chaque declencher_scenario est remplacé par les
    actions du sous-scénario correspondant. Profondeur max : 5 niveaux.
    Le répertoire chiffré et le journal restent gérés par le run parent.

    Retourne `(resultat, chainage)` (v1.19.0) : `chainage` est la liste
    ordonnée des sous-scénarios rencontrés, chacun sous la forme
    `{"scenario", "profondeur", "action_debut", "action_fin"}` — indices dans
    la liste `resultat` finale (aplatie). Vide si le scénario n'utilise pas
    declencher_scenario. Permet à `journal.py` de reconstruire l'arbre
    d'appels d'un scénario chaîné après un échec en profondeur.
    """
    if profondeur > 5:
        _sortir_erreur(
            "profondeur_max_chainages",
            message="Profondeur maximale de chaînage (5) atteinte — vérifier les appels circulaires.",
            profondeur=profondeur,
        )

    resultat = []
    chainage = []
    for a in actions:
        if not isinstance(a, dict) or a.get("type") != "declencher_scenario":
            resultat.append(a)
            continue
        nom = a.get("scenario", "")
        chemin, essais = resoudre_chemin_scenario(nom)
        if not chemin:
            _sortir_erreur(
                "fichier_introuvable",
                message=f"Sous-scénario introuvable : {nom}",
                chemins_testes=essais,
            )
        try:
            sous = charger_scenario(chemin)
        except Exception as e:
            _sortir_erreur("scenario_invalide", message=f"Sous-scénario {nom!r} : {e}")
        debut = len(resultat)
        sous_actions, sous_chainage = _aplatir_actions(sous.get("actions", []), profondeur + 1)
        resultat.extend(sous_actions)
        chainage.append({
            "scenario": nom,
            "profondeur": profondeur + 1,
            "action_debut": debut,
            "action_fin": len(resultat) - 1,
        })
        for entree_c in sous_chainage:
            chainage.append({
                **entree_c,
                "action_debut": entree_c["action_debut"] + debut,
                "action_fin": entree_c["action_fin"] + debut,
            })
    return resultat, chainage


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
                _sortir_erreur(
                    "dependance_manquante",
                    message="PyYAML requis pour les scénarios .yaml : "
                            "pip install pyyaml  (dans /opt/diwall/venv/)",
                )
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


def _echouer_assertion(message):
    """Imprime un message d'échec/impossibilité d'assertion sur stderr, quitte (exit 1).

    Factorisé (chantier qualité 05/08/2026) — print+sys.exit(1) répété à
    l'identique dans les trois branches d'assertion (attendu/contient/motif) ;
    le message reste spécifique à chaque branche, seul le mécanisme d'arrêt
    est partagé.
    """
    print(message, file=sys.stderr)
    sys.exit(1)


def _verifier_valeur_str(idx, ev, valeur_obtenue, cle):
    """Vérifie que la valeur évaluée est une chaîne — requis par les
    assertions 'contient' et 'motif'. Factorisé — bloc dupliqué à l'identique
    entre ces deux branches, seule la clé affichée diffère.
    """
    if not isinstance(valeur_obtenue, str):
        _echouer_assertion(
            f"Assertion impossible action #{idx} (evaluer) :\n"
            f"  script   : {ev.get('script')}\n"
            f"  clé      : \"{cle}\"\n"
            f"  problème : valeur retournée de type "
            f"{type(valeur_obtenue).__name__} ({valeur_obtenue!r}), pas str.\n"
            f"             Utilisez \"attendu\" pour comparer int ou bool."
        )


def main():
    p = argparse.ArgumentParser(description="Diwall RPA — exécuteur de scénarios")
    p.add_argument("--version", action="store_true",
                   help="Affiche la version installée et quitte immédiatement, sans Playwright (v1.18.0).")
    p.add_argument("--guide-version", dest="guide_version", default=None,
                   help="Jeton de lecture de docs/GUIDE_LLM.md — requis sauf marqueur local valide "
                        "(v1.18.0). Valeur : <!-- notice-version: X.Y --> en tête de ce fichier.")
    p.add_argument("--scenario", required=False, default=None,
                   help="Chemin vers le fichier de scénario (JSON ou YAML)")
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
    p.add_argument("--ignorer-waf", dest="ignorer_waf", action="store_true",
                   help="Un blocage WAF dégrade niveau_confiance mais ne force plus "
                        "pret_a_agir à false à lui seul (v1.17.2). Propagé à shot.py.")
    p.add_argument("--auth-indicator-negative", dest="auth_indicator_negative", default=None,
                   help="Sélecteur CSS dont la présence indique l'ABSENCE d'auth (v1.14.0). "
                        "Propagé à shot.py.")
    p.add_argument("--mode", choices=["fast", "full"], default=None,
                   help="Raccourci de mode : fast = --no-capture --a11y | full = défaut (v1.14.0). "
                        "Propagé à shot.py.")
    p.add_argument("--stealth", action="store_true",
                   help="Active le mode furtif playwright-stealth (v1.15.0). Propagé à shot.py.")
    p.add_argument("--wait-until", dest="wait_until",
                   choices=["networkidle", "load", "domcontentloaded"], default=None,
                   help="Condition d'arrêt de la navigation initiale (v1.22.0). Sans valeur, "
                        "shot.py garde son défaut (networkidle). 'load' pour une cible qui "
                        "n'atteint jamais le silence réseau (statistiques live, polling "
                        "continu). Prime sur la propriété racine 'wait_until' du scénario. "
                        "Propagé à shot.py.")
    p.add_argument("--ignore-tls-errors", dest="ignore_tls_errors", action="store_true",
                   help="Accepte les certificats TLS invalides (LAN dev/Step-CA). Propagé à shot.py. (v1.15.1)")
    p.add_argument("--http-credentials", dest="http_credentials", action="store_true",
                   help="Résout http_username/http_password depuis le répertoire chiffré et les injecte "
                        "au niveau du contexte navigateur pour répondre à un challenge HTTP "
                        "Basic Auth (v1.21.0). Combinable avec la propriété racine "
                        "'http_credentials: true' du scénario (OR, précédent shadow_dom). "
                        "Propagé à shot.py.")
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

    if args.version:
        print(json.dumps({"outil": "rpa.py", "version": __version__}))
        sys.exit(0)

    from lib.preflight_guide import guide_valide, erreur_guide_non_lu
    if not guide_valide(args.guide_version):
        print(json.dumps(erreur_guide_non_lu(__version__)), file=sys.stderr)
        sys.exit(1)

    if not args.scenario:
        _sortir_erreur("argument_manquant", message="--scenario est requis", exit_code=2)

    if args.sauver_verifier_reference and args.replay_verifier:
        _sortir_erreur(
            "arguments_incompatibles",
            message="--sauver-verifier-reference et --replay-verifier sont mutuellement "
                    "exclusifs — un run sauvegarde OU compare, jamais les deux.",
            exit_code=2,
        )

    chemin_scenario, essais = resoudre_chemin_scenario(args.scenario)
    if not chemin_scenario:
        _sortir_erreur(
            "fichier_introuvable",
            message=f"Scénario introuvable : {args.scenario}",
            chemins_testes=essais,
        )

    try:
        scenario = charger_scenario(chemin_scenario)
    except Exception as e:
        _sortir_erreur("scenario_invalide", message=str(e))

    # Validation contre scenarios/schema.json (lot 9.2). Bloquant si jsonschema
    # est installé et le schéma rejette ; warning unique sinon.
    _valider_schema(scenario, chemin_scenario)

    # Chaînage : inline les sous-scénarios avant toute autre opération (v1.9.2).
    actions_brutes = scenario.get("actions", [])
    actions, chainage = _aplatir_actions(actions_brutes)
    if chainage:
        # v1.19.0 — entrée racine (profondeur 0), ajoutée seulement si un
        # chaînage réel a eu lieu : un scénario sans declencher_scenario ne
        # doit produire aucun champ chainage dans le journal (additif strict).
        chainage.insert(0, {
            "scenario": os.path.basename(chemin_scenario),
            "profondeur": 0,
            "action_debut": 0,
            "action_fin": len(actions) - 1,
        })

    # Linter SoM : vérifie les id entiers avant Playwright (v1.9.2).
    _linter_som(actions, chemin_scenario)

    if args.url:
        scenario["url"] = args.url

    url = scenario.get("url")
    if not url:
        _sortir_erreur("scenario_invalide", message="Champ 'url' manquant dans le scénario")

    from urllib.parse import urlparse as _urlparse
    _scheme = _urlparse(url).scheme.lower()
    if _scheme not in {"http", "https"}:
        _sortir_erreur(
            "url_scheme_interdit",
            message=f"URL scheme '{_scheme}' interdit — seuls http et https sont acceptés. URL: {url}",
            exit_code=2,
        )

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

    # Pré-validation du répertoire chiffré (fail-fast) SANS résoudre les valeurs : on
    # vérifie l'existence du répertoire chiffré et des clés référencées, puis on passe
    # les actions avec 'depuis_secrets' INTACT à shot.py, qui résout lui-même
    # au moment de remplir. Le credential ne transite jamais par la ligne
    # de commande (§6.1 spec 35_).
    try:
        cles = []
        for a in actions:
            if a.get("valeur") == "depuis_secrets":
                cle = a.get("secret_cle")
                if not cle:
                    raise ValueError(
                        f"Action {a.get('type')!r} : 'secret_cle' requis "
                        f"quand valeur='depuis_secrets'"
                    )
                cles.append(cle)
        if cles:
            if args.secrets:
                verifier_cles_fichier(args.secrets, cles)
            else:
                verifier_cles(domaine_depuis_url(url), cles)
        # v1.21.0 — même fail-fast pour les identifiants HTTP Basic Auth,
        # avant tout lancement de Playwright. Clés dédiées en priorité, repli
        # sur username/password (miroir exact de la résolution shot.py).
        if args.http_credentials or scenario.get("http_credentials"):
            try:
                if args.secrets:
                    verifier_cles_fichier(args.secrets, ["http_username", "http_password"])
                else:
                    verifier_cles(domaine_depuis_url(url), ["http_username", "http_password"])
            except (KeyError, SecretsFermesError) as e:
                if isinstance(e, SecretsFermesError):
                    raise
                if args.secrets:
                    verifier_cles_fichier(args.secrets, ["username", "password"])
                else:
                    verifier_cles(domaine_depuis_url(url), ["username", "password"])
    except SecretsFermesError as e:
        _sortir_erreur(
            "secrets_fermes",
            message=str(e),
            exit_code=SecretsFermesError.CODE_SORTIE,
            code_sortie_recommande=SecretsFermesError.CODE_SORTIE,
        )
    except (FileNotFoundError, KeyError, ValueError) as e:
        _sortir_erreur("secrets_erreur", message=str(e))

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
        # v1.18.0 — nom de fichier (sans chemin) pour mode_conseille /
        # dernier_diagnostic_host. Pas de --guide-version à propager ici :
        # le marqueur ~/.config/diwall/guide_state.json déjà validé par le
        # garde-fou de rpa.py ci-dessus est visible du subprocess shot.py
        # (même environnement, même utilisateur OS — env=os.environ.copy()
        # plus bas).
        "--source-scenario", os.path.basename(chemin_scenario),
    ]
    if chainage:
        # v1.19.0 — plomberie interne vers lib/journal.py, comme
        # --source-scenario ci-dessus. Absent si le scénario n'a pas chaîné.
        cmd += ["--chainage", json.dumps(chainage)]
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
        _sortir_erreur(
            "arguments_incompatibles",
            message="--auth-indicator-negative requiert un auth_indicator "
                    "(clé 'auth_indicator' du scénario) — sans lui, l'indicateur "
                    "négatif est ignoré silencieusement",
            exit_code=2,
        )
    if auth_indicator:
        cmd += ["--auth-indicator", auth_indicator]
    if args.shadow_dom or scenario.get("shadow_dom"):
        cmd.append("--shadow-dom")
    if args.som_rafraichir or scenario.get("som_rafraichir"):
        cmd.append("--som-rafraichir")
    if args.ignorer_waf or scenario.get("ignorer_waf"):
        cmd.append("--ignorer-waf")
    if auth_indicator_negative:
        cmd += ["--auth-indicator-negative", auth_indicator_negative]
    if args.mode:
        cmd += ["--mode", args.mode]
    if args.stealth:
        cmd.append("--stealth")
    # v1.22.0, Axe D — l'argument CLI prime sur la propriété racine du scénario
    # (et non un OR comme shadow_dom/http_credentials : ces deux-là sont des
    # booléens d'activation, celui-ci porte une valeur, deux valeurs ne
    # s'additionnent pas). Absent des deux côtés : shot.py garde son défaut.
    wait_until = args.wait_until or scenario.get("wait_until")
    if wait_until:
        cmd += ["--wait-until", wait_until]
    if args.http_credentials or scenario.get("http_credentials"):
        cmd.append("--http-credentials")
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

    # ── Mise à jour du checkpoint (v1.17.0, item 2 ; v1.17.2, plafond) ────────
    if args.checkpoint and sortie is not None:
        plafond_atteint = (sortie.get("respect") or {}).get("plafond_atteint")
        if result.returncode == 0 and not plafond_atteint:
            # Tronçon restant entièrement exécuté — plus rien à reprendre.
            if os.path.isfile(args.checkpoint):
                os.remove(args.checkpoint)
        else:
            # v1.17.2 (FR-80) : un plafond de navigation atteint retourne
            # succes: true / exit 0 comme un tronçon terminé — sans ce test
            # explicite, le checkpoint était supprimé à tort et la progression
            # perdue, alors qu'il restait des actions à exécuter.
            if plafond_atteint:
                delta = (sortie.get("respect") or {}).get("actions_executees")
            else:
                delta = sortie.get("actions_executees_avant_echec")
            if delta is not None:
                n_avant = 0
                if reprise_checkpoint:
                    with open(args.checkpoint, encoding="utf-8") as f:
                        n_avant = json.load(f).get("actions_completees", 0)
                # 0600 explicite (audit 06/08/2026, E-09) : le checkpoint
                # divulgue le chemin du fichier de session ; l'écriture à
                # l'umask par défaut (souvent 644) le rendait lisible par
                # d'autres comptes du système.
                fd = os.open(args.checkpoint, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({
                        "actions_completees": n_avant + delta,
                        "session_file": checkpoint_session_file,
                    }, f, ensure_ascii=False, indent=2)
                print(
                    f"⚠ checkpoint mis à jour : {n_avant + delta} action(s) "
                    f"préservée(s) — relancer la même commande pour reprendre.",
                    file=sys.stderr,
                )
            # Sinon (échec avant tout executer_actions, ex. répertoire chiffré fermé) :
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
                _sortir_erreur("reference_illisible", message=str(e))
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
            _echouer_assertion(
                f"Assertion impossible action #{idx} : aucune évaluation retournée par shot.py"
            )

        valeur_obtenue = ev.get("valeur")

        if "attendu" in action:
            if valeur_obtenue != action["attendu"]:
                _echouer_assertion(
                    f"Assertion échouée action #{idx} (evaluer) :\n"
                    f"  script  : {ev.get('script')}\n"
                    f"  attendu : {json.dumps(action['attendu'], ensure_ascii=False)}\n"
                    f"  obtenu  : {json.dumps(valeur_obtenue, ensure_ascii=False)}"
                )

        elif "contient" in action:
            _verifier_valeur_str(idx, ev, valeur_obtenue, "contient")
            if action["contient"] not in valeur_obtenue:
                _echouer_assertion(
                    f"Assertion échouée action #{idx} (evaluer) :\n"
                    f"  script   : {ev.get('script')}\n"
                    f"  contient : {json.dumps(action['contient'], ensure_ascii=False)}\n"
                    f"  obtenu   : {json.dumps(valeur_obtenue, ensure_ascii=False)}"
                )

        elif "motif" in action:
            import re
            _verifier_valeur_str(idx, ev, valeur_obtenue, "motif")
            if not re.search(action["motif"], valeur_obtenue):
                _echouer_assertion(
                    f"Assertion échouée action #{idx} (evaluer) :\n"
                    f"  script : {ev.get('script')}\n"
                    f"  motif  : {json.dumps(action['motif'], ensure_ascii=False)}\n"
                    f"  obtenu : {json.dumps(valeur_obtenue, ensure_ascii=False)}"
                )

    sys.exit(0)


if __name__ == "__main__":
    main()
