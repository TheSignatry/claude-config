# Changelog

All notable changes to this skill are documented here, newest first.

## 0.4 — 2026-08-16

Schema additions surfaced by a repo-wide genericization pass, centralizing config that had been drifting into per-sibling local state: `owner.linkedin_url` (a genuine identity fact, previously about to be duplicated locally in `acos-email-sort`); `staff[].is_executive_assistant`, replacing `acos-email-sort`'s fragile substring match on freeform `role` text; `jira_workspaces.cloud_id`, replacing a hardcoded Jira site default in `acos-jira-analysis`; and `calendar_analysis.functional_area_keyword_patterns` / `calendar_analysis.functional_area_disambiguation`, the full regex vocabulary migrated out of `acos-calendar-analysis`'s module constants so a different organization can retune tagging without editing that skill's code. `SKILL.md`'s Schema section documents all five additions. Also fixed one wording-pass hit (an example signoff list that used real names).

## 0.3 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. Moved two "found via testing" provenance parentheticals out of `SKILL.md` into this entry: the working-hours zero-width-weekend-override rationale (found via testing 2026-08-10) and the `ignored_addresses` room-resource/2-person-1:1 rationale (found via testing 2026-08-10/11). The operational facts themselves stay in `SKILL.md`; only the dated attribution moved.

## 0.2 — 2026-08-10

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
