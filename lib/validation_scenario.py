"""
validation_scenario.py — validation d'un scénario Diwall contre scenarios/schema.json.

Pourquoi ce fichier existe :
    G-29 (CHANTIER_SANITISATION.md, LOT 5, audit 07/08/2026) : rpa.py valide
    tout scénario chargé depuis un fichier contre scenarios/schema.json avant
    tout lancement de Playwright ; shot.py invoqué directement (--actions,
    hors rpa.py) ne validait rien — un scénario malformé n'était détecté
    qu'au moment où Playwright échouait dessus, avec un message Playwright
    générique au lieu du diagnostic structuré du schéma.

    Fonction pure (pas de print/sys.exit), volontairement distincte de
    rpa.py:_valider_schema qui reste une implémentation CLI (stderr +
    sys.exit(1), déjà testée et committée en LOT 3/G-21). Les deux
    partagent la dépendance jsonschema et le fichier de schéma, pas encore
    le même code — une factorisation complète des deux est un chantier
    séparé, hors périmètre de ce lot.
"""
import json
import os

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scenarios", "schema.json",
)


class SchemaAbsent(Exception):
    """jsonschema n'est pas installé — dépendance déclarée manquante de requirements.txt."""


def valider_schema_scenario(scenario):
    """Valide `scenario` (dict {url, actions: [...]}) contre scenarios/schema.json.

    Lève ValueError si le scénario ne respecte pas le schéma, SchemaAbsent si
    jsonschema n'est pas installé (LOT 3, G-21 : fail dur, pas un mode dégradé).
    Ne fait rien si scenarios/schema.json est introuvable — même mode dégradé
    silencieux que rpa.py (schéma optionnel, pas une dépendance obligatoire).
    """
    try:
        import jsonschema
    except ImportError:
        raise SchemaAbsent(
            "jsonschema absent — installation cassée (dépendance déclarée de "
            "requirements.txt). Installer via : "
            "/opt/diwall/venv/bin/pip install jsonschema"
        )
    if not os.path.isfile(_SCHEMA_PATH):
        return
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    try:
        jsonschema.validate(instance=scenario, schema=schema)
    except jsonschema.ValidationError as e:
        chemin_champ = " → ".join(str(p) for p in e.absolute_path) or "(racine)"
        hint = ""
        if not e.absolute_path and "is not of type" in e.message:
            hint = ' — attendu : objet {"url": "...", "actions": [{"type": "...", ...}, ...]}'
        raise ValueError(f"Scénario invalide (champ {chemin_champ}) : {e.message}{hint}")
