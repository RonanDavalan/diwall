# Diwall — Human operator guide

Version 1.2 — June 2026 (v1.14.0)

---

## Why Diwall — what you actually delegate

### The problem Diwall solves

When you work with an LLM on a web application, a perception asymmetry occurs:
the model reads code, runs commands, observes textual output — but it does not see
the interface your users see. You do.

This asymmetry creates a specific form of anxiety: you don't know whether what
the model describes matches what you would see in a browser. To be sure, you must
either trust it at its word, or verify it yourself.

Diwall solves this problem by creating a **shared visual reference**:
the model captures the interface with a real browser (headless Chromium),
and you have access to the same PNG captures and accessibility trees.
You no longer take the model at its word — you observe the same state it does.

### What you delegate

Diwall lets you delegate **repetitive and anxiety-inducing visual verification**:

- Checking that 20 pages of a site display correctly after a deployment
- Confirming that a login form works on the right interface
- Ensuring a deployment did not break the rendering of a critical view
- Visually validating that a fix is correctly visible on screen

Without Diwall, these verifications are your responsibility. With Diwall, the model
performs them and reports the result — with visual proof.

### What you keep

You keep **high-level sense validation**: deciding whether the result
the model presents is acceptable, consistent with your expectations, and in line
with what your users should see. That decision remains yours.

### When Diwall is the right tool

| Use case | Diwall suitable? |
|---|---|
| Visual validation after deployment | ✓ Yes |
| Diagnosing a broken rendering | ✓ Yes |
| Navigation and form input (~30 s max) | ✓ Yes |
| Delegating repetitive checks | ✓ Yes |
| Long server operation (cloning ~2–5 min) | ✗ No — Playwright timeout |
| Bulk deletion or mutation | ✗ No — prefer a direct API call |
| Workflow requiring rollback | ✗ No — Diwall cannot undo |

For discouraged cases, see `docs/GUIDE_LLM.md` section "When NOT to use Diwall"
(frictions FR-59 and FR-60 documented).

---

**This document is for human operators using Diwall.**

It complements `GUIDE_LLM.md` (intended for models) with concrete examples,
step-by-step procedures, and reminders on common stumbling points.

---

## Prerequisites before starting

```bash
# 1. Verify Diwall responds
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --som --a11y
# → must return {"succes": true, ...}

# 2. Verify the vault is mounted (if gocryptfs)
ls ~/Vaults/Diwall/
# → must show .json files, not encrypted content

# 3. Verify credentials for a domain
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.vault import lire_credential
print('OK' if lire_credential('target.local', 'password') else 'EMPTY')
"
```

---

## Vault configuration per project

Each project can have its own vault. Two methods:

**Method 1 — Direct environment variable (one-shot):**
```bash
DIWALL_VAULT_DIR=~/Vaults/MyProject \
  /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

**Method 2 — Project `.diwall.conf` file (recommended for recurring projects):**
```bash
# Create the file at the project root
echo '{"vault_dir": "../MyProject-vault"}' > ~/git/MyProject/.diwall.conf

# Then prefix each invocation (or export at the start of the shell session)
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

The `vault_dir` in `.diwall.conf` can be a relative path — it is resolved
relative to the location of the `.diwall.conf` file.

---

## Capturing a page and analysing it

```bash
# Quick check (no PNG — ~2 s, read-only)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
# → returns url_courante, titre_page, a11y_tree in the JSON

# Full capture with numbered elements
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
# The PNG capture is in /tmp/diwall/capture_<ts>.png
```

**What you get:**
- `boussole.url_courante` + `boussole.titre_page`: effective URL and title after navigation
- `capture`: path to the PNG of the page as rendered
- `capture_som`: annotated PNG with element numbers
- `a11y_tree`: page structure in text (headings, fields, buttons)

---

## Automating a login form

**Step 1** — Prepare credentials in the vault.

The vault file is named `<hostname>.json` where `hostname` = result of
`urlparse(url).hostname`. For `https://app.example.com/`, the file is
`app.example.com.json`.

