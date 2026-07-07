# v1.19.0 validation — items 1-2 (mode_conseille filter, chainage)

Live evidence for the two code items of v1.19.0: `mode_conseille` filtered to
successful diagnostics, and `chainage` traceability for `declencher_scenario`.

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.19.0_validation/verifier.py
```

- **T-1** — `mode_conseille` success filter: a diagnostic entry with
  `resultat: "echec"` but non-empty `evaluations` (a run that returned
  partial results before failing) is the most recent entry for its host, yet
  must never be picked up — only the older `resultat: "succes"` entry is.
  A host whose only diagnostic entry failed gets `None`, never a guess.
- **T-2** — `_aplatir_actions()` unit-level: a two-level nested
  `declencher_scenario` produces the expected flattened action count and two
  `chainage` entries with correctly offset `action_debut`/`action_fin`
  indices; a scenario without chaining returns an empty `chainage` list.
- **T-3** — end-to-end: `rpa.py` on a real chained scenario (against
  `example.com`) writes a `chainage` field to the journal with both the root
  (`profondeur: 0`) and the sub-scenario (`profondeur: 1`) entries; root
  `journal.py --limite 1` renders the indented tree.

**Non-regression note:** this suite requires `--guide-version 3.7` (bumped
from 3.6 in this cycle) or a valid local marker. Reseed before running any
pre-existing suite:

```bash
/opt/diwall/venv/bin/python3 shot.py --url https://example.com --no-capture --guide-version 3.7
```
