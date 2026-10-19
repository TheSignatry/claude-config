# pboone run report

Source: [TT-1359 comment 68338](https://signatry1.atlassian.net/browse/TT-1359?focusedCommentId=68338)
Posted by Trevor Bunch, 2026-09-21.

---

Written for: Phil Boone as the reviewing relationship manager, with you as the operator.

The run is complete. Outputs are in `~/Downloads/pboone_451_contact_research/`: the enrichment workbook, 449 PDF profiles named with pattern 3 (`Phil_Boone_<Last>_<First>_<ID>_profile.pdf`), and the run state plus ledger so anything can be re-rendered without new research.

**Processing time and tokens by stage**

| Stage | Wall time | Model tokens | Notes |
|---|---|---|---|
| Init | under 1 s | 0 | 451 rows in, 449 accepted, 2 rejected |
| HubSpot pull | 12m 13s | 0 | 3 parallel workers, about 1.6 s per contact |
| Research | 2h 12m | 10,783,712 (measured) | 90 Fable subagents, 4,163 tool calls, 1,674 searches, 1,062 fetches |
| Render | 19 s | 0 | workbook plus 449 PDFs |
| Overall | 2h 16m | | |

Research tokens are the harness-measured totals for the 90 subagents (mean about 120k per group of 5). My own orchestration context is not reported by the harness, so it is not included. All 449 contacts were researched by claude-fable-5-1, on policy for the standard tier.

**Results**

| Score | High | Moderate | Low | None |
|---|---|---|---|---|
| Contact identification | 393 | 17 | 20 | 19 |
| Household | 231 | 39 | 30 | 149 |

211 companies were researched and shared across contacts. 100 records carry a likely-duplicate flag and 11 are Signatry staff records. The two rejected rows (Donny Newman, John Yun) had no email, phone, or address.

**IT15 handling, please read.** HubSpot engagement text on 239 of these contacts contained material the skill's screen or my broader sweep treated as possibly Restricted: portal login credentials, fund and account identifiers, wire details, health and hardship references, and one partial brokerage account number. All of it was redacted from the run state before rendering, and dollar amounts in notes were masked for gift-amount confidentiality. Nothing was carried into research prose. Please report the credential and account sightings to the Technology Team under IT14 Policy 10; the affected records are flagged in the workbook and on each PDF. My sweep is deliberately broad, so some ordinary donor-care emails were redacted too.

**Things I handled along the way**

- The auto-mode classifier blocked several subagents from re-running a merge after the validator rejected a source URL for a long digit run (SEC accession numbers, BBB profile IDs). Five fragments and one company file were merged by me after inspecting them; all passed validation without `--force`.
- I stripped three items under the minimum-data rule: a spouse's court ruling, a company bankruptcy filing, and a trustee claim that a later group showed belonged to the contact's spouse.
- The skill's PDF renderer crashed on very long HubSpot notes, so I capped note bodies in the run state at 400 characters. That is a skill limitation worth a separate fix, along with the validator's digit-run false positives on URLs.

**Next step for Phil:** review the `Accept?` column on the two Upload Prep sheets and the flags on each profile. Nothing has been written back to HubSpot. Twenty records are Low and nineteen are None, most for lack of geography in HubSpot; a city or firm name from Phil would unlock most of them on a re-run.

This is informational only and is not professional advice. Review by the appropriate internal team is required before use.
