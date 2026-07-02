# Diwall — Interactions guide (SoM, selectors, dialogs, assertions)

<!-- notice-version: 1.4 -->
Version 1.4 — July 2026 (v1.17.0) — --som-rafraichir stable identity, cross-origin iframe primitives

Load this notice when: timeout on `cliquer`, CSS/showModal dialog, SoM IDs, strict mode
violation, nth-match error, evaluer assertions, DOM mutations.

---

## Set-of-Mark (SoM) — how to use it

`--som` injects a JS overlay that numbers all visible interactive elements.
You read `capture_som` (annotated PNG), identify the number you need,
pass that ID to `cliquer_som` or `remplir_som`.

**Why SoM is better than `cliquer_visuel`:**
- No LLM vision call → instant (vs ~32s)
- Exact DOM click (vs ±12% coordinate estimation)
- Works with any model, any size

`cliquer_visuel` remains available as fallback for canvas and non-ARIA components.

---

## Decision tree — how to target an element

1. Element visible in first capture → `cliquer_som id=N`
2. Element not yet visible, but present in HTML with a stable attribute (`#id`, `[name]`, `[data-*]`, `[aria-label]`) → `cliquer { "selecteur": "…" }`
3. Element appears after mutation, no stable attribute → `cliquer_visuel` (~32s, last resort)
4. Element is in the DOM but CSS-hidden or behind showModal() → `cliquer { "selecteur": "…", "force": true }` (v1.11.0)
5. Element not yet in the DOM, or `force` fails → `evaluer` JS `.click()`

**Priority order for stable CSS selectors:**
1. `[data-testid=…]`, `[data-test=…]` — dedicated test attributes (v1.15.2, DeepSeek D2)
2. `#id` — stable (avoid if generated randomly by framework)
3. `[name=…]`, `[aria-label=…]`, `[title*=…]`, `[data-*=…]` — other semantic attributes
4. `:has-text("…")` — last resort, breaks on i18n changes

**Why `data-testid` ranks first (v1.15.2):** many applications expose attributes
dedicated to automated testing (`data-testid`, `data-test`), deliberately kept
stable across style and markup refactors — unlike `#id` or CSS classes, which
frameworks frequently regenerate. Playwright targets them natively:
```json
{"type": "cliquer", "selecteur": "[data-testid=\"btn-confirm\"]"}
```
If the target application exposes `data-testid`, prefer it over `#id` even when
both are present.

---

## `force: true` on `cliquer` — bypass interactability checks (v1.11.0)

Playwright refuses to click an element if it or an ancestor is CSS-hidden (`display:none`,
`visibility:hidden`), overlapping, or inside a `showModal()` dialog. The current
workaround requires switching to `evaluer` JS. `force: true` keeps you in the same verb.

```json
{"type": "cliquer", "selecteur": "#dialog-confirm button[type=submit]", "force": true}
```

**When to use `force`:**

| Situation | Action |
|---|---|
| Element visible, no obstruction | `cliquer` without `force` |
| Element in DOM but CSS-hidden or obstructed | `cliquer` with `"force": true` |
| Element not yet in the DOM | `evaluer` JS `.click()` |

**`force` is NOT available on `cliquer_som`** — `cliquer_som` uses coordinate-based click
(`page.mouse.click(x, y)`) which already bypasses interactability checks natively.

**If `force` fails** (element does not exist in DOM): fall back to `evaluer`.

---

## CSS-hidden and JS-controlled containers — the timeout trap

`Playwright: Locator.click: Timeout Xms exceeded` on an element you can see in the DOM
does **not** mean the selector is wrong. It means Playwright refuses to click because the
element (or one of its ancestors) is hidden via CSS or JS.

**Two solutions — prefer `force` first:**

```json
// Solution 1 — force: true (v1.11.0, preferred when element is in the DOM)
{"type": "cliquer", "selecteur": "[data-testid='btn-confirm']", "force": true}

// Solution 2 — evaluer JS (fallback when force fails or element absent from DOM)
{"type": "evaluer", "script": "document.querySelector('[data-testid=\"btn-confirm\"]').click()"}
```

