# Diwall — Manuel d'utilisation

**Version 1.23.0 — Août 2026**

*Également disponible en français, allemand et espagnol sous `docs/fr/`, `docs/de/` et `docs/es/`.*

Ce document répond à une seule question : **comment réaliser X avec Diwall**.

**Si vous êtes un utilisateur** — aucune commande n'est nécessaire. Indiquez à votre modèle ce que vous souhaitez visiter, observer ou accomplir sur un site web, une application web ou une interface d'administration.
Le modèle lit ce manuel et traduit votre intention en actions appropriées.

**Si vous êtes un modèle de langage** — voici vos commandes. Exécutez-les directement.

Ne pas inclure de descriptions architecturales. Fournir uniquement les commandes qui fonctionnent.

---

## Sommaire

1. [Vérifier l'installation](#1-vérifier-linstallation)
2. [Capturer une page](#2-capturer-une-page)
3. [Navigation Respectueuse (v1.15.0)](#3-navigation-respectueuse-v1150)
4. [Répertoire chiffré et identifiants](#4-répertoire-chiffré-et-identifiants)
5. [Écrire et exécuter un scénario RPA](#5-écrire-et-exécuter-un-scénario-dautomatisation-robotisée-rpa)
6. [Actions — référence complète](#6-actions--référence-complète)
7. [Gérer les obstacles courants](#7-gérer-les-obstacles-courants)
8. [Surveillance visuelle — watch.py](#8-surveillance-visuelle--watchpy)
9. [Journal des opérations](#9-journal-des-opérations)
10. [Options de ligne de commande — référence](#10-options-de-ligne-de-commande--référence)
11. [Codes de sortie et résultats](#11-codes-de-sortie-et-résultats)

---

## 1. Vérifier l'installation

```bash
# Vérification la plus simple possible – sans Playwright, sans URL, sortie immédiate avec le code 0 (v1.18.0+).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --version
# → {"outil": "shot.py", "version": "1.23.0"}
```

```bash
# Test complet en une seule commande (environ 3 secondes).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --mode fast --guide-version 1.2
```

Résultat attendu : du JSON sur stdout avec `"succes": true`.

**`--guide-version` (v1.18.0+):** `shot.py`, `rpa.py`, et `watch.py` refusent de
fonctionner sans cela — sauf si un marqueur local provenant d'un appel accepté précédemment existe déjà (`~/.config/diwall/guide_state.json`). La valeur est la
`<!-- notice-version: X.Y -->` sur la ligne 3 de `docs/GUIDE_LLM.md` — et non le
numéro de version de Diwall. Consultez la version actuelle plutôt que de vous fier à une valeur quelconque mentionnée ici : `grep notice-version /opt/diwall/docs/GUIDE_LLM.md`. Reportez-vous à la section "Vérifications préalables obligatoires" de
`docs/GUIDE_LLM.md` pour comprendre le mécanisme complet et le format des erreurs si vous l'omettez.

Une fois le marqueur existant, ``--guide-version`` redevient optionnel — chaque autre exemple de commande dans ce manuel l'omet délibérément, car un marqueur provenant d'un appel précédent réussi les couvre déjà, tant que ``docs/GUIDE_LLM.md`'s `notice-version`` n'a pas changé depuis.

```bash
# Vérifiez la version installée.
grep "__version__" /opt/diwall/shot.py
# → __version__ = "1.23.0"

# Vérifiez que `playwright-stealth` est disponible (version v1.15.0).
/opt/diwall/venv/bin/python3 -c "import playwright_stealth; print('stealth OK')"

# Vérifiez que le répertoire chiffré est monté.
ls ~/Vaults/__PROJET__/Diwall/
# → doit afficher les fichiers .json, et non une liste vide.
```

Si `ls ~/Vaults/...` renvoie une liste vide ou une erreur :
→ montez-le : `bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh`

### 1a. Installation à partir du paquet Debian : la méthode la plus simple

Le `.deb` est un dépôt sur GitHub. C'est le canal recommandé, sauf si vous avez l'intention de modifier le code propre de Diwall, auquel cas, voir 1b. Les deux canaux sont mutuellement exclusifs sur une seule machine : ils ciblent tous les deux `/opt/diwall/`.

```bash
sudo apt install ./diwall_1.23.0-1_all.deb
diwall-shot --version
man diwall
```

L'installation de `.deb` nécessite un accès réseau (l'installation des dépendances et le téléchargement de Chromium se déroulent pendant `postinst`). Six commandes sont disponibles, chacune étant une simple enveloppe — sans différence fonctionnelle par rapport aux propres invocations du canal git-clone :

| Commande | Enveloppe |
|---|---|
| `diwall-shot` | `shot.py` |
| `diwall-rpa` | `rpa.py` |
| `diwall-watch` | `watch.py` |
| `diwall-monter-secrets` | `scripts/monter-repertoire-chiffre.sh` |
| `diwall-demonter-secrets` | `scripts/demonter-repertoire-chiffre.sh` |
| `diwall-monitor-verifier` | `scripts/monitor-verifier.sh` |

La configuration se trouve à un chemin différent dans ce canal :
`/etc/diwall/diwall.conf` (et non `/opt/diwall/diwall.conf`) — un modèle est
placé à `/etc/diwall/diwall-sample.conf`, et n'est jamais activé automatiquement :

```bash
sudo cp /etc/diwall/diwall-sample.conf /etc/diwall/diwall.conf
sudo nano /etc/diwall/diwall.conf
sudo usermod -aG diwall $USER
```

`apt remove diwall` conserve `/var/log/diwall/` (journal des opérations, preuves)
inchangés — `apt purge diwall` supprime également cela. `~/Vaults/` n'est jamais modifié par
l'un ou l'autre, sur les deux canaux.

**Page de manuel (v1.22.0):** `man diwall` documente les six commandes sur une seule page. Les cinq autres noms de commandes (`man diwall-rpa`, etc.) renvoient à la même page. Elle est générée à partir de `debian/diwall.1.md` au moment de la compilation, elle ne peut donc pas devenir obsolète sans avertissement, mais pour la liste exhaustive des options de toute commande, `--help` reste la source d'information privilégiée par rapport à la page de manuel.

### 1b. Installation à partir du code source – pour modifier Diwall lui-même

N'utilisez ce canal que si vous comptez modifier le code de Diwall lui-même :
il place le dépôt là où `deploy.sh` peut pousser vos changements vers
`/opt/diwall/`. Pour un usage simple, le `.deb` ci-dessus tient en une commande
et fait le même travail.

```bash
# 1. Créer un utilisateur système et un répertoire.
sudo useradd --system --no-create-home --shell /bin/false diwall
sudo mkdir -p /opt/diwall
sudo chown root:diwall /opt/diwall

# 2. Cloner le dépôt.
git clone https://github.com/ronandavalan/diwall.git ~/git/Diwall/Diwall
cd ~/git/Diwall/Diwall

# 3. Créer un environnement virtuel Python.
sudo /usr/bin/python3 -m venv /opt/diwall/venv
sudo /opt/diwall/venv/bin/pip install -r requirements.txt

# 4. Installer Chromium.
sudo /opt/diwall/venv/bin/playwright install chromium

# 5. Déployer.
bash ~/git/Diwall/Diwall/scripts/deploy.sh

# 6. Créez votre répertoire de clés chiffrées.
mkdir -p ~/Vaults/<your-project>/Diwall
# Créez le fichier `~/Vaults/<votre_projet>/Diwall/<nom_d'hôte>.json` avec vos identifiants.
```

Sur ce canal, la configuration est `/opt/diwall/diwall.conf`, et non
`/etc/diwall/diwall.conf`. Désinstallez avec
`bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run` en premier, puis sans
l'indicateur.

**Construction du paquet (responsable) :**

```bash
bash ~/git/Diwall/Diwall/scripts/construire-paquet.sh
```

Construit puis archive les trois artefacts (`.deb`, `.buildinfo`, `.changes`)
sous `~/git/Diwall/paquets/<version>/`. Toutes les versions sont conservées : le
`.buildinfo` est la seule trace de l'environnement exact dans lequel un paquet a été construit, et il ne vaut rien s'il n'est pas conservé.

---

## 2. Capturer une page

### 2a. Capture rapide – texte uniquement, sans image PNG (~2 secondes)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
```

Retourne : `a11y_tree` (structure du texte de la page), `boussole` (URL effective, titre).
Utilisez ceci lorsque vous voulez lire le titre, vérifier l'URL ou extraire du texte sans capturer une image PNG.

### 2b. Capture visuelle complète avec éléments numérotés

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
```

Retourne :
- `capture`: chemin vers l'image PNG de la page
- `capture_som`: image PNG avec des numéros sur les éléments cliquables (SoM)
- `elements_som`: liste JSON d'éléments (id, tag, texte)
- `a11y_tree`: arbre d'accessibilité

![Ensemble de superpositions "Marque" : chaque élément interactif est encadré et numéroté](../images/som-example-fr.png)

*Ce que `--som` produit. Les nombres dans l'image sont les valeurs de `id` dans
`elements_som`, donc cliquer devient `{"type": "cliquer_som", "id": 7}` — il n'y a pas de
sélectionneur à deviner. Généré à partir d'une version du fichier de configuration stockée dans ce dépôt
(`scenarios/interoperabilite/fixture/`); la même figure existe en français,
allemand et espagnol, ainsi qu'en anglais.*

### 2c. Lisez d'abord la boussole

Toute sortie contient un objet `boussole` — lisez-le avant tout le reste :

```json
"boussole": {
  "url_courante": "https://target.local/dashboard",
  "titre_page": "Dashboard — My App",
  "auth_status": "active",
  "stealth_actif": true,
  "respect": {
    "pages_visitees": 0,
    "actions_executees": 3,
    "duree_totale_ms": 2140
  }
}
```

Si `boussole.url_courante` ne correspond pas à ce que vous attendez : arrêtez-vous
et investiguez avant toute action mutante.

### 2d. Lire `etat` pour prendre une décision d'acceptation ou de rejet (v1.16.0)

Chaque exécution réussie inclut un objet `etat` à la racine du format JSON ; consultez-le avant toute action modifiant les données, au lieu de vérifier manuellement `auth_status`, `respect.plafond_atteint`, `erreurs_js`, et `erreurs_console` vous-même :

```json
"etat": {
  "pret_a_agir": true,
  "niveau_confiance": "eleve",
  "raisons": ["aucun signal de friction détecté"]
}
```

Si `pret_a_agir` est égal à `false`, consultez `raisons` pour connaître la cause (authentification inactive, dérive de session, limite de navigation atteinte ou blocage détecté par un pare-feu applicatif) avant de continuer.

`etat` ne vérifie pas si l'URL ou le contenu de la page correspondent à vos attentes commerciales ; utilisez `evaluer` avec `attendu`/`contient`/`motif` (section 5d) pour cela.

### 2e. `mode_conseille` — Conseils de configuration avant le vol (v1.18.0)

Si Diwall dispose de données antérieures concernant l'hôte que vous appelez — provenant d'une exécution précédente `diagnostic_dom.json`, il peut proposer une recommandation pour votre prochain appel, mais cette recommandation n'est jamais appliquée automatiquement : `etat`

```json
"etat": {
  "pret_a_agir": true,
  "niveau_confiance": "eleve",
  "raisons": ["mode_conseille disponible : full recommandé (React détecté sur ce host)"],
  "mode_conseille": {
    "mode": "full",
    "shadow_dom": true,
    "som_rafraichir": false,
    "raisons": ["react_detecte", "shadow_roots:3"]
  }
}
```

Pour obtenir ces données pour un hôte, exécutez le diagnostic une seule fois :

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url https://target.local/ --mode fast
```

Aucun diagnostic préalable pour cet hôte → `mode_conseille` est absent, jamais une
estimation. Tous les détails dans `GUIDE_LLM_MONITORING.md`.

---

## 3. Navigation Respectueuse (v1.15.0)

### 3a. Mode furtif `--stealth`

Certains sites bloquent les navigateurs sans interface graphique sur `navigator.webdriver=true`
sans examiner l'intention. `--stealth` supprime ce marqueur technique automatique.

```bash
# shot.py en direct
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --stealth

# Par rpa.py
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --stealth
```

Lorsque l'option est activée : `boussole.stealth_actif = true` dans la sortie JSON.

**Ce que `--stealth` modifie :** `navigator.webdriver` supprimé, les plugins /languages/platform normalisés.
**Ce que `--stealth` ne modifie pas :** l'adresse IP de l'opérateur, son identité ou son intention de navigation.

### 3b. Retards dus à la courtoisie

Configuré dans `/opt/diwall/diwall.conf`:

```json
{
  "secrets_dir": "~/Vaults/__PROJET__/Diwall",
  "navigation": {
    "min_action_delay_ms": 800,
    "max_pages_par_run": 10,
    "max_actions_par_run": 30
  }
}
```

`min_action_delay_ms`: délai minimal (ms) entre chaque action. Expédié.
par défaut : 800 ms.

Développement local — définissez-le sur `0` (v1.19.0) : les 800 ms par défaut protègent un utilisateur distrait lors de sa *première* exécution, *sans configuration*, contre l'accès à Internet public ; cela n'a aucune fonction de protection pour votre propre machine de développement/de production, où rien ne doit se comporter d'une manière particulière. Définissez la clé explicitement dans votre fichier local `diwall.conf` :

```json
{
  "navigation": {
    "min_action_delay_ms": 0
  }
}
```

Conservez le délai par défaut de 800 ms (ou augmentez-le) pour tout objectif atteint via Internet public. La valeur est toujours un choix conscient associé à l'objectif, et non une propriété fixe de l'outil ; consultez les directives relatives au WAF et à la furtivité dans `docs/GUIDE_LLM.md` pour le même principe appliqué au comportement de blocage.

Les limites de seuil ``max_pages_par_run`` et ``max_actions_par_run`` interrompent proprement l'exécution si elles sont dépassées. Aucune exception n'est levée ; le fichier JSON de sortie contiendra :

```json
"respect": {
  "pages_visitees": 10,
  "actions_executees": 10,
  "duree_totale_ms": 12400,
  "plafond_atteint": "max_pages_par_run"
}
```

### 3c. Indicateurs d'impact

Chaque exécution renvoie `respect` (à la racine du JSON et dans boussole) :

| Clé | Signification |
|---|---|
| `pages_visitees` | Nombre de navigations `type: naviguer` exécutées |
| `actions_executees` | Nombre total d'actions du scénario exécutées |
| `duree_totale_ms` | Durée totale de l'exécution |
| `plafond_atteint` | `"max_pages_par_run"` ou `"max_actions_par_run"` en cas d'arrêt anticipé |

### 3d. Test de performance furtif - quantitatif (v1.17.1)

Privilégiez le comptage des signaux d'empreinte digitale concrets plutôt que la comparaison visuelle de captures d'écran — c'est la méthode utilisée pour vérifier la correction de compatibilité API v1.17.0 `playwright-stealth`.
Correction de compatibilité API (`docs/RETOUR_EXPERIENCE.md` FR-79) :

```bash
# Sans discrétion.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://bot.sannysoft.com --no-capture --timeout 20000 \
  --actions '[{"type":"evaluer","script":"navigator.webdriver"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.failed\").length"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.passed\").length"}]'

# Avec discrétion.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://bot.sannysoft.com --no-capture --stealth --timeout 20000 \
  --actions '[{"type":"evaluer","script":"navigator.webdriver"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.failed\").length"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.passed\").length"}]'
```

Lisez les trois valeurs de `evaluations[].valeur` : `navigator.webdriver` doit
passer de `true` à `false`, `td.failed` doit tendre vers `0`. Mesure de
référence (correctif v1.17.0, session 47) : 12 failed → 0 failed.

Pour un deuxième avis qualitatif, le scénario fourni génère toujours des captures d'écran à examiner :

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/test_stealth.json \
  --output-dir /tmp/diwall/stealth_with --stealth
```

`capture_sannysoft_*.png` et `capture_intoli_*.png` se trouvent dans ce répertoire.
Note : les deux pages cibles traitent de la détection des robots dans leur contenu, ce qui
peut déclencher `respect.waf_bloquants` comme un faux positif (section 3e) —
ce qui est attendu pour cette référence spécifique, et non un signe d'un blocage réel.

### 3e. Signal de détection WAF (v1.16.0, version améliorée v1.17.2)

Diwall signale un blocage probable par un WAF de manière passive : HTTP 403/429, ou une correspondance de titre/mot-clé HTML (`Cloudflare`, `CAPTCHA`, `checking your browser`, etc.). Ceci est un indicateur, et non une exception ; l'exécution se termine normalement :

```json
"respect": {
  "waf_bloquants": 1
}
```

Lorsque les éléments suivants sont présents et que `> 0` est vrai: `etat.niveau_confiance` est `"faible"` et
`etat.pret_a_agir` est `false`. Décidez vous-même si vous souhaitez réessayer avec
`--stealth`, modifier la cible, ou arrêter — Diwall n'interrompt pas l'exécution pour vous.

Depuis la version v1.17.2, les noms de fournisseurs génériques (`Cloudflare`, `Akamai`) ne correspondent qu'au
titre de la page ; auparavant, ils produisaient des faux positifs pour les références ordinaires aux ressources CDN. Si un faux positif persiste, `--ignorer-waf`
dégrade `niveau_confiance` sans forcer `pret_a_agir: false`
(`boussole.waf_ignore_actif: true` enregistre le contournement).
La détection est basée sur des mots-clés et peut produire des faux positifs sur les pages qui
traitent légitimement du blocage/de la détection (par exemple, une page de référence pour la détection de robots) ; considérez cela comme un signal rapide, et non comme un verdict certain.

---

## 4. Répertoire chiffré et identifiants

### 4a. Structure

Les identifiants sont stockés dans un répertoire chiffré, un volume gocryptfs, contenant un fichier `.json` par domaine.

```
~/Vaults/__PROJET__/Diwall/
  ├── app.example.com.json         ← credentials for https://app.example.com/
  ├── admin.example.com.json       ← credentials for https://admin.example.com/
  └── operations.jsonl             ← operation log (v1.15.0)
```

Format du fichier d'identifiants :

```json
{
  "username": "admin@example.com",
  "password": "my-password"
}
```

Le nom du fichier = `urlparse(url).hostname`. Pour `https://app.example.com/login/`, créez `app.example.com.json`.

### 4b. Remplir un formulaire : la règle absolue

**INTERDIT — affiche le mot de passe dans le terminal et `/proc` :**

```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER
curl -d "password=$PASS" https://...                 # NEVER
```

**CORRECT — les identifiants sont résolus à l'intérieur de Playwright :**

```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "username"},
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Les valeurs ne transitent jamais par le shell, l'historique de bash, les journaux des processus ou aucun fichier.

### 4c. Choisir le fichier d'identifiants pour une exécution

```bash
# Répertoire d'identifiants par défaut (défini dans diwall.conf > secrets_dir).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --som

# Fichier de crédentiels explicites (--secrets).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som \
  --secrets /path/to/mounted/directory/creds.json

# Répertoire de crédentielles par projet via .diwall.conf
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --som
```

**Contenu du fichier `--secrets` — `origines_autorisees` obligatoire depuis le
05/08/2026** (rupture, sans période de compatibilité) : un fichier sans cette clé est refusé avant toute lecture.

```json
{"username": "operator", "password": "secret", "origines_autorisees": ["target.local"]}
```

`origines_autorisees` liste les noms d'hôte auxquels ce fichier peut être utilisé.
Utilisez le même format en minuscules, sans schéma et sans port que `domaine_depuis_url()`. Une lecture
d'une page dont le domaine ne figure pas dans la liste est refusée
(`SecretsOrigineNonAutoriseeError`).

Contenu de `~/git/MyProject/.diwall.conf` :

```json
{"secrets_dir": "../MyProject-secrets"}
```

Le chemin est résolu par rapport à l'emplacement de `.diwall.conf`.

### 4d. TOTP / Authentification multifacteur

```json
{"type": "remplir_som", "id": 6, "valeur": "depuis_secrets_totp"}
```

Lit la clé `totp_cle` (seed base32) depuis le fichier de crédentielles et génère le code TOTP actuel.

Pour recevoir le code via ntfy (processus sans intervention humaine) :

```json
{"type": "attendre_mfa_ntfy", "id_som": 6, "timeout": 120}
```

### 4e. Somme de contrôle d'intégrité (optionnel, v1.15.0)

Pour protéger un fichier de crédentielles contre une corruption silencieuse de FUSE, ajoutez un champ `checksum`:

```bash
# Générez la somme de contrôle.
/opt/diwall/venv/bin/python3 -c "
import json, hashlib
creds = json.load(open('my_credentials.json'))
fields = {k: creds[k] for k in sorted(['username','password']) if k in creds}
print('sha256:' + hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest())
"
```

Ajoutez la valeur retournée au fichier d'identifiants :

```json
{
  "username": "admin@example.com",
  "password": "my-password",
  "checksum": "sha256:a3f2c1..."
}
```

Si la somme de contrôle ne correspond pas, `shot.py` déclenche `SecretsChecksumError` (sortie 42) avec un message explicite.
Sans la clé `checksum`, le comportement reste inchangé (option stricte).

### 4f. Répertoire chiffré fermé : que faire ?

```
SecretsFermesError: Le répertoire chiffré Diwall est initialisé mais non monté.
```

```bash
# Montez le répertoire chiffré.
bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh

# Vérifiez le montage.
ls ~/Vaults/__PROJET__/Diwall/
# → doit afficher les fichiers JSON.
```

### 4g. Authentification HTTP Basique — `--http-credentials` (v1.21.0)

Pour les cibles situées derrière un défi d'authentification HTTP Basic au niveau du réseau (RFC 7617) —
un pare-feu qu'un proxy inverse comme Caddy, nginx ou Traefik affiche avant que n'importe quelle
page ne s'affiche, ce qui est courant devant les interfaces d'administration auto-hébergées. Il s'agit d'un
mécanisme différent de l'authentification basée sur un formulaire décrite ci-dessus
(4a-4f), qui reste entièrement prise en charge et n'est pas affectée.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://internal.example/ \
  --http-credentials --secrets ~/Vaults/__PROJET__/Diwall/internal_example.json
```

Fichier d'identifiants : la paire `username` / `password` simple déjà utilisée pour le cas courant (un seul jeu d'identifiants pour la cible) :

```json
{"username": "admin", "password": "my-password"}
```

Les clés dédiées `http_username`/`http_password` sont testées en premier et ne sont nécessaires que lorsque la même cible possède à la fois une protection Basic Auth au niveau du réseau *et* sa propre connexion d'application distincte (deux paires d'identifiants différentes dans le même fichier) — Diwall revient automatiquement aux clés `username`/`password` lorsque les clés dédiées sont absentes.

Confirmé en production contre une cible réelle protégée par Caddy : la configuration
par défaut (`send: "unauthorized"` — les identifiants sont envoyés uniquement après un véritable
code 401, et jamais de manière préventive) a résolu le problème du premier coup.
`boussole.http_credentials_actif: true` confirme un succès réel, et non pas seulement que l'indicateur est transmis ; `boussole.http_auth_requise: true` indique clairement une erreur 401 non résolue d'un blocage WAF.

---

## 5. Écrire et exécuter un scénario d'automatisation robotisée (RPA)

### 5a. Protocole en 3 étapes

**Étape 1 : Explorer la page (lecture seule)**

```bash
# Aperçu rapide.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --mode fast

# Vue complète avec éléments numérotés.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y

# Application Web Components (Angular, Lit, Stencil).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y --shadow-dom

# Inventaire enrichi du DOM (cadres, racines d'ombre, attributs de données stables).
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url https://target.local/ --mode fast
```

**Ce qu'il faut relever :**
- Les identifiants SoM des champs et des boutons (lire `capture_som`)
- Les attributs stables : `name`, `id`, `aria-label`, `data-testid`
- Les surcouches bloquantes (bandeaux de cookies, fenêtres modales)
- SPA ou rechargement HTTP complet

**Étape 2 : Écrivez le scénario.**

```json
{
  "nom": "login_app",
  "url": "https://app.example.com/login/",
  "intention": "Administrator login with stored credentials",
  "actions": [
    {"type": "nettoyer_overlay", "selecteur": ".cookie-banner"},
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".user-avatar"},
    {"type": "capturer", "nom": "after-login"}
  ]
}
```

**Étape 3 — Exécution**

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/login_app.json --som
```

### 5b. Scénario complet : se connecter et naviguer entre les pages

```json
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "intention": "Visual audit after deployment",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".dashboard-main"},
    {"type": "capturer", "nom": "dashboard"},
    {"type": "naviguer", "url": "https://app.example.com/settings/"},
    {"type": "attendre_navigation"},
    {"type": "capturer", "nom": "settings"},
    {"type": "naviguer", "url": "https://app.example.com/users/"},
    {"type": "attendre_navigation"},
    {"type": "capturer", "nom": "users"}
  ]
}
```

### 5c. Extraire des données du DOM

```json
{
  "nom": "extract_counters",
  "url": "https://app.example.com/dashboard/",
  "actions": [
    {"type": "evaluer", "script": "document.title"},
    {"type": "evaluer", "script": "document.querySelectorAll('.user-row').length"},
    {"type": "evaluer", "script": "window.location.href"}
  ]
}
```

Résultat dans `evaluations[]` :

```json
"evaluations": [
  {"index": 0, "script": "document.title", "valeur": "Dashboard — My App"},
  {"index": 1, "script": "...", "valeur": 42},
  {"index": 2, "script": "...", "valeur": "https://app.example.com/dashboard/"}
]
```

### 5d. Affirmations sur evaluer (rpa.py uniquement)

Trois clés mutuellement exclusives, une pour chaque action :

```json
{"type": "evaluer", "script": "document.querySelectorAll('.row').length", "attendu": 3}
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
{"type": "evaluer", "script": "window.location.href", "motif": "/dashboard$"}
```

| Clé | Comparaison | Types valides |
|---|---|---|
| `attendu` | égalité stricte `==` | str, int, bool |
| `contient` | sous-chaîne `in` | str uniquement |
| `motif` | `re.search()` Python | str uniquement |

Si l'assertion échoue : rpa.py s'arrête immédiatement (exit 1) avant toute action mutante ultérieure.

### 5e. Sous-scénarios (declencher_scenario)

Définissez une connexion comme un sous-scénario réutilisable :

```json
{
  "nom": "login_app",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".user-avatar"}
  ]
}
```

Appelez ce sous-scénario depuis un autre scénario :

```json
{
  "nom": "full_audit",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "declencher_scenario", "scenario": "login_app"},
    {"type": "naviguer", "url": "https://app.example.com/report/"},
    {"type": "capturer", "nom": "report"}
  ]
}
```

Profondeur maximale : 5 niveaux d'imbrication.

### 5f. Vérifiez que vous êtes sur la bonne page avant toute modification

Ajoutez toujours une protection comme première action dans les scénarios qui suppriment ou modifient des données :

```json
{"type": "evaluer", "script": "window.location.href", "contient": "/dashboard"},
{"type": "evaluer", "script": "document.querySelector('.alert-danger')?.textContent ?? null", "attendu": null}
```

Si la protection échoue : rpa.py s'arrête avant que la suppression ne soit exécutée.

### 5g. Reprendre une session (cookies persistants)

```bash
# Première invocation : authentification et sauvegarde de la session.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ \
  --actions /tmp/login.json \
  --sauver-session /tmp/diwall/session.json \
  --som

# Appels suivants — réutiliser la session (pas de nouvelle connexion).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/dashboard/ \
  --reprendre-session /tmp/diwall/session.json \
  --som
```

**Signal de dérive de session :** si la session a expiré, mettez `boussole.session_derive: true` dans le JSON.
Dans ce cas : redémarrez la connexion complète sans `--reprendre-session`.

### 5h. Non-régression structurelle sans pixels — `--replay-verifier` (v1.17.0)

```bash
# Premier lancement : enregistrez la référence structurelle.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/dashboard.json \
  --sauver-verifier-reference /tmp/dashboard.ref.json

# Exécutions suivantes — comparer.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/dashboard.json \
  --replay-verifier /tmp/dashboard.ref.json
```

Compare les résultats de `http_status`, `dom_stats`, `evaluer`, et le nombre d'éléments SoM (sans tenir compte du contenu) par rapport à la référence enregistrée. Verdict dans stderr :

```json
{"type_comparaison": "replay_verifier", "verdict": "stable", "diffs": []}
```

Exit 1 sur `verdict: "regression"`, avec `diffs` qui liste chaque champ
divergent (`reference` contre `obtenu`). Les deux options sont mutuellement
exclusives.

### 5i. Reprendre un scénario après une erreur — `--checkpoint` (v1.17.0)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/long_audit.json \
  --checkpoint /tmp/long_audit.checkpoint.json
```

Si le scénario échoue en cours de route, `/tmp/long_audit.checkpoint.json` est
écrit avec le nombre d'actions accomplies et un fichier de session. **Relancez
exactement la même commande** pour reprendre : les actions déjà accomplies sont
sautées. En cas de succès complet, le fichier de checkpoint est supprimé
automatiquement.

Une exécution interrompue par une limite de navigation (`max_actions_par_run`/`max_pages_par_run`)
est traitée de la même manière qu'un échec partiel depuis la version v1.17.2 : le point de contrôle
est mis à jour avec l'avancement réel, et n'est pas supprimé. Avant la version v1.17.2, il était
supprimé dans ce cas également (il renvoie le même signal `succes: true` qu'un tronçon
complètement terminé), entraînant silencieusement la perte de tous les progrès restants dans les scénarios longs.

L'état du DOM (modales ouvertes, formulaires partiellement remplis) n'est jamais conservé entre deux sessions. Seuls les cookies/`localStorage` et la position dans la liste des actions sont sauvegardés. Ne vous fiez pas à `--checkpoint` pour reprendre un formulaire multi-étapes au milieu ; il reprend uniquement aux limites des actions.

### 5j. Cibler les éléments à l'intérieur d'un iframe (v1.17.0)

Aucune numérotation "Set-of-Mark" ne se produit à l'intérieur d'un `<iframe>` (même origine ou origine différente) ; ciblez-le directement via un sélecteur CSS :

```json
{"type": "cliquer_iframe", "iframe_selecteur": "iframe#paiement", "selecteur": "button.valider"},
{"type": "remplir_iframe", "iframe_selecteur": "iframe#paiement", "selecteur": "input[name=cvv]", "valeur": "depuis_secrets", "secret_cle": "cvv"}
```

`remplir_iframe` prend en charge `valeur: "depuis_secrets"` exactement comme `remplir`.
(section 4b) — il n'y a jamais d'identifiants en texte clair dans ce scénario. Si l'élément cible
refuse l'interaction (par exemple, une zone `contenteditable` dans un état de lecture seule), ajoutez `"force": true` à `cliquer_iframe` — même sémantique que `cliquer`.
(section 7e).

Pour trouver le sélecteur interne : utilisez `evaluer` sur le contenu de l'iframe si celui-ci est
du même domaine (`document.querySelector('iframe').contentDocument...`), ou
consultez la structure/la documentation propre de l'application cible si elle se trouve dans un autre domaine.

### 5k. Iframes imbriquées — `iframe_chemin` (v1.18.0)

Un iframe à l'intérieur d'un autre iframe : remplacez `iframe_selecteur` par `iframe_chemin`, un tableau ordonné – un sélecteur CSS par niveau d'imbrication, de l'extérieur vers l'intérieur.

```json
{"type": "cliquer_iframe", "iframe_chemin": ["iframe#wrapper", "iframe#paiement"], "selecteur": "button.valider"},
{"type": "remplir_iframe", "iframe_chemin": ["iframe#wrapper", "iframe#paiement"], "selecteur": "input[name=cvv]", "valeur": "depuis_secrets", "secret_cle": "cvv"}
```

`iframe_selecteur` (une seule trame) et `iframe_chemin` (descente imbriquée) sont
mutuellement exclusifs : exactement un est requis par action. Pour une iframe de niveau unique, continuez d'utiliser `iframe_selecteur` (section 5j).

---

## 6. Actions — référence complète

| Type | Paramètres requis | Paramètres optionnels | Notes |
|---|---|---|---|
| `naviguer` | `url` | — | Rechargement HTTP complet. Comptabilisé dans `respect.pages_visitees` |
| `cliquer` | `selecteur` | `force` (bool), `repli_js` (bool) | `force: true` permet de contourner les éléments masqués par CSS ou d'afficher une fenêtre modale. `repli_js: true` retente via JS si le clic natif échoue (v1.22.0) — nécessite que `--no-evaluer` soit désactivé |
| `cliquer_som` | `id` | — | Clic au centre des coordonnées de l'élément. Pas besoin de `force` |
| `cliquer_visuel` | `description` | — | Vision LLM (~32 s). Solution de dernier recours pour les éléments canvas ou sans attributs |
| `remplir` | `selecteur`, `valeur` | `secret_cle` | `valeur: "depuis_secrets"` résout les identifiants stockés |
| `remplir_som` | `id`, `valeur` | `secret_cle` | Efface le champ avant de taper. `valeur: "depuis_secrets_totp"` pour TOTP |
| `capturer` | `nom` | `som` (bool) | Image PNG intermédiaire nommée. `som: true` pour une capture annotée |
| `evaluer` | `script` | `attendu`, `contient`, `motif` | Code JS exécuté dans le navigateur. Assertions uniquement pour rpa.py |
| `defiler` | `px` ou `selecteur` | — | Défilement vertical en pixels (`px`) ou défilement vers un élément (`selecteur`) |
| `pause` | `ms` | `interval_capture` | Délai fixe en ms. Préférez `attendre_selecteur_present` pour les signaux DOM |
| `attendre` | `selecteur` | `interval_capture` | Attend que le sélecteur CSS soit présent |
| `attendre_navigation` | — | — | Attend que `networkidle` (fin des requêtes réseau) se produise |
| `attendre_url` | `motif` | `attendre_changement` (bool) | L'URL contient un motif (correspondance partielle). `attendre_changement: true` si l'URL actuelle contient déjà le motif |
| `attendre_selecteur_present` | `selecteur` | — | Attend que l'élément soit visible (état=visible) |
| `attendre_absence` | `selecteur` | `delai_initial_ms` | Attend que l'élément soit supprimé du DOM (état=detached) |
| `attendre_reseau_calme` | — | `timeout_ms` | 500 ms de silence réseau. `timeout_ms`: durée maximale avant d'abandonner |
| `attendre_mfa_ntfy` | `id_som` | `timeout` | Attend un code TOTP via ntfy, le remplit dans le champ SoM |
| `nettoyer_overlay` | `selecteur` | — | Masque les superpositions bloquantes (bannière de cookies, fenêtre modale). À utiliser avant SoM |
| `declencher_scenario` | `scenario` | — | Intègre les actions d'un sous-scénario. Profondeur maximale : 5 |
| `cliquer_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur` | `force` (bool) | Clic à l'intérieur d'un iframe (v1.17.0). `iframe_chemin` pour les iframes imbriquées (v1.18.0, section 5k). Pas de SoM à l'intérieur des frames |
| `remplir_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur`, `valeur` | `secret_cle` | Remplissage à l'intérieur d'un iframe (v1.17.0). `iframe_chemin` pour les iframes imbriquées (v1.18.0). `valeur: "depuis_secrets"` pris en charge |

---

## 7. Gérer les obstacles courants

### 7a. Bannière de cookies / superposition de blocage

```json
{"type": "nettoyer_overlay", "selecteur": ".cookie-consent-banner, #gdpr-overlay"}
```

Placez **avant** toute autre action et avant les numéros de SoM. Le masque recouvre les éléments qui sont numérotés par SoM.
Ne l'utilisez pas dans les scénarios `watch.py`. (Le masque fait partie de la référence visuelle).

### 7b. Élément hors de la zone visible

SoM avertit lorsqu'un élément interactif est hors de l'écran :

```json
"som_hors_viewport": 3,
"avertissement_scroll": "3 interactive element(s) off-viewport — use defiler before cliquer_som"
```

```json
{"type": "defiler", "selecteur": "#the-button"},
{"type": "remplir_som", "id": 7, "valeur": "depuis_secrets", "secret_cle": "username"}
```

### 7c. Composants web - Shadow DOM

Si les éléments interactifs visibles ne reçoivent aucun numéro SoM :

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --shadow-dom
```

Ou dans le scénario : `"shadow_dom": true` à la racine.

Quand utiliser : Angular, Lit, Stencil, FAST. Ne pas activer sur les projets qui n'utilisent pas de composants web.

Pour accéder à un élément à l'intérieur d'un Shadow Root sans `--shadow-dom` :

```json
{"type": "evaluer", "script": "document.querySelector('my-component').shadowRoot.querySelector('button').click()"}
```

### 7d. Applications Web monopages (SPA) (React, Vue, Angular) — navigation sans rechargement

Après un clic qui modifie l'affichage dans une application monopage (SPA), Playwright ne sait pas quand la navigation est terminée.

```json
{"type": "cliquer_som", "id": 5},
{"type": "attendre_url", "motif": "/dashboard"},
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
```

Ou attendez un élément spécifique à la nouvelle vue :

```json
{"type": "cliquer_som", "id": 5},
{"type": "attendre_selecteur_present", "selecteur": "[data-testid='dashboard-main']"}
```

Ne présumez jamais qu'un clic a terminé la navigation sans un signal DOM.

### 7e. Boîte de dialogue CSS ou `showModal()`

`TimeoutError` sur `cliquer` lorsque l'élément est visible dans le DOM = élément CSS-hidden
ou à l'intérieur d'une boîte de dialogue.

```json
{"type": "cliquer", "selecteur": "#dialog-confirm button[type=submit]", "force": true}
```

Si `force: true` est insuffisant (élément absent du DOM) :

```json
{"type": "evaluer", "script": "document.querySelector('#dialog-confirm button[type=submit]').click()"}
```

Ne pas utiliser `force` sur `cliquer_som`. C'est inutile, car `cliquer_som` utilise les coordonnées et contourne les vérifications de manière native.

### 7f. Opération longue durée (indicateur de progression, tâche par lot)

N'utilisez pas `pause` pour attendre une durée fixe. Attendez le signal DOM :

```json
{"type": "cliquer_som", "id": 7},
{"type": "attendre_absence", "selecteur": ".spinner", "delai_initial_ms": 500},
{"type": "attendre_selecteur_present", "selecteur": ".result-container"},
{"type": "capturer", "nom": "result"}
```

Si l'opération ne fournit aucun signal DOM, utilisez `interval_capture` pour observer l'état :

```json
{"type": "pause", "ms": 30000, "interval_capture": 5}
```

Les captures intermédiaires apparaissent dans `stream_captures[]`.

### 7g. Limite atteinte (v1.15.0)

Si `respect.plafond_atteint` est présent dans la sortie, l'exécution a été
arrêtée avant la fin du scénario. Les actions restantes n'ont pas été exécutées.

Options:
1. Augmenter `max_pages_par_run` ou `max_actions_par_run` dans `diwall.conf`.
2. Diviser le scénario en plusieurs exécutions.
3. Modifier les limites maximales dans le fichier JSON du scénario (à documenter dans _CADRE).

### 7h. `<select>` champ de formulaire

`remplir` ne fonctionne pas sur `<select>`. Utilisez `remplir_som` avec l'ID SoM de la `<select>`.

### 7i. Identifiants SoM non valides lors de l'exécution suivante

Les identifiants SoM sont recalculés à chaque capture. Ils ne persistent pas entre les exécutions.
Relancez toujours `shot.py --som` pour obtenir les identifiants de l'exécution actuelle.
Après un `defiler` ou l'ouverture d'une fenêtre modale : relancez `shot.py --som`.

### 7j. Dérive de l'ID SoM sur les pages très dynamiques — `--som-rafraichir` (v1.17.0)

Par défaut, `cliquer_som`/`remplir_som` résolvent `id: N` en réindexant le DOM actif au moment du clic ; si un élément apparaît ou disparaît **avant** votre cible dans l'ordre du DOM entre les phases de capture de `--som` et le clic (par exemple, une bannière de cookies qui se ferme, une fenêtre modale qui s'ouvre), `id: N` peut silencieusement résoudre vers un élément **différent** de celui affiché numériquement N dans la capture d'écran.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --som-rafraichir \
  --actions '[{"type":"cliquer_som","id":5}]'
```

Avec cet indicateur, chaque élément numéroté est marqué au moment de la capture et résolu
grâce à ce marquage plutôt que par réindexation — si l'élément exact a été supprimé, vous
obtenez une erreur explicite "élément SoM non trouvé" au lieu d'un clic sur une cible incorrecte. `boussole.som_rafraichir_actif: true` lorsqu'il est actif. Recommandé sur les
pages où le DOM change fréquemment entre la capture et l'action ; sans effet sur le
comportement par défaut lorsqu'il n'est pas spécifié.

Depuis la version v1.17.2, l'injecteur efface également les marqueurs laissés par une capture précédente `--som` sur la même page avant de renombrer — sans cela, un élément caché ou masqué entre deux captures pourrait conserver une référence obsolète `data-dw-som-id`, ce qui provoquerait un conflit avec un élément nouvellement numéroté et entraînerait l'utilisation de la mauvaise référence.

### 7k. Site bloqué par le WAF (erreur 403 immédiate)

```bash
# Essayez discrètement.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --mode fast --stealth
```

Si l'erreur 403 persiste avec `--stealth`: le site utilise l'empreinte TLS (JA3/JA4) ou une analyse comportementale avancée (Cloudflare Enterprise). `playwright-stealth` ne contourne pas ces protections.
Voir `docs/RETOUR_EXPERIENCE.md` FR-77/FR-78/FR-79 pour plus de contexte.

Diwall signale également un blocage probable de manière passive, sans que vous ayez à vérifier vous-même le
code d'état HTTP — voir la section 3e (`respect.waf_bloquants`).

### 7l. La navigation initiale ne se termine jamais — `--wait-until` (v1.22.0)

Symptôme : `TimeoutError` lors de la navigation initiale, et l'augmentation de `--timeout` ne change rien (45 s échoue exactement comme 10 s). Cause : par défaut, Diwall attend `networkidle` – 500 ms de silence réseau. Une page qui interroge continuellement (statistiques en direct, compteurs actualisés automatiquement, panneaux d'administration du routeur) ne produit jamais ce silence, donc aucune valeur de délai d'attente ne peut être suffisamment grande.

