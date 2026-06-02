# Diwall — LLM Session Guide

Version 1.4 — June 2026

**You are a language model. This document tells you everything you need to operate Diwall.**

---

## What you are, where you are, what you do

You are a language model (Claude Code or equivalent) running on a machine with Playwright installed.
Diwall gives you **eyes on web interfaces**.

You call `shot.py` → it returns a JSON with a PNG path → you read the PNG directly (multimodal) → you analyse, correct, loop.

**You do not guess the rendering. You do not use `lynx`. You SEE it.**

Architecture in one sentence: `shot.py` = hands (executor). You = brain (intelligence, ReAct loop).

---

## Infrastructure

```
/opt/diwall/             ← production deployment
├── shot.py              ← main script (Phases 1–4)
├── watch.py             ← visual monitoring (Phase 5)
├── rpa.py               ← RPA scenario runner (Phase 6)
├── journal.py           ← operation log reader (v1.4)
├── diwall.conf          ← {"vault_dir": "~/Vaults/<project>/Diwall"}
├── venv/                ← isolated Python — ALWAYS use this venv
├── lib/
│   ├── vision.py        ← visual localisation (qwen3-vl:2b via Ollama)
│   ├── journal.py       ← operation log writer (v1.4)
│   ├── modeles.py       ← Ollama model metadata collector (v1.3)
│   ├── ntfy.py          ← async MFA bridge via ntfy (v1.6)
│   ├── profil_operateur.py ← operator profile loader (v1.3)
│   └── vault.py         ← credential vault reader + TOTP (v1.6)
├── scenarios/           ← RPA scenario files (JSON)
├── skills/              ← promoted replayable scenarios (v1.6)
└── references/          ← watch.py visual references

/tmp/diwall/             ← temporary PNG captures (cleared on reboot, owned by your user)
/var/log/diwall/         ← persistent operation log (v1.4)
  ├── operations.jsonl   ← append-only JSONL log
  └── preuves/           ← archived captures from mutating runs
~/Vaults/<project>/Diwall/  ← credentials vault (never in git)
```

**Mandatory invocation pattern:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <url>
```

After modifying source files in `~/git/Diwall/Diwall/`, deploy with:
```bash
bash ~/git/Diwall/Diwall/scripts/deploy.sh
```

---

## Mode A — Simple capture

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  [--som]    # annotated capture + elements_som list
  [--a11y]   # accessibility snapshot (YAML-like text)
```

JSON output:
```json
{
  "succes": true,
  "capture": "/tmp/diwall/capture_<ts>.png",
  "capture_som": "/tmp/diwall/state_som_<ts>.png",
  "elements_som": [{"id": 1, "tag": "INPUT", "role": "textbox", "texte": "Password"}],
  "a11y_tree": "- document:\n  - heading \"App\" [level=1]\n  ...",
  "http_status": 200,
  "url_finale": "https://target.local/",
  "duree_ms": 1240
}
```

---

## Mode B — ReAct step-by-step

**Step 1 — Initial navigation:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --navigate https://target.local/ \
  --sauver-session /tmp/diwall/session.json \
  --som --a11y
```

**Subsequent steps — ReAct action:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session /tmp/diwall/session.json \
  --action '{"type": "cliquer_som", "id": 2}' \
  --sauver-session /tmp/diwall/session.json \
  --som
```

**Atomic fill+submit (mandatory in SPAs — form values are NOT persisted in storage_state):**
```bash
--action '[{"type":"remplir_som","id":1,"valeur":"password"},{"type":"cliquer_som","id":2}]'
```

**With vault credentials:**
```bash
--action '[{"type":"remplir_som","id":1,"valeur":"depuis_vault","vault_cle":"password"},{"type":"cliquer_som","id":2}]'
```

---

