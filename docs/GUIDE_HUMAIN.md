# Diwall — Guide opérateur humain

Version 1.1 — June 2026

---

## Pourquoi Diwall — ce que vous déléguez réellement

### Le problème que Diwall résout

Quand vous travaillez avec un LLM sur une application web, il se produit une asymétrie
de perception : le modèle lit le code, exécute les commandes, constate les sorties
textuelles — mais il ne voit pas l'interface que vos utilisateurs voient. Vous, si.

Cette asymétrie crée une forme d'anxiété spécifique : vous ne savez pas si ce que
le modèle vous décrit correspond à ce que vous verriez dans un navigateur. Pour être
sûr, vous devez soit lui faire confiance sur parole, soit vérifier vous-même.

Diwall résout ce problème en créant un **référentiel visuel partagé** :
le modèle capture l'interface avec un navigateur réel (Chromium headless),
et vous avez accès aux mêmes captures PNG et aux mêmes arbres d'accessibilité.
Vous ne prenez plus le modèle sur parole — vous constatez le même état que lui.

### Ce que vous déléguez

Diwall vous permet de déléguer la **vérification visuelle répétitive et anxiogène** :

- Vérifier que 20 pages d'un site s'affichent correctement après un déploiement
- Confirmer qu'un formulaire de connexion fonctionne sur la bonne interface
- S'assurer qu'un déploiement n'a pas cassé l'affichage d'une vue critique
- Valider visuellement qu'une correction est bien visible à l'écran

Sans Diwall, ces vérifications vous incombent. Avec Diwall, le modèle les effectue
et vous en rapporte le résultat — avec preuve visuelle à l'appui.

### Ce que vous conservez

Vous conservez **la validation de sens de haut niveau** : décider si le résultat
que le modèle vous présente est acceptable, cohérent avec vos attentes, conforme
à ce que vos utilisateurs doivent voir. Cette décision-là reste la vôtre.

### Quand Diwall est pertinent

| Cas d'usage | Diwall adapté ? |
|---|---|
| Validation visuelle post-déploiement | ✓ Oui |
| Diagnostic d'un affichage cassé | ✓ Oui |
| Navigation et saisie dans un formulaire (~30 s max) | ✓ Oui |
| Délégation de vérifications répétitives | ✓ Oui |
| Opération serveur longue (clonage ~2–5 min) | ✗ Non — timeout Playwright |
| Suppression ou mutation en lot | ✗ Non — préférer un appel API direct |
| Workflow avec besoin de rollback | ✗ Non — Diwall ne peut pas annuler |

Pour les cas déconseillés, voir `docs/GUIDE_LLM.md` section "When NOT to use Diwall"
(frictions FR-59 et FR-60 documentées).

---

**Ce document est destiné aux opérateurs humains qui utilisent Diwall.**

Il complète le `GUIDE_LLM.md` (destiné aux modèles) avec des exemples concrets,
des procédures pas-à-pas, et des rappels sur les points qui font trébucher.

---

## Prérequis avant de démarrer

```bash
# 1. Vérifier que Diwall répond
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --som --a11y
# → doit retourner {"succes": true, ...}

# 2. Vérifier que le vault est monté (si gocryptfs)
ls ~/Vaults/Diwall/
# → doit afficher les fichiers .json, pas le contenu chiffré

# 3. Vérifier les credentials d'un domaine
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.vault import lire_credential
print('OK' if lire_credential('target.local', 'password') else 'VIDE')
"
```

---

## Configuration du vault par projet

Chaque projet peut avoir son propre vault. Deux méthodes :

**Méthode 1 — Variable d'environnement directe (one-shot) :**
```bash
DIWALL_VAULT_DIR=~/Vaults/MonProjet \
  /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

**Méthode 2 — Fichier `.diwall.conf` projet (recommandé pour un projet récurrent) :**
```bash
# Créer le fichier à la racine du projet
echo '{"vault_dir": "../MonProjet-vault"}' > ~/git/MonProjet/.diwall.conf

# Puis prefix à chaque invocation (ou export en début de session shell)
export DIWALL_CONF=~/git/MonProjet/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

Le `vault_dir` dans `.diwall.conf` peut être un chemin relatif — il est résolu
par rapport à l'emplacement du fichier `.diwall.conf`.

---

## Capturer une page et l'analyser

```bash
# Capture simple
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y

# Lire le résultat (chemin de la capture dans le JSON)
# La capture PNG est dans /tmp/diwall/capture_<ts>.png
```

**Ce que vous obtenez :**
- `capture` : chemin du PNG de la page telle qu'elle s'affiche
- `capture_som` : PNG annoté avec les numéros des éléments cliquables
- `a11y_tree` : structure de la page en texte (titres, champs, boutons)

---

## Automatiser un formulaire de connexion

**Étape 1** — Préparer les credentials dans le vault.

Le fichier vault se nomme `<hostname>.json` où `hostname` = résultat de
`urlparse(url).hostname`. Pour `https://app.example.com/`, le fichier est
`app.example.com.json`.

