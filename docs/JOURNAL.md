# Development journal — Diwall

History of decisions and discoveries by session, in reverse chronological order.

---

## 2026-08-07 — A same-day follow-up audit, cross-checked before acting on it

A second audit landed the same day as the fix above and found three more
real gaps: an exception message that listed every key name in a credentials
file when one was missing (harmless on its own, but a name like "totp_key"
tells a reader that two-factor authentication is configured before they've
authenticated at all), four error paths that hadn't been wired into the new
shared redaction module yet, and a script passed to the browser-evaluation
action that could carry a hard-coded secret straight into the persistent
log.

The credentials-file fix took a narrower shape than first suggested,
deliberately. A blanket keyword scan across an entire script would have
flagged completely ordinary code — looking up a page element named
"password" to read its state isn't the same as exposing one — so the check
instead looks only for the *structural* shapes an actual secret takes: a
JSON web token, or a long enough random-looking string. That misses a
secret typed as a plain word, but it also doesn't reject legitimate scripts
that merely mention a sensitive field by name.

One thing found on the way: two independent outside reviews of the fix
plan disagreed with an initial idea to group the follow-up work by which
file it touched, pointing out that the file in question already had
unrelated work scheduled in two other places — doing it a third way would
have meant three separate passes over the same code instead of one. The
plan was revised before anything was written.

A separate finding from the same audit turned out to be a false alarm: a
credentials file reported as world-writable was in fact a symlink, and a
symlink's own permission bits are cosmetic on Linux — what matters is the
permissions of the file it points to, which were already correctly
restricted. Worth remembering for whoever runs the next one of these.

## 2026-08-07 — Six independent audits kept finding the same leak under different names

A redaction function existed and worked correctly — but only one of the two
channels that carry Diwall's output called it. The persistent operations log
redacted a cookie value, a bearer token, a URL's query string before writing
it to disk. Standard output — what the LLM agent actually reads — did not.
An `evaluer` action that read `document.cookie` on an authenticated page, an
OAuth callback URL with a `?code=...` parameter, an exception message that
happened to quote a URL: all three reached the agent's context in the clear,
even though the exact same value would have been redacted one line later, on
its way to the log file.

The fix is a small shared module both programs now import, so the two
channels can no longer drift apart. A new flag makes the difference
observable from the output itself: neutralization is on unless a debug run
explicitly turns it off, and when it does, the JSON output says so.

A related pair of checks was tightened at the same time. A file holding
credentials that turned out to be readable beyond its owner used to print a
warning and continue; it now refuses to proceed. A missing dependency that
should never be missing on a real installation used to degrade silently into
running unchecked; it now stops with a clear message instead. And a form
field whose name looks like a password or token field is now rejected before
any value is typed into it — regardless of whether the scenario declared it
as a credential — closing a path where a plaintext secret could still slip
through an unmarked field.

## 2026-08-06 — A protection written for one program that touches credentials was missing from a second one

The tool that pre-validates a scenario before running it loads the entire
decrypted credentials file into memory to check that the keys it needs are
present, then hands the actual run off to a second program. The safeguard
against core dumps — refusing to let the operating system write a crash
snapshot containing whatever secrets happen to be in memory — had only ever
been applied to the second program, the one that actually uses the
credentials. The first program, which also holds the full file in memory for
that brief validation window, never got the same protection. One line,
fixed.

The static check written to catch this class of gap the first time it
surfaces was tried in a form that would have matched every file that merely
imports the credentials module, including three that only read local
configuration and never touch a credential value — a check that would flag
files it was never meant to flag, and consequently would never pass. Caught
before being relied on, by running it against the real codebase rather than
trusting that it was correct because its surrounding details (paths, naming
conventions, line numbers) checked out. Corrected to match only the specific
calls that actually load credential values, and re-run to confirm it now
fails on the unprotected file and passes once that file is fixed.

## 2026-08-06 — Four of this pass's findings were the previous pass's findings, unfixed

A third review of the same code, the same day as the second, found nineteen
new things. Four of them turned out to be exact repeats of findings from the
first review — same file, same line, same defect — carried forward twice as
"worth hardening eventually" and never actually revisited. That repetition
was the most useful thing this pass produced: it meant a fix aimed at the
one case in front of it, rather than at every place built the same way, was
the dominant failure mode across all three reviews, not an occasional one.
The response was to stop treating each finding as its own fix and instead
group them by what they actually shared, so the same mistake could only be
made once per shared mechanism rather than once per occurrence.

**A check for web addresses carrying embedded login credentials existed in
one of the tool's two places that build one, not both.** The stronger of
the two rejects an address whose scheme isn't right and one carrying a
username or password baked into it; the weaker, in a second program that
hands work off to the first, only checked the scheme. An address with
embedded credentials passed the weak check, was placed on the command line
of the process handing off the work, and only then reached the strong
check and got rejected — after a brief window where it was visible to
anything inspecting that process's command line on the same machine. The
two checks are now one, called from every place an address enters the tool
from outside, including a resume-a-previous-session path that had never
called either.

**A safeguard against reading credentials from an unlocked location
computed which folder to check without following symbolic links, while the
read that came right after did.** A link placed inside the correct,
unlocked location and pointing at a file anywhere else on disk passed the
check on its own location, and then had its actual target read regardless
of where that turned out to be. Two independent code paths had grown this
same gap — one checking a credentials file supplied directly, the other
resolving one by hostname — and both are fixed the same way now: resolve
the link first, check the result, read that. A legitimate link already in
active use, pointing at a different but equally protected location within
the same encrypted store, keeps working exactly as before; only a target
that lands outside any protected location is refused.

**A record meant to prove a credentials file hasn't been tampered with
didn't cover the field controlling which sites it can be used against.**
That field was added after the tamper check was first written, and never
folded into what the check actually covers — so an edit to which sites a
credentials file is authorised for could not trip an alarm meant to catch
exactly that kind of edit.

**An error message written to the permanent operations log wasn't put
through the same redaction its own output already gets on every other
channel.** A resolved credential is stripped from the tool's JSON output
before it's printed; the error text handed to the log was rebuilt
separately from the raw underlying exception and skipped that step. On the
one error actually seen this way, the message named the exact file the
credential had come from — and that filename carries the account it
belongs to. Fixed by reusing the already-redacted text instead of
rebuilding it, and every message elsewhere that names a stored file now
gives its name alone, not the folder path that gets there — the full path
was quietly exposing which local account the tool runs under.

**The existing redaction of a resolved credential has no minimum length by
design, and that turned the redaction itself into a tell.** On a list where
every other row shows a genuine value, the one row blanked out is
identifiable simply by being the only one masked. Loosening the threshold
would trade a full leak for a partial one, so instead the output now
separately reports how many values were blanked on a given run — enough for
a reader to know in advance that the view in front of them has holes,
without adding a second way to guess which row they cover.

**The most useful screenshot of an authenticated run never left the
temporary working folder.** Two different in-progress structures — extra
screenshots taken mid-scenario, and ones taken automatically during a long
wait — feed the same archiving step through two different shapes, and that
step only recognised one of them; the other passed a check that always
silently found nothing, on every single run. The screenshot taken right
after a successful sign-in is the one that reliably followed the shape
nobody was reading. Both shapes are now recognised, and a masking failure
found the same way — the browser call that blanks sensitive on-screen
fields can be refused mid-navigation, and the previous code took the
picture anyway, unmasked — now takes no picture at all on that path, with a
note in the output explaining why.

**Files and folders this tool writes on the operator's behalf are usually
owner-only by design, and that discipline had gaps.** A screenshot's own
permissions followed the operating system's default rather than an
explicit setting, since the underlying browser call ignores the containing
folder's mode entirely; the folders holding a run's archived evidence
inherited whatever the system happened to leave behind the first time they
were created, sometimes readable by more than the owner, and a later run
reusing that same folder never corrected it. Both are now set explicitly on
every write, including a one-time correction of folders already created
under the old, looser default. A saved reference file, used to detect
whether a page's behaviour changed between runs, stores whatever a
diagnostic script actually returned from the page — unlike every other
channel this tool writes to disk, that value went through no filter at
all. It now passes through the same one the operations log already uses,
and is written owner-only.

**Chaining one test scenario into another accepted any file path the
calling scenario supplied**, including one reaching outside the folder
scenarios are meant to live in — a scenario shared by someone else could
name an arbitrary file elsewhere on the machine running it. Restricted to
the intended folder; naming a scenario's location directly on the command
line, a normal and different use case, is unaffected.

**A named list of actions this tool must never take without a human
present had existed since an earlier release, and nothing in the code
actually consulted it.** A configuration file could name one of those
actions and the tool would silently treat it as an unrecognised setting
rather than refuse it outright — a lock with no bolt in it. It now refuses
outright, on the same footing as a malformed configuration file.

**Smaller fixes carried in the same pass:** a background process's use of
a local fallback queue didn't correct that folder's permissions if the
folder already existed from an earlier run, and the queue file itself
didn't refuse to follow a symbolic link placed at its path; a second
program shelled out for a piece of information the main one already reads
without a shell; three small setup scripts built a one-off command by
pasting a file path directly into program source rather than passing it as
an argument, so a path containing a stray quote could misbehave; two of
those same scripts parsed their own command-line options in a way that
silently ignored a flag placed anywhere but first; and a check for whether
a folder is actively mounted searched for the folder's name as a substring
of the whole mount table rather than matching the exact entry, which could
return a false "yes" from an unrelated folder whose name happened to
contain it.

The newest of the shared checks above lived only in a new file, and the
script that copies code into the running install hadn't been told about
it — caught before publishing rather than after, since publishing it as
written would have left the very next invocation of the installed copy
failing on a missing import. Two of the existing validation tests turned
out to depend on exactly the behaviour these fixes closed off — one by
chaining a scenario from outside its intended folder, the other by relying
on the enforcement gap in the never-consult list above — and were rewritten
to check the new, intended behaviour instead of the old one. Thirteen
suites replayed clean after that, save the same two pre-existing, unrelated
failures already on record. Deployed, and the two most consequential fixes
— the shared address check and the encrypted-directory link check — were
then run again for real against a live target, against the installed copy
this time, not the source tree.

---

## 2026-08-06 — Fixing a fix is not the same act as writing the code it touched

The previous entry closed a security pass with a set of thirteen fixes. This
one reran every test that had established the original findings, against
the corrected code — and then treated each fix itself as new code, subject
to the same scrutiny. Eleven of the thirteen held exactly as intended. Two
did not, and three introduced a defect of their own — the same pattern each
time: a fix proven against the one case in front of it, not against the
class of case it was meant to cover.

**None of the thirteen fixes were running anywhere.** They existed in the
source tree and nowhere else — the installed copy the documentation
actually points operators at still ran the code the fixes were written to
replace. Not an oversight: a real installation cycle was already a known
blocker on something unrelated, and the fixes had been sitting behind it.
Deployed now, last, after everything below — publishing them before fixing
what follows would have frozen two new problems into production in the
same gesture meant to close the old ones.

**A screenshot of an authenticated dashboard was still found in the clear.**
The previous fix redirected such screenshots to the encrypted secrets
store, but only when the operator had explicitly declared the page
authenticated. Left undeclared — which most runs are — the tool falls back
to believing whatever it is told, not what it can see: a login that
actually succeeded, with credentials it had just resolved from the
encrypted store itself, produced a full-page capture of a live dashboard
sitting unencrypted on disk. A second, narrower gap sat right next to it —
an operator using the "one credentials file per target" pattern this
project documents got neither an encrypted archive nor a clear-text one:
the archiving code checked only a global setting that mode doesn't use, and
silently archived nothing at all. Both are now closed: resolving any
credential during a run is itself treated as proof of an authenticated
page, whether or not the operator says so, and the destination now follows
whichever credentials file was actually in use. The seventy-six files left
over from before either fix existed — screenshots of pages that had been
authenticated, sitting world- or group-readable on the local disk — were
locked down and moved into the encrypted store, checksummed on the way.

