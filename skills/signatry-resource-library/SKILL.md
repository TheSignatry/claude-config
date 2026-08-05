---
name: signatry-resource-library
description: The Signatry's authoritative Fact Sheets and Guides on DAF mechanics, complex asset giving, family generosity, and nonprofit vetting/fundraising. Use this whenever recommending an existing donor resource, answering a product/feature question about The Signatry, or drafting new donor-facing or nonprofit-facing content that should be grounded in these documents. Pair with signatry-facts for atomic figures and signatry-style for voice.
metadata:
  version: 1.0.0
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

1. **Search the catalog first** (`category`, `topic`, and `summary` columns) to find
   the right document(s). Filter out `status: superseded` unless the user specifically
   wants historical versions.
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

**Notification channel:** all staleness/refresh notifications from this skill go to
the **#wg_marketing** Slack channel (channel ID `C051ANTSF7W`) — never to whichever
individual happens to be running the skill. This matters especially once the skill
is promoted org-wide: the average staff member using this skill should not be pinged
with questions about catalog upkeep. Refresh mechanics are a Brand Team concern and
should surface only in #wg_marketing.

**Staleness check (run automatically on every use of this skill):**
1. Compare today's date to `last_synced` in this file's frontmatter.
2. If 30 days or fewer have passed, proceed normally — no SharePoint call.
3. If more than 30 days have passed, run the staleness check for each source type:

   **SharePoint rows:** run a single lightweight `sharepoint_search` scoped to
   `folderName: "02. Fact Sheets and Guides"` (driveId above), requesting just
   filenames and `lastModifiedDateTime` — not full content, not a re-fetch of every
   document. Diff against `catalog.csv` rows where `source_type: sharepoint_pdf`:
   - A filename not in the catalog → candidate new document.
   - A filename in the catalog whose `lastModifiedDateTime` is newer than the
     catalog's `last_modified` → candidate updated document.

   **Webpage rows:** there's no folder listing to diff against — each of the 13
   URLs must be checked individually. For each, `web_fetch` the page and compare
   its `article.modified_time` meta value (visible in the fetched frontmatter)
   against the catalog's `last_modified` for that row:
   - A newer `article.modified_time` → candidate updated page.
   - This only checks the 13 known URLs — it will not discover new pages added to
     thesignatry.com. Finding genuinely new webpages worth cataloging is a manual
     "hey, add this URL" action from the user, not something this check surfaces
     on its own.

4. For each candidate, apply the auto-edit rules below, then post one summary
   message to **#wg_marketing** describing what was auto-applied and what still
   needs a human call. Do not interrupt the user's current task with this — it's a
   background note to the channel, not a blocking question in the conversation.
5. Update `last_synced` in this file's frontmatter once the check completes,
   whether or not any changes were found.
6. If anything actually changed (new row, updated row, status change), bump
   `version` under `metadata` and add a dated entry to the Changelog below.
   A no-op check (nothing new or updated found) does not need a version bump —
   only update `last_synced` in that case.

**Versioning convention:** semantic-ish, not strict — bump the patch number
(1.0.x) for routine content refreshes (new/updated files, corrected summaries),
the minor number (1.x.0) for structural changes (new source type, new column,
new refresh mechanism), and the major number (x.0.0) only for a rebuild that
changes how the catalog is meant to be used.

**Auto-edit rules (applied without waiting for confirmation):**
- **New file with no obvious relation to an existing catalog row:** fetch full
  content, write a summary + talking points, add a row with `status: pending-review`.
  `pending-review` is a label only — the document is fully usable in drafts and
  recommendations immediately, same as `current`. It just flags in the catalog that
  a human hasn't confirmed the auto-generated summary yet.
- **Existing file with a newer `lastModifiedDateTime` but same filename:** re-fetch
  content, update that row's summary/talking points/`last_modified`. Status stays
  whatever it was (don't reset a `current` row to `pending-review` just for a minor
  content refresh).

**Flagged for human confirmation (not auto-applied):**
- **Possible supersession** — a new or renamed file appears to replace an existing
  topic (e.g., a version-bumped filename, or near-identical content to an existing
  row). Don't auto-mark either file `superseded`; add the new file as
  `pending-review` and note the suspected relationship in `related_docs`, then flag
  it explicitly in the #wg_marketing message for a human to confirm the supersession
  call.
- **Contradicted figures** — new/updated content that conflicts with a figure
  already recorded in another catalog row (e.g., a different RMD age, a different
  fee schedule). Flag in the message rather than silently overwriting either row.

This keeps routine drift (new file, updated file, nothing unusual) resolving itself,
while judgment calls (is this really a replacement, does this contradict something
else) still reach a person before being treated as settled.

This staleness/refresh cycle can run inline whenever the skill is used in a
conversation, or via a Claude Cowork scheduled task pointed at this folder for a
periodic check independent of usage.

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
