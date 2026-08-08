% DIWALL(1) | Diwall commands
%
% July 2026

# NAME

diwall - visual perception and RPA toolkit for LLM agents

# SYNOPSIS

**diwall-shot** \[*options*\] **--url** *URL*

**diwall-rpa** \[*options*\] **--scenario** *FILE*

**diwall-watch** \[*options*\]

**diwall-monter-secrets** \[*options*\]

**diwall-demonter-secrets** \[*options*\]

**diwall-monitor-verifier** **--scenario** *FILE* **--reference** *FILE*

# DESCRIPTION

Diwall gives an LLM agent eyes and hands on web interfaces it cannot
otherwise see or operate: screenshots, Set-of-Mark annotation and an
accessibility tree on one side, Playwright-driven actions on the other.
Every command prints a single JSON object on standard output, designed to
be read by a program rather than by a human.

This package installs six commands under **/usr/bin**. They are thin
wrappers around the Python entry points in **/opt/diwall**, and they read
their configuration from **/etc/diwall/diwall.conf** instead of the
**/opt/diwall/diwall.conf** used by the git-clone installation channel.

There is one manual page for all six commands, on purpose: a single page
cannot drift out of sync with itself. For the exhaustive option list of any
command, run it with **--help** — that output is always authoritative over
this page.

# COMMANDS

**diwall-shot**
: Captures a page and returns JSON describing it. With **--som**, interactive
elements are numbered in the screenshot so an agent can refer to them by
index; with **--a11y**, the accessibility tree is included. Actions can be
executed in the same browser session via **--actions**.

**diwall-rpa**
: Executes a scenario file (JSON or YAML) describing a sequence of actions,
and returns one JSON line. This is the command to use for anything
repeatable, and the only one that evaluates scenario assertions.

**diwall-watch**
: Visual monitoring. Saves a reference image of a page, then compares later
captures against it — pixel diff locally, or a description by a local vision
model. Used for detecting visual regressions without a human looking.

**diwall-monter-secrets**, **diwall-demonter-secrets**
: Mount and unmount the gocryptfs-encrypted credentials directory. Diwall refuses
to resolve any credential while it is closed, exiting with status 42
rather than falling back to anything weaker.

**diwall-monitor-verifier**
: Runs one structural non-regression pass of a scenario against a saved
reference and exits non-zero on divergence. Intended to be driven by cron or
a systemd timer; it contains no loop of its own.

# COMMON OPTIONS

The options below are shared by **diwall-shot** and **diwall-rpa** unless
stated otherwise. This is a selection, not the full list.

**--guide-version** *X.Y*
: Mandatory proof that **/opt/diwall/docs/GUIDE_LLM.md** was read. Without it
— and without a still-valid local marker — the command refuses to run and
exits 1. The expected value is the *notice-version* comment on line 3 of that
guide. This is the one place where Diwall is not opt-in.

**--version**
: Print the installed version as JSON and exit, without starting a browser.
Distinct from **--guide-version**; the two numbers are unrelated.

**--mode** *fast*|*full*
: *fast* is **--no-capture --a11y**: no PNG, roughly two seconds quicker,
enough to read state. *full* is the default and captures the rendering.

**--som**
: Number the visible interactive elements in the capture, so that actions can
target them by index instead of by CSS selector.

**--wait-until** *networkidle*|*load*|*domcontentloaded*
: When the initial navigation is considered finished. The default,
*networkidle*, waits for 500 ms of network silence and is right for most
targets. A page that polls continuously never goes silent — use *load* there;
raising **--timeout** cannot help, since the page will never finish.
**diwall-shot** only.

**--timeout** *MS*
: Per-operation timeout in milliseconds (default 10000). Distinct from
**--screenshot-timeout** (default 120000), which covers the screenshot alone.

**--stealth**
: Remove the automatic markers that identify a headless browser. It does not
change the operator's IP address and does not forge an identity — the point
is equal treatment, not disguise.

**--secrets** *FILE*
: Resolve credentials from an explicit JSON file inside a mounted directory,
instead of the default host-based lookup.

**--no-evaluer**
: Refuse the **evaluer** action for the whole run — arbitrary JavaScript is
not executed on the target page.

**--no-filtre-evaluer**
: Disable stdout neutralisation of **evaluer** return values, URLs and error
messages — explicit debug runs only. Neutralisation is on by default; when
disabled, `boussole.filtre_evaluer_actif: false` is set in the output so the
operator can audit it from the JSON itself.

# FILES

**/etc/diwall/diwall.conf**
: Configuration read by the packaged commands. Created by the operator, never
generated automatically. The **DIWALL_CONF** environment variable overrides
this path, which is how several projects keep separate configurations on one
machine.

**/opt/diwall/**
: Application code, the Python virtual environment, and the documentation
that the commands themselves refer to.

**/opt/diwall/docs/GUIDE_LLM.md**
: The entry point an agent is required to read. **MANUEL.md** in the same
directory holds the exact commands with real paths.

**/var/log/diwall/**
: Append-only operation log. Preserved on **apt remove**, deleted on
**apt purge**.

**/tmp/diwall/**
: Captured PNG files, cleared on reboot.

# EXIT STATUS

**0**
: The run completed. Note that an HTTP 404 or 403 on the target is reported
in the JSON, not as a failure of the command.

**1**
: The run failed, or the guide-read pre-flight was not satisfied
(*guide_non_lu*).

**2**
: Incompatible arguments, rejected before any browser was started.

**42**
: The credentials directory is closed. Mount it with **diwall-monter-secrets**.

**43**
: A credentials integrity checksum did not match.

# EXAMPLES

Capture a page with numbered elements and the accessibility tree:

    diwall-shot --url https://example.com --som --a11y --guide-version 1.2

Read only the state of a page, without producing an image:

    diwall-shot --url https://example.com --mode fast --guide-version 1.2

Reach an administration panel that refreshes statistics continuously:

    diwall-shot --url http://target.local/ --wait-until load --som

Run a scenario with credentials from an explicit file:

    diwall-rpa --scenario ./login.json --secrets ~/Vaults/project/creds.json

Check that a page has not structurally regressed:

    diwall-monitor-verifier --scenario ./page.json --reference ./page.ref.json

# SEE ALSO

Full documentation is installed with the package:
**/opt/diwall/docs/MANUEL.md** for the operator manual,
**/opt/diwall/docs/GUIDE_LLM.md** for the agent-facing guide,
**/opt/diwall/docs/FAQ_LLM.md** for capability-by-version answers.

The project homepage is listed by **apt show diwall**.
