# Diwall — Operator guide

Version 1.10 — August 2026 (v1.23.0) — four more demonstration use cases (self-hosted observability, ticketing platform administration, local events tracking, e-commerce access under Respectful Navigation)

*Also available in French, German and Spanish under `docs/fr/`, `docs/de/` and `docs/es/`.*

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

### Respectful Navigation (v1.15.0)

Diwall does not disguise its identity to bypass bot detection. `--stealth`
removes automatic technical markers (`navigator.webdriver`) that block
headless browsers regardless of intent — it does not change the operator's
IP, identity, or the fact that the run is declared. In exchange, every run
reports its own footprint (`respect`: pages visited, actions executed,
duration) and respects configurable courtesy delays and hard caps
(`diwall.conf [navigation]`). The right to navigate and the duty to navigate
measurably are treated as inseparable — see `docs/RETOUR_EXPERIENCE.md`
FR-77/FR-78/FR-79 for the field context that shaped this.

**Local targets — the courtesy delay is not a doctrine, it is a default
(v1.19.0):** the shipped `min_action_delay_ms: 800` protects
an unconfigured first run against the public internet — it is meaningless
against your own development/production machine. Set it to `0` in your local
`diwall.conf` for local debugging; see `docs/MANUEL.md` section 3b.

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

**This document is written for the person operating Diwall.**

It complements `GUIDE_LLM.md` (intended for models) with concrete examples,
step-by-step procedures, and reminders on common stumbling points.

---

## Demonstration use cases

The cases below illustrate what an agent-plus-Diwall session can look like in
practice. They are meant for you to evaluate against your own context, not as
a recommendation to adopt any specific one. Only Case 1 ships as a runnable
scenario; the others are narrative on purpose, and each explains why under its
own heading.

### Case 1 — local CSS/JS troubleshooting

Committed as a real, runnable scenario:
`scenarios/exemples/depannage_local.json`. It diagnoses a visual
shift or a blocked interaction on a locally-served interface — a fast probe
(`--mode fast`), reading `erreurs_js`/`erreurs_console`, an `--som` capture
if the shift is purely visual, then validating the fix with
`watch.py --comparer-pixel` against a reference captured before the
regression. Run it directly:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/exemples/depannage_local.json \
  --guide-version 1.2
