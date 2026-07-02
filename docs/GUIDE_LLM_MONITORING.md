# Diwall — Monitoring guide (watch.py, long ops, screenshot timeouts, journal)

<!-- notice-version: 1.4 -->
Version 1.4 — July 2026 (v1.16.0) — operation_id row, etat deterministic verdict

Load this notice when: watch.py, pixel diff, long-running operations, `--screenshot-timeout`,
interval_capture, journal.py, FN7/FN8/FN9.

---

## Boussole JSON — exhaustive key activation table

Exhaustive by construction (v1.15.2, item 1) — every key `shot.py` can add to
`boussole` is listed here. No key is added to the runtime without a matching row
in this table in the same commit (design rule, see below).

| Key | Type | Always present? | Condition |
|---|---|---|---|
| `utilisateur` | string | always | OS user running the process |
| `ip_locale` | string | always | empty string if outbound UDP probe fails |
| `repertoire` | string | always | `os.getcwd()` at invocation |
| `url_courante` | string | always | final URL after navigation and actions |
| `titre_page` | string | always | empty string if `page.title()` fails |
| `citoyennete` | object | always | `{pages_visitees, actions_executees, duree_totale_ms}`; sub-key `plafond_atteint` only if `max_pages_par_run` or `max_actions_par_run` was hit; sub-key `waf_bloquants` (integer, v1.16.0) only if at least one navigation (initial or `naviguer` action) was flagged as WAF-blocked; sub-key `indice_agressivite` (float, v1.16.0) present whenever at least one action ran |
| `operation_id` | string (12 hex chars) | always | unified run identity (v1.16.0, item B) — same value in the journal entry for this run and in the isolated temp directory path |
| `session_derive` | object | conditional | `--reprendre-session` active **and** final URL diverged from the URL saved at `--sauver-session` time |
| `auth_status` | string (`"active"`\|`"inactive"`) | conditional | `--auth-indicator` provided |
| `som_hors_viewport` | integer | conditional | `--som` active **and** at least one interactive element is off-screen (value > 0) |
| `shadow_dom_actif` | boolean (`true`) | conditional | `--shadow-dom` active |
| `stealth_actif` | boolean (`true`) | conditional | `--stealth` active |
| `tls_errors_ignored` | boolean (`true`) | conditional | `--ignore-tls-errors` active |

Do not assert the absence of conditional keys as a failure signal. Check `auth_status`
value (`"active"` / `"inactive"`), not its presence alone.

**Root vs `boussole` duplication:** `citoyennete`, `auth_status`, and `derive_session`
(root spelling) / `session_derive` (boussole spelling — same object, different key name)
appear **both** at the JSON root and inside `boussole`. This is intentional (two
consumers, spec `V1_15_0_NAVIGATION_CITOYENNE.md`): the root serves structured
extraction, `boussole` serves at-a-glance orientation. Do not treat the two as
independent signals — they carry the same value.

**Design rule (prerequisite for v1.16.0):** any conditional key added to `boussole`
in a future release must be documented as a new row in this table in the same
commit as the code that adds it. An undocumented key is a defect, not a feature.

**Temporary-file isolation rule (K1′, prerequisite for v1.16.0):** every temporary
file `shot.py` writes under `/tmp/diwall/` must be isolated by a unique run
identifier, to prevent silent overwrite between concurrent runs. v1.15.2 ships a
minimal patch (`chemin_png()` uses `time.time_ns()` instead of `int(time.time())`
— nanosecond resolution eliminates same-second collisions on named captures).
v1.16.0 completes this with a transverse `operation_id` (UUID4) generated once in
`main()`, isolating **all** temporaries — including the `stream/<run_id>/` directory,
which v1.15.2 does not yet cover — under `/tmp/diwall/<operation_id>/`.

---

## watch.py — visual monitoring

watch.py compares a current screenshot to a stored reference image using pixel diff or LLM
semantic analysis. It does **not** loop by itself — call it from a shell loop or cron.

**Save a reference image (known-good state):**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --sauver-reference
```

**Compare against the reference (pixel diff):**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/status-ok.png \
  --seuil-regression 0.02
```

**Compare against the reference (LLM semantic diff):**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer \
  --llm local
