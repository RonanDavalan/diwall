# Development journal — Diwall

History of decisions and discoveries by session, in reverse chronological order.

---

## 2026-07-02 — Session 47 (v1.17.1 — Documentation correction)

**Work done:**

- Documentation-only patch. No functional change to `shot.py`/`rpa.py` logic —
  `__version__` bumped for traceability of the JSON-reported version only.
- Triggered by a documentation-drift report relayed from Gemini, verified
  directly against the code rather than trusted on relay (per standing
  discipline): the report was half right. `GUIDE_LLM_SESSIONS.md`,
  `GUIDE_LLM_INTERACTIONS.md`, `GUIDE_LLM_MONITORING.md` already contained
  their v1.17.0 content — only their `notice-version` headers had never been
  bumped for that cycle. `docs/MANUEL.md` was the real gap: still at
  "Version 1.15.0", zero mention of `etat`, `operation_id`, the WAF signal,
  `indice_agressivite`, or any v1.17.0 primitive.
- **`docs/MANUEL.md`**: brought to 1.17.1. New sections 2d (`etat`), 3e (WAF
  signal), 5h/5i/5j (`--replay-verifier`, `--checkpoint`, iframe actions), 7j
  (`--som-rafraichir`); action table, CLI flag tables, and output JSON
  structure updated; section 3d (stealth benchmark) upgraded from a
  qualitative "compare screenshots" instruction to the quantitative
  fingerprint-count method actually used to verify the FR-79 fix.
- **A wider, self-identified audit** went beyond the reported scope, on
  request: `README.md` (root) was found frozen since roughly v1.7 — a
  broken usage example (`--navigate`, a flag that does not exist; only
  `--url` does), a direct internal contradiction on vault encryption status
  ("fully supported since v1.5.0" vs. "planned" twenty lines apart), and a
  "Roadmap (v1.7)" section describing shipped features (Shadow DOM,
  cross-origin iframes) as future candidates — removed, per the doctrine
  that public documents ship what exists, not planning. Capabilities and
  requirements tables extended through v1.17.0.
  `docs/FAQ_LLM.md` contained an outright false statement — "cross-origin
  iframes remain unsupported... not yet implemented" — for a feature shipped
  the same day; corrected, plus the `boussole` field reference and the
  version-history table extended through v1.17.0.
  `docs/GUIDE.md` and `docs/GUIDE_EXPLORATION.md` updated with the
  operator/exploration-relevant consequences of v1.15.0–v1.17.0 (Citizen
  Navigation summary, WAF false-positive note, iframe/`--som-rafraichir`
  exploration checklist items).

**Validation:** preflight exit 0. Regression: `v1.17.0_validation` 4/4,
`v1.16.0_validation` 7/7, `v1.15.2_validation` 4/4.

