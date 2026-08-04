# Diwall — cheat sheet

Version 1.23.0 — August 2026

Everything on one page. Full reference: `docs/MANUEL.md`.

---

## Three commands

```bash
# See a page: PNG + numbered elements + accessibility tree
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --som --a11y

# Read without capturing (~2 s faster, no PNG)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --mode fast

# Run a scenario
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario FILE.json
```

Installed from the `.deb`? Use `diwall-shot` and `diwall-rpa` instead of the
full paths. First call on a machine needs `--guide-version X.Y`, read with
`grep notice-version /opt/diwall/docs/GUIDE_LLM.md`.

---

## The loop

```
        you decide what to do next
                  │
                  ▼
   ┌──────────────────────────────┐
   │  shot.py / rpa.py            │   one process, one JSON on stdout
   │    ├─ Chromium (headless)    │
   │    ├─ SoM: numbers elements  │
   │    ├─ A11y: page structure   │
   │    └─ secrets: fills credentials│   never in the shell, never in a log
   └──────────────┬───────────────┘
                  │  PNG + JSON
                  ▼
        you read the same state
        the operator can see too
```

Session state lives in a file, not in the process: a second call with
`--reprendre-session` reuses cookies — never DOM state.

---

## Read the output in this order

| Read | Tells you |
|---|---|
| `succes` | did the run complete |
| `boussole.url_courante` | where you actually ended up |
| `boussole.dernier_code_http` | last navigation status |
| `etat.pret_a_agir` + `etat.raisons` | frictions perceived — a report, never a gate |
| `capture_som` / `elements_som` | what to click, and its number |
| `respect` | your own footprint: pages, actions, duration |

If `boussole` does not match your expectation, stop before any mutating action.

---

## Every action

`type` is always required. Keys below are the additional ones.

| Action | Required | Optional |
|---|---|---|
| `naviguer` | `url` | — |
| `cliquer` | `selecteur` | `force`, `repli_js` |
| `cliquer_som` | `id` | — |
| `cliquer_visuel` | `description` | — |
| `cliquer_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur` | `force` |
| `remplir` | `selecteur`, `valeur` | `secret_cle` |
| `remplir_som` | `id`, `valeur` | `secret_cle` |
| `remplir_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur`, `valeur` | `secret_cle` |
| `capturer` | `nom` | `som` |
| `evaluer` | `script` | `attendu` \| `contient` \| `motif` |
| `defiler` | `px` \| `selecteur` | — |
| `pause` | `ms` | `interval_capture` |
| `attendre` | `selecteur` | `interval_capture` |
| `attendre_selecteur_present` | `selecteur` | — |
| `attendre_absence` | `selecteur` | `delai_initial_ms` |
| `attendre_navigation` | — | — |
| `attendre_url` | `motif` | `attendre_changement` |
| `attendre_reseau_calme` | — | `timeout_ms` |
| `attendre_mfa_ntfy` | `id_som` | `timeout` |
| `nettoyer_overlay` | `selecteur` | — |
| `declencher_scenario` | `scenario` | — |

---

## Credentials — the only correct form

```json
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Never extract a secret into the shell. `lib/repertoire_chiffre.py` resolves it inside the
Playwright process; the value never reaches your command line, your history,
or any log. `depuis_secrets_totp` does the same for a TOTP code.

---

## When something resists

| Symptom | Try |
|---|---|
| Click times out, element visually hidden | `"force": true`, then `"repli_js": true` |
| Element not numbered by SoM | `--shadow-dom` (open Shadow Roots) |
| Element below the fold | `defiler` first — check `boussole.som_hors_viewport` |
| Page never finishes loading | `--wait-until load` |
| Submit does nothing, no error | native HTML validation — submit the form via `evaluer` |
| `exit 42` | encrypted directory not mounted: `diwall-monter-secrets` |
| `exit 43` | no `diwall.conf` — copy the sample next to it |
| `guide_non_lu` | pass `--guide-version` once |
| 403 / 429 | read `respect.waf_bloquants` — a signal, not an exception |

---

## Exit codes

`0` success · `1` Playwright error or failed assertion · `2` viewport mismatch
(`watch.py`) · `3` wrong interpreter, use the venv · `42` encrypted directory closed or bad
checksum · `43` `diwall.conf` missing.
