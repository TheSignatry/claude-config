# darmstrong run report

Source: [TT-1359 comment 68341](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68341)
Posted by Trevor Bunch, 2026-09-21.

---

Written for: Dale Armstrong as the reviewing relationship manager, with you as the operator.

The darmstrong run is complete. Outputs are in `~/Downloads/darmstrong_333_contact_research/`: the enrichment workbook, 333 PDF profiles named `Dale_Armstrong_<Last>_<First>_<ID>_profile.pdf`, and the run state plus ledger so anything can be re-rendered without new research. The William Allen PDF was rendered to an image and checked: Signatry header, confidence badges, owner badge, and Fable model footer all correct.

**Processing time and tokens by stage**

| Stage | Wall time | Model tokens | Notes |
| --- | --- | --- | --- |
| Init | under 1 s | 0 | 333 rows in, 333 accepted, 0 rejected |
| HubSpot pull | 11m 15s | 0 | 4 parallel workers, about 2 s per contact |
| Research | 1h 24m | 8,463,135 (measured) | 67 Fable subagents, 3,214 tool calls, 1,323 searches, 823 fetches |
| Render | 18 s | 0 | workbook plus 333 PDFs |
| Overall | 1h 39m | | |

Research tokens are the harness-measured totals for the 67 subagents (mean about 126k per group of 5, range 95k to 161k). My own orchestration context is not measured by the harness and is not included. All 333 contacts were researched by claude-fable-5-1, on policy for the standard tier.

Compared with the pboone run, this one used about 20 percent fewer tokens per contact and ran faster per contact, mostly because the HubSpot pull used four workers and the queue never drained below ten concurrent agents.

**Results**

| Score | High | Moderate | Low | None |
| --- | --- | --- | --- | --- |
| Contact identification | 297 | 9 | 15 | 12 |
| Household | 204 | 20 | 16 | 93 |

157 companies were researched and shared across contacts. 122 records carry a likely-duplicate flag, and 3 are flagged as Signatry staff or former staff.

**IT15 handling, please read.** HubSpot engagement text on 187 of these contacts was redacted as possibly Restricted before any research began: portal credentials, fund identifiers, partial account numbers, wire and bank references, and health or hardship notes. Subagents also reported three items my sweep missed, which I redacted afterwards without reading them: a health detail in a Scott Shane note, a wire-instruction email on Shawn Boskie, and one field each on two other records. Please report the credential, account, and wire sightings to the Technology Team under IT14 Policy 10. Dollar amounts in notes were masked for gift-amount confidentiality.

**Things I handled along the way**

- Under the minimum-data rule I removed six items subagents had recorded from public sources: regulatory disclosure and probe mentions (Keith Phillips, Curt Cronin), unfetched litigation mentions (Erik Weir, Layne Sapp), a personal net-worth figure (Tim Dunn), and inheritance wording (Terry Leprino). Each edit is logged in that contact's state file.
- Two subagent reports were flagged by the auto-mode classifier. I verified all ten records directly: correct model, sourced, no forced merges.
- The HubSpot user record stores the owner as lowercase "dale armstrong", which would have produced lowercase filenames. I normalized it to "Dale Armstrong" in state and noted that in the manifest.

**Reviewer items worth attention first**

- Two contacts are deceased per public sources but not marked in HubSpot: Robert Woodson (May 2026, still Grant Advisor on four funds) and Tom Cousins (July 2025).
- The second Hilgardt Lamprecht record appears to be Janice Lamprecht's record misnamed. Natalie Scott's Spouse label to Caleb Scott appears mis-linked to a different Natalie Scott.
- Several household pairs derived from import timing are not spouses (parent, son, sibling, or unrelated); the fragments say so, and no Spouse associations should be created from them.
- Two fund-closure signals (Londal, Waller) and one advisor-not-donor record (Andrew Fowler) are flagged for status review.

**Skill issues to fix**, same as last run: the validator rejects any URL with a 13 to 19 digit run (SEC accession numbers, BBB, Facebook, Business Wire IDs) and cost roughly 25 re-merges; `pack_contact.py` was denied by the classifier for about a third of subagents; a `manifest.json.tmp` race hit parallel HubSpot workers once and a parallel merge once; and the derive step's "no association recorded" household flag is stale whenever a Spouse label exists.

Nothing has been written back to HubSpot. Review starts with the `Accept?` column on the two Upload Prep sheets.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
