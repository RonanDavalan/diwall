# Diwall — Sessions guide (vault, credentials, SPA, MFA, multi-page)

<!-- notice-version: 1.2 -->
Version 1.2 — June 2026 (v1.14.0) — auth_indicator_negative

Load this notice when: vault credentials, `--secrets`, session persistence, SPA navigation,
multi-page flows, MFA/TOTP, auth_indicator, --no-capture.

---

## Security rules — non-negotiable

**FORBIDDEN — extracts credential into shell:**
```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER
USER=$(jq -r '.username' ~/Vaults/.../file.json)    # NEVER
```

**CORRECT — vault resolved inside Playwright by lib/vault.py:**
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "username"}
{"type": "remplir_som", "id": 3, "valeur": "depuis_vault", "vault_cle": "password"}
```

Values never appear in shell, bash history, process list, or any log.
Also forbidden: using `curl`, `wget`, or any HTTP client for authentication.

---

## Vault configuration — how it works

The vault is a JSON file inside a gocryptfs-encrypted directory, mounted by the operator.
`lib/vault.py` reads the mounted file; it never exposes values in the shell.

The active vault path is configured in `diwall.conf` (YAML, `secrets_defaut`).
You never need to know the path — pass `--secrets` when you need a specific vault,
otherwise the default vault in `diwall.conf` is used.

`vault_cle` is the JSON key inside the decrypted file (e.g., `"username"`, `"password"`).

**If the vault is closed** (gocryptfs not mounted): shot.py exits with `VaultFermeError(42)`.
Do not try to mount the vault yourself — ask the operator to run the mount script.

**Critical — unmounted vault and write operations:**
`VaultFermeError` only protects reads. If a vault is not mounted, its directory
exists on disk but is empty and unencrypted. Any file written there is stored
in plain text. Before creating or updating a credential file, confirm the vault
is mounted: the directory must be non-empty. If in doubt, stop and ask the
operator to verify — never write credentials assuming the vault is open.

---

## `--secrets` — specifying a non-default vault

When a scenario needs credentials from a vault different from the default:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --secrets /opt/diwall/vaults/other-vault/creds.json
```

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --secrets /opt/diwall/vaults/other-vault/creds.json
```

**Multi-vault scenarios** (v1.10.0): pass `--secrets` multiple times for multiple vaults.
```bash
--secrets /opt/diwall/vaults/vault-A/creds.json \
--secrets /opt/diwall/vaults/vault-B/creds.json
```

---

## Mode A (interactive — shot.py direct)

Use Mode A for exploration and single captures with a visual ReAct loop.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y --llm local
```

Output: JSON with `capture_som`, `elements_som`, `a11y_tree`, `boussole`.
You read the PNG, decide which element to interact with, pass the ID to the next call.

**Keep Mode A alive across steps:** pass `--actions` with accumulated actions each time.
Closing and reopening shot.py loses the browser session. Use `--sauver-session` to save
the session state to a JSON file, then `--reprendre-session` to reload it on the next call.

---

## Mode B (RPA — rpa.py declarative)

Use Mode B for fully autonomous, repeatable scenarios.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/login-check.json
```

rpa.py runs shot.py once per captured intermediate and once at the end.
It collects all `evaluations[]` and runs assertions if `attendu`, `contient`, or `motif` is set.

**When to choose Mode B over Mode A:**
- The flow is already known and validated in Mode A
- The task must run unattended (cron, scheduled check)
- You are building a test suite

**stdout of rpa.py** (v1.11.0) is a single JSON line — no tail-1 needed. Pipe freely.

---

## Session persistence across calls (`--reprendre-session`)

When a login form saves a cookie in the browser, you can persist the session.

```bash
# First call — authenticate and save session
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/login \
  --actions login_actions.json \
  --sauver-session ~/diwall-session.json \
  --som

# Subsequent calls — reuse session
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/dashboard \
  --reprendre-session ~/diwall-session.json \
  --som
