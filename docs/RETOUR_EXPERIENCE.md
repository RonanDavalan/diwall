# Diwall — Retour d'expérience d'un LLM

Première session vécue : simulation « Pierre » sur Sillage — 18 mai 2026.
Six frictions rencontrées, dans l'ordre où elles sont apparues.

---

## 1. Le piège de Mode B (sessions ReAct)

Au départ, j'ai cru qu'il fallait `--sauver-session` / `--reprendre-session` pour
tout parcours multi-étapes. Réflexe naturel : « ReAct = un pas à la fois ».

**Réalité** : Mode B coûte cher — chaque appel relance Playwright, recharge le
storage_state, redessine le SoM. Pour un formulaire de 3 champs + submit, c'est
4 captures × ~2 s = 8 s minimum, plus le temps LLM entre chaque pas.

**Ce qui marche** : `--action` accepte un **tableau** d'actions atomiques. Une
seule invocation enchaîne fill+fill+fill+click, une seule capture finale.

```bash
--action '[
  {"type":"remplir_som","id":1,"valeur":"foo"},
  {"type":"remplir_som","id":2,"valeur":"bar"},
  {"type":"cliquer_som","id":3}
]'
```

**Heuristique** : Mode B uniquement quand le DOM change entre deux pas et que
je dois *voir* ce changement pour décider du suivant.

---

## 2. `--output sans extension` → `mime type None`

J'ai passé `--output /tmp/test` (sans `.png`). Erreur peu parlante :
`unknown mime type None`. Quelques minutes perdues à chercher si c'était un
problème Playwright, un PATH, une perm.

**Origine** : Playwright déduit le format d'image de l'extension du chemin de
sortie. Pas d'extension, pas de mime type.

**Fix côté utilisateur** : toujours `.png` (ou laisser Diwall générer le nom
automatique dans `/tmp/diwall/`).

**Fix côté Diwall** (suggestion) : ajouter `.png` si manquant, ou échouer tôt
avec un message explicite.

---

## 3. `remplir` plante quand le sélecteur matche plusieurs éléments

Tentative naïve : `{"type":"remplir","selecteur":"input","valeur":"foo"}`.
Le formulaire a 3 inputs → Playwright refuse (strict mode violation).

**Lecon** : `remplir` (CSS) est piégeux dès qu'il y a plusieurs candidats.
Le SoM résout ça nativement — chaque élément a un ID unique.

**Règle perso** : préférer `remplir_som` par défaut, garder `remplir` pour les
cas où l'on sait que le sélecteur est unique (ex : `#username`).

---

## 4. `remplir_som` sur input pré-rempli : le triple-clic rate

Le formulaire avait un champ URL pré-rempli avec `https://`. J'ai voulu écrire
`https://ada.example.com`. Diwall a tapé `ada.example.com` *après* le contenu
existant → résultat : `https://ada.example.com` (par chance correct au premier
test), mais sur le **troisième** champ URL, le triple-clic de sélection n'a pas
pris → le préfixe est resté → domaine créé = `ada` au lieu de `ada.example.com`.

**Origine** : `remplir_som` fait `triple-click → fill`. Sur certains inputs
(autocomplete, masques), le triple-click ne sélectionne pas tout le contenu.

**Workaround** : précéder le fill d'un clear explicite, ou utiliser
`element.fill('')` puis `element.fill(value)` côté Playwright.

**Fix côté Diwall** (suggestion) : faire `element.fill('')` avant le fill
réel, plutôt que de compter sur le triple-click.

---

## 5. Session PHP non persistée entre appels Mode B

Login réussi → capture montre la page authentifiée. Action suivante en
`--reprendre-session` → redirection vers `/login`. Cookies perdus.

**Origine** : `storage_state` capture cookies + localStorage, mais
**pas la session côté serveur**. Si le serveur PHP refait `session_start()`
avec un session ID périmé (ex : régénéré post-login), le cookie côté client
n'aide pas.

Dans le cas Sillage, c'était plus subtil : `session_regenerate_id()` après
login changeait l'ID, et `--sauver-session` capturait l'**ancien**. La fenêtre
de validité du nouveau cookie n'était pas dans le snapshot.

**Workaround** : enchaîner login + action suivante en **un seul** Mode A
multi-actions. Ou refaire le login à chaque étape (coûteux).

**Mention dans `GUIDE_LLM.md`** : la note SPA §3 dit
« Form values are NOT persisted in storage_state » — c'est vrai, mais
le problème session-côté-serveur mériterait sa propre ligne.

