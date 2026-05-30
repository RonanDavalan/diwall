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

Validation E2E du clonage VPS → __HOST_ADMIN__ via l'UI Sillage (post-R13). Six
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
plutôt que relationnels. Ici, le bouton avait `title="Cloner __HOST_ADMIN__
(WordPress) depuis le VPS vers __HOST_ADMIN__"` → sélecteur unique :
`button[title*="Cloner __HOST_ADMIN__"][title*="(WordPress)"]`.

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

**Friction ressentie** : « j'ai cliqué Cloner pour un domaine donné, et
le log montre qu'un autre domaine a démarré ». Inversion silencieuse.

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

Le vault par défaut est `~/Vaults/Diwall/<domaine>.json`. L'opérateur
peut avoir historiquement rangé les credentials en `~/Vaults/<PROJET>/Diwall/...`.
La première tentative `remplir … "valeur":"depuis_vault"` a échoué parce
que Diwall cherchait `~/Vaults/Diwall/__HOST_ADMIN__.json` (absent).

**Origine** : `lib/vault.py` lit `DIWALL_VAULT_DIR` (env var), sinon défaut
`~/Vaults/Diwall`. La doc ne dit pas que la convention multi-projet
`~/Vaults/<Projet>/Diwall/` est gérée à la main par l'utilisateur via env.

**Friction ressentie** : « j'ai mis les credentials au bon endroit, pourquoi
ça ne marche pas ? ». Cinq minutes de `find` pour réaliser que c'était une
question de variable d'env.

**Workaround** : `DIWALL_VAULT_DIR=~/Vaults/<PROJET>/Diwall` devant
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

---

# Session 4 — Validation suppression en lot Sillage (29 mai 2026)

Session de validation UI : tester la suppression en lot de clones WordPress
depuis la vue domaine de l'interface Sillage (cases à cocher + barre d'actions).
Deux frictions, l'une bloquante (manque d'action dans shot.py), l'autre
préventive (workaround déjà connu mais non documenté pour rpa.py).

## 15. `remplir` incompatible avec `<select>` — action `select_option` manquante

> **RÉSOLU le 29/05/2026 (commit `4bc463e`).** `remplir_som` détecte désormais
> `tag == "SELECT"` et applique `el.value = valeur; el.dispatchEvent(new Event('change', {bubbles:true}))`
> via `page.evaluate()`, au lieu de `fill()`. Plus besoin d'action `select_option`
> dédiée : on cible le `<select>` par son ID SoM avec `remplir_som`. Validé E2E
> (suppression en lot Sillage, session 5).

Besoin : choisir une option dans un `<select>` HTML (la barre d'actions en lot
de Sillage utilise un `<select id="select-action-lot">`).

**Tentative** : `{"type":"remplir","selecteur":"#select-action-lot","valeur":"supprimer"}`.

**Erreur** :
```
Locator.fill: Error: Element is not an <input>, <textarea> or [contenteditable] element
```

`fill()` Playwright ne supporte que les inputs textuels. Pour un `<select>`,
Playwright expose `select_option()`.

**shot.py n'a pas d'action `select_option`** → blocage total sur tout scénario
nécessitant un `<select>`.

**Workaround côté LLM** : aucun workaround propre. On peut tenter un `evaluate`
JavaScript, mais shot.py ne supporte pas `evaluate`. Le scénario s'arrête là.

