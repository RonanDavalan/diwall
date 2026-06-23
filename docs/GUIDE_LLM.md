# Diwall — LLM Guide (index)

Version 3.1 — June 2026 (v1.12.0) — error routing table added

**You are a language model. This is the entry point. Read it fully, then load
the notice that matches your task.**

---

## Security — non-negotiable (read this before anything else)

**FORBIDDEN — extracts credentials into the shell:**
```bash
PASS=$(jq -r '.password' ~/Vaults/.../file.json)   # NEVER
```

**CORRECT — vault resolved inside Playwright:**
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_vault", "vault_cle": "username"}
{"type": "remplir_som", "id": 3, "valeur": "depuis_vault", "vault_cle": "password"}
```

Values never appear in shell, bash history, or any log.
Also forbidden: using `curl`, `wget`, or any HTTP client for authentication.

---

## What Diwall does

Diwall gives you **eyes and hands on web interfaces** via a local Playwright process.

```
shot.py → returns JSON with PNG path → you read the PNG → you analyse → you loop
```

You do not guess the rendering. You do not use `lynx`. You SEE it.

---

## Installation paths

```
/opt/diwall/          ← production (always invoke from here)
  shot.py             ← main capture + action executor
  rpa.py              ← declarative scenario runner
  watch.py            ← visual drift monitoring
  journal.py          ← operation log reader
  lib/vault.py        ← credential resolver (inside Playwright only)
  venv/               ← isolated Python — ALWAYS use this venv
  scenarios/          ← RPA scenario files (JSON/YAML)
  references/         ← watch.py visual references

~/git/Diwall/Diwall/  ← source (modify here, then deploy.sh)
/var/log/diwall/      ← persistent operation log
/tmp/diwall/          ← temporary PNG captures (cleared on reboot)
```

Canonical invocation:
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <url>
```

Deploy after source changes:
```bash
bash ~/git/Diwall/Diwall/scripts/deploy.sh
```

---

## Modes at a glance

