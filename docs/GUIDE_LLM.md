# Diwall — LLM Guide (index)

<!-- notice-version: 4.1 -->
Version 4.1 — July 2026 (v1.22.0) — **breaking: the `citoyennete` output key is now `respect`** (sub-keys unchanged);
`--wait-until` for never-idle targets; `repli_js` (JS click escalation), `dernier_code_http` in boussole.

**You are a language model. This is the entry point. Read it fully, then load
the notice that matches your task.**

> **Need a command right now?** Load `docs/MANUEL.md` — exact commands, real
> paths, real values. This guide handles routing and security rules only.
> `cat /opt/diwall/docs/MANUEL.md`

## Non-presumption rule — non-negotiable (v1.21.0)

Never affirm a Diwall capability does not exist, and never presume one does,
without checking first — grep the action tables below/in the notices, or run
`--help`. Unsure? Say "not confirmed in the documentation," never a guess
either way. (A model once claimed Diwall couldn't fill an auth form — false,
see Security below.)

---

## Mandatory pre-flight — `--guide-version` (v1.18.0+)

`shot.py`/`rpa.py`/`watch.py` refuse to run without proof you read this file
— the only exception to Diwall's opt-in design. Token: line 3
(`<!-- notice-version: X.Y -->`), same convention as the three notices.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <url> --guide-version 4.1
```

Accepted once → a local marker (`~/.config/diwall/guide_state.json`) is
written, not asked again on this machine/user until `notice-version`
changes. Quick check without Playwright: `shot.py --version` (Diwall
release — a different number from `--guide-version`, don't confuse them).

No marker + skipped → `exit 1`, `erreur: "guide_non_lu"`, stderr. No bypass.

**Known limit:** this lock is cooperative by nature — a model already
holding a token from a prior context can pass it without rereading current
content. Diwall accepts this deliberately: a content-tied challenge would
complicate a mechanism meant to stay lightweight, and a model willing to
fabricate a token would defeat a stronger check just as easily. The lock
makes skipping the guide a deliberate act, not an accident — not a
guarantee against lying about it.

---

## Security — non-negotiable (read before anything else)

**FORBIDDEN — extracts credentials into the shell:**
```bash
PASS=$(jq -r '.password' ~/Secrets/.../file.json)   # NEVER
```

**CORRECT — vault resolved inside Playwright** (this is Diwall's core
authentication mechanism — form-filling with real credentials, always
supported):
```json
{"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "username"}
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Values never appear in shell, bash history, or any log. Also forbidden:
`curl`, `wget`, or any HTTP client for authentication.

---

## What Diwall does

Diwall gives you **eyes and hands on web interfaces** via a local Playwright
process: `shot.py → JSON with PNG path → you read it → you analyse → you
loop`. You do not guess the rendering, you do not use `lynx`. You SEE it.

---

## Installation paths

```
/opt/diwall/          ← production (always invoke from here)
  shot.py rpa.py watch.py journal.py   ← main tools
  lib/repertoire_chiffre.py         ← credential resolver (inside Playwright only)
  venv/                ← isolated Python — ALWAYS use this venv
  scenarios/ references/

~/git/Diwall/Diwall/  ← source (modify here, then deploy.sh)
/var/log/diwall/      ← persistent operation log
/tmp/diwall/          ← temporary PNG captures (cleared on reboot)
```

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <url>
bash ~/git/Diwall/Diwall/scripts/deploy.sh   # after source changes
```

---

## Modes and capture — quick reference

**Mode A (`shot.py`):** `--url ... --som --a11y` → JSON with `capture_som`,
`elements_som`, `a11y_tree`, `boussole`. `--actions FILE` executes actions in
the same session. `--reprendre-session` reuses cookies only, never DOM state.

**Mode RPA (`rpa.py`):** `--scenario FILE` → one JSON line on stdout.
`--secrets FILE` for a non-default vault.

**Shell escaping:** for `--action` with JS quotes, always use
`--actions /tmp/file.json` — inline JSON is silently corrupted by the shell.

| Goal | Command |
|---|---|
| Check auth state | `--mode fast --auth-indicator <sel>` |
| Read DOM / extract JS data | `--mode fast` + `evaluer` |
| Observe visual rendering | default (`--mode full`) |
| Number and click elements | `--som` |
| Detect visual regression | `watch.py --comparer-pixel` |
| Test Web Components | `--som --shadow-dom` |
| Reach a target that never goes network-silent | `--wait-until load` (shot.py + rpa.py, v1.22.0) |

`--mode fast` = `--no-capture --a11y` (~2s faster, no PNG). `--som` is
opt-in with either mode.

---

## Action verbs — quick reference

| Verb | Key params | Notes |
|---|---|---|
| `naviguer` | `url` | Full HTTP reload — avoid in SPAs |
| `cliquer` | `selecteur`, [`force`\|`repli_js`] | `force` bypasses CSS-hidden/showModal; `repli_js` retries via JS if the native click still fails (needs `--no-evaluer` off) |
| `cliquer_som` | `id` | Coordinate click — no `force` needed |
| `cliquer_visuel` | `description` | LLM vision fallback (~32s) |
| `remplir` | `selecteur`, `valeur` | `valeur` can be `"depuis_secrets"` |
| `remplir_som` | `id`, `valeur`, [`secret_cle`] | Clears field before typing |
| `capturer` | `nom` | Named intermediate PNG |
| `evaluer` | `script`, [`attendu`\|`contient`\|`motif`] | Assertion keys are rpa.py-only |
| `defiler` | `px` or `selecteur` | Scroll viewport |
| `pause` | `ms`, [`interval_capture`] | Prefer `attendre_selecteur_present` for DOM signals |
| `attendre` / `attendre_navigation` | `selecteur` / — | Wait for selector / network idle |
| `attendre_url` | `motif` | Partial match — see `GUIDE_LLM_INTERACTIONS.md` pitfall |
| `attendre_selecteur_present` / `attendre_absence` | `selecteur` | Wait for appear/removal |
| `attendre_reseau_calme` | [`timeout_ms`] | 500ms network silence |
| `attendre_mfa_ntfy` | `id_som`, [`timeout`] | Wait for TOTP via ntfy |
| `nettoyer_overlay` | `selecteur` | Hide fixed overlays before SoM |
| `declencher_scenario` | `scenario` | Inline a sub-scenario (max depth 5) |
| `cliquer_iframe` / `remplir_iframe` | `iframe_selecteur`\|`iframe_chemin`, `selecteur`, [`valeur`] | Cross-origin iframe; `iframe_chemin` array for nested |

---

## Boussole JSON — orientation at a glance

Every output includes a `boussole` object — read it first:

```json
"boussole": {
  "utilisateur": "operator", "ip_locale": "__IP_LAN__", "repertoire": "/opt/diwall",
  "url_courante": "https://target.local/dashboard", "titre_page": "Dashboard",
  "auth_status": "active", "som_hors_viewport": 3, "dernier_code_http": 200
}
```

Conditional keys (absent when inactive): `session_derive` (`--reprendre-session` URL drift), `auth_status` (`--auth-indicator`), `som_hors_viewport` (>0),
`shadow_dom_actif`, `stealth_actif`, `repli_js_utilise` (v1.22.0, real JS escalade only, never just the flag), `wait_until` (v1.22.0, only when it differs from the default), `http_credentials_actif`/`http_auth_requise`
— each conditioned on real effect, never just the CLI flag being passed (precedent: `stealth_actif` bug fixed v1.16.0).
Always present (unlike the above): `dernier_code_http` (v1.22.0) — last navigation's HTTP status; ambiguous across multi-navigation runs, see
`GUIDE_LLM_SESSIONS.md` for the nuance.

`etat.mode_conseille` — present only with real prior data for this host,
never a guess. Full detail: `GUIDE_LLM_MONITORING.md`.

If `boussole` does not match your expectation: stop and investigate before any mutating action.

**`etat` is declarative, never a gate:** `pret_a_agir`/`niveau_confiance`/
`raisons` are a report, not a control — no dispatcher checks them before
running. `pret_a_agir: false` means a friction was perceived (WAF, JS errors,
navigation cap, session drift) worth your attention, not a refusal. Read
`raisons`, decide on the actual friction — the decision is always yours.

---

## Error routing — load by symptom

| Symptom | Notice |
|---|---|
| Timeout on click/fill, `showModal()`, strict mode, SoM mismatch, Shadow DOM, `evaluer` assertion | `GUIDE_LLM_INTERACTIONS.md` |
| Initial navigation times out despite a generous `--timeout` (live-stats/polling target) → `--wait-until load` | `GUIDE_LLM_INTERACTIONS.md` |
| `exit 42`/`43` (vault), `--secrets`, `--http-credentials`, `--reprendre-session`, SPA nav, auth expiry | `GUIDE_LLM_SESSIONS.md` |
| Screenshot timeout, `watch.py` diff, long operations, `journal.py` | `GUIDE_LLM_MONITORING.md` |

## Notice index — load on demand

| Notice | Load when | Version |
|---|---|---|
| `GUIDE_LLM_INTERACTIONS.md` | Interaction/DOM errors, `--wait-until`, Shadow DOM, iframes | v1.10 |
| `GUIDE_LLM_SESSIONS.md` | Vault, `--secrets`, `--http-credentials`, sessions, SPA, MFA, `--checkpoint` | v1.10 |
| `GUIDE_LLM_MONITORING.md` | `watch.py`, pixel diff, `--replay-verifier`, `mode_conseille`, journal | v1.11 |

> Version column is canonical — reload a notice if your copy shows lower. If in doubt: load INTERACTIONS first (most frequent errors).

---

## Stop-and-Search rule — bloquant

On `succes: false` or a Playwright error: (1) query the RAG
(`search-index.py <keywords>`), (2) re-read the relevant notice, (3) declare
cause + rule violated, (4) propose the correction, then stop until validated.
No `actions_v2.json`/`_v3.json` in `/tmp/` without this step.

## Reconnaissance before mutation — bloquant

Before any mutating action on a feature never tested with Diwall:
`shot.py --url <target> --som --a11y` first, extract selectors, write the
complete scenario in one pass, execute once via `rpa.py`. Forbidden:
mutating before completing the map.

---

## WAF and Cloudflare blocking — Respectful Navigation

`--stealth` (v1.15.0) is the first response — removes `navigator.webdriver`,
normalises plugins/languages/platform. **Not** covered: TLS fingerprinting
(JA3/JA4), Cloudflare Enterprise behavioural analysis — persistent 403 means
deep fingerprinting. Field data: `docs/RETOUR_EXPERIENCE.md` FR-77/FR-78,
doctrine: `LEGITIMITE_ETRE_LLM.md`.

**Passive detection — `respect.waf_bloquants`:** flagged on every
navigation (403/429, or a title/HTML keyword match) — a **signal, never an
exception**, Diwall does not abort or moralize about access. Heuristic
(keyword match): a false positive is possible on a page that legitimately
mentions one of these terms — verify before concluding a real block.
Generic vendor names (`cloudflare`, `akamai`) match only the page title, not
full HTML (v1.17.2 — avoids false positives on ordinary CDN resources).

**Overrule — `--ignorer-waf`:** only after an independent, non-mutating
check (`--mode fast` + `evaluer`, or a prior `diagnostic_dom.json`) confirms
the page is usable. Degrades `niveau_confiance` but no longer forces
`pret_a_agir: false`; `boussole.waf_ignore_actif: true` keeps it auditable.
Never a first response, never wired automatically into a scenario.

---

## `--screenshot-timeout` and operator group

Default `page.screenshot()` timeout is 120 000 ms, configurable
(`--screenshot-timeout 180000` for heavy dashboards), distinct from
`--timeout`. If all else fails: `--no-capture` + `a11y_tree` + `evaluer`.
Diwall files are owned by group `diwall` — service accounts:
`sudo usermod -aG diwall <account>`, detail in `docs/MANUEL.md`.
