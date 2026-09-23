# apratt run report

Source: [TT-1359 comment 68387](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68387)
Posted by Trevor Bunch, 2026-09-21.

---

The apratt_436 run is complete. All outputs are in `~/Downloads/apratt_436_contact_research/` and the PDF preview renders correctly with the Signatry header, the "Owner: Alan Pratt" badge, and the IT14 Policy 1 footer.

**Deliverables**

- `apratt_436_Enriched.xlsx` with six sheets: Contact Enrichment (436 rows), Summary, Upload Prep – Contacts, Upload Prep – Notes, Methodology, Sources (2,792 rows).
- `profiles/` with 436 PDFs named `Alan_Pratt_{Last}_{First}_{Id}_profile.pdf`, 31.5 MB total.
- `state/` with all 436 contact JSON files, 228 company records, and `ledger.json`.

**Time and tokens by stage**

| Stage | Wall time | Tokens |
| --- | --- | --- |
| Init | under 1 s | 0 |
| HubSpot pull (18 batches, 4 workers, 9,368 engagements) | 12 min 19 s | 0 (API only) |
| Research (94 subagents, 8 concurrent) | 2 h 01 min | 10,756,353 measured |
| Render (workbook + 436 PDFs) | 47 s | 0 |
| Overall (init start to render end) | 2 h 22 min | |

Research token detail: 86 agents reported usage covering 424 contacts, mean 125,073 per agent, about 25,400 per contact. Eight agents were killed by the usage-credit exhaustion and reported no usage, so the true total is higher by their partial work. Those eight had merged 12 contacts before termination; the remaining 28 were regrouped into six rerun groups that consumed 728,119 of the tokens above. Subagent wall time summed to 13.7 hours, 1,632 web searches, 1,056 page fetches.

**Results**

| Match confidence | Count | Household confidence | Count |
| --- | --- | --- | --- |
| High | 400 | High | 226 |
| Moderate | 12 | Moderate | 26 |
| Low | 16 | Low | 24 |
| None | 8 | None | 160 |

All 436 on Fable 5.1, no forced merges, no digit-run or off-model flags. 262 contacts have a named spouse. 104 contacts carry a possible-duplicate flag, which is the largest single HubSpot cleanup item in this list.

**IT15 items to report to the Technology Team (IT14 Policy 10)**

- 311 of 436 contacts had HubSpot engagement text redacted as possible Restricted content, 3,886 fields in total. Most came from the pipeline scrub. 18 were targeted redactions I applied after subagents reported health details, a bereavement, a pregnancy mention, a board meeting note, wire and account references, children's birth dates, sale proceeds, ownership percentages, or gift commitments. Neither I nor the subagents read the redacted bodies. The McGowan record (29169715056) had 100 of 129 engagement fields redacted because the flagged content spanned the email history.
- Subagents also dropped Restricted or sensitive content seen in public sources without recording it: obituary causes of death, a family member's substance recovery, a State Bar license number, insurance license and CRD numbers, and people-search ages and birth dates.

**Orchestrator edits (109 contacts, logged in each record's status.errors)**

- EIN and CRD identifiers stripped from research text and source URLs across 109 contacts and about 50 company files, matching the minimum-data rule used in prior runs.
- Regulatory or litigation references removed from 7 records (Stalcup SEC investigation and lawsuit allegations, LaRocca client litigation, Alexandrovic and Lockard disclosure notes, and similar).
- Anticipated business sale note removed from Stamm; unsupported resignation claim removed from Dong.

**Reviewer items worth attention first**

- Vaughn Mulcrone (29170057481) is reported deceased May 2, 2026 while HubSpot shows an active client. Gregory Jantz, Bill Kennedy, Stuart Messnick, and Germaine Korum are also deceased per public sources.
- Heal Our Land (Starr family nonprofit) is typed as a grant recipient and needs a related-party grant review.
- Gary Nagel is a Signatry board member. His board-related engagement fields were redacted as possible Board Confidential material.
- Roughly 20 contacts are financial advisors on client funds, not donors (Falcon, Freeman, McVicker, Betts, Good, Bankey, Auger, T. Johnson, and others).
- Several stale employers: Hay retired, Yeung moved to Coldstream, Amaradio's firm joined SEIA, Auger at Alta Strada, Lockard leaving Morgan Stanley, Cargill at Bluebonnet, Noy left Wealth Legacy Group.

**Skill issues seen this run**

- The credit exhaustion killed 8 agents mid-run. Recovery worked because state is per-contact, but the ledger has no token usage for those 8.
- The 13 to 19 digit card/account validator kept rejecting URLs from Business Wire, SEC EDGAR, BBB, LinkedIn, Facebook, and LoopNet, forcing about 20 re-merges. A URL exemption would remove this.
- `pack_contact.py` was denied by the auto-mode classifier for roughly a third of subagents; they read state directly with equivalent results.
- `derive.py` misclassified proton.me, pm.me, duck.com, frontier.com, and family vanity domains as corporate, and its "no association recorded" flag is stale where a Spouse label exists.
- `company_prior` keys only on the contact's own email domain, so shared domains like nm.com and lpl.com collide across different practices.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