```json
{"username": "admin@example.com", "password": "my-secret"}
```

**Étape 2** — Explorer la page de login.
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ --som --a11y
```
Ouvrir le PNG annoté (`capture_som`) pour identifier les IDs SoM des champs.

**Étape 3** — Écrire le scénario.
```bash
cat > /tmp/login.json << 'EOF'
{
  "nom": "app_login",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "apres-login"}
  ]
}
EOF
```

**Étape 4** — Exécuter.
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /tmp/login.json --som
```

---

## Valider plusieurs pages en une seule invocation

Pour vérifier N pages d'un site authentifié sans rejouer le login à chaque fois :

```bash
cat > /tmp/audit.json << 'EOF'
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "naviguer",     "url": "https://app.example.com/dashboard/"},
    {"type": "capturer",     "nom": "dashboard"},
    {"type": "naviguer",     "url": "https://app.example.com/settings/"},
    {"type": "capturer",     "nom": "settings"}
  ]
}
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/audit.json --som
```

---

## Extraire une valeur de la page

Pour lire un texte, un compteur ou n'importe quelle valeur du DOM :

```bash
cat > /tmp/extract.json << 'EOF'
[{"type": "evaluer", "script": "document.title"}]
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --actions /tmp/extract.json
# → résultat dans evaluations[0].valeur
```

**Important** : toujours écrire les scripts JS dans un fichier `--actions`,
jamais en inline avec `--action` (le shell casse les guillemets imbriqués).

---

## Mettre en place une surveillance visuelle

```bash
# 1. Sauvegarder la référence visuelle
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --nom accueil

# 2. Comparer ultérieurement (pixel diff)
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ \
  --comparer-pixel /opt/diwall/references/target.local_accueil/reference.png \
  --nom accueil
# → verdict : stable / drift / regression (exit code 0 ou 1)

# 3. Sur une page authentifiée : capturer d'abord avec rpa.py, puis enregistrer
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/login.json > /tmp/out.json
CAPTURE=$(python3 -c "import json; d=json.load(open('/tmp/out.json')); print(d['captures_intermediaires'][-1])")
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --capture "$CAPTURE" --nom dashboard
```

---

## Points d'attention courants

| Situation | Ce qu'il faut faire |
|---|---|
| `FileNotFoundError` sur le vault | Vérifier que le fichier JSON est nommé avec le FQDN complet (`urlparse(url).hostname`) |
| `VaultFermeError` (exit 42) | Monter le vault : `bash scripts/mount-vault.sh` |
| JSON invalide dans la sortie | Utiliser `2>/dev/null \| tail -1` pour extraire uniquement la ligne JSON |
| Les IDs SoM sont différents d'une session à l'autre | Normal — les IDs SoM sont recalculés à chaque capture. Ne jamais les réutiliser cross-session |
| Login suivi d'une redirection Django vers le dashboard | Ne pas utiliser `naviguer` dans une session reprise Django — passer l'URL via `--url` |
| Formulaire `<select>` non rempli | Utiliser `remplir_som` (pas `remplir`) avec l'ID SoM du `<select>` |
| Clic sans effet sur un bouton hors viewport | Ajouter `{"type":"defiler","selecteur":"#le-bouton"}` avant le clic |

---

## Désinstaller Diwall

Le script `scripts/uninstall.sh` supprime l'installation proprement, dans l'ordre inverse
de `install.sh`.

```bash
# Voir ce qui sera supprimé, sans rien faire
bash scripts/uninstall.sh --dry-run

# Désinstallation complète (confirmation interactive)
bash scripts/uninstall.sh

# Sans confirmation (tests à froid, réinstallation enchaînée)
bash scripts/uninstall.sh --confirme && bash scripts/install.sh
```

**Ce qui est supprimé :**

| Élément | Détail |
|---|---|
| `/opt/diwall/` | Code, venv Python, configuration |
| `/var/log/diwall/` | Journaux d'opérations |
| Utilisateur système `diwall` | Créé exclusivement pour Diwall |
| Groupe système `diwall` | Idem |
| Appartenance au groupe | Votre compte est retiré du groupe `diwall` |
| Hook git pre-push | `core.hooksPath` désactivé dans le dépôt source |

**Ce qui n'est jamais touché :**
- `~/Vaults/` — vos coffres de credentials
- `~/git/Diwall/` — les sources git
- Le cache navigateur Playwright (`~/.cache/ms-playwright/`)

**Captures de preuves (`/var/log/diwall/preuves/`) :** si le répertoire contient des
captures, il est conservé par défaut avec un avertissement. Pour le supprimer :

```bash
bash scripts/uninstall.sh --confirme --purge-preuves
```

---

## Consulter l'historique des opérations

```bash
# Toutes les opérations sur une cible
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local

# Opérations mutantes uniquement (clics, saisies)
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --mutatif

# Depuis une date
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local \
  --depuis 2026-06-01
```
