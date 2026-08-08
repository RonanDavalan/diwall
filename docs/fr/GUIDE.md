# Diwall — Guide de l'utilisateur

Version 1.10 — Août 2026 (v1.23.0) — quatre nouveaux exemples d'utilisation (observabilité hébergée en interne, administration de la plateforme de ticketing, suivi des événements locaux, accès à l'e-commerce via Respectful Navigation).

*Également disponible en français, allemand et espagnol sous `docs/fr/`, `docs/de/` et `docs/es/`.*

---

## Pourquoi Diwall — ce que vous déléguez réellement

### Le problème que Diwall résout

Lorsque vous travaillez avec un LLM dans une application web, une asymétrie de perception se produit :
le modèle lit du code, exécute des commandes, observe les résultats textuels, mais il ne voit pas
l'interface que vos utilisateurs voient. Vous, par contre, la voyez.

Cette asymétrie crée une forme spécifique d'anxiété : vous ne savez pas si ce que
le modèle décrit correspond à ce que vous verriez dans un navigateur. Pour être sûr, vous devez
soit lui faire confiance aveuglément, soit le vérifier vous-même.

Diwall résout ce problème en créant une **référence visuelle partagée** :
le modèle capture l'interface avec un navigateur réel (Chromium sans interface graphique),
et vous avez accès aux mêmes captures PNG et aux arbres d'accessibilité.
Vous ne faites plus confiance aveuglément au modèle — vous observez le même état que lui.

```
 Browser (headless Chromium)
        │  Playwright drives it — click, fill, navigate
        ▼
 shot.py / rpa.py
        │  reads the resulting DOM state through parallel views
        ├──▶ capture_som   PNG, interactive elements numbered
        ├──▶ elements_som  JSON list — id, tag, text
        ├──▶ a11y_tree     accessibility tree, text
        └──▶ session file  cookies only (--sauver-session)
        │
        ▼
 boussole + JSON on stdout — same state you would see in a browser
        │
        ▼
 You (the model): read → analyse → decide → act → loop
```

### Ce que vous déléguez

Diwall vous permet de déléguer les **vérifications visuelles répétitives et source d'anxiété** :

- Vérifier que 20 pages d'un site s'affichent correctement après un déploiement.
- Confirmer qu'un formulaire de connexion fonctionne sur l'interface appropriée.
- S'assurer qu'un déploiement n'a pas compromis le rendu d'une vue critique.
- Valider visuellement qu'une correction est correctement visible à l'écran.

Sans Diwall, ces vérifications sont de votre responsabilité. Avec Diwall, le modèle les effectue et rapporte le résultat, avec une preuve visuelle.

### Ce que vous conservez

Vous conservez une **validation globale du résultat** : vous décidez si le résultat
présenté par le modèle est acceptable, cohérent avec vos attentes, et conforme
à ce que vos utilisateurs devraient voir. Cette décision reste la vôtre.

### Navigation Respectueuse (v1.15.0)

Diwall ne masque pas son identité pour contourner la détection des robots. `--stealth`
supprime les marqueurs techniques automatiques (`navigator.webdriver`) qui bloquent
les navigateurs sans interface graphique, quel que soit l'objectif — il ne modifie pas
l'adresse IP de l'utilisateur, son identité, ni le fait que l'exécution est déclarée. En échange, chaque exécution
signale sa propre empreinte (`respect`: pages visitées, actions exécutées,
durée) et respecte les délais de politesse configurables et les limites strictes
(`diwall.conf [navigation]`). Le droit de naviguer et le devoir de naviguer
de manière mesurable sont considérés comme inséparables — voir `docs/RETOUR_EXPERIENCE.md`
FR-77/FR-78/FR-79 pour le contexte qui a façonné cela.

Les cibles locales : le délai de courtoisie n'est pas une doctrine, mais un paramètre par défaut.
(v1.19.0) : la version livrée `min_action_delay_ms: 800` protège
une première exécution non configurée contre l'accès public à Internet ; elle est inutile
contre votre propre machine de développement/de production. Définissez-la sur `0` dans votre fichier local
`diwall.conf` pour le débogage local ; voir la section 3b de `docs/MANUEL.md`.

