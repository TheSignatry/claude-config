# Resource Library — Staleness Check and Maintenance

Load this file only when setting up, running, or troubleshooting the catalog's
refresh cycle — not when answering a donor question or drafting content. Ordinary
use of `signatry-resource-library` (searching, citing, recommending a document)
never needs this file.

**Where this runs.** This procedure is meant to run as a **Claude Cowork scheduled
task** pointed at this skill, independent of any conversation. It can also be run
inline if a person explicitly asks to check for updates, but nothing in ordinary
use of this skill triggers it automatically.

## Staleness check

1. Compare today's date to `last_synced` in `SKILL.md`'s frontmatter.
2. If 30 days or fewer have passed, nothing to do.
3. If more than 30 days have passed, run the check for each source type:

   **SharePoint rows:** run a single lightweight `sharepoint_search` scoped to
   `folderName: "02. Fact Sheets and Guides"` (`driveId` in `SKILL.md`'s
   frontmatter), requesting just filenames and `lastModifiedDateTime` — not full
   content, not a re-fetch of every document. Diff against `catalog.csv` rows
   where `source_type: sharepoint_pdf`:
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
   needs a human call. Do not interrupt anyone's task with this — it's a
   background note to the channel, not a blocking question in a conversation.
5. Update `last_synced` in `SKILL.md`'s frontmatter once the check completes,
   whether or not any changes were found.
6. If anything actually changed (new row, updated row, status change), bump
   `version` under `SKILL.md`'s `metadata` and add a dated entry to that file's
   Changelog. A no-op check (nothing new or updated found) does not need a
   version bump — only update `last_synced` in that case.

**Versioning convention:** semantic-ish, not strict — bump the patch number
(1.0.x) for routine content refreshes (new/updated files, corrected summaries),
the minor number (1.x.0) for structural changes (new source type, new column,
new refresh mechanism), and the major number (x.0.0) only for a rebuild that
changes how the catalog is meant to be used.

## Auto-edit rules (applied without waiting for confirmation)

- **New file with no obvious relation to an existing catalog row:** fetch full
  content, write a summary + talking points, add a row with `status: pending-review`.
  `pending-review` is a label only — the document is fully usable in drafts and
  recommendations immediately, same as `current`. It just flags in the catalog that
  a human hasn't confirmed the auto-generated summary yet.
- **Existing file with a newer `lastModifiedDateTime` but same filename:** re-fetch
  content, update that row's summary/talking points/`last_modified`. Status stays
  whatever it was (don't reset a `current` row to `pending-review` just for a minor
  content refresh).

## Flagged for human confirmation (not auto-applied)

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

## History

**2026-08-06** — Extracted from `SKILL.md` (was previously mandated to "run
automatically on every use of this skill," meaning any ordinary lookup could
trigger a SharePoint call, 13 webpage fetches, and a Slack post if the 30-day
window had lapsed). Moved here and repointed to run only as a scheduled task, per
a token-efficiency audit. No change to the logic itself — same staleness window,
same auto-edit/human-confirmation split, same notification channel.
