# Changelog

All notable changes to this skill are documented here, newest first.

## 0.7 — 2026-11-01

**`collect` subcommand, and oversized connector pages are now a documented, expected step.** Every Product QA run began with "Error: result (N characters) exceeds maximum allowed tokens". It is harmless: the host saves the full page to a file, which keeps it out of the conversation. But `SKILL.md` never said so, so each run had to work out the recovery and stitch the pages together with `jq` on its own.

- **Why fewer fields can't fix it.** A live 30 Oct Product QA fetch measured about 4,200 characters per TRM idea. Of that, `issuelinks` was 35% (each link embeds the linked issue's status, priority, and issue-type objects), `assignee` 22%, and `status` 10%. The report needs all three. At the connector's smallest page size of 50, a page is still about 210,000 characters, roughly twice the limit.
- **`jira_report.py collect`** takes `--page <query id>=<file>` once per page in fetch order, with an optional `--plan` and `--merge`. It accepts saved tool-result files or pages written to disk, in both page shapes (`issues.nodes` + `pageInfo`, or a flat `issues` + `isLast`/`nextPageToken`), plus the content-block wrapper some hosts save. It fails with a one-line JSON error when a plan query has no pages, an id isn't in the plan, or the last page for a query says more follow. `--merge` adds a second-stage fetch (`focus_comments`) to an existing raw file.
- **`SKILL.md`.** The main report's Fetch step now explains the oversized-page message and says to pass the saved path to `collect`, never read the file in, and never retry. The fetch steps for all four QA reports now use `collect`. The Work Boards `directory` results are still added by hand, as before.
- **Verified** against the live 30 Oct Product QA pages: the raw file from `collect` is identical to the hand-built one. 11 new tests in `tests/test_collect.py` use synthetic pages; the full suite is 128 tests, all passing.

**Archived ideas: a new Archive QA report, the standard report stops counting them, and "Merged" joins the non-active Roadmap values.** Archiving a Jira Product Discovery idea hides it but leaves its Roadmap value and status untouched. A 1 Nov live check found 27 archived TRM ideas, 17 of them still holding a non-concluding Roadmap value or an open status. Two (TRM-366 and TRM-368, both Roadmap Now with October targets) were showing as overdue in the standard report's Product detail list.

