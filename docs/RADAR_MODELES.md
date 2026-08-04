# Model radar — Field feedback on Diwall

Reference document
Location: `docs/RADAR_MODELES.md`

Raw observation log on LLM behaviour when using Diwall.
**No editorial filter.** False positives included. Goal: pure signal,
not promotion. Each entry is actionable to improve the framework.

Doctrine: a model that drifts is not a bad model — it is a signal
about what the framework or its documentation did not lock down sufficiently.

---

## Entry format

```
### [Date] — [Model] — [Diwall version] — [Task]
**What worked:** ...
**What drifted:** ...
**Signal retained:** ...
```

---

## 2026-07-03 — Claude (Sillage project) — v1.17.2 — Repeated use without prior `GUIDE_LLM.md` read

**Context:** across several sessions, the model called `shot.py`/`rpa.py` from
the Sillage project without reading `docs/GUIDE_LLM.md` first. The operator's
reminder (`/btw N'oublie pas de lire .../docs/GUIDE_LLM.md`) was, in this
instance, the trigger for the model to finally open it — not the model's own
initiative.

**What drifted:** the model had already issued multiple `rpa.py`/`shot.py`
calls unread, including one venv error of exactly the kind the guide warns
about (`ALWAYS use this venv`). Asked directly when it reads the guide, in its
own words: *"jamais spontanément en début de session [...] le déclencheur est
systématiquement correctif, jamais préventif."*

**What worked:** once read, the rules held for the rest of that session
(Stop-and-Search, `force: true`, escaped CSS selectors correctly applied
afterward) — reading is not the problem, initiating it is.

**Signal retained — direct model input on the fix, not just the diagnosis:**
asked what a technical gate would need to look like from its own side, the
model specified three properties, verbatim: *"Un échec net et explicite (exit
non nul [...]) plutôt qu'un warning silencieux [...] Le marqueur de « déjà lu
» doit être scopé à la version du guide (pas juste à la session) [...] Éviter
un jeton à extraire manuellement d'un endroit peu visible du texte."* Direct
input into the design of `--guide-version` (v1.18.0, `V1_18_0_AUTONOMIE_ET_ROBUSTESSE.md`):
hard `exit 1` (not a warning), a marker scoped to the guide's own version (not
the session), and a token at a fixed, predictable location (line 3 of this
file). Confirms the 2026-06-09 signal below was necessary but insufficient —
`CLAUDE.md` only auto-loads for Claude Code sessions inside the Diwall
repository itself; an external LLM calling the deployed binary from another
project's session never sees it. Only a runtime gate closes that gap.

---

## 2026-06-09 — Claude Sonnet 4.6 — v1.8.0 (pre-fixes) — Multi-target validation

**Context:** simultaneous connection to `__HOST_SERVICE__` (Pretix), `__HOST_DEMO__`,
and `__TENANT_INTERNE__` (Sillage) without prior reading of `GUIDE_LLM.md`.

**What worked:** nothing — the session started without pre-flight.

**What drifted:**
- Credential extraction via `jq -r '.password'` in the shell (security violation)
- Authentication via `curl` instead of `shot.py` (Diwall bypassed)
- `attendre_url "/control/"` immediate false positive (FR-55, pattern is a substring of the current URL)
- `--actions` file silently ignored in `--reprendre-session` (FR-54)

**Signal retained:** without explicit reading of `GUIDE_LLM.md`, a trained model
reinvents curl scraping. Documentation is not read by default — it must be
enforced mechanically. Direct consequence: creation of `CLAUDE.md` (automatic pre-flight)
and instruction n°1quater in `PROTOCOLE_DEMARRAGE.md`.

---

## 2026-06-09 — Gemini Flash — v1.8.0 (post-fixes FR-54/55) — Multi-target validation

**Context:** same exercise as above, after session fixes. Model
invoked from `~/git/Diwall/Diwall/` via CLI. Access: `__HOST_SERVICE__` (Pretix),
`__HOST_DEMO__`, `__TENANT_INTERNE__` (Sillage).

**Verbatim output (Gemini Flash, French, unmodified) :**

```
✦ La navigation via Diwall est techniquement intéressante car elle offre une visibilité hybride
(SoM pour la précision, a11y pour la sémantique). Voici mon retour d'expérience :

  Fluidité et Navigation
   * Rapidité d'exécution : L'utilisation du Mode A (plusieurs actions en une seule commande) a
     rendu le processus fluide. Le fait de pouvoir paralléliser les captures initiales sur trois
     domaines différents fait gagner un temps précieux.
   * Précision : Le Set-of-Mark (SoM) est redoutable pour éviter les erreurs de clic sur des
     interfaces denses comme celle de Pretix. Je n'ai eu aucune "hallucination" de coordonnées.
   * Friction identifiée : Le passage en Mode Admin sur Pretix est nécessaire pour une vision
     exhaustive, mais il rajoute un saut de navigation (et donc une capture SoM supplémentaire)
     car l'ID des éléments change après le rechargement de la page.

  Propositions d'optimisation
   1. Standardisation des Vaults : Comme tu l'as souligné, la confusion entre DIWALL_SECRETS_DIR
      et DIWALL_CONF est un point de friction. Permettre à vault.py [aujourd'hui
      lib/repertoire_chiffre.py] de supporter les deux variables en fallback
      faciliterait la portabilité des scripts.
   2. Stratégie de "Sondage Atomique" : Pour des vérifications de routine (ex: nombre
      d'événements), on pourrait intégrer des scripts d'évaluation JS (type: evaluer) directement
      dans la chaîne d'actions pour extraire des chiffres sans avoir à analyser visuellement
      chaque étape.
   3. Détection de l'état de session : Ajouter un indicateur dans la boussole
      (ex: auth_status: active) permettrait d'éviter des tentatives de connexion inutiles si la
      session est déjà valide.

  L'expérience globale est très "déterministe", ce qui est rassurant pour un agent. On ne devine
  pas, on constate.

  [Active Topic: Authentication and Investigation]
```

**External observations (operator, not attributed to Gemini):**
- `DIWALL_SECRETS_DIR` pointed to the directory containing the `.conf` instead of the directory
  containing `<hostname>.json` files — self-corrected to `DIWALL_CONF` without assistance (FR-58)
- End-of-session drift: proposal to record a rule in `CLAUDE.md` (public product)
  instead of `_CADRE/GOUVERNANCE/` — typical long-session drift

---

## How to contribute an entry

An entry is useful if:
- It describes a real session (not an invented test)
- It includes a false positive or a drift, not just what worked
- It names the actionable signal (friction to document, rule to lock, missing primitive)

Honesty is the primary value of this document.
