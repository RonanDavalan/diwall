# Diwall — Monitoring guide (watch.py, long ops, screenshot timeouts, journal)

Version 1.0 — June 2026 (extracted from GUIDE_LLM.md v2.5 + v1.11.0 additions)

Load this notice when: watch.py, pixel diff, long-running operations, `--screenshot-timeout`,
interval_capture, journal.py, operator profiles, FN7/FN8/FN9.

---

## watch.py — continuous visual monitoring

watch.py compares periodic screenshots to a reference image using pixel diff.
Use it when you need to detect a visual change on a page that you cannot poll via API.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --reference /opt/diwall/references/status-ok.png \
  --interval 30 \
  --threshold 0.02
```

**Key parameters:**
- `--interval N` — check every N seconds
- `--threshold F` — fraction of pixels that must differ to trigger an alert (0.0–1.0)
- `--reference PATH` — PNG to compare against (see `capture-reference` below)

**Output:** JSON per check with `diff_fraction`, `verdict` (`ok` / `alerte`), and
`capture` (PNG path of the latest frame). When `verdict` is `alerte`, the calling
LLM can decide what to do (retry, notify, stop).

**Vision model in watch.py:** uses `qwen3-vl:2b` (local Ollama) for semantic
interpretation of the diff when `--llm` is passed. Without `--llm`, pixel diff only.

**Running watch.py in the background:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py --url ... --interval 60 &
```

Redirect stdout to a file if you need to process the stream:
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --reference /opt/diwall/references/status-ok.png \
  --interval 30 > /tmp/watch-output.jsonl 2>&1 &
```

---

## `capture-reference` — building a reference image

Before running watch.py, build a reference image from a known-good state.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/status \
  --output-dir /opt/diwall/references/status-ok
```

The PNG at `capture` in the JSON output is your reference. Copy it to the
`/opt/diwall/references/` directory (or any stable path you control).

**Reference stability:** the reference must be captured from the same viewport
size and zoom level as watch.py calls. If the page has animation or time-sensitive
content, use `--no-capture` during watch iterations and only capture diffs.

---

## `--screenshot-timeout` — configuring the screenshot limit (v1.11.0)

Playwright's `page.screenshot()` has a fixed 30s default timeout. On slow pages
or heavy SPA renders, this causes `TimeoutError` during capture.

**v1.11.0 adds `--screenshot-timeout` to shot.py:**

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/heavy-report \
  --screenshot-timeout 120000
```

`--screenshot-timeout` is in milliseconds. Default: 120000 (120 s).

**This parameter is distinct from `--timeout`:**
- `--timeout` controls Playwright action timeouts (click, fill, wait…)
- `--screenshot-timeout` controls only `page.screenshot()` calls

`--screenshot-timeout` is propagated to ALL screenshot calls inside shot.py:
SoM capture, `capturer` actions, intermediate captures, `cliquer_visuel`, and the
final capture.

**When to increase it:**
- Heavy dashboards or BI pages that render for 10–30s before stabilizing
- Pages with lazy-loaded charts or PDF embeds
- Pages that time out on the SoM overlay injection

**When to decrease it:**
- Simple pages where you want fast failure rather than a 120s wait
- Test suites where speed matters more than reliability on slow pages

**If all else fails** and the screenshot still times out: use `--no-capture` to
skip the visual capture entirely and rely on `a11y_tree` + `evaluer` instead.

---

## `interval_capture` — periodic screenshots during long actions

`interval_capture` is a per-action parameter (available on `attendre`, `pause`,
`attendre_navigation`) that adds intermediate screenshots every N seconds.

```json
{"type": "attendre", "selecteur": ".result-loaded", "interval_capture": 5}
{"type": "pause", "ms": 30000, "interval_capture": 10}
```

The intermediate captures are appended to `stream_captures[]` in the JSON output.
Use them to diagnose what happened during a long wait.

**Global default:** `--interval-capture N` on the rpa.py CLI sets the default for
all actions that support it. Per-action `interval_capture` overrides the default.

---

## Long-running operations — FN7: the race condition trap

When an operation (batch job, file import, report generation) is triggered by a click
and takes several seconds to complete, do not use `pause` to wait.

**Wrong pattern (FN7):**
```json
[
  {"type": "cliquer_som", "id": 7},
  {"type": "pause", "ms": 10000},
  {"type": "capturer", "nom": "result"}
]
```

**Problem:** `pause` does not adapt to the actual operation duration.
If the operation takes 15s, you get a stale capture. If it takes 2s, you waste 8s.

**Correct pattern:**
```json
[
  {"type": "cliquer_som", "id": 7},
  {"type": "attendre_absence", "selecteur": ".spinner"},
  {"type": "attendre_selecteur_present", "selecteur": ".result-container"},
  {"type": "capturer", "nom": "result"}
]
```

Or, if the operation redirects to a result page:
```json
[
  {"type": "cliquer_som", "id": 7},
  {"type": "attendre_navigation"},
  {"type": "evaluer", "script": "document.title", "contient": "Résultat"}
]
```

**FN7 exception:** when the app provides no DOM signal for completion (spinner not
in DOM, no URL change, no text change) — use `pause` with `interval_capture` to
observe the state manually. The LLM then reads the intermediate captures to decide
when to proceed.

---

## FN8 — `attendre_selecteur_present` vs `pause` for delayed DOM elements

When an element appears after a network request (lazy load, AJAX):

```json
// WRONG — element may not be present yet after pause
{"type": "pause", "ms": 3000},
{"type": "cliquer", "selecteur": ".lazy-button"}

