# Changelog

All notable changes to this skill are documented here, newest first.

## 0.8 — 2026-10-30

**Meetings with other departments are classified by rule instead of falling to 5c.** When acos-aboutme's new `owner.functional_areas` is set, an internal meeting that no earlier rule claimed and that includes someone tagged with a functional area outside the owner's own becomes Operating rhythm if it is an occurrence of a recurring series and Stakeholder partnership if it is a one-off, per the owner's direction that regular cross-department meetings run the business and one-off ones are stakeholder engagement. It runs before the two-or-more-areas rule, so it only changes events that rule would have sent to 5c, and it is off while `owner.functional_areas` is empty.

Prompted by a 5c misjudgment: "SUP-930 Discussion" (a one-off with two Finance staff) was resolved as Operating rhythm because the ticket key in the subject outweighed the attendees. The 5c step in SKILL.md now says to weigh attendees over the subject line.

Recurrence comes from the Exchange item id, because the O365 connector returns `recurrence: null` for every event. `_series_occurrence` decodes the id header: 0x0009 then 0x01 is an occurrence, 0x00 a single item, anything else unknown, which leaves the event for 5c. The format is undocumented. Across 189 real events (October 5 – November 8, 2026) it returned 137 occurrences, 52 single items, and 0 unknown, and every meeting seen more than once read as an occurrence. One exception to watch: "Care-Tech Sync Meeting 2026Q4" is named like a series but is a single item, so it reads as one-off.

Measured against those weeks with the rule off and on: October 5 – November 1 (150 events) went from 3 events in 5c to 1, and two changed category ("Trevor Calls Alan", Revenue, and "Lakeside Close Out Internal Meeting", Operations, both one-off Stakeholder partnership). November 2–8 (39 events) went from 2 to 1, with SUP-930 now classified by rule. No event already classified by a rule changed category; conflicts, schedule health, and prep flags were identical.

**5c gets names.** `_describe_participant` read names and roles only from the 13-person legacy `staff` list, so most 5c attendees arrived as bare addresses. It now falls back to names in `reports`, `team`, and `functional_areas` (role stays null). `staff` still wins when present.

**First test suite** (`tests/test_classification.py`, synthetic data, 13 tests): the id decoder including unknown shapes, the rule firing and not firing (own areas only, setting empty, unknown id), the name fallback, and 0.7's intentional overlaps.

## 0.7 — 2026-10-30

Overlaps the owner has declared deliberate are no longer reported as double-bookings. `detect_conflicts` reads acos-aboutme's new `calendar_analysis.intentional_overlaps`: when two overlapping meetings both match one entry's patterns, the pair moves from `conflicts.double_bookings` to a new `conflicts.intentional_overlaps` list, so the suppression stays visible in the JSON instead of disappearing. Tight transitions are unaffected. Because morning-plan's conflicts and week-plan's `double_bookings` both come from this field, neither report flags the pair any more.

Prompted by the Dev Team and Run Team Retrospectives, booked over each other every Friday on purpose; the owner alternates between them. Checked against the real week of 2 November 2026 (39 events): double-bookings went from 2 to 1 (the retrospectives moved to `intentional_overlaps`, 60 minutes), the Tuesday 7:00 sprint review and Dr. B overlap is still flagged, and every other report field is byte-identical. An event matching only one side, or a profile with no entries, behaves as before.

SKILL.md lists the new field under Config and explains under Corrections that a deliberate overlap is recorded through acos-aboutme, not `correct`.

## 0.6 — 2026-10-07

A known-series match now outranks the Focused production and People leadership rules, so a series entry for a recurring solo block (no attendees) takes effect. It still comes after Capacity unavailable, so a PTO or travel block is never overridden by a subject pattern.

This fixes an inert correction. A solo block has no real attendees, and Focused production's generic "no real attendees" rule claimed it before the series table was ever consulted. Entries added through `correct` for "Strategy - Protected", "Strategy and Planning - Protected", and "TRM Grooming and Release Slate" were written correctly but could never match. Checked against a real week (34 events): exactly those four events moved, from Focused production to Strategy and transformation. Nothing else changed category, and no event became unresolved.

