# Changelog

All notable changes to this skill are documented here, newest first.

## 0.4 — 2026-09-24

`CATEGORY_COLORS` is documented as deriving from `signatry-brand-core/reference/tints.md`, the authoritative palette. All eight values are canonical: seven base hexes plus Midnight at 40% for "Capacity unavailable".

It stays a literal map rather than a runtime read of that skill, because this script has to render a chart without requiring `signatry-brand-core` to be installed beside it. The cost of a literal is silent drift if a brand color ever changes, so `lint_skills.py`'s new `check_acos_brand_colors` verifies at lint time — which gates packaging — that every hex still exists in `signatry-brand-core`. Confirmed it fails on a non-brand value and passes on the current eight.

## 0.3 — 2026-08-16

Completed the `SKILL.md` wording pass (3 body mentions), replacing "Trevor" with "the owner" so the orchestration steps read correctly for any adopter. The week-plan headline-authoring instruction ("address Trevor by name") was rewritten to point explicitly at `acos-aboutme`'s `owner.first_name` field rather than a name baked into the instruction text.

## 0.2 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. Moved one provenance date out of `SKILL.md` into this entry: the week-plan day-chart's design note that an earlier proportional-segmented-bar version was replaced (2026-08-15) after it was found to silently double-count overlapping time. The design rationale itself stays in `SKILL.md`; only the bare date moved.

## 0.1 — 2026-08-13

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