### Quand Diwall est le bon outil

| Cas d'utilisation | Diwall adapté ? |
|---|---|
| Validation visuelle après le déploiement | ✓ Oui |
| Diagnostic d'un rendu incorrect | ✓ Oui |
| Navigation et saisie de formulaires (max. 30 s) | ✓ Oui |
| Délégation de vérifications répétitives | ✓ Oui |
| Opération serveur longue (clonage ~2–5 min) | ✗ Non — Dépassement du délai d'attente de Playwright |
| Suppression ou modification en masse | ✗ Non — Privilégier un appel API direct |
| Flux de travail nécessitant une restauration | ✗ Non — Diwall ne peut pas annuler les actions |

Pour les cas où l'utilisation est déconseillée, voir la section "Quand NE PAS utiliser Diwall" (références FR-59 et FR-60 documentées).
`docs/GUIDE_LLM.md`

---

**Ce document est destiné à la personne qui utilise Diwall.**

Il complète `GUIDE_LLM.md` (destiné aux modèles) avec des exemples concrets,
des procédures étape par étape et des rappels sur les points problématiques courants.

---

## Cas d'utilisation de démonstration

Les exemples ci-dessous illustrent ce à quoi peut ressembler une session "agent+Diwall"
dans la pratique. Ils sont destinés à être évalués par rapport à votre propre contexte, et non comme une recommandation d'adopter un modèle spécifique. Seul le cas 1 est fourni sous forme de scénario exécutable ; les autres sont délibérément narratifs, et chacun explique pourquoi, sous son propre titre.

### Cas 1 : Dépannage des fichiers CSS/JavaScript locaux

Considéré comme un scénario réel et exécutable :
`scenarios/exemples/depannage_local.json`. Il diagnostique un décalage visuel
ou une interaction bloquée sur une interface locale — une vérification rapide
(`--mode fast`), lisant `erreurs_js`/`erreurs_console`, une capture `--som`
si le décalage est purement visuel, puis validez la correction avec
`watch.py --comparer-pixel` par rapport à une référence capturée avant la
régression. Exécutez-le directement :

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/exemples/depannage_local.json \
  --guide-version 1.2