```

### Case 2 — comparing hardware components across shops

An agent asked to compare a component's price and stock across several
online shops could compose Diwall with a separate URL-discovery tool (a
local search instance, for example) to find candidate shop pages, then use
Diwall in sonde mode (`--mode fast`, no PNG) with `evaluer` actions to
extract price/stock/specifications from each page, and finally compare the
results itself.

**Not shipped as a committed scenario, deliberately:** naming a specific
shop in a public, versioned scenario is a decision that belongs to you, not
a default this project should make on your behalf. It also carries a real
fragility risk — a public scenario targeting a named commercial site can
fail months later when that site's anti-bot posture changes (39% of the
commercial sites sampled in `docs/RETOUR_EXPERIENCE.md` FR-77 returned an
immediate block), which discredits the example more than it helps. If you
build this composition yourself, note that any URL-discovery tool you pair
Diwall with (a local search instance or otherwise) is not a Diwall
component — it is a separate piece the agent composes on top.

### Case 3 — exploring and summarising technical documentation (single-page apps)

An agent tasked with producing an integration guide for a documentation
site built as a single-page app could use `rpa.py` with
`attendre_reseau_calme` to let client-side routing settle, extract the
accessibility tree in fast mode to map the page structure, then walk code
blocks recursively with `evaluer` to pull their exact content, and finally
synthesise the collected material into a guide.

**Not shipped as a committed scenario, for the same reason as Case 2** —
naming a specific documentation site (or, worse, a specific payment
provider whose documentation happens to be the working example) is a
commercial and reputational commitment this project should not make by
default, and the same WAF-fragility risk applies to a public scenario
pinned to one real target.

### Case 4 — configuring a self-hosted observability or analytics dashboard

An operator setting up a self-hosted monitoring or web-analytics dashboard
behind a reverse proxy can use Diwall to drive the interface itself —
creating a dashboard, wiring a data source, setting an alert rule — the
same way any other admin panel gets configured, rather than hand-editing
files for steps the UI is meant to handle. This includes targets sitting
behind a network-level HTTP Basic Auth challenge (`--http-credentials`,
v1.21.0) — confirmed against a real Caddy-protected admin interface, not
just a synthetic fixture: the stored credentials answered the
challenge on the first attempt.

**Not shipped as a committed scenario** — the dashboard layout and data
source names are specific to one operator's infrastructure, and inventing
a synthetic equivalent would duplicate what the local fixture in Case 1
already covers for structural regression, not for this kind of guided,
multi-step configuration work.

### Case 5 — administering a ticketing platform end-to-end

Diwall used across several sessions to configure and operate a real
self-hosted ticketing installation — event setup, ticket categories, a
custom domain, and the day-of scan/check-in tooling — through the same web
interface a human administrator would use. Real friction was encountered
and resolved along the way (session handling, dropdown quirks, a
permission prompt blocking an unattended step) — not a friction-free
success story, which is part of what makes it a useful example: the
obstacles were ordinary web-automation obstacles, not something specific
to Diwall.

**Not shipped as a committed scenario** — a ticketing configuration touches
billing and venue specifics unique to the operator, same reasoning as
Case 2.

### Case 6 — tracking a regional events calendar

A simple semantic-probe usage: asking an agent to check a local events
calendar for upcoming happenings, without knowing in advance which page
holds the answer. Diwall's fast mode (`--mode fast`, no
capture) combined with the accessibility tree lets the agent scan and
report back in a handful of requests — no vision model needed for this
kind of read-only, text-driven task. One session also produced a clean,
real example of the WAF signal's documented false-positive behaviour: a
page loaded normally (rich content, no captcha, no interstitial) while
`respect.waf_bloquants` still fired, because of an unrelated third-party
resource on the page matching a detection keyword — resolved in about a
minute by reading the accessibility tree already present in the same
response, exactly as the guide's "signal, never a lock" rule anticipates.

**Not shipped as a committed scenario** — a specific regional events site
is not a stable, reproducible public target, and naming one publicly is
the operator's call, not a project default.

### Case 7 — testing real-world access to e-commerce sites under Respectful Navigation

A recurring, honest observation from actual sessions: used respectfully
(rate-limited delays, page/action caps, `--stealth` active, no attempt to
force access past a real block), Diwall run against a range of e-commerce
sites finds that a large share of major platforms return an outright
block — HTTP 403, or a request that never completes — regardless of how
courteous the traffic is. This is not a Diwall shortcoming to fix:
anti-bot posture is the site's own choice, and Diwall does not attempt to
defeat it (see "Respectful Navigation" above). Practically: for
shopping-comparison tasks against large commercial platforms, expect a
meaningful share of dead ends, and treat a block signal
(`respect.waf_bloquants`) as information to route around, not an error
to retry against.

A distinction worth keeping in mind: an invisible verification screen that
never resolves and presents nothing to act on (no checkbox, no image
challenge) is different from an interactive CAPTCHA. The latter is
legitimate to answer honestly — an agent operating for a named human, from
that human's own IP, is not the "robot" the question is aimed at. The
former simply offers no door to open from the agent's side, and forcing
past it (IP rotation, TLS fingerprint spoofing) falls outside what Diwall
does.

**Not shipped as a committed scenario, and deliberately not naming the
platforms involved** — see the WAF-fragility reasoning under Case 2: a
dated block/no-block table tied to named commercial sites goes stale and
undermines its own point faster than it illustrates it. `docs/RETOUR_EXPERIENCE.md`
FR-77 documents the same pattern at panel scale (39% immediate block rate).

---

## Prerequisites before starting

```bash
# 1. Verify Diwall responds
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --som --a11y
# → must return {"succes": true, ...}

# 2. Verify the encrypted directory is mounted (if gocryptfs)
ls ~/Vaults/Diwall/
# → must show .json files, not encrypted content

# 3. Verify credentials for a domain
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.repertoire_chiffre import lire_credential
print('OK' if lire_credential('target.local', 'password') else 'EMPTY')
"
```

---

## Credentials configuration per project

Each project can have its own credentials directory. Two methods:

**Method 1 — Direct environment variable (one-shot):**
```bash
DIWALL_SECRETS_DIR=~/Vaults/MyProject \
  /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

