# Diwall — Exploration and mapping guide

Version 1.1 — June 2026 (v1.14.0)

**This document is for language models using Diwall.**

It describes the "Exploration before Execution" protocol: how to map an unknown
interface soberly, then automate it without improvisation.

---

## The problem this guide solves

A model launched on an unknown interface without preparation navigates blind:
it fumbles, retries, burns tokens to rediscover what it could have
known from the start. This is the "headless chicken" problem.

The solution: **two distinct modes, two distinct objectives.**

---

## Exploration Mode — The first pass

**Objective**: draw the interface map, identify stable selectors.

**Rule**: read-only. No mutating action.

**Typical invocations:**

Light exploration — check structure without PNG (fast, ~2 s saved):
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
```

Full exploration — annotated PNG + accessibility tree:
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
```

Web Components application (Angular, Lit, Stencil):
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y --shadow-dom
```

**What to extract:**
- `boussole.url_courante` + `boussole.titre_page` → confirmation of effective URL and page title
- `capture_som` → annotated PNG with numeric IDs on interactive elements
- `elements_som` → JSON list of elements (tag, role, text, id)
- `a11y_tree` → YAML accessibility tree (fields, buttons, headings, structure)

**What to look for:**
1. Selectors for form fields (login, password, etc.)
2. SoM IDs or stable attributes (`name`, `id`, `aria-label`, `data-*`)
3. Blocking elements (cookie banners, overlays, sticky headers)
4. Navigation behaviour (SPA or full HTTP reload?)
5. If the interface is an Angular/Lit SPA: presence of Shadow Roots (activate `--shadow-dom`)

**Expected output**: a JSON scenario file in `scenarios/` or
`_CADRE/SPECIFICATIONS/PROCEDURES_LLM/instance/`.

---

## Writing the map — The JSON scenario

After exploration, the procedure is locked into a scenario file.

**Basic format:**
```json
{
  "nom": "pretix_login",
  "url": "https://target.local/control/login/",
  "intention": "Administrator login via vault",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "post-login"}
  ]
}
```

**Writing rules:**

| Priority | Selector | When to use |
|---|---|---|
| 1 | SoM ID | Element visible in the first capture |
| 2 | `[name=…]`, `[aria-label=…]`, `[id=…]` | Stable attribute, survives reloads |
| 3 | `:has-text("…")` | Last resort, fragile under translation |

**What to avoid:**
- Cross-session SoM IDs (not reusable between invocations — REX friction #27)
- Positional selectors (`:first-child`, `:nth-child`) — fragile
- Framework-generated random IDs

---

## Execution Mode — Subsequent passes

**Objective**: replay the map without improvisation.

**Invocation:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/pretix_login.json --som
```

**Zero fumbling.** The scenario was validated in exploration. If the scenario
fails, it is a signal: the interface has changed. Re-run exploration,
do not improvise in-line.

---

## Handling common obstacles

### Cookie banner / blocking overlay

In exploration, note the CSS class of the overlay. Add it to the scenario
with `nettoyer_overlay` **before** any action and before SoM generation.

```json
{"type": "nettoyer_overlay", "selecteur": ".cookie-consent-banner, #gdpr-overlay"}
```

**Important:** `nettoyer_overlay` requires an explicit selector. Never
activate in `watch.py` scenarios (would mask visual regressions).

### Waiting in modern applications (SPAs)

Replace arbitrary `pause` with semantic wait primitives
*(available in v1.9)* :

```json
{"type": "attendre_url",               "motif": "/dashboard"},
{"type": "attendre_selecteur_present", "selecteur": "[data-testid='user-menu']"},
{"type": "attendre_absence",           "selecteur": ".loading-spinner"},
{"type": "attendre_reseau_calme",      "timeout_ms": 10000}
```

Until v1.9, `{"type": "pause", "ms": 2000}` after a submit remains the
established workaround (REX friction #16).

### Django application with sudo redirects

Django applications (Pretix, Django admin) redirect some protected URLs
via a sudo middleware. Mandatory sequence in a single Mode A call:
`login → reauth → target` without intermediate session.

Never use `naviguer` in a resumed session on Django — it redirects
to the dashboard (REX friction #50). Pass the URL directly via `--url`.

---

## Semantic memory — Linking scenario and documentation

**Separation of concerns:**
Diwall provides the **mechanics** (`/opt/diwall/skills/`, `journal.py --exporter-skill`).
The **semantic memory** of validated scenarios belongs to the project using Diwall,
in its own `_CADRE/SPECIFICATIONS/PROCEDURES_LLM/`.

For each validated scenario, create a `SKILL_<name>.md` file in the `_CADRE/`
of the **user project** (not in Diwall's `_CADRE/`):

**`SKILL_pretix_login.md`** (in your project's _CADRE):
```markdown
---
skill: pretix-login
scenario: pretix_login.json
cible: __HOST_SERVICE__
type: skill-rejoue
derniere-validation: YYYY-MM-DD
---

Administrator Pretix login via vault credentials.
Prerequisites: vault mounted, `__HOST_SERVICE__.json` file present.
```

The file is indexed by the project's RAG. The agent finds the skill by
semantic search, reads the `scenario:` key, executes with `rpa.py --scenario`.

The reference template is `SKILL_TEMPLATE.md` in `_CADRE/SPECIFICATIONS/PROCEDURES_LLM/`.

---

## Exploration checklist

Before writing a scenario:

- [ ] `shot.py --mode fast` run on the target URL to verify URL and title (boussole)
- [ ] `shot.py --som --a11y` run for the full visual map
- [ ] If Angular / Lit / Web Components: re-run with `--shadow-dom` for elements inside Shadow Roots
- [ ] Annotated PNG read and elements identified
- [ ] Stable selectors noted (attributes `name`, `id`, `aria-label`)
- [ ] Blocking overlays spotted and their CSS selectors noted
- [ ] SPA or full-HTTP behaviour determined (`boussole.url_courante` vs `a11y_tree` heading)
- [ ] If auth_indicator needed: test `--auth-indicator <sel>` [+ `--auth-indicator-negative <sel>` if selector is ambiguous]
- [ ] Credentials verified in vault for this domain (`urlparse(url).hostname`)
- [ ] JSON scenario written and saved in `scenarios/`
- [ ] `SKILL_<name>.md` file created in the user project's `_CADRE/` (not in Diwall's `_CADRE/`)