```

**Key parameters:**
- `--sauver-reference` — capture and save the current page as reference
- `--comparer-pixel REF_PNG` — quantitative pixel diff against REF_PNG
- `--comparer` — semantic LLM diff against stored reference
- `--seuil-bruit N` — max RGB delta per pixel to consider unchanged (default: 5)
- `--seuil-stable F` — upper bound for `stable` verdict (default: 0.002)
- `--seuil-regression F` — lower bound for `regression` verdict (default: 0.05)
- `--heatmap` — also produce a PNG heatmap of changed zones
- `--llm-en-complement` — re-run LLM diff only when pixel verdict is `drift` or `regression`
- `--exclure-zone X,Y,W,H` — ignore a zone during diff (repeatable)
- `--nom NOM` — named view, for multiple reference views per URL
- `--ntfy-url URL` — push alert to ntfy when regression detected
- `--timeout MS` — Playwright capture timeout for this run (default: 10000)

**Verdict bands:**

| `taux_diff` | Verdict | Exit code |
|---|---|---|
| `< seuil-stable` (0.2%) | `stable` | `0` |
| `seuil-stable ≤ x < seuil-regression` | `drift` | `0` |
| `≥ seuil-regression` (5%) | `regression` | `1` |
| Dimensions mismatch | `viewport_mismatch` | `2` |
| I/O error | — | `3` |

**Reference stability:** capture the reference at the same viewport size and zoom as
comparison runs. If the page has animations, use `--exclure-zone` on the animated area.

**Monitoring loop (shell):**
```bash
while true; do
  /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
    --url https://target.local/status \
    --comparer-pixel /opt/diwall/references/status-ok.png \
    --ntfy-url https://ntfy.sh/my-alerts
  sleep 60
done
```

NumPy is used when present (~200ms on 1280×720); Pillow-only fallback for ~10s per comparison.

---

## `--screenshot-timeout` — configuring the screenshot limit (v1.11.0)

Playwright's `page.screenshot()` internal default is 30s. On slow pages or heavy SPA
renders, this causes `TimeoutError` during capture. v1.11.0 raises shot.py's default to
120 000 ms and makes it configurable.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/heavy-report \
  --screenshot-timeout 120000
```

`--screenshot-timeout` is in milliseconds. Default: 120 000 (120 s).

**This parameter is distinct from `--timeout`:**
- `--timeout` controls Playwright action timeouts (click, fill, wait…)
- `--screenshot-timeout` controls only `page.screenshot()` calls

`--screenshot-timeout` is propagated to ALL screenshot calls inside shot.py:
SoM capture, `capturer` actions, intermediate captures, `cliquer_visuel`, and the
final capture.

**When to increase it:**
- Heavy dashboards or BI pages that render for 10–30s before stabilising
- Pages with lazy-loaded charts or PDF embeds
- Pages that time out on the SoM overlay injection

**When to decrease it:**
- Simple pages where you want fast failure rather than a long wait
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
all actions that support it. Per-action `interval_capture` overrides the global default.

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

**Correct pattern — wait for a DOM signal:**
```json
[
  {"type": "cliquer_som", "id": 7},
  {"type": "attendre_absence", "selecteur": ".spinner"},
  {"type": "attendre_selecteur_present", "selecteur": ".result-container"},
  {"type": "capturer", "nom": "result"}
]
```

**Or, if the operation redirects to a result page:**
```json
[
  {"type": "cliquer_som", "id": 7},
  {"type": "attendre_navigation"},
  {"type": "evaluer", "script": "document.title", "contient": "Result"}
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

This is useful when the spinner is injected by JS before the POST response arrives —
Playwright needs a moment to register the new DOM state (REX #66).

---

## journal.py — operations log

journal.py appends a structured JSON line to `/var/log/diwall/operations.jsonl`
after each shot.py / rpa.py execution. It is called automatically by rpa.py.

```bash
# Read the last 10 entries
tail -n 10 /var/log/diwall/operations.jsonl | python3 -m json.tool --no-ensure-ascii
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
| `modeles_appeles` | list of LLM models called during the run |
| `duree_ms` | wall-clock duration in ms |
| `erreur` | error message if `succes: false` |

**When to read the journal:** after a failure in cron mode (no terminal output),
or to audit which models were used in a given session.

---

## `etat` — deterministic operational verdict (v1.16.0, item A)

Every successful `shot.py` run includes an `etat` object at the JSON root —
a pre-computed verdict synthesizing the signals already present elsewhere in
the output, so you do not have to cross-reference `auth_status`,
`citoyennete.plafond_atteint`, `derive_session`, and `erreurs_js` by hand
before deciding whether to proceed with a mutating action.

