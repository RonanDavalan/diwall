# v1.15.2 validation — item 6 (Q2, GL2)

Live evidence that two behaviors audited by the June multi-model campaign were
already correct before v1.15.2 — no code change, only proof.

Targets `https://example.com` only (same public fixture used by
`scripts/preflight-publication.sh` smoke tests).

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.15.2_validation/verifier.py
```

## Q2 — `--no-evaluer` is surgical

`--no-evaluer` blocks only the scenario-level `evaluer` action type. It must
never block `shot.py`'s own internal `page.evaluate()` calls (secret masking,
`dom_stats`, SoM injection/count) — confusing the two would make the runtime
inoperable as soon as the flag is active.

- **T-Q2-A** — a scenario with an `evaluer` action, run with `--no-evaluer`:
  exit 1, `succes: false`, message mentions `--no-evaluer`.
- **T-Q2-B** — a scenario with **no** `evaluer` action, run with
  `--no-evaluer --som`: exit 0, `succes: true`, `capture_som` and
  `elements_som` present — proving SoM's internal `page.evaluate()` calls were
  untouched by the flag.

## GL2 — auth negative assertion

`auth_status` is `"active"` only if the positive marker (`--auth-indicator`)
is visible **and** the negative marker (`--auth-indicator-negative`) is not.

- **T-GL2-A** — `--auth-indicator h1 --auth-indicator-negative div` against
  `example.com` (both `h1` and the wrapping `div` are visible) → `inactive`.
- **T-GL2-B** — `--auth-indicator h1 --auth-indicator-negative .selecteur-inexistant-xyz`
  (negative selector matches nothing) → `active`.
