# Diwall — Sessions guide (encrypted directory, credentials, SPA, MFA, multi-page)

<!-- notice-version: 1.1 -->
Version 1.1 — August 2026. This number counts revisions of this notice, not
releases of Diwall. Notable in the current text: `action_secret_en_clair`
and `url_scheme_interdit` error codes documented under Security rules.
Prior (v1.0): `dernier_code_http` in boussole, disambiguates real session
expiry from a masked server error on the same login redirect. Prior
(v1.21.0): `--http-credentials`: username/password fallback, confirmed
against a real Caddy target. Fixed a false claim that `--secrets`
accumulates across repeated flags (it does not); clarified that its
filename is arbitrary, never hostname-derived — both found via a real field
session (Qwen3.6 Plus, ticketing-platform check-in documentation, 14/07/2026)

Load this notice when: credentials, `--secrets`, session persistence, SPA navigation,
multi-page flows, MFA/TOTP, auth_indicator, --no-capture.

---

## Security rules — non-negotiable

**FORBIDDEN — extracts credential into shell:**
```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER
USER=$(jq -r '.username' ~/Vaults/.../file.json)    # NEVER
```

**CORRECT — credentials resolved inside Playwright by lib/repertoire_chiffre.py:**
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "username"}
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Values never appear in shell, bash history, process list, or any log.
Also forbidden: using `curl`, `wget`, or any HTTP client for authentication.

**`action_secret_en_clair` (`rpa.py`, exit 1):** a scenario action carries a
plaintext value on a `password`/`secret`-looking selector or field instead of
`"valeur": "depuis_secrets"` + `"secret_cle": "..."`. Checked before the
scenario ever reaches Playwright's argv. Fix: replace the plaintext value
with the `depuis_secrets` form above — this is the only accepted shape,
scenario JSON or not, test tenant or not.

**`url_scheme_interdit` (`shot.py`/`rpa.py`, exit 2):** the target URL —
`--url`, a scenario's `url` field, or the URL restored by
`--reprendre-session` — uses a scheme other than `http`/`https` (e.g.
`file://`, `javascript:`), or carries userinfo (`user:pass@host`). Fix:
pass a plain `http(s)://host/path` URL; resolve credentials through
`depuis_secrets`, never through the URL itself.

---

## Credentials — how it works

The credentials file is a JSON file inside an encrypted directory (a gocryptfs volume), mounted by the operator.
`lib/repertoire_chiffre.py` reads the mounted file; it never exposes values in the shell.

The active credentials path is configured in `diwall.conf` (YAML, `secrets_defaut`).
You never need to know the path — pass `--secrets` when you need a specific file,
otherwise the default one in `diwall.conf` is used.

`secret_cle` is the JSON key inside the decrypted file (e.g., `"username"`, `"password"`).

**If the encrypted directory is closed** (gocryptfs not mounted): shot.py exits with `SecretsFermesError(42)`.
Do not try to mount it yourself — ask the operator to run the mount script.

**Unmounted directory and internal writes (fixed in v1.17.2):**
Diwall's own operations journal (`operations.jsonl`) and mutative-run proof
archiving (`preuves/`) now detect a closed directory before writing: if the
configured path is inside it but it is not currently mounted,
the journal entry is redirected to a local fallback
(`/tmp/diwall/operations.fallback.jsonl`, permissions 700/600) instead of
being written in clear text on the raw host directory, and proof archiving is
skipped entirely rather than duplicating authenticated screenshots outside
the encrypted directory. Note: the fallback location is not encrypted either — it is a
lesser evil (already the existing degraded-write behavior on any journal
failure), not a substitute for a mounted encrypted directory.

**Still your responsibility — writing new credential files:**
The internal guard above only covers Diwall's own journal/proof writes. If
you construct or update a *credential file* yourself (e.g., via a shell
command or `evaluer` outside Diwall's `depuis_secrets` mechanism), the same
risk applies and is not automatically caught: the encrypted directory, if
unmounted, exists on disk but is empty and unencrypted. Before creating or
updating a credential file, confirm it is mounted — the directory
must be non-empty. If in doubt, stop and ask the operator to verify — never
write credentials assuming it is open.

---

## `--secrets` — specifying a non-default credentials file

When a scenario needs credentials from a file other than the default:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --secrets ~/Vaults/Diwall/other-project/creds.json
```

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --secrets ~/Vaults/Diwall/other-project/creds.json
```

**`origines_autorisees` — mandatory since 05/08/2026 (breaking change, no
compatibility period):** every `--secrets` file must declare which hostnames
it may be used against, or it is refused before any read:

```json
{"username": "u", "password": "p", "origines_autorisees": ["target.local"]}
```

Without `--secrets`, a credential is bound to the domain actually loaded in
the browser (`domaine_depuis_url(page.url)`) — a redirection to another
domain fails resolution. `--secrets` reads a designated file regardless of
origin unless `origines_autorisees` is present; a domain outside the list
refuses the read (`SecretsOrigineNonAutoriseeError`), same exit family as a
closed encrypted directory (42).

**Multiple credentials files (v1.10.0):** one `--secrets FILE` per run — not repeatable on the
same command line (`--secrets` is a single value; a second occurrence
silently overrides the first, it does not accumulate). "Multiple files" means
across runs: an operator with several tenants/projects each keeps their own
credentials file, and each run picks the right one explicitly via `--secrets`,
instead of relying on automatic per-hostname resolution. **The filename is
whatever the operator chose — never assume it matches the target's
hostname** (e.g. a file named `client-a.json` can hold credentials for
`app.client-a.example`); `ls` the credentials directory or ask rather than guess.

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
  --sauver-session /tmp/diwall/session.json \
  --som

# Subsequent calls — reuse session
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/dashboard \
  --reprendre-session /tmp/diwall/session.json \
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
  "url_courante": "https://target.local/login",
  "dernier_code_http": 302
}
```

If `session_derive` is true: run the full login flow again without `--reprendre-session`.

**`dernier_code_http` (v1.22.0), always present, disambiguates the cause:** a
real expired session and a masked server-side error (e.g. `display_errors=0`
hiding a 500) both redirect to the same login page — `session_derive: true`
looks identical either way. Compare `dernier_code_http`: `302`/`200` on the
redirect points to a real session expiry, `500`/`4xx` points to an
application error, not your session. **Nuance:** on a run with several
`naviguer` actions, this reflects the *last* navigation only — not
necessarily the one that explains the drift if more than one navigation
happened in the same run.

---

## Checkpoints for long scenarios (`rpa.py --checkpoint`, v1.17.0)

A checkpoint is **session state + action-list position** — never a DOM
snapshot. Open modals, half-filled fields, unsubmitted forms are never
preserved between two invocations (same constraint as `--reprendre-session`
above). Only a boundary between two fully-completed actions is a valid
resume point.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario long_scenario.json --checkpoint /tmp/mon_run.checkpoint.json
```

