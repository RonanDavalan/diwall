# v1.20.0 validation — items 1-2 (journal.py --erreurs, latences_actions)

Live evidence for the two code items of v1.20.0: the `journal.py --erreurs`
filter, and `latences_actions` per-action timing in `shot.py`.

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.20.0_validation/verifier.py
```

- **T-1** — `journal.py --erreurs`: two synthetic journal entries (one
  `resultat: "succes"`, one `resultat: "echec"`) written to an isolated
  `DIWALL_JOURNAL`. Without `--erreurs`, both entries are read back. With
  `--erreurs`, only the failed entry survives.
- **T-2** — `latences_actions` is always present in `shot.py`'s output, even
  as an empty list when no actions were passed (`--no-capture`, no
  `--actions`).
- **T-3** — end-to-end against `example.com`: two `evaluer` actions produce
  two `latences_actions` entries, indices `0`/`1` matching action order,
  `type` reflecting each action's verb, `latence_ms` a non-negative integer.

Item 3 of the v1.20.0 plan (real `.deb` upgrade test, 1.19.0 → 1.20.0) is not
a unit/integration test — it is a manual procedure run once against the live
development/production installation, documented in `PROTOCOLE_CLOTURE.md`
instruction n°1bis (private `_CADRE/`) and reported in the session's
ADDENDUM.

**Non-regression note:** this suite requires `--guide-version 4.1` (bumped
from 3.7 in this cycle) or a valid local marker. Reseed before running any
pre-existing suite:

```bash
/opt/diwall/venv/bin/python3 shot.py --url https://example.com --no-capture --guide-version 4.1
```
