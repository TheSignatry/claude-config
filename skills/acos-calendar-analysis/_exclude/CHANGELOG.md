# Changelog

All notable changes to this skill are documented here, newest first.

## 0.3 — 2026-08-16

Migrated `FUNCTIONAL_AREA_KEYWORD_RULES` and its four auxiliary disambiguation patterns (`AI_DATA_GOVERNANCE_PATTERN`, `LEGAL_NON_GOVERNANCE_PATTERN`, `REVENUE_NON_PIPELINE_PATTERN`, `BARE_PIPELINE_PATTERN`) out of `scripts/calendar_report.py`'s module constants into `acos-aboutme`'s shared profile (`calendar_analysis.functional_area_keyword_patterns` / `.functional_area_disambiguation`) — the Legal/Revenue/Systems special-case branch *structure* stays fixed code, but the regex vocabulary itself is now config a different organization can retune without touching the script. Verified behaviorally equivalent before/after against four representative synthetic cases (Legal-governance, Legal-with-AI-governance-exclusion, Revenue-bare-pipeline, Systems-partner-domain) — all four matched identically pre- and post-migration. Also genericized real-staff-name docstring examples (`compute_functional_area_tags`'s worked example, the zero-attendee-solo-keyword rationale's meeting example, the Google-Calendar-sync-artifact example subject) and completed a full `SKILL.md` wording pass (frontmatter description plus 6 body mentions) replacing "Trevor" with "the owner" throughout, so the skill reads correctly for any adopter, not just this organization.

## 0.2 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. No dated provenance parentheticals were found in `SKILL.md` to consolidate — this skill's `SKILL.md` explicitly defers empirical/build-history detail to `scripts/calendar_report.py`'s own module docstring rather than restating it, so nothing moved here.

## 0.1 — 2026-08-11

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
