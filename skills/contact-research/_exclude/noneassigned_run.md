# noneassigned run report

Source: [TT-1359 comment 68395](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68395)
Posted by Trevor Bunch, 2026-09-22.

---

The NoneAssigned_37 test run is complete. Outputs are in `~/Downloads/noneassigned_37_contact_research/`, and the v1.6 tooling behaved as designed with one renderer bug found and fixed along the way.

**Deliverables**

- `noneassigned_37_Enriched.xlsx` with six sheets: Contact Enrichment (37 rows, 59 columns), Summary, Upload Prep – Contacts, Upload Prep – Notes, Methodology, Sources (190 rows).
- `profiles/` with 37 PDFs, every one named `None_Assigned_{Last}_{First}_{Id}_profile.pdf` with an "OWNER: NONE ASSIGNED" badge.
- `state/` with all contact JSON, 8 company records, and `orchestration/` with the ledger, queue, and fragments.

**Time and tokens by stage** (from `orchestrate.py stats`, measured only)

| Stage | Wall time | Tokens |
| --- | --- | --- |
| Init | 21 s | 0 |
| HubSpot pull (2 batches, 200 engagements) | 3 min 25 s | 0 (API only) |
| Research (8 subagents, all concurrent) | 10 min 59 s | 980,945 |
| Render (workbook + 37 PDFs) | 2 s | 0 |
| Overall | 16 min 07 s | |

Per contact: 26,512 tokens, in line with the 23,000 to 25,000 seen in prior runs. All 8 agents reported usage; none failed, so no rerun groups. Range 86,041 to 148,022 per agent, 371 tool uses, 197 searches, 89 fetches.

**Results**

| Match confidence | Count | Household confidence | Count |
| --- | --- | --- | --- |
| High | 21 | High | 18 |
| Moderate | 8 | Moderate | 8 |
| Low | 4 | Low | 2 |
| None | 4 | None | 9 |

All on Fable 5.1, no forced merges, no digit-run rejections outside URLs, no prefix violations. 11 contacts carry a possible-duplicate flag. The four Nones are Cates, Nixon, Lee, and Blair, each with a documented reason.

**What the v1.6 changes did in practice**

- "None Assigned" appeared consistently in the pulled state, the workbook column, the PDF badge, and all 37 filenames.
- The IMPORT rule produced zero household-pair artifacts on 29 imported records. Seven contacts have a Spouse label, and subagents still found probable spouses for several unlabeled records.
- No subagent needed to run a payload script, and none reported a classifier denial.
- URL exemption held: no source URL tripped the account screen. One merge was still rejected because a subagent wrote a Wyoming Secretary of State entity number in prose. That is a public identifier the governance now permits, so the 13 to 19 digit pattern remains a friction point for entity numbers outside URLs.
- Renderer bug found and fixed in the skill: one contact's HubSpot note exceeded a page and crashed the PDF build. `build_profiles.py` now strips HTML and clips each note body to 400 characters. Prior runs had masked this with a scratch script. Lint passes and the zip is rebuilt.

**Items for the relationship manager**

- William Coody (29166034050) is reported deceased on August 6, 2026 by a Tulsa World obituary matched on name and city only. HubSpot shows him as an active Full Access fund holder. Verify before any outreach and check for a successor advisor.
- Warren Richards (29167065441) shares a mailbox with Bowman Richards and may be his father or minor son. Identity unresolved.
- Janet Green's HubSpot ZIP 39107 is a Mississippi code; the property is 38017.
- Unassociated probable spouses with existing HubSpot records: Annette Godfrey, Amy Bouley, Julie Kaylor, Kim Roberts, Leticia Harnung, Lianne Terry, Jenna McCawley, Linda Graeve.
- Likely duplicates: Teeple 220309184157, Godfrey 29167392257, Boutross 187459891021, Tommerup 30974002689, Cates 187097636504.
- Michel Borchardt's HubSpot surname is misspelled "Bochardt".

**IT15 items to report to the Technology Team (IT14 Policy 10)**

The pull redacted 12 engagement fields on 7 contacts as possible Restricted content. No targeted redactions were needed this run. Subagents reported and did not record a spouse date of birth, aggregator phone numbers, and stock share counts in emails; these are Confidential rather than Restricted and required no action.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