**A session-expiry check went blind on the one target it exists to
protect.** An earlier fix stopped a harmless difference in a web address
from being mistaken for a security problem — but it did so by ignoring the
part of the address where a real session expiry actually shows up on this
target's own login page. The fix traded a false alarm for a missed one, on
exactly the case it was written for. The address is compared in full now,
normalised rather than stripped.

**A one-line cleanup broke something it never touched.** A note was added
that a housekeeping step, though harmless, ran more often than it needed
to — so a check was added to stop it running twice. That check outlived
the very reason the file gets reopened at all: a periodic log rotation,
which the surrounding code was explicitly written to survive. After a
rotation, the check now silently prevented a permission repair that used to
happen automatically. Removed; the repair runs every time again, as it did
before the note was written.

**A secrets filter, tightened, took a diagnostic feature down with it.**
An earlier pass had taught a log filter to recognise real credential
shapes it was missing. Widening it caught the missing shapes — and also
began catching ordinary field labels, CSS selectors and filenames that
merely resembled one by coincidence of length. On a routine page scan, this
silently discarded the one result an operator actually needed: the
inventory of input fields on the page, because one of those fields happened
to be typed "password". The filter is now applied structurally — value by
value inside a scanned page, not to the page's result as one long string —
and only treats an isolated, punctuation-free string as a candidate
keyword, so an ordinary sentence stops being mistaken for a token.

**A rare failure path in the accessibility-snapshot redaction fell back the
wrong way.** If the browser call that finds and masks sensitive field
values failed mid-run, the previous version returned the snapshot
unredacted rather than not at all — exactly backwards for a step whose only
job is withholding that value. It now withholds the whole snapshot on that
path instead, with a flag in the output noting why.

**Smaller fixes carried in the same pass:** a retention policy meant to
purge old evidence in days was deleting by calendar month instead, which
could discard six-day-old evidence the moment the calendar turned; a
checkpoint file and a monitoring run's saved output were written at the
process's default file permissions rather than the owner-only mode used
elsewhere; and a two-line note documenting an intentionally-idempotent
operation was written as a stale comment instead of removed.

The twelve validation suites that could be replayed offline came back
green except for the same two pre-existing, unrelated failures already on
record. The fixes above were then run for real against a live authenticated
target: the password-leak check from the previous entry still holds on the
deployed copy, and a full login performed with no authentication flag set
and only a per-target credentials file in use archived its screenshot to
the encrypted store on the first try, exactly as intended.

---

## 2026-08-05 — Running the tool against itself found what reading it did not

Every review so far had been static: reading the code, reasoning about what
it does. This one ran it — nine real invocations against a live,
authenticated target, checking what actually came back rather than what the
code suggested would.

**A filled password field could show up in the accessibility snapshot.**
`--a11y` (and `--mode fast`, which forces it on) asks the browser for its
full accessibility tree, and that tree includes the current value of every
input on the page — password fields included. The screenshot masking and the
numbered-element listing had both been fixed to withhold this exact value in
an earlier pass; the accessibility snapshot is a fourth, separate output
channel, and nothing had ever been asked whether it needed the same
treatment. It was the most-recommended way to confirm a login had
succeeded — the guide pointed operators at the one output that was still
leaking. Two independent fixes now close it: the accessibility snapshot text
has any value matching a known sensitive field redacted before it is
returned, and, separately, every credential value a run actually resolves
from the encrypted secrets store is tracked for the run's duration and
stripped from the entire JSON result — whichever output channel it might
have ended up on, including ones nobody has found yet.

**A screenshot of an authenticated page was archived in the clear,
indefinitely.** Any run classed as a write (which, out of caution, includes
a plain diagnostic script) copies its screenshots into a standing archive
for later reference — outside the encrypted secrets directory by default,
world-readable to the local machine's operator group, never purged. A
screenshot of a signed-in dashboard is not meaningfully different from the
session cookie that got the tool there, and the cookie was already
protected. The archive now follows the same rule: a screenshot taken on an
authenticated page is only kept if the encrypted secrets directory is
mounted, and it is written there rather than to the general log location.
Off that directory, nothing is archived at all — the screenshot stays only
in the run's own temporary folder. Archived files are now owner-only, with
an optional retention limit.

**Three unrelated modules each hardcoded the same configuration path,**
silently ignoring the environment variable that every other part of the
tool already honours to redirect it. The practical effect: an operator who
installs the packaged distribution and configures a private notification
relay for two-factor codes — precisely to avoid sending them through a
public service — got the public service anyway, without any indication that
their configuration had been read and discarded. All three now share the
one function that already resolves this correctly.

**The operations log's secret-detection filter matched words, and secrets
have shapes, not words.** A session identifier, a bearer token, an API key
and a signed authentication token all have recognisable structures that
contain none of the keywords the filter was searching for — confirmed with
the exact values that slipped through: a session cookie, a synthetic API
key, and a real-format signed token, none of which literally spell out the
word the filter was looking for. The filter now also matches by structure,
not only by vocabulary.

**Smaller fixes carried in the same pass:** a scenario-supplied file name
could climb out of its intended output folder with a relative path; a
session cookie's file could inherit stale permissions from a leftover
temporary file instead of always starting from a clean, owner-only one; a
distributed package applied looser file permissions to instance data
(target URLs, login sequences) than the from-source install already did;
and a run without any configuration file at all executed with no pacing and
no cap on how many pages or actions it would take — a safety limit that
depended on an optional file being present at all now applies by default.

Ten of the existing validation suites were replayed after these changes and
stayed green; the two that carry a documented, unrelated pre-existing
failure each still carry only that one failure.

---

## 2026-08-05 — A code-quality pass, and what a full install cycle still catches

A pass distinct from the security review above: every root script and
`lib/` module now carries a docstring header (why the file exists, its
inputs/outputs, its dependencies) — no author or date lines, since those
go stale the moment someone else touches the file and `git blame` never
does. Duplication the same pass turned up got factored out rather than
left standing: the Set-of-Mark selector list and visibility filter, copied
across seven near-identical JavaScript blocks; the `depuis_secrets`
credential-resolution logic, duplicated across three action types; a
mount-check block duplicated verbatim between two functions in the
encrypted-secrets module; and, in the RPA executor, a JSON error-emission
pattern repeated roughly fifteen times and three assertion branches that
shared everything but their message. Each factoring was checked against
the pre-change behaviour before being trusted — byte-for-byte comparison
of the generated JavaScript, and every branch of the credential resolution
exercised against fixtures — then the full validation suite replayed on a
real browser run.

Separately, a complete install/remove cycle of the `.deb` package, run on
a fresh machine rather than assumed to still work, found two real bugs
neither static review nor the existing test suite could have caught.
First: Chromium's binaries were downloading to `/root/.cache`, invisible
to the operator who runs the tool afterwards — `postinst` runs as root
regardless of who invoked the install, so the browser location silently
depended on where root's home directory happened to be. Second: asking
Playwright to install its own system library dependencies from inside
that same `postinst` deadlocks, because that call spawns its own package
manager transaction while the one already installing Diwall still holds
the lock. Both are fixed now — a browser path pinned independently of
`$HOME`, and the required libraries declared as ordinary package
dependencies instead of installed by a nested call that could never have
worked from that context.

The release also adds a security-disclosure policy, exact dependency
pins in place of open-ended floors, a continuous-integration workflow
that recompiles and re-validates on every push, and a changelog generated
from the package's own release history rather than maintained by hand
alongside it.

---

## 2026-08-05 — The same review, checked a second time, found what it had missed

A same-day cross-check of the security fixes below found one more instance of
the exact pattern they were meant to close. `--http-credentials` combined
with `--secrets` resolves its username and password through the same
function the other four call sites use, but without telling it which page it
was resolving credentials for. The mandatory origin declaration was still
checked for presence — a file missing it was still refused — but never
matched against anything, because nothing was passed to match against.

Confirmed directly rather than inferred: a fixture whose declared origin
named a different host than the actual target was accepted before the fix
and refused after it, with no other behaviour change (the existing
`--http-credentials` test suite, exercising the correct-origin case, stayed
green throughout).

The documentation had a gap of its own: the origin declaration this fix
depends on has been mandatory since last night, but no example anywhere
showed it — an operator following the docs literally to build a `--secrets`
file would have been refused at runtime with nothing but the error message
to explain why. Both guides now show it.

Separately, last night's fix for the password-in-listing leak duplicated its
detection logic verbatim across the two Set-of-Mark code paths (standard and
Shadow DOM), which the review that found the leak had itself flagged as the
wrong way to close it. Factored into one shared fragment, reused in both —
checked byte-for-byte against the original to confirm nothing but a comment
moved.

---

## 2026-08-05 — A security review found the gaps between protections that already existed

A static review of the full public codebase (shot.py, rpa.py, watch.py, the
lib/ modules, the shell scripts) found no dangerous primitive and several
protections that were already correct — masked screenshots, a neutralised
operations log, HTTP Basic Auth scoped by origin. What it found instead were
places where a protection applied rigorously in one spot had not been
extended to a symmetric one.

**A filled password field could show up in the numbered-element listing.**
Set-of-Mark labelling reads `el.value` as a fallback when an element has no
visible text — the right choice for a filled text input, the wrong one for a
filled password field, whose value is a secret, not a label. The screenshot
masking that already existed for this exact case did not extend to the JSON
output. It now does: password, token, secret, OTP and TOTP fields report an
empty label instead of their value.

**A designated credentials file (`--secrets`) stopped being bound to the page
that was actually loaded.** Without it, a credential is resolved from the
domain of the current page, and a redirection to another domain simply fails
to find a match — nothing gets typed. With a designated file, that binding
was gone: the file was read regardless of where the browser had actually
navigated. Every `--secrets` file must now declare which origins it applies
to; a file that omits this is refused outright rather than silently trusted
everywhere.

**A few smaller gaps closed alongside these two:** a saved session file
(cookies, effectively equivalent to being logged in) was written with default
file permissions instead of owner-only; a diagnostic script's return value
could carry a token or session identifier into the operations log verbatim;
a URL with embedded credentials (`user:pass@host`) survived log sanitisation
because only the query string and fragment were stripped, not the
credentials themselves; and a code delivered over the push-notification MFA
channel was accepted without checking that it looked like a code at all.

None of this involved a new feature or a changed public interface beyond the
`--secrets` file format, which now requires one more field.

The French, German and Spanish documentation was brought back in line with the
English source after the credential vocabulary was renamed. 430 segments were
retranslated in twenty minutes; the fingerprint cache reused the other 1,300
untouched. That part is unremarkable and it worked.

The interesting part is what came out of reading the result. Six mechanical
checks run over every translation — tag integrity, options and paths, register,
completeness, referenced images, and a cosine-similarity gate on meaning. All
of them were green. Human review then found four families of defects, and none
of the six could have caught any of them.

**A heading stopped being a heading.** `## Why Diwall — what you actually
delegate` came back in Spanish without its hashes, as ordinary prose. The
document was one section short, and so was the generated PDF. The text was
translated, the tags were intact, the register was right: every net passes a
paragraph that used to be a title.

**Literal option values were translated.** `--mode fast` became `--mode rapide`
in French and `--mode schnell` in German, inside the manual page. The option
name is protected and survived; its value is not, and does not exist. A reader
copying that line gets an error. The options check compares option names
between source and translation, so it saw `--mode` on both sides and said
nothing.