**This rule covers all hidden-container patterns (REX #61–63, FR-57, FN10–FN12):**
- CSS `display:none → block` dialogs (app confirmation modals)
- `showModal()` native `<dialog>` elements
- CSS toggle-switch hidden `<input type="checkbox">`
- Button that opens a CSS modal (FN10): the trigger button itself may timeout

**FN11 — `capturer` timeout while a CSS modal is open:**
When a CSS modal is open (JS show/hide), `capturer` may time out (even at 120s) because
Playwright waits for the page to stabilise before screenshotting. Remove any intermediate
`capturer` while the modal is in the open state. Capture only after it closes.

**FN12 — Batch deletion dialog (native `<dialog open>`):**
```json
{"type": "evaluer", "script": "Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Appliquer')?.click()"},
{"type": "pause", "ms": 1000},
{"type": "evaluer", "script": "Array.from(document.querySelectorAll('dialog[open] button')).find(b=>b.textContent.includes('Supprimer'))?.click()"}
```

**FN13 — Batch checkboxes — prefer a single `evaluer` over multiple `cliquer`:**
```json
{"type": "evaluer", "script": "(function(){ var cibles=['v1','v2']; Array.from(document.querySelectorAll('input[type=checkbox]')).filter(cb=>cibles.includes(cb.value)).forEach(cb=>{cb.checked=true;cb.dispatchEvent(new Event('change',{bubbles:true}));}); })()"}
```

**Conditional button with JS guard — silent no-op on `cliquer` (REX #62):**
```json
[
  {"type": "evaluer", "script": "document.querySelector('[data-testid=\"select-action\"]').value = 'delete'"},
  {"type": "cliquer", "selecteur": "[data-testid='btn-apply']"},
  {"type": "attendre_selecteur_present", "selecteur": "dialog#dialog-batch[open]"}
]
```

---

## `evaluer` — DOM/JS introspection

Use when you need to read a value from the page without parsing a screenshot.

```json
{"type": "evaluer", "script": "document.title"}
{"type": "evaluer", "script": "window.MyApp?.version ?? null"}
{"type": "evaluer", "script": "document.querySelectorAll('.row').length"}
```

Output appended to `evaluations[]` in JSON result:
```json
"evaluations": [{"index": 0, "script": "document.title", "valeur": "My App — home"}]
```

Non-JSON-serializable values fall back to `str(value)` with `"serialisation": "str"`.
Never inject user input or URL parameters into the script.

**Security restriction — `--no-evaluer` (v1.15.1):**
`evaluer` executes arbitrary JavaScript in the browser context. In production scenarios
involving authentication forms, financial data, or any sensitive interface, the operator
may disable this action entirely by passing `--no-evaluer` to shot.py or rpa.py.

When `--no-evaluer` is active, any `evaluer` action in the scenario raises an error
and the run aborts. This flag is an operator-level decision — you cannot bypass it.

**What this means for you:** if `evaluer` is available and you use it to read a value,
you are responsible for ensuring your script does not extract sensitive data
(passwords, tokens, cookies, session identifiers). Do not write scripts that return
`document.cookie`, `localStorage`, or any authentication token — even if the intent
is diagnostic. These values will appear in `evaluations[]` in the JSON output.

---

## Assertions on `evaluer` — three keys (rpa.py only)

Three mutually exclusive assertion keys — choose one per action:

| Key | Comparison | Valid return types |
|---|---|---|
| `attendu` | Strict equality (`==`) | Any (str, int, bool) |
| `contient` | Substring (`in`) | `str` only |
| `motif` | Python `re.search()` regex | `str` only |

**`attendu` — strict equality (existing behaviour):**
```json
{"type": "evaluer", "script": "document.querySelectorAll('.row').length", "attendu": 3}
{"type": "evaluer", "script": "!!document.querySelector('.logged-in')", "attendu": true}
```

**`contient` — substring (v1.11.0):**
```json
{"type": "evaluer", "script": "document.title", "contient": "User management"}
{"type": "evaluer", "script": "window.location.href", "contient": "view=dashboard"}
```

**`motif` — Python regex (v1.11.0):**
```json
{"type": "evaluer", "script": "window.location.href", "motif": "view=dashboard$"}
{"type": "evaluer", "script": "document.title", "motif": "^My App — "}
```

**Error on wrong type:** if the return value is not `str` and you use `contient` or `motif`,
rpa.py exits 1 with an explicit message. Use `attendu` for int and bool.

**Error on conflict:** if two assertion keys are present on the same action, rpa.py exits 1.

`shot.py` ignores all assertion keys (they are rpa.py-only).

---

## Verify you are on the right page (pattern — item F)

Always end a navigation with a semantic assertion, not just `attendre_selecteur_present`
on a generic selector.

```json
// With <title>
{"type": "evaluer", "script": "document.title", "contient": "User management"}

// Without <title> or generic title — use h1
{"type": "evaluer",
 "script": "document.querySelector('h1')?.textContent.trim() ?? ''",
 "contient": "User management"}
```

**On error pages (404/500):** the title will be "404 Not Found" or the error template
title — `contient` fails cleanly with exit 1. No extra code needed.

---

## SoM mutations — always recapture after DOM changes

SoM IDs are computed at the moment of the `--som` capture. Any DOM change
(cookie banner, modal open/close, overlay, scroll) invalidates previous IDs.

**Rule:** after any action that adds or removes visible DOM elements, run a new
`shot.py --som` before using `cliquer_som` or `remplir_som`.

**SoM after scroll:** `defiler` also invalidates IDs. After scrolling, recapture.
`capturer` alone does **not** recalculate SoM IDs — it produces a PNG without
a new `elements_som`. Run a new `shot.py --som` for a fresh index.

**Off-screen elements warning:**
```json
"som_hors_viewport": 3,
"avertissement_scroll": "3 élément(s) interactif(s) hors viewport — utilisez defiler avant cliquer_som"
```
Scroll to the element before using `cliquer_som`:
```json
{"type": "defiler", "selecteur": "input#otp-field"},
{"type": "remplir_som", "id": 7, "valeur": "123456"}
```

**SoM excludes closed `<dialog>` elements** (no `open` attribute) — intentional.
A closed dialog is not interactable. Use CSS selectors for buttons inside closed dialogs.

**Stable identity resolution — `--som-rafraichir` (v1.17.0):** by default,
`cliquer_som`/`remplir_som` re-index the live DOM at click time — this is a
mechanism against *identity* drift, not staleness: if an element appears or
disappears **before** your target in DOM order between the `--som` capture and
the click (a cookie banner closing, a modal opening), `id: N` silently
resolves to a **different** element than the one numbered N in the screenshot.
Recapturing SoM (the rule above) reduces the exposure window but does not
eliminate it on a page that keeps mutating.

`--som-rafraichir` closes this gap: SoM injection stamps each numbered element
with `data-dw-som-id="N"`, and resolution looks up that attribute instead of
re-indexing. If the exact element is still in the DOM, `id: N` always resolves
to it — regardless of what else changed around it. If it was removed: an
honest "élément SoM non trouvé" error, never a click on the wrong target.
Opt-in, zero effect on default behavior — recommended on pages with frequent
DOM churn between capture and action (long scenarios, live-updating dashboards).

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --som --som-rafraichir \
  --actions '[{"type":"cliquer_som","id":5}]'
```

`boussole.som_rafraichir_actif: true` when active.

---

## DOM mutations in Mode A — mixing SoM and CSS selectors

```json
[
  {"type": "cliquer_som", "id": 3},
  {"type": "pause", "ms": 800},
  {"type": "capturer", "nom": "after_click"},
  {"type": "cliquer", "selecteur": "#dialog-action button[type=submit]"},
  {"type": "pause", "ms": 2000}
]
```

SoM is your exploration map. CSS selectors are your execution GPS.

**`capturer` to inspect intermediate state** without breaking Mode A: generates PNG
without interrupting the session. Replaces Mode B at lower cost.

---

## Selectors — pitfalls and patterns

**Domain names in link selectors — strict mode violation (FN5):**
A domain like `example.fr` typically appears in multiple `<a>` elements (header, clone
link, breadcrumb). `a:has-text("example.fr")` hits all of them → strict mode refusal.
Never use domain names as link text selectors. Navigate by direct URL instead.

**`:nth-match` chaining rule (FN6):**
```
// WRONG — "nth-match engine expects non-empty selector list and an index argument"
button:has-text("Texte"):nth-match(2)

// CORRECT — :nth-match() wraps the full selector expression
:nth-match(button:has-text("Texte"), 2)
```

**Playwright extended selectors** supported in `cliquer` and `remplir`:
`:has-text("…")`, `:visible`, `:nth-match(N)` work reliably.
Avoid relational pseudo-selectors (`:left-of`, `:right-of`, `:near`) — version-sensitive.

---

## Reconnaissance before mutation (bloquant)

Before writing any mutating action on a feature **never previously tested with Diwall**:

```bash
# Step 1 — Visual map
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <target_url> --som --a11y

# Step 2 — DOM inventory
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/diagnostic_dom.json \
  --url <target_url> --no-capture

# Step 3 — Read eval results, extract selectors
# Step 4 — Write complete operational scenario in one pass
# Step 5 — Execute once via rpa.py
```

**Forbidden:** launching a mutating action without completing steps 1–3.

**Diagnostic-driven strategy (v1.15.2, ChatGPT C2):** `diagnostic_dom.json` is not
a passive readout — its `evaluer` results should set the strategy for the
remainder of the run:

| `diagnostic_dom.json` result | Strategy |
|---|---|
| No modern framework detected (static DOM) | `--mode fast` (`--no-capture --a11y`) — no need to pay for screenshots on a static page |
| Shadow root count > 0, or Angular/Lit/Stencil detected | Add `--shadow-dom` to every subsequent `--som` call, and expect stability waits to need `attendre_selecteur_present` more than `attendre_navigation` |
| `data-testid`/`data-test` attributes present in the inventory | Use them as primary selectors (see priority order above) instead of `#id` |

**Citizenship self-regulation (v1.15.2, ChatGPT C1):** `citoyennete` (root and
`boussole`) is not only an audit trail for the operator — the agent can read it
mid-strategy. If `pages_visitees` or `actions_executees` approaches the caps
configured in `diwall.conf` (`max_pages_par_run`, `max_actions_par_run`),
narrow the exploration scope or end the run cleanly before hitting
`plafond_atteint` (see the citizenship cap behavior notice in
`GUIDE_LLM_MONITORING.md`).

**Aggressiveness index — `citoyennete.indice_agressivite` (v1.16.0, Grok G1):**
ratio of mutating actions (`cliquer`, `cliquer_som`, `cliquer_visuel`,
`remplir`, `remplir_som`, `evaluer`, `attendre_mfa_ntfy`) over the total
actions executed in the run — logged in the journal alongside every run.
Recommendation for open-ended exploration: keep this ratio under 0.3 (30%
writes). A high ratio during exploration signals the agent is mutating the
target more than it is observing it — a citizenship-adjacent concern, not a
runtime-enforced cap.

---

## Error recovery — Stop-and-Search rule (bloquant)

If an action returns `succes: false` or a Playwright error, you must:

1. Query the local RAG (`search-index.py`) on the exact error message
2. Re-read the relevant section of this guide
3. Declare the analysis: cause identified, rule violated
4. Propose the correction

---

## Shadow DOM and Web Components — `--shadow-dom` (v1.13.0)

By default, Diwall's SoM injection uses `document.querySelectorAll()`, which does **not**
traverse Shadow DOM boundaries. Elements encapsulated inside a Shadow Root (Web Components
built with Angular, Lit, Stencil, FAST, etc.) are invisible to the numbering.

### Enabling Shadow DOM traversal

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --shadow-dom --som
```

Or in a scenario file (field `shadow_dom: true` at the root level):
```json
{
  "url": "https://target.local/",
  "shadow_dom": true,
  "actions": [...]
}
```

When active, `boussole` includes `"shadow_dom_actif": true`.

### What changes with `--shadow-dom`

All three SoM functions (`_SOM_INJECTER_JS`, `_SOM_COMPTER_HORS_VIEWPORT_JS`,
`_SOM_TROUVER_JS`) switch to a recursive `queryShadowAll` walker that descends into
every open Shadow Root in document order. The indexing is consistent across the three
functions — the element numbered K by injection is always the element returned for `id: K`
by the finder.

`cliquer_som` and `remplir_som` work normally on shadow elements once `--shadow-dom` is active.

### When to enable it

Use `--shadow-dom` when:
- The target page uses Angular, Lit, Stencil, FAST, or similar Web Component frameworks
- You see interactive elements in `a11y_tree` that receive no SoM number
- `cliquer_som` reports "element not found" for elements visually present on screen

Do **not** enable it on standard DOM projects (no Web Components): no benefit, slight
performance cost from the recursive tree walk.

### Fallback for ad-hoc shadow access (without --shadow-dom)

If only one or two elements are in a shadow root:
```json
{"type": "evaluer", "script": "document.querySelector('my-component').shadowRoot.querySelector('button').click()"}
```

Check root accessibility first:
```json
{"type": "evaluer", "script": "document.querySelector('my-component').shadowRoot !== null"}
```

### Permanent limit — closed Shadow Roots

Shadow Roots created with `{mode: 'closed'}` are inaccessible from any external script,
including Playwright and Diwall. This is a browser security boundary — `--shadow-dom` has
no effect on them. Closed Shadow Roots are rare in public-facing Web Components; the
majority use open mode.

**Perceptual fallback ladder when SoM cannot reach an element (v1.15.2, Kimi K2):**
when `--shadow-dom` still leaves an element untargetable (closed Shadow Root, or any
other structural boundary), do not jump straight to `cliquer_visuel`:

1. `--som` (`+ --shadow-dom` if applicable) — fastest, exact DOM click.
2. `--a11y` (`a11y_tree`) — semantic landmarks (roles, names) often expose an
   accessible name for elements SoM cannot number; use it to build a `cliquer`
   selector via `aria-label` or role.
3. `cliquer_visuel` — last resort (~32s, coordinate estimation). Only once 1 and
   2 have been tried and failed.

This ladder minimizes cost: SoM is near-free, `a11y_tree` is a single extra
snapshot, `cliquer_visuel` is the expensive option and should stay a fallback,
not a default.

**No `actions_v2.json` / `_v3.json` in `/tmp/` without this step.**

---

## Iframes — cross-origin primitive, no SoM inside (v1.17.0)

Same-Origin Policy blocks JS injection (and therefore SoM numbering) from
reaching into a cross-origin iframe's content — a hard browser security
boundary, unlike Shadow DOM (same document, just encapsulated). Playwright's
`frame_locator()` bypasses this via CDP, not JS injection — Diwall exposes it
through two scoped actions:

```json
{"type": "cliquer_iframe", "iframe_selecteur": "iframe#paiement", "selecteur": "button.valider"}
{"type": "remplir_iframe", "iframe_selecteur": "iframe#paiement", "selecteur": "input[name=cvv]", "valeur": "depuis_vault", "vault_cle": "cvv"}
```

`remplir_iframe` supports `depuis_vault`/`depuis_vault_totp` exactly like
`remplir` — never a plaintext credential in a scenario.

**No SoM numbering inside the frame (cadrage assumé) :** you must know or
discover the inner CSS selector yourself — via `evaluer` if the iframe is
same-origin (`document.querySelector('iframe').contentDocument...`), or from
the target application's own documentation/markup if cross-origin. This is a
first unlock, not full iframe-aware SoM — same honesty as the closed Shadow
Root limit above.

**On failure:** Playwright's own interactability rules still apply inside the
frame (e.g. `.fill()` refuses a `contenteditable` element in a read-only
state) — `"force": true` is available on `cliquer_iframe`, matching `cliquer`.