---

## 6. `button:has-text()` — la syntaxe Playwright qui n'est pas du CSS

Réflexe : `{"selecteur":"button:has-text('Connexion')"}`. C'est de la syntaxe
Playwright (pseudo-sélecteur étendu), pas du CSS standard. Diwall passe ça
tel quel à Playwright → ça **marche** la plupart du temps, mais ce n'est pas
documenté dans `GUIDE_LLM.md`.

**Suggestion doc** : ajouter au tableau des actions une ligne
« Playwright extended selectors supportés (`:has-text()`, `:visible`, etc.) »
ou au contraire les interdire pour rester strictement CSS.

---

## Synthèse session 1 — ce qui m'aurait fait gagner du temps

1. **Mode A multi-actions par défaut**, Mode B comme exception → à dire plus
   fort dans `GUIDE_LLM.md`. La doc actuelle présente Mode B en premier (§78),
   ce qui suggère que c'est le mode normal.
2. **Coup d'œil dès le départ sur les pièges du SoM** — pré-remplis,
   autocomplete, inputs maskés. Une section « SoM edge cases » manque.
3. **Un exemple de scénario complexe** (login + form + submit) dans `examples/`
   aiderait à voir le pattern « tout en une action ».

Le reste — l'idée d'avoir des yeux, la boucle Read(PNG) → analyse → fix,
le coût marginal d'une capture, la rapidité du SoM vs `cliquer_visuel` —
c'est aussi bon que la doc le promet. Une fois ces six pièges connus, on
travaille vite.

---

# Session 2 — Pierre v4 sur Sillage (19 mai 2026, après-midi)

Validation E2E du clonage VPS → IKE4 via l'UI Sillage (post-R13). Six
nouvelles frictions sont apparues, distinctes de celles de la session 1.

## 7. `attendre` vs `pause` — deux verbes pour deux choses

Réflexe : `{"type":"attendre","duree":1500}` pour insérer un délai de 1,5 s
entre deux clics. Diwall lève `KeyError: 'selecteur'`. Confusion : « attendre »
en français suggère un sleep ; en réalité c'est `page.wait_for_selector()`.

**Origine** : `attendre` mappe sur `page.wait_for_selector(a["selecteur"], …)`.
Champ requis : `selecteur`. La pause temporelle, c'est `pause` avec `ms`.

**Friction ressentie** : l'erreur `KeyError 'selecteur'` ne dit pas
*« vous vouliez peut-être pause ? »*. Plusieurs minutes à relire `shot.py`
avant de comprendre que `attendre ≠ sleep`.

**Workaround** : utiliser `{"type":"pause","ms":1500}`.

**Suggestion doc** : renommer ou doc claire — `attendre_selecteur` (alias
explicite) et garder `attendre` en deprecated. Ou renommer en `wait_for` /
`sleep` pour lever toute ambiguïté linguistique.

---

## 8. `<dialog>` HTML modal disparaît après `--reprendre-session`

Scénario : Pierre clique un bouton qui appelle `dialog.showModal()`. La
capture SoM montre bien les éléments de la modal (id=18 « Annuler », id=19
« Lancer le clonage »). Action suivante : `--reprendre-session` puis
`cliquer_som id=19` → `élément SoM 19 non trouvé sur la page`.

**Origine** : `storage_state` capture cookies + localStorage + URL, mais pas
l'état JS d'un `<dialog>` ouvert via `showModal()`. À chaque `--reprendre`,
Playwright fait `page.goto(url)` → la page recharge → la modal disparaît.

**Friction ressentie** : croire que la session est un *snapshot complet*
de l'état UI. C'est faux. La session est un *snapshot transactionnel* :
cookies + storage, pas l'état des composants JS.

**Workaround** : enchaîner `cliquer-bouton-qui-ouvre-modal` + `pause` +
`cliquer-bouton-de-la-modal` dans **une seule** invocation Mode A. Pas de
`--reprendre-session` entre les deux.

**Suggestion doc** : ajouter dans `GUIDE_LLM.md` une note sur les pièges
de la reprise de session — modals, popovers, focus, sélections, scroll,
champs dirty.

---

## 9. Sélecteurs Playwright étendus pas tous supportés (`:left-of`, etc.)

Tentative : `button:has-text("↺ Cloner"):left-of(:has-text("Gérer →"))`.
Playwright supporte officiellement `:left-of()`, mais le verbe `cliquer` de
Diwall fait `page.click(selector)` qui ne semble pas activer ces extensions
par défaut → timeout 120 s sans capture intermédiaire utile.

