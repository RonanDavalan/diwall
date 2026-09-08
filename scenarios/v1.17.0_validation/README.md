# v1.17.0 validation — items 1-4 (+ T-5, v1.24.0 hybrid SoM)

Live and unit evidence for the frontier-robustness items. Targets
`https://example.com` and `https://the-internet.herokuapp.com/iframe`
(stable public QA fixture, purpose-built for iframe testing).

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.17.0_validation/verifier.py
```

- **T-1** — `--sauver-verifier-reference` then `--replay-verifier`: verdict
  `stable` on an identical rerun (item 1).
- **T-2** — full checkpoint lifecycle: a 2-action scenario where action #2
  fails, verify the checkpoint file records `actions_completees: 1` and
  survives; a corrected scenario resumed with the same `--checkpoint` flag
  replays only the un-run action (proven via a single `evaluations` entry,
  not two) and deletes the checkpoint file on full success (item 2).
- **T-3** — stable-vs-index identity proof (`_SOM_TROUVER_STABLE_JS`): injects
  a decoy element before the real target in DOM order, shows raw re-indexing
  resolves `id: 1` to the *wrong* element (verified against an independent
  ground-truth query, not stale coordinates), the stable mechanism resolves to
  the *correct* one, and removing the marked element yields an honest `null`
  rather than a wrong-target click (item 3).
- **T-4** — `cliquer_iframe` resolves and clicks inside a same-document
  iframe via `page.frame_locator()`; `indice_agressivite` confirms the new
  action type is correctly classified as a write in `ACTIONS_ECRITURE`
  (item 4).
- **T-5** — hybrid resolver (`_SOM_TROUVER_HYBRIDE_JS`, default since v1.24.0):
  with no SoM capture, resolution falls back to raw re-indexing and reports
  `resolution: brut_sans_reference`, `derive: false`; after an in-page SoM
  capture plus a decoy prepend, `id: 1` resolves via the stable path to the
  correct element and reports `resolution: stable`, `derive: true`. Read-only —
  the resolver never mutates the DOM.