**Three sentences reversed their meaning.** "Capture storage" became "capture
de stockage" and "captura de almacenamiento" — the two nouns swapped roles —
and, in German, "Datensicherung", which means data backup. "High-level
validation" became "hochwertige Validierung", high-quality validation.
"Headless" became "sin cabeza". Each is fluent, plausible, and wrong; the
similarity gate measures whether meaning drifted, and a confident mistranslation
does not read as drift.

**Sixty-three segments disagreed with each other.** "Informations
d'identification" beside "identifiants", "Anmeldedaten" beside "Zugangsdaten",
"encriptado" beside "cifrado" — all correct in isolation, all in the same
document. Translating segment by segment carries no memory across a document,
so terminology drifts by construction rather than by accident. This is the
failure mode to expect from any incremental pipeline, and the one a glossary
alone does not fix: the terms are enforced after the fact, not in the prompt,
because listing them in the prompt dropped first-try acceptance from 20/30 to
13/30.

Three defects that predate the translation surfaced while checking it. The
manual's illustration was missing from all four reference PDFs, English
included — pandoc resolves an image path from its working directory, never from
the file citing it, and only warns. The `MANUEL.md` table of contents was dead
on all eleven entries in the three languages: an anchor is a URL, so it is
protected from the translator, while the heading it points at is prose, so it
is translated. And the compilation preface still announced three documents
after the cheat sheet made them four.

Manual page section names were taken from the pages installed on the machine
rather than chosen: VOIR AUSSI appears on 1,164 of them against 8 for VOIR
ÉGALEMENT, CODE DE RETOUR on 76 against 13, and RÜCKGABEWERT on 17 while
EXIT-STATUS appears on none. A convention is measured, not picked.

---

## 2026-08-04 — A published measurement did not add up, and the benchmark claimed a total it never had

Two figures this project had been publishing for weeks do not survive being
checked against the record that produced them. Both are corrected here and on
the website, and the way they were found is worth more than either correction.

**The June campaign counted 22 sites and announced 23.** The accessibility
figures from 27 June 2026 — 39 % blocked by a WAF, 26 % timing out, 22 %
wrong-URL 404s, 8.7 % accessible — break down as 9 + 6 + 5 + 2. That is
twenty-two results for a panel described as twenty-three sites, and the shares
stop at 95.7 % instead of 100. Exactly one result, `1/23`, was never written
down.

It cannot be recovered: the list of URLs was not kept either, and rebuilding a
commercial panel without a genuine purchase intent was declined at the time as
indistinguishable from a load test on somebody else's infrastructure.

So the gap is now stated rather than smoothed over. The counts stay as they
are, and the shares stay relative to the panel targeted — **not** rebased on
22, which would assert that the twenty-third site went untested. Nothing
establishes that. All that is known is that its result went unrecorded, and
that is what the documents now say.

**The stealth benchmark never measured "31 of 31".** The site claimed
`--stealth` passed 31 of 31 fingerprint checks on a public benchmark. The
source records something else: 12 checks failed and 18 passed without the flag,
0 failed and 31 passed with it. The two columns describe 30 checks and 31 — the
totals are not equal, and nothing in the record explains why. The benchmark
page plausibly renders some checks only when a signal is present, but that was
never verified.

A denominator that was never measured is not a rounding detail on a page whose
whole argument is that its numbers can be checked. The claim is now what the
record supports: 31 checks passed with the flag, against 18 without, and no
total asserted.

**How both were found, and why it matters.** A first pass compared the website
against the repository and found them consistent. They were — and both were
wrong in the same way, because the site had copied the repository faithfully.
Consistency between a copy and its source proves only that the copy is
faithful. What the second pass did differently was go back to the record that
produced each number: the field log, the observation file, the code. Checking
downstream text against upstream text will confirm a mistake as readily as a
fact.

---

## 2026-08-02 — The dated corpora stay in the repository, and the site copies them at build time

Yesterday's decision is reversed. `JOURNAL.md`, `RETOUR_EXPERIENCE.md`,
`RADAR_MODELES.md` and `ACCESS_OBSERVATIONS.md` — 5 104 lines — had been moved
out of the public repository so the website could carry them without
duplicating content. They are back, and the site publishes them without owning
them: `deploy-site.sh` copies them from `docs/` just before the Hugo build, and
the site repository does not version them.

**Why the reversal.** The first trust argument of this project is that
everything is inspectable, failures included. A developer who lands on the
forge — the most demanding reader, and the one who will never visit the site —
must be able to read the history of decisions next to the code those decisions
produced. Moving the files made that history invisible where it matters most,
and detached the writing of the log from the commits it narrates.

The duplicate-content objection that motivated the move was real, and it is the
copy at build time that answers it — not the removal. There is never a second
history of the same text.

**What the move actually cost, and it is the useful part of this entry.** The
files were not simply moved: they were transposed into Hugo pages, with roughly
a hundred and thirty presentation `<div>` tags injected into the body, and the
sources were deleted. No content was lost — the 44 entries were all there, word
for word. What was lost was **the file one writes in**. What remained was a
template to edit, and, no copy script having been written, no path to publish
at all. At closing time there was nothing left to write the day's entry into.

Two rules come out of it, and they are now in the site specification. A file an
operator fills in by hand between two sessions carries no layout markup — the
styling belongs to the template, in CSS. And a page copied at build time
reproduces its source in full, in the language it is written in; what deserves
to be known from a long corpus is lifted into a short editorial page, in four
languages, which cites its source. Selecting is not rewriting.

**Annual rotation, done at the copy.** 44 entries in four months, roughly 6 000
lines a year: a single page becomes unreadable in its second year. The
deployment splits entries by year into one page each; the source stays one
continuous file. A blocking check compares the number of entries before and
after the split.

**One section was flattened.** `Le projet` had a heading, one sentence and a
link to its only sub-page: a reader arriving from the menu got an announcement
rather than an answer. The history moved up into the section page, the sub-page
is gone, and the four `.htaccess` redirects that had been hiding the emptiness
since 31 July went with it — they never applied locally, since `hugo serve`
does not read that file, so the defect was only visible in production. This
stays an exception: the other seven sections have several sub-pages with real
material, and flattening them would destroy translated, indexable URLs.

**Twenty-six cross-references repaired.** Removing the files had turned
internal references into links to the website, throughout the guides, in all
four languages, and inside `shot.py` and `lib/preflight_guide.py`. They are
local paths again. Nine translation cache files carried the same URLs — the
exact trap already met on 1 August, where published files were fixed and the
cache that re-injects them was not.

**Four version numbers, none of them the shipped one.** The package shipped
1.23.0 while `shot.py` and `rpa.py` declared 1.22.0, `watch.py` 1.18.0 and
`journal.py` 1.20.0. Every JSON output therefore announced `version_shot:
1.22.0` on a 1.23.0 install — a model reading that key to decide whether a
feature exists gets it wrong, and an operator reporting a bug quotes the wrong
number.

The closing checklist had asked for this consistency from the start. Nothing
verified it, so it drifted across four releases. `verifier-coherence.sh` now
checks each root script's `__version__` against `debian/changelog`, which is
already the source of truth for the package build. The check was **proven to
fail on a deliberate drift** before being trusted: a check nobody has watched
fail proves nothing.

**A cold-install test that proved nothing, and its correction.** Session 51 had
found that `postinst` never created `/opt/diwall/references`, so
`watch --sauver-reference` failed on a fresh install. Re-running that test
today looked green — wrongly. `dpkg` does not remove `/opt/diwall/scenarios`
when it is not empty, so the parent directory survives the purge and
`references/` with it: the test was measuring a leftover. With the directory
actually deleted first, `postinst` does create it, `770 root:diwall`. The fix
holds; the test that was supposed to guard it did not.

---

## 2026-08-01 — `man diwall` in four languages, and both channels ship the same thing

The manual page is translated into French, German and Spanish. `dh_installman`
derives the language from the file name, so `debian/diwall.fr.1` lands in
`/usr/share/man/fr/man1/` and `man` picks it up from the reader's locale with
no configuration at all. The six `.so` redirections are generated per language
too — without them a French reader would get French on `man diwall` and English
on `man diwall-shot`, which is worse than no translation.

Section names follow the Debian conventions of each language rather than a
literal translation: `BEZEICHNUNG` and `ÜBERSICHT` in German, `VÉASE TAMBIÉN`
in Spanish. Those were read off installed pages, not guessed — the Spanish form
was chosen by counting occurrences on this machine, 67 against 2.

**Both installation channels now ship the translated documentation.** The
package and `deploy.sh` place `i18n/**/*.md` and `docs/images/` under
`/opt/diwall/`. A package that shipped them while a git clone did not would
produce two different installations of the same version, and the divergence
would surface at every consistency check until someone silenced it. What the
pipeline uses to *build* the documentation stays out: segment sidecars and
arbitrations — larger, together, than the documentation they produce — plus
the manifest, the LaTeX preamble and the generated PDFs, which are git-ignored
and therefore absent from a fresh clone. What a reader reads ships; what builds
it does not.

**A real render caught what no automatic check did.** The manual is the first
document in the pipeline that is not ordinary markdown prose, and three of its
constructions had no protection: pandoc's metadata header, which carries the
page name *and section*; the escaped brackets of the SYNOPSIS; and command
names. `diwall-monter-secrets` came back translated into a command that does not
exist — inside a SYNOPSIS, with every mechanical check passing, because prose
documents write command names as inline code, already masked, while manual
pages write them in bold. Four patterns were added, and the first translation
was re-run from scratch afterwards: a net added after the fact does not catch
what is already written.

## 2026-07-31 — Repository governance scripts leave the repository

The governance scripts of this repository — publication check, coherence
check, pre-push hook, package build, translation chain — are no longer
distributed. They serve to maintain Diwall, not to use it.

This is a cleanup, and it presents itself as one. Nine files are affected;
the eight scripts a user actually needs stay exactly where they were:
`install.sh`, `uninstall.sh`, `deploy.sh`, `configurer-repertoire-chiffre.sh`, `monter-repertoire-chiffre.sh`,
`demonter-repertoire-chiffre.sh`, `migrer-repertoire-chiffre.sh`, `monitor-verifier.sh`. The test that
matters — "can this be rebuilt from zero with the Git repository alone?" —
still passes, which is precisely why those eight are not going anywhere.

Two consequences are worth stating rather than discovering:

**Git history is not rewritten.** Versions v1.1 through v1.21.0 still contain
these files. A history purge is justified by data that must be erased, never
by a preference about tidiness — and the check run before the move found
nothing sensitive in the seventeen scripts.

**`scripts/i18n/` is gone, and the translations are not.** What ships is the
result: the translated markdown under `i18n/`, its segment fingerprints, and
the manifest declaring the order of the reference PDFs. The machine that
produces them needs `pandoc`, a LaTeX engine and a local Ollama instance —
none of which was ever a Diwall dependency, and none of which a packager or a
fork needs. The `README.md` reproduction command changed accordingly: it now
demonstrates Diwall itself against a fixture versioned in this repository,
rather than the maintainer script that generated the illustration.

The v1.23.0 validation suite (`scenarios/v1.23.0_validation/`) tests that
translation chain, so it now skips cleanly when the tooling is absent instead
of failing on import — an absent maintainer tool must not read as a broken
product.

## 2026-07-29 — Session 63 (v1.23.0 — multilingual documentation: `i18n/`, ordered PDF, segmented translation pipeline)

**English stays canonical and stays in place.** Translations of the
human-facing documents (`README.md`, `docs/GUIDE.md`, `docs/MANUEL.md`) live
under `i18n/<language>/`, mirroring the source path. Nothing was moved — the
tree is asymmetric on purpose.

