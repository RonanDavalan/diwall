% DIWALL(1) | Commandes Diwall
%
% Juillet 2026

# NOM

diwall - outil de perception visuelle et de RPA pour les agents LLM

# RÉSUMÉ

**diwall-shot** \[*options*\] **--url** *URL*

**diwall-rpa** \[*options*\] **--scenario** *FICHIER*

**diwall-watch** \[*options*\]

**diwall-monter-secrets** \[*options*\]

**diwall-demonter-secrets** \[*options*\]

**diwall-monitor-verifier** **--scenario** *FICHIER* **--reference** *FICHIER*

# DESCRIPTION

Diwall offre à un agent LLM des "yeux" et des "mains" pour interagir avec des interfaces web qu'il ne pourrait autrement voir ou manipuler : captures d'écran, annotations de type "Set-of-Mark" et un arbre d'accessibilité d'un côté, et actions pilotées par Playwright de l'autre. Chaque commande affiche un seul objet JSON sur la sortie standard, conçu pour être lu par un programme plutôt que par un humain.

Ce paquet installe six commandes sous **/usr/bin**. Elles sont de simples
interfaces autour des points d'entrée Python dans **/opt/diwall**, et elles lisent
leur configuration depuis **/etc/diwall/diwall.conf** au lieu du
**/opt/diwall/diwall.conf** utilisé par le canal d'installation git-clone.

Il existe une seule page de manuel pour les six commandes, intentionnellement : une seule page ne peut pas perdre sa cohérence interne. Pour obtenir la liste exhaustive des options de n'importe quelle commande, exécutez-la avec **--help** – cette sortie est toujours plus fiable que celle de cette page.

# COMMANDES

**diwall-shot**
: Capture une page et renvoie un JSON la décrivant. Avec **--som**, les éléments interactifs sont numérotés dans l'image afin qu'un agent puisse s'y référer par index ; avec **--a11y**, l'arborescence d'accessibilité est incluse. Des actions peuvent être exécutées dans la même session de navigateur via **--actions**.

**diwall-rpa**
: Exécute un fichier de scénario (JSON ou YAML) décrivant une séquence d'actions,
et renvoie une seule ligne JSON. C'est la commande à utiliser pour tout ce qui est
répétable, et la seule qui évalue les assertions du scénario.

**diwall-watch**
: Surveillance visuelle. Enregistre une image de référence d'une page, puis compare les captures ultérieures à celle-ci — comparaison pixel par pixel localement, ou une description fournie par un modèle de vision locale. Utilisé pour détecter les régressions visuelles sans intervention humaine.

**diwall-monter-secrets**, **diwall-demonter-secrets**
: Montez et démontez le répertoire de crédentielles chiffré par gocryptfs. Diwall refuse
de résoudre les identifiants tant qu'il est fermé, et se termine avec le code de sortie 42 au lieu de revenir à une méthode moins sécurisée.

**diwall-monitor-verifier**
: Effectue une passe de vérification structurelle d'un scénario par rapport à une référence enregistrée et se termine avec un code non nul en cas de divergence. Conçu pour être exécuté par cron ou un minuteur systemd ; il ne contient pas de boucle propre.

# OPTIONS COURANTES

Les options ci-dessous sont partagées par **diwall-shot** et **diwall-rpa**, sauf indication contraire. Il s'agit d'une sélection, et non de la liste complète.

**--guide-version** *X.Y*
: Preuve obligatoire que **/opt/diwall/docs/GUIDE_LLM.md** a été lu. Sans cela,
— et sans un marqueur local toujours valide —, la commande refuse de s'exécuter et
se termine avec le code 1. La valeur attendue est le commentaire *notice-version* sur la ligne 3 de ce
guide. C'est le seul endroit où Diwall n'est pas une option facultative.

**--version**
: Afficher la version installée au format JSON et quitter, sans lancer de navigateur.
Différent de **--guide-version** ; les deux numéros ne sont pas liés.

**--mode** *fast*|*full*
: *fast* est **--no-capture --a11y**: sans PNG, environ deux secondes plus rapide,
suffisant pour lire l'état. *full* est le mode par défaut et capture le rendu.

**--som**
: Numérotez les éléments interactifs visibles dans la capture, afin que les actions puissent
les cibler par index plutôt qu'en utilisant des sélecteurs CSS.