**Method 2 — Project `.diwall.conf` file (recommended for recurring projects):**
```bash
# Create the file at the project root
echo '{"secrets_dir": "../MyProject-secrets"}' > ~/git/MyProject/.diwall.conf

# Then prefix each invocation (or export at the start of the shell session)
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

The `secrets_dir` in `.diwall.conf` can be a relative path — it is resolved
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

**Step 1** — Prepare the credentials file.

The credentials file is named `<hostname>.json` where `hostname` = result of
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
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
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

## Setting up continuous structural monitoring (v1.18.0)

Complements the visual monitoring above: this checks the page's *structure*
(status code, DOM element counts, JS evaluation results) instead of its
*appearance* — cheaper, and catches a different class of regression (a
disappeared form field with unchanged layout, for instance).

```bash
# 1. Save a structural reference, once
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --sauver-verifier-reference /opt/diwall/references/my-scenario.ref.json

# 2. One check-and-alert pass
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring
```

Silent when stable, one `ntfy` push when a regression is detected. Schedule
it yourself with cron — the script does one pass and exits, it does not loop.
`scripts/*.sh` is never deployed to `/opt/diwall/`, so the cron entry runs
from the git source, as your own user (not the `diwall` service account,
which cannot reach `~/git/Diwall/Diwall/`):

```bash
# crontab -e (your own crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

---

## Common pitfalls

| Situation | What to do |
|---|---|
| `FileNotFoundError` on the credentials file | Check that the JSON file is named with the full FQDN (`urlparse(url).hostname`) |
| `SecretsFermesError` (exit 42) | Mount the encrypted directory: `bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh` |
| Invalid JSON in output | Use `2>/dev/null \| tail -1` to extract only the JSON line |
| SoM IDs differ between sessions | Expected — SoM IDs are recalculated on each capture. Never reuse them cross-session |
| Login followed by Django redirect to dashboard | Do not use `naviguer` in a resumed Django session — pass the URL via `--url` |
| `<select>` form field not filled | Use `remplir_som` (not `remplir`) with the SoM ID of the `<select>` |
| Click has no effect on out-of-viewport button | Add `{"type":"defiler","selecteur":"#the-button"}` before the click |
| `auth_status: "active"` even on the login page | Positive selector is ambiguous (persistent header) — add `--auth-indicator-negative .btn-login` |
| Web Components elements not numbered by SoM | Add `--shadow-dom` (Angular, Lit, Stencil) |
| `respect.waf_bloquants` appears on a page that is not actually blocked | Detection is keyword-based (v1.16.0, refined v1.17.2) — treat as a signal, not a verdict. If it persists on a page you've confirmed is not blocked, add `--ignorer-waf` |
| `cliquer_som` clicks the wrong element on a page that mutated between capture and click | Add `--som-rafraichir` (v1.17.0) — resolves by a stable marker instead of live re-indexing |
| A long RPA scenario fails partway through and you don't want to replay completed steps | Add `--checkpoint FILE` (v1.17.0) — relaunch the same command to resume; DOM state is not preserved, only session + action position |
| Interactive elements inside an iframe are invisible to Diwall | SoM cannot number iframe content (same-origin or cross-origin) — use `cliquer_iframe`/`remplir_iframe` (v1.17.0) with an explicit CSS selector, or `iframe_chemin` (v1.18.0) for an iframe nested inside another |
| Your model reports `"erreur": "guide_non_lu"` / exit 1 on its first Diwall call | Expected the first time a model uses Diwall on this machine as this OS user (v1.18.0) — it must read `docs/GUIDE_LLM.md` and pass `--guide-version` once. This is deliberate, not a bug — tell the model to read the guide rather than working around the error |

---

## Uninstalling Diwall

The `~/git/Diwall/Diwall/scripts/uninstall.sh` script removes the installation cleanly, in the reverse
order of `install.sh`.

```bash
# See what will be removed, without doing anything
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run

# Full uninstall (interactive confirmation)
bash ~/git/Diwall/Diwall/scripts/uninstall.sh

# Without confirmation (cold tests, chained reinstall)
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme && bash ~/git/Diwall/Diwall/scripts/install.sh
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
- `~/Vaults/` — your credentials
- `~/git/Diwall/` — git sources
- Playwright browser cache (`~/.cache/ms-playwright/`)

**Evidence captures (`/var/log/diwall/preuves/`):** if the directory contains
captures, it is preserved by default with a warning. To remove it:

```bash
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme --purge-preuves
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
