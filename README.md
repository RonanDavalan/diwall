# Diwall — Visual Perception for Language Models

> **If you are a human developer:** share this README with Claude Code (or your LLM of choice) and ask it to install and configure Diwall. You do not need to understand every detail — your LLM does.

*LLM technical reference: [`docs/GUIDE_LLM.md`](docs/GUIDE_LLM.md)*

---

## What is Diwall?

Diwall is **not a tool for humans**. It is an execution API that gives language models (Claude Code, Gemini, etc.) the ability to **see web interfaces**.

When a language model develops a web application, it can modify code but cannot see the result in a browser. `lynx` does not render modern interfaces. Diwall solves this: it takes a screenshot using Playwright and returns it to the model, which analyses it directly using its multimodal capabilities.

```
LLM writes code → Diwall captures → LLM sees → LLM corrects → loop
```

The model calls `shot.py`, reads the PNG, analyses it, corrects the code, and loops — without any human in the feedback cycle.

---

## Architecture

```
Language Model (brain — ReAct loop)
        ↓  calls
  shot.py (hands — Playwright executor)
        ↓
  Chromium headless → PNG capture
        ↓
  Language Model reads PNG directly (multimodal)
```

`shot.py` has no intelligence. It executes instructions and returns state.
The language model decides what to do next.

---

## Capabilities

| Feature | Description |
|---|---|
| **Capture** | Screenshot any web page |
| **Actions** | Fill forms, click, navigate |
| **Set-of-Mark (SoM)** | Number all interactive elements for precise DOM clicks |
| **Accessibility snapshot** | Extract semantic page structure (A11y tree) |
| **Session persistence** | Maintain login state across multi-step ReAct loops |
| **RPA scenarios** | Execute action sequences from JSON files |
| **Visual monitoring** | Detect if a page changed since last reference |
| **Pixel diff** | Quantitative, deterministic diff against a stored reference (v1.2) |
| **Credential vault** | Secure credential injection — never in plaintext, never on the command line |
| **Encrypted vault** | gocryptfs-backed vault — `VaultFermeError` (exit 42) if vault not mounted (v1.5) |
| **Scroll** | `defiler` action — relative pixel scroll or `scrollIntoView` by CSS selector (v1.6) |
| **Off-screen warning** | `som_hors_viewport` count in JSON when interactive elements exist below the fold (v1.6) |
| **Procedural memory** | Successful runs stored as replayable skills via `journal.py --exporter-skill` (v1.6) |
| **TOTP 2FA** | Google Authenticator / Authy codes generated at runtime from vault seed (v1.6) |
| **Async MFA via ntfy** | SMS/email 2FA codes received asynchronously via ntfy push notification (v1.6) |
| **Operator profile** | YAML profile to lift repetitive administrative confirmations (v1.3) |
| **Model traceability** | Every run records which models were called, including Ollama digest (v1.3) |
| **Operation log** | Persistent append-only log of all runs — who did what, where, when (v1.4) |

---

## Requirements

| Component | Version / Notes |
|---|---|
| **OS** | Debian 13 Trixie (Linux, may work on macOS — not tested on Windows) |
| **Display server** | Wayland (Playwright runs in this ecosystem) |
| **Python** | 3.11+ in isolated venv (PEP 668 — system pip blocked on Debian 13) |
| **Playwright** | 1.59+ (installed in venv) |
| **Chromium** | Headless, installed via `playwright install chromium` |
| **Ollama** | Local vision models for `cliquer_visuel` and `watch.py` |
| **GPU** | Recommended: NVIDIA RTX 3060 12 GB VRAM or equivalent (for Ollama qwen3-vl models) |

---

## Installation

> **Recommended:** share this README with Claude Code and ask it to install Diwall for you.

If you want to install manually:

```bash
# 1. Create system user and directory
sudo useradd --system --no-create-home --shell /bin/false diwall
sudo mkdir -p /opt/diwall
sudo chown root:diwall /opt/diwall

# 2. Clone the repository
git clone https://github.com/ronandavalan/diwall.git ~/git/Diwall/Diwall
cd ~/git/Diwall/Diwall

# 3. Create Python virtual environment
sudo /usr/bin/python3 -m venv /opt/diwall/venv
sudo /opt/diwall/venv/bin/pip install -r requirements.txt

# 4. Install Chromium
sudo /opt/diwall/venv/bin/playwright install chromium

# 5. Deploy
bash scripts/deploy.sh

# 6. Create your credential vault
mkdir -p ~/Vaults/<your-project>/Diwall
# Create ~/Vaults/<your-project>/Diwall/<hostname>.json with your credentials
```

---

## Usage (by your LLM)

### Simple capture

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://your-app.local/ --som --a11y
```

### ReAct loop (multi-step navigation)

```bash
# Step 1 — navigate and observe
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --navigate https://your-app.local/ \
  --sauver-session /tmp/diwall/session.json --som

# Step 2 — act on what was observed
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session /tmp/diwall/session.json \
  --action '{"type":"cliquer_som","id":2}' \
  --sauver-session /tmp/diwall/session.json --som