```

### Cas 2 : comparaison des composants matériels entre différents magasins

Un agent chargé de comparer le prix et la disponibilité d'un composant dans plusieurs boutiques en ligne pourrait utiliser Diwall avec un outil distinct de découverte d'URL (par exemple, une instance de recherche locale) pour trouver les pages de boutiques potentielles, puis utiliser Diwall en mode sonde (`--mode fast`, sans PNG) avec les actions `evaluer` pour extraire le prix /stock/specifications de chaque page, et enfin comparer les résultats lui-même.

**Volontairement non livré comme scénario versionné :** nommer une boutique
précise dans un scénario public et versionné est une décision qui vous
appartient, pas un choix par défaut que ce projet devrait faire à votre place.
Cela comporte aussi un vrai risque de fragilité — un scénario public visant un
site commercial nommé peut échouer des mois plus tard quand la posture anti-bot
de ce site change (39 % des sites commerciaux de l'échantillon de
`docs/RETOUR_EXPERIENCE.md` FR-77 ont renvoyé un blocage immédiat), ce qui
discrédite l'exemple plus qu'il n'aide. Si vous construisez cette composition
vous-même, notez que tout outil de découverte d'URL que vous associez à Diwall
(une instance de recherche locale ou autre) n'est pas un composant de Diwall —
c'est une brique distincte que l'agent compose par-dessus.

### Cas 3 : exploration et résumé de la documentation technique (applications monopages)

Un agent chargé de produire un guide d'intégration pour un site de documentation
construit en tant qu'application monopage pourrait utiliser `rpa.py` avec
`attendre_reseau_calme` pour permettre au routage côté client de se stabiliser, extraire
l'arborescence d'accessibilité en mode rapide afin de cartographier la structure de la page, puis parcourir
récursivement les blocs de code avec `evaluer` pour extraire leur contenu exact, et enfin
synthétiser le matériel collecté dans un guide.

**Ne pas livrer en tant que scénario "clé en main", pour la même raison que le cas 2 :**

Mentionner un site de documentation spécifique (ou, pire, un fournisseur de paiement spécifique dont la documentation est l'exemple fonctionnel) engage une responsabilité commerciale et de réputation que ce projet ne devrait pas assumer par défaut. De plus, le même risque de vulnérabilité lié à un pare-feu applicatif (WAF) s'applique à un scénario public associé à une cible réelle spécifique.

### Cas 4 : configuration d'un tableau de bord d'observabilité ou d'analyse auto-hébergé

Un opérateur configurant un tableau de bord de surveillance ou d'analyse web auto-hébergé
derrière un proxy inverse peut utiliser Diwall pour gérer l'interface elle-même —
créer un tableau de bord, connecter une source de données, définir une règle d'alerte —,
de la même manière que n'importe quel autre panneau d'administration est configuré, plutôt que de modifier manuellement
des fichiers pour des étapes que l'interface utilisateur est censée gérer. Cela inclut les cibles situées
derrière un défi HTTP Basic Auth au niveau du réseau (`--http-credentials`,
v1.21.0) — confirmé contre une véritable interface d'administration protégée par Caddy, et non pas
juste un environnement de test artificiel : les identifiants stockés ont répondu
au défi dès la première tentative.

**Ne pas livrer en tant que scénario prédéfini** — la disposition du tableau de bord et les noms des sources de données sont spécifiques à l'infrastructure d'un opérateur donné, et inventer un équivalent synthétique dupliquerait ce que le test local du cas 1 couvre déjà pour la régression structurelle, et non pour ce type de travail de configuration guidée et en plusieurs étapes.

### Cas 5 : administration complète d'une plateforme de gestion des tickets

Diwall a été utilisé sur plusieurs sessions pour configurer et exploiter une véritable installation de billetterie auto-hébergée : configuration des événements, catégories de billets, un domaine personnalisé et les outils de scan/enregistrement le jour J, tout cela via la même interface web qu'utiliserait un administrateur humain. Des difficultés réelles ont été rencontrées et résolues en cours de route (gestion des sessions, particularités des menus déroulants, une invite de permission bloquant une étape automatisée), ce qui n'est pas une réussite sans problèmes, et c'est précisément ce qui fait de cet exemple un outil utile : les obstacles étaient des obstacles ordinaires à l'automatisation web, et non quelque chose de spécifique à Diwall.

**Ne pas expédier en tant que scénario configuré** : une configuration de billetterie concerne
les aspects liés à la facturation et aux spécificités du lieu, qui sont propres à l'opérateur, comme pour
le cas 2.

### Cas 6 : suivi d'un calendrier régional des événements

Un exemple simple d'utilisation de la recherche sémantique : demander à un agent de vérifier le calendrier des événements locaux pour connaître les prochaines manifestations, sans savoir à l'avance quelle page contient la réponse. Le mode rapide de Diwall (`--mode fast`, sans capture), combiné à l'arborescence d'accessibilité, permet à l'agent de scanner et de renvoyer des informations en quelques requêtes seulement — aucun modèle de vision n'est nécessaire pour ce type de tâche axée sur le texte et en lecture seule. Une session a également produit un exemple clair et réel du comportement documenté de faux positifs du signal WAF : une page s'est chargée normalement (contenu riche, sans captcha, sans fenêtre contextuelle) alors que [`respect.waf_bloquants`] était toujours déclenché, en raison d'une ressource tierce non liée sur la page qui correspondait à un mot-clé de détection — ce problème a été résolu en environ une minute en lisant l'arborescence d'accessibilité déjà présente dans la même réponse, exactement comme le prévoit la règle du guide : "signal, et non blocage".

**Ne pas distribuer en tant que scénario validé** — un site spécifique d'événements régionaux
n'est pas une cible publique stable et reproductible, et le choix de la nommer publiquement
relève de l'opérateur, et non d'une configuration par défaut du projet.

### Cas 7 — test de l'accès réel aux sites de commerce en ligne sous Navigation Respectueuse

Une observation honnête et récurrente provenant de sessions réelles : utilisée avec respect
(retards limités, plafonds de pages/actions, `--stealth` actif, aucune tentative de
forcer l'accès au-delà d'un bloc réel), Diwall, lorsqu'il est utilisé contre une gamme de sites de commerce électronique, constate qu'une part importante des principales plateformes renvoie un bloc total — HTTP 403, ou une requête qui ne se termine jamais —, quel que soit le comportement du trafic. Ce n'est pas un défaut de Diwall à corriger :
la posture anti-bot est le choix propre du site, et Diwall ne tente pas de
la contourner (voir "Navigation Respectueuse" ci-dessus). En pratique : pour les tâches de comparaison de prix auprès de grandes plateformes commerciales, attendez-vous à un nombre important d'impasses, et considérez un signal de bloc (`respect.waf_bloquants`) comme une information permettant de trouver un itinéraire alternatif, et non comme une erreur à réessayer.

Il est important de garder à l'esprit la distinction suivante : un écran de vérification invisible qui ne se résout jamais et ne présente rien sur lequel agir (pas de case à cocher, pas de défi visuel) est différent d'un CAPTCHA interactif. Ce dernier peut être répondu honnêtement : un agent agissant pour une personne identifiable, depuis l'adresse IP de cette personne, n'est pas le "robot" auquel la question s'adresse. Le premier ne propose tout simplement aucune option à exploiter du côté de l'agent, et contourner cet obstacle (rotation d'IP, usurpation de l'empreinte TLS) sort du champ d'action de Diwall.

Ne pas considérer ceci comme un scénario validé, et intentionnellement ne pas mentionner les plateformes impliquées — voir le raisonnement sur la fragilité du WAF dans le cas 2 : un tableau de blocage/non-blocage daté, lié à des sites commerciaux spécifiques, devient obsolète et compromet son propre objectif plus rapidement qu'il ne l'illustre. `docs/RETOUR_EXPERIENCE.md`
FR-77 documente le même schéma à l'échelle d'un panneau (taux de blocage immédiat de 39 %).

---

## Prérequis avant de commencer

```bash
# 1. Vérifier si Diwall répond.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --som --a11y
# → must return {"succes": true, ...}

