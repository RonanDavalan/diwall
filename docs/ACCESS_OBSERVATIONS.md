# Diwall — Access observations

Version 1.0 — July 2026 (v1.19.0)

A neutral, dated log of real access outcomes encountered while using Diwall
against public sites. Purpose: give future runs (and future models) factual
grounding instead of repeated guessing about which targets are reachable.

**What this file is not:** a verdict on any site's legitimacy, a WAF-vendor
classifier, or a call to action. An entry records what was observed, on what
date, with what Diwall configuration — nothing about the target's intent or
worth. See `docs/GUIDE_LLM.md` section "WAF and Cloudflare blocking" for the
doctrine behind this neutrality (perceive the friction, do not moralize
about it).

**Scope note:** only aggregate, already-published campaign data is recorded
here for now — see `docs/RETOUR_EXPERIENCE.md` FR-77/FR-79 for the sourcing.
Per-site entries will be added once field runs log target identity alongside
outcome as a matter of course; this file grows from real runs, never from
a reconstructed panel assembled without a genuine intent to visit each site
(see FR-79's note on why a synthetic 23-site re-test was declined).

---

## 2026-06-27 — Commercial search campaign, 23 sites (FR-77)

**Context:** real purchase research (reconditioned game consoles, budget
≤ 200 €), francophone e-commerce sites. Diwall v1.14.0, no `--stealth`
(introduced later, v1.15.0).

| Outcome | Count | Share |
|---|---|---|
| Blocked 403 (WAF) | 9 | 39% |
| Timeout / no HTTP response | 6 | 26% |
| 404 (guessed URL wrong) | 5 | 22% |
| Accessible (HTTP 200 + content) | 2 | 8.7% |

**23 sites were targeted; 22 results were recorded.** The four counts above sum
to 22, and the shares to 95.7 % — the outcome of the twenty-third site was
never written down. Since the URL list was not kept either (below), it cannot
be recovered. The shares are shares of the panel targeted; they are left as
they are rather than rebased on 22, because nothing establishes that the
twenty-third site went untested — only that its result went unrecorded.

Accessible sites were both SSR without a WAF. Blocked sites were major
retailers and reconditioning marketplaces. Individual site identities were
not logged in this run — only the aggregate is available (see
`docs/RETOUR_EXPERIENCE.md` FR-77).

---

## 2026-07-02 — Stealth benchmark, quantitative (FR-79)

**Context:** `--stealth` was found non-functional in production since v1.15.0
(a `playwright-stealth` 2.x API break silently no-op'd it). After the fix
(v1.16.0), measured on `bot.sannysoft.com` (`scenarios/test_stealth.json`).

| Signal | Without `--stealth` | With `--stealth` |
|---|---|---|
| `navigator.webdriver` | `true` | `false` |
| `navigator.plugins.length` | 0 | 3 |
| `navigator.languages.length` | 1 | 2 |
| Fingerprint tests failed | 12 | 0 |
| Fingerprint tests passed | 18 | 31 |

The two columns do not describe the same number of checks: 12 + 18 = 30
without `--stealth`, 0 + 31 = 31 with it. The benchmark page renders some
checks only when a signal is present, which plausibly accounts for the
difference — but that was not verified at the time, so the figures are
reported as counts and no total is claimed. In particular this is **not** a
"31 of 31" result.

**What this confirms:** `--stealth`, once actually applied, clears every
basic JS/browser fingerprint check on this benchmark. **What it does not
answer:** whether this would have changed FR-77's 39% block rate — that
panel's 23 URLs were never individually logged, and reconstructing a
commercial panel without a genuine purchase intent was declined as
indistinguishable from a load test on third-party infrastructure (see
`docs/RETOUR_EXPERIENCE.md` FR-79 for the full reasoning). TLS fingerprinting
(JA3/JA4) and Cloudflare Enterprise behavioural analysis remain untested by
this benchmark — `playwright-stealth` does not claim to cover either.

---

## Adding an entry

When a real run produces a genuine access observation (not a synthetic
re-test), append a dated section above the "Adding an entry" heading:

- Date, target (public name, no internal codenames), Diwall version and
  flags used (`--stealth`, `--mode`, etc.)
- Outcome: accessible / blocked (403, timeout, other) — cite the actual
  `http_status` or symptom from the JSON output
- No qualification of the target beyond the observed outcome