`docs/GUIDE_LLM.md` and its three notices are never translated. Their paths
are frozen (guide-lock, `debian/diwall.install`, `deploy.sh`, runtime error
messages, partner documentation), but the deciding reason is subtler: a
translated locked guide can desynchronise silently. A version number
mechanically resynchronised over content that is still the previous version
lets an agent pass the lock having read obsolete instructions — the exact
failure the lock exists to prevent. A model reads English natively and English
costs fewer tokens: the benefit is nil, the risk is real.
`docs/RETOUR_EXPERIENCE.md` stays French and untranslated; the dated logs
(`JOURNAL.md`, `RADAR_MODELES.md`, `ACCESS_OBSERVATIONS.md`) are observation
records, not usage documentation.

**The order is declared once, in `i18n/manifeste.json`, and shared by every
language.** The table of contents is never maintained by hand — pandoc
generates it from the merged headings (`--toc`). Only the *order* is declared.
An implicit order (alphabetical, or whatever the filesystem returns) is never
the pedagogical order: that is how a manual ends up presenting reinstallation
before installation. If translations each redeclared the order, four PDFs
would end up with three different ones, and nobody would notice until a
Spanish reader uninstalled before installing.

Every file in the declared perimeter must appear in either the order or the
motivated exclusions. A file in neither fails the build, and
`scripts/verifier-coherence.sh` gained a fifth, static check for the same
reason: a document added under `docs/` and forgotten in the manifest would
otherwise drop out of the PDF silently.

**What must not be translated never reaches the model.** Fenced code blocks
are never sent at all. Inside prose, protected zones — inline code, paths,
long options, URLs, anchor targets, JSON keys — are replaced by opaque tags
before the call and restored after it. Asking a model not to translate
`--wait-until` works most of the time, and "most of the time", on technical
documentation, produces a broken command somewhere nobody looks. The check is
mechanical: the tags in the answer must be exactly those in the input, same
count, intact, no duplicates. Any divergence rejects the segment to human
arbitration, English source kept. There is no semantic judgement a convincing
model could talk its way around.

**Segments carry their source fingerprint**, stored next to the translation.
Fixing a typo retranslates the touched segments only. Without that, correcting
one word relaunches four complete translations and the pipeline dies of
exhaustion after three releases — the deciding motive, ahead of the small
models' context limits.

**Two mechanisms earned their place from measured failures, not from
foresight.** First run on `README.md` rejected 21 of 51 segments; 19 carried
the same cause — the model *invented* tags on segments that had none, because
the prompt explained tags to it regardless. The placeholder instruction is now
sent only when the segment actually holds placeholders. Second: some segments
came back untranslated, verbatim English. The similarity gate is structurally
blind to this — an untranslated segment back-translates to itself and scores a
perfect 1.0, the best mark available. Only a mechanical string comparison
catches it, so a segment handed back unchanged is now rejected outright.

A third fix came from the prompt itself: naming the *shape* of the tags
(`[[[xxx]]]`) rather than listing the ones present. Listing them makes the
model copy the list into its answer, so every tag comes back duplicated — a
mechanism visible in the failures, not a correlation.

Final figures, four checks and one retry, across three languages: **100
segments in arbitration out of 1005 (10.0%)** — French 35, German 33, Spanish
32. Rejected segments keep their English source and are listed with their
reason; a handful are trivial (`## Architecture`, `## Installation`,
`## Licence` are identical in French — the model was right, a human clears
them in seconds). The rate rose from 3% to 10% when the last two checks went
in, which is the whole point: those 7% were being delivered corrupted and
silent.

**Two failures the first three checks could not see, both found by running
the pipeline on three languages rather than one.**

The model sometimes *answered* the instruction instead of following it: the
output opened with the instruction itself, faithfully translated, followed by
the real translation. 89 segments across the delivered French and Spanish
files. Tags were intact, so tag integrity passed; on a long segment the extra
300 characters barely move a length ratio, so that would not have caught it
either. What catches it is a literal: the instruction describes the tag shape
as `[[[xxx]]]`, and real tags are always numeric — that string can reach an
answer exactly one way.

And from the single heading `## Uninstalling Diwall`, the German run produced
a complete invented Windows uninstall procedure, control panel and all. It was
caught only because the invention happened to mention `/usr/local`, a path the
second net could compare against the source. Invented prose without a path
would have shipped. Hence the fourth check, on length ratio: translation
stretches text by tens of percent, never by a factor of ten. A short segment
answered with paragraphs is a model answering, not translating.

Both are worth stating plainly: the safety of this pipeline does not come from
the model behaving, it comes from checks that do not need it to. Every one of
the four was added after seeing the failure, not before.

**A measurement that reversed itself, kept here because the mistake is the
useful part.** Tags are numbered sequentially, and the numbering looked like a
liability: shown `[[[0]]]`, a model has an obvious next term to invent. Opaque
identifiers (`[[[k9]]]`) were tried and looked like a clear win — 9 of 10
against 1 of 10 on a sample of ten segments. On the full corpus the
improvement vanished: 35 rejections against 31. The sample was the problem. It
had been built from segments that failed *under sequential tags*, which is
precisely the sample that cannot answer the question — those segments are
selected for being hard for one arm of the comparison. Re-measured on 40
randomly drawn segments, same model, same prompt, the ranking inverted:
sequential 39/40 accepted first try, opaque 34/40. Sequential numbering
stayed. Ten cherry-picked cases outrank a plausible theory, and both outrank
nothing — but only a sample drawn without knowing the answer settles it.

**Two independent nets after translation.** Options and paths are compared
source-to-translation across the whole document, deliberately independent of
the tag mechanism: two nets that fail for different reasons are worth more
than one very careful net. Then the similarity gate — back-translation by a
fresh call, cosine similarity over local `nomic-embed-text` embeddings. It is
posterior to code masking and never replaces it: similarity judges *meaning*,
and would validate `--wait-until` rendered as `--attendre-jusqu-a` without
hesitation, since the meaning is indeed preserved. The gate is entirely
switchable off (`--sans-porte`), and never applies to positioning text —
cosine similarity measures drift of meaning, not drift of register, and a
faithful translation slid into a promotional register would clear the
threshold unnoticed.

**Model quality, measured rather than assumed.** `translategemma:4b` and
`translategemma:12b-it-q4_K_M` both hold the tags. The 4b inserts a stray
space before each tag, which turns `[label](#anchor)` into `[label ](#anchor)`
— still valid markdown, visibly sloppier. The 12b does not, at roughly twice
the wall time. The 12b is the default.

Pandoc, the LaTeX chain and Ollama stay maintainer tooling on the build
machine. Nothing entered `requirements.txt`. Generated PDFs are not versioned;
translations and their fingerprint sidecars are — without the fingerprints,
another maintainer retranslates everything from zero.

**An outside reading, and what it cost to take seriously.** The Spanish PDF was
submitted to two external models before release. The verdict — "engineer's
documentation, well above the average open-source project of this size", but
suffering "the classic syndrome of projects that grow fast with a single
maintainer: it accretes" — was accepted, and produced six changes.

Every criticism was measured before being acted on, and four turned out to be
wrong: section numbering is sequential (1→11, `7a`→`7l`, `5a`→`5k`, no gaps),
heading case is consistent across all seven use cases, the doctrinal content
sits in `GUIDE.md` exactly where the documentation doctrine puts it, and the
JSON keys (`boussole`, `etat`, `respect`) must **never** be translated — a
reviewer read them as sloppiness, when they are the output contract partner
projects consume. Those four are recorded as verified-unfounded, so a later
reading of the same report does not "fix" them.

What was real: **installation duplicated** between README and manual (12 lines
against 45), **seven chronological blocks** in the table of contents
duplicating the changelog, **stale version headers**, `Case 1` formatted unlike
its six neighbours, and **no synthesis at all** — no cheat sheet, no diagram,
and, in a tool that gives a model eyes, not a single picture of what it
produces.

The fix follows one principle: **organise by time-to-access, not by
exhaustiveness**. Start → cheat sheet → reference. The suggestion to cut the
whole thing to 25 pages was declined: operational density is the point, and
what a hurried reader needs is a shorter path in, not less material.

Each document now has an exclusive role — the README leads with `apt install`
and hands off, the guide carries architecture and use cases, the manual holds
both installation channels and every command. The PDF keeps its three
documents and gains a compilation preface, because each of them also has to
live alone: the README on GitHub, the manual in `/opt/diwall/docs/`.

`docs/CHEAT_SHEET.md` puts the 21 scenario actions, their required and
optional keys, the reading order of the output and the exit codes on one page.
And the README now shows **a real `--som` capture**, produced from a local
fixture committed alongside it — ten numbered elements on a rendered admin
panel, reproducible in two commands by anyone. A tool that gives a model eyes
should show what it makes visible.

**The version drift got a machine, not a third written rule.** Rule 5 of the
documentation doctrine — "the manual is a condition of publication" — was
written in session 44, restated in session 47 after the manual sat at 1.15.0
for two releases, and violated again here. `verifier-coherence.sh` now
compares the version header of the documents that must track releases against
`debian/changelog`. Only those documents: a file untouched since v1.19.0 that
announces v1.19.0 is telling the truth, and forcing it to display the current
release would be the same mechanical lie the guide-lock exists to prevent.

Reading the manual for this also turned up `currently 3.9` where the guide had
been at 4.1 — invisible to the token check because the value sat on the line
*after* the word that introduces it. The fix is not a cleverer pattern: the
hardcoded value is gone, replaced by the command that reads it.

**The cheat sheet was written, and stayed invisible.** An external reviewer
reported the absence of a condensed cheat sheet and of a quick-start page —
while `docs/CHEAT_SHEET.md` existed, shipped in the package, opening on
*Three commands*. It was excluded from the PDF at creation, on the grounds
that it is almost entirely code and four near-identical translations would
cost maintenance for nothing. The reasoning was sound; the side effect was
not. The answer to the criticism existed and could not be seen by the person
making it.

Measured before deciding: 19 translatable segments, about 76 seconds per
language. The cost we had judged prohibitive was marginal, precisely because
the document is mostly code. It now **opens every PDF**, ahead of the
overview — which is the access-time principle finally applied rather than
merely written down: commands first, then presentation, architecture, and
reference.

**Code comments now follow the document's language, and the guarantee that
allowed it.** 75 comments per language sat in English inside code blocks —
`# Preview what will be removed` in the middle of a French manual. They were
untouched because the rule was simple and absolute: nothing inside a fenced
block ever changes, which is what makes a copied command work.

The rule is now held by a check rather than by abstention. Only lines whose
first non-blank character is `#` are eligible; shebangs are excluded, and so
are commented-out commands, recognised by their first word (`sudo`, `bash`,
`git`, a path). Each comment goes through the same masking as prose, which
does the rest of the sorting on its own. After rebuilding, **every non-comment
line is compared character for character** with its source: 84 blocks changed
across three languages, zero executable line touched.

A first version of that verification cried 259 breaches. It compared segments
by position, and re-segmenting a translated file desynchronises everything the
moment a translation adds a line break — the same trap already met on the
similarity gate, and solved the same way: pair by fingerprint, never by
position. The check was wrong, not the translations.

**Rejection needed a destination, not just a report.** Keeping the English
source and listing the reason is right for a pipeline and wrong for a
deliverable: a reader of the French PDF hit English mid-page. Hand-fixing the
output was not an option either — it survives until the next `--forcer`, then
vanishes silently. `i18n/<language>/arbitrages.json` holds human-settled
translations keyed by source fingerprint, consulted **before** the automatic
cache, so a stale machine translation can never outrank a human decision.
Keying on the fingerprint also means editing the English source correctly
invalidates the arbitration: the settled text belonged to the sentence as it
was. All 100 pending segments are now settled; the three languages build with
zero segments awaiting arbitration.