## Mode RPA — Scenario file

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my_scenario.json --som
```

Scenario format:
```json
{
  "nom": "app_login",
  "url": "https://target.local/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "password"},
    {"type": "cliquer_som", "id": 2},
    {"type": "capturer",    "nom": "after_login"}
  ]
}
```

`shot.py` resolves `depuis_vault` at fill time (reading from the vault for the current page domain). `rpa.py` passes actions intact — credentials never appear in CLI arguments or process lists.

---

## Available actions

| Action | Key params | Notes |
|---|---|---|
| `naviguer` | `url` | Full HTTP reload — avoid in SPAs |
| `cliquer` | `selecteur` (CSS) | Mode A only |
| `remplir` | `selecteur`, `valeur` | `valeur` can be `"depuis_vault"` or `"depuis_vault_totp"` |
| `cliquer_som` | `id` | Exact DOM click via SoM |
| `remplir_som` | `id`, `valeur`, [`vault_cle`] | Exact DOM fill; `valeur` can be `"depuis_vault_totp"` |
| `cliquer_visuel` | `description` | LLM vision fallback (~32s, avoid if SoM works) |
| `attendre` | `selecteur` | Wait for CSS selector |
| `attendre_navigation` | — | Wait for networkidle |
| `capturer` | `nom` | Named intermediate capture |
| `pause` | `ms` | Fixed delay |
| `evaluer` | `script` | Runs `page.evaluate(script)`; result returned in `evaluations[]` (v1.1) |
| `defiler` | `px` or `selecteur` | Scroll viewport: relative pixels or `scrollIntoView` (v1.6) |
| `attendre_mfa_ntfy` | `id_som`, [`timeout`] | Wait for 2FA code via ntfy, type into SoM element (v1.6) |

### `evaluer` — DOM/JS introspection (v1.1)

Use when you need to read a value from the page (attribute, global, computed
state) without parsing a screenshot. Black-box targets: when you cannot see
the server source, `evaluer` lets the page speak for itself.

```json
{"type": "evaluer", "script": "document.title"}
{"type": "evaluer", "script": "window.MyApp?.version ?? null"}
```

Output is appended to `evaluations` in the JSON result, one entry per call:

```json
"evaluations": [
  {"index": 0, "script": "document.title", "valeur": "My App — home"}
]
```

Non-JSON-serializable values fall back to `str(value)` with an extra
`"serialisation": "str"` marker. The script is read from the scenario only —
never inject user input or URL parameters into it.

### `attendu` — assertion key for `evaluer` (v1.1, rpa.py only)

On an `evaluer` action, the optional `attendu` key turns the evaluation into
an integration assertion. `shot.py` ignores it; `rpa.py` reads the
`evaluations` from `shot.py`'s output and compares strictly (`==`).

```json
{"type": "evaluer", "script": "document.title", "attendu": "My App — home"}
```

On mismatch, `rpa.py` exits with code `1` and prints to stderr:

```
Assertion échouée action #N (evaluer) :
  script  : document.title
  attendu : "My App — home"
  obtenu  : "My App — home — Login"