Recurring solo blocks registered as a known series (no real attendees, e.g. "Strategy - Protected") keep their series category for time allocation but are still treated as the owner's protected time. They stay out of tight-transition, double-booking, and needs-prep checks, and they count as deep-work blocks, so a meeting overlapping one is reported as a deep-work infringement. `find_protected_block_ids` identifies them. Without it the reorder made these blocks read as meetings: tight transitions went from 5 to 9, needs-prep from 21 to 24, and the deep-work block count fell from 7 to 3 on the same real week. With it, all three match the pre-change figures. A synthetic meeting placed inside a Strategy - Protected block is reported as an infringement.

Not changed: Work Mode for these blocks reads Meeting or Planning instead of Execution.

## 0.5 — 2026-09-24

`plan` reads acos-aboutme's shared `references/defaults.json` underneath the personal profile via the vendored `load_acos_profile()` helper. The Functional Area tagging vocabulary and the time-allocation benchmark tables now arrive from the org-wide defaults rather than needing to be present in every profile.

This fixes a silent failure. Those regexes moved out of this skill's module constants and into the profile schema in 0.4; any profile created before that change compiled zero tagging rules, and because `functional_area_rules` is built from `(cal.get(...) or {})`, an absent key and an empty one are indistinguishable — every Functional Area tag came back blank with no error. Confirmed against the maintainer's profile: 0 rules where 10 were expected.

`correct` deliberately does **not** use the merged view. `save_known_series_atomic` splices against the exact bytes it re-reads, so handing it a defaults-merged dict would risk rewriting the file from the merged shape.

## 0.4 — 2026-08-30

Added `FLIGHT_NUMBER_PATTERN` to `_is_capacity_unavailable`'s solo-block checks: a subject naming a flight and its flight number (e.g. "Delta Air Lines flight 4065 to Detroit") now resolves to Capacity unavailable, the same as the pre-existing `AIRPORT_CODE_PAIR_PATTERN` already did for IATA-shorthand phrasing ("DL30001: BNA to ATL"). Found via live use: two flights in the same real week, phrased each way, landed in different categories (one Capacity unavailable, one Focused production's generic "no real attendees" branch) purely from subject wording, not any real difference between the trips. Same session also corrected `acos-aboutme`'s shared `known_meeting_series` STRATOP entry via this skill's own `correct` subcommand (a data fix, not a code change) — its only pattern, `"stratop"`, missed the two-word "Strat Op Day 1/2"/"Strat Op Team Dinner" phrasing a real annual StratOp Renewal offsite used, so those events fell through to External ecosystem instead of Strategy and transformation; added `"strat op"` as a second pattern.

## 0.3 — 2026-08-16

Migrated `FUNCTIONAL_AREA_KEYWORD_RULES` and its four auxiliary disambiguation patterns (`AI_DATA_GOVERNANCE_PATTERN`, `LEGAL_NON_GOVERNANCE_PATTERN`, `REVENUE_NON_PIPELINE_PATTERN`, `BARE_PIPELINE_PATTERN`) out of `scripts/calendar_report.py`'s module constants into `acos-aboutme`'s shared profile (`calendar_analysis.functional_area_keyword_patterns` / `.functional_area_disambiguation`) — the Legal/Revenue/Systems special-case branch *structure* stays fixed code, but the regex vocabulary itself is now config a different organization can retune without touching the script. Verified behaviorally equivalent before/after against four representative synthetic cases (Legal-governance, Legal-with-AI-governance-exclusion, Revenue-bare-pipeline, Systems-partner-domain) — all four matched identically pre- and post-migration. Also genericized real-staff-name docstring examples (`compute_functional_area_tags`'s worked example, the zero-attendee-solo-keyword rationale's meeting example, the Google-Calendar-sync-artifact example subject) and completed a full `SKILL.md` wording pass (frontmatter description plus 6 body mentions) replacing "Trevor" with "the owner" throughout, so the skill reads correctly for any adopter, not just this organization.

## 0.2 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. No dated provenance parentheticals were found in `SKILL.md` to consolidate — this skill's `SKILL.md` explicitly defers empirical/build-history detail to `scripts/calendar_report.py`'s own module docstring rather than restating it, so nothing moved here.

## 0.1 — 2026-08-11

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
