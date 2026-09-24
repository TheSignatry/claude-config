# Changelog

All notable changes to this skill are documented here, newest first.

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
