# Changelog

All notable changes to this skill are documented here, newest first.

## 0.4 — 2026-08-30

Added `FLIGHT_NUMBER_PATTERN` to `_is_capacity_unavailable`'s solo-block checks: a subject naming a flight and its flight number (e.g. "Delta Air Lines flight 4065 to Detroit") now resolves to Capacity unavailable, the same as the pre-existing `AIRPORT_CODE_PAIR_PATTERN` already did for IATA-shorthand phrasing ("DL30001: BNA to ATL"). Found via live use: two flights in the same real week, phrased each way, landed in different categories (one Capacity unavailable, one Focused production's generic "no real attendees" branch) purely from subject wording, not any real difference between the trips. Same session also corrected `acos-aboutme`'s shared `known_meeting_series` STRATOP entry via this skill's own `correct` subcommand (a data fix, not a code change) — its only pattern, `"stratop"`, missed the two-word "Strat Op Day 1/2"/"Strat Op Team Dinner" phrasing a real annual StratOp Renewal offsite used, so those events fell through to External ecosystem instead of Strategy and transformation; added `"strat op"` as a second pattern.

## 0.3 — 2026-08-16

Migrated `FUNCTIONAL_AREA_KEYWORD_RULES` and its four auxiliary disambiguation patterns (`AI_DATA_GOVERNANCE_PATTERN`, `LEGAL_NON_GOVERNANCE_PATTERN`, `REVENUE_NON_PIPELINE_PATTERN`, `BARE_PIPELINE_PATTERN`) out of `scripts/calendar_report.py`'s module constants into `acos-aboutme`'s shared profile (`calendar_analysis.functional_area_keyword_patterns` / `.functional_area_disambiguation`) — the Legal/Revenue/Systems special-case branch *structure* stays fixed code, but the regex vocabulary itself is now config a different organization can retune without touching the script. Verified behaviorally equivalent before/after against four representative synthetic cases (Legal-governance, Legal-with-AI-governance-exclusion, Revenue-bare-pipeline, Systems-partner-domain) — all four matched identically pre- and post-migration. Also genericized real-staff-name docstring examples (`compute_functional_area_tags`'s worked example, the zero-attendee-solo-keyword rationale's meeting example, the Google-Calendar-sync-artifact example subject) and completed a full `SKILL.md` wording pass (frontmatter description plus 6 body mentions) replacing "Trevor" with "the owner" throughout, so the skill reads correctly for any adopter, not just this organization.

## 0.2 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. No dated provenance parentheticals were found in `SKILL.md` to consolidate — this skill's `SKILL.md` explicitly defers empirical/build-history detail to `scripts/calendar_report.py`'s own module docstring rather than restating it, so nothing moved here.

## 0.1 — 2026-08-11

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
