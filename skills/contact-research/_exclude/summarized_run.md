# Contact research runs — consolidated summary

Summarizes the seven run reports in this folder: `pboone_run.md`, `darmstrong_run.md`, `jmcbroom_run.md`, `sfrench_run.md`, `apratt_run.md`, `noneassigned_run.md`, `others_run.md`. Source comments are on [TT-1359](https://signatry1.atlassian.net/browse/TT-1359), posted 2026-09-21 and 2026-09-22.

Compiled 2026-09-23. Every confidence row reconciles to its run's contact count.

## Time and tokens by stage

| Run | Contacts | HubSpot pull | Research | Overall | Tokens | Tokens/contact |
|---|---|---|---|---|---|---|
| pboone | 449 | 12m 13s | 2h 12m | 2h 16m | 10,783,712 | 24,017 |
| darmstrong | 333 | 11m 15s | 1h 24m | 1h 39m | 8,463,135 | 25,414 |
| jmcbroom | 76 | 5m 43s | 49m | 49m | 2,777,057 | 36,540 |
| sfrench | 245 | 7m 59s | 1h 10m | 1h 18m | 5,802,750 | 23,684 |
| apratt | 436 | 12m 19s | 2h 01m | 2h 22m | 10,756,353 | 24,670 |
| noneassigned | 37 | 3m 25s | 11m | 16m | 980,945 | 26,512 |
| others | 543 | 12m 40s | 2h 35m | 2h 50m | 15,189,108 | 27,972 |
| **Total** | **2,119** | **1h 06m** | **10h 22m** | **11h 30m** | **54,753,060** | **25,839** |

Init and render never exceeded 47 seconds and consumed no model tokens. Research is 90 percent of wall time and effectively all of the token spend. Across all runs: 442 subagents, 8,664 web searches, 5,019 page fetches, 878 company records built and reused.

Throughput held at 18 to 19 seconds per contact on every run except jmcbroom and the tiny noneassigned batch.

## Results

| Run | Contact High | Mod | Low | None | High rate | Household High | Mod | Low | None | Household None rate |
|---|---|---|---|---|---|---|---|---|---|---|
| pboone | 393 | 17 | 20 | 19 | 88% | 231 | 39 | 30 | 149 | 33% |
| darmstrong | 297 | 9 | 15 | 12 | 89% | 204 | 20 | 16 | 93 | 28% |
| jmcbroom | 52 | 10 | 5 | 9 | 68% | 35 | 10 | 10 | 21 | 28% |
| sfrench | 210 | 13 | 13 | 9 | 86% | 110 | 29 | 15 | 91 | 37% |
| apratt | 400 | 12 | 16 | 8 | 92% | 226 | 26 | 24 | 160 | 37% |
| noneassigned | 21 | 8 | 4 | 4 | 57% | 18 | 8 | 2 | 9 | 24% |
| others | 389 | 55 | 55 | 44 | 72% | 289 | 81 | 57 | 116 | 21% |
| **Total** | **1,762** | **124** | **128** | **105** | **83%** | **1,113** | **213** | **154** | **639** | **30%** |

## Trends worth raising

**The jmcbroom run is the one real outlier, and it was a concurrency mistake.** Launching all 16 groups at once hit a session-wide 200-search cap, so 42 of 76 contacts were researched with truncated or zero searches and had to be re-run. That cost 36,540 tokens per contact against a 23,700 to 28,000 band everywhere else, and 38.7 seconds per contact against 18 to 19. Every run after it held 8 concurrent and stayed in band. The cap is the binding constraint on parallelism, not model capacity.

**Identification quality tracks whether the list has an owner.** RM-owned lists returned 86 to 92 percent High. The two unowned buckets returned 57 percent for noneassigned and 72 percent for others. Those lists are dominated by House Account records with thin HubSpot data, so the shortfall is input completeness rather than research quality. A city or firm name from the RM would unlock most of the 105 None results.

**Household is the weakest output across the board.** 639 contacts, 30 percent of everything researched, returned no household at all. That is by far the largest remaining gap and the most likely target for a follow-up pass.

**Restricted data in HubSpot engagement text is systemic, not incidental.** Roughly 1,081 of 2,119 contacts had engagement fields redacted, near 51 percent. The recurring categories are portal credentials, fund and account identifiers, wire and bank references, and health or hardship notes. The apratt run alone redacted 3,886 fields across 311 contacts. This is a HubSpot data-hygiene problem worth raising with the Technology Team independently of any single run.

**Deceased contacts are a live outreach risk.** Ten named individuals were found deceased by public sources while HubSpot still showed them active, plus six deceased spouses in the others run.

| Run | Deceased found |
|---|---|
| darmstrong | Robert Woodson, May 2026, still Grant Advisor on four funds; Tom Cousins, July 2025 |
| jmcbroom | Bill Ostrie, unverified, carries a Survived By association |
| sfrench | Derek Gunn, household member, May 2026 |
| apratt | Vaughn Mulcrone, May 2026, HubSpot shows active client; Gregory Jantz; Bill Kennedy; Stuart Messnick; Germaine Korum |
| noneassigned | William Coody, August 2026, active Full Access fund holder |
| others | Six deceased spouses, recorded as fact and date only |

**Duplicate records are the single largest HubSpot cleanup item.** 588 records carry a likely-duplicate or same-person flag, 28 percent of everything processed. Unlabeled spouse associations were only counted systematically in the last two runs, where others alone flagged 91, about 17 percent of that list. Roughly 41 records across all runs are financial advisors on client funds rather than donors, and 27 are Signatry staff or board records.

**The v1.6 fixes held, and then the largest run found the next tier.** The noneassigned test confirmed three fixes landed: the URL exemption stopped the digit-run validator false positives, no subagent needed the payload script that the classifier kept denying, and the PDF renderer no longer crashes on long notes. The subsequent others run surfaced a new set: the credential screen misses bare-token password bodies, ACH authorization codes, and Zoom passwords; the account screen misses hyphenated brokerage numbers and "ending in" partials; and staff or board detection fails when the record has a personal email or no email, which is how both Mark Bainbridge and Alan Pratt slipped through.

---

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
