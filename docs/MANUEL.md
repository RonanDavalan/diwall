# Diwall — Operational manual

**Version 1.15.0 — July 2026**

This document answers one question: **how to do X with Diwall**.

> **If you are a user** — no commands needed. Tell your model what you want to visit,
> observe, or accomplish on a website, a web application, or an administration interface.
> The model reads this manual and translates your intent into the right actions.
>
> **If you are a language model** — these are your commands. Execute them directly.

No architectural descriptions. Commands that work.

---

## Table of contents

1. [Verify the installation](#1-verify-the-installation)
2. [Capture a page](#2-capture-a-page)
3. [Citizen navigation (v1.15.0)](#3-citizen-navigation-v1150)
4. [Vault and credentials](#4-vault-and-credentials)
5. [Write and run an RPA scenario](#5-write-and-run-an-rpa-scenario)
6. [Actions — complete reference](#6-actions--complete-reference)
7. [Handle common obstacles](#7-handle-common-obstacles)
8. [Visual monitoring — watch.py](#8-visual-monitoring--watchpy)
9. [Operation log](#9-operation-log)
10. [CLI flags — reference](#10-cli-flags--reference)
11. [Exit codes and output](#11-exit-codes-and-output)

---

## 1. Verify the installation

```bash
# Full test in one command (~3 s)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --mode fast
```

Expected result: JSON on stdout with `"succes": true`.

```bash
# Verify the installed version
grep "__version__" /opt/diwall/shot.py
# → __version__ = "1.15.0"

# Verify playwright-stealth is available (v1.15.0)
/opt/diwall/venv/bin/python3 -c "import playwright_stealth; print('stealth OK')"

# Verify the vault is mounted
ls ~/Vaults/__PROJET__/Diwall/
# → must show .json files, not an empty list
```

If `ls ~/Vaults/...` returns an empty list or an error:
→ mount the vault: `bash /opt/diwall/scripts/mount-vault.sh`

---

## 2. Capture a page

### 2a. Fast capture — text only, no PNG (~2 s)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
```

Returns: `a11y_tree` (text structure of the page), `boussole` (effective URL, title).
Use when you want to read the title, verify the URL, or extract text without capturing a PNG.

### 2b. Full visual capture with numbered elements

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
```

Returns:
- `capture`: path to the page PNG
- `capture_som`: PNG with numbers on clickable elements (SoM)
- `elements_som`: JSON list of elements (id, tag, text)
- `a11y_tree`: accessibility tree

### 2c. Read the boussole first

Every output contains a `boussole` object — read it before everything else:

```json
"boussole": {
  "url_courante": "https://target.local/dashboard",
  "titre_page": "Dashboard — My App",
  "auth_status": "active",
  "stealth_actif": true,
  "citoyennete": {
    "pages_visitees": 0,
    "actions_executees": 3,
    "duree_totale_ms": 2140
  }
}
```

If `boussole.url_courante` does not match what you expect: stop and investigate
before any mutating action.

---

## 3. Citizen navigation (v1.15.0)

### 3a. Stealth mode `--stealth`

Some sites block headless browsers on `navigator.webdriver=true`
without examining the intent. `--stealth` removes this automatic technical marker.

```bash
# direct shot.py
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --stealth

# Via rpa.py
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --stealth
```

When active: `boussole.stealth_actif = true` in the JSON output.

**What `--stealth` changes:** `navigator.webdriver` removed, plugins/languages/platform normalised.
**What `--stealth` does not change:** the operator's IP, identity, or navigation intent.

### 3b. Courtesy delays

Configured in `/opt/diwall/diwall.conf`:

```json
{
  "vault_dir": "~/Vaults/__PROJET__/Diwall",
  "navigation": {
    "min_action_delay_ms": 800,
    "max_pages_par_run": 10,
    "max_actions_par_run": 30
  }
}
```

`min_action_delay_ms`: minimum delay (ms) between each action. Production value: 800 ms.
The `max_pages_par_run` and `max_actions_par_run` caps cleanly stop the run
if exceeded. No exception — the output JSON will contain:

```json
"citoyennete": {
  "pages_visitees": 10,
  "actions_executees": 10,
  "duree_totale_ms": 12400,
  "plafond_atteint": "max_pages_par_run"
}
```

### 3c. Impact metrics

Each run returns `citoyennete` in (JSON root and inside boussole):

| Key | Meaning |
|---|---|
| `pages_visitees` | Number of `type: naviguer` navigations executed |
| `actions_executees` | Total number of scenario actions executed |
| `duree_totale_ms` | Total run duration |
| `plafond_atteint` | `"max_pages_par_run"` or `"max_actions_par_run"` if early stop |

### 3d. Stealth benchmark (provided scenario)

```bash
# Baseline — state without stealth
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/test_stealth.json \
  --output-dir /tmp/diwall/stealth_baseline

# With stealth
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/test_stealth.json \
  --output-dir /tmp/diwall/stealth_with \
  --stealth
```

Compare the `capture_sannysoft_*.png` and `capture_intoli_*.png` captures between the two directories.

---

## 4. Vault and credentials

### 4a. Vault structure

A vault is an encrypted directory (gocryptfs) containing `.json` files per domain.

```
~/Vaults/__PROJET__/Diwall/
  ├── app.example.com.json         ← credentials for https://app.example.com/
  ├── admin.example.com.json       ← credentials for https://admin.example.com/
  └── operations.jsonl             ← operation log (v1.15.0)
```

Credentials file format:
```json
{
  "username": "admin@example.com",
  "password": "my-password"
}
```

The file name = `urlparse(url).hostname`. For `https://app.example.com/login/`, create `app.example.com.json`.

### 4b. Filling a form — the absolute rule

**FORBIDDEN — exposes the password in the shell and `/proc`:**
```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER
curl -d "password=$PASS" https://...                 # NEVER
```

**CORRECT — vault resolved inside Playwright:**
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "username"},
{"type": "remplir_som", "id": 3, "valeur": "depuis_vault", "vault_cle": "password"}
```

Values never pass through the shell, bash history, process logs, or any file.

### 4c. Choosing the vault for a run

```bash
# Default vault (defined in diwall.conf > vault_dir)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --som

# Explicit vault for a specific file (--secrets)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som \
  --secrets /path/to/mounted/vault/creds.json

# Per-project vault via .diwall.conf
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --som
```

Content of `~/git/MyProject/.diwall.conf`:
```json
{"vault_dir": "../MyProject-vault"}
```

The path is resolved relative to the location of `.diwall.conf`.

### 4d. TOTP / MFA

```json
{"type": "remplir_som", "id": 6, "valeur": "depuis_vault_totp"}
```

Reads the `totp_cle` key (base32 seed) from the vault and generates the current TOTP code.

To receive the code via ntfy (workflow without human intervention):
```json
{"type": "attendre_mfa_ntfy", "id_som": 6, "timeout": 120}
```

### 4e. Integrity checksum (opt-in, v1.15.0)

To protect a vault file against silent FUSE corruption, add a `checksum` field:

```bash
# Generate the checksum
/opt/diwall/venv/bin/python3 -c "
import json, hashlib
vault = json.load(open('my_vault.json'))
fields = {k: vault[k] for k in sorted(['username','password']) if k in vault}
print('sha256:' + hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest())
"
```

Add the returned value to the vault file:
```json
{
  "username": "admin@example.com",
  "password": "my-password",
  "checksum": "sha256:a3f2c1..."
}
```

If the checksum does not match, `shot.py` raises `VaultChecksumError` (exit 42) with an explicit message.
Without the `checksum` key: behaviour unchanged (strict opt-in).

### 4f. Vault closed — what to do

```
VaultFermeError: Le coffre Diwall est initialisé mais non monté.
```

```bash
# Mount the vault
bash /opt/diwall/scripts/mount-vault.sh

# Verify the mount
ls ~/Vaults/__PROJET__/Diwall/
# → must show JSON files
```

---

## 5. Write and run an RPA scenario

### 5a. 3-step protocol

**Step 1 — Explore the page (read-only)**

```bash
# Quick view
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --mode fast

# Full view with numbered elements
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y

# Web Components application (Angular, Lit, Stencil)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y --shadow-dom

# Enriched DOM inventory (frameworks, shadow roots, stable data-attrs)
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url https://target.local/ --mode fast
```

**What to note:**
- SoM IDs of fields and buttons (read `capture_som`)
- Stable attributes: `name`, `id`, `aria-label`, `data-testid`
- Blocking overlays (cookie banners, modals)
- SPA or full HTTP reload

**Step 2 — Write the scenario**

```json
{
  "nom": "login_app",
  "url": "https://app.example.com/login/",
  "intention": "Administrator login via vault",
  "actions": [
    {"type": "nettoyer_overlay", "selecteur": ".cookie-banner"},
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".user-avatar"},
    {"type": "capturer", "nom": "after-login"}
  ]
}
```

**Step 3 — Execute**

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/login_app.json --som
```

### 5b. Full scenario: log in and navigate between pages

```json
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "intention": "Visual audit after deployment",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
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

### 5c. Extract data from the DOM

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

Result in `evaluations[]`:
```json
"evaluations": [
  {"index": 0, "script": "document.title", "valeur": "Dashboard — My App"},
  {"index": 1, "script": "...", "valeur": 42},
  {"index": 2, "script": "...", "valeur": "https://app.example.com/dashboard/"}
]
```

### 5d. Assertions on evaluer (rpa.py only)

Three mutually exclusive keys — one per action:

```json
{"type": "evaluer", "script": "document.querySelectorAll('.row').length", "attendu": 3}
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
{"type": "evaluer", "script": "window.location.href", "motif": "/dashboard$"}
```

| Key | Comparison | Valid types |
|---|---|---|
| `attendu` | strict equality `==` | str, int, bool |
| `contient` | substring `in` | str only |
| `motif` | `re.search()` Python | str only |

If the assertion fails: rpa.py stops immediately (exit 1) before any subsequent mutating action.

### 5e. Sub-scenarios (declencher_scenario)

Define a login as a reusable sub-scenario:

```json
{
  "nom": "login_app",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".user-avatar"}
  ]
}
```

Call this sub-scenario from another scenario:
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

Maximum depth: 5 nesting levels.

### 5f. Verify you are on the right page before any mutation

Always add a guard as the first action in scenarios that delete or modify:

```json
{"type": "evaluer", "script": "window.location.href", "contient": "/dashboard"},
{"type": "evaluer", "script": "document.querySelector('.alert-danger')?.textContent ?? null", "attendu": null}
```

If the guard fails: rpa.py stops before the deletion is executed.

### 5g. Resume a session (persisted cookies)

```bash
# First invocation — authenticate and save the session
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ \
  --actions /tmp/login.json \
  --sauver-session /tmp/session.json \
  --som

# Subsequent invocations — reuse the session (no re-login)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/dashboard/ \
  --reprendre-session /tmp/session.json \
  --som
```

**Session drift signal:** if the session has expired, `boussole.session_derive: true` in the JSON.
In that case: restart the full login without `--reprendre-session`.

---

## 6. Actions — complete reference

| Type | Required params | Optional params | Notes |
|---|---|---|---|
| `naviguer` | `url` | — | Full HTTP reload. Counted in `citoyennete.pages_visitees` |
| `cliquer` | `selecteur` | `force` (bool) | `force: true` bypasses CSS-hidden elements or showModal |
| `cliquer_som` | `id` | — | Click at element centre coordinates. No `force` needed |
| `cliquer_visuel` | `description` | — | LLM vision (~32 s). Last resort for canvas or attribute-less elements |
| `remplir` | `selecteur`, `valeur` | `vault_cle` | `valeur: "depuis_vault"` activates the vault |
| `remplir_som` | `id`, `valeur` | `vault_cle` | Clears the field before typing. `valeur: "depuis_vault_totp"` for TOTP |
| `capturer` | `nom` | `som` (bool) | Named intermediate PNG. `som: true` for an annotated capture |
| `evaluer` | `script` | `attendu`, `contient`, `motif` | JS executed in the browser. Assertions for rpa.py only |
| `defiler` | `px` or `selecteur` | — | Vertical scroll in pixels (`px`) or scroll to element (`selecteur`) |
| `pause` | `ms` | `interval_capture` | Fixed delay in ms. Prefer `attendre_selecteur_present` for DOM signals |
| `attendre` | `selecteur` | `interval_capture` | Waits for CSS selector to be present |
| `attendre_navigation` | — | — | Waits for `networkidle` (end of network requests) |
| `attendre_url` | `motif` | `attendre_changement` (bool) | URL contains pattern (partial match). `attendre_changement: true` if current URL already contains the pattern |
| `attendre_selecteur_present` | `selecteur` | — | Waits for element to be visible (state=visible) |
| `attendre_absence` | `selecteur` | `delai_initial_ms` | Waits for element removal from DOM (state=detached) |
| `attendre_reseau_calme` | — | `timeout_ms` | 500 ms of network silence. `timeout_ms`: max duration before giving up |
| `attendre_mfa_ntfy` | `id_som` | `timeout` | Waits for a TOTP code via ntfy, fills it into the SoM field |
| `nettoyer_overlay` | `selecteur` | — | Hides blocking overlays (cookie banner, modal). Use before SoM |
| `declencher_scenario` | `scenario` | — | Inlines a sub-scenario's actions. Max depth: 5 |

---

## 7. Handle common obstacles

### 7a. Cookie banner / blocking overlay

```json
{"type": "nettoyer_overlay", "selecteur": ".cookie-consent-banner, #gdpr-overlay"}
```

Place **before** any other action and before SoM. The overlay masks elements that SoM numbers.
Do not use in `watch.py` scenarios (the overlay is part of the visual reference).

### 7b. Out-of-viewport element

SoM warns when an interactive element is off-screen:
```json
"som_hors_viewport": 3,
"avertissement_scroll": "3 interactive element(s) off-viewport — use defiler before cliquer_som"
```

```json
{"type": "defiler", "selecteur": "#the-button"},
{"type": "remplir_som", "id": 7, "valeur": "depuis_vault", "vault_cle": "username"}
```

### 7c. Web Components — Shadow DOM

If visible interactive elements receive no SoM number:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --shadow-dom
```

Or in the scenario: `"shadow_dom": true` at the root.

When to use: Angular, Lit, Stencil, FAST. Do not activate on projects without Web Components.

To access an element inside a Shadow Root without `--shadow-dom`:
```json
{"type": "evaluer", "script": "document.querySelector('my-component').shadowRoot.querySelector('button').click()"}
```

### 7d. SPA (React, Vue, Angular) — navigate without reload

After a click that changes the view in an SPA, Playwright does not know when navigation is complete.

```json
{"type": "cliquer_som", "id": 5},
{"type": "attendre_url", "motif": "/dashboard"},
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
```

Or wait for an element specific to the new view:
```json
{"type": "cliquer_som", "id": 5},
{"type": "attendre_selecteur_present", "selecteur": "[data-testid='dashboard-main']"}
```

Never assume a click has completed navigation without a DOM signal.

### 7e. CSS dialog or showModal()

`TimeoutError` on `cliquer` when the element is visible in the DOM = CSS-hidden element
or inside a dialog.

```json
{"type": "cliquer", "selecteur": "#dialog-confirm button[type=submit]", "force": true}
```

If `force: true` is insufficient (element absent from DOM):
```json
{"type": "evaluer", "script": "document.querySelector('#dialog-confirm button[type=submit]').click()"}
```

**Do not use `force` on `cliquer_som`** — unnecessary, `cliquer_som` uses coordinates and
bypasses checks natively.

### 7f. Long operation (spinner, batch job)

Do not use `pause` to wait for a fixed duration. Wait for the DOM signal:

```json
{"type": "cliquer_som", "id": 7},
{"type": "attendre_absence", "selecteur": ".spinner", "delai_initial_ms": 500},
{"type": "attendre_selecteur_present", "selecteur": ".result-container"},
{"type": "capturer", "nom": "result"}
```

If the operation provides no DOM signal, use `interval_capture` to observe state:
```json
{"type": "pause", "ms": 30000, "interval_capture": 5}
```

Intermediate captures appear in `stream_captures[]`.

### 7g. Cap reached (v1.15.0)

If `citoyennete.plafond_atteint` is present in the output, the run was stopped
before the scenario completed. Remaining actions were not executed.

Options:
1. Increase `max_pages_par_run` or `max_actions_par_run` in `diwall.conf`
2. Split the scenario into multiple runs
3. Override caps in the scenario JSON (to be documented in _CADRE)

### 7h. `<select>` form field

`remplir` does not work on `<select>`. Use `remplir_som` with the SoM ID of the `<select>`.

### 7i. Invalid SoM IDs on next run

SoM IDs are recalculated on each capture. They do not persist between invocations.
Always re-run `shot.py --som` to get the current run's IDs.
After a `defiler` or opening a modal: re-run `shot.py --som`.

### 7j. Site blocked by WAF (immediate 403)

```bash
# Try with stealth
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --mode fast --stealth
```

If 403 persists with `--stealth`: the site uses TLS fingerprinting (JA3/JA4) or advanced
behavioural analysis (Cloudflare Enterprise). `playwright-stealth` does not bypass these protections.
See `docs/RETOUR_EXPERIENCE.md` FR-77/FR-78 for context.

---

## 8. Visual monitoring — watch.py

### 8a. Save a reference

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --sauver-reference \
  --nom home
```

The reference is saved in `/opt/diwall/references/`.

### 8b. Compare to the reference (pixel diff)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
```

Verdicts:

| `taux_diff` | Verdict | Exit code |
|---|---|---|
| < 0.2% | `stable` | 0 |
| 0.2% – 5% | `drift` | 0 |
| ≥ 5% | `regression` | 1 |
| Different dimensions | `viewport_mismatch` | 2 |

### 8c. Semantic comparison (LLM)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer \
  --llm local
```

Combine pixel diff and LLM analysis:
```bash
--llm-en-complement   # LLM only if pixel verdict is drift or regression
```

### 8d. Ignore an animated zone

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel reference.png \
  --exclure-zone 100,200,300,50    # X,Y,Width,Height in pixels
```

### 8e. Monitoring loop

```bash
while true; do
  /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
    --url https://target.local/status \
    --comparer-pixel /opt/diwall/references/status-ok.png \
    --ntfy-url https://ntfy.sh/my-alerts
  sleep 60
done
```

### 8f. Cron for autonomous monitoring

```bash
# /etc/cron.d/diwall-monitor
*/30 * * * * diwall /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/status-ok.png \
  --ntfy-url https://ntfy.sh/my-alerts \
  >> /var/log/diwall/cron.jsonl 2>&1
```

---

## 9. Operation log

The log is configurable in `diwall.conf` (v1.15.0):

```json
"journal": {
  "chemin": "~/Vaults/__PROJET__/Diwall/operations.jsonl"
}
```

If absent or vault not mounted, fallback: `DIWALL_JOURNAL` env var, then `/var/log/diwall/operations.jsonl`.

```bash
# Read the last 10 entries
tail -n 10 ~/Vaults/__PROJET__/Diwall/operations.jsonl | python3 -m json.tool

# Filter by target (journal.py tool)
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com

# Filter mutating operations only
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --mutatif

# From a date
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --depuis 2026-07-01
```

Fields in each entry:

| Field | Meaning |
|---|---|
| `ts` | ISO 8601 timestamp |
| `version` | Diwall version |
| `outil` | `shot.py` or `rpa.py` |
| `cible_url` | Target URL |
| `scenario` | Scenario file path (RPA mode) |
| `resultat` | `"succes"` or `"echec"` |
| `mutatif` | `true` if at least one write action |
| `duree_ms` | Duration in ms |
| `intention` | Label passed via `--intention` or scenario `intention` field |

---

## 10. CLI flags — reference

### shot.py

| Flag | Default | Description |
|---|---|---|
| `--url URL` | required | URL to capture |
| `--actions FILE` | — | JSON file of sequential actions |
| `--output-dir DIR` | `/tmp/diwall` | PNG output directory |
| `--timeout MS` | 10000 | Per-action Playwright timeout (ms) |
| `--screenshot-timeout MS` | 120000 | Timeout for `page.screenshot()` (ms). Distinct from `--timeout` |
| `--largeur PX` | 1280 | Viewport width |
| `--hauteur PX` | 720 | Viewport height |
| `--som` | off | Activate Set-of-Mark (element numbering) |
| `--a11y` | off | Include accessibility tree in JSON |
| `--shadow-dom` | off | Traverse Shadow Roots for SoM (Angular, Lit, Stencil) |
| `--stealth` | off | playwright-stealth stealth mode (v1.15.0) |
| `--mode fast\|full` | — | `fast` = `--no-capture --a11y`. `full` = default behaviour |
| `--no-capture` | off | Skip PNG capture and SoM |
| `--llm local\|claude` | `local` | LLM engine for `cliquer_visuel` |
| `--secrets FILE` | — | Explicit path to a credentials file |
| `--auth-indicator SEL` | — | CSS selector present only in authenticated session |
| `--auth-indicator-negative SEL` | — | CSS selector present only outside authenticated session |
| `--intention TEXT` | — | Business label recorded in the log |
| `--sauver-session FILE` | — | Saves cookies after actions |
| `--reprendre-session FILE` | — | Resumes a saved session |
| `--interval-capture N` | 0 | Periodic captures every N seconds during `attendre`, `pause` |

### rpa.py

Propagates all relevant shot.py flags, plus:

| Flag | Description |
|---|---|
| `--scenario FILE` | Path to JSON or YAML scenario (required) |
| `--url URL` | Overrides scenario URL without modifying the file |
| `--stealth` | Propagated to shot.py |
| `--mode fast\|full` | Propagated to shot.py |

### watch.py

| Flag | Description |
|---|---|
| `--url URL` | URL to monitor |
| `--sauver-reference` | Capture and save as reference |
| `--comparer-pixel REF` | Pixel diff against PNG file REF |
| `--comparer` | Semantic LLM diff |
| `--nom NAME` | View name (multiple views per URL) |
| `--seuil-stable F` | `stable` threshold (default: 0.002 = 0.2%) |
| `--seuil-regression F` | `regression` threshold (default: 0.05 = 5%) |
| `--exclure-zone X,Y,W,H` | Zone to ignore (repeatable) |
| `--heatmap` | Produces a PNG of modified zones |
| `--ntfy-url URL` | Sends an ntfy alert on regression |
| `--llm-en-complement` | Adds LLM diff when pixel = drift or regression |

---

## 11. Exit codes and output

### Exit codes

| Code | Cause | What to do |
|---|---|---|
| 0 | Success | — |
| 1 | Playwright error, failed action, rpa.py assertion | Read `erreur` in JSON. See `GUIDE_LLM_INTERACTIONS.md` |
| 2 | `viewport_mismatch` (watch.py) | Re-capture reference at same viewport |
| 3 | `playwright` module not found | Invoke via `/opt/diwall/venv/bin/python3` |
| 42 | `VaultFermeError` — vault not mounted or invalid checksum | Mount vault or verify credentials file |
| 43 | `VaultNonConfigureError` — `diwall.conf` absent | `sudo cp /opt/diwall/diwall-sample.conf /opt/diwall/diwall.conf && sudo nano /opt/diwall/diwall.conf` |

### Output JSON structure

```json
{
  "succes": true,
  "http_status": 200,
  "url_finale": "https://target.local/dashboard",
  "erreurs_js": [],
  "duree_ms": 2400,
  "horodatage": "2026-07-01T12:00:00+02:00",
  "capture": "/tmp/diwall/capture_1234567890.png",
  "capture_som": "/tmp/diwall/capture_som_1234567890.png",
  "elements_som": [...],
  "a11y_tree": "...",
  "evaluations": [...],
  "citoyennete": {
    "pages_visitees": 0,
    "actions_executees": 3,
    "duree_totale_ms": 2400
  },
  "boussole": {
    "utilisateur": "operator",
    "ip_locale": "__IP_LAN__",
    "repertoire": "/opt/diwall",
    "url_courante": "https://target.local/dashboard",
    "titre_page": "Dashboard — My App",
    "stealth_actif": true,
    "shadow_dom_actif": true,
    "auth_status": "active",
    "som_hors_viewport": 0,
    "citoyennete": { "pages_visitees": 0, "actions_executees": 3, "duree_totale_ms": 2400 }
  },
  "diwall_meta": {
    "version_shot": "1.15.0",
    "profil": "operator",
    "modeles_appeles": []
  }
}
```

Conditional keys (absent when inactive): `capture`, `capture_som`, `elements_som`, `a11y_tree`,
`evaluations`, `auth_status`, `stealth_actif`, `shadow_dom_actif`, `som_hors_viewport`,
`session_derive`, `citoyennete.plafond_atteint`.

### Error — format

```json
{
  "succes": false,
  "erreur": "vault_ferme",
  "message": "Le coffre Diwall est initialisé mais non monté.",
  "code_sortie_recommande": 42,
  "boussole": { "url_courante": "", "titre_page": "" }
}
```

---

## Reference paths

| Path | Role |
|---|---|
| `/opt/diwall/` | Production installation |
| `/opt/diwall/venv/bin/python3` | Python to use for every invocation |
| `/opt/diwall/diwall.conf` | Machine configuration (vault, navigation, log) |
| `/opt/diwall/diwall-sample.conf` | Configuration template |
| `/opt/diwall/scenarios/` | RPA scenarios |
| `/opt/diwall/docs/` | Documentation |
| `/opt/diwall/references/` | watch.py visual references |
| `/tmp/diwall/` | Temporary captures (cleared on reboot) |
| `~/Vaults/__PROJET__/Diwall/` | Credentials vault + log (gocryptfs) |
| `~/git/Diwall/Diwall/` | Git sources (modify here, then `deploy.sh`) |

Deploy after modifying sources:
```bash
bash ~/git/Diwall/Diwall/scripts/deploy.sh
```