```

No regex in v1.1 — strict equality only. Use one `evaluer` per assertion.

### `--interval-capture N` — periodic captures during long waits (v1.1)

Adds a screenshot every `N` seconds while a `pause`, `attendre` or
`attendre_navigation` is in flight. Opt-in: nothing happens without the flag
or the per-action key.

```bash
shot.py --url … --actions '[{"type":"pause","ms":10000}]' --interval-capture 2
```

Per-action override (wins over the CLI default):

```json
{"type": "attendre", "selecteur": ".loaded", "interval_capture": 1}
```

Output is written to `/tmp/diwall/stream/<run_id>/<action_index>_<t_ms>.png`
(mode 700). The JSON gains a `stream_captures` array with the same shape as
`evaluations`. Useful for cloning, exports, or slow probes where you want
to see the progression instead of just the final frame.

> **Playwright extended selectors** are supported in `cliquer` and `remplir`:
> `:has-text("…")`, `:visible`, `:nth-match(N)` work reliably.
> Avoid relational pseudo-selectors (`:left-of`, `:right-of`, `:near`) — version-sensitive and fail with silent timeout.
> Prefer intrinsic attributes (`[title*=…]`, `[aria-label=…]`) over positional selectors.

### `derive_session` — session drift warning (v1.2)

`shot.py --sauver-session` now embeds a `diwall_meta` block recording the URL
at the moment of saving. When you later run `shot.py --reprendre-session`,
the effective URL after the initial navigation is compared to that saved
URL. If they diverge, a `derive_session` key is added to the JSON output:

```json
{
  "succes": true,
  "url_finale": "https://app/settings",
  "derive_session": {
    "url_sauvegardee": "https://app/dashboard",
    "url_reprise":     "https://app/settings",
    "avertissement":   "URL at reprise time diverges from URL at save time. DOM state (checkboxes, filled fields, open modals) was not preserved..."
  }
}
```

**Read this signal carefully.** It means the assumption that DOM state
carried over from `--sauver-session` is unsafe. The save/restore mechanism
only preserves `storage_state` (cookies, localStorage), never the DOM.
If your workflow depends on a checkbox, a filled field, an open modal or
a current selection, re-plan it as a **single Mode A** invocation (one
`shot.py` call, one `actions` list). The drift warning exists precisely
to prevent the silent failure pattern described in `RETOUR_EXPERIENCE.md`
friction #20.

Legacy session files written by Diwall v1.1 (without `diwall_meta`) load
without error; drift detection is then disabled for that file and a
one-shot warning is printed on stderr.

### Scenario schema and validation (v1.2)

A formal JSON Schema (draft-07) now lives at `scenarios/schema.json` at
the repository root. It pins all 11 verbs (`naviguer`, `cliquer`,
`cliquer_som`, `cliquer_visuel`, `remplir`, `remplir_som`, `attendre`,
`attendre_navigation`, `pause`, `capturer`, `evaluer`), requires the
correct keys for each, and rejects unknown properties.

Annotate your scenarios with `$schema` for IDE-side validation:

```json
{
  "$schema": "../scenarios/schema.json",
  "nom": "my-test",
  "url": "https://example.com",
  "actions": [
    {"type": "evaluer", "script": "document.title"}
  ]
}
```

At runtime, `rpa.py` validates each scenario it loads if the `jsonschema`
Python package is available in the venv:

- **`jsonschema` installed** → validation is mandatory and blocking. A
  typo (`cliker_som`), a misplaced key (`attendu` on `attendre`), or a
  missing `vault_cle` when `valeur == "depuis_vault"` causes `rpa.py`
  to exit `1` with a structured diagnostic pointing at the offending
  field path.
- **`jsonschema` absent** → one-shot stderr warning, scenario runs as
  on v1.1. No hard dependency added.

Install in the production venv:

```bash
/opt/diwall/venv/bin/pip install jsonschema
```

Effects: typos that previously executed as silent no-ops (because
`shot.py` skips unknown `type` values) now fail fast at load time. This
closes the friction #21 class (`attendu` ignored silently on wrong verb).

### `watch.py --comparer-pixel` — local quantitative diff (v1.2)

Complements the existing semantic LLM diff (`--comparer`) with a
deterministic pixel comparison against a stored reference. Useful for
nightly drift surveillance where you want a quantitative verdict
instead of a one-second LLM call.

```bash
watch.py --comparer-pixel /path/to/reference.png \
         [--capture /path/to/current.png]      \
         [--seuil-bruit 5]                     \
         [--seuil-stable 0.002]                \
         [--seuil-regression 0.05]             \
         [--heatmap] [--heatmap-tile 16]       \
         [--llm-en-complement]
