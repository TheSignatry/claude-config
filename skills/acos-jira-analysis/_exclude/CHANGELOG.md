# Changelog

All notable changes to this skill are documented here, newest first.

## 0.3 — 2026-08-16

Removed the hardcoded `DEFAULT_CLOUD_ID = "signatry1.atlassian.net"` fallback from `scripts/jira_report.py` — `build_plan()` now reads `jira_workspaces.cloud_id` from the `acos-aboutme` profile and fails fast with a clear one-line JSON error if it's missing, matching the existing pattern for missing project keys, rather than silently defaulting to this organization's own site. `--cloud-id` remains available as an explicit CLI override for testing/multi-site cases. Completed the `SKILL.md` wording pass (frontmatter description plus 2 body mentions), replacing "Trevor" with "the owner" so a different adopter isn't misdirected to enroll a specific named person.

## 0.2 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. Moved four pure-date provenance parentheticals out of `SKILL.md` into this entry: the `--since`/`--until` month-retro flags addition (2026-08-13), the `cloudId`-works-directly-on-this-site confirmation (2026-08-10), the Roadmap-column addition (2026-08-14), and the `PRODUCT_DELIVERED_LOOKBACK_DAYS` 180-day fetch-volume-guard addition (2026-08-15). One borderline date — the `duedate`-population confirmation on `TT`/`IL`/`HSER`/`GE`/`DVR` — was left in `SKILL.md` since it may function as a re-verification caveat rather than pure provenance.

## 0.1 — 2026-08-10

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
