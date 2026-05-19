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

## Synthèse — ce qui m'aurait fait gagner du temps

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
