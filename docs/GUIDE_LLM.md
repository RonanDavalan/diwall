# Diwall — LLM Session Guide

Version 2.3 — June 2026

**You are a language model. This document tells you everything you need to operate Diwall.**

---

## ⚠ Security rules — read before anything else

These rules are non-negotiable. Violating them exposes credentials in clear text.

**FORBIDDEN — extracts password into shell environment and process table:**
```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER DO THIS
USER=$(jq -r '.username' ~/Vaults/.../file.json)    # NEVER DO THIS
```

**CORRECT — vault resolved inside Playwright by shot.py, never in the shell:**
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "username"}
{"type": "remplir_som", "id": 3, "valeur": "depuis_vault", "vault_cle": "password"}
```

The vault is read by `lib/vault.py` inside the Playwright process. Values never
appear in the shell, bash history, process list, or any log.

**Also forbidden:** using `curl`, `wget`, or any HTTP client other than shot.py/rpa.py
for authentication or page scraping. Diwall exists precisely to avoid this pattern.

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
├── diwall.conf          ← {"vault_dir": "~/Vaults/<project>/Diwall"} — machine-specific, created manually
├── diwall-sample.conf   ← generic template written by deploy.sh — copy → diwall.conf and configure
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

## Multi-model access — adding a service account

If you operate under a service account other than `ron`, add it to the `diwall` group:

```bash
sudo usermod -aG diwall <service_account>
```

Verify:
```bash
getent group diwall
# → diwall:x:NNN:ron,<service_account>
```

The group becomes active at the next login or immediately via `sg diwall -c "command"`.

**Architecture note:** Diwall runs on the operator's machine only. Target machines are
visited over HTTPS — no Diwall process, no `diwall` user, no Playwright runs on remote targets.

---

## Mode A — Simple capture

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  [--som]                          # annotated capture + elements_som list
  [--a11y]                         # accessibility snapshot (YAML-like text)
  [--auth-indicator "<css>"]       # passive auth state check (v1.9)
  [--no-capture]                   # skip PNG — semantic probe only (v1.9)
```

JSON output:
```json
{
  "succes": true,
  "auth_status": "active",
  "capture": "/tmp/diwall/capture_<ts>.png",
  "capture_som": "/tmp/diwall/state_som_<ts>.png",
  "elements_som": [{"id": 1, "tag": "INPUT", "role": "textbox", "texte": "Password"}],
  "a11y_tree": "- document:\n  - heading \"App\" [level=1]\n  ...",
  "http_status": 200,
  "url_finale": "https://target.local/",
  "duree_ms": 1240
}
```

`auth_status` is only present when `--auth-indicator` is provided.
`capture`, `capture_som`, `elements_som` are absent when `--no-capture` is active.

---

## Mode B — ReAct step-by-step

**Step 1 — Initial navigation:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
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

