# v1.3 validation scenarios

Reproducible test cases that exercise the v1.3 lot (operator
profile + model traceability). Mirrors `_CADRE/SPECIFICATIONS/
33_CONFIG_OPERATEUR.md` section 8 (private spec).

All scenarios are pure-Python and run offline — no network calls,
no Playwright. They target `lib/profil_operateur.py` directly and
exercise `_construire_diwall_meta` from `shot.py` for scenario (e).

## How to run

From the repository root:

```bash
PYTHONPATH=/path/to/Diwall/Diwall python3 \
  /path/to/Diwall/Diwall/scenarios/v1.3_validation/verifier.py
```

Or, with the script executable bit set, from the scenarios
directory:

```bash
./verifier.py
```

Exit code: 0 if all five scenarios pass, 1 otherwise.

## Scenarios

| Id | File | What it checks |
|---|---|---|
| a | `test_v1_3_a_profil_absent.txt` (notes) | No profile resolved → strict fallback, all confirmations active, model traceability still on by default. |
| b | `test_v1_3_b_profil_minimal.yaml` | Single `auto_confirmer:` entry → only that friction lifted, others stay active. |
| c | `test_v1_3_c_nom_inconnu.yaml` | Unknown name in `auto_confirmer:` → single stderr warning, valid entries kept, unknown ignored. |
| d | `test_v1_3_d_tentative_liste_rouge.yaml` | Attempt to bypass a red-list verrou (`git_push`) via profile → ignored with warning, runtime constant preserved. Asserts also that LISTE_BLANCHE ∩ LISTE_ROUGE = ∅. |
| e | `test_v1_3_e_tracabilite_desactivee.yaml` | `tracabilite_modeles.active: false` → `modeles_utilises` key absent from the built `diwall_meta`, other keys still present. |

## Acceptance

Scenario (a) requires `_PROFIL_STRICT` to be returned when no
profile is resolvable. Scenarios (b)–(e) load the YAML at this
path and assert the behaviour spec §3.2, §4.4, §5.4.

Adding a new red-list name to `lib/profil_operateur.py` should
keep all five green: the disjoint check in (d) catches accidental
overlaps between the white and red lists.
