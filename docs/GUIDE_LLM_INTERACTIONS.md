# Diwall — Interactions guide (SoM, selectors, dialogs, assertions)

<!-- notice-version: 1.1 -->
Version 1.1 — June 2026

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
1. `#id` — most stable (avoid if generated randomly by framework)
2. `[name=…]`, `[aria-label=…]`, `[title*=…]`, `[data-*=…]` — semantic attributes
3. `:has-text("…")` — last resort, breaks on i18n changes

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

---

## Error recovery — Stop-and-Search rule (bloquant)

If an action returns `succes: false` or a Playwright error, you must:

1. Query the local RAG (`search-index.py`) on the exact error message
2. Re-read the relevant section of this guide
3. Declare the analysis: cause identified, rule violated
4. Propose the correction

---

## Current limit — Shadow DOM and Web Components

Diwall's SoM injection uses `document.querySelectorAll()`, which does **not** traverse Shadow
DOM boundaries. Elements encapsulated inside a Shadow Root (Web Components built with Angular,
Lit, Stencil, etc.) are invisible to Diwall's numbering.

**Practical impact:**
- `cliquer_som` and `remplir_som` cannot target elements inside Shadow Roots
- The SoM overlay shows no number for Web Component interactive elements
- `a11y_tree` may also be incomplete for components with shadow content

**Workaround — open Shadow DOM via evaluer:**
```json
{
  "type": "evaluer",
  "script": "document.querySelector('my-component').shadowRoot.querySelector('button').click()"
}
```
Verify the root is accessible first:
```json
{"type": "evaluer", "script": "document.querySelector('my-component').shadowRoot !== null"}
```

**Coming in v1.13.0:** `--shadow-dom` flag — recursive SoM traversal of open Shadow Roots,
disabled by default to preserve indexing consistency on standard DOM projects.

**Permanent limit — closed Shadow Roots:** `{mode: 'closed'}` Shadow Roots are inaccessible
from any external script, including Playwright. This is a browser security boundary.

**No `actions_v2.json` / `_v3.json` in `/tmp/` without this step.**
