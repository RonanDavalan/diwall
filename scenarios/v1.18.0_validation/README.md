# v1.18.0 validation — items 1-5

Live evidence for the guide-read lock, `mode_conseille`, `iframe_chemin`,
the interoperability fixtures, and `monitor-verifier.sh`.

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.18.0_validation/verifier.py
```

- **T-1** — `--version` on the three scripts: exit 0, `{outil, version}`
  JSON, no Playwright launch (item 1).
- **T-2** — `--guide-version` gate: refused without token or marker, refused
  with a wrong token, accepted with the correct token (writes the marker
  under an isolated `$HOME`), accepted on the next call without the flag
  (marker reuse) (item 1).
- **T-3** — `iframe_chemin`: schema accepts it alone, rejects it combined
  with `iframe_selecteur` or with neither present; a real click descends
  through two nested iframes on the local fixture (items 2 and 4).
- **T-4** — `mode_conseille`: absent for a host never diagnosed, absent for a
  diagnosed host with no framework/Shadow DOM signal, present with the
  correct `shadow_dom`/`som_rafraichir` recommendation for a host with a
  detected framework and shadow roots (item 3).
- **T-5** — `monitor-verifier.sh`: one pass, silent exit 0 on a stable
  target, exit 1 with a verdict on stderr on a forced regression (item 5).

**Non-regression note (item 1):** this gate is the one deliberate exception
to Diwall's additive-only doctrine — see `V1_18_0_AUTONOMIE_ET_ROBUSTESSE.md`.
Any subprocess call to `shot.py`/`rpa.py`/`watch.py` in the pre-existing
validation suites (`v1.15.2_validation`, `v1.16.0_validation`,
`v1.17.0_validation`, `v1.17.2_validation`) now requires either
`--guide-version 3.7` or a valid local marker
(`~/.config/diwall/guide_state.json`) for the OS user running the suite —
seed it once before running any of them:

```bash
/opt/diwall/venv/bin/python3 shot.py --url https://example.com --no-capture --guide-version 3.7
```