An arbitration may also target a fenced block, and only a human can: some
blocks are ASCII diagrams whose content is prose, not code
(`LLM acts → Diwall captures → …`). Those blocks still never reach a model.

**What the checks caught on their author.** Writing arbitrations by hand
removes the code-masking safety net, and both remaining nets fired on this
session's own work. The second net rejected a Spanish segment where
`plugins/languages/platform` had been translated — those are `navigator.*`
property names, and the model had been protected from touching them precisely
because masking hid them. The margin check then rejected the freshly
translated ASCII diagrams: 110pt past the edge in German, because pandoc emits
plain `verbatim` for a fenced block with no language declared, which never
breaks a line — `Highlighting` alone was not enough. The English source
happened to have no long line in an unlabelled block, so the gap had been
invisible.

**Documentation audit.** `docs/FAQ_LLM.md` announced `--guide-version current
token 3.9` while the guide had been at 4.1 since v1.22.0 — a model copying
that token gets `guide_non_lu` with nothing explaining why. Same failure mode
as the script desynchronisation fixed in v1.22.0, at a place the check did not
reach: `verifier-coherence.sh` gained a sixth, static check over `docs/`
(`JOURNAL.md` excluded — a dated history, where old tokens are facts).
`repli_js` (v1.22.0) was missing from the action table in `docs/MANUEL.md`,
documented only in the LLM notices, so an operator reading the reference table
could not find it. And installation now leads with the Debian package rather
than burying it under a manual six-step procedure as an "alternative": one
`apt install` line is the simple path, and building from source is for
modifying Diwall itself.

**The register drifted, and fixing it naively made things far worse.** The
first Spanish build mixed 20 `tú` with 29 `usted` inside one document. Nothing
was mistranslated; the text simply stopped addressing the reader the same way
halfway through — which reads exactly like a document that went through a
third language, and was reported as such. The cause is structural:
segment-by-segment translation has no memory, each call sees one paragraph and
nothing else. `i18n/glossaire.json` declares the form of address and the
imposed terms per language.

Declaring them in the prompt, however, cost far more than it bought. Measured
on 30 randomly drawn segments, same model, same text: **no register
instruction 28/30 accepted first try, a one-line instruction 20/30, the
instruction plus six imposed terms 13/30**. `translategemma` is built for
translation, not for following instructions — every added sentence degrades
it. The instruction is now paid only where needed: a segment that comes back
in the familiar register is retried *with* it. Imposed terminology left the
prompt entirely.

**And that mistake exposed the net that was missing.** The over-long prompt
pushed Spanish to 165 rejections out of 345 — and since a rejected segment
keeps its English source, **48% of the document was English while every other
net reported OK**. Paths and options are identical by construction; English
contains no familiar-register word either. Nothing could see it. The
completeness check now runs first and fails on any segment still carrying its
source: a pipeline may leave work for a human, a deliverable may not. That
check, not the register one, is what would have caught the original complaint.

**Page layout, measured the same way.** The first PDFs pushed 13 lines past
the margin on the English build, the worst by 150pt — about 5cm off the page,
on a document whose commands are meant to be copied. Pandoc swallows the TeX
log, so nothing reported it: the defect was visible only by opening the file.
`i18n/style.tex` fixes it, derived from the Sillage documentation preamble
with three deliberate departures. Hyphenation stays *on* (Sillage disables it
for a clean French look; these documents also ship in German, where forbidding
hyphenation guarantees overflow). Polyglossia is not hardcoded to French —
pandoc loads the right language from the `lang` metadata, since one preamble
serves four languages. And cell padding drops from 14pt to 4pt, because the
wide reference tables are exactly what generous padding pushes off the page.

Long code lines now wrap (`fvextra`), and `snake_case` identifiers may break
after an underscore — with no hyphen inserted, so what a reader copies is
still the exact identifier. That is why hyphenation of monospace was rejected
rather than enabled: a hyphen in `attendre_selec-teur_present` is a broken
command waiting to happen. All four languages now build with zero overflowing
lines, checked by `generer-pdf.py --verifier-marges`, which compiles through
LaTeX and reads the log pandoc hides.

`scenarios/v1.23.0_validation/`: 12/12, offline and model-free. Five of the
twelve are counter-tests: a net that never fires is indistinguishable from a
net that is not there.

---

## 2026-07-29 — Session 62 (v1.22.0 — `--wait-until`, `citoyennete` → `respect` breaking rename, `man diwall`, packaging)

**Breaking change — the `citoyennete` output key is now `respect`.** At the
JSON root, inside `boussole`, and in the operations log. Sub-keys unchanged
(`pages_visitees`, `actions_executees`, `duree_totale_ms`, `plafond_atteint`,
`waf_bloquants`, `indice_agressivite`). No transitional dual emission: a
deprecation window installs permanent debt to avoid a one-minute update, on
infrastructure whose consumers are known and reachable. Anyone reading
`citoyennete.waf_bloquants` or `citoyennete.plafond_atteint` must update.

The doctrine itself does not change — measured pace, declared identity never
disguised, navigation caps, counters reported in the output. Only the name
does: "Citizen Navigation" becomes "Respectful Navigation" throughout. The
previous term carried a civic-political register foreign to the intent, and
translates badly in a four-language site (*Bürger*, *ciudadano* carry the same
charge). The rename landed in a version that was never tagged or published, so
no released version has ever carried the obsolete contract.

**`--wait-until {networkidle,load,domcontentloaded}` (`shot.py`):** sets when
the initial navigation is considered finished; the default `networkidle` is
unchanged. Motivated by a real target — a router administration panel that
polls live statistics, where the 500 ms of network silence `networkidle`
requires simply never occurs. That is not a duration problem: `--timeout
45000` fails exactly like `--timeout 10000`, because the page never finishes.
Propagated by `rpa.py` to its `shot.py` subprocess, and available as a root
`wait_until` property on a scenario so it stays self-contained (the CLI flag
wins over the property — it carries a value, unlike the boolean activation
flags combined with OR). Without that propagation the flag would only have
served direct reconnaissance, while the target that motivated it is
administered by scenario. Applies to the initial navigation only; the
`naviguer` action keeps Playwright's `load` default, an asymmetry left as is
for lack of a second real use case. `boussole.wait_until` carries the value used, and only when it
differs from the default — never the bare CLI flag (same discipline as
`stealth_actif`, fixed in v1.16.0). It reports the value rather than a boolean
because an agent re-reading an output needs to know under which condition the
page was judged ready.

**`man diwall(1)`:** the six `/usr/bin/diwall-*` commands shipped with no
manual page at all — a genuine packaging defect on Debian, where `man
<command>` is the first reflex. One page documents all six, `git(1)`-style:
seven pages would drift out of sync with `--help`, one has a single source of
truth. Generated at build time by pandoc from `debian/diwall.1.md`, so it
cannot go stale by omission, and `man diwall-shot` (plus the five other names)
resolves to it. A real defect was found while writing it: pandoc's default
`smart` extension rewrites `--url` as an en dash, which would have shipped a
manual page documenting options nobody can type — hence `markdown-smart` in
`debian/rules`.

**`scripts/construire-paquet.sh`:** builds, then moves the `.deb`,
`.buildinfo` and `.changes` into `paquets/<version>/`. `dpkg-buildpackage`
writes to the parent directory by construction and no `debian/rules` setting
redirects that cleanly, so build artefacts had been accumulating in a
directory that was never meant to be a build output. Building then moving
leaves the tool's own behaviour intact. All versions are kept — the
`.buildinfo` is the only record of the exact build environment.

**Pre-existing desynchronisation found and fixed:** `scripts/install.sh` and
`scripts/preflight-publication.sh` still passed `--guide-version 3.7` while
the guide had moved to 4.0 — masked by an already-valid local marker on the
development machine, which is precisely the failure mode the guide-read lock
exists to prevent. Same staleness in three user-facing examples
(`docs/MANUEL.md`, `docs/GUIDE.md`, `docs/FAQ_LLM.md`, all at 3.9): an
operator copying those commands would have hit `guide_non_lu`. All
resynchronised to 4.1, and `scripts/verifier-coherence.sh` now fails on any
future divergence between the guide's own `notice-version`, the
`GUIDE_VERSION_ATTENDUE` constant, and the token those two scripts pass.
This check has to be static: the cold-install test cannot catch this class of
drift, since the `.deb` channel passes no token at all — the defect lives on
the git-clone path, where `install.sh` would fail its own final smoke test on
a clean machine.

**Validation:** `scenarios/v1.22.0_validation/` 11/11 green, including a new
fixture (`polling_continu.html`, one request every 200 ms) with a contrast
test proving `networkidle` genuinely fails on it and `--wait-until load`
succeeds by the normal path — not by the error fallback, which yields neither
`elements_som` nor `a11y_tree`. Regression: `v1.15.2` 4/4, `v1.16.0` 7/7,
`v1.17.0` 4/4, `v1.17.2` 4/4, `v1.18.0` 5/5, `v1.19.0` 3/3, `v1.20.0` 3/3,
`v1.21.0` 3/3.

**Comment tester / comment lancer :**

```bash
# Suite de validation v1.22.0, depuis la racine du dépôt source
/opt/diwall/venv/bin/python3 scenarios/v1.22.0_validation/verifier.py

# --wait-until sur une cible qui n'atteint jamais le silence réseau
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url http://<cible>/ --wait-until load --som --a11y --guide-version 4.1

# Lire la nouvelle clé respect (ex-citoyennete)
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url https://example.com \
  --no-capture --guide-version 4.1 | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['respect'])"

# Construire le paquet et le ranger dans paquets/<version>/
bash ~/git/Diwall/Diwall/scripts/construire-paquet.sh
man diwall
```

---

## 2026-07-19 — Session 58 (v1.22.0 — JS click escalation, last HTTP status in boussole, clearer vault error)

**`repli_js` on `cliquer` (`shot.py`):** new optional boolean key on the
`cliquer` action, distinct from `force: true` and not a replacement for it —
a second-level escalation, tried only when a native click (with or without
`force`) still fails on an interactability/obstruction error. On failure,
Diwall retries via `page.eval_on_selector(selecteur, "el => el.click()")`.
`boussole.repli_js_utilise: true` appears only when the escalation actually
ran, never just because the flag is set (same discipline as `stealth_actif`).
Rejected at scenario validation (`arguments_incompatibles`, exit 2, before any
browser launch) when combined with `--no-evaluer`, since `repli_js` executes
JS and `--no-evaluer` forbids that on the run.

