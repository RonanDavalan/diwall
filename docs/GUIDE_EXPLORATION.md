# Diwall — Guide d'exploration et de cartographie

Version 1.1 — June 2026 (v1.14.0)

**Ce document est destiné aux modèles de langage utilisant Diwall.**

Il décrit le protocole "Exploration avant Exécution" : comment cartographier une
interface inconnue de façon sobre, puis l'automatiser sans improvisation.

---

## Le problème que ce guide résout

Un modèle lancé sur une interface inconnue sans préparation navigue à l'aveugle :
il tâtonne, retente, consomme des tokens pour redécouvrir ce qu'il aurait pu
savoir dès le départ. C'est le "canard sans tête".

La solution : **deux modes distincts, deux objectifs distincts.**

---

## Mode Exploration — Le premier passage

**Objectif** : dresser la carte de l'interface, identifier les sélecteurs stables.

**Règle** : lecture seule. Aucune action mutante.

**Invocations types :**

Exploration légère — vérifier la structure sans PNG (rapide, ~2 s économisées) :
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
```

Exploration complète — PNG annotés + arbre d'accessibilité :
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
```

Application Web Components (Angular, Lit, Stencil) :
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y --shadow-dom
```

**Ce qu'on extrait :**
- `boussole.url_courante` + `boussole.titre_page` → confirmation de l'URL effective et du titre de la page
- `capture_som` → PNG annoté avec IDs numériques des éléments interactifs
- `elements_som` → liste JSON des éléments (tag, role, texte, id)
- `a11y_tree` → arbre d'accessibilité YAML (champs, boutons, titres, structure)

**Ce qu'on cherche :**
1. Les sélecteurs des champs de formulaire (login, mot de passe, etc.)
2. Les IDs SoM ou attributs stables (`name`, `id`, `aria-label`, `data-*`)
3. Les éléments bloquants (bandeaux cookie, overlays, headers sticky)
4. Les comportements de navigation (SPA ou rechargement full HTTP ?)
5. Si l'interface est une SPA Angular/Lit : présence de Shadow Roots (activer `--shadow-dom`)

**Sortie attendue** : un fichier de scénario JSON dans `scenarios/` ou
`_CADRE/SPECIFICATIONS/PROCEDURES_LLM/instance/`.

---

## Rédaction de la carte — Le scénario JSON

Après l'exploration, on fige la procédure dans un fichier de scénario.

**Format de base :**
```json
{
  "nom": "pretix_login",
  "url": "https://target.local/control/login/",
  "intention": "Login administrateur via vault",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "post-login"}
  ]
}
```

**Règles de rédaction :**

| Priorité | Sélecteur | Quand l'utiliser |
|---|---|---|
| 1 | ID SoM | Élément visible dans la première capture |
| 2 | `[name=…]`, `[aria-label=…]`, `[id=…]` | Attribut stable, survit aux rechargements |
| 3 | `:has-text("…")` | Dernier recours, fragile en cas de traduction |

**Ce qu'on évite :**
- Les IDs SoM cross-session (non réutilisables entre invocations — REX friction #27)
- Les sélecteurs positionnels (`:first-child`, `:nth-child`) — fragiles
- Les IDs générés aléatoirement par les frameworks JS

---

## Mode Exécution — Les passages suivants

**Objectif** : rejouer la carte sans improvisation.

**Invocation :**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/pretix_login.json --som
```

**Zéro tâtonnement.** Le scénario a été validé en exploration. Si le scénario
échoue, c'est un signal : l'interface a changé. Il faut refaire une exploration,
pas improviser en ligne.

---

## Traiter les obstacles courants

### Bannière cookie / overlay bloquant

En exploration, noter la classe CSS de l'overlay. L'ajouter dans le scénario
avec `nettoyer_overlay` **avant** toute action et avant la génération SoM.

```json
{"type": "nettoyer_overlay", "selecteur": ".cookie-consent-banner, #gdpr-overlay"}
```

**Important :** `nettoyer_overlay` exige un sélecteur explicite. Ne jamais
activer dans les scénarios `watch.py` (masquerait les régressions visuelles).

### Attentes sur applications modernes (SPAs)

Remplacer les `pause` arbitraires par des primitives d'attente sémantiques
*(disponibles en v1.9)* :

```json
{"type": "attendre_url",               "motif": "/dashboard"},
{"type": "attendre_selecteur_present", "selecteur": "[data-testid='user-menu']"},
{"type": "attendre_absence",           "selecteur": ".loading-spinner"},
{"type": "attendre_reseau_calme",      "timeout_ms": 10000}
```

En attendant la v1.9, `{"type": "pause", "ms": 2000}` après un submit reste le
workaround établi (REX friction #16).

### Application Django avec redirections sudo

Les applications Django (Pretix, Django admin) redirigent certaines URLs
protégées via un middleware sudo. Séquence obligatoire en Mode A unique :
`login → reauth → cible` sans session intermédiaire.

Ne jamais utiliser `naviguer` dans une session reprise sur Django — il redirige
vers le dashboard (REX friction #50). Passer l'URL directement via `--url`.

---

## Mémoire sémantique — Lier scénario et documentation

**Séparation des responsabilités :**
Diwall fournit la **mécanique** (`/opt/diwall/skills/`, `journal.py --exporter-skill`).
La **mémoire sémantique** des scénarios validés appartient au projet qui utilise Diwall,
dans son propre `_CADRE/SPECIFICATIONS/PROCEDURES_LLM/`.

Pour chaque scénario validé, créer une fiche `SKILL_<nom>.md` dans le `_CADRE/`
du **projet utilisateur** (pas dans le `_CADRE/` de Diwall) :

**`SKILL_pretix_login.md`** (dans le _CADRE de votre projet) :
```markdown
---
skill: pretix-login
scenario: pretix_login.json
cible: __HOST_SERVICE__
type: skill-rejoue
derniere-validation: AAAA-MM-JJ
---

Login administrateur Pretix via vault credentials.
Prérequis : vault monté, fichier `__HOST_SERVICE__.json` présent.
```

La fiche est indexée par le RAG du projet. L'agent retrouve le skill par
recherche sémantique, lit la clé `scenario:`, exécute avec `rpa.py --scenario`.

Le gabarit de référence est `SKILL_TEMPLATE.md` dans `_CADRE/SPECIFICATIONS/PROCEDURES_LLM/`.

---

## Checklist d'exploration

Avant de rédiger un scénario :

- [ ] `shot.py --mode fast` lancé sur l'URL cible pour vérifier URL et titre (boussole)
- [ ] `shot.py --som --a11y` lancé pour la carte visuelle complète
- [ ] Si Angular / Lit / Web Components : relancer avec `--shadow-dom` pour les éléments dans les Shadow Roots
- [ ] PNG annoté lu et éléments identifiés
- [ ] Sélecteurs stables notés (attributs `name`, `id`, `aria-label`)
- [ ] Overlays bloquants repérés et leurs sélecteurs CSS notés
- [ ] Comportement SPA ou full-HTTP déterminé (`boussole.url_courante` vs `a11y_tree` heading)
- [ ] Si auth_indicator nécessaire : tester `--auth-indicator <sel>` [+ `--auth-indicator-negative <sel>` si sélecteur ambigu]
- [ ] Credentials vérifiés dans le vault pour ce domaine (`urlparse(url).hostname`)
- [ ] Scénario JSON rédigé et sauvegardé dans `scenarios/`
- [ ] Fiche `SKILL_<nom>.md` créée dans le `_CADRE/` du projet utilisateur (pas dans le `_CADRE/` de Diwall)
