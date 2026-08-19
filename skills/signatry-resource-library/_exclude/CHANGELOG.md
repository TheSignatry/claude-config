# Changelog

All notable changes to this skill are documented here, newest first.

## 1.0.1 — 2026-08-06

Token-efficiency pass — no factual changes. Moved the full staleness-check
procedure, auto-edit rules, and versioning convention out of this file into
`reference/maintenance.md`, and added `scripts/find_resources.py` so a lookup
searches the catalog without reading `catalog.csv` (40KB, 45 rows) into context.
Previously, "run automatically on every use of this skill" meant every ordinary
donor-question lookup carried the risk of a SharePoint call, 13 webpage fetches,
and a Slack post if the 30-day staleness window had lapsed — a real, non-trivial
cost this skill's own text already suggested moving to a scheduled task (see prior
"can run inline... or via a Claude Cowork scheduled task" note) without making that
the default. It is now the only supported path; nothing about the maintenance
logic itself changed. See `reference/maintenance.md`'s own history for anything
that changes there going forward.

## 1.0.0 — 2026-08-03

Initial build. Cataloged all 32 documents in the SharePoint "02. Fact Sheets and
Guides" folder (Fact Sheets + Guides subfolders, plus one root-level file) and all
13 thesignatry.com webpages covering DAF fundamentals, asset giving, BRI/alternative
investments, advisor-managed accounts, and the generosity calculator. Marked 2
documents `superseded` (Family Pathways_0226.pdf → digital_202604; The Signatry
Charity Fund.pdf → Charity-Fund_How-It-Works_202411) and 2 `needs-review`
(Designated Funds_TheSignatry.pdf — outdated QCD age; Who-We-Serve_2024.pdf — 2023
stats). Established the >30-day staleness check, auto-edit rules for routine drift,
human-confirmation flagging for supersession/contradicted-figure cases, and
#wg_marketing as the sole notification channel.
