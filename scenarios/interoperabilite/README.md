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

## Fixture Basic Auth (`--http-credentials`, v1.21.0)

`scenario_basicauth.json` cible un serveur Python minimal
(`fixture/serveur_basicauth.py`) qui émet un vrai challenge HTTP Basic Auth
(RFC 7617, `WWW-Authenticate: Basic`) — aucune dépendance réseau externe,
comportement déterministe. Identifiants attendus (non sensibles, fixture
locale uniquement) : `diwall_fixture` / `diwall_fixture_password`.

```bash
# 1. Lancer le serveur de fixture (tourne pendant toute la durée du test)
python3 scenarios/interoperabilite/fixture/serveur_basicauth.py &

# 2. Créer le fichier d'identifiants de la fixture (clés fixes http_username/http_password)
#    DANS un point de montage FUSE actif (le répertoire chiffré gocryptfs de l'opérateur) —
#    /tmp est un tmpfs mais _repertoire_est_monte() restreint T1 aux montages FUSE
#    uniquement (lib/repertoire_chiffre.py), tmpfs est donc refusé malgré la mention dans
#    le message d'erreur (vérifié en conditions réelles, 15/07/2026).
cat > ~/Vaults/<REPERTOIRE_MONTE>/diwall_fixture_identifiants.json <<'EOF'
{"http_username": "diwall_fixture", "http_password": "diwall_fixture_password"}
EOF

# 3. Lancer le scénario
cd /opt/diwall
venv/bin/python3 rpa.py --scenario scenarios/interoperabilite/scenario_basicauth.json \
  --secrets ~/Vaults/<REPERTOIRE_MONTE>/diwall_fixture_identifiants.json --guide-version 1.0

# Vérifications attendues dans la sortie JSON :
#   succes: true
#   boussole.http_credentials_actif: true
#
# Contre-épreuve (sans --http-credentials, éditer temporairement le scénario
# pour retirer "http_credentials": true) : le serveur renvoie 401,
# boussole.http_auth_requise: true, l'assertion 'contient' échoue (succes: false).
```
