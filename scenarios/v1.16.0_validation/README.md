# v1.16.0 validation — items A-F

Live and unit evidence for the boussole/identity/friction-signal items shipped
in v1.16.0. Live tests target `https://example.com` only (same public fixture
as `scripts/preflight-publication.sh`).

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.16.0_validation/verifier.py
```

- **T-B1** — `operation_id` present, 12 hex chars (item B).
- **T-A1/T-A2** — `etat` deterministic verdict, nominal and degraded on
  inactive auth (item A).
- **T-C1** — `_detecter_waf()` unit tests: 403/429/keyword/clean (item C,
  pure function, no network dependency — avoids relying on an unreliable
  external WAF target).
- **T-D1** — `console.error(...)` captured in `erreurs_console`, distinct
  from `erreurs_js` (item D).
- **T-E1** — `citoyennete.indice_agressivite` computed correctly on a mixed
  read/write action sequence (item E).
- **T-F1** — `--stealth` genuinely masks `navigator.webdriver` and
  `boussole.stealth_actif` only reflects real application (FR-79 fix,
  discovered while executing item F).