```bash
# shot.py — direct reconnaissance
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url http://target.local/ --wait-until load --som --a11y --guide-version 1.2

# rpa.py — propagé à shot.py, de sorte que les scénarios atteignent les mêmes cibles.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario ./admin_login.json --wait-until load --guide-version 1.2
```

Un scénario peut également l'inclure comme propriété racine, ce qui le rend autonome :

```json
{"url": "http://target.local/", "wait_until": "load", "actions": [...]}
```

Le paramètre de ligne de commande a priorité sur la propriété du scénario.

| Valeur | Attend | Utiliser lorsque |
|---|---|---|
| `networkidle` | 500 ms de silence réseau | par défaut - à conserver sauf en cas de problème |
| `load` | événement `load` (page et ressources secondaires) | sondage continu / statistiques en direct |
| `domcontentloaded` | HTML analysé, les ressources secondaires sont toujours en attente | page très lourde, seul le DOM est nécessaire |

S'applique uniquement à la navigation initiale ; l'action `naviguer` n'est pas affectée.
`boussole.wait_until` affiche la valeur uniquement lorsqu'elle diffère de la valeur par défaut.

---

## 8. Surveillance visuelle — watch.py

### 8a. Sauvegarder une référence

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --sauver-reference \
  --nom home
```

La référence est enregistrée dans `/opt/diwall/references/`.

### 8b. Comparaison avec la référence (différence de pixels)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
```

