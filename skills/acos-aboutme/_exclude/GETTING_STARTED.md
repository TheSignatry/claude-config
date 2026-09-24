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

- **`acos-aboutme`** — the shared identity/org-chart profile. No analysis
  logic of its own; every other skill below reads from it. Installing this
  alone does nothing observable — it only stores data for the others to
  read. It also ships `scripts/state_backup.py`, the snapshot/restore tool
  that protects every acos skill's `state/` folder.
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
any skill later just reads what's already saved — you're never asked twice.

Adding a second skill later that needs a field the first enrollment didn't
ask about (e.g. installing `acos-jira-analysis` after enrolling via
`acos-calendar-analysis`) prompts for that specific gap rather than a full
re-enrollment.

**What an upgrade does and does not carry forward.** Organization-wide
settings are not in your profile at all — they ship in each skill's
`references/defaults.json` (see the next section), so a new release's
retuned values reach you on upgrade without you doing anything. Personal
fields are different: a field added to the profile schema after you
enrolled is simply absent from your file, and skills treat absent as "not
provided" rather than erroring. Nothing detects that for you yet, so after
upgrading, if a feature that depends on a new personal field seems inert,
ask `acos-aboutme` to set it — `owner.pronouns` and
`jira_workspaces.cloud_id` are both fields that arrived this way.

## Two config files per skill: shared defaults, then your own

Each skill that has configuration splits it in two, and reads both:

- **`references/defaults.json`** ships inside the skill and holds everything
  identical for everyone — `acos-aboutme` carries the Jira site and Product
  Discovery field IDs, the Functional Area vocabulary, the time-allocation
  benchmark tables and default working hours; `acos-email-sort` carries the
  whole classification vocabulary, folder names, thresholds and
  operational-alert senders. You do not edit these. They arrive with the
  package and change when a new version ships.
- **`state/profile.json`** (and `acos-email-sort/state/config.json`) hold
  only what is personal.

A skill loads the defaults, then overlays your file. Any key you set wins;
anything you omit falls back. Dicts merge key by key, so overriding one
working-hours day keeps the rest.

**Why it matters for upgrades.** Before this split, shared values lived in
the profile schema, so anyone who had already enrolled kept their original
copy forever and never saw a central retune. Two real bugs came from that:
Functional Area tagging ran silently with zero rules, and the Jira site
hostname was missing outright. Set a key in your own file only when you
mean to differ from the organization — doing so opts that key out of
future updates.

## This is personal data, not shared

Everything under any skill's `state/` is gitignored — the rule is
`skills/*/state/*` with a `!skills/*/state/.gitkeep` negation, so only the
empty-directory marker is ever committed. Each person who installs these
skills gets their own profile and config, never someone else's.

Three independent layers keep it that way, because one is not enough:

1. **`.gitignore`** keeps it out of the repo. The rule used to be
   `state/*.json`, which silently let `acos-email-sort/state/run_history.jsonl`
   be committed for six commits before it was caught.
2. **`skills/package_skill.py`** excludes `state/` from the built zip,
   keeping only `state/.gitkeep`. Before this rule the packaged
   `acos-aboutme` and `acos-email-sort` zips carried 108 real email
   addresses between them, and a zip is exactly what gets uploaded for
   distribution.
3. **`skills/lint_skills.py`** (`check_no_shipped_state`) fails the build
   if any state file is *tracked in git*. It deliberately tests tracked
   rather than present, because this repo doubles as the runtime
   environment — your live profile always sits in the working tree.

## Backing up your profile, and restoring it

`state/` is gitignored and excluded from the packaged zip, so neither git
nor a reinstall is your safety net. An `acos-aboutme` profile has already
been lost once to a working-tree restructure and had to be recovered from
a stray download. Use the backup tool, which now ships **inside
`acos-aboutme`** so it is available wherever the skill is installed, not
only in this repository:

```bash
# from the repo
python3 skills/acos-aboutme/scripts/state_backup.py

# from an installed skill folder
python3 scripts/state_backup.py

python3 scripts/state_backup.py --roots        # what would be covered
python3 scripts/state_backup.py --list         # snapshots, newest first
python3 scripts/state_backup.py --verify LABEL
python3 scripts/state_backup.py --restore LABEL
python3 scripts/state_backup.py --restore LABEL --skill acos-aboutme
```