```

If `--capture` is omitted, a fresh PNG is taken from `--url` first.

Verdict bands:

| `taux_diff` | Verdict | Exit code | Artifacts |
|---|---|---|---|
| `< seuil-stable` (default 0.2%) | `stable` | `0` | none |
| `seuil-stable ≤ x < seuil-regression` | `drift` | `0` | diff image |
| `≥ seuil-regression` (default 5%) | `regression` | `1` | diff image (+ heatmap if `--heatmap`) |

Special exits: `2` if the capture and reference have **different
dimensions** (verdict `viewport_mismatch`, no auto-resize — interpolation
would corrupt the noise threshold; regenerate the reference); `3` on
I/O errors.

The diff image renders unchanged pixels as 50% grayscale and modified
pixels as saturated red. The optional heatmap (16×16 tiles by default)
encodes per-tile mean delta as a red gradient — useful for spotting
where the change concentrates.

NumPy is used when present (~200 ms on 1280×720); a Pillow-only
fallback handles light targets (Raspberry Pi) at the cost of ~10 s per
comparison. Numerical results are identical.

With `--llm-en-complement`, the v1.0 semantic LLM diff re-runs only
when the pixel verdict is `drift` or `regression`, and the LLM output
appears under `analyse_llm`. The pixel verdict remains primary; the LLM
adds qualitative context.

Install NumPy in the production venv (optional but recommended):

```bash
/opt/diwall/venv/bin/pip install numpy
```

---

## Set-of-Mark (SoM) — how to use it

`--som` injects a JS overlay that numbers all visible interactive elements.
You read `capture_som` (annotated PNG), identify the number you need,
pass that ID to `cliquer_som` or `remplir_som`.

**Why SoM is better than `cliquer_visuel`:**
- No LLM vision call → instant (vs ~32s)
- Exact DOM click (vs ±12% coordinate estimation)
- Works with any model, any size

`cliquer_visuel` remains available as fallback for canvas and non-ARIA components.

---

## Credential vault

**Format:** `~/Vaults/<project>/Diwall/<hostname>.json`
```json
{"password": "value", "username": "admin"}
```

**Resolution cascade:**
1. `DIWALL_VAULT_DIR` environment variable
2. `vault_dir` key in `/opt/diwall/diwall.conf`
3. Default: `~/Vaults/Diwall/`

**Per-project usage** — prefix your invocation to override the vault for a specific project:
```bash
DIWALL_VAULT_DIR=~/Vaults/MyProject/Diwall /opt/diwall/venv/bin/python3 /opt/diwall/shot.py …
```
For a permanent machine-wide default, set `vault_dir` in `/opt/diwall/diwall.conf`.

**Encrypted vault (v1.5.0+):** the vault directory can be a `gocryptfs` mountpoint.
Use `scripts/setup-vault.sh --gocryptfs` to initialise, `scripts/mount-vault.sh` to mount
(password via interactive prompt, never in arguments), `scripts/umount-vault.sh` to unmount.

If the vault is initialised (`gocryptfs.conf` present in the crypt dir) but **not mounted**,
every credential read raises `VaultFermeError` — both `shot.py` and `rpa.py` catch it,
return `{"erreur": "vault_ferme"}` in their JSON output, and exit with code **42**.
This lets the caller distinguish "wrong key" from "vault locked" without guessing.

```bash
# Exit code 42 = vault initialised but not mounted
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py … ; echo "exit: $?"
```

**Quick test:**
```bash
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.vault import lire_credential
print(lire_credential('target.local', 'password'))
"
```

---

## DOM mutations in Mode A — the SoM trap and how to escape it

SoM re-indexes on every capture. An `id` from capture N is meaningless in capture N+1.
This creates a problem when an element only appears **after** a first action (modal, conditional field, dropdown reveal).

**The solution: mix SoM and structural CSS selectors in the same action sequence.**

- Use `cliquer_som id=N` for elements visible in the first capture (you have them under your eyes when writing the JSON).
- Use `cliquer { "selecteur": "…" }` for elements that will appear later but whose HTML structure you can anticipate.

SoM is your exploration map. CSS selectors are your execution GPS.

**One-line rule:** Mode A breaks not when an element doesn't exist on screen yet, but when it doesn't exist yet in a structurally predictable form.

**Decision tree — how to target an element:**
1. Element visible in first capture → `cliquer_som id=N`
2. Element not yet visible, but present in HTML with a stable attribute (`#id`, `[name]`, `[data-*]`, `[aria-label]`) → `cliquer { "selecteur": "…" }`
3. Element appears after mutation, no stable attribute → `cliquer_visuel` (~32s, last resort) or Mode B as reconnaissance (one call, then back to Mode A)
4. DOM is fully generative (uuid-based ids, CSS-in-JS) → iterative Mode B or ask developers to add a stable `data-testid`

**Priority order for stable CSS selectors:**
1. `#id` — most stable (avoid if generated randomly by framework)
2. `[name=…]`, `[aria-label=…]`, `[title*=…]`, `[data-*=…]` — semantic attributes, survive DOM mutations
3. `:has-text("…")` — last resort, breaks on i18n changes

**Example — multi-step sequence with a modal that appears mid-sequence:**
```json
[
  {"type": "cliquer_som", "id": 3},
  {"type": "pause", "ms": 800},
  {"type": "capturer", "nom": "after_click"},
  {"type": "cliquer", "selecteur": "#dialog-action button[type=submit]"},
  {"type": "pause", "ms": 2000}
]
```

