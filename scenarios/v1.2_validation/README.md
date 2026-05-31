# v1.2 validation scenarios

Reproducible test cases that exercise the three v1.2 lots
(8.5 session drift, 9.2 JSON schema, 9.1 pixel diff). Mirrors
`_CADRE/SPECIFICATIONS/SCENARIOS_TEST.md` section 3 (private spec).

All scenarios target public sites only (`example.com`, `iana.org`).

## Lot 8.5 — session drift signal

The two action arrays are intended as inline `--actions` for the
second `shot.py` invocation after a `--sauver-session` step.

```bash
# Step 1 — save a session on example.com
/opt/diwall/shot.py --url https://example.com \
                    --sauver-session /tmp/sess.json

# Step 2a — resume on the same URL (no derive_session expected)
/opt/diwall/shot.py --url https://example.com \
                    --reprendre-session /tmp/sess.json \
                    --actions "$(cat test_8_5_a_session_propre.json)"

# Step 2b — resume on a different URL (derive_session expected)
/opt/diwall/shot.py --url https://www.iana.org/domains/example \
                    --reprendre-session /tmp/sess.json \
                    --actions "$(cat test_8_5_b_derive_url.json)"
```

Expected: step 2a returns a JSON without `derive_session`. Step 2b
returns a JSON containing `derive_session.url_sauvegardee` /
`url_reprise`, and `rpa.py` would print the warning on stderr.

## Lot 9.2 — JSON schema validation

```bash
/opt/diwall/rpa.py --scenario test_9_2_a_valide.json     # exit 0
/opt/diwall/rpa.py --scenario test_9_2_b_typo_verbe.json # exit 1, schema rejection
/opt/diwall/rpa.py --scenario test_9_2_c_cle_egaree.json # exit 1, additionalProperties
```

Validation requires `jsonschema` in the venv. When the package is
absent, all three scenarios run through with a one-shot warning,
and 9.2.b will silently no-op the unknown verb at execution time —
the exact failure mode the schema is meant to prevent.

## Lot 9.1 — pixel diff

No JSON scenarios for this lot; reference fixtures are PNGs that
should be generated locally (see `_CADRE/SPECIFICATIONS/SCENARIOS_TEST.md`
section 3.3 for the fixture recipe). Drop reference and capture PNGs
into a working directory and run:

```bash
/opt/diwall/watch.py --comparer-pixel ref.png --capture cap.png [--heatmap]
```

Exit codes: 0 (stable/drift), 1 (regression), 2 (viewport_mismatch),
3 (I/O error).
