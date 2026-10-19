# jmcbroom run report

Source: [TT-1359 comment 68351](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68351)
Posted by Trevor Bunch, 2026-09-21.

---

Written for: Jill McBroom as the reviewing relationship manager, with you as the operator.

The jmcbroom run is complete. Outputs are in `~/Downloads/jmcbroom_76_contact_research/`: the enrichment workbook, 76 PDF profiles named `Jill_McBroom_<Last>_<First>_<ID>_profile.pdf`, and the run state plus ledger. The C. Craft PDF was rendered to an image and checked: Signatry header, confidence badges, owner badge, and Fable footer all correct.

**Processing time and tokens by stage**

| Stage | Wall time | Model tokens | Notes |
| --- | --- | --- | --- |
| Init | under 1 s | 0 | 76 rows in, 76 accepted, 0 rejected |
| HubSpot pull | 5m 43s | 0 | 2 staggered workers, about 4.5 s per contact |
| Research (first wave) | 24 min | 1,678,156 | 16 Fable subagents, all 16 launched at once |
| Research (re-run wave) | 25 min | 1,098,901 | 9 Fable subagents covering 42 contacts |
| Render | 4 s | 0 | workbook plus 76 PDFs |
| Overall | 49 min | 2,777,057 | 25 subagents, 1,082 tool calls, 343 searches, 166 fetches |

Tokens are harness-measured subagent totals. My own orchestration context is not measured and is not included.

**What went wrong and how it was handled.** Launching all 16 groups at once hit a session-wide web search cap of 200 calls about a third of the way through the wave. Every contact still got merged, but 42 of the 76 were researched with truncated or zero searches. Once search was available again I re-ran those 42 in nine smaller groups with a brief that told agents to redo the research over the provisional block and clear the "incomplete" flags. The re-run raised several scores (Hewson None to High, Synek and Walls to High, Lopez and LeBouf households to High) and confirmed others as genuine None. This is why the run cost about 36,500 tokens per contact against roughly 25,000 for the darmstrong run. Lesson recorded for future runs: keep concurrent research groups to about eight, or spread them across turns.

**Results**

| Score | High | Moderate | Low | None |
| --- | --- | --- | --- | --- |
| Contact identification | 52 | 10 | 5 | 9 |
| Household | 35 | 10 | 10 | 21 |

19 companies were researched and shared across contacts. 29 records carry a likely-duplicate flag. Fourteen contacts in this file have only an email address in HubSpot, which is why the None and Low counts run higher than the previous two lists.

**IT15 handling, please read.** HubSpot engagement text on 61 of these contacts was redacted as possibly Restricted before research began: a portal credential term on the Craft record, partial account references, and health or hardship notes. I also redacted a James Smart call note that a subagent reported as containing health remarks, without reading it. One subagent flagged an October 2025 "invitation" email on Rick Werts's record that asks recipients to download and install a file, which looks like phishing or a compromised sender. Please report the credential, account, and phishing items to the Technology Team under IT14 Policy 10.

**Things I handled along the way**

- One merge (Ted Hewson) was denied for its subagent by the classifier. I inspected the fragment, confirmed no digit runs, no Restricted terms, correct model, and ten sources, then merged it myself without `--force`.
- Under the minimum-data rule I removed one business-litigation mention from Mike Bookout's record. This is the only orchestrator content edit in this run.

**Reviewer items worth attention first**

- Bill Ostrie carries a "Survived By" association in HubSpot and may be deceased; verify before outreach.
- Nic Perez and C. Craft are financial advisors coordinating client funds, not fund holders.
- Ruth Thomas's record lists Summer Thomas as a candidate spouse, but Summer's own record confirms a different spouse; the pair is an import artifact and should not become an association.
- Several probable spouses exist in HubSpot without Spouse labels (Martens, Wu, Wambolt-style cases are listed in each profile's flags).
- Caleb Gile's only public footprint suggests a dependent, not an independent donor.

Nothing has been written back to HubSpot. Review starts with the `Accept?` column on the two Upload Prep sheets.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
