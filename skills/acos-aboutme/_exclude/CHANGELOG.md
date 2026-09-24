# Changelog

All notable changes to this skill are documented here, newest first.

## 0.8 — 2026-09-24

**The state backup tool now ships with the skill, and covers the copy that actually runs.** It was `skills/acos_state_backup.py`, repo tooling that never packaged, documented only in `_exclude/GETTING_STARTED.md`, which also never packages. Anyone who installed these skills from the Console had neither the tool nor the instructions — the entire backup protocol was invisible to the people who most needed it. It moves to `scripts/state_backup.py` here, so it travels with the skill.

**It was also backing up the wrong copy.** The old version resolved one root from its own location and snapshotted `<repo>/skills/acos-*/state/`. But Console-synced skills install as siblings under `~/.claude/skills/synced/<id>/`, and that installed tree carries its own live `profile.json`, `config.json` and ledger. Both copies were real and had diverged — the installed profile was missing `owner.linkedin_url` and still carried `jira_workspaces.upcoming_window_days` inline. A Console re-sync can replace that folder wholesale, so the unbacked-up copy was the more exposed one. The tool now discovers every acos root it can see (its own tree, plus `~/.claude/skills/` at three depths), snapshots all of them, keeps each root's files under a hashed subdirectory so two roots holding the same relative path never collide, and restores each file to the root it came from. `--roots` previews what it found, `--root PATH` adds one, `--list-roots LABEL` shows what a snapshot holds.

Manifests move to version 2 to carry the root mapping. Snapshots written by the old script are detected and refused rather than misplaced, with instructions to copy them out by hand. `.gitkeep` is no longer snapshotted as if it were data.

Restore safety, tested end to end: it still refuses to overwrite a live file differing from the snapshot without `--force`; it reports and skips a recorded root that no longer exists rather than failing the whole restore; and redirecting a multi-root selection into one directory with `--root` is refused outright, because it would have written one root's file over another's and silently kept whichever came last. That last case was a real bug found in testing and fixed with `--from-root`.

**`SKILL.md` gained a "Backing up and restoring the profile" section** with the commands, when to take a snapshot, the two-copies explanation, and an instruction never to pass `--force` on the person's behalf. Enrollment now says explicitly what to do when a profile already exists. `lint_skills.py`'s state-tracking error text points at the new path, and the root `README.md` lists all five acos skills in its version table with a footnote pointing at the setup guide.

## 0.7 — 2026-09-24

Added `owner.pronouns` — optional, free text such as `she/her` or `they/them`. Any skill writing prose about the owner uses it and falls back to they/them when unset, rather than inferring from a name. Added to `profile.example.json`, the Schema section, the enrollment questions, and the Updating triggers ("My pronouns are ___").

## 0.6 — 2026-09-24

**Config split into shared defaults and personal profile.** New shipped `references/defaults.json` holds every value that is identical for everyone: `jira_workspaces.cloud_id` and `product_fields`, `upcoming_window_days`, `calendar_analysis.functional_area_keyword_patterns` and `functional_area_disambiguation`, `time_allocation_targets`, and the default `working_hours`. `state/profile.json` now holds only personal data — owner, staff, reports, team, VIPs, partner vendors, protected contacts, the person's own Jira project keys, their meeting series, ignored addresses, and any deliberate override. Both `profile.example.json` and the maintainer's live profile were trimmed accordingly.

Consumers load defaults, then overlay the profile: any key the profile sets wins, anything it omits falls back. Dicts merge key by key, so overriding one working-hours day keeps the rest.

**Why.** Shared values living in the profile schema meant a profile created before a value existed silently ran without it. That is not hypothetical: the Functional Area regex vocabulary moved from `acos-calendar-analysis`'s module constants into this profile in 0.4, and every profile predating that change tagged nothing — `(cal.get(...) or {})` cannot tell "absent" from "legitimately empty", so it failed with no error for weeks. `jira_workspaces.cloud_id` had the same root cause but failed loudly instead. Shipping the shared half separately makes a stale profile structurally impossible: a profile never has to carry what it can inherit.

SKILL.md gains a "Two files" section explaining the split and the override rule, and the "For skill authors" contract now covers reading both files and the vendored `load_acos_profile()` helper.

## 0.5 — 2026-09-24

Sanitization pass ahead of org-wide distribution, plus one more step in the 0.4 direction of moving site config out of sibling skills' code.

`references/profile.example.json` was shipping real identity: the `owner` block carried a real first name, full name, email and signoff, and `jira_workspaces` carried seven real project keys. Those are now placeholders (`Example Owner` / `owner@example.org`) and empty key lists — the block's `_comment` already documents the format, so nothing is lost. `cloud_id` deliberately keeps the real site: every user of these skills shares one Jira Cloud site, so it is an org fact rather than personal data, and a working default saves every colleague the same lookup.

New `jira_workspaces.product_fields` block holding the Jira Product Discovery custom-field IDs (`project_target`, `product_area`, `roadmap`) and the Roadmap values excluded from the product-detail query. These had been hardcoded in `acos-jira-analysis/scripts/jira_report.py` across nine call sites. Custom-field IDs are assigned per Jira site, so they are configuration, not constants — the same reasoning that moved the calendar regex vocabulary here in 0.4. That skill falls back to its previous values when the block is absent, so existing profiles are unaffected.

`state/profile.json` is no longer shipped in the packaged zip at all (`skills/package_skill.py` now excludes `state/` except `.gitkeep`), and `_exclude/GETTING_STARTED.md` documents the three layers that keep it out plus the new `skills/acos_state_backup.py` snapshot/restore workflow.

## 0.4 — 2026-08-16

Schema additions surfaced by a repo-wide genericization pass, centralizing config that had been drifting into per-sibling local state: `owner.linkedin_url` (a genuine identity fact, previously about to be duplicated locally in `acos-email-sort`); `staff[].is_executive_assistant`, replacing `acos-email-sort`'s fragile substring match on freeform `role` text; `jira_workspaces.cloud_id`, replacing a hardcoded Jira site default in `acos-jira-analysis`; and `calendar_analysis.functional_area_keyword_patterns` / `calendar_analysis.functional_area_disambiguation`, the full regex vocabulary migrated out of `acos-calendar-analysis`'s module constants so a different organization can retune tagging without editing that skill's code. `SKILL.md`'s Schema section documents all five additions. Also fixed one wording-pass hit (an example signoff list that used real names).

## 0.3 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. Moved two "found via testing" provenance parentheticals out of `SKILL.md` into this entry: the working-hours zero-width-weekend-override rationale (found via testing 2026-08-10) and the `ignored_addresses` room-resource/2-person-1:1 rationale (found via testing 2026-08-10/11). The operational facts themselves stay in `SKILL.md`; only the dated attribution moved.

## 0.2 — 2026-08-10

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