Jugements :

| `taux_diff` | Verdict | Code de sortie |
|---|---|---|
| < 0,2 % | `stable` | 0 |
| 0,2 % – 5 % | `drift` | 0 |
| ≥ 5 % | `regression` | 1 |
| Dimensions différentes | `viewport_mismatch` | 2 |

### 8c. Comparaison sémantique (LLM)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer \
  --llm local
```

Combiner l'analyse des différences de pixels et l'analyse par modèle linguistique (LLM) :

```bash
--llm-en-complement   # LLM only if pixel verdict is drift or regression
```

### 8d. Ignorer une zone animée

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel reference.png \
  --exclure-zone 100,200,300,50    # X,Y,Width,Height in pixels
```

### 8e. Boucle de surveillance

```bash
while true; do
  /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
    --url https://target.local/status \
    --comparer-pixel /opt/diwall/references/status-ok.png \
    --ntfy-url https://ntfy.sh/my-alerts
  sleep 60
done
```

### 8f. Cron pour la surveillance autonome

```bash
# /etc/cron.d/diwall-monitor
*/30 * * * * diwall /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/status-ok.png \
  --ntfy-url https://ntfy.sh/my-alerts \
  >> /var/log/diwall/cron.jsonl 2>&1
```

### 8g. Surveillance structurelle continue — `monitor-verifier.sh` (v1.18.0)

