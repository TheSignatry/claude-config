# sfrench run report

Source: [TT-1359 comment 68374](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68374)
Posted by Trevor Bunch, 2026-09-21.

---

Written for: Steve French as the reviewing relationship manager, with you as the operator.

The sfrench run is complete. Outputs are in `~/Downloads/sfrench_246_contact_research/`: the enrichment workbook, 245 PDF profiles named `Steve_French_<Last>_<First>_<ID>_profile.pdf`, and the run state plus ledger. The Jeremy Affeldt PDF was rendered to an image and checked: Signatry header, badges, owner badge, and Fable footer all correct.

**Processing time and tokens by stage**

| Stage | Wall time | Model tokens | Notes |
| --- | --- | --- | --- |
| Init | under 1 s | 0 | 246 rows in, 245 accepted, 1 rejected |
| HubSpot pull | 7m 59s | 0 | 3 staggered workers, about 2 s per contact |
| Research | 1h 10m | 5,802,750 (measured) | 49 Fable subagents held at 8 concurrent, 2,232 tool calls, 907 searches, 606 fetches |
| Render | 13 s | 0 | workbook plus 245 PDFs |
| Overall | 1h 18m | | |

Tokens are harness-measured subagent totals (mean about 118k per group of five). My own orchestration context is not measured and not included. Holding concurrency at eight avoided the web search cap that hit the jmcbroom run, so no contact needed a re-run. Per-contact cost was about 23,700 tokens, the lowest of the four runs.

**Results**

| Score | High | Moderate | Low | None |
| --- | --- | --- | --- | --- |
| Contact identification | 210 | 13 | 13 | 9 |
| Household | 110 | 29 | 15 | 91 |

123 companies were researched and shared. 86 records carry a likely-duplicate flag and 5 are flagged as Signatry staff or staff-related. The rejected row was a Maryalice Smith record with no email, phone, or address.

**IT15 handling, please read.** HubSpot engagement text on 96 of these contacts was redacted as possibly Restricted before research: a credential term and health note on the Paul Tims record, wire and bank references, fund identifiers, and health or hardship notes. I added redactions during the run for items subagents surfaced: meeting dial-in PINs on Keith Greenfield, fund identifiers in email subjects on Carver Morgan and five other records, and a stock share-quantity email on Lauren Morgan. Please report the credential, PIN, account, and fund-identifier items to the Technology Team under IT14 Policy 10.

**Things I handled along the way**

- Under the minimum-data rule I removed a regulatory disclosure mention (David Stryzewski) and divorce details (Nicole Mullen). Both edits are logged in the contact's state file.
- I corrected two household attributions: Mark Graham's record had recorded a same-surname import pair as a spouse (now Low, candidate only), and Lauren Richards was paired against the wrong person when a public bio and shared address show she is Bowman Richards's wife (now High).
- One merge (Eric Dunavant) was denied for its subagent by the classifier. I checked the fragment for digit runs, Restricted terms, sources, and model, then merged it without `--force`.

**Reviewer items worth attention first**

- The Alpharetta address 11625 Rainwater Dr Suite 500 is the National Christian Foundation office and sits on 12 or more contacts here. It is a placeholder, not a residence, and subagents did not treat those contacts as households.
- Derek Gunn, household member of Shayna Gunn, died in May 2026 per a public obituary. Handle household mailings with care.
- Several records are not donors: Nic Perez-style advisor records (Tom Bardwell, Richard Betts, Michael Childs, Roger Proper, Chris Marks), organizational mailboxes (Pre-Born Donation Office, the Bouchard Remainder Unitrust), and two Steve French records (a personal one and the staff one). The staff record shows 80 redactions.
- Roughly 20 contacts have stale employers or emails per public sources (Dave Neff, Brian McGuire, Tommy Doerfler, Frank McGrew, Glenn Cranfield, David Cox, and others named in the profile flags).
- Nine None and 13 Low results are mostly email-only records with no geography; a city from Steve would unlock most of them.

**Skill issues**, unchanged from the earlier runs: the validator rejects any URL with a 13 to 19 digit run and forced roughly 20 re-merges; `pack_contact.py` was denied by the classifier for about a third of subagents; and the derive step still flags "no association recorded" where a Spouse label exists.

Nothing has been written back to HubSpot. Review starts with the `Accept?` column on the two Upload Prep sheets.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