```json
"etat": {
  "pret_a_agir": true,
  "niveau_confiance": "eleve",
  "raisons": ["aucun signal de friction détecté"]
}
```

| Field | Type | Meaning |
|---|---|---|
| `pret_a_agir` | boolean | `false` if authentication is inactive, session drifted, or a citizenship cap was hit |
| `niveau_confiance` | `"eleve"` \| `"modere"` \| `"faible"` | degrades to `modere` on non-blocking friction (JS/console errors, cap hit), to `faible` on auth/session problems or a detected WAF block |
| `raisons` | array of strings | one entry per signal that contributed to the verdict; `["aucun signal de friction détecté"]` when everything is clean |

**Scope — what `etat` does NOT check:** it has no notion of your business
expectation for the page (is this the *right* URL, does the title match what
you expect). That is the job of `evaluer` + `contient`/`motif`/`attendu`
assertions in `rpa.py` — Diwall has no external reference to compare against
on its own. `etat` only aggregates signals `shot.py` can determine by itself.

**When absent:** `etat` is present only on the success path (`succes: true`).
On a failure (`succes: false`), the error itself is already the clearest
signal — read `erreur` and `message` instead.

---

## `erreurs_js` vs `erreurs_console` — two distinct signals (v1.16.0, item D)

Both are root-level lists, always present (empty if nothing was captured), and
both feed `etat.niveau_confiance` (non-empty → degrades to `modere`). They are
**not** duplicates:

| Field | Playwright source | Captures |
|---|---|---|
| `erreurs_js` | `page.on("pageerror", ...)` | uncaught JS exceptions (script crashes) |
| `erreurs_console` | `page.on("console", ...)`, filtered to `type == "error"` | `console.error(...)` calls and browser-level error-level console messages (failed network requests, application warnings logged as errors) |

A page can log `console.error` for a failed API call without ever throwing an
uncaught exception — `erreurs_js` would stay empty while `erreurs_console`
flags the friction. Read both; neither substitutes for the other.

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

watch.py does not loop internally. Call it from cron for scheduled checks:

```bash
# /etc/cron.d/diwall-monitor
*/30 * * * * diwall /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/status-ok.png \
  --ntfy-url https://ntfy.sh/my-alerts \
  >> /var/log/diwall/cron.jsonl 2>&1
```

Each run appends one JSON line to `cron.jsonl`. Exit code `1` on regression.

Use `--ntfy-url` for push alerts without shell scripting. Or check the exit code:
```bash
if [ $? -ne 0 ]; then
  # regression detected — take action
fi
```

**Never expose vault paths or credentials in cron commands.** Use `diwall.conf`
with `secrets_defaut` instead of `--secrets` in cron.

---

## Behavior after hitting a citizenship cap (v1.15.2, Qwen Q3)

When `max_pages_par_run` or `max_actions_par_run` is reached, `shot.py` closes
the Chromium process cleanly (see `citoyennete.plafond_atteint` in `boussole`).
This has consequences for state:

- **DOM state is destroyed** — open modals, unsubmitted form fields, scroll
  position are all lost with the browser process.
- **Session state (cookies, `localStorage`) survives only if `--sauver-session`
  was explicit** on this run. Without it, nothing is preserved.
- **Resuming via `--reprendre-session` reloads the saved URL from scratch** —
  it does not replay DOM interactions since the save.

**Planning consequence:** submit data (forms, confirmations) *before* the
citizenship caps are likely to be reached. Only save session state at a point
where the DOM is stable (no open modal, no pending submission) — a save
mid-interaction is not a checkpoint, it is a snapshot of cookies only.

---

## Duration thresholds — suspecting a stuck run (v1.15.2, Qwen Q5)

`citoyennete.duree_totale_ms` (root and `boussole`) measures wall-clock time
spent in `executer_actions()`. Indicative thresholds, not hard caps enforced by
the runtime:

- **Under 60 000 ms (1 minute):** normal for a simple exploration run.
- **Above 120 000 ms (2 minutes):** suspect a redirect loop or network
  congestion. Self-impose a semantic stop rather than waiting further — Diwall
  will not interrupt itself; there is no runtime timeout tied to this figure.

This is a recommendation for agent self-regulation, not a plafond configured in
`diwall.conf` (compare with `max_pages_par_run` / `max_actions_par_run`, which
are enforced).