```json
{"username": "admin@example.com", "password": "my-secret"}
```

**Step 2** — Explore the login page.
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ --som --a11y
```
Open the annotated PNG (`capture_som`) to identify the SoM IDs of the fields.

**Step 3** — Write the scenario.
```bash
cat > /tmp/login.json << 'EOF'
{
  "nom": "app_login",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "after-login"}
  ]
}
EOF
```

**Step 4** — Execute.
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /tmp/login.json --som
```

---

## Validating multiple pages in a single invocation

To check N pages of an authenticated site without replaying the login each time:

```bash
cat > /tmp/audit.json << 'EOF'
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
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

## Extracting a value from the page

To read a text string, a counter, or any DOM value:

```bash
cat > /tmp/extract.json << 'EOF'
[{"type": "evaluer", "script": "document.title"}]
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --actions /tmp/extract.json
# → result in evaluations[0].valeur
```

**Important**: always write JS scripts to an `--actions` file,
never inline with `--action` (the shell corrupts nested quotes).

---

## Setting up visual monitoring

```bash
# 1. Save the visual reference
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --nom home

# 2. Compare later (pixel diff)
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
# → verdict: stable / drift / regression (exit code 0 or 1)

# 3. On an authenticated page: capture first with rpa.py, then save
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/login.json > /tmp/out.json
CAPTURE=$(python3 -c "import json; d=json.load(open('/tmp/out.json')); print(d['captures_intermediaires'][-1])")
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --capture "$CAPTURE" --nom dashboard
```

---

## Common pitfalls

| Situation | What to do |
|---|---|
| `FileNotFoundError` on vault | Check that the JSON file is named with the full FQDN (`urlparse(url).hostname`) |
| `VaultFermeError` (exit 42) | Mount the vault: `bash scripts/mount-vault.sh` |
| Invalid JSON in output | Use `2>/dev/null \| tail -1` to extract only the JSON line |
| SoM IDs differ between sessions | Expected — SoM IDs are recalculated on each capture. Never reuse them cross-session |
| Login followed by Django redirect to dashboard | Do not use `naviguer` in a resumed Django session — pass the URL via `--url` |
| `<select>` form field not filled | Use `remplir_som` (not `remplir`) with the SoM ID of the `<select>` |
| Click has no effect on out-of-viewport button | Add `{"type":"defiler","selecteur":"#the-button"}` before the click |
| `auth_status: "active"` even on the login page | Positive selector is ambiguous (persistent header) — add `--auth-indicator-negative .btn-login` |
| Web Components elements not numbered by SoM | Add `--shadow-dom` (Angular, Lit, Stencil) |

---

## Uninstalling Diwall

The `scripts/uninstall.sh` script removes the installation cleanly, in the reverse
order of `install.sh`.

```bash
# See what will be removed, without doing anything
bash scripts/uninstall.sh --dry-run

# Full uninstall (interactive confirmation)
bash scripts/uninstall.sh

# Without confirmation (cold tests, chained reinstall)
bash scripts/uninstall.sh --confirme && bash scripts/install.sh
```

**What is removed:**

| Item | Detail |
|---|---|
| `/opt/diwall/` | Code, Python venv, configuration |
| `/var/log/diwall/` | Operation logs |
| `diwall` system user | Created exclusively for Diwall |
| `diwall` system group | Same |
| Group membership | Your account is removed from the `diwall` group |
| git pre-push hook | `core.hooksPath` disabled in the source repository |

**What is never touched:**
- `~/Vaults/` — your credential vaults
- `~/git/Diwall/` — git sources
- Playwright browser cache (`~/.cache/ms-playwright/`)

**Evidence captures (`/var/log/diwall/preuves/`):** if the directory contains
captures, it is preserved by default with a warning. To remove it:

```bash
bash scripts/uninstall.sh --confirme --purge-preuves
```

---

## Consulting the operation history

```bash
# All operations on a target
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local

# Mutating operations only (clicks, form input)
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --mutatif

# From a date
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local \
  --depuis 2026-06-01
```