# 2. Vérifiez que le répertoire chiffré est monté (si vous utilisez gocryptfs).
ls ~/Vaults/Diwall/
# → doit afficher les fichiers .json, et non le contenu chiffré.

# 3. Vérifier les identifiants pour un domaine.
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.repertoire_chiffre import lire_credential
print('OK' if lire_credential('target.local', 'password') else 'EMPTY')
"
```

---

## Configuration des identifiants par projet

Chaque projet peut avoir son propre répertoire de certificats. Deux méthodes :

**Méthode 1 : Variable d'environnement directe (exécution unique) :**

```bash
DIWALL_SECRETS_DIR=~/Vaults/MyProject \
  /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

**Méthode 2 : Fichier de projet `.diwall.conf` (recommandée pour les projets récurrents) :**

```bash
# Créez le fichier à la racine du projet.
echo '{"secrets_dir": "../MyProject-secrets"}' > ~/git/MyProject/.diwall.conf

# Then prefix each invocation (or export at the start of the shell session)
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

Le `secrets_dir` dans le fichier `.diwall.conf` peut être un chemin relatif ; il est résolu par rapport à l'emplacement du fichier `.diwall.conf`.

---

## Capture d'une page et analyse de son contenu

```bash
# Vérification rapide (sans fichier PNG - environ 2 secondes, lecture seule).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
# Retourne url_courante, titre_page, a11y_tree dans le format JSON.

