# v1.17.2 validation — items 1-4

Live and unit evidence for the credential-hardening and reliability items.

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.17.2_validation/verifier.py
```

- **T-1** — write guard: with `DIWALL_SECRETS_DIR` pointing at a plain
  (non-FUSE) temp directory and `DIWALL_JOURNAL` inside it, a run still
  succeeds but writes nothing in clear text under the fake directory — the entry
  lands in the local fallback instead (item 1).
- **T-2** — SoM cleanup: two SoM captures in the same page, where the element
  numbered `1` in the first capture is hidden and a new element takes over
  number `1` in the second. Without the cleanup pass, both the stale and the
  fresh element would carry `data-dw-som-id="1"` simultaneously (item 2).
- **T-3** — WAF heuristic: a page loading an ordinary `cdnjs.cloudflare.com`
  script no longer false-positives; a real challenge page (`cf-error-details`,
  `checking your browser`) and HTTP 403 are still detected. `--ignorer-waf`
  keeps `niveau_confiance` degraded but no longer forces `pret_a_agir: false`
  on its own (item 3).
- **T-4** — checkpoint on navigation cap: a mocked `shot.py` response with
  `succes: true` and `plafond_atteint` set no longer deletes the checkpoint
  file — it's updated with the run's progress instead (item 4, FR-80).
