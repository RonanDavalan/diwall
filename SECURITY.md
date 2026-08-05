# Security Policy

Diwall handles credentials (via the encrypted secrets directory) and drives
a real browser session on behalf of an LLM. A vulnerability here has a real
cost for whoever runs it — this policy exists so it gets reported before it
gets exploited.

## Supported versions

Only the latest published release is supported. Diwall does not maintain
parallel maintenance branches; a fix lands in the next release, not as a
backport to an older tag.

## Reporting a vulnerability

**Do not open a public GitHub issue.** A public issue discloses the
vulnerability before a fix exists, exposing everyone currently running
Diwall.

Report privately via **GitHub Security Advisories**:
<https://github.com/ronandavalan/diwall/security/advisories/new>

If that path is unavailable to you, open a regular issue asking for an
alternate private contact — do not include vulnerability details in it.

## What to expect

- Acknowledgement within **72 hours**.
- A good-faith, coordinated disclosure is never met with legal action —
  report responsibly and it stays that way.
- Fixes ship as a normal release once verified; the report stays private
  until then, and credit is given in the release notes if you want it.

## Scope

This policy covers the code in this repository: `shot.py`, `rpa.py`,
`watch.py`, `journal.py`, and everything under `lib/`. It does not cover:

- Unofficial forks or modified copies.
- Versions predating the current release — see "Supported versions" above.
- The `diwall.davalan.fr` website, which is a separate, unrelated codebase.
