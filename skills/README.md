# Skills — Mémoire procédurale Diwall (v1.6.0)

Un **skill** est un scénario promu : un parcours qui a réussi en conditions réelles
et a été extrait du journal pour être rejoué sans réanalyser l'interface.

## Format

Un skill est un fichier JSON au même format qu'un scénario `scenarios/*.json` :

```json
{
  "nom": "connexion_sillage",
  "description": "Connexion admin Sillage depuis la page de login",
  "url": "https://sillage.ike4.local/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 2}
  ]
}
```

Les champs `description` et `nom` sont requis pour distinguer un skill d'un scénario jetable.

## Créer un skill depuis le journal

Après un run réussi, récupérer son `operation_id` dans le journal :

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible mon-app.local --limite 5
```

Puis exporter :

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --exporter-skill a1b2c3d4e5f6 \
  --nom connexion_sillage
```

Le fichier `skills/connexion_sillage.json` est créé et peut être rejoué via `rpa.py`.

## Rejouer un skill

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/skills/connexion_sillage.json --som
```

## Règles

- Un skill ne contient jamais de credentials en clair — toujours `"valeur": "depuis_vault"`.
- Les IDs SoM ne sont valables que si l'interface n'a pas changé depuis la validation.
- Ajouter `derniere_validation` (date ISO) dans le JSON lors des rejeux réussis.