**Origine** : la chain de sélecteurs Playwright a deux modes — les pseudos
classiques (`:has-text`, `:visible`, `:nth-match`) qui marchent partout, et
les pseudos relationnels (`:left-of`, `:right-of`, `:near`) qui nécessitent
Playwright >= 1.18 et parfois un `engine` explicite.

**Friction ressentie** : la doc Playwright dit *« ça marche »*, mais sans
préciser que c'est sensible aux versions. Diagnostic compliqué — `cliquer`
ne fait pas de capture d'échec utilisable (juste le timeout).

**Workaround** : préférer des sélecteurs *intrinsèques* à l'élément cible
plutôt que relationnels. Ici, le bouton avait `title="Cloner clone.davalan.fr
(WordPress) depuis le VPS vers IKE4"` → sélecteur unique :
`button[title*="Cloner clone.davalan.fr"][title*="(WordPress)"]`.

**Leçon** : SoM > sélecteurs CSS relationnels > sélecteurs CSS basiques.
Quand un élément a un attribut HTML unique (`title`, `aria-label`, `id`),
l'utiliser plutôt que sa position.

---

## 10. Plusieurs boutons identiques — `:has-text()` matche le premier

La vue projet contenait **trois** boutons « ↺ Cloner WordPress » (un par
domaine). Le sélecteur `button:has-text("↺ Cloner WordPress")` matche le
premier rencontré dans le DOM. Pierre ne sait pas lequel il va lancer.

**Origine** : `page.click(selector)` sans qualificatif. Playwright en mode
strict refuserait, mais Diwall ne semble pas le forcer.

**Friction ressentie** : « j'ai cliqué Cloner pour clone.davalan.fr, et le
log montre que c'est sillage.davalan.fr qui a démarré ». Inversion silencieuse.

**Workaround** : sélecteur précis via `title=` (qui contient le nom du
domaine), ou via SoM (chaque bouton a un `id` SoM unique).

**Suggestion Diwall** : activer le `strict mode` Playwright par défaut, ou
au moins le surfacer dans `GUIDE_LLM.md`. Un échec strict-mode est BIEN plus
utile qu'un clic silencieux sur le mauvais élément.

---

## 11. Pas de visibilité sur une action longue (clonage 2-3 min)

Le clonage WordPress prend ~2 min. Diwall capture *après* la `pause` finale.
Entre temps, l'interface affiche peut-être un spinner, une barre de progrès,
des logs en temps réel — Pierre ne voit rien. Pour suivre l'exécution j'ai
dû ouvrir une session SSH en parallèle (`tail -f` du log côté serveur).

**Origine** : Diwall = capture *terminale*. Le modèle « 1 invocation = 1 PNG »
n'autorise pas le streaming.

**Friction ressentie** : 3 minutes d'attente aveugle. Si le clonage avait
planté à 30 s, je l'aurais su qu'au bout de 3 min. Et pour itérer, c'est
2-3 min de plus à chaque test.

**Workaround** : insérer plusieurs `{"type":"capturer","nom":"intermediaire-N"}`
dans la séquence d'actions. Chaque appel capturer génère un PNG dans
`output-dir`, on peut faire `Read` dessus à la fin et inspecter visuellement
les étapes.

**Suggestion Diwall** : option `--stream-toutes-les-Ns 10` qui capture
automatiquement toutes les 10 s pendant les `pause` longues, et stocke les
PNG dans `output-dir/`. Très utile pour le debug.

---

## 12. `~/Vaults/Diwall` par défaut, pas `~/Vaults/<Projet>/Diwall`

Le vault par défaut est `~/Vaults/Diwall/<domaine>.json`. Ronan a
historiquement rangé les credentials en `~/Vaults/Sillage/Diwall/...`.
La première tentative `remplir … "valeur":"depuis_vault"` a échoué parce
que Diwall cherchait `~/Vaults/Diwall/sillage.ike4.local.json` (absent).

**Origine** : `lib/vault.py` lit `DIWALL_VAULT_DIR` (env var), sinon défaut
`~/Vaults/Diwall`. La doc ne dit pas que la convention multi-projet
`~/Vaults/<Projet>/Diwall/` est gérée à la main par l'utilisateur via env.

**Friction ressentie** : « j'ai mis les credentials au bon endroit, pourquoi
ça ne marche pas ? ». Cinq minutes de `find` pour réaliser que c'était une
question de variable d'env.

