# Diwall — FAQ for LLMs

Version 1.1 — June 2026 (v1.14.0)

Answers to technical questions raised by language models during real Diwall sessions.
No attribution — these are recurring questions, not individual testimonies.

---

## Perception

### Q: Can Diwall analyze image files (JPG, PNG, PDF)?

**Yes — natively, without any OCR library.**

Chromium renders image files and PDFs as visual pages. `shot.py` captures the
rendered output as a PNG and passes it to the local vision model (`qwen3-vl:2b`
via Ollama). No external library, no cloud service.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url file:///home/<user>/documents/invoice.pdf \
  --som --a11y
```

For a JPEG:
```bash
--url file:///home/<user>/photos/screenshot.jpg
```

The browser renders it, `shot.py` captures it, the vision LLM reads it.
Text extraction (if needed) goes through `evaluer` on the DOM text layer exposed
by the PDF viewer — not through OCR pixel parsing.

**Not yet supported:** audio files. There is no ASR integration in Diwall.
Do not confuse Vosk (ASR = audio-to-text) with OCR (image-to-text). Vosk cannot
read text from images or screenshots.

---

### Q: What is in the `boussole` object?

The `boussole` is the first object to read in any Diwall JSON output. Since v1.14.0
it always contains five fields:

```json
"boussole": {
  "utilisateur": "operator",
  "ip_locale": "__IP_LAN__",
  "repertoire": "/opt/diwall",
  "url_courante": "https://target.local/dashboard",
  "titre_page": "Dashboard — My App"
}
```

Plus conditional fields that appear only when active:

| Key | Present when |
|---|---|
| `session_derive` | `--reprendre-session` active and URL diverged |
| `auth_status` | `--auth-indicator` active (`"active"` or `"inactive"`) |
| `som_hors_viewport` | SoM active and at least one interactive element is off-screen |
| `shadow_dom_actif` | `--shadow-dom` active |

`titre_page` is always present but may be empty (`""`) on `about:blank` or if Playwright
cannot read the title before closing.

---

### Q: Are `boussole`, `auth_status`, and `derive_session` present in `--no-capture` mode?

**`boussole`** — always present, always enriched with `url_courante` and `titre_page`
(v1.14.0). `--no-capture` does not affect it.

**`auth_status`** — present whenever `--auth-indicator` is provided. The check
(`page.locator(selector).is_visible()`) is a lightweight DOM query, not a capture.
`--no-capture` does not affect it.

**`derive_session`** — controlled by `--reprendre-session`, not by `--no-capture`.
If you resume a session and the URL diverged, `derive_session` appears in both the
root JSON and the `boussole` object regardless of whether a PNG was taken.

Summary:

| Key | Present with `--no-capture`? |
|---|---|
| `boussole` (incl. `url_courante`, `titre_page`) | Always |
| `auth_status` | Yes, if `--auth-indicator` provided |
| `evaluations` | Yes, if `evaluer` actions present |
| `a11y_tree` | Yes, if `--a11y` provided |
| `dom_stats` | **Only** in `--no-capture` mode |
| `derive_session` | If `--reprendre-session` + URL drift |
| `capture` | **No** — that is the purpose of `--no-capture` |
| `capture_som` / `elements_som` | **No** |

---

### Q: What about Shadow DOM and iframes — are they supported?

**Shadow DOM: yes, via `--shadow-dom` (v1.13.0). Iframes: no (cross-origin limitation).**

`shot.py`'s standard SoM injection uses `document.querySelectorAll`, which does not
cross Shadow Root boundaries. Since v1.13.0, pass `--shadow-dom` to enable recursive
traversal of **open** Shadow Roots:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://angular-app.local/ --som --shadow-dom
```

The three SoM JS functions (inject / count-off-screen / find-by-id) all share the
same `queryShadowAll` recursive walker, guaranteeing indexing consistency.

**When to use it:** Angular, Lit, Stencil, Polymer applications where interactive
elements inside shadow roots are not numbered by default.

**Known limitation:** closed Shadow Roots (created with `{mode: 'closed'}`) are
inaccessible from JS and are silently skipped. There is no workaround — this is
a browser-level enforcement, not a Diwall limitation.

In scenario JSON, activate with `"shadow_dom": true` at the root level.

**Cross-origin iframes** remain unsupported (Playwright `frame_locator` is the
planned path but is not yet implemented).

---

### Q: What does `--mode fast` do, and when should I use it?

`--mode fast` is a shortcut introduced in v1.14.0. It is exactly equivalent to
passing both `--no-capture` and `--a11y`:

```bash
# These two calls are strictly equivalent:
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --mode fast
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --no-capture --a11y
```

**When to use `--mode fast`:**

| Goal | Use |
|---|---|
| Check authentication status | `--mode fast --auth-indicator <sel>` |
| Read DOM text / extract a JS value | `--mode fast` + `evaluer` actions |
| Verify page title or URL after navigation | `--mode fast` (read `boussole`) |
| Check that an element is present | `--mode fast --a11y` (read `a11y_tree`) |