**Process note:** the two-part failure that produced this patch — three
consecutive releases (v1.15.2, v1.16.0, v1.17.0) shipped without satisfying
`DOCTRINE_DOCUMENTATION_OPERATIONNELLE.md` rule 5 ("MANUEL.md is a condition
of publication, not a bonus"), and a phase-protocol violation when the gap
was reported (verification turned into unrequested rewrite-and-commit
without a phase declaration) — is recorded in
`_CADRE/MEMOIRE/ADDENDUM_2026_07_02_session47.md`, not here. This file
documents the product, not the collaboration incident.

---

## 2026-07-02 — Session 47 (v1.17.0 — Frontier of robustness and qualification)

**Work done:**

- Four items, each with its own design reasoning exposed before implementation
  (condensed PHASE_PLANIFICATION, operator-authorized to run through
  execution without an intermediate validation round — spec
  `V1_17_0_FRONTIERE_ROBUSTESSE.md`). Every item additive and opt-in; the one
  item touching a validated acquis (SoM) changes nothing in the default path.
- **Item 1 — `--replay-verifier` (rpa.py only):** `--sauver-verifier-reference
  FICHIER` / `--replay-verifier FICHIER`, mutually exclusive (rejected early,
  exit 2). Compares `http_status`, `dom_stats`, `evaluations`, `elements_som`
  count against a saved reference — CI-friendly, no pixels, no LLM call.
  Verdict `stable`/`regression` on stderr, exit 1 on mismatch.
- **Item 2 — checkpoints for long scenarios:** required a prerequisite fix —
  `executer_actions()` reported no partial progress on a mid-run exception.
  Added a `progress` dict (mutable, passed by reference, updated after each
  action's dispatch completes without raising) rather than restructuring the
  ~350-line action-dispatch block. `shot.py`'s `executer_actions()` call is
  now wrapped in a narrow try/except that saves the session (if
  `--sauver-session` was requested) *before* the `with sync_playwright()`
  block's implicit teardown closes the browser — the only point where this is
  still possible. Failure JSON gained `actions_executees_avant_echec` /
  `pages_visitees_avant_echec`. `rpa.py --checkpoint FICHIER` orchestrates:
  loads `{actions_completees, session_file}`, slices the action list, resumes
  via `--reprendre-session` instead of `--url`, deletes the checkpoint file
  on full success. DOM state (open modals, half-filled fields) never survives
  a resume — only session state + action-list position do (constraint
  inherited from Qwen Q3, v1.15.2).
- **Item 3 — `--som-rafraichir`, opt-in SoM identity fix:** code reading
  revealed the real mechanism at fault — `_SOM_TROUVER_JS` re-indexes
  `document.querySelectorAll()` on every call, so it is not a *staleness*
  problem but an *identity* one: if elements appear/disappear before the
  target in DOM order, `id: N` silently resolves to a different element.
  Fix: `_SOM_INJECTER_JS`(`_SHADOW`) now stamps every numbered element with
  `data-dw-som-id="N"` unconditionally (harmless, invisible, zero effect on
  existing output). Two new functions `_SOM_TROUVER_STABLE_JS`(`_SHADOW`)
  resolve by that attribute instead of re-indexing — used only when
  `--som-rafraichir` is passed. Removed element → honest `null`, never a
  wrong-target click. Default behavior strictly unchanged without the flag.
- **Item 4 — `cliquer_iframe` / `remplir_iframe`:** scoped down from "SoM
  inside iframes" (a much larger redesign — JS injection cannot cross the
  Same-Origin Policy boundary by construction, unlike Shadow DOM) to a
  targeted primitive using Playwright's `page.frame_locator()`, which
  bypasses that boundary via CDP. No SoM numbering inside the frame —
  selector-based targeting only, documented as a first unlock, not the full
  vision (same honesty pattern as the closed-Shadow-Root limit).
  `remplir_iframe` supports `depuis_vault`/`depuis_vault_totp` like `remplir`.
  Both actions added to `lib/journal.py`'s `ACTIONS_ECRITURE` — caught and
  fixed a real masking gap in the same commit: `_resumer_action()` and
  `_neutraliser_actions_raw()` did not yet know about `remplir_iframe`, so a
  plaintext `valeur` would have leaked into the journal unmasked.

**Validation:** `scenarios/v1.17.0_validation/` — 4/4 green, live tests
against `example.com` and `the-internet.herokuapp.com/iframe` (stable public
QA fixture). Regression: `v1.16.0_validation` 7/7, `v1.15.2_validation` 4/4,
`v1.3_validation` 8/8, `v1.4_validation` 2/3 (pre-existing stale T3,
unrelated — see session 47 v1.15.2 entry below). Preflight exit 0.

**Technical decision:** root `journal.py` untouched this cycle (no functional
change to it), left at `1.14.1`. `rpa.py` jumps `1.15.2` → `1.17.0` (skips
`1.16.0`, which did not touch it) — both consistent with the per-file bump
discipline already in place.

---

## 2026-07-02 — Session 47 (v1.16.0 — Deterministic boussole and unified run identity)

**Work done:**

- Six items shipped, all additive, isolated helpers that never degrade the
  existing output on failure. Recommended execution order followed: B (identity)
  → A (etat) → C, D, E (friction signals) → F (measurement).
- **Item B — `operation_id`:** `uuid.uuid4().hex[:12]` generated once at the top
  of `main()`, before argument parsing — available even on early validation
  failures. Default `--output-dir` isolated to `/tmp/diwall/<operation_id>/`
  (explicit `--output-dir` overrides are respected as-is, never double-isolated).
  `run_id` inside `executer_actions()` derived from `operation_id` (kept, not
  removed — immutability). Transmitted to `lib/journal.py`'s
  `enregistrer_operation()`, which now reuses it instead of generating a second
  identity. `_boussole()` extended to accept and expose it (9 call sites updated).
- **Item A — `etat`:** `_construire_etat()` synthesizes `auth_status`,
  `citoyennete.plafond_atteint`, `derive_session`, `erreurs_js`,
  `erreurs_console`, and `waf_bloquants` into `{pret_a_agir, niveau_confiance,
  raisons}` at the JSON root. Explicitly scoped: does not check URL/title
  conformance to a business expectation (that remains `rpa.py`'s assertion job).
- **Item C — WAF detection:** `_detecter_waf()` (403/429 or keyword match)
  checked on the initial navigation and every `naviguer` action. Counted in
  `citoyennete.waf_bloquants` (root and boussole, via the existing duplication).
  Signal only — no exception, ever (session 47 arbitration: Diwall perceives,
  it does not moralize about access).
- **Item D — `erreurs_console`:** `page.on("console", ...)` filtered to
  `type == "error"`, root-level list, always present. Distinct from `erreurs_js`
  (`pageerror` — uncaught exceptions only).
- **Item E — `citoyennete.indice_agressivite`:** ratio of `ACTIONS_ECRITURE`
  (reused from `lib/journal.py`, not duplicated) over total actions executed.
  Logged in `operations.jsonl` via a new `citoyennete` field on
  `enregistrer_operation()`.
- **Item F — stealth benchmark:** see FR-79 below — blocked, then unblocked by
  a real fix.

**Finding and fix — FR-79 (`docs/RETOUR_EXPERIENCE.md`):** `--stealth` has been
non-functional in production since v1.15.0 — `playwright-stealth` 2.0.3 (the
version actually installed, matching `requirements.txt`) removed the
`stealth_sync` function `shot.py` imported. Failed silently via
`except ImportError`, and `boussole.stealth_actif` lied (reflected the CLI flag,
not real application). Fixed: `Stealth().apply_stealth_sync(page)` (new 2.x
API) + `stealth_actif` now gated on actual success (`stealth_applique`).
Post-fix measurement on `bot.sannysoft.com`: fingerprint test failures dropped
from 12 to 0 (`navigator.webdriver` `true` → `false`). Full write-up, including
why the original FR-77 23-site panel was not reproduced, in
`docs/RETOUR_EXPERIENCE.md` FR-79.

**Documentation debt caught and paid down:** the "Notice index" version column
in `GUIDE_LLM.md` had drifted from the `notice-version` header comments since
the v1.15.2 commit (bumped the headers, forgot the index table). Corrected for
all three notices; `GUIDE_LLM_SESSIONS.md`'s own header was also found stale
(missed in v1.15.2's item 5) and corrected retroactively.

**Validation:** `scenarios/v1.16.0_validation/` — 7/7 green (operation_id,
etat nominal/degraded, `_detecter_waf` unit tests, erreurs_console,
indice_agressivite, stealth fix). Regression: `v1.15.2_validation` 4/4,
`v1.3_validation` 8/8, `v1.4_validation` 2/3 (pre-existing stale T3, see
session 47 v1.15.2 entry below — unrelated to this cycle). Preflight exit 0.

**Technical decision:** `rpa.py` and root `journal.py` left untouched — no
functional change to either this cycle (only `shot.py` and `lib/journal.py`
were modified), matching the per-file version bump discipline.

---

## 2026-07-02 — Session 47 (v1.15.2 — Consolidation, DX and anti-collision patch)

**Work done:**

- Static-audit-driven patch cycle, sourced from a June multi-model review (ten LLM
  families) filtered by the operator and Gemini, then planned/documented in
  `_CADRE/` and executed same-day. Eight items, zero new capability — pure
  hygiene and defensive hardening. Commit `00ef073`.
- `shot.py`: `chemin_png()` switched from `int(time.time())` to `time.time_ns()` —
  eliminates same-second filename collision between concurrent runs (parade
  K1′, full fix deferred to v1.16.0 `operation_id`).
- `shot.py` / `rpa.py`: `--auth-indicator-negative` without `--auth-indicator` now
  rejected early (`arguments_incompatibles`, exit 2, before any Playwright launch).
  Previously silently ignored — the auth check block was skipped entirely.
- `scenarios/exemples/`: three canonical scenarios (`sondage_fast`, `navigation_som`,
  `rpa_securise`), zero secrets, schema-validated. Already covered by the existing
  preflight `scenarios/*` scope — no script change needed.
- `docs/GUIDE_LLM_MONITORING.md`: exhaustive boussole key activation table
  (replaces the incomplete v1.2 table), root/boussole duplication note, a design
  rule requiring every future conditional key to ship with a table row in the same
  commit, and the temporary-file isolation rule (prerequisite for v1.16.0).
- `docs/GUIDE_LLM_INTERACTIONS.md`: `data-testid` selector priority, a
  `diagnostic_dom.json`-driven strategy table, a citizenship self-regulation note,
  and a perceptual fallback ladder (SoM → `a11y_tree` → `cliquer_visuel`).
- `docs/GUIDE_LLM_SESSIONS.md`: `--stealth` + `--shadow-dom` compatibility note.
- `scenarios/v1.15.2_validation/`: live proof against `example.com` that
  `--no-evaluer` is surgical (blocks scenario `evaluer` only, not `shot.py`'s
  internal `page.evaluate()` calls) and that the auth negative assertion already
  degrades correctly. 4/4 tests green.

**Validation:** preflight exit 0 (65 files scanned, 3 smoke tests green).
Regression: `v1.3_validation` 8/8 green, `v1.4_validation` 2/3 green.

**Finding — pre-existing stale test, not a regression:** `v1.4_validation` T3
asserts `depuis_vault` and `vault_cle` are absent from the raw journal line.
Both now legitimately appear inside `actions_raw` (introduced in v1.6.0 for
`--exporter-skill`) — by design, `depuis_vault` and `vault_cle` are key
*references*, never the resolved secret value (confirmed: the actual filled
value `S3CR3T_RESOLU` stays absent). Reproduced identically on unmodified
pre-session code via `git stash` — the test predates v1.6.0 and was never
updated. Not fixed this cycle (outside the planned v1.15.2 item list); flagged
for a future patch.

**Technical decision:** `journal.py` (root CLI reader) left at `__version__
1.14.1` — untouched this cycle, matching the per-file bump discipline already
observed in git history (each of `shot.py`/`rpa.py`/`journal.py` bumps only
when it functionally changes, not in lockstep on every release).

---

## 2026-07-01 — Session 46 (v1.15.1 — Security hardening)

**Work done:**

- Static audit: 11 security vectors identified and fixed (commit `544f66f`).
- `shot.py`: `_prendre_capture()` centralises all PNG captures with guaranteed secret masking.
  `_valider_schema_url()` rejects non-HTTP schemes (exit 2). `--no-evaluer` flag blocks `evaluer` at runtime.
  `--ignore-tls-errors` replaces hardcoded `ignore_https_errors=True`. `_valider_actions_vault()` validates
  inline actions. `_MASQUER_SECRETS_JS` extended to 9 selectors.
- `lib/journal.py`: `_ecrire_ligne()` uses `os.open(..., 0o640)` + `chown` diwall group.
  `_sanitiser_url_journal()` strips query string and fragment. Fallback `/tmp/diwall/` at 700/600.
  `enregistrer_operation()` logs `evaluer` script and return value in `evaluations[]`.
- `rpa.py`: `--no-evaluer` and `--ignore-tls-errors` propagated to `shot.py`. URL scheme validation added.
- `scripts/preflight-publication.sh`: scope extended to `.py`/`.sh`/`.yaml`. Structural JSON credential
  check replaces hardcoded password string. Auto-exclusion of the script itself.
- `docs/GUIDE_LLM_INTERACTIONS.md`: `evaluer` security restriction documented (forbidden targets, audit trail).
- `docs/GUIDE_LLM_SESSIONS.md`: `--ignore-tls-errors` section added.

**Validation:** 12/12 tests green. Preflight exit 0 (60 files scanned). Zero direct `page.screenshot()` outside `_prendre_capture()`.

---

## 2026-07-01 — Session 44 (v1.15.0 — Navigation Citoyenne + operational manual)

**Work done:**

- `--stealth` flag (playwright-stealth 2.0.3) added to `shot.py` and `rpa.py`.
  Applies `stealth_sync(page)` after `page = ctx.new_page()`. `boussole.stealth_actif: true` when active.
- `scenarios/test_stealth.json`: new scenario navigating sannysoft.com then intoli.com (stealth benchmark).
- `executer_actions()` returns a 5-tuple; 5th element is `citoyennete` dict:
  `{"pages_visitees": N, "actions_executees": N, "duree_totale_ms": N}` + optional `plafond_atteint`.
- `_conf_navigation()`: reads `diwall.conf[navigation]` for `min_action_delay_ms`,
  `max_pages_par_run`, `max_actions_par_run`. Applied at start of `main()`.
- `lib/journal.py`: `_journal_path()` reads path from `diwall.conf[journal][chemin]`.
  Fallback: `DIWALL_JOURNAL` env var, then `/var/log/diwall/operations.jsonl`.
- `lib/vault.py`: opt-in SHA256 checksum via `VaultChecksumError` + `_verifier_checksum()`.
  Covers fields `username`, `password`, `totp_cle`. Absent `checksum` key = no check (strict opt-in).
- `scenarios/diagnostic_dom.json`: 3 new `evaluer` actions (React/Vue/Angular detection,
  shadow root count, data-attr inventory).
- `git mv docs/GUIDE_HUMAIN.md docs/GUIDE.md`.
- `docs/MANUEL.md` created (900 lines, 11 sections, operational reference for humans and LLMs).
- `docs/GUIDE_LLM.md` v3.4: pointer to MANUEL.md at top, WAF section updated for v1.15.0.

**Architectural decision:** `citoyennete` appears both at JSON root and inside `boussole` —
two consumers with different needs (boussole for orientation, root for structured extraction).

**Tests:** T-GUIDE-K, T-STEALTH-1/2/3, T-CITOYEN-1/2/3, T-DELAY-1, T-VAULT-I-1/2/3 — all green.
Preflight exit 0.

**Commits:** `91e8c56` (v1.15.0), `c3768b6` (MANUEL.md).

---

## 2026-06-27 — Session 42 (v1.14.1 — Scenario neutralisation + anti-leak doctrine)

**Work done:**

- Inter-session anomaly audit: 5 untracked scenarios + plaintext credential in scenarios
  already committed since session 31.
- Full neutralisation of 8 scenario files: credentials → `depuis_vault`,
  internal hosts → `__HOST_ADMIN__`, named identifiers → vault keys.
- `CLAUDE.md`: Rule n°6 added — every `password` field in a scenario must use `depuis_vault`.
- `scripts/preflight-publication.sh`: scope extended to `scenarios/*.json`, dummy credential pattern added.
- `docs/GUIDE_LLM.md`: WAF note added — e-commerce sites protected by Cloudflare/CloudFront
  return 403 systematically; web landscape friction, not a Diwall constraint.
- `docs/RETOUR_EXPERIENCE.md`: FR-77 — REX commercial search session (23 sites, 8.7% accessible,
  39% WAF blocking).
- `__version__`: 1.14.0 → 1.14.1 in shot.py / rpa.py / journal.py.
- Production deployment `/opt/diwall/`: 13 files updated.

**Technical decision:** no git history rewrite for the plaintext credential
(preferred transparent explanatory commit — dummy password, dev local app with no required auth,
cleaned up as a matter of principle).

**Commits:** `7eb9820` (neutralisation), `1832773` (docs + bump). Tag `v1.14.1`. GitHub release published.

**Backlog v1.15.x recorded in `_CADRE/SPECIFICATIONS/10_ROADMAP.md`:** stealth mode,
`timeout_network`/`timeout_dom` distinction, cross-call session persistence — each requires PHASE_PLANIFICATION.

---

## 2026-06-23 — Session 41 (v1.14.0 — Operational boussole and signal readability)

**Context:** v1.13.0 delivered. Spec v1.14.0 validated (PHASE_PLANIFICATION + PHASE_DOCUMENTATION closed).

**Technical decisions:**

- Enriched boussole: `url_courante` + `titre_page` always present, 3 conditional fields
  (`session_derive`, `auth_status`, `som_hors_viewport`). Fix for documentation drift
  (guide showed target boussole, code did not produce it).
- `--auth-indicator-negative`: inverse selector to disambiguate `auth_status`
  on interfaces with persistent headers. Logic: AND(positive_visible, NOT negative_visible).
- `--mode fast|full`: shortcut `fast = --no-capture --a11y`, resolved before cascade validations.
- Decision-tree capture sensor in `GUIDE_LLM.md` v3.3.
- `GUIDE_LLM_SESSIONS.md` v1.2 — `auth_indicator_negative` section.
- `GUIDE_LLM_MONITORING.md` v1.2 — note on conditional boussole fields.
- `FAQ_LLM.md` v1.1 — Shadow DOM updated (delivered in v1.13.0, not "not yet"),
  full version table, boussole Q/A, --mode fast, auth_indicator_negative.
- `GUIDE_EXPLORATION.md` v1.1 — `--mode fast` in light exploration, `--shadow-dom` in checklist.
- `GUIDE_HUMAIN.md` v1.2 — `--mode fast` in examples, Shadow DOM + auth_indicator_negative pitfalls.
- `scenarios/schema.json` — optional `auth_indicator_negative` property added.

**Tests:** T-A1 through T-C3 (10/10) GREEN. Preflight exit 0.

**71 frictions / 41 sessions.**

---

## 2026-06-23 — Session 40 bis (v1.13.0 — Shadow DOM SoM traversal)

**Context:** v1.12.0 delivered. Spec v1.13.0 validated in session 40 (PHASE_DOCUMENTATION closed).

**Technical decisions:**

- `--shadow-dom` opt-in flag in `shot.py` and `rpa.py`. Disabled by default.
- Recursive JS walker `queryShadowAll` — descends open Shadow Roots in document order.
- All three SoM functions share strictly the same walker (indexing consistency inviolable).
- Conditional `boussole.shadow_dom_actif: true` in JSON output.
- Propagation from scenario via `shadow_dom: true` root property.
- Closed Shadow Roots silently ignored (catch in walker).
- `GUIDE_LLM_INTERACTIONS.md` v1.2 — full `--shadow-dom` documentation.
- `GUIDE_LLM.md` v3.2 — notice index v1.2, Shadow DOM routing line.
- `scenarios/schema.json` — optional `shadow_dom` property added.

**Tests:** T-A1 GREEN, T-A2 GREEN, T-B1 GREEN, T-B2 GREEN, T-C1 GREEN, T-C2 GREEN, T-C3 GREEN.
Preflight exit 0.

**71 frictions / 40 sessions.**

---

## 2026-06-23 — Session 40 (v1.12.0 — DX, visual security and fast probe)

**Context:** v1.11.1 in production. Empty backlog. Multi-model feedback campaign
(DeepSeek, Qwen, Grok) consolidated by Gemini. Trilateral PHASE_PLANIFICATION,
then PHASE_DOCUMENTATION + PHASE_EXECUTION in a single session.

**Technical decisions:**

- `GUIDE_LLM.md` v3.1 — error-routing table by symptom (12 entries) + `Version` column
  in notice index + autonomous notice versioning rule.
- `GUIDE_LLM_INTERACTIONS.md` v1.1 — section "Current limit — Shadow DOM and Web Components":
  explanation, `evaluer` workaround, `--shadow-dom` v1.13.0 announcement.
- `GUIDE_LLM_SESSIONS.md` v1.1 — "Pre-condition pattern" section: 4 initial safety assertion
  patterns before mutating actions.
- `GUIDE_LLM_MONITORING.md` — header reformatting only (version unchanged v1.1).
- `shot.py` — `_MASQUER_SECRETS_JS` + `_RESTAURER_SECRETS_JS`: `blur(8px)` blurring of
  `input[type="password"]` and `autocomplete*="password"` fields in `try/finally` around
  the 3 capture points (final, SoM, `capturer` action). Silent security measure.
- `shot.py` — `_DOM_STATS_JS`: 6 semantic counters (buttons, inputs, dropdowns, forms,
  links, dialogs) injected into `result["dom_stats"]` in `--no-capture` mode only.

**Recorded roadmap:**
- `V1_12_0_DX_SECURITE_SONDE.md` (delivered this session)
- `V1_13_0_SHADOW_DOM_SOM.md` — Shadow DOM, `--shadow-dom` flag, dedicated session
- Parking lot: `attendre_stabilite` (MutationObserver opt-in), declarative syntactic contract

**Tests:** T-E1 GREEN, T-E2 GREEN, T-E3 GREEN, T-E4 GREEN, T-F1 GREEN, T-F2 GREEN, T-F3 GREEN.
Preflight exit 0 / smoke tests 3/3.

**Commit:** `0babfb7` — feat(v1.12.0)

**71 frictions / 40 sessions.**

---

## 2026-06-23 — Session 39 (v1.11.1 — session persistence FR-74/FR-75)

**Context:** v1.11.0 in production. Empty backlog. FR-74 and FR-75 raised by
Gemini 3.5 Flash (Sillage interface discovery audit) via Claude Sillage.

**Technical decision:**

- `_nettoyer_session_ephemere` disabled in `shot.py` — silent deletion of the
  `--reprendre-session` file removed. Common root cause of FR-74 and FR-75:
  end-of-run deletion prevented all chained use of `--reprendre-session`.
  Shot.py performs no `rmtree` on `/tmp/diwall/` — the cause attributed to
  "startup cleanup" in FR-75 was a tester misattribution; it was FR-74 with
  a path in `/tmp/diwall/`.

**Tests:** T-A1 GREEN, T-B1 GREEN. Preflight exit 0.

**71 frictions / 39 sessions.**

---

## 2026-06-23 — Session 38 (v1.11.0 — ergonomics and guide)

**Context:** v1.10.2 in production. Sillage REX: 6 field frictions raised by partner LLM
(CSS/showModal, screenshot timeout, fragile stdout, monolithic GUIDE_LLM, rigid assertions,
page title verification).

**Technical decisions:**

- `force: true` on `cliquer` — Playwright bypass for CSS-hidden elements and `showModal()`.
  Not applicable to `cliquer_som` (coordinate click, native bypass).
- `--screenshot-timeout` — configurable timeout for `page.screenshot()`, default 120 s.
  Distinct from `--timeout`. Propagated to all captures.
- Clean `rpa.py` stdout — `tail -1` internalised; cause: `print(result.stdout)` retransmitted
  the subprocess's full output.
- `contient` (substring) and `motif` (re.search) assertions on `evaluer` — mutually exclusive
  with `attendu`. Non-str type + contient/motif → exit 1.
- GUIDE_LLM restructured: 1,741 lines → 205-line index + 3 notices
  (`GUIDE_LLM_INTERACTIONS.md`, `GUIDE_LLM_SESSIONS.md`, `GUIDE_LLM_MONITORING.md`).

**Post-write audit (session):** 5 nominal leaks neutralised in new notices,
5 API errors corrected (`watch.py`, `--profil`, `journal.jsonl`, `--reprendre-session`, `--llm`).

**Commits:** `2ebc4fe` (v1.11.0), `97badad` (docs anti-leak fix + API). Tag v1.11.0 pushed.
GitHub release published.

---

## 2026-06-21 — Session 37 (v1.10.2 — FR-73 + related note FR-69)

**Context:** v1.10.1 in production. 68 frictions / 36 sessions. `scripts/uninstall.sh`
on `main` without tag. FR-73 raised by `<LLM_PARTENAIRE>` (messaging), related note
on `attendre`+`ms` hint.

**Technical decisions:**
- GUIDE_LLM FN7 corrected: removal of false claim "`capturer` does not trigger a timeout".
  Distinction: capture after operation (OK) vs during (30s Playwright fixed timeout).
  Added `pause`+`interval_capture` pattern.
- rpa.py: targeted hint `attendre`+`ms` → suggests `pause`. Detection via
  `e.instance.get("type") == "attendre"` and `"ms" in e.instance`.
- FR-73 track 2 (`capturer` option to bypass stability) deferred to v1.11 — requires planning.

---

## 2026-06-21 — Session 36 (v1.10.1 — fixes FR-68–72)

**Context:** v1.10.0 in production. 64 frictions / 32 sessions. Empty backlog.
Frictions raised by Claude Sillage (8 items); additional analysis by Gemini (FR-72).

**Work done:**

5 frictions documented (FR-68 to FR-72), 4 code fixes:

- `scripts/install.sh` — `check_file()` added (FR-68): verifies `diwall-sample.conf`
  (644 root:diwall) and `diwall.conf` if present (640 root:diwall). Detects `root:root`
  cases caused by a silently failed `chown 2>/dev/null || true`.

- `rpa.py` — explicit hint in `_valider_schema` (FR-69): when `ValidationError`
  at root with `"is not of type"`, directs toward `{"actions": [...]}`.

- `lib/vault.py` — two fixes:
  - Distinct messages in `lire_credential_fichier` and `verifier_cles_fichier` (FR-71):
    "non-existent directory (vault not mounted?)" vs "existing directory not mounted
    (raw disk rejected)".
  - `_coffre_est_monte` (FR-72): parses column 2 of `/proc/mounts` and now accepts
    subdirectories of a FUSE vault (`path.startswith(mountpoint + "/")`). Restricted
    to FUSE fstypes to preserve T1. Semantic drift identified by Gemini: Sillage was
    blocked with `VaultFermeError(42)` when storing credentials in a vault subdirectory.

- `docs/GUIDE_LLM.md` v2.6 — 3 corrections: `tail -1` rule extended to `rpa.py`;
  `remplir_som`: "Clears the field before typing (v1.9.6+)" note; diagnostic rule
  `Locator.click: Timeout` → suspect JS-masked container → `evaluer`.

**68 frictions / 36 sessions.**

---

## 2026-06-20 — Session 35 (v1.10.0 — `--secrets` multi-vault + fail-fast venv)

**Context:** v1.9.8 in production. 64 frictions / 32 sessions.
PHASE_EXECUTION v1.10.0 pending since session 33.

**Work done:**

Complete PHASE_EXECUTION, spec `V1_10_0_SECRETS_MULTICOFFRE.md` (Items A–D):

- `lib/vault.py` — three new functions:
  `lire_credential_fichier(path, key)` — reads from designated file with mount check T1;
  `verifier_cles_fichier(path, keys)` — fail-fast pre-validation of keys;
  `lire_totp_fichier(path)` — TOTP generation from designated file.

- `shot.py` — fail-fast venv (`find_spec("playwright")` absent → explicit message + exit 3);
  `--secrets <file>` argument in `parse_args()`;
  `secrets_chemin` parameter in `executer_actions()` with full T3 coverage:
  `depuis_vault`, `depuis_vault_totp` (×2: remplir + remplir_som), `attendre_mfa_ntfy` (ntfy_topic).

- `rpa.py` — `--secrets` argument; `verifier_cles_fichier` import; bifurcated pre-validation
  (`verifier_cles_fichier` if `--secrets`, `verifier_cles` otherwise); propagation to shot.py subprocess.

- `docs/GUIDE_LLM.md` v2.5 — section "Multi-vault and explicit credential files":
  use cases, syntax, Diwall JSON format, T3 coverage, T1 doctrine + honest limit,
  T4 limit, T6 perception surface.

- `__version__` → `1.10.0` on `shot.py`, `rpa.py`, `journal.py`.

**Test results:**
T-A1 green (read from mounted vault, correct value).
T-A2 green (`VaultFermeError(42)` on non-mounted directory, exit 42).
T-A3 green (`FileNotFoundError`, exit 1, explicit message).
T-B1 green (fail-fast missing key before Playwright via rpa.py, 126ms).
T-B2 green (TOTP read from designated file, 6-digit code).
T-C1 green (message "run via /opt/diwall/venv", exit 3).
T-C2 green (exit 3 cleanly relayed by rpa.py).
T-D1 green (without `--secrets`: behaviour strictly identical to v1.9.8).
Preflight exit 0. Smoke tests 3/3.

**Note T-A2:** `/tmp` on neo is a mounted tmpfs — VaultFermeError does not trigger on `/tmp`.
Consistent with honest limit T1 (tmpfs = active mount). Test uses an unmounted directory
to validate rejection.

**State on exit:** Diwall v1.10.0. 64 frictions / 35 sessions.

---

## 2026-06-20 — Session 32 (v1.9.8 — FR-67: fixed pauses → semantic waits)

**Context:** v1.9.7 in production. 63 frictions / 31 sessions. Empty backlog.
Proposal raised by Claude Sillage: replace fixed pauses with `attendre_selecteur_present`.

**Work done:**

Trilateral operator / Claude Diwall / Claude Sillage — PHP selector verification
by Sillage before execution. Sillage commit `a762dbe`: `data-sillage` attribute added
on `<tr>` elements of `page_tenant.php` to make deletion awaitable (C3).

- `docs/GUIDE_LLM.md` v2.4 — two updates:
  (1) REX #66 revised: `attendre_absence + delai_initial_ms:500` becomes the preferred form
  (vs `pause 2000 + evaluer URL` which remains the pre-v1.9.7 fallback);
  (2) New section FR-67: `pause` vs `attendre_selecteur_present` rule — decision table,
  anti-pattern `attendre_selecteur_present body + pause N`, self-documenting scenario principle.

- `scenarios/valider_admin_maitre_c1b.json` — 10 pauses replaced out of 11:
  A (post-login ×2) → `attendre_absence + delai_initial_ms:500`;
  B (navigation + body ×3) → `attendre_selecteur_present [data-sillage="toggle-creer-locataire"]`;
  C1/C2 (post-AJAX ×2) → `attendre_selecteur_present [data-sillage="mdp-temp-locataire"]`;
  C3 (post-deletion) → `attendre_absence tr[data-sillage="ligne-tenant-test-c1b"]`;
  D (dialog open ×2) → `attendre_selecteur_present #dialog-id[open]`;
  E (details animation) → `attendre_selecteur_present input[name="nouveau_tenant"]`.
  1 pause kept (C3 deletion → `attendre_absence`, see above).

**Preflight:** exit 0 / smoke tests 3/3

**Validation:** succes:true — 6 cross-domain navigations (`__DOMAINE_OPERATEUR__` + `__HOST_CLONE__`)
with `attendre_selecteur_present: h1`, 4463ms, clean captures. Preflight exit 0 / smoke tests 3/3.

**State on exit:** Diwall v1.9.8. 64 frictions / 32 sessions.

---

## 2026-06-18 — Session 31 (v1.9.7 — delai_initial_ms + friction #66)

**Context:** v1.9.6 in production. 62 frictions / 30 sessions. Empty backlog.
Friction #66 raised by Claude Sillage (E2E validation C1b, campaign 18/06).

**Work done:**

Trilateral operator / Claude Diwall / Claude Sillage (via operator relay) upstream:
decision for a two-step fix — immediate documentary, non-urgent API.

- `docs/GUIDE_LLM.md` v2.3 — `attendre_absence` timeout rule on first form submission
  (REX #66): on the first POST navigation of a scenario, insert `pause ms:2000` + `evaluer`
  on the target URL. Immediate `attendre_absence` after a first submit triggers a timeout
  even if login succeeds — Playwright has not yet processed the redirect. Related to
  frictions #5 and #16 (session_regenerate_id timing).

- `shot.py` + `scenarios/schema.json` (friction #66) — new optional parameter
  `delai_initial_ms` on `attendre_absence`: pause in ms before `wait_for_selector(state=detached)`
  polling begins. Allows documenting intent in the scenario without adding a separate
  `pause` action. API decision: optional parameter, backwards-compatible, default behaviour unchanged.

- `scenarios/` — three Sillage scenarios versioned:
  `valider_auth_multitenant.json` (C1a), `valider_admin_maitre_c1b.json` (C1b — 14/14 assertions),
  `explorer_client_projet_vitrine.json` (DOM diagnostic `__DOMAINE_OPERATEUR__`).

**Preflight:** exit 0 / smoke tests 3/3

**State on exit:** Diwall v1.9.7. 63 frictions / 31 sessions.

---

## 2026-06-14 — Session 29 (v1.9.6 — group C: remplir_som + evidence permissions)

**Context:** v1.9.5 in production. 67 frictions / 28 sessions. Group C backlog.

**Work done:**

Discovery at session start: frictions #35 (recursive vault) and #37 (port-aware vault)
already implemented in `lib/vault.py` during session 16 — without spec or marking.
Retroactive spec `43_GROUPE_C_VAULT_FILL_PREUVES.md` created in `_CADRE/`.
Frictions #35 and #37 marked resolved in `docs/RETOUR_EXPERIENCE.md`.

- `shot.py` (friction #4) — `remplir_som` on non-SELECT input: `Control+a` replaced
  by `page.evaluate(document.activeElement.value = '')` + `input` dispatch. Guarantees
  field clearing before typing even on inputs with custom JS handlers.

- `scripts/install.sh` (friction #40) — step 6: `/var/log/diwall/preuves` changed from
  `root:diwall` to `$USER:diwall` (direct owner = current operator) + explicit `chmod 2770`.
  Eliminates immediate post-install `Permission denied` without waiting for `newgrp`.
  `check_dir` updated accordingly.

**Preflight:** exit 0 / smoke tests 3/3

**State on exit:** Diwall v1.9.6. 67 frictions / 29 sessions.
Group C: #35 ✓ #37 ✓ #4 ✓ #40 ✓ (cold test #40 to run before release).

---

## 2026-06-14 — Session 28 (v1.9.5 — relevant communication + frictions #61–63)

**Context:** v1.9.4 in production. 64 frictions / 27 sessions. Empty backlog.
Frictions #61–63 discovered during Sillage E2E campaign v3.5.6 (14/06).

**Work done:**

Trilateral operator / Claude Diwall / Gemini in PHASE_PLANIFICATION: repositioning
Diwall communication around the shared human/LLM visual reference.

- `README.md` — removal of "not a tool for humans". New pitch: shared visual reference,
  distinct benefits for humans (delegating anxiety) and LLMs (interface perception).

- `docs/GUIDE_HUMAIN.md` v1.1 — conceptual introduction "Why Diwall" added at the top:
  delegation of anxiety-inducing visual verification, recommended/discouraged use case table.

- `docs/GUIDE_LLM.md` v2.1 — two additions:
  - Section "When NOT to use Diwall": FR-59 (Playwright 30s non-configurable timeout),
    FR-60 (orphan mutation after timeout). Summary table with alternatives.
  - Frictions #61–63: rules on JS-interactive DOM elements — CSS-masked inputs
    (toggle-switch), conditional buttons on a `<select>`, buttons inside native `<dialog>`.
    General rule: any container opened/hidden via JS → `evaluer`, never `cliquer`.

- `scripts/deploy.sh` — removal of two obsolete blocks (empty `/opt/diwall/scripts/`,
  chmod on vault scripts not deployed in production).

- `_CADRE/SPECIFICATIONS/10_ROADMAP.md` — milestone "Dual-entry showcase __DOMAINE_OPERATEUR__" recorded.

**Group B fixes already present in sources:**
FR-48 (journal stderr), #41 (atomic session write), #36 (enriched vault message) — resolved
in previous sessions without REX marking.

**Commits:** `b12645a`, `d8c0d9d`, `87a1373`, `<this commit>`

**State on exit:** Diwall v1.9.5 in production on the production server. 67 frictions / 28 sessions.

---

## 2026-06-13 — Session 27 (v1.9.4 — Reconnaissance before mutation + FN10–FN13)

**Context:** v1.9.3 in production. 60 frictions / 26 sessions. Empty backlog.
Sillage message: 4 new field frictions FN10–FN13 from E2E re-test Milestone C on 13/06.

**Work done:**

Trilateral operator / Claude Diwall / Gemini in PHASE_PLANIFICATION: analysis of high
cost of E2E sessions on new features (7 rpa.py invocations for batch deletion — FN8 triggered).
Decision: reduce cost via a mandatory non-mutating exploration pass before any operational scenario.

- `rpa.py` — `--url` parameter: replaces scenario URL at execution without modifying the file.
  Allows generic scenarios to be reused on any target URL.

- `scenarios/diagnostic_dom.json` — non-mutating DOM inventory scenario: lists buttons
  (text, type, id, class), inputs (type, id, name, value) and selects (id, name, options)
  of the target page. To run before any operational scenario on unknown terrain.

- `docs/GUIDE_LLM.md` v2.0 — two major additions:
  - "Reconnaissance before mutation" rule (blocking): 5-step procedure with shot.py
    diagnostic then rpa.py diagnostic_dom before any mutating scenario on unknown terrain.
  - FN10–FN13: 4 Sillage field frictions documented (extended FD1, capturer timeout,
    batch dialog, batch checkboxes).

**Architectural decision:** the `--url` parameter follows shot.py's philosophy (already
uses `--url`). The "Reconnaissance before mutation" rule is the upstream counterpart of
"Stop-and-Search" (reactive after failure) — both form a complete invocation-sobriety doctrine.

**Commit:** `6b588bd` — feat(rpa): --url override + diagnostic_dom + GUIDE_LLM v2.0

**State on exit:** production `/opt/diwall/` synchronised. 64 frictions / 27 sessions
(FN10+FN11+FN12+FN13 = 4 new field frictions documented).

---

## 2026-06-12 — Session 25 (v1.9.3 — security hardening from Sillage REX)

**Context:** v1.9.2 in production. Empty backlog. Inter-LLM message open:
three architectural gaps identified by Claude Sillage during PHASE_VALIDATION C2.

**Work done:**

- `scripts/deploy.sh` — `diwall.conf` no longer created automatically at installation.
  `deploy.sh` now writes `diwall-sample.conf` (generic model, 644). `diwall.conf`
  must be created manually from this template — its absence shows a framed warning.
  Separate permissions: `lib/*.py` → 644, `scenarios/*` + `skills/*` + `diwall.conf` → 640.

- `lib/vault.py` — removal of silent fallback `~/Vaults/Diwall`.
  New exception `VaultNonConfigureError` (exit 43) raised if `diwall.conf` absent
  during vault resolution. Structured message with correction instructions.
  Vault error set: 42 = vault closed, 43 = not configured.

- `docs/GUIDE_LLM.md` — infrastructure tree updated (diwall-sample.conf / diwall.conf),
  vault fail-fast note, "Multi-model access" section (service account onboarding `usermod -aG`).

**Architectural decision:** `lib/` (public GitHub code) stays at 644;
`scenarios/` and `skills/` (instance data) move to 640 — the distinction is
semantic, not just technical.

**Commit:** `5f0d08e` — feat(security): diwall-sample.conf + vault fail-fast + 640 permissions scenarios/skills

**State on exit:** production `/opt/diwall/` synchronised. 56 frictions / 25 sessions.

---

## 2026-06-11 — Session 24 (Sillage field REX + inter-LLM channel)

**Context:** v1.9.2 in production. Empty backlog. E2E validation REX
Sillage Milestone C shared by the operator (PHASE_VALIDATION C2, 11/06/2026).

**Work done:**

- `docs/GUIDE_LLM.md` — two additions from field REX:
  - Section "Error recovery — Stop-and-Search rule" (blocking): mandatory
    RAG+GUIDE_LLM+analysis sequence before any corrected script after failure.
  - Friction FR-57 "CSS-only dialogs": `cliquer`/`cliquer_som` timeout on
    CSS-masked containers without `<dialog open>` — `evaluer`+JS pattern mandatory.
- `_CADRE/MEMOIRE/MESSAGERIE_PROJETS.md` — created: inbound inter-LLM channel.
  Any project using Diwall writes here (via the operator) to communicate with
  Claude Diwall. Conditional reading at startup (`grep OUVERT`).
- `_CADRE/GOUVERNANCE/PROTOCOLE_DEMARRAGE.md` — item 6 conditional (messaging)
  added to instruction n°2 and startup checklist.
- `_CADRE/INDEX.md` — MESSAGERIE_PROJETS reference added.

**Architectural decision:** the inter-LLM channel is centralised in `_CADRE Diwall`
(Diwall is the common instrument). Partner projects do not need to access each other's `_CADRE`.

**REX received from Claude Sillage:** two good reflexes documented (FD1 CSS dialogs,
FD2 placeholder/ID ambiguity). Avoidable frictions: modal Mode B rule violation,
ERR_ABORTED post-login (documented rules not re-read before execution).

**State on exit:** v1.9.2 unchanged. GUIDE_LLM enriched. Messaging channel operational.
56 frictions / 24 sessions.

---

## 2026-06-10 — Session 23 (strategic documentation post-v1.9.2)

**Context:** v1.9.2 in production. Empty backlog. Upcoming field work.

**Work done:**

- `_CADRE/SPECIFICATIONS/RADAR_USAGES.md` — parking lot of potential uses:
  horizons A (admin/sovereign RPA), B (content/ticketing), C (Sillage+Sentinelle synergies),
  D (armed technical signals). Decision: no speculative roadmap, ideas captured with explicit triggers.
- `docs/FAQ_LLM.md` — public FAQ for models: 5 technical Q&As from feedback of 9 LLMs
  (native PDF/images, `--no-capture` guarantees, Shadow DOM, dry-run/SoM linter, `declencher_scenario`,
  v1.9.x version map).
- `docs/GUIDE_LLM.md` — "See also" pointer to `FAQ_LLM.md` added.
- `_CADRE/MEMOIRE/MESSAGE_LLM_REPONSE_GLOBALE_2026_06_10.md` — global response
  to 9 LLMs: version corrections, stats, Vosk, Qwen/DeepSeek/Z.ai technical answers.
- `_CADRE/MEMOIRE/CONSENTEMENTS_LLM_2026_06_10.md` — 9/9 consents for FAQ.
  Perplexity/S3 governance note. Z.ai (GLM) behaviour documented.
- `_CADRE/MEMOIRE/SIGNAUX_POST_V192.md` — 5 extracted signals (A: sensor selection,
  B: fast/full mode, C: DOM diff, D: auth_status_confidence, E: auth_indicator_negative)
  + 3 meta observations. Signals A+B converge (2/9 independent models).
- `_CADRE/INDEX.md` — updated (RADAR_USAGES, SIGNAUX_POST_V192, CONSENTEMENTS).
- Public GitHub push: `FAQ_LLM.md` + `GUIDE_LLM.md`. No release (documentation
  only — a release would mask the strategic work).

**Session strategy:** consultation of 9 independent LLMs designed to simultaneously produce
signal (SIGNAUX_POST_V192), FAQ, consents, and RADAR_USAGES.
Same method as the 03 June 2026 campaign (SIGNAUX_V18.md).

**State on exit:** v1.9.2 unchanged. Documentation enriched. Field work planned.
56 frictions / 23 sessions.

---

## 2026-06-10 — Session 22 cont. (v1.9.2 — modular scenarios, SoM linter, pre-push hook)

**Context:** v1.9.1 in production. Spec 41_ validated in PHASE_DOCUMENTATION.

**Work done:**

- `rpa.py` (v1.9.2) — `_aplatir_actions()`: inlines `declencher_scenario` sub-scenarios
  recursively (max 5 levels, explicit error).
- `rpa.py` — `_linter_som()`: verifies that `cliquer_som`/`remplir_som` have a positive
  integer `id` before any Playwright call. Fail-fast with structured JSON.
- `scenarios/schema.json` — `DeclencherScenario` definition added to `Action` `oneOf`.
- `scripts/hooks/pre-push` — new file (755), invokes `preflight-publication.sh`.
- `scripts/install.sh` — step 8: `git config core.hooksPath scripts/hooks`.

**State on exit:** v1.9.2 delivered, GitHub release published. Field work planned session 23.
56 frictions / 22 sessions.

---

## 2026-06-10 — Session 22 (v1.9.1 — security hardening validation)

**Context:** v1.9.0 in production. Empty backlog. Roadmap updated.

**Work done:**

- Backlog audit: v1.4.1 (journal hardening & security memory) identified as
  progressively implemented during sessions v1.6 → v1.9, never formally validated.
- Validation via the 4 tests from spec `36_HARDENING_V141.md`: T-A ✓ T-B ✓ T-C ✓ T-D ✓.
  Items checked: `/tmp/` fallback, fallback warning in `journal.py`,
  `RLIMIT_CORE = (0,0)`, ephemeral session cleanup.
- `shot.py` + `journal.py`: `__version__` bumped 1.9.0 / 1.6.0 → **1.9.1**.
- `10_ROADMAP.md`: updated v1.6.0 → v1.9.0 (delivered entries), v1.9.1 added.
- `36_HARDENING_V141.md`: status updated DELIVERED v1.9.1.

**State on exit:** `/opt/diwall/` to deploy (deploy.sh). 56 frictions / 22 sessions.

---

## 2026-06-10 — Session 21 (S-1 auth_indicator, S-2 --no-capture, v1.9.0)

**Context:** v1.8.0 in production. Real backlog: S-1 and S-2
(Gemini field signals). FR-51 doctrine, #36/#38/#41/#42 closed (sessions 18-19).

**Work done:**

- `shot.py` (S-1) — `--auth-indicator "<css>"`: after actions, checks selector
  visibility via `page.locator().is_visible()`. Adds `auth_status: "active"|"inactive"`
  to root JSON. Key absent if flag absent.
- `shot.py` (S-2) — `--no-capture`: skips `page.screenshot()`, SoM,
  PNG writes. `--no-capture + --som` and `--no-capture + capturer`: blocking errors
  before Playwright launch. Compatible with `--a11y`, `--sauver-session`, `--auth-indicator`.
- `rpa.py` — `--no-capture` passed to shot.py. `auth_indicator` read from
  scenario JSON root, passed via `--auth-indicator`.
- `scenarios/schema.json` — optional `auth_indicator` added to root properties.

**Tests:** T_S1_A through T_S2_D — all green (8/8).

**State on exit:** `/opt/diwall/` synchronised (deploy.sh). v1.9.0. 56 frictions / 21 sessions.

---

## 2026-06-09/10 — Sessions 19–20 (FR-54 to FR-58, v1.8.0 published)

**Context:** session 18 errata — venv recreated, `docs/` missing from
`deploy.sh`, `__version__` stuck at 1.7.3. Fixed before any validation.

**Work done:**

- `shot.py` (FR-54) — `--actions` file now supported in `--reprendre-session`
  mode (Mode B). Both modes are now symmetric.
- `shot.py` (FR-55) — `attendre_url` gains `attendre_changement: true` parameter:
  waits for an outgoing navigation before applying the pattern (avoids false positive
  on substring URL).
- `scripts/deploy.sh` — `docs/` added to deployment list.
- `scripts/install.sh` — log directory permission check corrected `770` → `2770`.
- `CLAUDE.md` created at root — automatic Claude Code pre-flight: 5 non-negotiable
  rules including credential-in-shell prohibition and mandatory `GUIDE_LLM.md` pre-read.
- `docs/GUIDE_LLM.md` v1.8 — security block at top + 4 pitfalls
  (FR-54, FR-55, FR-56, FR-58 DIWALL_VAULT_DIR vs DIWALL_CONF).
- `docs/RETOUR_EXPERIENCE.md` — frictions #52–#56, session 19 summary.
- `docs/RADAR_MODELES.md` created — raw observation log on LLM behaviour with Diwall
  (2 entries: Claude Sonnet pre-fixes / Gemini Flash).

**Key decision:** `RADAR_MODELES.md` public, no editorial filter. The visibility doctrine
says silence on *promotion*, not on reality. False positives are included — they are the signal.

**Gemini Flash benchmark:** same multi-target exercise, post-fixes. Results
correct, `depuis_vault` used consistently, curl trap ignored. Single drift:
FR-58 (DIWALL_VAULT_DIR), self-corrected. Validation of perception/action doctrine.

**Commits:**
- `84100a1` — feat(v1.8): wait primitives, nettoyer_overlay, vault symlink fix, deploy docs
- `6982639` — fix(v1.8): FR-54 --actions file in Mode B, FR-55 attendre_url attendre_changement
- `7c84e01` — fix: neutralise client name in session 19 summary
- `9ca4d85` — docs(v1.8): FR-58 DIWALL_VAULT_DIR vs DIWALL_CONF, fix obsolete mentions

**Release:** `v1.8.0` — tag created, pushed, GitHub release published in English.

**State on exit:** production `/opt/diwall/` synchronised. 56 frictions / 19 sessions.

---

## 2026-06-09 — Session 18 (FR-47 to FR-53, v1.9)

**Context:** PHASE_EXECUTION validated by operator after co-planning with Gemini.
6 frictions to implement (FR-47, FR-48, FR-49, FR-50, FR-53; FR-52 cancelled).
Incomplete JSON schema (refs without definitions).

**Work done:**

- `lib/vault.py` (FR-47) — symlink security: `glob.glob` replaced by
  `os.walk(followlinks=False)`. All 4 T_CONF tests pass. Invariant: recursive
  traversal cannot escape the vault directory via a symbolic link.

- `_CADRE/GOUVERNANCE/PROTOCOLE_CLOTURE.md` (FR-48) — instruction n°4 completed:
  purge of orphaned `.tmp` files in `/opt/diwall/` (`find … -maxdepth 1 … -delete`).

- `shot.py` (FR-49/50) — 5 new actions in `executer_actions()` dispatcher:
  `attendre_url`, `attendre_selecteur_present`, `attendre_absence`,
  `attendre_reseau_calme`, `nettoyer_overlay`. Design point: `nettoyer_overlay`
  uses `visibility:hidden` (not `display:none`) to avoid invalidating SoM
  coordinates calculated before masking.

- `lib/vector.py` (FR-53) — new optional ChromaDB interface. DB_PATH cascade:
  `DIWALL_VECTOR_DB` env → `diwall.conf.vector_db` → `_CADRE/MEMOIRE/`
  (if sibling) → `~/Vaults/Diwall/chroma_db`. Lazy imports (chromadb, requests).

- `scenarios/schema.json` — 5 JSON Schema definitions added (AttendreUrl,
  AttendreSelecteurPresent, AttendreAbsence, AttendreReseauCalme, NettoyerOverlay),
  `additionalProperties:false` on each. Validation: 0 orphan `$ref`.

- `scripts/deploy.sh` — `lib/vector.py` added to `CODE_FILES`.
- `scripts/install.sh` — `/var/log/diwall/preuves` creation + permission checks.
- `docs/GUIDE_EXPLORATION.md` created (exploration/execution doctrine, SoM, SKILL_name.md).
- `docs/GUIDE_HUMAIN.md` created (step-by-step operator guides, pitfall table).
- `docs/GUIDE_LLM.md` updated (vault cascade v1.8, 5 v1.9 actions, CLI pitfalls).
- `docs/RETOUR_EXPERIENCE.md` updated (session 18).

**Key decision:** `nettoyer_overlay` without automatic heuristic — explicit CSS selector
mandatory. Reason: a heuristic that masked legitimate content would make regression
diagnosis impossible.

**Discovery:** `vector.py` had not been added to `deploy.sh` at creation time.
Addition during session detected during consistency check.

**Commit:** `01c9d8a` — feat(v1.9): 5 wait primitives, nettoyer_overlay, vector.py, vault symlink fix

**State on exit:** `main` up to date, production `/opt/diwall/` synchronised.
53 frictions / 18 sessions.

---

## Session 30 — 15 June 2026

**Work done:**

- Matomo tracker added to `site_internet/index.html` (site `__DOMAINE_OPERATEUR__`,
  ID 7, operator's Matomo instance). Deployed via `deploy-site.sh`.
- Friction #65 documented in `docs/RETOUR_EXPERIENCE.md`: selector `a.addSite`
  vs `button.addSite` (error), Vue.js framework vs AngularJS hypothesis (error),
  mandatory `remplir` primitive for Vue fields, 4000 ms pause required.
- Task sheet created: `_CADRE/SPECIFICATIONS/PROCEDURES_LLM/TACHE_matomo-ajouter-site.md`.

**Decision:** no version bump — `site_internet/` is outside the public repository,
no Diwall code modified.

---

## Session 26 — 12 June 2026

**Work done:**

- `docs/GUIDE_LLM.md` — 5 rules documented from E2E field validation (v1.9.3):
  - FN9: correct `defiler` fields (`px`/`selecteur`) — wrong/correct block added
    to prevent confusion with `direction`/`pixels`
  - FN6: `:nth-match()` syntax — cannot be chained as a suffix; must wrap the full selector
  - FN5: domain names in `<a>` selectors → strict mode violation; navigate via direct URL
  - FN7: `attendre_reseau_calme` + synchronous long server operation → fixed 30s screenshot
    timeout not controllable by `--timeout`; `pause` pattern documented
  - FN8: mutating `evaluer` dispatched before Diwall timeout → verify server state
    before relaunching the scenario

**Version:** GUIDE_LLM.md v1.9 (doc only — no Diwall version bump).

**Commit:** `8a59e36` — docs(GUIDE_LLM): add FN5–FN9 rules from Sillage E2E validation

---

## Earlier sessions

Sessions 1 to 17 are documented in:
`~/git/Diwall/_CADRE/MEMOIRE/ADDENDUM_*.md`
and in `docs/RETOUR_EXPERIENCE.md`.
