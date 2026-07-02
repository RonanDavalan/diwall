# Diwall — Shared Visual Reference between Human and LLM

> **For the human operator:** Diwall lets you delegate visual verification to your LLM. Both of you see the same capture — you stop having to take its word for it.
>
> **For the LLM:** [`docs/GUIDE_LLM.md`](docs/GUIDE_LLM.md) is your operational reference. Start there.
> If you are an AI agent discovering Diwall, skip the styled landing page and fetch your instructions directly: **[https://diwall.davalan.fr/instructions.md](https://diwall.davalan.fr/instructions.md)**

---

## What is Diwall?

Diwall creates a **shared visual reference** between a human operator and a language model. It gives the LLM the ability to **see web interfaces** — and gives the human operator a way to **delegate visual verification** without losing control.

Without Diwall, a human must either trust their LLM on its word or verify the result themselves. With Diwall, both parties see the same PNG capture and the same accessibility tree. The doubt disappears on both sides.

```
LLM acts → Diwall captures → LLM sees and reports → Human verifies from the same state
```

**What the human gains:** delegation of the anxious, repetitive work of visual verification. Instead of clicking through dozens of pages after a deployment, the human reviews the captures the LLM already produced.

**What the LLM gains:** real perception of the interface. Without Diwall, a model developing a web application modifies code but cannot see the result in a browser. `lynx` does not render modern interfaces.

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
| **Shadow DOM traversal** | `--shadow-dom` numbers interactive elements inside open Shadow Roots — Angular, Lit, Stencil, FAST (v1.13.0) |
| **Citizen Navigation** | `--stealth` (removes automatic headless markers), courtesy delays and hard caps (`min_action_delay_ms`, `max_pages_par_run`, `max_actions_par_run`), impact metrics (`citoyennete`) reported on every run (v1.15.0) |
| **Deterministic verdict** | `etat` object (`pret_a_agir`, `niveau_confiance`, `raisons`) synthesizes authentication, session drift, and friction signals into one read (v1.16.0) |
| **Unified run identity** | `operation_id` isolates every run's temporary files and ties them to its operations-log entry (v1.16.0) |
| **Passive WAF signal** | `citoyennete.waf_bloquants` flags a likely block (HTTP 403/429 or known keywords) as a non-fatal signal, never an exception (v1.16.0) |
| **Structural non-regression** | `--replay-verifier` compares HTTP status, DOM stats, and `evaluer` results against a saved reference — no pixels, no vision model (v1.17.0) |
| **Scenario checkpoints** | `--checkpoint` resumes a long scenario after a mid-run failure without replaying completed actions (v1.17.0) |
| **Stable SoM identity** | `--som-rafraichir` resolves `cliquer_som`/`remplir_som` by a DOM marker instead of live re-indexing, preventing silent retargeting on highly dynamic pages (v1.17.0) |
| **Cross-origin iframes** | `cliquer_iframe` / `remplir_iframe` target elements inside same- or cross-origin iframes via Playwright's native frame API (v1.17.0) |

---

## Requirements

| Component | Version / Notes |
|---|---|
| **OS** | Debian 13 Trixie (Linux, may work on macOS — not tested on Windows) |
| **Display server** | Wayland (Playwright runs in this ecosystem) |
| **Python** | 3.11+ in isolated venv (PEP 668 — system pip blocked on Debian 13) |
| **Playwright** | 1.50+ (installed in venv) |
| **playwright-stealth** | 2.0+ — required for `--stealth` (v1.15.0). API-incompatible with 1.x |
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

## Uninstallation

```bash
# Preview what will be removed (no changes made)
bash scripts/uninstall.sh --dry-run

# Full uninstallation with interactive confirmation
bash scripts/uninstall.sh

# Non-interactive (CI, cold-reinstall tests)
bash scripts/uninstall.sh --confirme
```

Removes: `/opt/diwall/`, `/var/log/diwall/`, system user `diwall`, system group `diwall`, operator's group membership, git pre-push hook.

**Never touched:** `~/Vaults/` (credential vaults), the repository itself, Playwright browser cache.

If `/var/log/diwall/preuves/` contains captures, they are preserved by default. Add `--purge-preuves` to remove them.

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
  --url https://your-app.local/ \
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

The vault directory (`~/Vaults/Diwall/` by default) contains credentials in plaintext JSON when unmounted. Protect it:

```bash
chmod 700 ~/Vaults/Diwall/
```

Encrypted filesystem support (`gocryptfs`) has been fully supported since v1.5.0 —
see "Credential vault" above and `scripts/setup-vault.sh`.

---

## For LLMs discovering Diwall

If you are a language model reading this README: see [`docs/GUIDE_LLM.md`](docs/GUIDE_LLM.md) for the complete technical reference — invocation patterns, SoM usage, vault integration, SPA navigation rules, and Ollama model specifications.

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