# Capture complète avec éléments numérotés.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
# La capture PNG se trouve dans /tmp/diwall/capture_<ts>.png.
```

**Ce que vous obtenez :**
- `boussole.url_courante` + `boussole.titre_page` : URL et titre effectifs après navigation
- `capture` : chemin du PNG de la page telle qu'elle est rendue
- `capture_som` : PNG annoté avec les numéros d'éléments
- `a11y_tree` : structure de la page en texte (titres, champs, boutons)

---

## Automatisation d'un formulaire de connexion

**Étape 1** — Préparer le fichier d'identifiants.

Le fichier d'identifiants s'appelle `<hostname>.json`, où `hostname` est le résultat de
`urlparse(url).hostname`. Pour `https://app.example.com/`, le fichier est
`app.example.com.json`.

```json
{"username": "admin@example.com", "password": "my-secret"}
```

**Étape 2** — Examinez la page de connexion.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ --som --a11y
```

Ouvrez l'image PNG annotée (`capture_som`) pour identifier les identifiants SoM des champs.

**Étape 3** — Rédigez le scénario.

```bash
cat > /tmp/login.json << 'EOF'
{
  "nom": "app_login",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "after-login"}
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

## Valider plusieurs pages en une seule exécution

Pour consulter N pages d'un site authentifié sans avoir à ressaisir les identifiants à chaque fois :

```bash
cat > /tmp/audit.json << 'EOF'
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
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

Pour lire une chaîne de texte, un compteur ou n'importe quelle valeur DOM :

```bash
cat > /tmp/extract.json << 'EOF'
[{"type": "evaluer", "script": "document.title"}]
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --actions /tmp/extract.json
# → résulte en évaluations[0].valeur
```

**Important** : écrivez toujours les scripts JS dans un fichier `--actions`,
jamais en ligne avec `--action` (le shell corrompt les guillemets imbriqués).

---

## Configuration de la surveillance visuelle

```bash
# 1. Enregistrer la référence visuelle.
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --nom home

# 2. Comparer ultérieurement (différence de pixels).
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
# → verdict : stable / dérive / régression (code de sortie 0 ou 1)

# 3. Sur une page authentifiée : capturez d'abord avec rpa.py, puis enregistrez.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/login.json > /tmp/out.json
CAPTURE=$(python3 -c "import json; d=json.load(open('/tmp/out.json')); print(d['captures_intermediaires'][-1])")
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --capture "$CAPTURE" --nom dashboard
```

---

## Configuration de la surveillance continue des structures (v1.18.0)

Complète la surveillance visuelle ci-dessus : ceci vérifie la *structure* de la page
(code de statut, nombre d'éléments DOM, résultats de l'évaluation JavaScript) au lieu de son
*apparence* — c'est moins coûteux et permet de détecter un type différent de régression (par exemple, un champ de formulaire disparu avec une mise en page inchangée).

```bash
# 1. Enregistrer une référence structurelle, une seule fois.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --sauver-verifier-reference /opt/diwall/references/my-scenario.ref.json