- First run: executes from action 0. On mid-scenario failure, writes
  `/tmp/mon_run.checkpoint.json` with `{"actions_completees": N, "session_file": ...}`
  and preserves the browser session (cookies/`localStorage`) as of the
  failure point.
- **Relaunch the exact same command** to resume: already-completed actions
  are skipped, the run continues from the saved session's URL.
- On full success (remaining actions complete): the checkpoint file is
  deleted automatically — nothing left to resume.
- On a failure with no recoverable progress (e.g. encrypted directory closed before any
  action ran): the checkpoint file is left untouched — retry is identical
  to before.
- **Navigation cap reached (fixed in v1.17.2):** if the run stops because
  `max_actions_par_run`/`max_pages_par_run` was hit, it returns `succes: true`
  like a genuinely completed tronçon — before v1.17.2 the checkpoint was
  deleted in this case too, silently losing the remaining progress on long
  scenarios. It is now updated with the run's actual progress, same as a
  partial failure — relaunch the same command to continue.

**Not a substitute for `--sauver-session`/`--reprendre-session` used directly**
— checkpoints are the right tool specifically for *long, single-scenario* runs
where a late failure would otherwise mean replaying everything from action 0.

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

The action polls the ntfy topic for a 4-to-8-digit code (non-matching
messages are ignored), then fills the input field and submits. It does NOT
read the credentials file — the code is pushed live by the authenticator.

**Production deployments:** the default `https://ntfy.sh` is a public
service with no end-to-end encryption. Point `DIWALL_NTFY_URL` at a private
ntfy instance outside of demonstration use.

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
| Credential fill | `valeur: "depuis_secrets"` + `secret_cle` — never shell |
| Non-default credentials file | `--secrets /path/to/creds.json` |
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

## `--http-credentials` — HTTP Basic Auth (v1.21.0)

Diwall's credential resolution handles web **form** authentication (`remplir_som` +
`depuis_secrets`). It does not, on its own, answer a browser-level HTTP Basic
Auth challenge (RFC 7617) — the kind a reverse proxy (Caddy, nginx, Traefik)
raises before any page renders. `--http-credentials` closes that specific
gap. It does **not** mean form-based authentication is unsupported — the
two are unrelated mechanisms, and conflating them is a documented mistake
to avoid (see the non-presumption rule in `docs/GUIDE_LLM.md`).

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://internal.example/ \
  --http-credentials
```

Or via `rpa.py` (propagated automatically), or as a scenario root property
`"http_credentials": true` — combinable with the CLI flag, same pattern as
`shadow_dom`.

**Credential keys:** `http_username`/`http_password` tried first (needed only if
the same target also has a separate application-level login behind the
Basic Auth wall, e.g. a reverse proxy in front of its own login form — two
different credential pairs in the same file). If absent, Diwall falls back
to the plain `username`/`password` keys — the common case, confirmed
against a real Caddy-protected target (v1.21.0): most credentials files already
have exactly this pair for a single-credential target, no renaming needed.
Resolved from the same file already in scope for the run (`--secrets` if
passed, otherwise the default file by hostname). Never passed on the
command line.

**Security — non-negotiable:** identifiers are scoped to the target's
origin (`scheme://host:port`) and sent only after a real 401
(`send: "unauthorized"`). This is not configurable per-run — it protects
against Diwall sending credentials to a third-party origin (CDN, tracker,
redirect) loaded inside the same browser context.

**Confirmed against a real target (v1.21.0):** `send: "unauthorized"`
resolved a real Caddy-protected admin interface on the first attempt — the
safe default is not just theoretical.

**When it may still fail:** if a target never issues a clean 401 (some
reverse proxies expect credentials preemptively), `--http-credentials` will
not resolve the challenge — a known limit of the safe default, not
exercised against a real target yet, and currently not switchable at
runtime (`send: "always"` would need a source change, no CLI flag exists
for it). `boussole.http_auth_requise: true` confirms a 401 was actually
hit; `boussole.http_credentials_actif: true` confirms the challenge was
actually resolved (never just that the flag was passed — same discipline
as `stealth_actif`, v1.16.0).

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