`#dialog-action button[type=submit]` is not visible in the first SoM capture, but it exists in the
rendered HTML (the `<dialog>` is just hidden by default). Its structure is invariant — safe to target.

**Using `capturer` to inspect intermediate state without breaking Mode A:**
`{"type": "capturer", "nom": "modal_open"}` generates a PNG in `output-dir` without interrupting
the session. Read these PNGs after the sequence to verify intermediate steps. This replaces Mode B
without its cost (no Playwright restart, no JS state loss).

**When to fall back to Mode B:**
If the target UI generates random `id={uuid}` per render (some JS frameworks), structural selectors
are unreliable. Use Mode B as **reconnaissance only**: one call with `--som` after the triggering
action to map stable attributes, then switch back to Mode A with those selectors for actual execution.

**Limit of this approach:**
All patterns above assume the future HTML is predictable (components rendered with stable attributes).
If every modal open generates a random id, the only honest recourse is iterative Mode B — or asking
developers to add a stable attribute.

---

## SPA navigation rules

If the target is a JavaScript SPA (single-page application):

1. **`url_finale` is unreliable** — the JS router may not update the address bar.
   Use `a11y_tree` heading as state detector instead.

2. **`naviguer` forces a full HTTP reload** that bypasses the SPA router.
   Use `cliquer_som` for in-app navigation, `naviguer` only for the initial URL.

3. **Form values are NOT persisted in `storage_state`** (cookies + localStorage only).
   Fill + Submit must be a single atomic action: `--action '[{fill},{submit}]'`

4. **`storage_state` does not preserve JS dialog state** (`dialog.showModal()`, overlays, etc.).
   Never use `--reprendre-session` to continue a sequence that depends on an open modal — the modal
   will be gone. Use Mode A with a single uninterrupted sequence instead.

---

## Multi-page authenticated pattern

`naviguer` keeps the browser context alive (cookies + storage) across calls.
Use it to validate N authenticated pages in a single Mode A invocation — no `--reprendre-session` needed.

```bash
--action '[
  {"type":"remplir_som","id":1,"valeur":"depuis_vault","vault_cle":"username"},
  {"type":"remplir_som","id":2,"valeur":"depuis_vault","vault_cle":"password"},
  {"type":"cliquer_som","id":3},
  {"type":"attendre_navigation"},
  {"type":"naviguer","url":"https://target.local/page-a"},
  {"type":"attendre_navigation"},
  {"type":"capturer","nom":"page-a"},
  {"type":"naviguer","url":"https://target.local/page-b"},
  {"type":"attendre_navigation"},
  {"type":"capturer","nom":"page-b"}
]'
```

Each `capturer` produces a PNG listed in `captures_intermediaires` in the final JSON.
`--reprendre-session` is never necessary for a validation walk-through.

---

## Ollama vision models on this machine

| Model | Size | Role | Speed |
|---|---|---|---|
| `qwen3-vl:2b` | 1.9 GB | **Default** — click localisation (`vision.py`) + semantic comparison (`watch.py`) | ~9–19s / ~1s |
| `qwen3-vl:8b` | 6.1 GB | Robust fallback — not default | ~114s |

`qwen3-vl:2b` became the default for both tools in v1.3.1, confirmed by 5/5 benchmark (2 June 2026). The digest is pinned in `_CADRE/SPECIFICATIONS/22_BENCHMARK_MODELES_VISION.md`; if `diwall_meta.modeles_utilises[].hash_tag_ollama` diverges from the pinned value, run the benchmark before concluding a regression.

Ollama API: use `/api/chat` with `think: false` (not `/api/generate`).

---

## Operator profile and model traceability (v1.3)

Every JSON output from `shot.py` and `watch.py` now carries a
`diwall_meta` block that documents the version of the script, the
ISO timestamp of the run, the active operator profile, and the
exact set of models that were called during the run.

```json
"diwall_meta": {
  "version_shot": "1.4.0",
  "horodatage_iso": "2026-06-02T14:23:11+02:00",
  "hostname_executant": "neo",
  "utilisateur_executant": "ron",
  "profil_actif": "operateur.exemple.yaml",
  "url_au_moment_capture": "https://target.local/",
  "modeles_utilises": [
    {
      "nom": "qwen3-vl",
      "version": "2b",
      "quantization": "Q4_K_M",
      "hash_tag_ollama": "sha256:0635d9d8…",
      "role": "localisation_clic"
    }
  ]
}
```