**Workaround** : `DIWALL_VAULT_DIR=/home/ron/Vaults/Sillage/Diwall` devant
l'invocation, à chaque fois.

**Suggestion Diwall** : (a) lire un fichier de config par projet
(`.diwall.toml` à la racine du dépôt courant qui pointe le vault dir), ou
(b) une convention « auto-détecter `~/Vaults/<basename-du-cwd>/Diwall/` ».

---

## Synthèse session 2 — ce qui se confirme

- **Mode A multi-actions reste la voie royale** — confirmé pour la 2e fois.
  Pierre v4 a tenté Mode B pour la modal post-clic, ça a foiré (friction #8).
- **SoM mieux que CSS relationnel** — friction #9. SoM > `:left-of` > tout.
- **Sélecteurs intrinsèques à l'élément** (`title=`, `aria-label`, `id`)
  > sélecteurs textuels — friction #10.
- **Captures intermédiaires sont sous-utilisées** — friction #11. À
  populariser dans la doc.

Bilan : 12 frictions sur 2 sessions. La 1ère a découvert les pièges
*structurels* (Mode B, session, `:has-text`, SoM edge cases) ; la 2e les
pièges *contextuels* (sémantique des verbes, état modal, sélecteurs
multi-match, suivi d'action longue, vault). Diwall reste un outil d'une
puissance rare une fois ces pièges connus.

---

# Session 3 — Validation R33-bis sur Sillage (21 mai 2026, après-midi)

Session courte : valider le rendu de trois pages de l'interface Sillage après
un changement back-end (durcissement de `config.sh`). Deux frictions, toutes
deux liées à l'enchaînement d'un parcours authentifié.

## 13. `naviguer` — valider plusieurs pages authentifiées en une invocation

Les sessions 1 et 2 ont établi « Mode A multi-actions = voie royale » pour un
formulaire sur **une** page. Restait une question : comment valider le rendu de
**plusieurs** pages derrière un login, sans `--reprendre-session` (proscrit,
frictions #5 et #8) ?

**Réflexe initial** : une invocation par page, en rejouant le login à chaque
fois. Coûteux et inutile.

**Réalité** : le verbe `naviguer` (`{"type":"naviguer","url":"…"}`) fait un
`page.goto()` en conservant le contexte navigateur — donc la session PHP
obtenue au login. Une seule invocation Mode A enchaîne login + `naviguer` vers
la page A + `capturer` + `naviguer` vers la page B + `capturer`, etc.

**Pattern** : pour valider N pages authentifiées, une liste d'actions unique —
`remplir_som`/`cliquer_som` (login), puis pour chaque page `naviguer` +
`attendre_navigation` + `capturer`. Chaque `capturer` produit un PNG dans
`output-dir`. Trois pages validées en une invocation, ~4 s.

**Leçon** : `naviguer` étend « Mode A = voie royale » du multi-action au
multi-page. `--reprendre-session` n'est jamais nécessaire pour un simple
parcours de validation.

---

## 14. Les fichiers `scenarios/*.json` ne sont pas consommables tels quels

`/opt/diwall/scenarios/sillage_login.json` est un objet
`{"nom":…, "url":…, "actions":[…]}`. Réflexe : `--actions
scenarios/sillage_login.json`.

**Réalité** : `--actions` (comme `--action`) attend un **tableau** d'actions.
`charger_actions` fait `json.load` et renvoie l'objet ; `executer_actions`
itère alors les **clés** du dict (`"nom"`, `"url"`, `"actions"`) et plante sur
`"str".get("type")`. Aucun flag `--scenario` n'existe.

**Friction ressentie** : le répertoire `scenarios/` ressemble à une
bibliothèque prête à l'emploi ; en fait ses fichiers sont des *gabarits*. Pour
s'en servir, il faut extraire `.actions` (à passer à `--actions`) et `.url`
(à passer à `--url`) séparément.

**Suggestion Diwall** : soit un flag `--scenario` qui lit l'objet complet
(`url` + `actions`), soit faire détecter à `charger_actions` un objet
contenant une clé `actions` et en extraire le tableau.

---

## Synthèse session 3

- `naviguer` complète le tableau : Mode A couvre désormais explicitement le
  parcours multi-page authentifié — friction #13.
- Le format des `scenarios/*.json` (objet) diverge de ce que `--actions`
  consomme (tableau) — friction #14.

14 frictions sur 3 sessions. La 3e était une session de validation pure :
deux frictions seulement, signe que l'outil est maîtrisé une fois les
sessions 1 et 2 digérées.

