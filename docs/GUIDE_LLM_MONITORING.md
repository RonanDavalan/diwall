# Diwall — Monitoring guide (watch.py, long ops, screenshot timeouts, journal)

<!-- notice-version: 1.1 -->
Version 1.1 — August 2026. This number counts revisions of this notice, not
releases of Diwall. Notable in the current text: `chemin_sensible_refuse`
error code documented for `--checkpoint`/`--sauver-verifier-reference`/
`--replay-verifier`. Prior (v1.0): `latences_actions` per-action timing, and
the `journal.py --erreurs` filter

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
| `respect` | object | always | `{pages_visitees, actions_executees, duree_totale_ms}`; sub-key `plafond_atteint` only if `max_pages_par_run` or `max_actions_par_run` was hit — since v1.17.2, `rpa.py --checkpoint` treats this as a partial run and preserves progress instead of deleting the checkpoint; sub-key `waf_bloquants` (integer, v1.16.0, refined v1.17.2) only if at least one navigation (initial or `naviguer` action) was flagged as WAF-blocked; sub-key `indice_agressivite` (float, v1.16.0) present whenever at least one action ran |
| `operation_id` | string (12 hex chars) | always | unified run identity (v1.16.0, item B) — same value in the journal entry for this run and in the isolated temp directory path |
| `session_derive` | object | conditional | `--reprendre-session` active **and** final URL diverged from the URL saved at `--sauver-session` time |
| `auth_status` | string (`"active"`\|`"inactive"`) | conditional | `--auth-indicator` provided |
| `som_hors_viewport` | integer | conditional | `--som` active **and** at least one interactive element is off-screen (value > 0) |
| `shadow_dom_actif` | boolean (`true`) | conditional | `--shadow-dom` active |
| `stealth_actif` | boolean (`true`) | conditional | `--stealth` active |
| `tls_errors_ignored` | boolean (`true`) | conditional | `--ignore-tls-errors` active |
| `waf_ignore_actif` | boolean (`true`) | conditional | `--ignorer-waf` active (v1.17.2) — a WAF block degrades `niveau_confiance` but no longer forces `pret_a_agir: false` on its own |

Do not assert the absence of conditional keys as a failure signal. Check `auth_status`
value (`"active"` / `"inactive"`), not its presence alone.

**Root vs `boussole` duplication:** `respect`, `auth_status`, and `derive_session`
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
- `--prompt TEXTE` — override the default LLM prompt used by `--comparer`
  (replaces the built-in comparison instructions with your own wording —
  useful to focus the model's attention on a specific zone or concern)
- `--seuil-bruit N` — max RGB delta per pixel to consider unchanged (default: 5)
- `--seuil-stable F` — upper bound for `stable` verdict (default: 0.002)
- `--seuil-regression F` — lower bound for `regression` verdict (default: 0.05)
- `--heatmap` — also produce a PNG heatmap of changed zones
- `--heatmap-tile N` — heatmap tile side in pixels (default: 16); a smaller
  tile gives finer-grained localisation of changed zones at the cost of a
  noisier-looking heatmap, a larger tile smooths minor pixel noise into
  fewer, broader blocks
- `--llm-en-complement` — re-run LLM diff only when pixel verdict is `drift` or `regression`
- `--exclure-zone X,Y,W,H` — ignore a zone during diff (repeatable)
- `--nom NOM` — named view, for multiple reference views per URL
- `--ntfy-url URL` — push alert to ntfy when regression detected
- `--timeout MS` — Playwright capture timeout for this run (default: 10000)
- `--sortie-json FICHIER` — redirect the verdict JSON to FICHIER instead of
  stdout (useful in cron mode alongside `--ntfy-url`, to keep a per-run
  artifact without relying on shell redirection)

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

## `--replay-verifier` — structural non-regression without pixels (v1.17.0)

Compares a run's structural surface (`http_status`, `dom_stats`,
`evaluations`, `elements_som` count) against a saved reference — CI-friendly,
no screenshot, no LLM call. Complements `watch.py --comparer-pixel` (visual)
rather than replacing it — this checks *structure*, not appearance.

```bash
# First run — save the reference
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario dashboard.json --sauver-verifier-reference ref.json

# Subsequent runs — compare
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario dashboard.json --replay-verifier ref.json
```

Verdict on stderr: `{"type_comparaison": "replay_verifier", "verdict": "stable"|"regression", "diffs": [...]}`.
Exit 1 on `regression`, `diffs` lists each mismatched field with `reference`
vs `obtenu`. Mutually exclusive with `--sauver-verifier-reference` (rejected
at parse time, exit 2, if both are passed).

**Scope — what is compared:** only volatile fields are excluded by
construction (timestamps, `operation_id`, `duree_ms`, `boussole.ip_locale`).
`elements_som` is compared by **count only**, not content — SoM element
identity across runs is not guaranteed stable (see `--som-rafraichir` below
for why).