# 2. Un contrôle et une alerte.
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring
```

Silencieux lorsqu'il est stable, il s'active avec une seule exécution de `ntfy` lorsqu'une régression est détectée. Planifiez-le vous-même avec cron : le script effectue un seul passage et se termine, il ne boucle pas.
`scripts/*.sh` n'est jamais déployé sur `/opt/diwall/`, donc la tâche cron s'exécute
à partir du code source git, en tant que votre propre utilisateur (et non le compte de service `diwall`,
qui ne peut pas accéder à `~/git/Diwall/Diwall/` :

```bash
# crontab -e (votre propre fichier crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

---

## Les pièges courants

| Situation | Ce qu'il faut faire |
|---|---|
| `FileNotFoundError` dans le fichier d'identifiants | Vérifiez que le fichier JSON est nommé avec le FQDN complet (`urlparse(url).hostname`) |
| `SecretsFermesError` (sortie 42) | Montez le répertoire chiffré : `bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh` |
| JSON invalide dans la sortie | Utilisez `2>/dev/null \| tail -1` pour extraire uniquement la ligne JSON |
| Les ID SoM diffèrent entre les sessions | Comportement attendu — les ID SoM sont recalculés à chaque capture. Ne les réutilisez jamais entre les sessions |
| Connexion suivie d'une redirection Django vers le tableau de bord | N'utilisez pas `naviguer` dans une session Django reprise — transmettez l'URL via `--url` |
| Le champ du formulaire `<select>` n'est pas rempli | Utilisez `remplir_som` (et non `remplir`) avec l'ID SoM de la section `<select>` |
| Un clic n'a aucun effet sur un bouton hors de la zone visible | Ajoutez `{"type":"defiler","selecteur":"#the-button"}` avant le clic |
| `auth_status: "active"` même sur la page de connexion | Le sélecteur positif est ambigu (en-tête persistant) — ajoutez `--auth-indicator-negative .btn-login` |
| Les éléments des composants Web ne sont pas numérotés par SoM | Ajoutez `--shadow-dom` (Angular, Lit, Stencil) |
| `respect.waf_bloquants` apparaît sur une page qui n'est en fait pas bloquée | La détection est basée sur des mots-clés (v1.16.0, affinée v1.17.2) — considérez cela comme un signal, et non comme un verdict. Si cela persiste sur une page que vous avez confirmée comme non bloquée, ajoutez `--ignorer-waf` |
| `cliquer_som` clique sur l'élément incorrect sur une page qui a muté entre la capture et le clic | Ajoutez `--som-rafraichir` (v1.17.0) — résout en utilisant un marqueur stable au lieu d'une réindexation en direct |
| Un long scénario RPA échoue à mi-chemin et vous ne voulez pas rejouer les étapes terminées | Ajoutez `--checkpoint FILE` (v1.17.0) — relancez la même commande pour reprendre ; l'état du DOM n'est pas conservé, seulement la session + la position de l'action |
| Les éléments interactifs à l'intérieur d'un iframe sont invisibles pour Diwall | SoM ne peut pas numéroter le contenu de l'iframe (même origine ou autre origine) — utilisez `cliquer_iframe`/`remplir_iframe` (v1.17.0) avec un sélecteur CSS explicite, ou `iframe_chemin` (v1.18.0) pour un iframe imbriqué dans un autre |
| Votre modèle signale `"erreur": "guide_non_lu"` / sortie 1 lors de son premier appel à Diwall | Comportement attendu la première fois qu'un modèle utilise Diwall sur cette machine en tant que cet utilisateur OS (v1.18.0) — il doit lire `docs/GUIDE_LLM.md` et passer `--guide-version` une seule fois. C'est intentionnel, ce n'est pas un bug — demandez au modèle de lire le guide plutôt que de contourner l'erreur |

---

## Désinstallation de Diwall

Le script `~/git/Diwall/Diwall/scripts/uninstall.sh` désinstalle proprement le logiciel, dans l'ordre inverse de `install.sh`.

```bash
# Voyez ce qui sera supprimé, sans rien faire.
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run

# Désinstallation complète (confirmation interactive).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh

# Sans confirmation (tests préliminaires, réinstallations successives).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme && bash ~/git/Diwall/Diwall/scripts/install.sh
```

Qu'est-ce qui est supprimé :

| Item | Detail |
|---|---|
| `/opt/diwall/` | Code, environnement Python (venv), configuration |
| `/var/log/diwall/` | Journaux d'opérations |
| `diwall` utilisateur système | Créé exclusivement pour Diwall |
| `diwall` groupe système | Identique |
| Appartenance au groupe | Votre compte est retiré du groupe `diwall` |
| Hook de pré-envoi Git | `core.hooksPath` désactivé dans le dépôt source |

Ce qui ne doit jamais être modifié :
- `~/Vaults/` — vos identifiants
- `~/git/Diwall/` — les sources Git
- Le cache du navigateur Playwright (`~/.cache/ms-playwright/`)

Conserve les captures (`/var/log/diwall/preuves/`) : si le répertoire contient des captures, elles sont conservées par défaut avec un avertissement. Pour les supprimer :

```bash
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme --purge-preuves
```

---

## Consulter l'historique des opérations

```bash
# Toutes les opérations sur une cible.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local

# Opérations de mutation uniquement (clics, saisie dans les formulaires).
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --mutatif

# À partir d'une date.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local \
  --depuis 2026-06-01
```