**Fix côté Diwall** (suggestion d'implémentation) :

```python
elif t == "select_option":
    page.locator(a["selecteur"]).select_option(a.get("valeur", ""), timeout=timeout)
```

À ajouter dans le bloc `elif` de `executer_actions()`, entre `remplir` et `cliquer`.
Usage dans un scénario :
```json
{"type": "select_option", "selecteur": "#select-action-lot", "valeur": "supprimer"}
```

**Impact** : toute interface utilisant des `<select>` est actuellement non
testable via scénario rpa.py ou Mode A. Fréquent dans les UI CRUD (filtres,
actions en lot, sélection de rôle…).

---

## 16. Navigation post-login RPA retombe sur la page de login sans pause

Dans un scénario rpa.py enchaînant login + `naviguer`, la navigation vers la
page cible retombait sur la page login si aucune pause n'était insérée après
le clic "Se connecter".

**Scénario défaillant** :
```json
{"type":"cliquer_som","id":2},
{"type":"attendre_navigation"},
{"type":"naviguer","url":"https://…/page-cible"}
```

**Scénario fonctionnel** :
```json
{"type":"cliquer_som","id":2},
{"type":"pause","ms":2000},
{"type":"naviguer","url":"https://…/page-cible"}
```

**Origine** : `attendre_navigation` ne suffit pas — il détecte `networkidle`
mais la session PHP côté serveur n'est pas encore validée (session_regenerate_id
post-login, cf. friction #5). La `pause 2000ms` laisse le serveur émettre le
cookie de session régénéré avant la prochaine navigation.

**Lien avec friction #5** : même cause racine. Ici c'est dans rpa.py au lieu
de Mode B, mais le diagnostic est identique : `attendre_navigation` ≠
« session serveur prête ».

**Suggestion doc** : ajouter dans `GUIDE_LLM.md` (section RPA ou parcours
authentifiés) : *"Après un submit de formulaire de login, insérer systématiquement
`{"type":"pause","ms":2000}` avant toute `naviguer` vers une page protégée.
`attendre_navigation` ne garantit pas que la session serveur est propagée."*

---

## Demande architecturale : documentation LLM avec mémoire des régressions

Au-delà des frictions techniques, une demande structurelle a émergé lors de
cette session : les LLM qui utilisent Diwall redécouvrent les mêmes frictions
à chaque session, car le `RETOUR_EXPERIENCE.md` est riche mais non synthétisé
en règles actionnables.

**Besoin** :
1. Une **documentation LLM courte** (< 2 pages) listant les règles définitives
   — ce qui fonctionne, ce qui est proscrit, les workarounds validés. Format
   "règle → contexte → exemple", pas de narratif.
2. Un **registre de scénarios testés et validés** (avec leurs résultats attendus)
   pour détecter les régressions entre versions de shot.py.

**Suggestion** : créer `docs/GUIDE_LLM_REGLES.md` (la synthèse des 16 frictions
en 20 règles numérotées) et `docs/SCENARIOS_VALIDES.md` (table des scénarios
avec version shot.py, résultat attendu, date de dernière validation).

---

## Synthèse session 4

- `select_option` manquant dans shot.py → bloquer sur tout `<select>` HTML
  (friction #15 — **bloquante, demande un correctif shot.py**).
- Pause obligatoire post-login dans rpa.py (friction #16 — workaround connu,
  à documenter explicitement dans `GUIDE_LLM.md`).
- Demande architecturale : doc LLM synthétique + registre de scénarios validés.

16 frictions sur 4 sessions.

---

# Session 5 — Reconnexion __HOST_VPS__ → __HOST_ADMIN__ sur Sillage (29 mai 2026, soir)

Session longue et de bout en bout : reconnecter un client hébergé sur un serveur
**Plesk à comptes cloisonnés** (un utilisateur à droits minimaux par site), via
l'UI Sillage pilotée par scénarios `rpa.py` — ajout serveur, sonde, création des
domaines, puis clonage WordPress distant→local. Friction #15 **confirmée résolue**.
Trois nouvelles frictions, dont une structurante.

## 17. `--scenario` existe désormais — mais attend un chemin, pas un nom

La suggestion de la friction #14 a été **implémentée** ✅ : `rpa.py` a maintenant
un flag `--scenario` qui lit l'objet complet `{url, actions}`. Mais il attend un
**chemin de fichier**, pas un nom de scénario du répertoire `scenarios/`.

`--scenario sillage_voir_client` → `{"erreur":"fichier_introuvable"}`.
Il faut `--scenario /opt/diwall/scenarios/sillage_voir_client.json`.

**Friction ressentie** : le répertoire `scenarios/` ressemble à une bibliothèque
adressable par nom ; en réalité il faut le chemin complet. (Et il n'y a pas de
wrapper `diwall.sh` — l'invocation est `venv/bin/python3 rpa.py --scenario …`.)

**Suggestion** : résoudre un nom nu contre `scenarios/<nom>.json` en plus du
chemin absolu.

---

## 18. Pas d'introspection DOM depuis rpa.py (ni `evaluate`, ni extraction HTML)

Pour passer de « je *vois* un bouton sur la capture » à « je connais son
**sélecteur** / son **href** », j'ai tenté `evaluer_js`, `extraire_html`,
`capturer_som` → tous `Type d'action inconnu`. Aucune action ne permet
d'interroger le DOM (`querySelectorAll`, lire un `href`, lister les liens d'une
page). Pour découvrir l'URL du bouton « Configurer » et le sélecteur du formulaire
« Lancer la sonde », j'ai dû lire le **source PHP côté serveur** (via SSH).

**Origine** : `shot.py` expose `naviguer/cliquer/remplir/capturer/*_som/cliquer_visuel`,
pas d'`evaluate`.

**Friction ressentie** : la capture est en lecture seule. Diwall *voit* mais ne
*renseigne* pas. Ici je m'en suis sorti parce que j'avais accès au source de
l'app ; **en boîte noire (vrai cas B2B), ce serait bloquant** — on ne pourrait
pas extraire un sélecteur sans le deviner visuellement.

**Workaround** : lire le source (PHP/HTML) en parallèle de la capture.

**Suggestion** : action `evaluer` (`page.evaluate`, retour JSON dans la sortie).
Débloque l'extraction de sélecteurs/href, l'inspection d'état, et — avant #15 —
aurait résolu le cas `<select>`.

---

## 19. SoM en mode scénario : `som:true` dans `capturer` semble ignoré

Pour obtenir l'overlay numéroté SoM, j'ai mis `{"type":"capturer","som":true}` →
la capture rendue n'avait **pas** les numéros. `rpa.py` expose un flag CLI `--som`
(visible dans l'usage) ; c'est probablement lui qui active le SoM, pas un champ
dans l'action `capturer`.

**Friction ressentie** : le champ `som:true` est accepté **silencieusement**
(aucune erreur) mais sans effet → on croit avoir le SoM, on ne l'a pas, et on
perd un aller-retour à comprendre pourquoi les IDs n'apparaissent pas.

**Workaround** : invoquer `rpa.py --som` (à reconfirmer), ou rester en sélecteurs
CSS quand on connaît le source.

**Suggestion** : soit honorer `som:true` au niveau de l'action `capturer`, soit
rejeter le champ inconnu avec un avertissement.

---

## Confirmations de cette session

- **#15 résolue** : suppression en lot E2E OK ; `remplir_som` pilote un `<select>`
  via JS. Le scénario complet (cocher → choisir « supprimer » → dialog → confirmer)
  passe.
- **#11 (action longue aveugle)** : le clonage __HOST_VPS__→__HOST_ADMIN__ a pris ~5 min.
  `--timeout 300000` + lancement en arrière-plan ont tenu (durée 306 622 ms), mais
  le suivi de progression s'est fait via `ssh … du -sh` en parallèle — aucune
  visibilité dans Diwall.
- **`:has()` CSS natif supporté** : `form:has(input[value='lancer_sonde']) button[type='submit']`
  a fonctionné — à bien distinguer de `:has-text()` Playwright (friction #6).

## Synthèse session 5

19 frictions sur 5 sessions. La 5e **confirme la résolution de #15** (le `<select>`
n'est plus un mur) et révèle la limite la plus structurante : **#18 — sans
`evaluate`, Diwall voit mais ne renseigne pas**. Tant que la cible est une app
dont on possède le source, on complète par la lecture du code ; pour une cible en
boîte noire, l'absence d'introspection DOM deviendrait bloquante. C'est le candidat
n°1 pour le prochain incrément de `shot.py`.

---

# Session 6 — 30 mai 2026 (validation v1.1 sur le terrain)

Première session après livraison locale de Diwall v1.1 (incréments A/B/C de la
Phase 8 lot 8.1). Cible : suppression unitaire d'une ressource identifiée par
horodatage sur `__HOST_ADMIN__` (banc de test). Mémoire procédurale lue avant
exécution : relevés d'instance de la cible (couche privée du `_CADRE/`).

## 20. `--reprendre-session` ne préserve pas l'état DOM (case cochée)

**Constat** : workflow stateful découpé en deux invocations
1. `shot.py … --sauver-session …` (login + navigation + clic sur une checkbox)
2. `shot.py --reprendre-session … --actions '[choisir action, confirmer]'`

L'étape 2 retourne `succes:true` en ~1 s, sans capture intermédiaire et sans effet
réel sur la cible. Cause : `storage_state` Playwright ne sauvegarde que cookies
et `localStorage`, **pas l'état DOM**. La case cochée à l'étape 1 est perdue à la
reprise ; les actions SoM suivantes ciblent les bons IDs sur une page propre, donc
opèrent sur des éléments sans intérêt (footer, etc.) sans erreur.

**Workaround** : ne **jamais découper** un workflow stateful. Faire un Mode A
unique du début à la fin (login → action → confirmation), même si cela impose de
re-loguer. Sur la cible de test, le Mode A unique a pris 7,5 s et réussi ; la
décomposition avait pris 1,1 s et silencieusement échoué.

**Suggestion** : signaler explicitement dans le JSON de retour de `--reprendre-session`
si l'URL chargée diffère de l'URL active à la sauvegarde (heuristique faible mais
utile), ou documenter clairement que l'état DOM n'est pas restauré dans
`GUIDE_LLM.md` / `26_GUIDE_CLAUDE_SESSION_DIWALL.md`.

## 21. SoM dynamique : la position d'un contrôle ajouté dépend du nombre d'éléments listés

**Constat** : une procédure validée sur une page contenant *N* lignes (cas 1
ligne au 29/05) plaçait le SELECT d'action en bas de liste à un certain ID SoM.
Le 30/05 sur la même page contenant *N+4* lignes, la même cible a été déplacée
d'autant d'IDs SoM. La barre d'action ajoute bien un nombre fixe d'éléments
(+2 ici), mais cette base bouge avec le nombre de lignes visibles précédentes.

**Workaround** : capturer SoM **après** le `cliquer_som` sur la cible pour
relever l'ID dynamique du SELECT, puis lancer la suite. Sinon, sélecteurs CSS
directs pour les éléments à id fixe — mais friction #15 oblige à passer par
`remplir_som` pour un `<select>`, qui exige l'id SoM dynamique.

**Suggestion** : nouveau verbe `remplir_select` (sélecteur CSS direct + valeur),
qui ferait le même boulot interne que `remplir_som` sur un SELECT mais sans
dépendance à la numérotation SoM volatile. Ouvre la voie au passage en Mode B
ReAct pour les workflows stateful.

## 22. `evaluer` (livré ce jour) sauve l'audit post-action

Vérification de l'effet de la suppression : au lieu d'une recapture SoM + analyse
visuelle des slugs visibles, une action
`{"type":"evaluer","script":"Array.from(document.querySelectorAll('input.chk-clone')).map(i => i.value)"}`
retourne immédiatement la liste des slugs restants en JSON, comparable
programmatiquement. **Friction #18 réellement résolue** dès la première session
post-livraison.

## 23. Identification temporelle d'une cible parmi N : SoM contient le slug

**Constat** : demande de suppression d'une ressource identifiée par sa date
(`AAAA-MM-JJ HH:MM`). La liste contient N candidats. Une heuristique du genre
« la plus récente = id SoM 7 » devient fausse dès qu'une nouvelle ressource est
créée. Le `value` de chaque case à cocher contient le slug horodaté
(`__SLUG_HORODATE__`), exposé tel quel dans `elements_som[].texte`. L'identification
se fait par filtrage textuel sur la sortie SoM — pas besoin de vision LLM.

**Leçon** : pour les cibles dont l'horodatage est dans un attribut DOM (`value`,
`data-*`, `id`), le SoM est auto-suffisant ; pas de delegation vision.

## Synthèse session 6

3 nouvelles frictions consignées (#20–#22), une procédure validée 30/05 ajoutée
côté Sillage (`VAL_tester-suppression.md` — variante unitaire ciblée), `evaluer`
adopté en production immédiatement après livraison. **Friction #20
(`--reprendre-session` + DOM stateful) est la candidate la plus probable pour le
prochain incrément** : soit signaler la dérive d'état, soit acter dans la doc que
le découpage est interdit pour les workflows stateful.

