# Fixtures d'interopérabilité (v1.18.0)

Corpus minimal de non-régression structurelle pour `--replay-verifier`
(v1.17.0) — deux cibles stables, choisies pour ne jamais dériver
indépendamment de Diwall :

- `scenario_example_com.json` — témoin neutre, cible publique triviale.
- `scenario_fixture_locale.json` — fixture HTML locale (`fixture/`),
  contrôlée à 100 % par Diwall : iframe imbriqué (`iframe_chemin`, v1.18.0),
  Shadow DOM ouvert, formulaire.

Pas les 23 sites du benchmark stealth (v1.16.0) — choisis pour la diversité
WAF, pas pour la stabilité structurelle. Les réutiliser ici rendrait cette
suite friable pour une mauvaise raison (une refonte tierce imprévisible).

## Lancer la fixture locale

```bash
python3 -m http.server 8642 --directory ~/git/Diwall/Diwall/scenarios/interoperabilite/fixture/
```

Le serveur doit tourner pendant toute la durée des commandes ci-dessous.

## Créer les références (une fois)

```bash
cd /opt/diwall
venv/bin/python3 rpa.py --scenario scenarios/interoperabilite/scenario_example_com.json \
  --sauver-verifier-reference scenarios/interoperabilite/ref_example_com.json

venv/bin/python3 rpa.py --scenario scenarios/interoperabilite/scenario_fixture_locale.json \
  --sauver-verifier-reference scenarios/interoperabilite/ref_fixture_locale.json
```

## Rejouer (non-régression)

```bash
venv/bin/python3 rpa.py --scenario scenarios/interoperabilite/scenario_example_com.json \
  --replay-verifier scenarios/interoperabilite/ref_example_com.json

venv/bin/python3 rpa.py --scenario scenarios/interoperabilite/scenario_fixture_locale.json \
  --replay-verifier scenarios/interoperabilite/ref_fixture_locale.json
```

`exit 0` + silence = stable. `exit 1` + verdict JSON sur stderr = régression
(diff détaillé). Les fichiers `ref_*.json` ne sont pas versionnés (générés
localement) — voir `.gitignore`.
