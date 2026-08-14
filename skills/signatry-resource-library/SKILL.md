---
name: signatry-resource-library
description: The Signatry's authoritative Fact Sheets and Guides on DAF mechanics, complex asset giving, family generosity, and nonprofit vetting/fundraising. Use this whenever recommending an existing donor resource, answering a product/feature question about The Signatry, or drafting new donor-facing or nonprofit-facing content that should be grounded in these documents. Pair with signatry-facts for atomic figures and signatry-style for voice.
metadata:
  version: 1.0.1
  last_synced: 2026-08-03
  source_folder: "AllTeam SharePoint > Shared Documents > Department-Shared > Brand & Marketing > 02. Fact Sheets and Guides"
  driveId: "b!So80IAsvh0eUdTDmtQzFGmdeT92dGu9Mu9V8IjhA8t4EDgW1hU37QLxlKISLVR2I"
---

# Signatry Resource Library

## What this is

A catalog of two source types:
- **32 SharePoint documents** from The Signatry's "02. Fact Sheets and Guides" folder
  (`source_type: sharepoint_pdf`) — the authoritative source for product/feature
  content (DAFs, complex asset giving, charity funds, alternative investments) and
  softer donor-audience guidance (family giving plans, values discussions, cause
  discovery, nonprofit vetting).
- **13 public webpages** from thesignatry.com (`source_type: webpage`) covering the
  same core DAF/asset-giving topics plus cryptocurrency giving, which has no
  SharePoint counterpart at all.

`catalog.csv` holds one row per document: category, topic, status, version/date,
a summary, key talking points, related documents, and a fetch reference — driveId +
itemId + webUrl for SharePoint rows, just webUrl for webpage rows.

**The catalog does not cache full document text.** It's metadata + summary only,
by design — see "How to use it" below for live-fetch guidance.

**Known cross-source discrepancies to watch for** (see the `talking_points` column
on the relevant rows for detail): the live "Other Ways to Give" webpage correctly
states QCD eligibility at age 70½, while the SharePoint "Designated Funds" fact
sheet says 72 — this is what triggered that file's `needs-review` status. The
"Alternative Investments" webpage and its SharePoint counterpart route donor
recommendations through slightly different contact channels. When webpage and
SharePoint content on the same topic disagree, treat the live webpage as more
likely current, but flag the conflict rather than silently picking one.

## When to use this skill

- The user asks a question that one of these documents directly answers (DAF vs.
  private foundation, how to gift business interest before a sale, IRA/QCD rules,
  how a charity fund works, etc.)
- Recommending a resource to send a donor, advisor, or nonprofit partner
- Drafting new external content on any topic these documents cover — ground framing,
  figures, and talking points in the actual source rather than paraphrasing from
  general knowledge
- Checking whether a draft's claims align with (or contradict) an existing
  authoritative resource

## How to use it

1. **Search with `scripts/find_resources.py` first** — don't read `catalog.csv`
   directly into context. The script filters by keyword, `category`, `topic`, or
   `status` and prints only the matching rows:
   ```
   python3 scripts/find_resources.py -k "business interest"
   python3 scripts/find_resources.py --topic "Designated Funds"
   python3 scripts/find_resources.py --category Guide
   python3 scripts/find_resources.py --list          # browse all 45 by topic
   ```
   `status: superseded` rows are included by default — pass `--status current` to
   drop them, unless the user specifically wants historical versions.
2. **Check `status`** before relying on a document:
   - `current` — safe to cite or draw from
   - `superseded` — a newer version exists; use the file named in `related_docs`
     instead, don't cite the superseded one
   - `needs-review` — usable for tone/structure, but flag any *figures or eligibility
     rules* to the user before reuse (see "Documents flagged for review" below)
3. **Fetch live content when it matters.** The catalog's summary and talking points
   are enough for routing and casual reference. But if the task is:
   - Quoting or closely paraphrasing the document
   - Pulling a specific number, worked example, or eligibility rule
   - Drafting new content meant to closely track the source's framing

   ...fetch the current content rather than relying on the cached summary:
   - **`source_type: sharepoint_pdf`** — use `read_resource` with
     `file:///{driveId}/{itemId}` (values from the catalog row).
   - **`source_type: webpage`** — use `web_fetch` with the row's `webUrl`.

   This keeps figures accurate even if the source changed since last sync, and
   avoids the upkeep burden of a full-text cache going stale.
4. **Cross-reference `related_docs`** — several documents share content or overlap
   in scope (e.g., the standalone Business Sale, Publicly Traded Securities, and Real
   Estate fact sheets also appear verbatim inside the Ministry Complex Asset Guide's
   appendix). If revising one, check whether its counterpart needs the same edit.

## Documents flagged for review

Two documents carry a `needs-review` status because they contain figures or rules
that may have changed since publication — flag these to the user rather than citing
the numbers directly:

- **Designated Funds_TheSignatry.pdf** — cites QCD eligibility age as 72 (original
  SECURE Act). SECURE 2.0 has since raised the RMD age; verify current age with
  compliance/signatry-facts before reuse.
- **Who-We-Serve_The-Signatry_2024.pdf** — donor/grant statistics are dated to 2023
  performance. Check against signatry-facts or the current annual report before
  citing externally.

## Dependencies

- **signatry-facts** — use for atomic figures (phone numbers, entity names, current
  statistics) referenced inside these documents, especially where a document's own
  figures are flagged `needs-review` above.
- **signatry-content-guardrails** — the "How to Choose a Nonprofit" guide includes a
  named donor quote (David Trogden). Check standing donor clearance before reusing
  it externally.
- **signatry-style** — apply house voice/terminology when drafting new content
  informed by these documents; the source PDFs themselves predate some current
  style rules (e.g., older files may not follow current Scripture citation format).

## Keeping this current

The SharePoint folder is updated periodically by the Brand Team; the website pages
are updated independently by whoever maintains thesignatry.com. Contains 45 total
entries (32 SharePoint, 13 webpage) as of `last_synced` above.

**The staleness/refresh check is not part of ordinary use of this skill.** Looking
up a fact sheet, recommending a resource, or drafting content from these documents
never triggers a SharePoint call, a round of webpage fetches, or a Slack post —
only reads `catalog.csv` (via the search script) and, where "How to use it" step 3
applies, the live document itself. The full staleness-check procedure — what it
does, when it should run, and the auto-edit/human-confirmation rules — is in
`reference/maintenance.md`, and is meant to run **as a scheduled task**, decoupled
from any conversation that happens to use this skill. Load that file only when
setting up, running, or troubleshooting that maintenance cycle — not when answering
a donor question.

**Notification channel:** all staleness/refresh notifications go to the
**#wg_marketing** Slack channel (channel ID `C051ANTSF7W`), never to whoever
happens to be running a scheduled maintenance task. Refresh mechanics are a Brand
Team concern, not something the average staff member using this skill should see.

## Changelog

**1.0.0 — 2026-08-03**
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

**1.0.1 — 2026-08-06**
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
