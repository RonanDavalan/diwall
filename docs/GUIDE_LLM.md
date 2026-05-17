# Diwall — LLM Session Guide

Version 1.0 — May 2026

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
├── diwall.conf          ← {"vault_dir": "~/Vaults/<project>/Diwall"}
├── venv/                ← isolated Python — ALWAYS use this venv
├── lib/
│   ├── vision.py        ← visual localisation (qwen3-vl:4b via Ollama)
│   └── vault.py         ← credential vault reader
├── scenarios/           ← RPA scenario files (JSON)
└── references/          ← watch.py visual references

/tmp/diwall/             ← temporary PNG captures (cleared on reboot)
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

`rpa.py` resolves `depuis_vault` in memory before calling `shot.py` — credentials never appear in CLI arguments.

---

## Available actions

| Action | Key params | Notes |
|---|---|---|
| `naviguer` | `url` | Full HTTP reload — avoid in SPAs |
| `cliquer` | `selecteur` (CSS) | Mode A only |
| `remplir` | `selecteur`, `valeur` | `valeur` can be `"depuis_vault"` |
| `cliquer_som` | `id` | Exact DOM click via SoM |
| `remplir_som` | `id`, `valeur`, [`vault_cle`] | Exact DOM fill |
| `cliquer_visuel` | `description` | LLM vision fallback (~32s, avoid if SoM works) |
| `attendre` | `selecteur` | Wait for CSS selector |
| `attendre_navigation` | — | Wait for networkidle |
| `capturer` | `nom` | Named intermediate capture |
| `pause` | `ms` | Fixed delay |

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

**Quick test:**
```bash
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.vault import lire_credential
print(lire_credential('target.local', 'password'))
"
```

---

## SPA navigation rules

If the target is a JavaScript SPA (single-page application):

1. **`url_finale` is unreliable** — the JS router may not update the address bar.
   Use `a11y_tree` heading as state detector instead.

2. **`naviguer` forces a full HTTP reload** that bypasses the SPA router.
   Use `cliquer_som` for in-app navigation, `naviguer` only for the initial URL.

3. **Form values are NOT persisted in `storage_state`** (cookies + localStorage only).
   Fill + Submit must be a single atomic action: `--action '[{fill},{submit}]'`

---

## Ollama vision models on this machine

| Model | Size | Role | Speed |
|---|---|---|---|
| `qwen3-vl:4b` | 3.3 GB | `vision.py` — click localisation | ~32s |
| `qwen3-vl:2b` | 1.9 GB | `watch.py` — semantic comparison | ~1s |
| `qwen3-vl:8b` | 6.1 GB | Fallback (not default) | ~35s |

Ollama API: use `/api/chat` with `think: false` (not `/api/generate`).

---

## Visual monitoring (watch.py)

```bash
# Save visual reference
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference

# Compare against reference
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --comparer
```

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