**`chemin_sensible_refuse` (`rpa.py`, exit 2):** `--checkpoint`,
`--sauver-verifier-reference`, or `--replay-verifier` was pointed at a `..`
traversal or a system-sensitive location (Diwall's own install directories,
`/etc`, `/root`, `/boot`, `/sys`, `/proc`). Fix: pass a path under a
directory you control — these three flags write or read arbitrary files at
the path given, so the check exists to stop a scenario-supplied path from
reaching outside the working area.

### Writing reference-safe assertions (v1.19.0)

The exclusion list above (timestamps, `operation_id`, `duree_ms`,
`boussole.ip_locale`) only covers fields Diwall itself produces. Anything
your own `evaluer` actions read from the target page is your responsibility:
a `--sauver-verifier-reference` capture freezes `evaluations[]` values at
reference time. If a scenario reads a legitimately dynamic value — a visitor
counter, a live timestamp, a session-specific ID rendered in the DOM — every
later `--replay-verifier` run diffs against a value that has since changed,
producing a false `regression` on an actually healthy page.

**Wrong (brittle) — asserts the exact value:**
```json
{"type": "evaluer", "script": "document.querySelector('.visitor-count').textContent"}
```
Matches `"128"` at reference time, fails on the very next run once the
counter increments — a false regression, not a real one.

**Correct — assert the shape, not the value:**
```json
{"type": "evaluer", "script": "!isNaN(parseInt(document.querySelector('.visitor-count').textContent))"}
```
Returns a stable `true` regardless of the counter's actual reading — the
check is "a numeric counter is present and rendering", which is what a
structural non-regression test should verify.

Apply this whenever building a reference for `monitor-verifier.sh` or
`--replay-verifier`: any field expected to change between runs by design
(timestamps, counters, session tokens visible in the DOM) should be asserted
as a shape (`typeof`, a regex match, non-empty) — never as an exact value.

---

## Continuous structural monitoring — `scripts/monitor-verifier.sh` (v1.18.0)

`--no-capture` + `--replay-verifier` already combine into a zero-image,
zero-LLM structural check — no new comparison capability is needed for
repeated monitoring, only repetition. `scripts/monitor-verifier.sh` wraps this
composition into a single, versioned command instead of leaving it to be
reinvented in an ad hoc crontab line.

```bash
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --reference /tmp/ref_sillage.json \
  --ntfy-topic diwall-monitoring
```

**One pass per invocation — not a daemon.** No internal loop, no persistent
process. Runs `rpa.py --scenario <fichier> --no-capture --replay-verifier
<reference>` once, then exits. Stable → silence. Regression detected (exit 1
from `rpa.py`) → an `ntfy` notification with the diff detail.

**Repetition is your job, by design** — cron or a systemd timer, not the
script itself. `scripts/*.sh` is never copied by `deploy.sh` — it lives only
in the git source, so the cron entry runs from there, as the operator (not
the `diwall` service account, which has no access to `~/git/Diwall/Diwall/`):

```bash
# crontab -e (operator's own crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --reference /opt/diwall/references/sillage_login.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

Each invocation is an isolated process — no memory leak risk from a
long-running daemon, and Respectful Navigation caps (`max_pages_par_run`,
`max_actions_par_run`) reset cleanly on every run instead of accumulating
across an unbounded loop.

**Complements, does not replace, `watch.py`** — this checks *structure*
(`http_status`, `dom_stats`, `evaluations`, SoM count), `watch.py` checks
*appearance* (pixels or LLM-semantic diff). Run both if you care about both
dimensions of regression.

**First run — create the reference** (same as `--replay-verifier` above):
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --sauver-verifier-reference /opt/diwall/references/sillage_login.ref.json
```

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
| `source_scenario` | Scenario file name only, no path (v1.18.0) — set when `rpa.py --scenario` is used; lets `mode_conseille` reliably identify a `diagnostic_dom.json` run without parsing script contents |
| `chainage` | List of `{scenario, profondeur, action_debut, action_fin}` (v1.19.0) — present only when the scenario used `declencher_scenario`; built by `rpa.py::_aplatir_actions()` while inlining sub-scenarios, indices refer to the final flattened action list. Absent on a run without chaining. `journal.py` (root CLI) renders it as an indented tree under each matching entry. |
| `succes` | boolean |
| `modeles_appeles` | list of LLM models called during the run |
| `duree_ms` | wall-clock duration in ms |
| `erreur` | error message if `succes: false` |

**When to read the journal:** after a failure in cron mode (no terminal output),
or to audit which models were used in a given session.

**Filtering flags (`journal.py` root CLI):** `--mutatif` (only writing runs),
`--erreurs` (v1.20.0, only entries where `resultat != "succes"`), `--cible`,
`--depuis`/`--jusqu`, `--intention` — combine freely, all are AND-ed together.