Real bug found while writing the regression fixture: the native-click failure
this feature targets (`showModal()`/CSS-hidden containers, previously
documented as FN14) raises a plain Playwright `Error` ("Element is not
visible"), not a `TimeoutError` — an initial implementation catching only
`TimeoutError` would have silently missed the exact case this item exists to
fix. Caught by testing against a real fixture before finalizing, not assumed.

**`dernier_code_http` in boussole (`shot.py`):** always present (unlike the
conditional `session_derive`), reflects the last navigation's HTTP status —
the initial navigation if the run performs no `naviguer` action, or the most
recent `naviguer` action otherwise. Reuses the status already captured for
WAF detection (v1.16.0), no new capture plumbing. On a run with several
navigations, reflects the last one only — documented as a known limit rather
than a guarantee.

**Clearer `SecretsNonConfigureError` message (`lib/repertoire_chiffre.py`):** the runtime
error now cites both fixes for a missing vault configuration — creating
`diwall.conf` from the sample file, or pointing `DIWALL_CONF` at a
project-specific file — instead of only the first. The second path already
existed and is the one that avoids the on-disk symlink workaround previously
seen in real usage.

**Validation:** `scenarios/v1.22.0_validation/` — 5/5 green, including a new
local fixture (`scenarios/interoperabilite/fixture/dialog_ferme.html`, a
never-opened `<dialog>`) reproducing the native-click failure deterministically,
plus a contrast test proving the same click genuinely fails without
`repli_js`. Regression: `v1.15.2_validation` 4/4, `v1.16.0_validation` 7/7,
`v1.17.2_validation` 4/4, `v1.18.0_validation` 5/5, `v1.19.0_validation` 3/3,
`v1.20.0_validation` 3/3, `v1.21.0_validation` 3/3 (hardcoded guide-version
tokens resynchronised across four of these suites, pre-existing staleness
found while running them, not a functional regression — same pattern as
prior cycles). Preflight exit 0 (103 files scanned, 3 smoke tests green
against a live `/opt/diwall/` deployment).

**Comment tester / comment lancer :**

```bash
# Suite de validation v1.22.0, depuis la racine du dépôt source
/opt/diwall/venv/bin/python3 scenarios/v1.22.0_validation/verifier.py

# repli_js en conditions réelles (cliquer sur un élément obstrué)
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario mon_scenario.json --guide-version 4.1
# où mon_scenario.json contient une action :
#   {"type": "cliquer", "selecteur": "...", "repli_js": true}

# dernier_code_http — lire la boussole de n'importe quel run
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url <cible> \
  --no-capture --guide-version 4.1 | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['boussole']['dernier_code_http'])"
```

**Not yet tagged/released** — `__version__` bumped to `1.22.0` in `shot.py`
only (`rpa.py`/`journal.py`/`watch.py` untouched this cycle, no functional
change to any of them, matching the per-file version bump discipline already
in place).

---

## 2026-07-14/15 — Session 55 (v1.21.0 — HTTP Basic Auth + guide hygiene + demonstration cases)

**Context:** triggered by a field report from a partner project (`__HOST_VPS__`) — Diwall
had no way to answer an HTTP Basic Auth challenge (RFC 7617), the common
authentication wall in front of self-hosted admin interfaces (Grafana,
Prometheus, and similar) behind a reverse proxy. The same investigation
surfaced a deeper documentation problem: a model had asserted Diwall could
not fill an authentication form at all — false, but revealing that the
mandatory `--guide-version` lock only gates tool *execution*, never
conversational claims about the tool.

**`--http-credentials` (shot.py, rpa.py):**

- Resolves `http_username`/`http_password` from the vault (fixed keys, same
  precedent as `ntfy_topic`) using the exact resolution idiom already used
  three times in `shot.py` for `depuis_secrets` fields — no new file mechanism.
- Injected at `browser.new_context()` as `http_credentials={"username",
  "password", "origin", "send": "unauthorized"}` — `origin` scoping is
  mandatory (verified against the installed Playwright 1.61.0), preventing
  credentials from being sent to any third-party origin loaded in the same
  browser context. Documented fallback for reverse proxies that never issue
  a clean 401: `"send": "always"`, still origin-scoped — never a hand-built
  `Authorization` header, which would defeat the scoping.
- `boussole.http_credentials_actif` reflects a verified success (flag active
  **and** the initial navigation did not end in 401) — never just the CLI
  flag, the same discipline already enforced for `stealth_actif` after its
  v1.16.0/FR-79 fix. `boussole.http_auth_requise` flags an unresolved 401
  distinctly from the WAF signal.
- Fail-fast pre-validation in `rpa.py` before any Playwright launch, same
  pattern as `--secrets`. Optional scenario root property `http_credentials:
  true`, combinable with the CLI flag (OR) — same pattern as `shadow_dom`.

**Guide hygiene:**

- Non-presumption rule (`CLAUDE.md` Règle n°7, `docs/GUIDE_LLM.md`): never
  affirm a Diwall capability is absent, never presume one exists, without
  checking the action tables first.
- `docs/GUIDE_LLM.md` compressed from 413 to 250 lines — the budget already
  promised in `CLAUDE.md` but silently exceeded across 8 prior version
  bumps. `scripts/verifier-coherence.sh` now fails on any future regression
  of this budget.

**Demonstration cases (`docs/GUIDE.md`):** four new narrative-only cases —
self-hosted observability/analytics dashboard, ticketing platform
administration, local events tracking, e-commerce access under Citizen
Navigation. Tools, brands, and the operator are generalised by functional
category rather than named — a reusable prompt pattern, not just an
anonymised anecdote.

**Validation:** `scenarios/interoperabilite/` gained a local Basic Auth
fixture (a minimal Python server issuing a real 401 challenge — no
third-party dependency, deterministic), added as a permanent regression
fixture alongside the existing Shadow DOM/iframe fixtures.
`scenarios/v1.21.0_validation/` — 3/3 green: unresolved 401 without the
flag, verified success with correct credentials, and no false-positive
`http_credentials_actif` even with the flag active but wrong credentials.
Full regression: `v1.15.2_validation` 4/4, `v1.16.0_validation` 7/7,
`v1.17.0_validation` 4/4, `v1.17.2_validation` 4/4, `v1.18.0_validation` 5/5
(hardcoded guide-version token resynchronised 3.7 → 3.9, pre-existing
staleness found while running the suite, not a functional regression),
`v1.19.0_validation` 3/3, `v1.20.0_validation` 3/3. Preflight exit 0 (a
pre-existing unneutralised host name in `docs/RETOUR_EXPERIENCE.md` was
found and fixed in the same pass, unrelated to this cycle's own changes).

**Real-target validation:** the fixture alone was deliberately not treated
as sufficient — the operator provided live access to a real
Caddy-protected admin interface. `send: "unauthorized"` resolved the
challenge on the first real attempt, confirming the safe default is not
just theoretical. The real gap the fixture could not have caught: the
vault file used the plain `username`/`password` keys, not the dedicated
`http_username`/`http_password` this cycle originally required. Fixed with
a fallback (dedicated keys tried first — needed when a target has both a
network-level Basic Auth and its own separate application login — falling
back to `username`/`password` otherwise, the common single-credential
case). Package rebuilt and reinstalled a second time in the same cycle so
that production and source stayed byte-identical, same discipline as prior
cycles that found a real issue after the first build.

**Debian package:** `diwall_1.21.0-1_all.deb` built, installed as a real
in-place upgrade over the `1.20.0-1` package active in production
(`sudo apt install ./diwall_1.21.0-1_all.deb`) — `diwall.conf` checksum and
`preuves/` permissions confirmed unchanged before/after, `dpkg -l` confirmed
`1.21.0-1`, three smoke tests green post-upgrade. `lintian` within the same
accepted tolerances as prior cycles.

**Technical decision:** `watch.py` and `journal.py` untouched this cycle —
no functional change to either, matching the per-file version bump
discipline already in place. `--http-credentials` deliberately excludes
`watch.py` to preserve the stability of existing automated monitoring tasks.

**Not engaged this cycle:** FR-83 detection (DOM-state-loss warning across
`--reprendre-session` boundaries) — parked, the underlying limitation is
already a documented, accepted architectural constraint since v1.15.2, and
the detection mechanism itself (intra- vs inter-invocation) is not yet
designed. Remains in `docs/RETOUR_EXPERIENCE.md` / private `RADAR_USAGES.md`.

---

## 2026-07-10 — Session 53 (v1.20.0 — Observability + human-operator compass demonstration cases)

**Context:** first point of entry queued at the close of session 52
(08/07/2026): the three Copilot signals grouped as v1.20.0, plus the
human-operator-compass demonstration content already specified in
`BOUSSOLE_OPERATEUR_HUMAIN.md`. Both had PHASE_PLANIFICATION and
PHASE_DOCUMENTATION already closed — executed directly on the operator's
green light, no new planning round.

**v1.20.0 — code:**

- `journal.py --erreurs`: `store_true` flag filtering `resultat != "succes"`,
  same pattern as the existing `--mutatif` filter.
- `latences_actions`: `shot.py::executer_actions()` now times each action
  dispatch (`time.time()` before/after), exposed as an always-present JSON
  root key — `[]` when no actions ran, one `{"index", "type", "latence_ms"}`
  entry per action that actually dispatched (an action skipped by a
  citizenship-cap break before dispatch produces no entry, consistent with
  `citoyennete.actions_executees` not counting it either). Complements the
  existing global `citoyennete.duree_totale_ms`.
- `__version__` → 1.20.0 (`shot.py`, `journal.py`); `rpa.py`/`watch.py`
  untouched this cycle, left at their prior version (per-file bump
  discipline).
- Guide-read lock re-armed: `notice-version` 3.7 → 3.8
  (`lib/preflight_guide.py::GUIDE_VERSION_ATTENDUE` resynchronised in the
  same commit); `GUIDE_LLM_MONITORING.md` 1.9 → 1.10 (routing row updated
  for both new items).
- Docs: `docs/MANUEL.md` and `docs/GUIDE_LLM_MONITORING.md` document
  `latences_actions` and `journal.py --erreurs`.
- Tests: `scenarios/v1.20.0_validation/` — 3/3 green (`--erreurs` filter,
  `latences_actions` always-present + two-action structure end-to-end).

**Human-operator-compass demonstration cases (`docs/GUIDE.md`):**

- Case 1 (local CSS/JS troubleshooting) shipped as a real, runnable,
  committed scenario: `scenarios/exemples/depannage_local.json` (fast probe
  + `erreurs_js`/`erreurs_console` + `--som` + pixel-diff validation
  pattern), run end-to-end against `example.com` as the reproducible
  stand-in target.
- Cases 2 (hardware component comparison) and 3 (SPA documentation
  synthesis) documented as prose only, no scenario file committed for
  either — deliberate, per the doctrine arbitrated 08/07/2026: naming a
  real third-party shop or payment provider in a public scenario is a
  commercial decision that belongs to the operator, and a public scenario
  pinned to one named commercial target degrades with that site's anti-bot
  posture (FR-77: 39% immediate block rate on the sampled sites) rather
  than staying reproducible.

**Debian package:** `diwall_1.20.0-1_all.deb` built twice this cycle — first
covering the two v1.20.0 code items only, installed as a real in-place
upgrade over the v1.19.0-1 package active in production (`sudo apt install
./diwall_1.20.0-1_all.deb`, never `dpkg -i` alone), which is the real
scenario this item exists to validate (Copilot signal 1: no upgrade path had
ever been tested, every prior cycle was a purge-then-install). `diwall.conf`
checksum and `preuves/` permissions confirmed unchanged before/after,
`dpkg -l` confirmed `1.20.0-1`, three smoke tests green. A second build
folded in the demonstration-cases doc/scenario additions and was reinstalled
over the first, so that the version actually running in production and the
git source tree stayed byte-identical (`diff -rq` on every touched
file/directory) before this session closes — same discipline as session 50.
`lintian` within the same accepted tolerances as v1.18.0/v1.19.0 (`/opt`
placement, per-file interpreter path, missing man pages, plus the
postinst-driven `chmod`/`chown` and shipped-non-executable warnings, both
structural to the existing packaging design, not new this cycle).

**Process fix (this cycle):** `scripts/preflight-publication.sh` scanned
`debian/*` without excluding the gitignored build-staging subdirectories
(`debian/diwall/`, `debian/.debhelper/`, and related regenerated files) —
running the mandatory preflight right after a local `dpkg-buildpackage`
produced false-positive "leak" findings (Maintainer/changelog duplicated
into the staging tree) on content git will never actually publish. Fixed by
adding the same exclusions `.gitignore` already declares for those paths.

**Comment tester / comment lancer :**

```bash
# Suite de tests v1.20.0 (journal.py --erreurs, latences_actions)
# depuis la racine du dépôt source ~/git/Diwall/Diwall/
/opt/diwall/venv/bin/python3 scenarios/v1.20.0_validation/verifier.py

# journal.py --erreurs en conditions reelles
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --erreurs

# Scenario exemple 1 (depannage local)
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/exemples/depannage_local.json \
  --guide-version 3.8

# Preflight avant toute publication
cd ~/git/Diwall/Diwall && bash scripts/preflight-publication.sh
```

**Statut : PHASE_EXECUTION + PHASE_VALIDATION closes. `_CADRE/` et `Diwall/`
non encore commités — commit et décision push/release à la charge de la
suite de session (voir ADDENDUM du jour).**

---

## 2026-07-07 — Session 50 (v1.19.0 — The responsible agent, not the constrained one)

**Context:** consolidation cycle following a cross-model signal review after
v1.18.0 (7 sources, one duplicate extraction detected and merged). Framed by
a new governance doctrine written the same session: a three-category
taxonomy for constraints (data-security hard locks / comprehension locks /
navigation-behaviour defaults), settling a real risk of the tool's Citizen
Navigation posture drifting from "educate the operator" toward "constrain
the tool" — the opposite of the intended design.

**Work done:**

- `mode_conseille` (v1.18.0) now filters on `resultat == "succes"` in
  `lib/journal.py::dernier_diagnostic_host()` — a diagnostic run interrupted
  mid-way no longer feeds a configuration recommendation. Closes a gap in the
  "never a guess" promise made at v1.18.0's introduction.
- `chainage` traceability for `declencher_scenario`: `rpa.py::_aplatir_actions()`
  now returns an ordered call tree (`{scenario, profondeur, action_debut,
  action_fin}`) alongside the flattened action list; `lib/journal.py` records
  it on the journal entry when present; root `journal.py` renders it as an
  indented tree under each matching entry. Absent on any run without chaining
  — purely additive, no change to the non-chained path.
- Guide-read lock re-armed: `docs/GUIDE_LLM.md` `notice-version` 3.6 → 3.7,
  `lib/preflight_guide.py::GUIDE_VERSION_ATTENDUE` synchronised in the same
  commit (the token is hardcoded by design — never read dynamically from the
  doc file — so the two must always move together).
- `scripts/verifier-coherence.sh` (git source only, never packaged): static
  doc/code coherence check — notice-version headers vs the index table in
  `GUIDE_LLM.md`, and every `argparse` flag in `shot.py`/`rpa.py`/`watch.py`
  against `docs/`. Caught its own first real finding on this cycle (the new
  `chainage` field lacked a journal-fields-table row — fixed before this
  entry) and confirmed three pre-existing gaps in `watch.py` (`--prompt`,
  `--heatmap-tile`, `--sortie-json`), left unfixed as out of scope for this
  cycle and flagged for a future documentation pass.
- Documentation: `--ignorer-waf` decision rule (when overrule is legitimate),
  `etat` explicitly clarified as declarative — never a gate — correcting a
  real misreading of `pret_a_agir` by a partner model on v1.18.0's release;
  the guide-lock's cooperative-nature limit documented rather than hardened;
  qualitative (unmeasured, no invented number) depth guidance for
  `iframe_chemin`; reference-safe assertion guidance for
  `--replay-verifier`/`monitor-verifier.sh` (assert shape, not volatile
  values); zero-delay guidance for `min_action_delay_ms` on local targets
  (shipped default of 800 ms unchanged — a deliberate choice protecting an
  unconfigured first run against the public internet, not a doctrine of
  slowness); new `docs/ACCESS_OBSERVATIONS.md` registry (neutral, dated
  access outcomes — seeded from the already-published FR-77/FR-79 data only).

**Debian package:** `diwall_1.19.0-1_all.deb` built (`dpkg-buildpackage -us
-uc -b`), `lintian` within the same accepted tolerances as v1.18.0 (`/opt`
placement, per-file interpreter path, missing man pages — inherent to a
self-distributed package outside the official archive, not new).

**Real install/remove test on the development/production machine** (git-clone channel cleanly uninstalled
first via `uninstall.sh`, vault/journal config backed up and restored)
uncovered two real `postinst` bugs, invisible to static inspection:

- `/opt/diwall/references/` (target of `watch.py --sauver-reference`) was
  never created — `install.sh` (git-clone channel) does this, `postinst`
  did not. Fresh install failed with `PermissionError`.
- `shot.py`/`watch.py`/`rpa.py`/`journal.py` were never chmod'd to `755` by
  `postinst` (`dh_fixperms` leaves regular files at `644`). `watch.py`
  invokes `shot.py` as a direct subprocess (shebang + execute bit, not
  `python3 shot.py`) — fresh install failed with `PermissionError`.
  `deploy.sh` (git-clone channel) already sets this.

Both fixed in `debian/postinst`, package rebuilt, full cycle replayed
(purge → reinstall → 3/3 smoke test → `preflight-publication.sh` exit 0) —
green on the development/production machine. Source and deployed code/docs confirmed byte-identical
(`diff -rq`). The development/production machine now runs the `.deb` channel in production.

**Process fix:** this live test was initially treated as a risky action
requiring prior confirmation — corrected: it is now a mandatory, automatic
step of any cycle touching packaged files (`PROTOCOLE_CLOTURE.md` instruction
1bis, private `_CADRE/`), never deferred.

**Validation:** see the session's ADDENDUM for exact commands and full
regression results.

**Technical decision:** `watch.py` untouched this cycle — no functional
change to it, matching the per-file version bump discipline already in place.

## 2026-07-04 — Closure hygiene: remaining hardcoded hostname

**Work done:** closure audit (`PROTOCOLE_CLOTURE.md` instruction n°1) found
the development/production machine's real hostname still hardcoded in four
places — three in prose (`docs/JOURNAL.md`, `docs/RETOUR_EXPERIENCE.md`,
two occurrences) and two in a test fixture
(`scenarios/v1.4_validation/verifier.py`, a `diwall_meta` example payload).
Reworded to generic phrasing / generic fixture values respectively. No
functional change — `test_t1_mutatif_preuves` re-verified green after the
rename. `scripts/preflight-publication.sh`'s closure rsync check
(`PROTOCOLE_CLOTURE.md`) also gained a `--exclude='debian/'` entry, missing
since the Debian packaging work below introduced that directory.

---

## 2026-07-03 — Debian package (native `.deb`, alternative distribution channel)

**Work done:**

- Native `debhelper` packaging (`debian/control`, `changelog`, `copyright`,
  `rules`, `postinst`, `postrm`) — an alternative to the existing git-clone +
  `install.sh` channel, never a replacement. Packages v1.18.0 as-is, no
  functional version bump on `shot.py`/`rpa.py`/`watch.py`.
- `postinst` mirrors `install.sh`'s logic (system user/group, venv, pip,
  Chromium via Playwright) — network access required at install time,
  documented in `debian/control`. `Architecture: all` — no per-arch binary
  content.
- Configuration moves to `/etc/diwall/diwall.conf` on this channel (a native
  Debian conffile location), distinct from the git-clone channel's
  `/opt/diwall/diwall.conf` — both paths coexist, never conflated.
- `lib/repertoire_chiffre.py::_lire_conf()` now respects the `DIWALL_CONF` environment
  variable (previously only `_chemin_vault()` did) — fixes a latent
  inconsistency where `shot.py`'s Citizen Navigation caps
  (`_conf_navigation()`) silently ignored `DIWALL_CONF`, unlike vault
  resolution. Purely additive: unset `DIWALL_CONF` preserves the exact prior
  default (`/opt/diwall/diwall.conf`).
- Six `/usr/bin/diwall-*` wrapper commands (`diwall-shot`, `diwall-rpa`,
  `diwall-watch`, `diwall-monter-secrets`, `diwall-demonter-secrets`,
  `diwall-monitor-verifier`) — thin, non-invasive: `monter-repertoire-chiffre.sh` /
  `demonter-repertoire-chiffre.sh` themselves are untouched, the wrapper alone injects
  `--config /etc/diwall/diwall.conf`.
- `postrm` distinguishes `remove` (code + venv + system user/group) from
  `purge` (also removes `/var/log/diwall` and `/etc/diwall`). `~/Vaults/` is
  never touched by either — outside dpkg's purview by construction.
- `scripts/preflight-publication.sh` scope extended to `debian/*` (no file
  extension on `control`/`postinst`/`postrm`/`rules` meant they were
  previously unscanned); three documented exceptions added for the
  Maintainer/Homepage/Copyright fields Debian's own format requires.

**Validation:** package builds cleanly (`dpkg-buildpackage -us -uc -b`),
`lintian` clean of all actionable findings (remaining warnings — `/opt`
placement, per-file interpreter path, missing man pages — are accepted,
consistent with a self-distributed package outside the official Debian
archive). Installed and removed on a live host: `postinst`/`postrm` both
idempotent, vault and journal data untouched throughout. Regression:
`v1.17.2_validation` 4/4, `v1.18.0_validation` 5/5.

**Docs:** `README.md`, `docs/MANUEL.md` (new section 1a) — installation via
`.deb`, command table, config path difference, `remove`/`purge` semantics.

---

## 2026-07-03 — Session 48 (v1.18.0 — Guide-read lock, mode_conseille, nested iframes, structural monitoring)

**Work done:**

Five items, planned in trilateral (operator + Claude + Gemini) with direct
field input from a Claude instance on a partner project (Sillage) that
surfaced the read-lock friction firsthand.

- **Mandatory guide-read lock (`--guide-version`) and `--version`:**
  `shot.py`, `rpa.py`, and `watch.py` now refuse to run without proof of
  reading `docs/GUIDE_LLM.md` — a hard `exit 1` (`guide_non_lu`) rather than
  a warning, unless a local marker (`~/.config/diwall/guide_state.json`) from
  a previously validated call already exists. The only deliberate exception
  to the project's additive-only design: documentation alone had repeatedly
  failed to be read before first use. `--version` reports the installed
  version immediately, without launching Playwright.
- **`mode_conseille`:** a new advisory sub-object of `etat`, computed from
  the operations journal's history for the current host — never a guess.
  Present only when a prior `diagnostic_dom.json` run detected a JS framework
  or Shadow Roots for that host; recommends `--mode`, `--shadow-dom`, and
  `--som-rafraichir` accordingly, never applied automatically.
- **Nested iframes (`iframe_chemin`):** `cliquer_iframe`/`remplir_iframe`
  accept an ordered array of selectors for iframe-inside-iframe descent.
  Deliberately not a pluralised name of the existing `iframe_selecteur` — the
  two are mutually exclusive by schema constraint, to avoid a one-letter
  mix-up on generated actions.
- **`scripts/monitor-verifier.sh`:** a one-pass orchestration script wrapping
  the existing `--no-capture` + `--replay-verifier` composition — zero image,
  zero LLM call. Silent on a stable run, an `ntfy` push on regression.
  Repetition over time is left to cron/systemd-timer, not an internal loop.
- **Interoperability fixtures:** `scenarios/interoperabilite/` — `example.com`
  as a neutral witness plus a fully Diwall-controlled local HTML fixture
  (nested iframe, open Shadow DOM component, form), for structural
  non-regression that does not depend on third-party sites remaining
  unchanged.

**Validation:** `scenarios/v1.18.0_validation/` 5/5. Regression:
`v1.15.2_validation` 4/4, `v1.16.0_validation` 7/7, `v1.17.0_validation` 4/4,
`v1.17.2_validation` 4/4 — seeded with a valid guide-read marker beforehand,
the one deliberate non-additive change of this cycle. Preflight exit 0.
Commit `ec4e35d`.

**Post-release fixes:** `lib/preflight_guide.py` was missing from `deploy.sh`'s
`CODE_FILES`, breaking every real call on `/opt/diwall/` right after the first
deploy (`--version` still worked, since it exits before the faulty import —
caught within minutes, before any real usage). Three docs pointed
`monitor-verifier.sh` at `/opt/diwall/scripts/`, which does not exist
(`scripts/*.sh` is never deployed). Commit `4a8a903`.

**Cold-install regression found and fixed:** `install.sh`'s own smoke test and
`preflight-publication.sh`'s smoke test both called `shot.py`/`watch.py`
without `--guide-version` — on any environment without a pre-existing local
marker (a genuinely fresh machine, a new operator account, CI), both would
fail with `guide_non_lu`. Masked in initial testing by an already-valid
personal marker from earlier manual verification. Found while preparing a
full cold-reinstall test, fixed before running it. Commit `480b55e`.

**Full cold-install validation:** `uninstall.sh --confirme` (complete removal:
`/opt/diwall/`, `/var/log/diwall/`, system user/group, pre-push hook —
`~/Vaults/`, git sources, and the Playwright cache confirmed preserved) then
`install.sh` from scratch (fresh user/group/venv/Chromium, 37 files deployed,
permissions check, integrated smoke test) — passed on the first run with the
fix in place. `scenarios/v1.18.0_validation/` 5/5 and all four regression
suites replayed against the fresh install, all green. Source/production
checksum-identical.

**Release:** `v1.18.0` — tag created, pushed, GitHub release published in English.

**State on exit:** production `/opt/diwall/` synchronised, validated via a
complete cold reinstall, not just a hot deploy.

---

## 2026-07-03 — Session 48 (v1.17.2 — Vault write guard and reliability fixes)

**Work done:**

Four fixes, each verified against the production code before being scheduled,
addressing a security gap and three reliability issues surfaced through real
operator use.

- **Vault write guard:** the operations journal and mutative-run proof
  archiving previously wrote to their configured path without checking
  whether the vault directory was actually mounted. If closed at write time,
  entries were silently written in clear text to the raw host directory.
  Both write paths now check the mount state first and redirect to the
  existing local fallback (`/tmp/diwall/operations.fallback.jsonl`) instead
  of writing into the unmounted vault path.
- **Set-of-Mark identity fix:** repeated SoM captures within the same page
  could leave a stale `data-dw-som-id` attribute on an element no longer
  matched, colliding with a freshly numbered element and risking a
  `--som-rafraichir` resolution to the wrong target. The injector now purges
  prior markers before renumbering.
- **WAF detection false positives reduced:** generic vendor names
  (`cloudflare`, `akamai`) are now matched only against the page title
  instead of the full raw HTML, eliminating false positives on pages loading
  an ordinary CDN resource. A new `--ignorer-waf` flag lets the operator
  override a residual false positive without disabling the signal entirely.
- **`--checkpoint` progress fix:** a run stopped by a citizenship cap
  (`max_actions_par_run`/`max_pages_par_run`) returns the same success signal
  as a fully completed run — the checkpoint file was being deleted in this
  case too, losing all remaining progress on long scenarios. It is now
  updated with the actual progress instead, matching the existing
  partial-failure behavior.

**Validation:** `scenarios/v1.17.2_validation/` 4/4. Regression:
`v1.15.2_validation` 4/4, `v1.16.0_validation` 7/7, `v1.17.0_validation` 4/4.
Preflight exit 0. Commit `102dfb6`.

---

## 2026-07-02 — Session 47 (documentation follow-up, no version change)

`scripts/*.sh` live only in the git source repository — `deploy.sh` never
copies that directory to `/opt/diwall/`. `README.md`, `docs/GUIDE.md`, and
`docs/MANUEL.md` referenced these scripts inconsistently: some as a bare
relative path (correct only if already `cd`'d into the repo root, never
stated), one (`docs/MANUEL.md`, vault mount instructions) as
`/opt/diwall/scripts/monter-repertoire-chiffre.sh` — a path that does not exist. All
occurrences now use the absolute path `~/git/Diwall/Diwall/scripts/<script>.sh`,
consistent with the rest of the documentation.

---

## 2026-07-02 — Session 47 (v1.17.1 — Documentation quality pass)

**Work done:**

Full documentation pass across `docs/` and `README.md`, bringing every public
reference current with the capability shipped through v1.17.0. Documentation-
only — no functional change to `shot.py`/`rpa.py` logic.

- **`docs/MANUEL.md`** — brought to 1.17.1. New sections covering the
  deterministic `etat` verdict, `operation_id`, the passive WAF signal,
  `--replay-verifier`, `--checkpoint`, `--som-rafraichir`, and cross-origin
  iframe actions (`cliquer_iframe`/`remplir_iframe`) — each with a working
  example. Action table, CLI flag tables, and output JSON structure updated
  to match. The stealth benchmark section now uses a quantitative
  fingerprint-count method instead of a visual screenshot comparison.
- **`README.md`** — usage example corrected (`--url`, not the nonexistent
  `--navigate`), vault encryption status clarified as supported since v1.5.0,
  capabilities and requirements tables extended through v1.17.0. The
  long-superseded "Roadmap (v1.7)" section removed — those items (Shadow DOM,
  cross-origin iframes) have been shipped for several release cycles.
- **`docs/FAQ_LLM.md`** — cross-origin iframe support documented (v1.17.0),
  `boussole` field reference and version-history table extended through
  v1.17.0.
- **`docs/GUIDE.md`, `docs/GUIDE_EXPLORATION.md`** — Citizen Navigation
  summary, WAF signal guidance, and v1.17.0 exploration checklist items
  (iframe detection, `--som-rafraichir` on highly dynamic pages) added.

**Validation:** preflight exit 0. Regression: `v1.17.0_validation` 4/4,
`v1.16.0_validation` 7/7, `v1.15.2_validation` 4/4.

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
  `remplir_iframe` supports `depuis_secrets`/`depuis_secrets_totp` like `remplir`.
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
asserts `depuis_secrets` and `secret_cle` are absent from the raw journal line.
Both now legitimately appear inside `actions_raw` (introduced in v1.6.0 for
`--exporter-skill`) — by design, `depuis_secrets` and `secret_cle` are key
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
- `lib/repertoire_chiffre.py`: opt-in SHA256 checksum via `SecretsChecksumError` + `_verifier_checksum()`.
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
- Full neutralisation of 8 scenario files: credentials → `depuis_secrets`,
  internal hosts → `__HOST_ADMIN__`, named identifiers → vault keys.
- `CLAUDE.md`: Rule n°6 added — every `password` field in a scenario must use `depuis_secrets`.
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

- `lib/repertoire_chiffre.py` — two fixes:
  - Distinct messages in `lire_credential_fichier` and `verifier_cles_fichier` (FR-71):
    "non-existent directory (vault not mounted?)" vs "existing directory not mounted
    (raw disk rejected)".
  - `_coffre_est_monte` (FR-72): parses column 2 of `/proc/mounts` and now accepts
    subdirectories of a FUSE vault (`path.startswith(mountpoint + "/")`). Restricted
    to FUSE fstypes to preserve T1. Semantic drift identified by Gemini: Sillage was
    blocked with `SecretsFermesError(42)` when storing credentials in a vault subdirectory.

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

- `lib/repertoire_chiffre.py` — three new functions:
  `lire_credential_fichier(path, key)` — reads from designated file with mount check T1;
  `verifier_cles_fichier(path, keys)` — fail-fast pre-validation of keys;
  `lire_totp_fichier(path)` — TOTP generation from designated file.

- `shot.py` — fail-fast venv (`find_spec("playwright")` absent → explicit message + exit 3);
  `--secrets <file>` argument in `parse_args()`;
  `secrets_chemin` parameter in `executer_actions()` with full T3 coverage:
  `depuis_secrets`, `depuis_secrets_totp` (×2: remplir + remplir_som), `attendre_mfa_ntfy` (ntfy_topic).

- `rpa.py` — `--secrets` argument; `verifier_cles_fichier` import; bifurcated pre-validation
  (`verifier_cles_fichier` if `--secrets`, `verifier_cles` otherwise); propagation to shot.py subprocess.

- `docs/GUIDE_LLM.md` v2.5 — section "Multi-vault and explicit credential files":
  use cases, syntax, Diwall JSON format, T3 coverage, T1 doctrine + honest limit,
  T4 limit, T6 perception surface.

- `__version__` → `1.10.0` on `shot.py`, `rpa.py`, `journal.py`.

**Test results:**
T-A1 green (read from mounted vault, correct value).
T-A2 green (`SecretsFermesError(42)` on non-mounted directory, exit 42).
T-A3 green (`FileNotFoundError`, exit 1, explicit message).
T-B1 green (fail-fast missing key before Playwright via rpa.py, 126ms).
T-B2 green (TOTP read from designated file, 6-digit code).
T-C1 green (message "run via /opt/diwall/venv", exit 3).
T-C2 green (exit 3 cleanly relayed by rpa.py).
T-D1 green (without `--secrets`: behaviour strictly identical to v1.9.8).
Preflight exit 0. Smoke tests 3/3.

**Note T-A2:** `/tmp` on the deployment machine is a mounted tmpfs — SecretsFermesError does not trigger on `/tmp`.
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
already implemented in `lib/repertoire_chiffre.py` during session 16 — without spec or marking.
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

- `lib/repertoire_chiffre.py` — removal of silent fallback `~/Vaults/Diwall`.
  New exception `SecretsNonConfigureError` (exit 43) raised if `diwall.conf` absent
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
  (FR-54, FR-55, FR-56, FR-58 DIWALL_SECRETS_DIR vs DIWALL_CONF).
- `docs/RETOUR_EXPERIENCE.md` — frictions #52–#56, session 19 summary.
- `docs/RADAR_MODELES.md` created — raw observation log on LLM behaviour with Diwall
  (2 entries: Claude Sonnet pre-fixes / Gemini Flash).

**Key decision:** `RADAR_MODELES.md` public, no editorial filter. The visibility doctrine
says silence on *promotion*, not on reality. False positives are included — they are the signal.

**Gemini Flash benchmark:** same multi-target exercise, post-fixes. Results
correct, `depuis_secrets` used consistently, curl trap ignored. Single drift:
FR-58 (DIWALL_SECRETS_DIR), self-corrected. Validation of perception/action doctrine.

**Commits:**
- `84100a1` — feat(v1.8): wait primitives, nettoyer_overlay, vault symlink fix, deploy docs
- `6982639` — fix(v1.8): FR-54 --actions file in Mode B, FR-55 attendre_url attendre_changement
- `7c84e01` — fix: neutralise client name in session 19 summary
- `9ca4d85` — docs(v1.8): FR-58 DIWALL_SECRETS_DIR vs DIWALL_CONF, fix obsolete mentions

**Release:** `v1.8.0` — tag created, pushed, GitHub release published in English.

**State on exit:** production `/opt/diwall/` synchronised. 56 frictions / 19 sessions.

---

## 2026-06-09 — Session 18 (FR-47 to FR-53, v1.9)

**Context:** PHASE_EXECUTION validated by operator after co-planning with Gemini.
6 frictions to implement (FR-47, FR-48, FR-49, FR-50, FR-53; FR-52 cancelled).
Incomplete JSON schema (refs without definitions).

**Work done:**

- `lib/repertoire_chiffre.py` (FR-47) — symlink security: `glob.glob` replaced by
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

## 2026-06-15 — Session 30

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

## 2026-06-12 — Session 26

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
