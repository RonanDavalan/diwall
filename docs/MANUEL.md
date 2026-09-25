# Diwall — Operational manual

**Version 1.24.3 — September 2026**

*Also available in French, German and Spanish under `docs/fr/`, `docs/de/` and `docs/es/`.*

This document answers one question: **how to do X with Diwall**.

> **If you are a user** — no commands needed. Tell your model what you want to visit,
> observe, or accomplish on a website, a web application, or an administration interface.
> The model reads this manual and translates your intent into the right actions.
>
> **If you are a language model** — these are your commands. Execute them directly.

No architectural descriptions. Commands that work.

---

## Table of contents

1. [Verify the installation](#1-verify-the-installation)
2. [Capture a page](#2-capture-a-page)
3. [Respectful navigation (v1.15.0)](#3-respectful-navigation-v1150)
4. [Encrypted directory and credentials](#4-encrypted-directory-and-credentials)
5. [Write and run an RPA scenario](#5-write-and-run-an-rpa-scenario)
6. [Actions — complete reference](#6-actions--complete-reference)
7. [Handle common obstacles](#7-handle-common-obstacles)
8. [Visual monitoring — watch.py](#8-visual-monitoring--watchpy)
9. [Operation log](#9-operation-log)
10. [CLI flags — reference](#10-cli-flags--reference)
11. [Exit codes and output](#11-exit-codes-and-output)


---

## 1. Verify the installation

```bash
# Cheapest possible check — no Playwright, no URL, exit 0 immediately (v1.18.0+)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --version
# → {"outil": "shot.py", "version": "1.23.0"}
```

```bash
# Full test in one command (~3 s)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --mode fast --guide-version 1.3
```

Expected result: JSON on stdout with `"succes": true`.

**`--guide-version` (v1.18.0+):** `shot.py`, `rpa.py`, and `watch.py` refuse to
run without it — unless a local marker from a previous accepted call already
exists (`~/.config/diwall/guide_state.json`). The value is the
`<!-- notice-version: X.Y -->` on line 3 of `docs/GUIDE_LLM.md` — not the
Diwall release number. Read the current one rather than trusting any value
quoted here: `grep notice-version /opt/diwall/docs/GUIDE_LLM.md`. See
`docs/GUIDE_LLM.md` section "Mandatory pre-flight" for the full mechanism and
the error format if you skip it.

**Once the marker exists, `--guide-version` becomes optional again** — every
other command example in this manual omits it deliberately, since a marker
from any earlier successful call already covers them, as long as
`docs/GUIDE_LLM.md`'s `notice-version` has not changed since.

```bash
# Verify the installed version
grep "__version__" /opt/diwall/shot.py
# → __version__ = "1.23.0"

# Verify playwright-stealth is available (v1.15.0)
/opt/diwall/venv/bin/python3 -c "import playwright_stealth; print('stealth OK')"

# Verify the encrypted directory is mounted
ls ~/Vaults/__PROJET__/Diwall/
# → must show .json files, not an empty list
```

If `ls ~/Vaults/...` returns an empty list or an error:
→ mount it: `bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh`

### 1a. Installing from the Debian package — the simple path

The `.deb` is a release asset on GitHub. It is the recommended channel unless
you intend to modify Diwall's own code, in which case see 1b. The two channels
are mutually exclusive on a single machine — both target `/opt/diwall/`.

```bash
sudo apt install ./diwall_1.23.0-1_all.deb
diwall-shot --version
man diwall
```

Installing the `.deb` requires network access (dependency install and
Chromium download happen during `postinst`). Six commands become available,
each a thin wrapper — no functional difference from the git-clone channel's
own invocations:

| Command | Wraps |
|---|---|
| `diwall-shot` | `shot.py` |
| `diwall-rpa` | `rpa.py` |
| `diwall-watch` | `watch.py` |
| `diwall-monter-secrets` | `scripts/monter-repertoire-chiffre.sh` |
| `diwall-demonter-secrets` | `scripts/demonter-repertoire-chiffre.sh` |
| `diwall-monitor-verifier` | `scripts/monitor-verifier.sh` |

**Configuration lives at a different path on this channel:**
`/etc/diwall/diwall.conf` (not `/opt/diwall/diwall.conf`) — a template is
dropped at `/etc/diwall/diwall-sample.conf`, never auto-activated:

```bash
sudo cp /etc/diwall/diwall-sample.conf /etc/diwall/diwall.conf
sudo nano /etc/diwall/diwall.conf
sudo usermod -aG diwall $USER
```

`apt remove diwall` keeps `/var/log/diwall/` (operations journal, evidence)
intact — `apt purge diwall` also removes it, together with `/etc/diwall/`,
the `watch.py` reference captures (`/opt/diwall/references/`) and the
downloaded Chromium: nothing is left under `/opt/diwall/` (v1.24.2). Save
`/opt/diwall/references/` first if you want to keep your baselines.
`~/Vaults/` is never touched by either, on both channels.

**Manual page (v1.22.0):** `man diwall` documents all six commands on a
single page. The five other command names (`man diwall-rpa`, and so on)
resolve to the same page. It is generated from `debian/diwall.1.md` at build
time, so it cannot silently go stale — but for the exhaustive option list of
any command, `--help` remains authoritative over the manual page.

### 1b. Installing from source — for modifying Diwall itself

Use this channel only if you intend to change Diwall's own code: it puts the
repository where `deploy.sh` can push your changes to `/opt/diwall/`. For
plain use, the `.deb` above is one command and does the same job.

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
bash ~/git/Diwall/Diwall/scripts/deploy.sh

# 6. Create your encrypted credentials directory
mkdir -p ~/Vaults/<your-project>/Diwall
# Create ~/Vaults/<your-project>/Diwall/<hostname>.json with your credentials
```

If Diwall is already installed from the `.deb`, `install.sh` and `deploy.sh`
refuse to run (v1.24.2): they would overwrite files that dpkg manages, and the
next package upgrade or purge would silently undo them. Run
`sudo apt purge diwall` first to switch channels.

On this channel the configuration is `/opt/diwall/diwall.conf`, not
`/etc/diwall/diwall.conf`. Uninstall with
`bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run` first, then without
the flag. `uninstall.sh` refuses too when the package is installed (v1.24.3):
it would remove `/opt/diwall/` and the `diwall` account that dpkg manages. Use
`sudo apt purge diwall` instead.

**Building the package (maintainer):**

```bash
bash ~/git/Diwall/Diwall/scripts/construire-paquet.sh
```

Builds and then files the three artefacts (`.deb`, `.buildinfo`, `.changes`)
under `~/git/Diwall/paquets/<version>/`. All versions are kept: the
`.buildinfo` is the only record of the exact environment a package was built
in, and it is worth nothing unkept.

---

## 2. Capture a page

### 2a. Fast capture — text only, no PNG (~2 s)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
```

Returns: `a11y_tree` (text structure of the page), `boussole` (effective URL, title).
Use when you want to read the title, verify the URL, or extract text without capturing a PNG.

### 2b. Full visual capture with numbered elements

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
```

Returns:
- `capture`: path to the page PNG
- `capture_som`: PNG with numbers on clickable elements (SoM)
- `elements_som`: JSON list of elements (id, tag, text)
- `a11y_tree`: accessibility tree

![Set-of-Mark overlay: each interactive element outlined and numbered](images/som-example-en.png)

*What `--som` produces. The numbers in the image are the `id` values in
`elements_som`, so clicking becomes `{"type": "cliquer_som", "id": 7}` — no
selector to guess. Generated from a fixture versioned in this repository
(`scenarios/interoperabilite/fixture/`); the same figure exists in French,
German and Spanish alongside this one.*

### 2c. Read the boussole first

Every output contains a `boussole` object — read it before everything else:

```json
"boussole": {
  "url_courante": "https://target.local/dashboard",
  "titre_page": "Dashboard — My App",
  "auth_status": "active",
  "stealth_actif": true,
  "respect": {
    "pages_visitees": 0,
    "actions_executees": 3,
    "duree_totale_ms": 2140
  }
}
```

If `boussole.url_courante` does not match what you expect: stop and investigate
before any mutating action.

`boussole.secrets_dir_effectif` and `boussole.secrets_dir_source` (v1.23.1)
report which encrypted-secrets directory was actually resolved for this run
and where that came from (`env:DIWALL_SECRETS_DIR`, `env:DIWALL_CONF`,
`conf:<path>`, or `non_configure`). A multi-project machine can silently fall
back to the machine-wide `diwall.conf` when a caller forgets to export
`DIWALL_SECRETS_DIR` — these two fields make that visible on every run instead
of after the fact.

### 2d. Read `etat` for a go/no-go decision (v1.16.0)

Every successful run includes an `etat` object at the JSON root — read it
before any mutating action instead of manually cross-checking `auth_status`,
`respect.plafond_atteint`, `erreurs_js`, and `erreurs_console` yourself:

```json
"etat": {
  "pret_a_agir": true,
  "niveau_confiance": "eleve",
  "raisons": ["aucun signal de friction détecté"]
}
```

If `pret_a_agir` is `false`: read `raisons` for the cause (inactive
authentication, session drift, navigation cap reached, or a detected WAF
block) before proceeding.

`etat` does not check whether the URL or page content matches your business
expectation — use `evaluer` with `attendu`/`contient`/`motif` (section 5d)
for that.

### 2e. `mode_conseille` — pre-flight configuration advice (v1.18.0)

If Diwall has real prior data about the host you are calling — from an
earlier `diagnostic_dom.json` run against it — `etat` carries a recommendation
for your **next** call, never applied automatically:

```json
"etat": {
  "pret_a_agir": true,
  "niveau_confiance": "eleve",
  "raisons": ["mode_conseille disponible : full recommandé (React détecté sur ce host)"],
  "mode_conseille": {
    "mode": "full",
    "shadow_dom": true,
    "som_rafraichir": false,
    "raisons": ["react_detecte", "shadow_roots:3"]
  }
}
```

Get this data flowing for a host by running the diagnostic once:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url https://target.local/ --mode fast
```

No prior diagnostic for this host → `mode_conseille` is absent, never a
guess. Full detail in `GUIDE_LLM_MONITORING.md`.

The `som_rafraichir` field is kept for output-shape stability but is vestigial
since v1.24.0 (hybrid SoM resolution with fallback is the default — nothing to
enable; see section 7j).

---

## 3. Respectful navigation (v1.15.0)

### 3a. Stealth mode `--stealth`

Some sites block headless browsers on `navigator.webdriver=true`
without examining the intent. `--stealth` removes this automatic technical marker.

```bash
# direct shot.py
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --stealth

# Via rpa.py
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --stealth
```

When active: `boussole.stealth_actif = true` in the JSON output.

**What `--stealth` changes:** `navigator.webdriver` removed, plugins/languages/platform normalised.
**What `--stealth` does not change:** the operator's IP, identity, or navigation intent.

### 3b. Courtesy delays

Configured in `/opt/diwall/diwall.conf`:

```json
{
  "secrets_dir": "~/Vaults/__PROJET__/Diwall",
  "navigation": {
    "min_action_delay_ms": 800,
    "max_pages_par_run": 10,
    "max_actions_par_run": 30
  }
}
```

`min_action_delay_ms`: minimum delay (ms) between each action. Shipped
default: 800 ms.

**Local development — set it to `0` (v1.19.0):** the 800 ms
default protects a distracted operator on their *first, unconfigured* run
against the public internet — it has no protective purpose against your own
development/production machine, where nothing is being asked to behave. Set
the key explicitly in your local `diwall.conf`:

```json
{
  "navigation": {
    "min_action_delay_ms": 0
  }
}
```

Keep the 800 ms default (or raise it) for any target reached over the public
internet. The value is always a conscious choice attached to the target, not
a fixed property of the tool — see the WAF and stealth guidance in
`docs/GUIDE_LLM.md` for the same principle applied to blocking behaviour.

The `max_pages_par_run` and `max_actions_par_run` caps cleanly stop the run
if exceeded. No exception — the output JSON will contain:

```json
"respect": {
  "pages_visitees": 10,
  "actions_executees": 10,
  "duree_totale_ms": 12400,
  "plafond_atteint": "max_pages_par_run"
}
```

### 3c. Impact metrics

Each run returns `respect` in (JSON root and inside boussole):

| Key | Meaning |
|---|---|
| `pages_visitees` | Number of `type: naviguer` navigations executed |
| `actions_executees` | Total number of scenario actions executed |
| `duree_totale_ms` | Total run duration |
| `plafond_atteint` | `"max_pages_par_run"` or `"max_actions_par_run"` if early stop |

### 3d. Stealth benchmark — quantitative (v1.17.1)

Prefer counting concrete fingerprint signals over comparing screenshots by
eye — this is the method used to verify the v1.17.0 `playwright-stealth`
API-compatibility fix (`docs/RETOUR_EXPERIENCE.md` FR-79):

```bash
# Without stealth
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://bot.sannysoft.com --no-capture --timeout 20000 \
  --actions '[{"type":"evaluer","script":"navigator.webdriver"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.failed\").length"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.passed\").length"}]'

# With stealth
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://bot.sannysoft.com --no-capture --stealth --timeout 20000 \
  --actions '[{"type":"evaluer","script":"navigator.webdriver"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.failed\").length"},
               {"type":"evaluer","script":"document.querySelectorAll(\"td.passed\").length"}]'
```

Read the three values in `evaluations[].valeur`: `navigator.webdriver` should
go from `true` to `false`, `td.failed` should drop toward `0`. Reference
measurement (v1.17.0 fix, session 47): 12 failed → 0 failed. A number or a
boolean returned by `evaluer` keeps its JSON type in the output and in the
journal (v1.24.3); before that, `shot.py` returned it as text (`"false"`,
`"0"`). Only text is filtered for secret shapes.

For a qualitative second opinion, the provided scenario still produces
screenshots to inspect:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/test_stealth.json \
  --output-dir /tmp/diwall/stealth_with --stealth
```

`capture_sannysoft_*.png` and `capture_intoli_*.png` land in that directory.
Note: both target pages discuss bot detection in their own content, which
can trigger `respect.waf_bloquants` as a false positive (section 3e) —
expected on this specific benchmark, not a sign of an actual block.

### 3e. WAF detection signal (v1.16.0, refined v1.17.2)

Diwall flags a probable WAF block passively — HTTP 403/429, or a title/HTML
keyword match (`Cloudflare`, `CAPTCHA`, `checking your browser`, etc.). This
is a signal, never an exception — the run completes normally:

```json
"respect": {
  "waf_bloquants": 1
}
```

When present and `> 0`: `etat.niveau_confiance` is `"faible"` and
`etat.pret_a_agir` is `false`. Decide yourself whether to retry with
`--stealth`, change target, or stop — Diwall does not abort the run for you.

Since v1.17.2, generic vendor names (`Cloudflare`, `Akamai`) only match the
page title — matching the full HTML previously false-positived on ordinary
CDN resource references. If a false positive persists, `--ignorer-waf`
degrades `niveau_confiance` without forcing `pret_a_agir: false`
(`boussole.waf_ignore_actif: true` records the override).
The detection is keyword-based and can produce false positives on pages that
legitimately discuss blocking/detection (e.g. a bot-detection benchmark
page) — treat it as a fast signal, not a certain verdict.

### 3f. Declared language (v1.24.1)

The browser declares the operator's language. It is taken from the
environment of the process, in the order Chromium itself follows:
`LANGUAGE`, then `LC_ALL`, `LC_MESSAGES`, `LANG` — and `en-US` when none of
them gives a usable value (`C`, `POSIX`). The same tag is sent in the
`Accept-Language` header and returned by `navigator.language`, so a site that
negotiates its language serves the operator's.

To declare another language for one run, set it in the environment:

```bash
LANGUAGE=en diwall-shot --url https://example.com --mode fast --guide-version 1.3
```

Before v1.24.1, no `Accept-Language` header was sent at all while
`navigator.language` carried the machine's language: a site that negotiates
its language served its default. A scenario that checks a text on such a site
(`evaluer` with `contient`, a wait on a label) can therefore give a different
result after upgrading.

---

## 4. Encrypted directory and credentials

### 4a. Structure

The credentials live in an encrypted directory — a gocryptfs volume — containing one `.json` file per domain.

```
~/Vaults/__PROJET__/Diwall/
  ├── app.example.com.json         ← credentials for https://app.example.com/
  ├── admin.example.com.json       ← credentials for https://admin.example.com/
  └── operations.jsonl             ← operation log (v1.15.0)
```

Credentials file format:
```json
{
  "username": "admin@example.com",
  "password": "my-password"
}
```

The file name = `urlparse(url).hostname`. For `https://app.example.com/login/`, create `app.example.com.json`.

### 4b. Filling a form — the absolute rule

**FORBIDDEN — exposes the password in the shell and `/proc`:**
```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER
curl -d "password=$PASS" https://...                 # NEVER
```

**CORRECT — credentials resolved inside Playwright:**
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "username"},
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Values never pass through the shell, bash history, process logs, or any file.

### 4c. Choosing the credentials file for a run

```bash
# Default credentials directory (defined in diwall.conf > secrets_dir)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --som

# Explicit credentials file (--secrets)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som \
  --secrets /path/to/mounted/directory/creds.json

# Per-project credentials directory via .diwall.conf
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://target.local/ --som
```

**`--secrets` file content — `origines_autorisees` mandatory since
05/08/2026** (breaking change, no compatibility period): a file missing this
key is refused before any read.

```json
{"username": "operator", "password": "secret", "origines_autorisees": ["target.local"]}
```

`origines_autorisees` lists the hostnames this file may be used against —
same lowercase, no-scheme, no-port format as `domaine_depuis_url()`. A read
against a page whose domain is not in the list is refused
(`SecretsOrigineNonAutoriseeError`).

Content of `~/git/MyProject/.diwall.conf`:
```json
{"secrets_dir": "../MyProject-secrets"}
```

The path is resolved relative to the location of `.diwall.conf`.

### 4d. TOTP / MFA

```json
{"type": "remplir_som", "id": 6, "valeur": "depuis_secrets_totp"}
```

Reads the `totp_cle` key (base32 seed) from the credentials file and generates the current TOTP code.

To receive the code via ntfy (workflow without human intervention):
```json
{"type": "attendre_mfa_ntfy", "id_som": 6, "timeout": 120}
```

### 4e. Integrity checksum (opt-in, v1.15.0)

To protect a credentials file against silent FUSE corruption, add a `checksum` field:

```bash
# Generate the checksum
/opt/diwall/venv/bin/python3 -c "
import json, hashlib
creds = json.load(open('my_credentials.json'))
fields = {k: creds[k] for k in sorted(['username','password']) if k in creds}
print('sha256:' + hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest())
"
```

Add the returned value to the credentials file:
```json
{
  "username": "admin@example.com",
  "password": "my-password",
  "checksum": "sha256:a3f2c1..."
}
```

If the checksum does not match, `shot.py` raises `SecretsChecksumError` (exit 42) with an explicit message.
Without the `checksum` key: behaviour unchanged (strict opt-in).

### 4f. Encrypted directory closed — what to do

```
SecretsFermesError: Le répertoire chiffré Diwall est initialisé mais non monté.
```

```bash
# Mount the encrypted directory
bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh

# Verify the mount
ls ~/Vaults/__PROJET__/Diwall/
# → must show JSON files
```

### 4g. HTTP Basic Auth — `--http-credentials` (v1.21.0)

For targets behind a network-level HTTP Basic Auth challenge (RFC 7617) —
the wall a reverse proxy like Caddy, nginx, or Traefik raises before any
page renders, common in front of self-hosted admin interfaces. This is a
different mechanism from the form-based authentication above
(4a-4f), which remains fully supported and unaffected.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://internal.example/ \
  --http-credentials --secrets ~/Vaults/__PROJET__/Diwall/internal_example.json
```

Credentials file — the plain `username`/`password` pair already used for the
common case (a single set of credentials for the target):
```json
{"username": "admin", "password": "my-password"}
```

Dedicated `http_username`/`http_password` keys are tried first and only
needed when the same target has *both* a network-level Basic Auth wall
*and* its own separate application login (two different credential pairs
in the same file) — Diwall falls back to `username`/`password`
automatically when the dedicated keys are absent.

Confirmed in production against a real Caddy-protected target: the safe
default (`send: "unauthorized"` — credentials sent only after a genuine
401, never preventively) resolved the challenge on the first attempt.
`boussole.http_credentials_actif: true` confirms a real success, not just
the flag being passed; `boussole.http_auth_requise: true` flags an
unresolved 401 distinctly from a WAF block.

---

## 5. Write and run an RPA scenario

### 5a. 3-step protocol

**Step 1 — Explore the page (read-only)**

```bash
# Quick view
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --mode fast

# Full view with numbered elements
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y

# Web Components application (Angular, Lit, Stencil)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y --shadow-dom

# Enriched DOM inventory (frameworks, shadow roots, stable data-attrs)
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url https://target.local/ --mode fast
```

**What to note:**
- SoM IDs of fields and buttons (read `capture_som`)
- Stable attributes: `name`, `id`, `aria-label`, `data-testid`
- Blocking overlays (cookie banners, modals)
- SPA or full HTTP reload

**Step 2 — Write the scenario**

```json
{
  "nom": "login_app",
  "url": "https://app.example.com/login/",
  "intention": "Administrator login with stored credentials",
  "actions": [
    {"type": "nettoyer_overlay", "selecteur": ".cookie-banner"},
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".user-avatar"},
    {"type": "capturer", "nom": "after-login"}
  ]
}
```

**Step 3 — Execute**

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/login_app.json --som
```

### 5b. Full scenario: log in and navigate between pages

```json
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "intention": "Visual audit after deployment",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".dashboard-main"},
    {"type": "capturer", "nom": "dashboard"},
    {"type": "naviguer", "url": "https://app.example.com/settings/"},
    {"type": "attendre_navigation"},
    {"type": "capturer", "nom": "settings"},
    {"type": "naviguer", "url": "https://app.example.com/users/"},
    {"type": "attendre_navigation"},
    {"type": "capturer", "nom": "users"}
  ]
}
```

### 5c. Extract data from the DOM

```json
{
  "nom": "extract_counters",
  "url": "https://app.example.com/dashboard/",
  "actions": [
    {"type": "evaluer", "script": "document.title"},
    {"type": "evaluer", "script": "document.querySelectorAll('.user-row').length"},
    {"type": "evaluer", "script": "window.location.href"}
  ]
}
```

Result in `evaluations[]`:
```json
"evaluations": [
  {"index": 0, "script": "document.title", "valeur": "Dashboard — My App"},
  {"index": 1, "script": "...", "valeur": 42},
  {"index": 2, "script": "...", "valeur": "https://app.example.com/dashboard/"}
]
```

### 5d. Assertions on evaluer (rpa.py only)

Three mutually exclusive keys — one per action:

```json
{"type": "evaluer", "script": "document.querySelectorAll('.row').length", "attendu": 3}
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
{"type": "evaluer", "script": "window.location.href", "motif": "/dashboard$"}
```

| Key | Comparison | Valid types |
|---|---|---|
| `attendu` | strict equality `==` | str, int, bool |
| `contient` | substring `in` | str only |
| `motif` | `re.search()` Python | str only |

If the assertion fails: rpa.py stops immediately (exit 1) before any subsequent mutating action.

### 5e. Sub-scenarios (declencher_scenario)

Define a login as a reusable sub-scenario:

```json
{
  "nom": "login_app",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "attendre_selecteur_present", "selecteur": ".user-avatar"}
  ]
}
```

Call this sub-scenario from another scenario:
```json
{
  "nom": "full_audit",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "declencher_scenario", "scenario": "login_app"},
    {"type": "naviguer", "url": "https://app.example.com/report/"},
    {"type": "capturer", "nom": "report"}
  ]
}
```

Maximum depth: 5 nesting levels.

### 5f. Verify you are on the right page before any mutation

Always add a guard as the first action in scenarios that delete or modify:

```json
{"type": "evaluer", "script": "window.location.href", "contient": "/dashboard"},
{"type": "evaluer", "script": "document.querySelector('.alert-danger')?.textContent ?? null", "attendu": null}
```

If the guard fails: rpa.py stops before the deletion is executed.

### 5g. Resume a session (persisted cookies)

```bash
# First invocation — authenticate and save the session
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ \
  --actions /tmp/login.json \
  --sauver-session /tmp/diwall/session.json \
  --som

# Subsequent invocations — reuse the session (no re-login)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/dashboard/ \
  --reprendre-session /tmp/diwall/session.json \
  --som
```

**Session drift signal:** if the session has expired, `boussole.session_derive: true` in the JSON.
In that case: restart the full login without `--reprendre-session`.

### 5h. Structural non-regression without pixels — `--replay-verifier` (v1.17.0)

```bash
# First run — save the structural reference
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/dashboard.json \
  --sauver-verifier-reference /tmp/dashboard.ref.json

# Subsequent runs — compare
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/dashboard.json \
  --replay-verifier /tmp/dashboard.ref.json
```

Compares `http_status`, `dom_stats`, `evaluer` results, and SoM element count
(not content) against the saved reference. Verdict on stderr:

```json
{"type_comparaison": "replay_verifier", "verdict": "stable", "diffs": []}
```

Exit 1 on `verdict: "regression"`, with `diffs` listing each mismatched
field (`reference` vs `obtenu`). The two flags are mutually exclusive.

A reference recorded before v1.24.3 stores a number or a boolean returned by
`evaluer` as text; replayed with v1.24.3 or later it is reported as a
regression (`"2"` against `2`). Record it again with
`--sauver-verifier-reference`.

### 5i. Resume a long scenario after failure — `--checkpoint` (v1.17.0)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/long_audit.json \
  --checkpoint /tmp/long_audit.checkpoint.json
```

If the scenario fails partway through, `/tmp/long_audit.checkpoint.json` is
written with the count of completed actions and a session file. **Relaunch
the exact same command** to resume: already-completed actions are skipped.
On full success, the checkpoint file is deleted automatically.

A run stopped by a navigation cap (`max_actions_par_run`/`max_pages_par_run`)
is treated the same way as a partial failure since v1.17.2 — the checkpoint
is updated with the actual progress, not deleted. Before v1.17.2 it was
deleted in this case too (it returns the same `succes: true` signal as a
fully completed tronçon), silently losing all remaining progress on long
scenarios.

DOM state (open modals, half-filled forms) is never preserved across a
resume — only cookies/`localStorage` and the action-list position are. Do
not rely on `--checkpoint` to resume mid-way through a single multi-step
form; it resumes at action boundaries only.

### 5j. Target elements inside an iframe (v1.17.0)

No Set-of-Mark numbering happens inside an iframe (same-origin or
cross-origin) — target it by CSS selector directly:

```json
{"type": "cliquer_iframe", "iframe_selecteur": "iframe#paiement", "selecteur": "button.valider"},
{"type": "remplir_iframe", "iframe_selecteur": "iframe#paiement", "selecteur": "input[name=cvv]", "valeur": "depuis_secrets", "secret_cle": "cvv"}
```

`remplir_iframe` supports `valeur: "depuis_secrets"` exactly like `remplir`
(section 4b) — never a plaintext credential in the scenario. If the target
element refuses interaction (e.g. a `contenteditable` region in a read-only
state), add `"force": true` to `cliquer_iframe` — same semantics as `cliquer`
(section 7e).

To find the inner selector: use `evaluer` on the iframe's content if it is
same-origin (`document.querySelector('iframe').contentDocument...`), or
consult the target application's own markup/documentation if cross-origin.

### 5k. Nested iframes — `iframe_chemin` (v1.18.0)

An iframe inside another iframe: replace `iframe_selecteur` with
`iframe_chemin`, an ordered array — one CSS selector per nesting level, from
outermost to innermost.

```json
{"type": "cliquer_iframe", "iframe_chemin": ["iframe#wrapper", "iframe#paiement"], "selecteur": "button.valider"},
{"type": "remplir_iframe", "iframe_chemin": ["iframe#wrapper", "iframe#paiement"], "selecteur": "input[name=cvv]", "valeur": "depuis_secrets", "secret_cle": "cvv"}
```

`iframe_selecteur` (single frame) and `iframe_chemin` (nested descent) are
mutually exclusive — exactly one required per action. For a single-level
iframe, keep using `iframe_selecteur` (section 5j).

---

## 6. Actions — complete reference

| Type | Required params | Optional params | Notes |
|---|---|---|---|
| `naviguer` | `url` | — | Full HTTP reload. Counted in `respect.pages_visitees` |
| `cliquer` | `selecteur` | `force` (bool), `repli_js` (bool) | `force: true` bypasses CSS-hidden elements or showModal. `repli_js: true` retries through JS if the native click still fails (v1.22.0) — needs `--no-evaluer` off |
| `cliquer_som` | `id` | — | Click at element centre coordinates. No `force` needed |
| `cliquer_visuel` | `description` | — | LLM vision (~32 s). Last resort for canvas or attribute-less elements |
| `remplir` | `selecteur`, `valeur` | `secret_cle` | `valeur: "depuis_secrets"` resolves the stored credential |
| `remplir_som` | `id`, `valeur` | `secret_cle` | Clears the field before typing. `valeur: "depuis_secrets_totp"` for TOTP |
| `capturer` | `nom` | `som` (bool) | Named intermediate PNG. `som: true` for an annotated capture |
| `evaluer` | `script` | `attendu`, `contient`, `motif` | JS executed in the browser. Assertions for rpa.py only |
| `defiler` | `px` or `selecteur` | — | Vertical scroll in pixels (`px`) or scroll to element (`selecteur`) |
| `pause` | `ms` | `interval_capture` | Fixed delay in ms. Prefer `attendre_selecteur_present` for DOM signals |
| `attendre` | `selecteur` | `interval_capture` | Waits for CSS selector to be present |
| `attendre_navigation` | — | — | Waits for `networkidle` (end of network requests) |
| `attendre_url` | `motif` | `attendre_changement` (bool) | URL contains pattern (partial match). `attendre_changement: true` if current URL already contains the pattern |
| `attendre_selecteur_present` | `selecteur` | — | Waits for element to be visible (state=visible) |
| `attendre_absence` | `selecteur` | `delai_initial_ms` | Waits for element removal from DOM (state=detached) |
| `attendre_reseau_calme` | — | `timeout_ms` | 500 ms of network silence. `timeout_ms`: max duration before giving up |
| `attendre_mfa_ntfy` | `id_som` | `timeout` | Waits for a TOTP code via ntfy, fills it into the SoM field |
| `nettoyer_overlay` | `selecteur` | — | Hides blocking overlays (cookie banner, modal). Use before SoM |
| `declencher_scenario` | `scenario` | — | Inlines a sub-scenario's actions. Max depth: 5 |
| `cliquer_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur` | `force` (bool) | Click inside an iframe (v1.17.0). `iframe_chemin` for nested iframes (v1.18.0, section 5k). No SoM inside frames |
| `remplir_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur`, `valeur` | `secret_cle` | Fill inside an iframe (v1.17.0). `iframe_chemin` for nested iframes (v1.18.0). `valeur: "depuis_secrets"` supported |

---

## 7. Handle common obstacles

### 7a. Cookie banner / blocking overlay

```json
{"type": "nettoyer_overlay", "selecteur": ".cookie-consent-banner, #gdpr-overlay"}
```

Place **before** any other action and before SoM. The overlay masks elements that SoM numbers.
Do not use in `watch.py` scenarios (the overlay is part of the visual reference).

### 7b. Out-of-viewport element

SoM warns when an interactive element is off-screen:
```json
"som_hors_viewport": 3,
"avertissement_scroll": "3 interactive element(s) off-viewport — use defiler before cliquer_som"
```

```json
{"type": "defiler", "selecteur": "#the-button"},
{"type": "remplir_som", "id": 7, "valeur": "depuis_secrets", "secret_cle": "username"}
```

### 7c. Web Components — Shadow DOM

If visible interactive elements receive no SoM number:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --shadow-dom
```

Or in the scenario: `"shadow_dom": true` at the root.

When to use: Angular, Lit, Stencil, FAST. Do not activate on projects without Web Components.

To access an element inside a Shadow Root without `--shadow-dom`:
```json
{"type": "evaluer", "script": "document.querySelector('my-component').shadowRoot.querySelector('button').click()"}
```

### 7d. SPA (React, Vue, Angular) — navigate without reload

After a click that changes the view in an SPA, Playwright does not know when navigation is complete.

```json
{"type": "cliquer_som", "id": 5},
{"type": "attendre_url", "motif": "/dashboard"},
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
```

Or wait for an element specific to the new view:
```json
{"type": "cliquer_som", "id": 5},
{"type": "attendre_selecteur_present", "selecteur": "[data-testid='dashboard-main']"}
```

Never assume a click has completed navigation without a DOM signal.

### 7e. CSS dialog or showModal()

`TimeoutError` on `cliquer` when the element is visible in the DOM = CSS-hidden element
or inside a dialog.

```json
{"type": "cliquer", "selecteur": "#dialog-confirm button[type=submit]", "force": true}
```

If `force: true` is insufficient (element absent from DOM):
```json
{"type": "evaluer", "script": "document.querySelector('#dialog-confirm button[type=submit]').click()"}
```

**Do not use `force` on `cliquer_som`** — unnecessary, `cliquer_som` uses coordinates and
bypasses checks natively.

### 7f. Long operation (spinner, batch job)

Do not use `pause` to wait for a fixed duration. Wait for the DOM signal:

```json
{"type": "cliquer_som", "id": 7},
{"type": "attendre_absence", "selecteur": ".spinner", "delai_initial_ms": 500},
{"type": "attendre_selecteur_present", "selecteur": ".result-container"},
{"type": "capturer", "nom": "result"}
```

If the operation provides no DOM signal, use `interval_capture` to observe state:
```json
{"type": "pause", "ms": 30000, "interval_capture": 5}
```

Intermediate captures appear in `stream_captures[]`.

### 7g. Cap reached (v1.15.0)

If `respect.plafond_atteint` is present in the output, the run was stopped
before the scenario completed. Remaining actions were not executed.

Options:
1. Increase `max_pages_par_run` or `max_actions_par_run` in `diwall.conf`
2. Split the scenario into multiple runs
3. Override caps in the scenario JSON (to be documented in _CADRE)

### 7h. `<select>` form field

`remplir` does not work on `<select>`. Use `remplir_som` with the SoM ID of the `<select>`.

### 7i. Invalid SoM IDs on next run

SoM IDs are recalculated on each capture. They do not persist between invocations.
Always re-run `shot.py --som` to get the current run's IDs.
After a `defiler` or opening a modal: re-run `shot.py --som`.

### 7j. SoM ID drift on highly dynamic pages — hybrid resolution (v1.24.0)

`cliquer_som`/`remplir_som` resolve `id: N` by re-indexing the live DOM at
click time — if an interactive element appears or disappears **before** your
target in DOM order between the `--som` capture and the click (a cookie
banner closing, a modal opening), a raw `id: N` can silently resolve to a
**different** element than the one shown numbered N in the screenshot.

Since v1.24.0 the default resolver is hybrid. In one page call it:

- looks up the `data-dw-som-id="N"` marker (**stable** path, set by a
  `{"type":"capturer","som":true}` action or the final capture);
- computes the N-th element by raw re-indexing (**raw** path);
- returns the stable path when the marker exists, the raw path otherwise
  (**fallback** — identical to pre-v1.24.0 behaviour);
- reports `boussole.respect.som_resolution` (`stable` \| `brut` \|
  `brut_sans_reference`) and, when the two paths disagree,
  `boussole.respect.som_derive_detectee` with the SoM id.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som \
  --actions '[{"type":"capturer","nom":"avant","som":true},{"type":"cliquer_som","id":5}]'
```

The stable path only helps within one scenario — the marker does not survive
across two `shot.py` calls (each reloads the page). For a mutation-prone
target, capture SoM in the same scenario before the first `cliquer_som`. When
`som_resolution` is `brut_sans_reference`, drift cannot be detected — recapture
SoM if the DOM changed. `--som-brut` forces pure raw re-indexing (no marker
lookup, no divergence detection); `boussole.som_brut_actif: true` then.
`--som-rafraichir` (v1.17.0) is a no-op alias kept for backward compatibility.

Since v1.17.2, the injector purges markers left by a previous `--som` capture
in the same page before renumbering — without this, an element hidden or
scrolled out between two captures could keep a stale `data-dw-som-id`,
colliding with a freshly numbered element and resolving to the wrong one.

### 7k. Site blocked by WAF (immediate 403)

```bash
# Try with stealth
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --mode fast --stealth
```

If 403 persists with `--stealth`: the site uses TLS fingerprinting (JA3/JA4) or advanced
behavioural analysis (Cloudflare Enterprise). `playwright-stealth` does not bypass these protections.
See `docs/RETOUR_EXPERIENCE.md` FR-77/FR-78/FR-79 for context.

Diwall also flags a likely block passively without you having to check the
HTTP status yourself — see section 3e (`respect.waf_bloquants`).

### 7l. Initial navigation never completes — `--wait-until` (v1.22.0)

Symptom: `TimeoutError` on the initial navigation, and raising `--timeout`
changes nothing (45 s fails exactly like 10 s). Cause: by default Diwall waits
for `networkidle` — 500 ms of network silence. A page that polls continuously
(live statistics, auto-refreshing counters, router admin panels) never
produces that silence, so no timeout value can ever be large enough.

```bash
# shot.py — direct reconnaissance
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url http://target.local/ --wait-until load --som --a11y --guide-version 1.3

# rpa.py — propagated to shot.py, so scenarios reach the same targets
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario ./admin_login.json --wait-until load --guide-version 1.3
```

A scenario can carry it as a root property instead, staying self-contained:

```json
{"url": "http://target.local/", "wait_until": "load", "actions": [...]}
```

The CLI flag takes precedence over the scenario property.

| Value | Waits for | Use when |
|---|---|---|
| `networkidle` | 500 ms of network silence | default — keep it unless it fails |
| `load` | `load` event (page and sub-resources) | continuous polling / live statistics |
| `domcontentloaded` | HTML parsed, sub-resources still pending | very heavy page, DOM is all you need |

Applies to the initial navigation only — the `naviguer` action is unaffected.
`boussole.wait_until` reports the value only when it differs from the default.

---

## 8. Visual monitoring — watch.py

### 8a. Save a reference

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --sauver-reference \
  --nom home
```

The reference is saved in `/opt/diwall/references/`.

### 8b. Compare to the reference (pixel diff)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
```

Verdicts:

| `taux_diff` | Verdict | Exit code |
|---|---|---|
| < 0.2% | `stable` | 0 |
| 0.2% – 5% | `drift` | 0 |
| ≥ 5% | `regression` | 1 |
| Different dimensions | `viewport_mismatch` | 2 |

### 8c. Semantic comparison (LLM)

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer \
  --llm local
```

Combine pixel diff and LLM analysis:
```bash
--llm-en-complement   # LLM only if pixel verdict is drift or regression
```

`--llm claude` (v1.24.2) sends both captures — reference and current — to the
Anthropic API instead of the local model; it applies to `--comparer` and to
`--llm-en-complement` alike. The captures leave the machine, reduced so that
their longest side does not exceed 1568 px, the size the API works at. It needs
the `anthropic` module, absent from a standard installation, and a key in the
environment of the process:

```bash
sudo /opt/diwall/venv/bin/pip install anthropic
ANTHROPIC_API_KEY=... diwall-watch --url https://target.local/status --comparer --llm claude --guide-version 1.3
```

A missing module, a refused key or a model refusal comes back as a plain
message in the output (`erreur`, or `analyse_llm` in pixel mode), never as a
traceback.

### 8d. Ignore an animated zone

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel reference.png \
  --exclure-zone 100,200,300,50    # X,Y,Width,Height in pixels
```

### 8e. Monitoring loop

```bash
while true; do
  /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
    --url https://target.local/status \
    --comparer-pixel /opt/diwall/references/status-ok.png \
    --ntfy-url https://ntfy.sh/my-alerts
  sleep 60
done
```

### 8f. Cron for autonomous monitoring

```bash
# /etc/cron.d/diwall-monitor
*/30 * * * * diwall /opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/status \
  --comparer-pixel /opt/diwall/references/status-ok.png \
  --ntfy-url https://ntfy.sh/my-alerts \
  >> /var/log/diwall/cron.jsonl 2>&1
```

### 8g. Continuous structural monitoring — `monitor-verifier.sh` (v1.18.0)

Complements 8a–8f: `watch.py` monitors *appearance* (pixels/semantic).
`scripts/monitor-verifier.sh` monitors *structure* (`http_status`,
`dom_stats`, `evaluations`, SoM count) — zero image, zero LLM call, built on
`--no-capture` + `--replay-verifier` (section 5h).

```bash
# First run — create the structural reference
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --sauver-verifier-reference /opt/diwall/references/sillage_login.ref.json

# One check-and-alert pass — not a daemon, run it repeatedly via cron.
# scripts/*.sh is never deployed to /opt/diwall/, so it runs from the git
# source, as your own user.
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --reference /opt/diwall/references/sillage_login.ref.json \
  --ntfy-topic diwall-monitoring
```

```bash
# crontab -e (your own crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/sillage_login.json \
  --reference /opt/diwall/references/sillage_login.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

Stable → silence. Regression → one `ntfy` notification with the diff. Each
invocation is an isolated process — no daemon, no memory-leak risk, and
Respectful Navigation caps reset cleanly on every pass.

---

## 9. Operation log

The log is configurable in `diwall.conf` (v1.15.0):

```json
"journal": {
  "chemin": "~/Vaults/__PROJET__/Diwall/operations.jsonl"
}
```

If absent or the encrypted directory is not mounted, fallback: `DIWALL_JOURNAL` env var, then `/var/log/diwall/operations.jsonl`.

```bash
# Read the last 10 entries
tail -n 10 ~/Vaults/__PROJET__/Diwall/operations.jsonl | python3 -m json.tool

# Filter by target (journal.py tool)
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com

# Filter mutating operations only
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --mutatif

# From a date
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --depuis 2026-07-01

# Failed runs only (v1.20.0) — resultat != "succes"
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py \
  --cible app.example.com --erreurs
```

Fields in each entry:

| Field | Meaning |
|---|---|
| `ts` | ISO 8601 timestamp |
| `version` | Diwall version |
| `outil` | `shot.py` or `rpa.py` |
| `cible_url` | Target URL |
| `scenario` | Scenario file path (RPA mode) |
| `source_scenario` | Scenario file name only, no path (v1.18.0) — powers `mode_conseille` (section 2e) |
| `resultat` | `"succes"` or `"echec"` |
| `mutatif` | `true` if at least one write action |
| `duree_ms` | Duration in ms |
| `intention` | Label passed via `--intention` or scenario `intention` field |

### 9a. Log rotation (G-36, CHANTIER_SANITISATION.md)

Diwall does not ship a logrotate configuration — `/var/log/diwall/operations.jsonl`
grows unbounded until the administrator installs one. `lib/journal.py` opens
and closes the file on every write (no persistent file descriptor across
runs), specifically so the **default** logrotate behaviour (rename the
current file, create a fresh one) works correctly without any special
option: the next write reopens the path and finds the new inode.

**Do not add `copytruncate`** to a Diwall logrotate config — it is
unnecessary here (unlike tools that hold a file descriptor open across
their lifetime) and reintroduces a write-loss window this design was built
to avoid. Example `/etc/logrotate.d/diwall`:

```
/var/log/diwall/operations.jsonl {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0640 diwall diwall
}
```

`journal.py` (the reader) already follows rotated files transparently
(`operations.jsonl`, `.1`, `.2.gz`, …) — no extra step needed after rotation.

---

## 10. CLI flags — reference

### shot.py

| Flag | Default | Description |
|---|---|---|
| `--version` | — | Prints installed version and exits immediately — no Playwright, no other argument required (v1.18.0) |
| `--guide-version X.Y` | — | Proof of reading `docs/GUIDE_LLM.md` — required unless a valid local marker already exists (v1.18.0, section 1) |
| `--url URL` | required | URL to capture |
| `--actions FILE` | — | JSON file of sequential actions |
| `--output-dir DIR` | `/tmp/diwall` | PNG output directory |
| `--timeout MS` | 10000 | Per-action Playwright timeout (ms) |
| `--screenshot-timeout MS` | 120000 | Timeout for `page.screenshot()` (ms). Distinct from `--timeout` |
| `--largeur PX` | 1280 | Viewport width |
| `--hauteur PX` | 720 | Viewport height |
| `--som` | off | Activate Set-of-Mark (element numbering) |
| `--a11y` | off | Include accessibility tree in JSON |
| `--shadow-dom` | off | Traverse Shadow Roots for SoM (Angular, Lit, Stencil) |
| `--stealth` | off | playwright-stealth stealth mode (v1.15.0) |
| `--mode fast\|full` | — | `fast` = `--no-capture --a11y`. `full` = default behaviour |
| `--no-capture` | off | Skip PNG capture and SoM |
| `--llm local\|claude` | `local` | LLM engine for `cliquer_visuel` |
| `--secrets FILE` | — | Explicit path to a credentials file |
| `--auth-indicator SEL` | — | CSS selector present only in authenticated session |
| `--auth-indicator-negative SEL` | — | CSS selector present only outside authenticated session |
| `--intention TEXT` | — | Business label recorded in the log |
| `--sauver-session FILE` | — | Saves cookies after actions |
| `--reprendre-session FILE` | — | Resumes a saved session |
| `--interval-capture N` | 0 | Periodic captures every N seconds during `attendre`, `pause` |
| `--som-brut` | off | Forces pure raw SoM re-indexing; disables the hybrid resolver's stable path and divergence detection (v1.24.0, section 7j) |
| `--som-rafraichir` | off | No-op alias since v1.24.0 — hybrid resolution is the default (v1.17.0, section 7j) |
| `--ignorer-waf` | off | A detected WAF block degrades `niveau_confiance` but no longer forces `pret_a_agir: false` on its own (v1.17.2, section 3e) |
| `--http-credentials` | off | Resolves HTTP Basic Auth credentials from the credentials file, scoped to the target's origin (v1.21.0, section 4g) |
| `--no-evaluer` | off | Refuses the **evaluer** action for the whole run — recommended in production against targets with sensitive forms (v1.15.1) |
| `--no-filtre-evaluer` | off | Disables stdout neutralisation of **evaluer** return values, URLs and error messages — explicit debug runs only. Neutralisation is on by default; when disabled, `boussole.filtre_evaluer_actif: false` is set in the output so the operator can audit it from the JSON itself (v1.23.0) |

### rpa.py

Propagates all relevant shot.py flags, plus:

| Flag | Description |
|---|---|
| `--version` | Prints installed version and exits immediately (v1.18.0) |
| `--guide-version X.Y` | Proof of reading `docs/GUIDE_LLM.md` — checked independently, same rule as shot.py (v1.18.0) |
| `--scenario FILE` | Path to JSON or YAML scenario (required) |
| `--url URL` | Overrides scenario URL without modifying the file |
| `--stealth` | Propagated to shot.py |
| `--mode fast\|full` | Propagated to shot.py |
| `--som-brut` | Propagated to shot.py. Also settable as scenario root property `"som_brut": true` (v1.24.0, section 7j) |
| `--som-rafraichir` | Propagated to shot.py — no-op alias since v1.24.0 (v1.17.0, section 7j) |
| `--ignorer-waf` | Propagated to shot.py (v1.17.2, section 3e) |
| `--http-credentials` | Propagated to shot.py. Also settable as scenario root property `"http_credentials": true` (v1.21.0, section 4g) |
| `--sauver-verifier-reference FILE` | Saves structural reference for `--replay-verifier` (v1.17.0, section 5h) |
| `--replay-verifier FILE` | Compares run against a structural reference, exit 1 on regression (v1.17.0, section 5h) |
| `--checkpoint FILE` | Resumes a long scenario after a mid-run failure (v1.17.0, section 5i) |

### watch.py

| Flag | Description |
|---|---|
| `--version` | Prints installed version and exits immediately (v1.18.0) |
| `--guide-version X.Y` | Proof of reading `docs/GUIDE_LLM.md` — checked independently, same rule as shot.py (v1.18.0) |
| `--url URL` | URL to monitor |
| `--sauver-reference` | Capture and save as reference |
| `--comparer-pixel REF` | Pixel diff against PNG file REF |
| `--comparer` | Semantic LLM diff |
| `--llm local\|claude` | Engine for `--comparer` and `--llm-en-complement` (default `local`; `claude` sends the captures to the Anthropic API, v1.24.2) |
| `--nom NAME` | View name (multiple views per URL) |
| `--seuil-stable F` | `stable` threshold (default: 0.002 = 0.2%) |
| `--seuil-regression F` | `regression` threshold (default: 0.05 = 5%) |
| `--exclure-zone X,Y,W,H` | Zone to ignore (repeatable) |
| `--heatmap` | Produces a PNG of modified zones |
| `--ntfy-url URL` | Sends an ntfy alert on regression |
| `--llm-en-complement` | Adds LLM diff when pixel = drift or regression |

---

## 11. Exit codes and output

### Exit codes

| Code | Cause | What to do |
|---|---|---|
| 0 | Success | — |
| 1 | Playwright error, failed action, rpa.py assertion | Read `erreur` in JSON. See `GUIDE_LLM_INTERACTIONS.md` |
| 1 | `guide_non_lu` — missing/wrong `--guide-version`, no valid marker (v1.18.0) | Fires before Playwright launches. Read `docs/GUIDE_LLM.md`, relaunch with `--guide-version X.Y` (section 1) |
| 2 | `viewport_mismatch` (watch.py) | Re-capture reference at same viewport |
| 3 | `playwright` module not found | Invoke via `/opt/diwall/venv/bin/python3` |
| 42 | `SecretsFermesError` — encrypted directory not mounted, or invalid checksum | Mount it, or verify the credentials file |
| 43 | `SecretsNonConfigureError` — `diwall.conf` absent | `sudo cp /opt/diwall/diwall-sample.conf /opt/diwall/diwall.conf && sudo nano /opt/diwall/diwall.conf` |

### Output JSON structure

```json
{
  "succes": true,
  "http_status": 200,
  "url_finale": "https://target.local/dashboard",
  "erreurs_js": [],
  "erreurs_console": [],
  "duree_ms": 2400,
  "horodatage": "2026-07-01T12:00:00+02:00",
  "capture": "/tmp/diwall/a1b2c3d4e5f6/capture_1234567890123456789.png",
  "capture_som": "/tmp/diwall/a1b2c3d4e5f6/capture_som_1234567890123456789.png",
  "elements_som": [...],
  "a11y_tree": "...",
  "evaluations": [...],
  "latences_actions": [
    {"index": 0, "type": "naviguer", "latence_ms": 842},
    {"index": 1, "type": "cliquer_som", "latence_ms": 63}
  ],
  "respect": {
    "pages_visitees": 0,
    "actions_executees": 3,
    "duree_totale_ms": 2400,
    "indice_agressivite": 0.33
  },
  "etat": {
    "pret_a_agir": true,
    "niveau_confiance": "eleve",
    "raisons": ["aucun signal de friction détecté"]
  },
  "boussole": {
    "utilisateur": "operator",
    "ip_locale": "__IP_LAN__",
    "repertoire": "/opt/diwall",
    "operation_id": "a1b2c3d4e5f6",
    "url_courante": "https://target.local/dashboard",
    "titre_page": "Dashboard — My App",
    "stealth_actif": true,
    "shadow_dom_actif": true,
    "auth_status": "active",
    "som_hors_viewport": 0,
    "respect": { "pages_visitees": 0, "actions_executees": 3, "duree_totale_ms": 2400, "indice_agressivite": 0.33, "som_resolution": "stable" }
  },
  "diwall_meta": {
    "version_shot": "1.23.0",
    "profil": "operator",
    "modeles_appeles": []
  }
}
```

`operation_id` (v1.16.0) is always present and identifies this run uniquely —
it names the isolation directory under `/tmp/diwall/<operation_id>/` and
matches the `operation_id` field of this run's entry in the operations log
(section 9). `etat` (v1.16.0) is present on the success path only.
`latences_actions` (v1.20.0) is always present (empty list if no actions),
one entry per action that actually dispatched — see `GUIDE_LLM_MONITORING.md`
for how it complements `respect.duree_totale_ms`.

Conditional keys (absent when inactive): `capture`, `capture_som`, `elements_som`, `a11y_tree`,
`evaluations`, `auth_status`, `stealth_actif`, `shadow_dom_actif`, `som_brut_actif`,
`som_hors_viewport`, `session_derive`, `respect.plafond_atteint`, `respect.waf_bloquants`,
`respect.som_resolution` (present whenever a SoM action was resolved),
`respect.som_derive_detectee` (present only on a stable/raw divergence),
`respect.indice_agressivite` (present whenever at least one action ran),
`actions_executees_avant_echec`, `pages_visitees_avant_echec` (failure JSON only, v1.17.0),
`etat.mode_conseille` (present only with real prior `diagnostic_dom.json` data for this host, v1.18.0, section 2e).

### Error — format

```json
{
  "succes": false,
  "erreur": "secrets_fermes",
  "message": "Le répertoire chiffré Diwall est initialisé mais non monté.",
  "code_sortie_recommande": 42,
  "boussole": { "url_courante": "", "titre_page": "" }
}
```

---

## Reference paths

| Path | Role |
|---|---|
| `/opt/diwall/` | Production installation |
| `/opt/diwall/venv/bin/python3` | Python to use for every invocation |
| `/opt/diwall/diwall.conf` | Machine configuration (credentials, navigation, log) |
| `/opt/diwall/diwall-sample.conf` | Configuration template |
| `/opt/diwall/scenarios/` | RPA scenarios |
| `/opt/diwall/docs/` | Documentation |
| `/opt/diwall/references/` | watch.py visual references |
| `/tmp/diwall/<operation_id>/` | Temporary captures for one run, isolated by `operation_id` (v1.16.0, cleared on reboot) |
| `~/Vaults/__PROJET__/Diwall/` | Credentials + log (gocryptfs volume) |
| `~/git/Diwall/Diwall/` | Git sources (modify here, then `deploy.sh`) |

Deploy after modifying sources:
```bash
bash ~/git/Diwall/Diwall/scripts/deploy.sh
```