**--wait-until** *networkidle*|*load*|*domcontentloaded*
: Indique quand la navigation initiale est considérée comme terminée. Par défaut,
*networkidle* attend 500 ms d'inactivité du réseau et convient à la plupart des
cibles. Une page qui interroge continuellement ne reste jamais inactive ; utilisez *load* dans ce cas ;
modifier **--timeout** ne peut pas aider, car la page ne se terminera jamais.
**diwall-shot** uniquement.

**--timeout** *MS*
: Délai d'expiration par opération en millisecondes (par défaut : 10000). Différent de
**--screenshot-timeout** (par défaut : 120000), qui concerne uniquement la capture d'écran.

**--stealth**
: Supprimez les marqueurs automatiques qui identifient un navigateur sans interface graphique. Cela ne modifie pas l'adresse IP de l'opérateur et ne falsifie pas une identité ; le but est d'assurer un traitement équitable, et non de masquer quoi que ce soit.

**--secrets** *FICHIER*
: Résoudre les identifiants à partir d'un fichier JSON explicite situé dans un répertoire monté,
au lieu de la recherche par défaut basée sur l'hôte.

**--no-evaluer**
: Refuser l'action **evaluer** pour toute la session — le code JavaScript arbitraire n'est pas exécuté sur la page cible.

**--no-filtre-evaluer**
: Désactiver la neutralisation de la sortie standard des valeurs de retour de **evaluer**, des URL et des messages d'erreur — uniquement pour les exécutions de débogage explicites. La neutralisation est activée par défaut ; lorsqu'elle est désactivée, `boussole.filtre_evaluer_actif: false` est défini dans la sortie afin que l'opérateur puisse l'auditer directement à partir du JSON.

# FICHIERS

**/etc/diwall/diwall.conf**
: Configuration lue par les commandes fournies. Créée par l'administrateur, et jamais
générée automatiquement. La variable d'environnement **DIWALL_CONF** remplace
ce chemin, ce qui permet à plusieurs projets de conserver des configurations distinctes sur une même
machine.

**/opt/diwall/**
: Code de l'application, l'environnement virtuel Python et la documentation
à laquelle les commandes elles-mêmes font référence.

**/opt/diwall/docs/GUIDE_LLM.md**
: Le point d'entrée qu'un agent doit lire.  **MANUEL.md** dans le même
répertoire contient les commandes exactes avec les chemins réels.

**/var/log/diwall/**
: Journal d'opérations en ajout seul. Conservé lors d'**apt remove**, supprimé lors d'**apt purge**.

**/tmp/diwall/**
: Fichiers PNG capturés, effacés au redémarrage.

# CODE DE RETOUR

**0**
: L'exécution est terminée. Notez qu'un code HTTP 404 ou 403 sur la cible est signalé dans le JSON, et non comme une erreur de la commande.

**1**
: L'exécution a échoué, ou la vérification préalable n'a pas été satisfaisante (*guide_non_lu*) .

**2**
: Arguments incompatibles, rejetés avant même que n'importe quel navigateur ne soit lancé.

**42**
: Le Répertoire d'identifiants est fermé. Montez-le avec **diwall-monter-secrets**.

**43**
: La somme de contrôle de l'intégrité des identifiants ne correspond pas.

# EXEMPLES

Capturer une page avec des éléments numérotés et l'arborescence d'accessibilité :

    diwall-shot --url https://example.com --som --a11y --guide-version 1.2

Consultez uniquement l'état d'une page, sans générer d'image :

    diwall-shot --url https://example.com --mode fast --guide-version 1.2

Accédez à un panneau d'administration qui actualise les statistiques en continu :

    diwall-shot --url http://target.local/ --wait-until load --som

Exécutez un scénario en utilisant les identifiants provenant d'un fichier spécifié :

    diwall-rpa --scenario ./login.json --secrets ~/Vaults/project/creds.json

Vérifiez qu'une page n'a pas subi de régressions structurelles :

    diwall-monitor-verifier --scenario ./page.json --reference ./page.ref.json

# VOIR AUSSI

La documentation complète est installée avec le paquet :
**/opt/diwall/docs/MANUEL.md** pour le manuel d'utilisation,
**/opt/diwall/docs/GUIDE_LLM.md** pour le guide destiné aux agents,
**/opt/diwall/docs/FAQ_LLM.md** pour les réponses classées par version.

La page d'accueil du projet est listée par la commande **apt show diwall**.
