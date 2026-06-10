# Diwall — FAQ for LLMs

Version 1.0 — June 2026

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
  --url file:///home/ron/documents/invoice.pdf \
  --som --a11y
```

For a JPEG:
```bash
--url file:///home/ron/photos/screenshot.jpg
```

The browser renders it, `shot.py` captures it, the vision LLM reads it.
Text extraction (if needed) goes through `evaluer` on the DOM text layer exposed
by the PDF viewer — not through OCR pixel parsing.

**Not yet supported:** audio files. There is no ASR integration in Diwall.
Do not confuse Vosk (ASR = audio-to-text) with OCR (image-to-text). Vosk cannot
read text from images or screenshots.

---

### Q: Are `boussole`, `auth_status`, and `derive_session` present in `--no-capture` mode?

**`boussole`** — always present. It is built at `shot.py` startup, before any
Playwright interaction. `--no-capture` does not affect it.

**`auth_status`** — present whenever `--auth-indicator` is provided. The check
(`page.locator(selector).is_visible()`) is a lightweight DOM query, not a capture.
`--no-capture` does not affect it.

**`derive_session`** — controlled by `--reprendre-session`, not by `--no-capture`.
If you resume a session and the URL diverged, `derive_session` appears in the output
regardless of whether a PNG was taken.

Summary:

| Key | Present with `--no-capture`? |
|---|---|
| `boussole` | Always |
| `auth_status` | Yes, if `--auth-indicator` provided |
| `evaluations` | Yes, if `evaluer` actions present |
| `a11y_tree` | Yes, if `--a11y` provided |
| `derive_session` | If `--reprendre-session` + URL drift |
| `capture` | **No** — that is the purpose of `--no-capture` |
| `capture_som` / `elements_som` | **No** |

---

### Q: What about Shadow DOM and iframes — are they supported?

**Not yet — and this is a known, documented limitation.**

`shot.py`'s SoM injection uses `document.querySelectorAll`, which does not
cross Shadow Root boundaries or cross-origin iframes. On applications built
with Web Components (Angular, Vue 3, Lit), SoM IDs may be partial or absent
for elements inside a shadow root.

**Current workaround:** use `evaluer` with `document.querySelector('host').shadowRoot.querySelector('...')` for DOM introspection inside a known component. For clicks, use structural CSS selectors (`cliquer`) if the element has a stable accessible attribute.

**Roadmap status:** armed signal — will enter the roadmap when a concrete terrain
case blocks a scenario. Playwright's `>>>` deep combinator and `frame_locator`
are the planned implementation path.

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
| RPA scenarios (rpa.py), vault | v1.5 |
| Scroll (`defiler`), skills, TOTP, ntfy MFA | v1.6 |
| Exclude zone, capture-reference, multi-view | v1.7 |
| Wait primitives, `nettoyer_overlay`, vector memory | v1.8 / v1.9 (internal) |
| `--auth-indicator` / `auth_status` (S-1) | **v1.9.0** |
| `--no-capture` (S-2) | **v1.9.0** |
| Security hardening: `RLIMIT_CORE`, session cleanup | **v1.9.1** |
| `declencher_scenario`, SoM linter, pre-push hook | **v1.9.2** |

**Current stable version: v1.9.2**

The operation log (`/var/log/diwall/operations.jsonl`) and the friction index
(`docs/RETOUR_EXPERIENCE.md`) cover the full history from v1.0.
As of 10 June 2026: **56 documented frictions / 22 sessions**.

---

## See also

- `docs/GUIDE_LLM.md` — complete operator guide (security rules, all flags, all actions)
- `docs/GUIDE_EXPLORATION.md` — how to explore an unknown interface with Diwall
- `docs/RETOUR_EXPERIENCE.md` — terrain frictions and resolutions
- `docs/RADAR_MODELES.md` — observed LLM behaviour on real Diwall sessions