> **Shell escaping rule (REX friction #49):** for any `--action` containing JavaScript quotes,
> backslashes, or special characters, **always use `--actions /tmp/file.json`** — never inline.
> Shell interpretation silently corrupts the JSON before it reaches shot.py.
> ```bash
> cat > /tmp/actions.json << 'EOF'
> [{"type":"evaluer","script":"document.querySelector('#field').value"}]
> EOF
> /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url … --actions /tmp/actions.json
> ```

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
| `remplir` | `selecteur`, `valeur` | `valeur` can be `"depuis_vault"` or `"depuis_vault_totp"`. **Does not work on `<select>` elements** — use `evaluer` with `HTMLSelectElement.value` or `remplir_som` instead. |
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
| `nettoyer_overlay` | `selecteur` | Mask fixed/sticky overlays before SoM injection. Explicit CSS selector required — no auto-detection. Forbidden in `watch.py` QA scenarios (would hide layout regressions). Execute **before** SoM generation. (v1.9) |
| `attendre_url` | `motif`, [`attendre_changement`] | Wait until current URL contains `motif`. **Partial match** — resolves immediately if current URL already contains `motif`. Set `"attendre_changement":true` to wait for a navigation away from the current URL first (FR-55, v1.8.0). |
| `attendre_selecteur_present` | `selecteur` | Wait for element to become visible. Uses `page.wait_for_selector(state="visible")`. Use to confirm a successful login before continuing. (v1.9) |
| `attendre_absence` | `selecteur` | Wait for element to disappear (spinner, loading veil). Uses `page.wait_for_selector(state="detached")`. (v1.9) |
| `attendre_reseau_calme` | [`timeout_ms`] | Wait for 500ms network silence. Uses `page.wait_for_load_state("networkidle")`. `timeout_ms` = max wait before abort (distinct from the 500ms silence threshold). (v1.9) |

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
>
> **`:nth-match` chaining rule (FN6):** `:nth-match()` is a top-level engine — it cannot be chained as a suffix.
> ```
> // WRONG — Playwright error: "nth-match engine expects non-empty selector list and an index argument"
> button:has-text("Texte"):nth-match(2)
>
> // CORRECT — :nth-match() wraps the full selector expression
> :nth-match(button:has-text("Texte"), 2)
> ```

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

**`diwall.conf` must exist before any vault operation.** It is not created automatically
by `deploy.sh` — only `diwall-sample.conf` (generic template) is. If absent, vault
operations fail immediately with a structured error message inviting you to run:
```bash
sudo cp /opt/diwall/diwall-sample.conf /opt/diwall/diwall.conf
# then edit vault_dir with the real vault path for this machine
```

**Resolution cascade (v1.8):**
1. `DIWALL_VAULT_DIR` env var — direct path override
2. `DIWALL_CONF` env var → reads the JSON file it points to → `vault_dir` key (relative path resolved from the conf file's directory)
3. `vault_dir` key in `/opt/diwall/diwall.conf` — machine-wide default
4. `~/Vaults/Diwall/` — universal fallback

**Per-project usage** — place a `.diwall.conf` at your project root, then point `DIWALL_CONF` to it:
```bash
echo '{"vault_dir": "../MyProject-vault"}' > ~/git/MyProject/.diwall.conf
DIWALL_CONF=~/git/MyProject/.diwall.conf /opt/diwall/venv/bin/python3 /opt/diwall/shot.py …
# vault_dir resolved relative to the .diwall.conf file's directory
```
For a one-shot override without a project conf, use `DIWALL_VAULT_DIR` directly.
For a machine-wide default, set `vault_dir` in `/opt/diwall/diwall.conf`.

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

**Domain names in link selectors — strict mode violation (FN5):** a domain like `example.fr` typically
appears in multiple `<a>` elements on the same page (header badge, clone link, breadcrumb).
`a:has-text("example.fr")` hits all of them and Playwright strict mode refuses.
Never use domain names as link text selectors. Prefer:
- Navigate by direct URL (`naviguer` or `--url`) when the target page is known
- Use a stable CSS class, `[data-domain]`, or structural context (`table tr:nth-child(N) a`) to disambiguate

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

`#dialog-action button[type=submit]` is not visible in the first SoM capture because, as of v1.7.3,
**SoM excludes all elements inside a closed `<dialog>` (no `open` attribute)**. This is intentional:
a closed dialog is not interactable, and indexing its buttons caused silent mis-clicks when several
dialogs were present in the DOM simultaneously (REX friction #34). The CSS selector approach is still
correct and recommended — it targets the button by its structural identity regardless of SoM indexing.

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
  "hostname_executant": "__HOSTNAME__",
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

---

## Execution context (`boussole`) — v1.7.3

Every JSON response from `shot.py` and `rpa.py` now includes a `boussole` field:

```json
"boussole": {
  "utilisateur": "ron",
  "ip_locale": "__IP_LAN__",
  "repertoire": "/opt/diwall"
}
```

`boussole` is always present — including on error responses. Use it to passively verify
the execution context at every chained call, without running separate shell commands.

**Expected values on your machine (`__HOSTNAME__`):**

| Field | Expected |
|---|---|
| `utilisateur` | `ron` |
| `ip_locale` | `192.168.1.x` |
| `repertoire` | `~/git/Diwall/Diwall` (dev) or `/opt/diwall` (production) |

**Why this matters in chaining:** if a mid-chain call returns an unexpected `ip_locale`
or `repertoire`, it signals an execution context drift before it causes silent failures.
Check `boussole` the same way you check `succes` — it costs nothing and prevents a class
of hard-to-diagnose environment bugs.

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

### Log rotation and disk management

`operations.jsonl` grows indefinitely. Configure `logrotate` to rotate it:

```
# /etc/logrotate.d/diwall
/var/log/diwall/operations.jsonl {
    daily
    rotate 30
    compress
    missingok
    notifempty
    copytruncate
}
```

`journal.py` reads rotated files automatically (`.1`, `.2.gz`, …) — no loss of history after rotation.

The `/var/log/diwall/preuves/` directory stores archived captures from mutating runs and grows with every mutating run. There is no auto-cleanup. Review and prune manually, or add a `find`-based cron:

```bash
# Keep proofs for 90 days
find /var/log/diwall/preuves/ -mtime +90 -delete
```

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

**Skills are strict replays**, not adaptive templates. They replay the exact sequence of actions recorded (SoM IDs, selectors, values). If the target page changes structure — new layout, different SoM numbering, renamed selectors — the skill will fail silently or act on a wrong element. Re-record by running a new session on the updated page and exporting the new `operation_id`.

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

**Common mistake (FN9):** the fields `direction` and `pixels` do not exist — `additionalProperties: false`
rejects them with a schema validation error. Use `px` (integer) or `selecteur` (string).

```json
// WRONG — schema rejection
{"type": "defiler", "direction": "bas", "pixels": 800}

// CORRECT
{"type": "defiler", "px": 800}    // scroll down 800px
{"type": "defiler", "px": -800}   // scroll up 800px
```

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

### SoM IDs after a scroll — always recapture

SoM IDs are computed from the viewport state **at the moment of the `--som` capture**. After a `defiler` action, the viewport has shifted: elements that were off-screen are now visible, elements that were visible may have scrolled out. The previous IDs are **invalidated**.

**Rule:** any time you use `defiler`, follow it with a new `shot.py --som` invocation before using `cliquer_som` or `remplir_som`. The new capture returns a fresh `elements_som` list with recalculated IDs reflecting the current viewport.

```json
{"type": "defiler", "selecteur": "#deep-section"},
{"type": "capturer", "nom": "after_scroll"}
```

`capturer` alone does **not** recalculate SoM IDs — it produces a PNG without a new `elements_som`. For a fresh index, run a new `shot.py --som` call. Alternatively, use `defiler` with `selecteur` pointing at the exact element and skip SoM entirely, relying on a structural CSS selector (`cliquer` / `remplir`) for the interaction.

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

## `--auth-indicator` — passive authentication check (v1.9)

Pass a CSS selector that is only visible when the user is authenticated.
After all actions complete, Diwall checks `page.locator(selector).is_visible()`
and adds `auth_status` at the root of the JSON output.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --reprendre-session session.json \
  --auth-indicator ".user-menu"
```

| `auth_status` value | Meaning |
|---|---|
| `"active"` | Selector is visible — session likely authenticated |
| `"inactive"` | Selector is absent or hidden |
| key absent | `--auth-indicator` was not provided |

**Semantic note:** `auth_status: "active"` means the selector is visible — not that
the session is authenticated. The mapping between DOM visibility and auth state
is the agent's responsibility. Diwall reports a DOM fact, not an interpretation.

In scenario files (`rpa.py`), declare `auth_indicator` at the root:
```json
{
  "nom": "pretix_login",
  "url": "https://target.local/",
  "auth_indicator": ".context-name",
  "actions": [...]
}
```

---

## `--no-capture` — semantic probe without PNG (v1.9)

Skips the final screenshot, SoM injection, and disk writes.
Use for routine DOM checks where visual feedback is not needed.

**Nominal pattern — pure semantic probe:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --reprendre-session session.json \
  --no-capture --a11y \
  --auth-indicator ".user-menu" \
  --actions '[
    {"type": "evaluer", "script": "document.querySelectorAll(\".event-row\").length"},
    {"type": "evaluer", "script": "document.title"}
  ]'
```

Output: `evaluations[]`, `a11y_tree`, `auth_status` — no `capture`, no `elements_som`.

**Compatible combinations:**

| Combination | Result |
|---|---|
| `--no-capture` + `--a11y` | **Allowed** — nominal pattern |
| `--no-capture` + `evaluer` actions | **Allowed** — data extracted without PNG |
| `--no-capture` + `--sauver-session` | **Allowed** — session saving does not require PNG |
| `--no-capture` + `--auth-indicator` | **Allowed** — DOM check, no PNG needed |
| `--no-capture` + `--som` | **Blocking error** — SoM requires a PNG |
| `--no-capture` + `{"type":"capturer"}` in actions | **Blocking error** — detected before Playwright starts |

**Performance:** saves ~1–2s (screenshot + SoM injection + disk I/O).
Total execution time remains ~2–3s (Chromium launch is incompressible at ~1–1.5s).

---

## Reconnaissance before mutation (bloquant)

Before writing any mutating action (`cliquer`, `cliquer_som`, `remplir`, `remplir_som`,
or a `evaluer` that submits a form or triggers a click) on a feature **never previously
tested with Diwall on this interface**, you must run a read-only exploration pass first.

**Signals that indicate unknown territory:**
- No dated workaround for this feature in the project's `VAL_valider-ui.md` (or equivalent)
- Feature not covered in this guide
- First time this action × interface combination is attempted

**Mandatory procedure — complete before writing the operational scenario:**

```bash
# Step 1 — Visual map: SoM + a11y tree
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url <target_url> --som --a11y [--reprendre-session session.json]

# Step 2 — DOM inventory: exact button texts, input names, select values
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url <target_url> [--reprendre-session session.json] --no-capture

# Step 3 — Read the eval results: extract selectors, button texts, checkbox values

# Step 4 — Write the complete operational scenario in one pass

# Step 5 — Execute once via rpa.py — no trial-and-error
```

**What is forbidden:** launching a mutating action without completing steps 1–3.
Building the operational scenario across multiple trial invocations (intermediate failures
create server-side side effects — REX FN8: parasitic clones, orphaned records).

**Why `diagnostic_dom.json`:** writing inline JS introspection scripts on the fly risks
quoting errors (REX friction #49). The pre-built scenario eliminates that risk.

---

## Error recovery — Stop-and-Search rule (bloquant)

Si une action retourne `succes: false` ou une erreur Playwright, il est **interdit** de
soumettre immédiatement un script corrigé. Séquence obligatoire avant toute correction :

1. Interroger le RAG local (`search-index.py`) sur le message d'erreur exact
2. Relire la section de ce guide correspondant à l'erreur
3. Déclarer l'analyse : cause identifiée, règle violée
4. Proposer la correction

**Aucun fichier `actions_v2.json` / `_v3.json` dans `/tmp/` sans cette étape.**

Cette règle est bloquante — elle n'est pas implicite dans la doctrine ReAct. Trois cycles
perdus en PHASE_VALIDATION C2 Sillage (11/06/2026) sur des erreurs explicitement documentées
dans ce guide (navigation post-login, sélecteurs nth-match).

---

## Known CLI pitfalls

### Journal warning on stdout — always parse with `| tail -1`

`shot.py` may emit `⚠ journal : log principal inaccessible` to **stdout** before the JSON
when the log directory is inaccessible. This breaks piped JSON parsing (REX friction #48).

**Always parse output this way:**
```bash
result=$(/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url … 2>/dev/null | tail -1)
python3 -c "import json,sys; print(json.loads(sys.stdin.read()))" <<< "$result"
```
`2>/dev/null` suppresses stderr; `tail -1` ensures you capture only the JSON line.

### `naviguer` in a resumed Django session redirects to dashboard

Using `{"type":"naviguer","url":"/control/some-page/"}` inside a `--reprendre-session` call
on a Django application (Pretix, etc.) silently redirects to the dashboard (REX friction #50).

**Workaround:** pass the target URL as `--url` directly to `shot.py`, not as a `naviguer` action.
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://host/control/some-page/ \
  --reprendre-session session.json --som
```

### `--actions` (file) silently ignored with `--reprendre-session` (FR-54)

In `--reprendre-session` mode (Mode B), only `--action` (inline JSON) is loaded.
`--actions /path/to/file.json` is **silently ignored** — the actions file is never read,
the fields stay empty, the login appears to succeed but does nothing (REX session 19).

**Rule:** in Mode B, always use `--action` (inline):
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session session.json \
  --action '[{"type":"remplir_som","id":2,"valeur":"depuis_vault","vault_cle":"username"}]' \
  --sauver-session session.json --som
```

**In Mode A (`--url`)**, `--actions /tmp/file.json` works correctly.

**Fixed in v1.8.0:** `--actions` file is now supported in Mode B (FR-54). Both modes are symmetric.

---

### `attendre_url` partial-match false positive (FR-55)

`attendre_url` uses `page.wait_for_url("**motif**")` which is a **substring match**.
The motif `/control/` matches the current URL `/control/login/` **immediately**, before
any navigation occurs. The action returns instantly with no post-login redirect.

**Never use a motif that is a substring of the current URL.**

```json
// BAD — /control/ matches /control/login/ immediately
{"type": "attendre_url", "motif": "/control/"}

// GOOD — use attendre_selecteur_present on an element that only exists post-login
{"type": "attendre_selecteur_present", "selecteur": ".context-name"}

// GOOD — use a motif that does NOT appear in the login URL
{"type": "attendre_url", "motif": "/control/dashboard"}
```

**Rule after any form submit:** always use `attendre_selecteur_present` on a
structural element that is only present on the post-login page. This is unambiguous
regardless of URL structure.

---

### SoM IDs invalidated after any DOM mutation (FR-56)

The "SoM IDs after a scroll" rule (see below) applies to **any** DOM mutation, not
only scrolls. Cookie consent banners, modals, overlays, flash messages — all of these
modify the interactive element count and **invalidate all previous SoM IDs**.

**Pattern:** accept cookie banner → DOM changes → SoM IDs shift → `cliquer_som 13` crashes.

**Rule:** after any action that adds or removes visible DOM elements (cookie banner
dismissal, modal open/close, overlay disappearance), always run a fresh `shot.py --som`
before using `cliquer_som` or `remplir_som`. Never reuse IDs across DOM mutations.

```bash
# Step 1: dismiss the cookie banner
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session session.json \
  --action '[{"type":"cliquer_som","id":2},{"type":"attendre_reseau_calme"}]' \
  --sauver-session session.json

# Step 2: re-capture SoM — IDs have changed
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session session.json --som
# → Read the new capture, use the new IDs
```

---

### Save session only after full auth redirect completes

Saving the session immediately after the login submit captures an incomplete state — auth
cookies are not yet established (REX friction #51). Same root cause as friction #5.

**Rule:** login + post-login navigation must be a single atomic action list. Never insert
`--sauver-session` between the form submit and the first authenticated page load.
```json
[
  {"type": "remplir_som", "id": 1, "valeur": "depuis_vault", "vault_cle": "username"},
  {"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "password"},
  {"type": "cliquer_som", "id": 3},
  {"type": "pause",        "ms": 2000},
  {"type": "naviguer",     "url": "https://host/dashboard/"},
  {"type": "capturer",     "nom": "post-login"}
]
```

### `attendre_absence` timeout on first form submission (REX #66)

`attendre_absence` polls `page.wait_for_selector(state="detached")` immediately after the
click. On the **first POST submission** of a scenario, Playwright has not yet started
processing the server response — every poll sees the login form still present, and the
10 s timeout fires even though the login succeeded server-side.

**Root cause:** `session_regenerate_id(true)` issues a new cookie, Playwright follows the
redirect — but polling starts before that redirect is processed. Subsequent submissions in
the same session do not reproduce the issue because Playwright's navigation pipeline is
already warm.

**Do not use `attendre_absence` immediately after the first form submit.** Use `pause` +
`evaluer` on the target URL instead:

```json
{"type": "cliquer",  "selecteur": "button.login-bouton"},
{"type": "pause",    "ms": 2000},
{"type": "evaluer",  "script": "!window.location.href.includes('vue=login')", "attendu": true}
```

**`attendre_absence` is safe** on subsequent submissions within the same session (Playwright
pipeline warm), and for spinners / loading veils that appear *after* a page has fully loaded.

**Related:** friction #5 (session_regenerate_id timing), friction #16 (same family).

---

### `DIWALL_VAULT_DIR` vs `DIWALL_CONF` — different semantics (FR-58)

Both env vars are supported by `vault.py`, but they point to **different things**:

| Env var | Points to | When to use |
|---|---|---|
| `DIWALL_VAULT_DIR` | A **directory** containing `<hostname>.json` files directly | Simple vault with flat structure, no conf indirection |
| `DIWALL_CONF` | A **`.diwall.conf` file** (JSON) with a `vault_dir` key | Per-project vault with conf indirection (recommended) |

**Common mistake (FR-58, REX Gemini benchmark 09/06/2026):** setting `DIWALL_VAULT_DIR` to
the directory that *contains* the `.conf` file — this is wrong. `DIWALL_VAULT_DIR` bypasses
the conf file entirely and expects credential JSON files at that path directly.

```bash
# WRONG — ~/Vaults/ProjectX/ contains diwall.conf, not hostname.json files
DIWALL_VAULT_DIR=~/Vaults/ProjectX/ python3 shot.py …

# CORRECT — points to the .conf file which resolves vault_dir internally
DIWALL_CONF=~/Vaults/ProjectX/diwall.conf python3 shot.py …
```

**Rule:** for any project that uses a `.diwall.conf` file for per-project vault configuration,
always use `DIWALL_CONF`. Reserve `DIWALL_VAULT_DIR` for simple flat vaults where `<hostname>.json`
files sit directly in the pointed directory.

### Long server-side operations — `attendre_reseau_calme` and screenshot timeout (FN7)

`Page.screenshot` has a **30-second hard timeout** inside Playwright that cannot be controlled
by `rpa.py`'s `--timeout` flag. When `attendre_reseau_calme` waits for network silence and the
server is processing a synchronous long operation (~1 min PHP clone, heavy export, etc.), the
screenshot fires before the operation completes and the scenario aborts.

**Rule:** never chain `attendre_reseau_calme` on a trigger whose server-side duration may exceed ~20s.
Use a fixed `pause` instead — it hands timing control to the scenario author:

```json
// WRONG — Playwright screenshot timeout (30s) fires before PHP clone finishes (~60s)
{"type": "evaluer", "script": "...click clone button..."},
{"type": "attendre_reseau_calme"}

// CORRECT — wait long enough for the server operation, then capture
{"type": "evaluer", "script": "...click clone button..."},
{"type": "pause", "ms": 150000},
{"type": "capturer", "nom": "after_clone"}
```

Tune `pause` to match the expected server duration + margin. `capturer` does not trigger a
screenshot timeout — it is compatible with long waits.

### Mutating `evaluer` and server state after a failed scenario (FN8)

`evaluer` sends a JS instruction to the page **immediately** — before any subsequent `attendre_*`
action. If the scenario fails after a mutating `evaluer` (clone trigger, delete button, form
submit), the server-side operation may have already started or completed.

**Diwall cannot cancel an action that has already been dispatched to the server.**
If you relaunch the scenario after a failure, you may create duplicate server-side artefacts
(clones, records, jobs).

**Rule:** after any failed scenario containing a mutating `evaluer`, verify the server state
before relaunching:

1. Capture the target page (Mode A, no actions) and inspect the result
2. Confirm whether the server-side operation completed, is in progress, or did not start
3. Only relaunch the scenario from the point after the successful mutation

This rule applies to all `evaluer` scripts that trigger side effects (click on submit/confirm
buttons, JS form dispatch, delete triggers).

---

### CSS-only dialogs — `cliquer` timeout on hidden containers (REX FR-57)

Some interfaces use `<div>` elements with CSS visibility (`display: none → block`) for
confirmation dialogs instead of the HTML `<dialog open>` attribute. Playwright evaluates
interactability via CSS layout and **refuses to click a button inside a CSS-hidden
container** → `Locator.click: Timeout 10000ms exceeded`.

**Affected pattern (Sillage):** "Lancer le clonage", "Supprimer définitivement", any
Sillage confirmation dialog.

**Mandatory pattern — always use `evaluer` + JS, never `cliquer` or `cliquer_som`:**
```json
{
  "type": "evaluer",
  "script": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Exact button text')?.click()"
}
```

**Diagnosis rule:** if a click on a confirmation button times out and the dialog has no
`open` attribute in the a11y tree, suspect CSS-only visibility. Switch to `evaluer`
immediately — do not retry `cliquer` with different selectors.

**FN10 — Extended scope: the button that *opens* the CSS modal (13/06/2026)**

FD1 applies not only to buttons *inside* the CSS modal but also to the button that *opens*
it. `cliquer button:has-text("Lancer un clonage")` → timeout "waiting for scheduled
navigations to finish". Same mandatory pattern:

```json
{"type": "evaluer", "script": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Lancer un clonage'))?.click()"}
```

**FN11 — `capturer` timeout while a CSS modal is open (13/06/2026)**

When a CSS Sillage modal is visible (JS show/hide, no `<dialog>`), `capturer` times out
at 30s. Playwright waits for font loading — the open modal blocks resolution.

**Rule:** remove any intermediate `capturer` while the CSS modal is in the open state.
Capture only after the modal closes (end of clone, post-submit navigation, etc.).

---

### Batch deletion dialog — native `<dialog open>` with `cliquer` timeout (FN12)

The batch deletion flow (checkboxes + select "supprimer" + Appliquer) opens a native
`<dialog open>`. Two sub-problems:

1. **Button text is "Supprimer définitivement" — never "Confirmer".** `cliquer dialog[open]
   button:has-text("Confirmer")` → timeout (button does not exist).
2. **`cliquer` Playwright native on `dialog[open] button` times out** even when the dialog
   is open. Use `evaluer` for both buttons (Appliquer and the confirmation button):

```json
{"type": "evaluer", "script": "Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Appliquer')?.click()"},
{"type": "pause", "ms": 1000},
{"type": "evaluer", "script": "Array.from(document.querySelectorAll('dialog[open] button')).find(b=>b.textContent.includes('Supprimer'))?.click()"}
```

---

### Batch checkboxes — prefer a single `evaluer` over multiple `cliquer` (FN13)

Multiple successive native Playwright `cliquer` calls on checkboxes can trigger timeouts
with a final URL of `vue=login` (unstable PHP session or unexpected redirect).

**Rule:** check all target boxes in a single `evaluer` JS call:

```json
{
  "type": "evaluer",
  "script": "(function(){ var cibles=['value-1','value-2','value-3']; Array.from(document.querySelectorAll('input[type=checkbox]')).filter(cb=>cibles.includes(cb.value)).forEach(cb=>{cb.checked=true;cb.dispatchEvent(new Event('change',{bubbles:true}));}); })()"
}
```

Replace `value-1`, `value-2`, … with the exact `value` attributes retrieved via
`diagnostic_dom.json` (input inventory, `type: checkbox`).

---

### CSS-hidden inputs — `cliquer` timeout on toggle-switch pattern (REX #61)

`<input type="checkbox">` hidden via CSS (e.g. `toggle-switch` pattern) is present in the
DOM but invisible to Playwright's layout engine. `cliquer` → timeout, even with `--timeout`.

**Rule:** For any CSS-hidden input, skip `cliquer` entirely — go directly to `evaluer`:

```json
{"type": "evaluer", "script": "document.querySelector('[data-sillage=\"toggle-wp-debug\"]').click()"}
```

`.click()` via JS bypasses Playwright's interactability checks (visibility, coverage).

---

### Conditional button with JS guard — silent no-op on `cliquer` (REX #62)

A button whose JS callback returns early based on a `<select>` value (e.g. `if select.value === ""
return`) looks clickable but produces no effect. Playwright reports `succes: true`, no dialog opens,
no error.

**Rule:** Before clicking any button that depends on a `<select>` value, force the value via
`evaluer` and confirm the effect with `attendre_selecteur_present`:

```json
[
  {"type": "evaluer", "script": "document.querySelector('[data-sillage=\"select-action-lot\"]').value = 'supprimer'"},
  {"type": "cliquer", "selecteur": "[data-sillage='btn-appliquer-lot']"},
  {"type": "attendre_selecteur_present", "selecteur": "dialog#dialog-lot[open]"}
]
```

A "successful" click does not prove the intended effect occurred — always verify with a selector.

---

### Native `<dialog>` opened via `showModal()` — `cliquer` timeout (REX #63)

A button inside a `<dialog>` opened via `showModal()` (HTML native, not CSS show/hide) can still
timeout with Playwright `cliquer`, even after `attendre_selecteur_present` confirms `dialog[open]`.

**Rule (general):** If the parent container was opened/shown via JS — whether CSS show/hide (FR-57)
or `showModal()` — do not attempt `cliquer`. Use `evaluer` directly:

```json
{"type": "evaluer", "script": "document.querySelector('[data-sillage=\"btn-annuler-lot\"]').click()"}
```

This extends FR-57 to all JS-controlled containers.

---

## When NOT to use Diwall

Diwall excels at short functional scenarios and shared visual verification. There are cases where it is the wrong tool — using it in these situations costs tokens, produces timeouts, and can leave the server in an inconsistent state.

### FR-59 — Long server-side operations (do not use Diwall)

**Context:** Playwright's internal `Page.screenshot` timeout is fixed at 30 seconds and is not configurable per action. The `--timeout` parameter of `rpa.py` controls the overall run timeout, not individual action timeouts.

**Consequence:** Any server-side operation that takes more than ~20–30 seconds (WordPress clone ~2–5 min, Matomo rebuild, database import) will cause `attendre_reseau_calme` or the final capture to timeout. The scenario fails even if the server-side operation completed successfully.

**Rule:** For long operations, prefer a direct SSH dispatcher call or an API endpoint. Use Diwall only to verify the result *after* the operation completes:
```bash
# Wrong: Diwall waiting for a 3-minute clone
{"type": "cliquer_som", "id": 5},
{"type": "attendre_reseau_calme"}   # ← will timeout at 30s

# Correct: trigger via SSH dispatcher, then verify with Diwall
ssh target "wp core clone …"        # runs to completion
# then: Diwall shot.py to verify the result visually
```

### FR-60 — Mutating actions before a long wait (use with caution)

**Context:** A `evaluer` JS click that triggers a server-side mutation (clone, delete, import) is dispatched to the server immediately — before Diwall's timeout fires. If Diwall then times out on `attendre_reseau_calme` or the capture, the server-side mutation has already been executed.

**Consequence:** Retrying the scenario creates a duplicate mutation (second clone, second delete). The server is now in an inconsistent state that Diwall cannot roll back — Diwall has no undo capability.

**Rule:** After any scenario that fails on a step following a mutating action, verify the server state before replaying:
```bash
# Before replaying: passive capture to check what the server did
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url <target_url> --a11y --no-capture
# → read the a11y_tree to confirm whether the mutation already happened
```

### Summary — cases where Diwall is not recommended

| Case | Reason | Alternative |
|---|---|---|
| Server operation > 20–30 s | FR-59 — Playwright screenshot timeout not configurable | SSH dispatcher + Diwall for verification only |
| Batch mutations (delete 50 items) | Unreliable at scale, FR-60 risk on failure | Direct batch API call |
| Mutating action + long wait | FR-60 — orphan mutation on timeout | Split: trigger via API, then verify with Diwall |
| Workflows requiring rollback | Diwall cannot undo a dispatched action | Application-level rollback before Diwall retry |

---

## See also

- `docs/FAQ_LLM.md` — answers to recurring LLM questions (Shadow DOM, `--no-capture` guarantees, dry-run, version map, PDF/image analysis)
- `docs/GUIDE_EXPLORATION.md` — exploring an unknown interface
- `docs/RETOUR_EXPERIENCE.md` — terrain frictions and resolutions
- `docs/RADAR_MODELES.md` — observed LLM behaviour on real sessions

---

## Recommended pipeline — no intermediate model needed (v2.2)

Validated by E2E campaign Sillage v3.5.6 (2026-06-14, 32 functions in < 30 min):

```
Claude Code → rpa.py → JSON + PNG → Claude Code (analysis + iteration)
```

Claude Code writes the JSON scenario, calls rpa.py, reads the JSON output and the PNG
capture directly. No intermediate model is needed in this loop.

**Delegating to a third-party model (Qwen, opencode…) to pilot rpa.py adds overhead
with no benefit:** Claude Code already reads the result natively and iterates in under
two minutes per cycle.

### When a third-party model IS useful

| Use case | Relevant | Notes |
|---|---|---|
| Fine visual analysis on static captures (texture, contrast, small text) | ✓ | Qwen/vision model on a PNG already captured |
| Detachable CLI tasks (long, repetitive, no visual feedback loop) | ✓ | Independent of the main context |

### When a third-party model is NOT recommended

| Use case | Not recommended | Reason |
|---|---|---|
| Pilot rpa.py instead of Claude Code | ✗ | Indirection layer, no added value |
| Any task where Claude Code can read the result directly | ✗ | Claude Code is already the right consumer |

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