Compléments 8a–8f : `watch.py` surveille l'*apparence* (pixels/sémantique).
`scripts/monitor-verifier.sh` surveille la *structure* (`http_status`,
`dom_stats`, `evaluations`, nombre de SoM) — image nulle, appel LLM nul, basé sur
`--no-capture` + `--replay-verifier` (section 5h).

```bash
# Premier lancement : créer la référence structurelle.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --sauver-verifier-reference /opt/diwall/references/sillage_login.ref.json

# Un script de vérification et d'alerte – ce n'est pas un démon, exécutez-le à plusieurs reprises via cron.
# Les fichiers `*.sh` situés dans le répertoire `scripts/` ne sont jamais déployés vers /opt/diwall/, ils s'exécutent donc depuis Git.
# source, en tant que votre propre utilisateur.
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --reference /opt/diwall/references/sillage_login.ref.json \
  --ntfy-topic diwall-monitoring
```

```bash
# crontab -e (votre propre fichier crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --reference /opt/diwall/references/sillage_login.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

Stable → silence. Régression → une notification `ntfy` avec le différentiel. Chaque
invocation est un processus isolé : pas de démon, pas de risque de fuite mémoire, et
les plafonds de Navigation Respectueuse se réinitialisent proprement à chaque passe.

---

## 9. Journal des opérations

Le journal est configurable dans `diwall.conf` (v1.15.0) :

```json
"journal": {
  "chemin": "~/Vaults/__PROJET__/Diwall/operations.jsonl"
}
```

Si le fichier est absent ou si le répertoire chiffré n'est pas monté, utiliser comme solution de repli : la variable d'environnement `DIWALL_JOURNAL`, puis `/var/log/diwall/operations.jsonl`.

```bash
# Lisez les 10 dernières entrées.
tail -n 10 ~/Vaults/__PROJET__/Diwall/operations.jsonl | python3 -m json.tool