**When NOT to use `--mode fast`:**
- When you need a visual render (PNG) for inspection
- When you need `--som` (SoM requires a capture — `fast` and `som` are incompatible)

`--mode full` is the current default behavior. It is useful to name it explicitly for
clarity in scripts or when overriding a `--mode fast` set upstream.

---

### Q: What is `auth_indicator_negative` and when do I need it?

`--auth-indicator-negative` (v1.14.0) is a companion to `--auth-indicator` for
interfaces where the positive selector is ambiguous — e.g. a `.user-menu` element
that is present even on the login page (persistent header, multi-account banner).

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --auth-indicator ".user-menu" \
  --auth-indicator-negative ".btn-login"
```

Logic:
- `auth_status: "active"` → positive visible **AND** negative absent or not visible
- `auth_status: "inactive"` → otherwise

In a scenario file, add `"auth_indicator_negative": ".btn-login"` at the root level
alongside `"auth_indicator"`. `rpa.py` propagates it to `shot.py` automatically.

---

## Scenarios and validation

### Q: Is there a dry-run or pre-validation mode?

**Partial — since v1.9.2.**

`rpa.py` now runs two static validators **before launching Playwright**:

1. **Schema validation** (`jsonschema`) — checks action types, required keys, and
   rejects unknown properties. Requires `jsonschema` in the venv:
   ```bash
   /opt/diwall/venv/bin/pip install jsonschema
   ```

2. **SoM linter** (`_linter_som`) — checks that every `cliquer_som` / `remplir_som`
   action has a positive integer `id`. Exits with a structured JSON error if not:
   ```json
   {"succes": false, "erreur": "linter_som",
    "message": "Action #2 (cliquer_som) : 'id' doit être un entier positif, reçu : \"btn-submit\"."}
   ```

A full dry-run (resolving `depuis_vault`, validating CSS selectors on a live DOM)
would require Playwright and is not yet implemented. The linter catches the most
common authoring errors without browser overhead.

---

### Q: Can a scenario call another scenario?

**Yes — since v1.9.2, via `declencher_scenario`.**

```json
{
  "url": "https://target.local/dashboard",
  "actions": [
    {"type": "declencher_scenario", "scenario": "login"},
    {"type": "cliquer_som", "id": 5}
  ]
}
```

`rpa.py` inlines the sub-scenario's actions before calling Playwright — the browser
runs a single continuous session. The vault and journal are managed by the parent run.

- Sub-scenario resolved via: `scenarios/<name>{.json,.yaml,.yml}` or absolute path.
- Recursion depth capped at 5 levels. Circular references produce a structured
  `profondeur_max_chainages` error.
- The SoM linter runs on the **full flattened action list** (parent + all sub-scenarios
  inlined) before any Playwright call.

---

## Versions

### Q: Which version introduced which feature?

| Feature | Version |
|---|---|
| SoM, A11y, ReAct, session persistence | v1.4 |
| RPA scenarios (`rpa.py`), vault | v1.5 |
| Scroll (`defiler`), skills, TOTP, ntfy MFA | v1.6 |
| Exclude zone, capture-reference, multi-view | v1.7 |
| Wait primitives, `nettoyer_overlay`, vector memory | v1.8 / v1.9 (internal) |
| `--auth-indicator` / `auth_status` (S-1) | v1.9.0 |
| `--no-capture` (S-2) | v1.9.0 |
| Security hardening: `RLIMIT_CORE`, session cleanup | v1.9.1 |
| `declencher_scenario`, SoM linter, pre-push hook | v1.9.2 |
| `diwall-sample.conf`, `VaultNonConfigureError` (exit 43) | v1.9.3 |
| Modular scenarios (group C vault fill), `evaluer` field clearing | v1.9.6 |
| `--secrets` multi-vault, fail-fast venv | v1.10.0 |
| `force: true` on `cliquer`, `--screenshot-timeout`, assertions `contient`/`motif` | v1.11.0 |
| Session file persistence fix (FR-74/FR-75) | v1.11.1 |
| Error routing table, notice versioning, secret blurring, `dom_stats` | v1.12.0 |
| Shadow DOM SoM traversal (`--shadow-dom`) | **v1.13.0** |
| Enriched `boussole` (`url_courante`, `titre_page`), `--auth-indicator-negative`, `--mode fast\|full` | **v1.14.0** |

**Current stable version: v1.14.0**

The operation log (`/var/log/diwall/operations.jsonl`) and the friction index
(`docs/RETOUR_EXPERIENCE.md`) cover the full history from v1.0.
As of 23 June 2026: **71 documented frictions / 41 sessions**.

---

## See also

- `docs/GUIDE_LLM.md` — complete operator guide (security rules, all flags, all actions)
- `docs/GUIDE_EXPLORATION.md` — how to explore an unknown interface with Diwall
- `docs/RETOUR_EXPERIENCE.md` — terrain frictions and resolutions
- `docs/RADAR_MODELES.md` — observed LLM behaviour on real Diwall sessions
