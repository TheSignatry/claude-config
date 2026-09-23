# others run report

Source: [TT-1359 comment 68431](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68431)
Posted by Trevor Bunch, 2026-09-22.

---

The others_543 run is complete and delivered to `~/Downloads/others_543_contact_research/`. It holds the workbook, 543 PDF profiles, the full state folder, and the orchestration records (ledger, queue, agent map, fragments, verify and stats output).

## Time and tokens by stage

| Stage | Wall time | Model tokens | Notes |
| --- | --- | --- | --- |
| Init | 0m 18s | 0 | 543 contacts, 0 rejected |
| HubSpot pull + derive | 12m 40s | 0 | 22 batches, 4 workers, 10,861 engagements |
| Research | 2h 34m 40s | 15,189,108 | 109 Fable subagents, 8 concurrent, 0 failures |
| Render | 0m 23s | 0 | workbook + 543 PDFs |
| **Total** | **2h 49m 52s** | **15.19M** | ~27,970 tokens per contact |

Research agents used 5,075 tool calls (2,588 searches, 1,217 fetches) and 18 hours of combined agent wall time. Tokens are the subagents' reported usage only.

## Results

| Contact match | Count | Household match | Count |
| --- | --- | --- | --- |
| High | 389 | High | 289 |
| Moderate | 55 | Moderate | 81 |
| Low | 55 | Low | 57 |
| None | 44 | None | 116 |

Owner distribution in the output: House Account 364, Heather Benak 74, Lauren Shoener 48, Shyla Collins 21, Drew Wright 13, Terri Slack 9, and eight others with 1 to 4 each. Owner badges and PDF filename prefixes vary accordingly. 132 company records were written and reused across colleagues.

## IT15 and IT14 Policy 10 items to report to the Technology Team

- **Pipeline redactions**: 841 engagement fields on 180 contacts, plus 3,092 gift-amount fields masked on 385 contacts.
- **Orchestrator redactions**: 226 additional fields across 78 entries on 89 contacts, each logged in the record's status errors. The main categories were plaintext temporary passwords (Wooddell, Bouwens, and two earlier), nonprofit ACH-form authorization codes (10 records), The Signatry's own Schwab account numbers embedded in DTC instructions (9 records, two account numbers), partial bank digits in "account ending in" phrasing (4 records), an outside DAF account number (Lehman), a Zoom meeting password (Sweeney), health or bereavement notes (Theut, Yoder, Garza, Woodward, Busenitz, Hudspeth, Selman, Simmons, Haugen, Fenno), and named third-party grant beneficiaries (Luthi).
- **Board Confidential**: Mark Bainbridge (Board Chairman) and Alan Pratt (President, Northwest Region) were missed by the insider detection because their records use personal or no email. I set the relationship manually and ran the board screen. Seven staff or board records are flagged in the Summary sheet.
- **Minimum-data edits**: dates of birth masked on 8 records; allegation characterization removed from the Bickle research while retaining the factual separation date.

## Reviewer items

- 136 records carry duplicate or same-person flags, and 91 carry unlabeled or partially labeled spouse flags. The workbook flags column and each PDF's Notes section list them.
- 6 records report a deceased spouse from a public source, recorded as fact and date only.
- 13 records are advisor-only fund roles; several (Strombeck, Amstutz, Jahnke, Walsh, Basch) look like mislabeled donors.
- Two records are Signatry insiders with personal emails; two records (Bainbridge, Ocenasek) have separate work-email duplicates.
- The Lynn Brown record is a corporate employee-giving fund whose emails carry the donor company's employee termination notices. That is Internal data, not Restricted, but the reviewer should decide whether it belongs in HubSpot.

## Skill gaps observed this run

- Credential screen misses "Temporary Password" bodies that are a bare token, ACH-form authorization codes, and Zoom passwords.
- Account screen misses hyphenated 4-4 brokerage numbers and "ending in xNNNN" partials, including The Signatry's own Schwab accounts.
- Staff and board detection needs a name-based fallback for personal or missing emails.
- ISP domains (ptd.net, iamotelephone.com, rocketmail.com, ibyfax.com) are classified as corporate.
- Subagent budgets were exceeded by one search on three contacts; the classifier denied five people-search fetches or searches.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use. All outputs are AI-assisted and require human review before use in decisions affecting donors (IT14 Policy 1).