# Filtrez par cible (journal.py outil).
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com

# Filtrez uniquement les opérations qui modifient l'état.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --mutatif

# À partir d'une date.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --depuis 2026-07-01

# Exécutions ayant échoué uniquement (v1.20.0) — resultat != "succès"
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --erreurs
```

Champs dans chaque entrée :

| Champ | Signification |
|---|---|
| `ts` | Horodatage ISO 8601 |
| `version` | Version Diwall |
| `outil` | `shot.py` ou `rpa.py` |
| `cible_url` | URL cible |
| `scenario` | Chemin du fichier de scénario (mode RPA) |
| `source_scenario` | Nom du fichier de scénario uniquement, sans chemin (v1.18.0) — active `mode_conseille` (section 2e) |
| `resultat` | `"succes"` ou `"echec"` |
| `mutatif` | `true` si au moins une action d'écriture est présente |
| `duree_ms` | Durée en ms |
| `intention` | Étiquette transmise via `--intention` ou champ de scénario `intention` |

### 9a. Rotation des journaux (G-36, CHANTIER_SANITISATION.md)

Diwall ne fournit pas de configuration `logrotate` — `/var/log/diwall/operations.jsonl`
et grandit indéfiniment jusqu'à ce que l'administrateur en installe une. `lib/journal.py` ouvre
et ferme le fichier à chaque écriture (pas de descripteur de fichier persistant entre
les exécutions), spécifiquement pour que le comportement par défaut de `logrotate` (renommer
le fichier actuel, créer un nouveau fichier) fonctionne correctement sans aucune option spéciale : la prochaine écriture rouvre le chemin et trouve le nouvel inode.

Ne pas ajouter ``copytruncate`` à une configuration de logrotate pour Diwall, car c'est
inutile ici (contrairement aux outils qui maintiennent un descripteur de fichier ouvert
pendant toute leur durée de vie) et cela réintroduit une fenêtre de perte d'écriture que cette conception a été conçue pour éviter. Exemple ``/etc/logrotate.d/diwall``:

```
/var/log/diwall/operations.jsonl {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0640 diwall diwall
}
```

`journal.py` (le lecteur) suit déjà les fichiers rotatifs de manière transparente.
(`operations.jsonl`, `.1`, `.2.gz`, ...) — aucune étape supplémentaire n'est nécessaire après la rotation.

---

## 10. Options de ligne de commande — référence

### shot.py

| Flag | Default | Description |
|---|---|---|
| `--version` | — | Affiche la version installée et se termine immédiatement — aucun Playwright, aucun autre argument requis (v1.18.0) |
| `--guide-version X.Y` | — | Preuve de lecture de `docs/GUIDE_LLM.md` — requis sauf si un marqueur local valide existe déjà (v1.18.0, section 1) |
| `--url URL` | required | URL à capturer |
| `--actions FILE` | — | Fichier JSON des actions séquentielles |
| `--output-dir DIR` | `/tmp/diwall` | Répertoire de sortie PNG |
| `--timeout MS` | 10000 | Délai d'attente Playwright par action (ms) |
| `--screenshot-timeout MS` | 120000 | Délai d'attente pour `page.screenshot()` (ms). Différent de `--timeout` |
| `--largeur PX` | 1280 | Largeur de la fenêtre d'affichage |
| `--hauteur PX` | 720 | Hauteur de la fenêtre d'affichage |
| `--som` | off | Active le marquage (numérotation des éléments) |
| `--a11y` | off | Inclut l'arborescence d'accessibilité dans le fichier JSON |
| `--shadow-dom` | off | Parcourt les Shadow Roots pour le marquage (Angular, Lit, Stencil) |
| `--stealth` | off | Mode furtif playwright-stealth (v1.15.0) |
| `--mode fast\|full` | — | `fast` = `--no-capture --a11y`. `full` = comportement par défaut |
| `--no-capture` | off | Ignore la capture PNG et le marquage |
| `--llm local\|claude` | `local` | Moteur LLM pour `cliquer_visuel` |
| `--secrets FILE` | — | Chemin explicite vers un fichier d'informations d'identification |
| `--auth-indicator SEL` | — | Sélecteur CSS présent uniquement dans la session authentifiée |
| `--auth-indicator-negative SEL` | — | Sélecteur CSS présent uniquement en dehors de la session authentifiée |
| `--intention TEXT` | — | Étiquette commerciale enregistrée dans le journal |
| `--sauver-session FILE` | — | Enregistre les cookies après les actions |
| `--reprendre-session FILE` | — | Reprend une session enregistrée |
| `--interval-capture N` | 0 | Captures périodiques toutes les N secondes pendant `attendre`, `pause` |
| `--som-rafraichir` | off | Résolution stable du marquage par attribut au lieu de la réindexation en direct (v1.17.0, section 7j) |
| `--ignorer-waf` | off | Un bloc WAF détecté dégrade `niveau_confiance` mais ne force plus automatiquement `pret_a_agir: false` (v1.17.2, section 3e) |
| `--http-credentials` | off | Résout les informations d'identification HTTP Basic Auth à partir du fichier d'informations d'identification, limitées à l'origine de la cible (v1.21.0, section 4g) |
| `--no-evaluer` | off | Refuse l'action **evaluer** pour toute l'exécution — recommandé en production pour les cibles avec des formulaires sensibles (v1.15.1) |
| `--no-filtre-evaluer` | off | Désactive la neutralisation de la sortie standard (**stdout**) des valeurs de retour, des URL et des messages d'erreur de **evaluer** — uniquement pour les exécutions de débogage explicites. La neutralisation est activée par défaut ; lorsqu'elle est désactivée, `boussole.filtre_evaluer_actif: false` est défini dans la sortie afin que l'opérateur puisse l'auditer directement à partir du fichier JSON (v1.23.0) |

### rpa.py

Transmet tous les drapeaux shot.py pertinents, ainsi que :

| Flag | Description |
|---|---|
| `--version` | Affiche la version installée et se termine immédiatement (v1.18.0) |
| `--guide-version X.Y` | Preuve de lecture de `docs/GUIDE_LLM.md` — vérifiée indépendamment, même règle que shot.py (v1.18.0) |
| `--scenario FILE` | Chemin vers le scénario JSON ou YAML (obligatoire) |
| `--url URL` | Remplace l'URL du scénario sans modifier le fichier |
| `--stealth` | Propagé à shot.py |
| `--mode fast\|full` | Propagé à shot.py |
| `--som-rafraichir` | Propagé à shot.py (v1.17.0, section 7j) |
| `--ignorer-waf` | Propagé à shot.py (v1.17.2, section 3e) |
| `--http-credentials` | Propagé à shot.py. Peut également être défini comme propriété racine du scénario `"http_credentials": true` (v1.21.0, section 4g) |
| `--sauver-verifier-reference FILE` | Enregistre la référence structurelle pour `--replay-verifier` (v1.17.0, section 5h) |
| `--replay-verifier FILE` | Compare l'exécution à une référence structurelle, sortie 1 en cas de régression (v1.17.0, section 5h) |
| `--checkpoint FILE` | Reprend un long scénario après un échec pendant son exécution (v1.17.0, section 5i) |

### watch.py

| Flag | Description |
|---|---|
| `--version` | Affiche la version installée et se termine immédiatement (v1.18.0) |
| `--guide-version X.Y` | Preuve de lecture de `docs/GUIDE_LLM.md` — vérifiée indépendamment, même règle que shot.py (v1.18.0) |
| `--url URL` | URL à surveiller |
| `--sauver-reference` | Capture et sauvegarde comme référence |
| `--comparer-pixel REF` | Différence de pixels par rapport au fichier PNG REF |
| `--comparer` | Différence sémantique LLM |
| `--nom NAME` | Nom de la vue (plusieurs vues par URL) |
| `--seuil-stable F` | Seuil `stable` (par défaut : 0.002 = 0,2 %) |
| `--seuil-regression F` | Seuil `regression` (par défaut : 0.05 = 5 %) |
| `--exclure-zone X,Y,W,H` | Zone à ignorer (répétable) |
| `--heatmap` | Produit une image PNG des zones modifiées |
| `--ntfy-url URL` | Envoie une alerte ntfy en cas de régression |
| `--llm-en-complement` | Ajoute la différence LLM lorsque le pixel = dérive ou régression |

---

## 11. Codes de sortie et résultats

### Codes de sortie

| Code | Cause | Que faire |
|---|---|---|
| 0 | Succès | — |
| 1 | Erreur Playwright, action en échec, assertion rpa.py | Lire `erreur` dans le JSON. Voir `GUIDE_LLM_INTERACTIONS.md` |
| 1 | `guide_non_lu` — `--guide-version` absent ou erroné, aucun marqueur valide (v1.18.0) | Se déclenche avant le lancement de Playwright. Lire `docs/GUIDE_LLM.md`, relancer avec `--guide-version X.Y` (section 1) |
| 2 | `viewport_mismatch` (watch.py) | Reprendre la référence au même viewport |
| 3 | Module `playwright` introuvable | Invoquer via `/opt/diwall/venv/bin/python3` |
| 42 | `SecretsFermesError` — répertoire chiffré non monté, ou somme de contrôle invalide | Le monter, ou vérifier le fichier d'identifiants |
| 43 | `SecretsNonConfigureError` — `diwall.conf` absent | `sudo cp /opt/diwall/diwall-sample.conf /opt/diwall/diwall.conf && sudo nano /opt/diwall/diwall.conf` |

### Structure du JSON de sortie

```json
{
  "succes": true,
  "http_status": 200,
  "url_finale": "https://target.local/dashboard",
  "erreurs_js": [],
  "erreurs_console": [],
  "duree_ms": 2400,
  "horodatage": "2026-07-01T12:00:00+02:00",
  "capture": "/tmp/diwall/a1b2c3d4e5f6/capture_1234567890123456789.png",
  "capture_som": "/tmp/diwall/a1b2c3d4e5f6/capture_som_1234567890123456789.png",
  "elements_som": [...],
  "a11y_tree": "...",
  "evaluations": [...],
  "latences_actions": [
    {"index": 0, "type": "naviguer", "latence_ms": 842},
    {"index": 1, "type": "cliquer_som", "latence_ms": 63}
  ],
  "respect": {
    "pages_visitees": 0,
    "actions_executees": 3,
    "duree_totale_ms": 2400,
    "indice_agressivite": 0.33
  },
  "etat": {
    "pret_a_agir": true,
    "niveau_confiance": "eleve",
    "raisons": ["aucun signal de friction détecté"]
  },
  "boussole": {
    "utilisateur": "operator",
    "ip_locale": "__IP_LAN__",
    "repertoire": "/opt/diwall",
    "operation_id": "a1b2c3d4e5f6",
    "url_courante": "https://target.local/dashboard",
    "titre_page": "Dashboard — My App",
    "stealth_actif": true,
    "shadow_dom_actif": true,
    "som_rafraichir_actif": true,
    "auth_status": "active",
    "som_hors_viewport": 0,
    "respect": { "pages_visitees": 0, "actions_executees": 3, "duree_totale_ms": 2400, "indice_agressivite": 0.33 }
  },
  "diwall_meta": {
    "version_shot": "1.23.0",
    "profil": "operator",
    "modeles_appeles": []
  }
}
```

`operation_id` (v1.16.0) est toujours présent et identifie de manière unique cette exécution ;
il nomme le répertoire d'isolation sous `/tmp/diwall/<operation_id>/` et
correspond au champ `operation_id` de l'entrée de cette exécution dans le journal des opérations
(section 9). `etat` (v1.16.0) est présent uniquement sur le chemin de succès.
`latences_actions` (v1.20.0) est toujours présent (liste vide s'il n'y a pas d'actions),
une entrée par action réellement exécutée ; voir `GUIDE_LLM_MONITORING.md`
pour comprendre comment il complète `respect.duree_totale_ms`.

Les clés conditionnelles (absentes lorsqu'elles sont inactives) : `capture`, `capture_som`, `elements_som`, `a11y_tree`,
`evaluations`, `auth_status`, `stealth_actif`, `shadow_dom_actif`, `som_rafraichir_actif`,
`som_hors_viewport`, `session_derive`, `respect.plafond_atteint`, `respect.waf_bloquants`,
`respect.indice_agressivite` (présentes chaque fois qu'au moins une action a été exécutée),
`actions_executees_avant_echec`, `pages_visitees_avant_echec` (uniquement dans le format JSON en cas d'échec, v1.17.0),
`etat.mode_conseille` (présentes uniquement avec des données antérieures réelles de type `diagnostic_dom.json` pour cet hôte, v1.18.0, section 2e).

### Erreur — format

```json
{
  "succes": false,
  "erreur": "secrets_fermes",
  "message": "Le répertoire chiffré Diwall est initialisé mais non monté.",
  "code_sortie_recommande": 42,
  "boussole": { "url_courante": "", "titre_page": "" }
}
```

---

## Chemins de référence

| Chemin | Rôle |
|---|---|
| `/opt/diwall/` | Installation de production |
| `/opt/diwall/venv/bin/python3` | Python à utiliser pour chaque invocation |
| `/opt/diwall/diwall.conf` | Configuration de la machine (identifiants, navigation, logs) |
| `/opt/diwall/diwall-sample.conf` | Modèle de configuration |
| `/opt/diwall/scenarios/` | Scénarios RPA |
| `/opt/diwall/docs/` | Documentation |
| `/opt/diwall/references/` | Références visuelles watch.py |
| `/tmp/diwall/<operation_id>/` | Captures temporaires pour une seule exécution, isolées par `operation_id` (v1.16.0, effacées au redémarrage) |
| `~/Vaults/__PROJET__/Diwall/` | Identifiants + logs (volume gocryptfs) |
| `~/git/Diwall/Diwall/` | Sources Git (modifier ici, puis `deploy.sh`) |

Déployez après avoir modifié les sources :

```bash
bash ~/git/Diwall/Diwall/scripts/deploy.sh
```
