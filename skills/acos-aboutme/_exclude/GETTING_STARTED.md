# Getting started with the acos family

This is a human-facing setup guide, not something Claude reads. It lives here
(`_exclude/`) specifically because that folder is excluded from
`package_skill.py`'s zip and never loaded into Claude's context — see the
root `README.md`'s "Skills" section for that convention. If you're looking
for what Claude itself is told to do on first run, see each skill's own
`SKILL.md` — "Enrollment" section for `acos-aboutme`/`acos-email-sort`,
"Config (read from acos-aboutme)" for the rest.

## What this is

A small personal productivity suite of five skills that share one identity
profile instead of each asking you the same setup questions:

- **`acos-aboutme`** — the shared identity/org-chart profile. Holds no logic
  of its own; every other skill below reads from it. Installing this alone
  does nothing observable — it only stores data for the others to read.
- **`acos-calendar-analysis`** — calendar time-classification, conflict
  detection, schedule health, and time-allocation benchmarking.
- **`acos-jira-analysis`** — deterministic overdue/upcoming Jira reporting.
- **`acos-email-sort`** — morning inbox triage into an Outlook folder
  taxonomy, plus drafted (never sent) vendor declines.
- **`acos-main`** — the orchestrator: runs the others together for a
  morning/week/month plan.

## Install

All acos-family skills you want must live as **sibling folders** under the
same parent skills directory — every consumer skill hardcodes a relative
path to the shared profile (e.g. `../acos-aboutme/state/profile.json` from
its own folder). Install each one the same way the root `README.md`
already describes under "Local development/testing" (symlink or copy the
folder into `~/.claude/skills/` or a project's `.claude/skills/`) — nothing
acos-specific about the mechanism itself, just the sibling-folder
requirement.

**Minimum viable install:** `acos-aboutme` plus at least one consumer skill.
`acos-jira-analysis` and `acos-email-sort` also support a local-only
fallback config if you'd rather skip installing `acos-aboutme` entirely —
see their own `SKILL.md` for what that looks like. `acos-calendar-analysis`
has no such fallback; it requires `acos-aboutme`.

## Enrollment

Nothing to configure by hand ahead of time. The first time any acos skill
runs and doesn't find `acos-aboutme/state/profile.json`, it asks you a
short set of setup questions itself and saves the answers there. Re-running
any skill later just reads what's already saved — you're never asked
twice. Adding a second skill later that needs a field the first enrollment
didn't ask about (e.g. installing `acos-jira-analysis` after already
enrolling via `acos-calendar-analysis`) just prompts for that specific gap,
not a full re-enrollment.

## This is personal data, not shared

`state/*.json` under both `acos-aboutme` and `acos-email-sort` is
gitignored (`skills/acos-aboutme/state/*.json`,
`skills/acos-email-sort/state/*.json` in this repo's `.gitignore`). Each
person who installs these skills gets their own profile and config —
never someone else's — and none of it is ever committed to this repo.

## Data handling

Only names, emails, and business-contact-type org-chart facts belong in
the profile — permitted Confidential data under IT14/IT15. Never enter
Restricted data (SSNs, financial/bank details, health information,
credentials) during enrollment, even if asked for by name in a template —
decline and point to IT15 if that ever comes up.

## Distribution status

Unlike the `signatry-*` skill family, acos-family skills aren't (yet)
packaged and uploaded to the Console Skills page — install locally only,
per the root `README.md`'s "Local development/testing" method, not its
"Org-wide deployment" one. That's also why they're intentionally left out
of that README's tracked skill table, which represents what's actually
distributed org-wide.

## Extending the family

Building a new sibling skill that should read this shared profile? See
`acos-aboutme/SKILL.md`'s "For skill authors" section for the technical
contract — how to read the profile, what degrades gracefully vs. what
should fail loudly, and which one field (`calendar_analysis.known_meeting_series`)
is the sole exception to "read-only from every other skill."