```

### RPA scenario

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my_scenario.json --som
```

Full LLM reference: [`docs/GUIDE_LLM.md`](docs/GUIDE_LLM.md)

---

## Credential vault

Credentials are stored in JSON files, one per domain, **never in code or scenario files**:

```
~/Vaults/Diwall/
├── my-app.local.json        → {"password": "...", "username": "admin"}
└── other-service.com.json   → {"password": "...", "api_key": "..."}
```

In a scenario or action: `"valeur": "depuis_vault", "vault_cle": "password"` — Diwall reads the credential at runtime from the vault directory.

Vault path is configurable via `/opt/diwall/diwall.conf` or `DIWALL_VAULT_DIR` environment variable.

**Recommendation:** protect `~/Vaults/Diwall/` with `chmod 700` and encrypt it with `gocryptfs` (see `scripts/setup-vault.sh --gocryptfs`). Encrypted vault is fully supported since v1.5.0 — if the vault is initialised but not mounted, Diwall returns a structured `VaultFermeError` (exit code 42) instead of silently failing.

---

## Security

### Capture storage

By default, captures are stored in `/tmp/diwall/` with permissions `700` (owner only).
Do not change `--output-dir` to a shared location (`/tmp/`, `~/Desktop/`, etc.) — captures may contain sensitive interface data.

### Local vs cloud models

When Diwall is used with a cloud-based LLM (Claude API, OpenAI, etc.), PNG captures are transmitted to external servers. This is the user's responsibility. For interfaces containing private data (credentials, client information, private keys), use local Ollama models only.

### Vault directory

The vault directory (`~/Vaults/Diwall/` by default) contains credentials in plaintext JSON. Protect it:

```bash
chmod 700 ~/Vaults/Diwall/
```

Encrypted filesystem support (`gocryptfs`) is planned. See `scripts/setup-vault.sh`.

---

## For LLMs discovering Diwall

If you are a language model reading this README: see [`docs/GUIDE_LLM.md`](docs/GUIDE_LLM.md) for the complete technical reference — invocation patterns, SoM usage, vault integration, SPA navigation rules, and Ollama model specifications.

---

## Roadmap (v1.7)

Items under consideration for the next release, sourced from production friction reports and LLM feedback after v1.6:

| Feature | Description | Origin |
|---|---|---|
| **Inline SoM recalculation post-scroll** | Allow `defiler` + SoM recapture within a single `shot.py` invocation, so a scroll mid-sequence does not require a new process call. | Friction #27 |
| **Bundled logrotate config** | Ship `/etc/logrotate.d/diwall` with the repository so log rotation is zero-config after installation. | Operational gap |
| **Shadow DOM / iframe support** | Extend SoM indexing to traverse shadow boundaries and iframe documents, enabling automation of web components and embedded frames. | Community feedback |

These are candidates, not commitments. A feature enters v1.7 only once validated against a real Sillage use case.

**Blocking for authenticated dashboard monitoring (from session 9 field report):**

| Feature | Description | Origin |
|---|---|---|
| **`watch.py --exclure-zone`** | Pixel exclusion zones (coordinates or mask image) to ignore dynamic content areas (counters, timestamps, status badges) during comparison. Without this, semantic regressions on live dashboards fall below the noise threshold. | Friction #28 — blocking |
| **`watch.py --sauver-reference --capture FILE`** | Accept an existing capture (produced by `rpa.py` or `shot.py`) as a reference, without replaying navigation. Required for authenticated pages where `--sauver-reference` alone cannot reach the target. | Friction #31 — blocking |
| **`watch.py --sauver-reference --nom VIEW`** | Name the reference view to support multiple views per hostname (login, dashboard, settings). Currently requires manual directory creation. | Friction #30 — ergonomics |

---

## Credits

This project was developed using an **asymmetric human-LLM collaboration model**.
Roles are documented formally to reflect the actual work performed.

**Architect & Arbiter:** Ronan Davalan
Product vision, security requirements, project direction, validation and testing.
All architectural decisions are validated by him.

**Systems Engineer & Lead Developer:** Claude Code (Anthropic)
Implementation of the ReAct pattern, Python/Bash scripts, complex state management,
SoM injection, session persistence. Principal author of the source code.

**Synthesizer & Strategic Advisor:** Gemini (Google)
Independent architectural analysis, logical conflict resolution,
workflow optimisation, cross-validation of technical decisions.

**Perception models (Ollama, local):**
- `qwen3-vl:2b` (Alibaba) — click localisation and semantic comparison, ~9–19s (default since v1.3.1)
- `qwen3-vl:8b` (Alibaba) — robust fallback, ~114s

**Maintenance operators (via OpenCode):**
- Big Pickle — heavy semantic cleanup of documentation
- MiniMax — verification and commits

---

## Licence

MIT — see `LICENSE` file.

*Developed on Debian 13 Trixie · Wayland · AMD Ryzen 9 3950X · NVIDIA RTX 3060*