- **Standard report.** `product`, `product_detail`, and `product_delivered` now fetch `product_fields.idea_archived`, and `build_report` drops any idea where it is set. This is the same rule Product QA and the Focus dashboard already apply. A plan built without that field ID (an older acos-main round trip) filters nothing, as before.
- **Merged.** The TRM Roadmap field gained a "Merged" option (verified live 1 Nov on TRM-366 and TRM-368). acos-aboutme 0.11 adds it to `product_fields.roadmap_exclude`, `product_qa.qa_roadmap_exclude`, and `product_qa.exclude_from_qa.roadmap_values`, the last of which also drops merged ideas from the Focus dashboard. `DEFAULT_PRODUCT_FIELDS.roadmap_exclude` matches.
- **Archive QA** (`archive-qa-plan`, `archive-qa-report`, `scripts/archive_qa.py`, `assets/archive_qa_template.html`, `references/archive_qa_design.md`). It runs one query for every idea whose archived field is set, and two config-driven checks: Roadmap not in `archive_qa.concluding_roadmap` (Done, Won't do, Merged; an empty value fails), and status category not in `concluding_status_categories` (done). Parking Lot is deliberately not concluding. The page has four fixed sections (Neither concluded, Needs a Roadmap value, Needs the status closed, and a collapsed Concluded), plus the shared ledger, owner filter, and glyph QA cell, with colors from `product_qa.palette`. Rule text fills `{values}` from config, so the page can't drift from it. HTML, markdown, and JSON output are supported. The first live run on 1 Nov: 17 of 27 flagged (11 neither, 6 status only), 10 concluded.
- **Tests.** `tests/test_archive_qa.py` adds 13 tests with synthetic ideas: plan and config errors, sections, counts, rule text, owners, a disabled check, markdown, and an HTML build through the CLI, plus the standard report's archived filter and the shipped-defaults plan. `test_product_qa`'s shipped-defaults JQL assertion now includes "Merged". The suite is 141 tests, all passing.

## 0.6 — 2026-10-24

**Four config-driven QA reports, rendered as branded, interactive HTML pages.** Each one is ported from its prototype without redesign. Each has plan and report subcommands in `scripts/jira_report.py` that call a pure-function module. HTML, markdown, and JSON output are all supported. Nothing org-specific is hardcoded: checks, glyphs, colors, thresholds, rules, and copy come from `jira_workspaces.*_qa` and `jira_workspaces.focus` (acos-aboutme 0.9). Fonts embed as base64 from `signatry-brand-core`, and a missing font directory fails loudly. Comment bodies are never read; only timestamps and authors are. The existing `plan`/`report` path is unchanged.

- **Product QA** (`qa-plan`, `qa-report`, `scripts/product_qa.py`, from the 23 Oct prototype, draft 5). It reviews every idea in the `product` group against a data-quality checklist and shows a runway chart, an owner table, a headline, rewrite rules, and agenda parsing and corrections. The prototype's two judgment passes, "Needs a rewrite" and the agenda corrections, are now explicit rules. `DEFAULT_PRODUCT_FIELDS` gains six Product Discovery field IDs to match the shared defaults.
- **Support QA** (`support-qa-plan`, `support-qa-report`, `scripts/support_qa.py`, from the 24 Oct prototype, draft 2). It covers every open ticket in the `support` group, team-wide. Nine checks feed six verdict sections. The page has an aging chart, an owner table, and seven computed diagnostics that replace the prototype's hand-written findings. Comments come from a separate, comments-only query.
- **Work Boards QA** (`work-qa-plan`, `work-qa-lookups`, `work-qa-report`, `scripts/work_qa.py`, from the 24 Oct prototype, draft 2). One report covers every key in the `work` group, with a client-side board filter. A per-board vendor status map in config puts each item in one of three lanes: our move, vendor's move, or backlog. Thirteen checks feed seven verdict sections, and every per-board view is precomputed in Python. Former-employee detection uses read-only `slack_search_users` lookups, matched by a fixed rule and cached in `state/directory_cache.json`. When Slack isn't connected or the check is off, the report marks that check "not run". Eight computed diagnostics are included.
- **Personal Focus** (`focus-plan`, `focus-comments`, `focus-report`, `scripts/focus.py`, from the 24 Oct prototype, draft 1). It shows only the owner's assigned items, sorted into three lanes (your move, waiting, parked) and ranked by `jira_workspaces.focus.score`. Roadmap gaps reuse the Product checks, and the vendor lane reads `work_qa.vendors`. The owner's identity is verified against every returned item, and a mismatch stops the run with nothing rendered.

**Shared machinery.** `scripts/qa_common.py` holds the date, timezone, and whole-day helpers (days count to noon in the owner's timezone, clamped at zero). It also holds validation, the issue loader, owner aggregation, and page assembly, including a single-row ledger option. `assets/qa_base.css` holds the shared layout: `.inner` is 1360px, prose is capped at 780px, and the Summary column takes the remaining width. Design notes are generated from `references/*_design.md`.

**Tests.** 117 stdlib unittest tests run against golden fixtures and reproduce each prototype item by item:
- Product: 39 rows (6/28/5) and check counts 6/8/18/4/0/30/32/32.
- Support: 108 tickets; check counts 31/20/51/19/14/3/16/62/0; sections 33/20/22/2/31; aging buckets 27/6/13/14/11/22/15.
- Work: 495 items after 5 templates are excluded; the directory-disabled and Slack-not-connected variants; cold and warm cache.
- Focus: lanes 15/4/14, check counts 6/4/3/1/3/7/3/10, and next-moves order and scores. Also covered: weight-change reordering, identity mismatch, and the second-stage comments query.

Deliberate differences from the prototypes:
- Product: the horizon is today plus `horizon_days`, which gives 22 Nov for a 23 Oct run (the prototype used 23 Nov). `no_outcome_cue` also flags six ideas the prototype did not list.
- Work: day counts clamp at zero, so TT-1404 now stays on the chart. "Ours" 0–30 reads 25, not 24.
- Focus: TT-1442 ranks above TT-1444 on the key tie-break, and parked items score 0.
- Focus: range dates wrap in the Date column, and timeline labels get a halo so the today line passes behind them.

**Tests are repo-only, and their data is pseudonymized.**
- `tests/` no longer ships. `package_skill.py` now excludes it, which drops about 1.6 MB from the zip. `SKILL.md` no longer tells the runtime how to run the tests; the command is in each test file's docstring.
- The fixtures, the `_exclude/*_data.json` prototypes, and the data quoted in test source were rewritten with `skills/pseudonymize_fixtures.py`. That covers 40 name tokens and 1,372 words, including security-posture ticket text and new-hire names.
- The goldens were regenerated from the rewritten inputs and proved equivalent to the originals: every number, flag, ordering, and list length is unchanged, and only names and wording differ.
- No Restricted data was involved. The raw originals are backed up outside the repo.
- Real-data examples in shipped files were replaced with synthetic ones. These were the `SKILL.md` garbled-phrase example and the docstrings in `product_qa.clean_label` and `work_qa.resolve_match`.

A headless Chrome pass covered all four pages, light and dark, at 390, 1280, and 1920px, plus print. It found no console errors, missing glyphs, overflow, or overlapping chart text. Every filter combination's banner count matched its rows, and clicking a dot in a collapsed section opened that section and flashed the row.

## 0.5 — 2026-09-24

Reads acos-aboutme's shared `references/defaults.json` underneath the personal profile via the vendored `load_acos_profile()` helper, so `cloud_id` and the Product Discovery `product_fields` now arrive from the org-wide defaults instead of having to be present in every profile. A profile that sets either still wins. This fixes a live failure: the maintainer's profile predated `cloud_id` entering the schema, so `plan` hard-failed and took `acos-main`'s morning-plan and month-retro with it.

`DEFAULT_PRODUCT_FIELDS` stays as a last-resort fallback for an install whose acos-aboutme is older than the defaults file.

## 0.4 — 2026-09-24

The three Jira Product Discovery custom-field IDs — `customfield_10149` (Project target), `customfield_10156` (Product Area), `customfield_10139` (Roadmap) — and the Roadmap values excluded from the product-detail JQL were hardcoded across nine call sites in `scripts/jira_report.py`. Custom-field IDs are assigned per Jira site, so a differently-configured site would have returned empty fields with no error rather than failing loudly.

They now come from the profile's `jira_workspaces.product_fields` block, resolved once in `build_plan` by the new `resolve_product_fields()` and carried through the returned plan so `build_report` reads the same IDs the queries asked for. The merge is per key, so a profile that overrides only one ID still gets working defaults for the rest, and `DEFAULT_PRODUCT_FIELDS` keeps the previous values as the fallback — a profile without the block produces byte-identical JQL to 0.3. Continues the 0.4 `acos-aboutme` pattern of moving site configuration out of sibling skills' module constants.

## 0.3 — 2026-08-16

Removed the hardcoded `DEFAULT_CLOUD_ID = "signatry1.atlassian.net"` fallback from `scripts/jira_report.py` — `build_plan()` now reads `jira_workspaces.cloud_id` from the `acos-aboutme` profile and fails fast with a clear one-line JSON error if it's missing, matching the existing pattern for missing project keys, rather than silently defaulting to this organization's own site. `--cloud-id` remains available as an explicit CLI override for testing/multi-site cases. Completed the `SKILL.md` wording pass (frontmatter description plus 2 body mentions), replacing "Trevor" with "the owner" so a different adopter isn't misdirected to enroll a specific named person.

## 0.2 — 2026-08-15

Created `_exclude/` per the repo-wide skill-structure standard. Moved four pure-date provenance parentheticals out of `SKILL.md` into this entry: the `--since`/`--until` month-retro flags addition (2026-08-13), the `cloudId`-works-directly-on-this-site confirmation (2026-08-10), the Roadmap-column addition (2026-08-14), and the `PRODUCT_DELIVERED_LOOKBACK_DAYS` 180-day fetch-volume-guard addition (2026-08-15). One borderline date — the `duedate`-population confirmation on `TT`/`IL`/`HSER`/`GE`/`DVR` — was left in `SKILL.md` since it may function as a re-verification caveat rather than pure provenance.

## 0.1 — 2026-08-10

Initial tracked release under the repo-wide CHANGELOG.md standard. No changelog was kept prior to this entry.