`LABEL` is the UTC timestamp `--list` prints, e.g. `20260924T174557Z`.

**You probably have two live copies of this state, not one.** The skills
you actually run live in your installed skills folder — Console-synced
skills land as siblings under
`~/.claude/skills/synced/<id>/` — while a maintainer also has a checkout
under `<repo>/skills/`. Those two copies drift apart, and a Console
re-sync can replace the installed folder wholesale. The tool discovers
every root it can see, snapshots all of them, keeps each root's files
separate inside one snapshot, and restores each file to the copy it came
from. Run `--roots` first to see what it found; add another location with
`--root PATH`.

Snapshots land in `~/.claude/acos-state-backups/<UTC timestamp>/`,
deliberately **outside** every skill folder, so they survive a clone, a
branch switch, a clean checkout, a restructure, `git clean -fdx`, and a
re-sync. Each snapshot carries a `manifest.json` recording every file's
source root, size, SHA-256 and the skill version at the time.

**Take a snapshot before upgrading a skill, before re-running enrollment
over an existing profile, and before any bulk profile edit.** `--restore`
refuses to overwrite a live file that differs from the snapshot unless you
pass `--force`, so a restore cannot silently discard a profile you have
since rebuilt. If a recorded root no longer exists it says so and restores
the rest. To pull one specific copy into a new location, combine `--root`
with `--from-root` (use `--list-roots LABEL` to see the choices); a
redirect that would merge two roots onto the same paths is refused rather
than letting one overwrite the other.

Snapshots taken before September 24, 2026 use the older single-root
layout. The tool refuses to restore those rather than misplacing them —
copy files out of the snapshot folder by hand if you need one.

## Data handling

Only names, emails, and business-contact-type org-chart facts belong in
the profile — permitted Confidential data under IT14/IT15. Never enter
Restricted data (SSNs, financial/bank details, health information,
credentials) during enrollment, even if asked for by name in a template —
decline and point to IT15 if that ever comes up.

## Distribution status

**Beta, distributed org-wide since September 2026.** All five skills are
packaged and uploaded to the Console Skills page like the `signatry-*`
family, and beta testers enable all five on their own accounts — they
depend on each other, so a partial install is not supported. The
team-facing walkthrough is the *acos Beta Skills Setup Guide* (Technology
Team, September 2026), which covers connectors, enrollment, the seven
Outlook folders, first runs, and the beta's known limitations. This file
is the maintainer's companion to it, not a replacement.

Two consequences for anyone changing these skills:

- **Package for real.** `python3 skills/package_skill.py <skill>` and
  upload the zip, per the root `README.md`'s "Org-wide deployment"
  method. Committing to this repo does not deploy anything.
- **The setup guide carries a version table.** Bump a skill and that
  table goes stale — reissue the guide, or at least the table, alongside
  the upload so testers are not reading last release's numbers. **It is
  stale for all five right now**: as of 2026-09-24 the repo holds
  `acos-aboutme` 0.8, `acos-calendar-analysis` 0.5, `acos-jira-analysis`
  0.5, `acos-email-sort` 0.9 and `acos-main` 0.4, and none of those have
  been uploaded yet — the installed copies are still 0.4 / 0.4 / 0.3 /
  0.5 / 0.3. Tell testers to take a state snapshot before they pick up
  the new build.

The root `README.md`'s skill table now lists all five acos skills
alongside the `signatry-*` family, with a footnote pointing back here.
Keep the versions in that table in step when you bump one.

Because they now ship, nothing owner-specific belongs in a shipped file:
no real names, addresses, project keys, or example subject lines drawn
from one person's mailbox. Identity lives in `state/`, which is
gitignored and excluded from the zip; organization-wide facts that every
tester shares — the Jira site hostname, for instance — are fine in
`references/*.example.json`.

## Extending the family

Building a new sibling skill that should read this shared profile? See
`acos-aboutme/SKILL.md`'s "For skill authors" section for the technical
contract — how to read the profile, what degrades gracefully vs. what
should fail loudly, and which one field (`calendar_analysis.known_meeting_series`)
is the sole exception to "read-only from every other skill."