---

## `latences_actions` — per-action timing (v1.20.0)

Every `shot.py` run includes a `latences_actions` list at the JSON root,
always present (empty list if no actions were passed). One entry per action
that actually dispatched — an action skipped because a navigation cap
(`max_actions_par_run`/`max_pages_par_run`) was hit before dispatch produces
no entry, consistent with `respect.actions_executees` not counting it
either.

```json
"latences_actions": [
  {"index": 0, "type": "naviguer", "latence_ms": 842},
  {"index": 1, "type": "cliquer_som", "latence_ms": 63},
  {"index": 2, "type": "attendre_selecteur_present", "latence_ms": 1204}
]
```

Complements `respect.duree_totale_ms` (global, single measurement at run
end): `latences_actions` breaks that total down per action, useful to spot
which specific step of a scenario is slow before reaching for
`--screenshot-timeout` or a longer `--timeout`. Measurement cost is nil — a
`time.time()` call already runs at each action dispatch.

---

## `etat` — deterministic operational verdict (v1.16.0, item A)

Every successful `shot.py` run includes an `etat` object at the JSON root —
a pre-computed verdict synthesizing the signals already present elsewhere in
the output, so you do not have to cross-reference `auth_status`,
`respect.plafond_atteint`, `derive_session`, and `erreurs_js` by hand
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
| `pret_a_agir` | boolean | `false` if authentication is inactive, session drifted, or a navigation cap was hit |
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

## `mode_conseille` — pre-flight configuration advice (v1.18.0)

A sub-key of `etat`, advisory only — never applied automatically, never an
order. Recommends a configuration (`--mode`, `--shadow-dom`,
`--som-rafraichir`) for your **next** call on the same host, based on real
prior measurement, never a guess.

```json
"etat": {
  "pret_a_agir": true,
  "niveau_confiance": "eleve",
  "raisons": ["aucun signal de friction détecté", "mode_conseille disponible : full recommandé (React détecté sur ce host)"],
  "mode_conseille": {
    "mode": "full",
    "shadow_dom": true,
    "som_rafraichir": false,
    "raisons": ["react_detecte", "shadow_roots:3"]
  }
}
```

**Where the signal comes from:** `shot.py` does not detect frameworks or
Shadow Roots on an ordinary call — that richer inventory comes specifically
from `scenarios/diagnostic_dom.json` (see "Reconnaissance before mutation" in
`GUIDE_LLM_INTERACTIONS.md`). `mode_conseille` looks up the operations journal
(`operations.jsonl`) for the most recent `diagnostic_dom.json` run against the
same host as the current call.

**Absent when there is nothing real to base it on** — a host never diagnosed
before gets no `mode_conseille`, not an invented default. Run
`diagnostic_dom.json` once against a target to start receiving advice on
subsequent calls to that host:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url https://target.local/ --mode fast
# next call to the same host may now carry etat.mode_conseille
```

**Treat it exactly like the WAF signal above:** a recommendation to weigh, not
an instruction to follow blindly. `mode_conseille` never changes the
configuration of the call that returns it — only future calls, and only if
you choose to act on the advice.

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

**Never expose credentials paths or values in cron commands.** Use `diwall.conf`
with `secrets_defaut` instead of `--secrets` in cron.

---

## Behavior after hitting a navigation cap (v1.15.2, Qwen Q3)

When `max_pages_par_run` or `max_actions_par_run` is reached, `shot.py` closes
the Chromium process cleanly (see `respect.plafond_atteint` in `boussole`).
This has consequences for state:

- **DOM state is destroyed** — open modals, unsubmitted form fields, scroll
  position are all lost with the browser process.
- **Session state (cookies, `localStorage`) survives only if `--sauver-session`
  was explicit** on this run. Without it, nothing is preserved.
- **Resuming via `--reprendre-session` reloads the saved URL from scratch** —
  it does not replay DOM interactions since the save.

**Planning consequence:** submit data (forms, confirmations) *before* the
navigation caps are likely to be reached. Only save session state at a point
where the DOM is stable (no open modal, no pending submission) — a save
mid-interaction is not a checkpoint, it is a snapshot of cookies only.

---

## Duration thresholds — suspecting a stuck run (v1.15.2, Qwen Q5)

`respect.duree_totale_ms` (root and `boussole`) measures wall-clock time
spent in `executer_actions()`. Indicative thresholds, not hard caps enforced by
the runtime:

- **Under 60 000 ms (1 minute):** normal for a simple exploration run.
- **Above 120 000 ms (2 minutes):** suspect a redirect loop or network
  congestion. Self-impose a semantic stop rather than waiting further — Diwall
  will not interrupt itself; there is no runtime timeout tied to this figure.

This is a recommendation for agent self-regulation, not a plafond configured in
`diwall.conf` (compare with `max_pages_par_run` / `max_actions_par_run`, which
are enforced).
