# Diwall — Règles de démarrage pour Claude Code

Ce fichier est lu automatiquement à chaque ouverture de session Claude Code
dans ce répertoire. Ces règles sont **non négociables**.

---

## Règle n°1 — Pré-vol obligatoire avant toute manipulation Diwall

**Avant d'exécuter la moindre commande impliquant shot.py, rpa.py, watch.py,
vault.py, ou tout fichier sous `/opt/diwall/` ou `~/git/Diwall/` :**

```bash
cat /opt/diwall/docs/GUIDE_LLM.md
```

Lire cet index en entier (≤250 lignes). Puis, selon la tâche, charger
la notice correspondante :

```bash
# Timeout cliquer, SoM, dialogs CSS/showModal, assertions evaluer, DOM mutations :
cat /opt/diwall/docs/GUIDE_LLM_INTERACTIONS.md

# Vault, --secrets, SPA, sessions, MFA, auth_indicator, --no-capture :
cat /opt/diwall/docs/GUIDE_LLM_SESSIONS.md

# watch.py, pixel diff, opérations longues, --screenshot-timeout, journal :
cat /opt/diwall/docs/GUIDE_LLM_MONITORING.md
```

**Pourquoi c'est non négociable :**
Diwall n'est pas dans le corpus d'entraînement du modèle. Sans cette lecture,
le LLM improvise : il réinvente du scraping curl, il extrait des credentials
en clair dans le shell, il utilise les mauvaises primitives. Cela a eu lieu en
session 19 (09/06/2026) et a causé une violation de sécurité documentée.

---

## Règle n°2 — Interdiction absolue d'extraction de credentials en shell

Les formes suivantes sont **interdites** :

```bash
# INTERDIT — expose le mot de passe dans l'environnement shell et /proc
PASS=$(jq -r '.password' ~/Vaults/.../fichier.json)
USER=$(jq -r '.username' ~/Vaults/.../fichier.json)

# INTERDIT — le mot de passe transite en clair dans la ligne de commande
curl -d "password=$PASS" https://...
```

**Forme correcte — vault résolu par shot.py à l'intérieur de Playwright :**

```json
[
  {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "username"},
  {"type": "remplir_som", "id": 3, "valeur": "depuis_vault", "vault_cle": "password"},
  {"type": "cliquer_som", "id": 5},
  {"type": "attendre_selecteur_present", "selecteur": ".user-logged-in"}
]
```

Le vault est lu par `lib/vault.py` à l'intérieur du processus Playwright.
Les valeurs ne transitent jamais dans le shell, dans les logs de processus,
ni dans l'historique bash.

---

## Règle n°3 — Utiliser Diwall, pas curl

Toute tâche d'authentification, de navigation, de lecture de page web
**doit passer par shot.py ou rpa.py**. Jamais par curl, wget, lynx, ou
un script d'extraction HTML maison.

Diwall donne des yeux (captures PNG + SoM + a11y) et des mains (actions
Playwright) au LLM. L'utiliser comme prévu, pas l'ignorer.

---

## Règle n°4 — Piège `attendre_url` (FR-55)

`attendre_url` utilise une correspondance partielle (`contains`).
Le motif `/control/` correspond **immédiatement** à l'URL `/control/login/`
sans attendre la navigation post-login.

**Toujours utiliser `attendre_selecteur_present` après un submit de formulaire :**

```json
{"type": "attendre_selecteur_present", "selecteur": ".element-present-apres-login"}
```

---

## Règle n°5 — `--actions` (fichier) et `--reprendre-session` (FR-54)

**Corrigé en v1.8.0** — les deux modes sont désormais symétriques.

En mode `--reprendre-session`, `--actions /fichier.json` **et** `--action '[{...}]'` (inline)
sont tous les deux supportés. Avant v1.8.0, `--actions` était silencieusement ignoré.

Si vous utilisez une version antérieure à v1.8.0, vérifiez avec `grep __version__ /opt/diwall/shot.py`.