// CORRECT — wait for the element to be visible before acting on it
{"type": "attendre_selecteur_present", "selecteur": ".lazy-button"},
{"type": "cliquer", "selecteur": ".lazy-button"}
```

`attendre_selecteur_present` uses Playwright `state=visible` — it blocks until
the element is in the DOM AND visible. Max wait: `--timeout` ms (default: 60000).

---

## FN9 — `attendre_absence` and the initial delay

When a form submission triggers a POST redirect, Playwright may not have started
processing the redirect when `attendre_absence` begins polling. The spinner may
still be present from a previous run.

Use `delai_initial_ms` to add a small delay before polling starts:

```json
{"type": "attendre_absence", "selecteur": ".loading-overlay", "delai_initial_ms": 500}
```

This is specifically useful when the spinner is injected by JS before the POST
response arrives, so Playwright needs a moment to register the new DOM state.

---

## journal.py — operations log

journal.py appends a structured JSON line to `/var/log/diwall/journal.jsonl`
after each shot.py / rpa.py execution. It is called automatically by rpa.py.

```bash
# Read the last 10 entries
tail -n 10 /var/log/diwall/journal.jsonl | python3 -m json.tool --no-ensure-ascii
```

**Fields in each log entry:**

| Field | Meaning |
|---|---|
| `ts` | ISO 8601 timestamp |
| `version` | Diwall version string |
| `mode` | `"shot"` or `"rpa"` |
| `url` | Target URL |
| `scenario` | Scenario file path (rpa mode) |
| `succes` | boolean |
| `modeles_appeles` | list of LLM model names called during the run |
| `duree_ms` | wall-clock duration in ms |
| `erreur` | error message if `succes: false` |

**When to read the journal:** after a failure in cron mode (no terminal output),
or to audit which models were used in a given session.

---

## Operator profiles — `--profil`

Operator profiles are YAML files in `/opt/diwall/profiles/` (or `~/.config/diwall/profiles/`).
A profile sets default values for `--timeout`, `--llm`, `--screenshot-timeout`, etc.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --profil standard
```

Profile `standard.yaml` example:
```yaml
timeout: 60000
screenshot_timeout: 120000
llm: qwen3-vl:2b
interval_capture: 10
```

CLI flags override profile values. Profiles do not affect vault paths.

**When there is no profile configured:** all parameters use built-in defaults
(`--timeout 60000`, `--screenshot-timeout 120000`, no `--llm`).

---

## Boussole JSON — orientation at a glance

Every shot.py and rpa.py output includes a `boussole` object:

```json
"boussole": {
  "url_courante": "https://target.local/dashboard",
  "titre_page": "Dashboard — My App",
  "session_derive": false,
  "auth_status": "active",
  "som_hors_viewport": 0
}
```

Read `boussole` first in every JSON output — it tells you:
- Where you are (`url_courante`, `titre_page`)
- Whether the session drifted (`session_derive`)
- Whether you are authenticated (`auth_status`, if `auth_indicator` is set)
- Whether elements are off-screen (`som_hors_viewport`)

`boussole` is the substitute for a human looking at the browser window.
If `boussole` does not match your expectation: stop and investigate before
running any mutating action.

---

## Cron mode — autonomous monitoring

To schedule a monitoring check:

```bash
# /etc/cron.d/diwall-monitor
*/30 * * * * diwall /opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/health-check.json \
  >> /var/log/diwall/cron.jsonl 2>&1
```

Each run appends one JSON line to `cron.jsonl`. On failure (`succes: false`),
the `erreur` field contains the cause.

Use ntfy integration to push alerts:
```bash
# After rpa.py, check exit code
if [ $? -ne 0 ]; then
  curl -s -X POST https://ntfy.sh/diwall-alerts -d "Health check failed"
fi
```

**Never expose vault paths or credentials in cron commands.** Use `diwall.conf`
with `secrets_defaut` instead of `--secrets` in cron.
