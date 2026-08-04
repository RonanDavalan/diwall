# v1.21.0 validation — `--http-credentials` (HTTP Basic Auth)

Live evidence for Axe A of v1.21.0: `--http-credentials` resolves an HTTP
Basic Auth challenge (RFC 7617) from the credentials file, scoped to the target's
origin, without ever letting the boussole claim a success it did not
verify.

```bash
/opt/diwall/venv/bin/python3 scenarios/v1.21.0_validation/verifier.py
```

Starts and stops its own fixture server (`scenarios/interoperabilite/fixture/serveur_basicauth.py`)
— no external network dependency, deterministic.

- **T-1** — without `--http-credentials`: `http_status: 401`,
  `boussole.http_auth_requise: true`, and `http_credentials_actif` never
  appears. Fully portable, no credentials required.
- **T-2** — with `--http-credentials` and correct fixture credentials: the
  challenge is actually resolved (`http_status: 200`), and
  `boussole.http_credentials_actif: true` reflects that real success —
  requires a mounted gocryptfs volume (skipped otherwise, not failed).
- **T-3** — with `--http-credentials` but a wrong password: still 401.
  `http_credentials_actif` stays absent even though the flag was passed —
  same discipline as `stealth_actif` (bug fixed v1.16.0/FR-79): a boussole
  key never reflects intent, only verified effect.

T-2 and T-3 require a mounted gocryptfs volume (any project's, auto-detected
via `/proc/mounts`, fstype `fuse.gocryptfs`) — `/tmp` does not qualify:
`lib.repertoire_chiffre._repertoire_est_monte()` restricts T1 to FUSE mounts specifically,
tmpfs is rejected despite being mentioned in the error message (found while
writing this suite, 15/07/2026).
