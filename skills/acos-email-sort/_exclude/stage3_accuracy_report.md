# acos-email-sort — Stage 3: Post-Fix Reclassification Report

**Date:** 2026-08-12 (updated multiple times same day: a follow-up round fixing 3 of the 6 original regressions, a correction after that round's own side effect was found, then a targeted round fixing Groups D/F/G from the high-severity review)
**Method:** Every fix from Themes A–J (excluding I) is now live in `triage.py`/`config.json`/`rejection_templates.yaml`. This stage re-runs the **current** `classify_message` against the original 281 Stage 1 messages (`stage1_messages.json` — full subject/sender/body/importance data, reused as-is, no new O365 fetches) and compares the result against Stage 2's real ground truth (`actual_folder` in `stage2_comparison.json`). This is a **simulation, not a live run** — see the Methodology section for exactly how "planned folder" was derived from each classify result, including the cases a genuinely fresh judgment call was required rather than mechanically reused.

Full per-message data: `_exclude/stage3_comparison.json`.

## Headline

| | Stage 2 (before) | First pass | Follow-up 1 | Follow-up 2 | **D/F/G round (final)** |
|---|---|---|---|---|---|
| Exact match | 103/278 (37.1%) | 134/278 (48.2%) | 139/278 (50.0%) | 141/278 (50.7%) | **145/278 (52.2%)** |
| Mismatch — low severity (bulk/filed shuffle, untouched by design) | — | 99 (35.6%) | 96 (34.5%) | 96 (34.5%) | 96 (34.5%) |
| Mismatch — medium severity | — | 19 (6.8%) | 19 (6.8%) | 19 (6.8%) | 21 (7.6%) |
| Mismatch — high severity (touches `1_priority`) | — | 26 (9.4%) | 24 (8.6%) | 22 (7.9%) | **16 (5.8%)** |

(278 = 281 minus the 3 resolved not-found cases, excluded from both sides for a fair comparison. Stage 2's original headline used 281 as the denominator; recomputed here on the same 278 basis Stage 3 uses.)

**75 of 281 messages (26.7%) now classify differently than they did in Stage 1**, after every round below — that's the real footprint of everything implemented this session.

## D/F/G round: fixing 6 of the 19 remaining high-severity cases

After follow-up round 2, the user asked to dig into 3 of the 19 still-open high-severity mismatches (see the earlier conversation for the full list and grouping): **Group D** (bare `undetermined`, no rule claims them), **Group F** (`priority` firing for a debatable reason), **Group G** (`bulk_review` catching a message that was actually priority-worthy).

**Fixed (6 messages, all verified via a status + severity diff against the pre-round snapshot):**
- **Group D — "The University of Texas at Austin - Recommendation Request"** (`gradref@austin.utexas.edu`) and **"Re: [TheSignatry/claude-config] Update Brand Tools..." (unsigned commits)** (`notifications@github.com`) — new `personal_action_request_keyword_patterns` (`has requested that you`, `letter of recommendation`, `unsigned commits`, `stopping a merge`) in `score_priority`. Both now MATCH.
- **Group G — "You've been invited to join TeamLogic IT Kansas City"** (`no-reply@notifications.ui.com`) — new paired check: message mentions a known `partner_vendors` name ("TeamLogic IT Kansas City") *and* matches `vendor_onboarding_keyword_patterns` (`you've been invited to join`, `sign up for an account`, `activate your account`, `create your account`). Catches the vendor's own invitation even though it arrived via a third-party platform, not TeamLogic's own domain. Now MATCHES. **Bonus, unplanned fix**: the reply in the same thread ("Re: You've been invited to join TeamLogic IT Kansas City," `ABrizendine@thesignatry.com`) also mentions the vendor name and "sign up for an account," so it independently resolved to MATCH too — the general fix (per the user's explicit choice over a one-off patch) caught a second real case nobody had specifically targeted.
- **Group F — "Your payment has been processed for the invoice IN-007-678-133"** (`no_reply@am.atlassian.com`) — added to the existing `financial_document_excluded_senders` allowlist (same mechanism as the earlier `elevate.inc` fix). No longer falsely escalates to priority (moved from high-severity mismatch to medium; doesn't land in the exact right folder, but the false-priority-escalation problem is solved).
- **Group F — "NLG Intake CYTD - DVR Approved"** (`noreply@notifications.hubspot.com`) — new `urgent_keyword_excluded_senders` allowlist (mirrors `financial_document_excluded_senders`'s design, scoped only to the urgent-keyword loop), seeded with this sender. Same result: no longer a high-severity false escalation, moved to medium (this one now lands in `bulk_review` rather than `2_review`, exposing a separate, smaller pre-existing gap — `notifications.hubspot.com` is a subdomain of the `hubspot.com` partner_vendors entry, and the domain match is exact-string, not subdomain-aware, so `protected_contact` doesn't catch it; not fixed here, flagged for later if it recurs).

**Accepted as-is, no fix:**
- **Group D — "Re: Update on Service Desk Analytics Beta Access"** (`Natalie.Sansone@infotech.com`) — no safe generalizable keyword for "an active vendor thread finally delivering something Trevor was waiting on." Added a new judgment-call bullet to `SKILL.md` instead, so a live run's LLM judgment step has explicit guidance to recognize this shape — doesn't move today's simulation number (Stage 1's judgment can't be retroactively re-run), but should help future live runs.
- **Group F — "Re: QA / DevOps Resources // Prerequisites"** (`cmurray@covalience.com`) — genuinely discusses an active SOW signing; a defensible, reasonable-either-way case, same as the previously-accepted Groups 1/4/6.

Verified with the same status+severity diff discipline established after follow-up round 2's near-miss: exactly 6 records changed (4 to a clean match, 2 from high to medium severity), nothing else moved.

**Why there's a second follow-up round:** fixing regression group 3 (VIP auto-replies wrongly suppressed) by letting the VIP-sender signal survive calendar/OOO suppression turned out to be too broad on its own — it also let a VIP's *pure calendar RSVP* ("Accepted: TreisD Meeting," from two different VIP senders) escalate to `1_priority` with zero actual content, since `Accepted:` is caught by the same `is_calendar_or_ooo_artifact` check as `Automatic reply:`. This was caught only because the second verification pass diffed mismatch *severity*, not just match/mismatch status, between before/after snapshots — the first round's verification had checked status only and reported "zero new side effects," which was accurate for status but missed that two low-severity mismatches had quietly become high-severity ones. Fixed by narrowing the VIP exemption to genuine `Automatic reply:` subjects only (`is_calendar_rsvp_artifact` now guards it) — verified clean with the same status+severity diff, confirmed exactly the two affected records changed and nothing else.

**Follow-up round (same day):** of the 13 regressions found in the first pass, groups 2, 3, and 5 were fixed (see "What got worse" below for the original root-cause writeups, still accurate as history) — all 5 affected messages resolved cleanly with **zero new side effects** introduced by the fixes themselves. Groups 1, 4, and 6 (8 messages) were explicitly accepted as-is rather than fixed. The sections below are left as originally written (they're the record of what was found and why); read "candidate fix" in groups 2/3/5 as "implemented," not merely proposed.

## Confusion matrix — final state (278 messages, excludes the 3 not-found cases)

Rows are the current classifier's planned folder; columns are the real, ground-truth folder Trevor actually filed each message into. The diagonal (**bold**) is a clean match; everything off it is a mismatch, and reading across a row shows exactly where that folder's mistakes land.

| planned ↓ / actual → | 1_priority | 2_review | 3_delegate | 4_autorespond | 5_drafts | 6_bulk | 7_toBeFiled | **Total** |
|---|---|---|---|---|---|---|---|---|
| **1_priority** | **24** | 9 | – | – | – | – | 1 | **34** |
| **2_review** | 6 | **51** | 2 | – | – | 1 | 10 | **70** |
| **3_delegate** | – | – | **1** | – | – | – | – | **1** |
| **4_autorespond** | – | – | – | – | – | – | – | **0** |
| **5_drafts** | – | – | – | 7 | – | 1 | – | **8** |
| **6_bulk** | – | 4 | – | 2 | – | **32** | 61 | **99** |
| **7_toBeFiled** | – | 13 | – | – | – | 16 | **37** | **66** |
| **Total** | **30** | **77** | **3** | **9** | **0** | **50** | **109** | **278** |

Diagonal sums to 145 — the exact-match count in the headline above. A few things jump out reading the off-diagonal cells:

- **`6_bulk → 7_toBeFiled` (61) and `7_toBeFiled → 6_bulk` (16)** dominate everything else combined (77 of the 133 total mismatches) — this is Theme A's bulk/filed boundary, left deliberately untouched this session (monitoring instead, per the Theme A decision).
- **`7_toBeFiled` row is the least reliable planned destination** — only 37 of 66 messages planned there (56%) actually landed there; 13 should have been `2_review` and 16 `6_bulk`. Filing something away is the single riskiest bucket_hint outcome in this matrix.
- **`1_priority` and `2_review` are reasonably solid** (24/34 = 71%, 51/70 = 73%) and are each other's main confusion partner (9 + 6 = 15 messages cross between them) — consistent with the VIP-sender-vs-content tension Theme D/the D/F/G round only partially resolved.
- **`5_drafts` never matches** (0 of 8) because of Theme I's dry-run caveat — no draft was ever actually created in this simulation, so there's nothing in `5_draftsToReview` for these 7 (Theme C matches) to land in for real; this column artifact is expected, not a defect.
- **`3_delegate` and `4_autorespond` are both essentially clean** (1/1 and correctly empty) — the narrowest, most deterministic buckets have the least room to go wrong.

## Methodology: how "Stage 3 planned folder" was derived

For each message, the new `classify_message` returns a `bucket_hint` plus flags, exactly as it would in a live run:

- **Fully deterministic buckets** (`priority`, `bulk_review`, `decline`, `routine_notification`) map directly to their folder (`decline` assumes the draft succeeds and moves to `5_draftsToReview`, matching the Decline flow's success path).
- **Deterministic flags on `undetermined`** (`ea_scheduling_delegate`, `farewell_note`, `protected_contact`, `internal_or_operational_alert`, and bare `sensitive`) map to their documented destination (`3_delegate` or `2_review`).
- **Bare `undetermined`** (nothing matched at all) needs a human/LLM judgment call, same as a live run. Where Stage 1's `bucket_hint` was *also* bare `undetermined`, Stage 1's original planned folder is reused verbatim — the judgment criteria for that residual bucket hasn't changed, so this is safe.
- **One case required a genuinely fresh judgment call, not a reuse**: "Automatic reply: Following up on the Interconfessional AI Conference" (`ballison@americanbible.org`) was `priority` in Stage 1 only because of the urgent-keyword false positive (`is_calendar_or_ooo_artifact` now correctly suppresses this). Its Stage 1 *planned folder* (`1_priority`) was a direct artifact of that bug, not a judgment call — reusing it would have silently re-introduced the bug into this report. Applied fresh judgment instead: routine OOO autoreply, no action items → `7_toBeFiled`.

## What improved — 44 messages, mismatch → match

| Mechanism | Count |
|---|---|
| `internal_or_operational_alert` (Theme B) | 26 |
| `priority` — financial/deal-document/HR-lifecycle signals (Theme D + G) | 8 |
| `routine_notification` (Theme F) | 6 |
| `sensitive` guidance (Theme E) | 2 |
| `ea_scheduling_delegate` (Theme J) | 1 |
| `protected_contact` (pre-existing, now reached correctly) | 1 |

Theme B's internal-domain fix did most of the work here — the bulk of Trevor's real "file this internal mail in 2_review" behavior was previously invisible to the classifier entirely.

**A confirmed win worth calling out specifically, not a regression:** the `5_draftsToReview → 4_autorespond` mismatch group grew from 3 (Stage 2) to 7 (Stage 3). This is Theme C working exactly as intended — 4 more of the real cold-pitch examples (Confiz's Data & AI pitch, the "Built For Nonprofits" pitch, the Salesforce "free sessions" upsell, the "Network monitoring" MSP pitch, "Demo Review," and "quick check") now correctly resolve to `bucket_hint: decline` instead of falling through to `undetermined`. The mismatch itself is purely Theme I's known caveat — no real draft was ever created in this dry run, so there's nothing to compare against except where Trevor hand-filed the original email (`4_autorespond`, exactly where Theme H said he would).

## What got worse — 13 new mismatches, match → mismatch

This is the part a Stage 3 test is *for*: catching side effects the Stage 2 report couldn't have predicted. Six distinct root causes, none of them large, all specific and fixable:

### 1. `internal_or_operational_alert` is too broad for routine, fully-automated internal notifications (5 cases)
**Evidence:** "Grant Paid from The Signatry" (x2), "Grant Recommended from The Bunch Family Fund" (x2), "Monday Meeting Agenda" — all `@thesignatry.com` senders Trevor actually just filed to `7_toBeFiled` with no review, now forced to `2_review` because *any* internal sender triggers the flag.
**Root cause:** Theme B's fix was built to catch security/system alerts and an internal newsletter being wrongly bulk-screened — it never distinguished those from routine, already-actioned internal system notifications (a donor's grant already processed, a meeting agenda already covered) that need no review at all.
**Candidate fix:** Add a narrow allowlist of internal *sender addresses* known to be fully-automated, no-action-needed systems (`donorcare@thesignatry.com` is the clearest candidate) that bypass `internal_or_operational_alert` and fall through to normal judgment instead.

### 2. Calendar accept/decline noise isn't suppressed outside the priority check (1 case)
**Evidence:** "Accepted: FirstRate - Dev Kickoff" (`dwright@thesignatry.com`) — a pure calendar-accept notification, forced to `2_review` via `internal_or_operational_alert`.
**Root cause:** `is_calendar_or_ooo_artifact` (Theme D) only suppresses the **priority** check; it was never wired into the internal-domain/operational-alert check, so an internal sender's calendar noise still trips it.
**Candidate fix:** Have `find_internal_or_operational_alert` also skip messages matching `is_calendar_or_ooo_artifact` — the same reasoning Theme D already established (these are system artifacts, not judgment calls) applies here too.

### 3. Calendar/OOO suppression is too broad for VIP-sender auto-replies tied to a real initiative (3 cases) — fixed in two steps
**Evidence:** "Automatic reply: Input for 'Stewarding AI at The Signatry'" from **three different VIP senders** (Greg Chapman, Kristin Hammett, Dane Frazier) — all real executives on a real initiative Trevor is running, all filed to `1_priority`, all now suppressed to `2_review` because the subject starts with "Automatic reply:".
**Root cause:** Theme D's negative filter was built from a single example (an external contact's routine OOO with a false urgent-keyword hit) and generalized to suppress *all* priority signals unconditionally — including VIP-sender priority. Real data shows that generalization was too aggressive: Trevor treats an executive's auto-reply to his own active initiative differently than a stranger's vacation notice.
**Fix, step 1 (implemented):** let the VIP-sender signal survive calendar/OOO suppression entirely — `is_calendar_or_ooo_artifact` no longer wipes it out. Fixed all 3 cases, verified clean via match/mismatch-status diff.
**Fix, step 2 (implemented after a second finding):** step 1 turned out to be too broad on its own — it also let a VIP's **pure calendar RSVP** ("Accepted: TreisD Meeting," from Steve French and Dane Frazier) escalate to `1_priority` with zero actual content, since `Accepted:` is caught by the same `is_calendar_or_ooo_artifact` check as `Automatic reply:`. This was only caught because a follow-up verification pass diffed mismatch *severity*, not just status — the step-1 verification had checked status only, correctly reporting "zero new side effects" for match/mismatch, but missed that two low-severity mismatches had quietly become high-severity ones. Added `is_calendar_rsvp_artifact` — narrows the VIP exemption to genuine `Automatic reply:` subjects (a generated message that can carry real content) only, never to the four pure-RSVP prefixes (which never carry content regardless of sender). Verified clean with a status+severity diff: exactly the two TreisD messages changed, nothing else.

### 4. HR-lifecycle "termination" keyword was over-generalized from one example (2 cases)
**Evidence:** There are **three** "Termination Workflow Notification" messages in the sample, not one. Trevor filed exactly one of them (Nicklaus Bartelli) to `1_priority` and the other two (Noah Edmondson, Oakley Gee) to `2_review`. The original Theme D analysis only surfaced one instance, and the new `hr_lifecycle_keyword_patterns` rule — built from that single data point — now force-escalates all three to priority, fixing 1 and breaking 2.
**Root cause:** A real generalization error on my part — one example was treated as representative of a uniform rule, but Trevor's actual behavior on this exact subject line is split 1-for-3, not unanimous.
**Candidate fix:** This one genuinely needs your input rather than a mechanical fix — is there something specific about the Nicklaus Bartelli case (a direct report? a role you were more invested in?) that made it priority-worthy where the other two weren't? If there's no reliable signal to distinguish them, `termination` may need to drop out of the priority keyword list entirely and go back to being handled via the existing `sensitive` flag → `2_review` guidance instead.

### 5. "invoice" keyword doesn't distinguish an actionable bill from an FYI-only auto-pay confirmation (1 case)
**Evidence:** "Replenishment Invoice ready" (Rippling spend-management auto-replenishment, `no-reply@elevate.inc`) — a fully automatic, recurring $130 replenishment notice with nothing to review or approve, filed to `6_bulkToReview` by Trevor, now forced to `1_priority`.
**Root cause:** `financial_document_keyword_patterns`'s `invoice` match doesn't distinguish "here's a bill you need to act on" from "here's a receipt-style confirmation that an automatic payment already happened."
**Candidate fix:** Low priority to fix given it's a single instance — if it recurs, a pattern like `\breplenishment\b` combined with `\binvoice\b` could specifically exclude this template, or exclude `no-reply@elevate.inc` as a known auto-pay confirmation sender.

### 6. A softer, more defensible miss (1 case)
**Evidence:** "TEAMLOGICIT KANSAS CITY | Payment request" — a real payment with a due date (`Due August 18th, 2026`), filed to `2_review` by Trevor, now escalated to `1_priority` via the `invoice` keyword in the body.
**Assessment:** Unlike case 5, this one has a real due date and a real payment action attached — reasonable people could file this either way. Not flagging this as something to fix, just noting it for completeness since it appears in the regression list.

## What's still unaddressed (131 cases — mostly as expected)

- **93 low-severity**: the `6_bulkToReview ↔ 7_toBeFiled` and related shuffle — untouched by design, per your decision to leave that boundary alone and monitor instead (Theme A).
- **19 medium-severity**: largely the same categories Stage 2 already described and that this round's fixes weren't aimed at.
- **19 high-severity, still open**: mostly VIP-senders forwarding routine/FYI content that Trevor didn't treat as priority (`FW: Finance Lead Team`, `Re: Compliance Courses are ready`, `Fw: Update and thoughts as promised`, three separate "Re:/FW: First Rate & The Signatry - MSA & SOW Review" messages) — a pre-existing Theme D gap (VIP sender ≠ automatic priority) this round's fixes didn't target, since the recommendations implemented were about *adding* sender-independent signals, not *removing* the VIP-sender signal's false positives. One concrete, easy find in this group: **"Re: The Signatry- Documents for GE100 Offering" should have matched `deal_document_keyword_patterns` but its regex (`documents for (the )?(offering|engagement)`) doesn't allow a deal name in between — real text is "Documents for GE100 Offering." Broadening to `documents for .{0,25}(offering|engagement)` would catch it** and is a one-line fix if you want it.

## Bottom line

First-pass net effect: **+44 fixed, −13 newly broken, for a net +31 messages** moved into a correct classification, on top of 90 that were already correct and unaffected. Every regression found had a specific, named root cause and either a concrete proposed fix or an explicit "needs your judgment" flag (Theme D's termination case) — nothing here was a mystery.

**Follow-up round 1: groups 2, 3, and 5 fixed, net +5 more messages.**
- **Group 2** (calendar-accept noise forced into `2_review` via internal-domain check) — `find_internal_or_operational_alert` now skips calendar/OOO artifacts, same reasoning Theme D already established for the priority check.
- **Group 3** (calendar/OOO suppression too broad for VIP auto-replies) — `score_priority` restructured so the VIP-sender check runs first and survives the calendar/OOO gate; only importance/urgent-keyword/financial-deal-HR-lifecycle signals are suppressed now.
- **Group 5** (auto-pay confirmation false-triggering the invoice keyword) — new `financial_document_excluded_senders` allowlist, seeded with `no-reply@elevate.inc`.

Verified with a status-only diff at the time: zero new match→mismatch side effects. **This check turned out to be incomplete** — see follow-up round 2.

**Follow-up round 2: Group 3's own fix had a side effect, found and fixed, net +2 more messages.** Letting the VIP-sender signal survive calendar/OOO suppression applied too broadly — it also let a VIP's pure calendar RSVP ("Accepted: TreisD Meeting" ×2) escalate to `1_priority` with zero content, silently upgrading two low-severity mismatches to high-severity ones without ever flipping their match/mismatch status (which is exactly why round 1's status-only diff missed it). `is_calendar_rsvp_artifact` now narrows the exemption to genuine `Automatic reply:` subjects only. Verified this time with a **status + severity** diff: exactly the 2 affected records changed, nothing else.

**Groups 1, 4, and 6 (8 messages) were explicitly accepted as-is, not fixed:**
- Group 1 (routine automated internal notifications forced into `2_review`) — accepted.
- Group 4 (HR-lifecycle "termination" keyword split 1-for-3 against real ground truth) — accepted; genuinely needs case-by-case judgment this test can't supply.
- Group 6 (TEAMLOGICIT payment request) — accepted as a defensible, reasonable-either-way miss.

Final state: **50.7% exact match** (141/278), high-severity mismatches down from 26 to 22. Lesson worth keeping for next time: when verifying a fix that touches which *bucket* a message lands in, diff severity/category, not just match-vs-mismatch status — a fix can move a mismatch from harmless to serious without ever showing up as a new mismatch.