**Mode A — interactive, single shot.py call:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --a11y
```
Returns JSON with `capture_som`, `elements_som`, `a11y_tree`, `boussole`.
Pass `--actions /tmp/actions.json` to execute actions in the same browser session.
Pass `--reprendre-session` to reuse a previous session (cookies only — not DOM state).

**Mode RPA — declarative, rpa.py:**
```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json
```
stdout: one JSON line (v1.11.0). Use `--secrets` for non-default vault.

**Shell escaping rule:** for `--action` containing JS quotes, always use
`--actions /tmp/file.json` — inline JSON is corrupted silently by the shell.

---

## Action verbs — quick reference

| Verb | Key params | Notes |
|---|---|---|
| `naviguer` | `url` | Full HTTP reload — avoid in SPAs |
| `cliquer` | `selecteur`, [`force`] | `force: true` bypasses CSS-hidden / showModal (v1.11.0) |
| `cliquer_som` | `id` | Coordinate click — bypasses interactability natively, no `force` needed |
| `cliquer_visuel` | `description` | LLM vision fallback (~32s) |
| `remplir` | `selecteur`, `valeur` | `valeur` can be `"depuis_vault"` |
| `remplir_som` | `id`, `valeur`, [`vault_cle`] | Clears field before typing (v1.9.6+) |
| `capturer` | `nom` | Named intermediate PNG |
| `evaluer` | `script`, [`attendu`\|`contient`\|`motif`] | JS evaluate; assertion keys are rpa.py-only (v1.11.0) |
| `defiler` | `px` or `selecteur` | Scroll viewport |
| `pause` | `ms`, [`interval_capture`] | Fixed delay — prefer `attendre_selecteur_present` for DOM signals |
| `attendre` | `selecteur` | Wait for CSS selector |
| `attendre_navigation` | — | Wait for network idle |
| `attendre_url` | `motif` | URL contains motif (partial match, v1.8.0) |
| `attendre_selecteur_present` | `selecteur` | Wait for visible element |
| `attendre_absence` | `selecteur`, [`delai_initial_ms`] | Wait for element removal |
| `attendre_reseau_calme` | [`timeout_ms`] | 500ms network silence |
| `attendre_mfa_ntfy` | `id_som`, [`timeout`] | Wait for TOTP via ntfy |
| `nettoyer_overlay` | `selecteur` | Hide fixed overlays before SoM |
| `declencher_scenario` | `scenario` | Inline a sub-scenario (max depth 5) |

---

## Boussole JSON — orientation at a glance

Every shot.py and rpa.py output includes a `boussole` object. Read it first:

```json
"boussole": {
  "url_courante": "https://target.local/dashboard",
  "titre_page": "Dashboard — My App",
  "session_derive": false,
  "auth_status": "active",
  "som_hors_viewport": 0
}
```

If `boussole` does not match your expectation: stop and investigate before any mutating action.

---

## Error routing — load by symptom

Already in an error? Route by symptom, not by task type:

| Symptom | Notice |
|---|---|
| `TimeoutError` on `cliquer`, `cliquer_som`, `remplir`, `remplir_som` | `GUIDE_LLM_INTERACTIONS.md` |
| `showModal()` / CSS-hidden element / `force: true` questions | `GUIDE_LLM_INTERACTIONS.md` |
| Strict mode violation, `:nth-match()`, DOM locator error | `GUIDE_LLM_INTERACTIONS.md` |
| SoM ID mismatch, element numbered but not clickable | `GUIDE_LLM_INTERACTIONS.md` |
| `evaluer` assertion failed (`attendu` / `contient` / `motif`) | `GUIDE_LLM_INTERACTIONS.md` |
| `exit 42` (VaultFermeError) — vault not mounted | `GUIDE_LLM_SESSIONS.md` |
| `exit 43` (VaultNonConfigureError) — `diwall.conf` absent | `GUIDE_LLM_SESSIONS.md` |
| `--secrets` file, multi-vault, credential resolution | `GUIDE_LLM_SESSIONS.md` |
| `--reprendre-session` issues, SPA navigation, auth expiry | `GUIDE_LLM_SESSIONS.md` |
| `TimeoutError` on `page.screenshot()`, capture hangs | `GUIDE_LLM_MONITORING.md` |
| `watch.py` pixel diff, verdicts, `--screenshot-timeout` | `GUIDE_LLM_MONITORING.md` |
| Long-running operations, `interval_capture`, journal.py | `GUIDE_LLM_MONITORING.md` |

---

## Notice index — load on demand

| Notice | Load when | Version |
|---|---|---|
| `GUIDE_LLM_INTERACTIONS.md` | Timeout on `cliquer`, CSS/showModal dialog, SoM IDs, strict mode violation, nth-match error, evaluer assertions, DOM mutations | v1.1 |
| `GUIDE_LLM_SESSIONS.md` | Vault credentials, `--secrets`, session persistence, SPA navigation, multi-page flows, MFA/TOTP, auth_indicator, --no-capture | v1.1 |
| `GUIDE_LLM_MONITORING.md` | watch.py, pixel diff, long-running operations, `--screenshot-timeout`, interval_capture, journal.py | v1.1 |

> **Version check:** the version column is canonical. If your local copy of a notice shows
> a lower version, reload it. Notice versions increment independently of Diwall releases.

```bash
cat /opt/diwall/docs/GUIDE_LLM_INTERACTIONS.md
cat /opt/diwall/docs/GUIDE_LLM_SESSIONS.md
cat /opt/diwall/docs/GUIDE_LLM_MONITORING.md
```

If in doubt about which notice: load INTERACTIONS first (covers the most frequent errors).

---

## Stop-and-Search rule — bloquant

If an action returns `succes: false` or a Playwright error, you must:

1. Query the local RAG: `search-index.py <error keywords>`
2. Re-read the relevant notice section
3. Declare: cause identified, rule violated
4. Propose the correction — then stop until validated

**No `actions_v2.json` / `_v3.json` in `/tmp/` without this step.**

---

## Reconnaissance before mutation — bloquant

Before writing any mutating action on a feature never previously tested with Diwall:

```bash
# Step 1 — Visual map + DOM inventory
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <target_url> --som --a11y

# Step 2 — Extract selectors from evaluer results
# Step 3 — Write the complete scenario in one pass
# Step 4 — Execute once via rpa.py
```

Forbidden: launching a mutating action without completing steps 1–2.

---

## `--screenshot-timeout` — v1.11.0 key parameter

Default timeout for `page.screenshot()` is now 120 000 ms (120 s), configurable:

```bash
--screenshot-timeout 180000   # 3 minutes for heavy dashboards
```

Distinct from `--timeout` (Playwright action timeouts). Propagated to all screenshot
calls. If all else fails: add `--no-capture` and rely on `a11y_tree` + `evaluer`.

---

## Operator group

Diwall files are owned by group `diwall`. If you run as a service account:

```bash
sudo usermod -aG diwall <account>
sg diwall -c "/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …"
```