```

**Note (v1.11.1):** `shot.py` no longer deletes the session file at end of run (FR-74/FR-75).
`--reprendre-session` without `--sauver-session` is now safe across chained calls.
Add `--sauver-session` only if you want to explicitly refresh the on-disk session state.

**Warning — session drift signal (lot 8.5):** if the session has expired or the
app redirected you to the login page, `boussole.session_derive: true` will appear
in the JSON output. Check it after every `--reprendre-session` call.

```json
"boussole": {
  "session_derive": true,
  "url_courante": "https://target.local/login"
}
```

If `session_derive` is true: run the full login flow again without `--reprendre-session`.

---

## SPA navigation — rules

Single-page applications (React, Vue, Angular) do not reload the page on navigation.
Playwright's default navigation wait (`load` event) never fires.

**Rules:**
1. After clicking a navigation link → add `attendre_url` or `attendre_selecteur_present`
2. After a form submission → add `attendre_url` or `attendre_selecteur_present`
3. Never assume navigation is complete after a click alone

```json
[
  {"type": "cliquer_som", "id": 5},
  {"type": "attendre_url", "motif": "dashboard"},
  {"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
]
```

Note: `motif` in `attendre_url` is a URL glob substring (not a Python regex).
`motif` in `evaluer` is a Python `re.search()` expression.

---

## Multi-page flows and subdomain navigation

When a flow crosses domains or requires a full page reload:

```json
[
  {"type": "cliquer_som", "id": 8},
  {"type": "attendre_navigation"},
  {"type": "capturer", "nom": "after_redirect"}
]
```

After `attendre_navigation`, the browser has loaded the new page.
A new `shot.py --som` call is required to get fresh SoM IDs.

---

## `attendre_reseau_calme` — wait for AJAX to finish

After submitting a form or triggering an AJAX operation:

```json
[
  {"type": "cliquer", "selecteur": "button[type=submit]"},
  {"type": "attendre_reseau_calme", "timeout_ms": 10000},
  {"type": "capturer", "nom": "after_submit"}
]
```

Internal silence threshold: 500ms of network inactivity. `timeout_ms` is the maximum
total wait before abort (distinct from the silence threshold).

---

## `auth_indicator` — authentication status (v1.9.0)

Add `auth_indicator` in the scenario root to declare a CSS selector that is only
visible when the user is authenticated. shot.py checks for it on every capture.

```json
{
  "url": "https://target.local/",
  "auth_indicator": ".user-avatar",
  "actions": [...]
}
```

Output includes `auth_status: "active"` when the selector is found, `"inactive"` otherwise.
If `auth_indicator` is not set: `auth_status` is absent from the output.

**`auth_indicator_negative` — disambiguation for ambiguous selectors (v1.14.0)**

On some interfaces, the positive selector (e.g. `.user-menu`) is visible even on the
login page (persistent header). Add `auth_indicator_negative` to cross-check:

```json
{
  "auth_indicator": ".user-menu",
  "auth_indicator_negative": ".btn-login"
}
```

Logic: `auth_status = "active"` if positive selector visible **AND** negative selector
absent or not visible. Use `--auth-indicator-negative` on the CLI for shot.py direct calls.

---

## `--no-capture` — skip screenshot for text-only queries (v1.9.0)

Pass `--no-capture` to shot.py when you only need `a11y_tree` or `evaluer` results
and do not need a visual capture. Avoids the ~2s screenshot overhead.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/api/status \
  --no-capture --a11y
```

Output: JSON without `capture` and `capture_som` fields. `a11y_tree` and
`evaluations` are still present.

---

## MFA / TOTP flows

The `attendre_mfa_ntfy` action waits for a TOTP code pushed via the ntfy
notification system. This requires the ntfy integration to be configured.

```json
[
  {"type": "cliquer_som", "id": 5},
  {"type": "attendre_mfa_ntfy", "id_som": 6, "timeout": 120}
]
```

`id_som`: SoM ID of the OTP input field. `timeout`: max wait in seconds (default 120).

The action polls the ntfy topic for a 6-digit code, then fills the input field
and submits. It does NOT use the vault — the code is pushed live by the authenticator.

**Manual TOTP fallback** (no ntfy):
```json
[
  {"type": "remplir_som", "id": 6, "valeur": "123456"},
  {"type": "cliquer_som", "id": 7}
]
```

Replace `123456` with the live TOTP code. Requires human intervention.

---

## Skills — calling a named sub-sequence

Skills are reusable action sequences defined in `skills/` (YAML files).
Invoke a skill with the `declencher_scenario` action:

```json
{"type": "declencher_scenario", "scenario": "login_myapp"}
```

Resolved as `scenarios/login_myapp.json` (or `.yaml`, `.yml`). Max depth: 5.

**Common pattern:** define the authentication sequence as a skill, call it at
the beginning of every scenario that requires a logged-in session.

---

## Session summary — checklist

| Task | Action |
|---|---|
| First login | Mode A with `--actions`, then check `auth_status` |
| Persistent session | Add `--reprendre-session` to next calls |
| Session drift detected | Re-run login without `--reprendre-session` |
| SPA navigation | Always add `attendre_url` after click |
| Credential fill | `valeur: "depuis_vault"` + `vault_cle` — never shell |
| Non-default vault | `--secrets /path/to/creds.json` |
| OTP in real-time | `attendre_mfa_ntfy` or manual `remplir_som` |

---

## `--ignore-tls-errors` — LAN and internal PKI targets (v1.15.1)

By default, Playwright rejects invalid TLS certificates. This is the secure default.

On internal networks using a self-signed CA (e.g. Step-CA, mkcert, corporate PKI)
or a LAN device with a self-signed certificate, you may pass:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://router.local/ \
  --ignore-tls-errors
```

Or via rpa.py:
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/lan-check.json \
  --ignore-tls-errors
```

When active, `boussole.tls_errors_ignored: true` appears in the JSON output.

**Never use on public internet targets.** An invalid TLS certificate on a public
target is a strong signal of a TLS interception attack (MITM). Do not pass this
flag unless you have a specific, documented reason for a controlled LAN or dev environment.

---

## `--stealth` + `--shadow-dom` — compatibility (v1.15.2, Qwen Q1)

The two flags operate on entirely distinct layers and combine without conflict:

- `--stealth` (playwright-stealth) acts at **browser context creation**, before
  any page loads — it patches `navigator.webdriver` and normalizes fingerprint
  attributes once, at the Chromium level.
- `--shadow-dom` acts **intra-page**, during SoM injection — it changes which
  JS walker function (`_SOM_INJECTER_JS` vs `_SOM_INJECTER_JS_SHADOW`) traverses
  the DOM to number elements.

They can be combined freely:
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.example/ --stealth --shadow-dom --som
```
`boussole` will show both `stealth_actif: true` and `shadow_dom_actif: true`.

---

## Pre-condition pattern — Securing scenario entry

Before any **mutating action** (delete, submit, write), add an `evaluer` assertion as the
first action to verify you are on the expected page. This guards against orphaned actions
when a session expired in the background or a redirect landed on the wrong page.

**Pattern — URL check:**
```json
{"type": "evaluer", "script": "window.location.href", "contient": "/dashboard"}
```

**Pattern — title check:**
```json
{"type": "evaluer", "script": "document.title", "contient": "Dashboard"}
```

**Pattern — absence of error banner:**
```json
{"type": "evaluer", "script": "document.querySelector('.alert-danger')?.textContent ?? null", "attendu": null}
```

**Pattern — selector present (readable state):**
```json
{"type": "attendre_selecteur_present", "selecteur": ".user-logged-in"}
```

**Fail-fast behaviour:** if the assertion fails, `rpa.py` exits immediately (exit 1) with a
structured diagnostic before any mutating action runs.

Place the guard as action index 0 in any scenario that performs deletions or sensitive writes.