### Selecting an operator profile

Resolution order (first match wins):

1. `DIWALL_PROFIL` env var → absolute path to a YAML profile.
2. `~/git/Diwall/Diwall/diwall.conf.d/operateur.$(whoami).yaml`.
3. `/opt/diwall/diwall.conf` → key `profil_par_defaut`.
4. None → strict default: all confirmations active, traceability on.

### Profile YAML format

The template lives at `diwall.conf.d/operateur.exemple.yaml`. A
profile contains only **editable, active** parameters. Sanctuarisation
locks (red list) are coded in the runtime and cannot be lifted by
a profile — listing them in YAML would be a false affordance.

```yaml
nom_profil: my_profile

# Administrative frictions to lift — whitelist names only.
# Unknown names are ignored with a single stderr warning.
auto_confirmer:
  - ecriture_capture_tmp
  - ecriture_journal_diwall
  - invocation_ollama_locale

# Model traceability — on by default; turn off if you don't want
# `modeles_utilises` in diwall_meta.
tracabilite_modeles:
  active: true
  inclure_hash_ollama: true
```

Recognised `auto_confirmer:` names: `ecriture_capture_tmp`,
`montage_coffre_visuel`, `lecture_reference_chiffree`,
`ecriture_journal_diwall`, `invocation_ollama_locale`.

### Why this matters for you (LLM consumer)

If you compare runs over time and notice a regression on a fixed
visual target, `diwall_meta.modeles_utilises[].hash_tag_ollama`
lets you tell apart *« the page changed »* from *« the Ollama tag
was rebuilt with a different quantization »*. The Ollama digest is
the ground truth for the model that actually answered.

### Turning traceability off

```yaml
tracabilite_modeles:
  active: false
```

This omits the `modeles_utilises` key from `diwall_meta`. Other
keys (version, timestamp, profile) stay.

---

## Operation log — what did I do here? (v1.4)

Every run of `shot.py`, `watch.py`, and `rpa.py` is automatically appended to
`/var/log/diwall/operations.jsonl`. Before operating on a target, query the log:

```bash
# All operations on a target
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local

# Mutating operations only (form fills, clicks, DOM changes)
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --mutatif

# Filter by date and intent keyword
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local \
  --depuis 2026-06-01 --intention suppression
```

Sample output:
```
2026-06-02T08:41:59+02:00  [succes] ✏ MUTATIF  shot.py  https://target.local/
      intention : Delete clone allsys.online 2026-05-30
      actions   : cliquer_som#10, remplir_som#19=<saisie>, cliquer #btn-lot-confirmer
      preuves   : 2 → /var/log/diwall/preuves/2026-06/4bd9449655d8/…

1 opération(s).
```

### `--intention` flag

Pass a human-readable description of what a run is for — it appears in the log
and makes the history intelligible months later.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --intention "Nightly login smoke test" \
  --actions '[{"type":"pause","ms":100}]'
```

In an RPA scenario file, the optional `intention` key is equivalent:

```json
{
  "nom": "my_scenario",
  "intention": "Create new client christophe-leveque",
  "url": "https://target.local/",
  "actions": [ … ]
}
```

### Mutating vs read-only

The log classifies every run automatically:

- **`mutatif: true`** — at least one action that changes state (`cliquer*`,
  `remplir*`, `evaluer`). Captures are archived under
  `/var/log/diwall/preuves/AAAA-MM/<id>/` as a permanent audit trail.
- **`mutatif: false`** — read-only run (captures, waits, pauses). No archiving.

`--sauver-reference` on `watch.py` is always `mutatif: true` (overwrites a
sanctuarised reference).

### Credential safety in the log

Credentials from the vault are **never written to the log**. A `remplir_som`
with `depuis_vault` is recorded as `remplir_som#1=<vault:password>`. Any other
fill value is recorded as `<saisie>` (defence in depth — `rpa.py` no longer
resolves the vault before `shot.py`, but the log masking is unconditional).

### Procedural memory — skills (v1.6)

Every successful run stores its raw actions (vault-safe) in an `actions_raw`
field in the log. After a successful session, promote it to a replayable skill:

```bash
# Find the operation_id of the run you want to promote
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --limite 5

# Export as a named skill
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --exporter-skill a1b2c3d4e5f6 \
  --nom connexion_admin
# → writes /opt/diwall/skills/connexion_admin.json
```

Skills are plain scenario files in `/opt/diwall/skills/` — replay with `rpa.py --scenario`.

---

## Scroll and off-screen elements (v1.6)

### `defiler` — scroll the viewport

```json
{"type": "defiler", "px": 600}
{"type": "defiler", "px": -300}
{"type": "defiler", "selecteur": "form#checkout"}
```

`px` is relative (positive = down, negative = up). `selecteur` scrolls the element
into the center of the viewport. Exactly one parameter is required.

`defiler` is **not mutating** — it does not change state on the server and is not
classified as `mutatif` in the log.

### `som_hors_viewport` — off-screen interactive elements warning

When you capture with `--som`, the JSON may include:

```json
"som_hors_viewport": 3,
"avertissement_scroll": "3 élément(s) interactif(s) hors viewport — utilisez defiler avant cliquer_som"
```

This means **3 interactive elements exist in the DOM but are below the fold** and
were not numbered. Before using `cliquer_som` on one of them, scroll to it first:

```json
{"type": "defiler", "selecteur": "input#otp-field"},
{"type": "remplir_som", "id": 7, "valeur": "123456"}
```

When all elements are visible, these keys are absent from the JSON.

---

## 2FA / MFA (v1.6)

### TOTP — Google Authenticator / Authy (fully automatic)

Store the base32 seed in the vault under key `totp_cle`:

```json
{"username": "admin", "password": "...", "totp_cle": "JBSWY3DPEHPK3PXP"}
```

Use `"depuis_vault_totp"` as the fill value (no `vault_cle` needed — key is always `totp_cle`):

```json
{"type": "remplir_som", "id": 4, "valeur": "depuis_vault_totp"}
```

Diwall generates the current 6-digit code at fill time. The code is **never logged**.

### Async MFA via ntfy (SMS / email — requires human relay)

For codes received by SMS or email, Diwall cannot retrieve them automatically.
Use `attendre_mfa_ntfy`: Diwall pauses, notifies the operator via ntfy,
and waits for the human to publish the code.

Store the ntfy topic (a secret random string) in the vault:

```json
{"ntfy_topic": "a3f9c2e1b8d7k4m2"}
```

Generate a topic: `openssl rand -hex 12`

In the scenario:

```json
{"type": "attendre_mfa_ntfy", "id_som": 5, "timeout": 120}
```

The operator publishes the code from their phone or via curl:

```bash
curl -d "847291" https://ntfy.mon-serveur.local/a3f9c2e1b8d7k4m2
```

Diwall retrieves the code and types it into SoM element 5.

Configure the ntfy URL in `diwall.conf` or `DIWALL_NTFY_URL` env var (default: `https://ntfy.sh`):

```json
{"vault_dir": "~/Vaults/Diwall", "ntfy": {"url": "https://ntfy.mon-serveur.local"}}
```

---

## Visual monitoring (watch.py)

```bash
# Save visual reference
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference

# Compare semantically (LLM, qualitative)
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --comparer

# Compare quantitatively (pixel diff, deterministic, v1.2)
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --comparer-pixel /opt/diwall/references/<slug>/reference.png \
  --url https://target.local/ --heatmap
```

Choose `--comparer` when you need a verbal explanation of what changed
(e.g. *"the navigation menu is missing"*) — cost ~1 s per call. Choose
`--comparer-pixel` when you need a deterministic quantitative verdict
(stable / drift / regression) that scales to dozens of targets per night
— cost ~200 ms per call with NumPy. Both can be combined with
`--llm-en-complement`.

---

## AgentIc loop — your basic gesture

```
1. Modify code on the target server
2. Call shot.py on this machine → JSON with PNG path
3. Read PNG with Read() → direct multimodal analysis
4. Fix if needed → loop
```

**Quick start for a new session:**
```bash
# 1. Verify shot.py responds
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y

# 2. Read the capture
# → Read("/tmp/diwall/capture_<ts>.png")

# 3. If login required, use the existing RPA scenario
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/example_login.json --som

# 4. Loop: modify → capture → read → fix
```
