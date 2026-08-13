# acos-email-sort — Stage 2 Real-World Accuracy Report

**Date of run:** 2026-08-12
**Method:** Stage 1 (dry run) produced a planned target folder for all 281 messages then in Trevor's Inbox, using `triage.py classify` plus LLM judgment for the `undetermined` bucket — nothing was moved. Trevor then manually filed all 281 messages by hand into the real `_claude` folder structure. Stage 2 re-read the actual current location of every one of those 281 messages (matched by `internetMessageId`, sequentially per folder to avoid tool-batching attribution errors — see note below) and compared it against the Stage 1 plan.

Source data: `stage1_plan.json` (plan) vs. `actual_<folder>.json` (ground truth), merged by `build_stage2_comparison.py` into `stage2_comparison.json` (full per-message result).

## Headline numbers

| Outcome | Count | % of 281 |
|---|---|---|
| **Exact match** | 103 | 36.7% |
| Mismatch — low severity (taxonomy overlap between two "no action needed" buckets) | 89 | 31.7% |
| Mismatch — Stage-1 dry-run artifact (decline drafts never actually existed) | 3 | 1.1% |
| Mismatch — medium severity (review-need or decline-detection gap) | 57 | 20.3% |
| Mismatch — high severity (crosses the `1_priority` boundary) | 26 | 9.3% |
| Not found in any of the 7 folders or Inbox | 3 | 1.1% |
| **Total** | **281** | **100%** |

*Update: all 3 "not found" cases are resolved — see §1. Two are invitation responses Outlook auto-moved to Deleted Items (outside this survey's scope, not a classification miss); one is a thread-superseded message that, per Trevor, would have added another `7_toBeFiled → 2_review` mismatch had it still been present.*

Read plainly: exact-match accuracy was **36.7%**. But a third of the "misses" (the low-severity group) are really a case of the skill and Trevor agreeing the message needed no action, just disagreeing on *which* no-action folder — functionally harmless. Folding those in, the skill placed messages in a **functionally acceptable location 68.4% of the time** (103 + 89 = 192 / 281). The genuinely concerning slice is the 26 high-severity misses (9.3%) where the skill's plan and Trevor's actual filing disagreed about whether something was urgent at all, plus the 57 medium-severity misses (20.3%) where a review-worthy or decline-worthy message would have been silently filed or bulk-swept.

Folder-count sanity check (all 7 subfolders + Inbox independently re-verified via sequential, single-call-at-a-time queries this session, after an earlier parallel-batch attempt produced internally contradictory data and was discarded):

| Folder | Actual count |
|---|---|
| 1_priority | 30 |
| 2_review | 79 |
| 3_delegate | 3 |
| 4_autorespond | 9 |
| 5_draftsToReview | 0 |
| 6_bulkToReview | 50 |
| 7_toBeFiled | 109 |
| Inbox (new mail, out of scope) | 9 |
| **Sum of the 7 filing folders** | **280** |

280 of 281 planned messages were accounted for across the 7 folders; the 1 remaining is one of the 3 "not found" cases below (the other 2 "not found" messages are presumably duplicates within a reply thread — see that section).

---

## 1. Not-found cases (3) — resolved

These 3 messages from the Stage 1 plan were not located, by exact `internetMessageId`, in any of the 7 `_claude` folders or the Inbox. **Method gap identified:** Stage 2's folder survey covered only the 7 `_claude` subfolders plus Inbox — it never checked Deleted Items. Trevor confirmed all 3 have a mundane explanation that this scope gap alone accounts for:

1. **"Thank you for registering"** — `do_not_reply@on24event.com` — planned `7_toBeFiled`. A meeting/event invitation; Outlook auto-moves these to Deleted Items once responded to. Not a classification miss — just outside the folder set this survey checked.
2. **"Introduction - The Signatry and Roshon Therapeutics"** — `jwynn@thesignatry.com` — planned `2_review`. Same explanation — an invitation, auto-deleted after response.
3. **"Re: Applications Systems Administrator Position"** — `mstacy@thesignatry.com` — planned `7_toBeFiled`. This is the one substantive case: the thread's original message (from Aril Brizendine, asking to post the position) is the one Stage 1 planned for and that's now missing; Melissa Stacy's reply confirming the position was posted ("Posted!") is the message actually sitting in `2_review`. Per Trevor, **the original message from Aril would have qualified for review** — meaning had it been found, this would register as an additional `7_toBeFiled → 2_review` mismatch, reinforcing Theme E/F below (personnel/staffing-adjacent requests from non-HR-system senders under-triggering review).

**Methodology note for future re-runs:** include Deleted Items in the actual-location survey, or accept that invitation-type messages will systematically read as "not found" once responded to, and don't count them against accuracy.

---

## 2. Root-cause themes and recommendations

Ranked by how much they explain (largest bucket of mismatches first).

### Theme A — The bulk/no-action boundary is too fine-grained for how Trevor actually processes marketing mail
**Evidence:** 89 low-severity mismatches, split `6_bulkToReview → 7_toBeFiled` (61), `7_toBeFiled → 6_bulkToReview` (16), `2_review → 7_toBeFiled` (11), `2_review → 6_bulkToReview` (1).
**Root cause:** The skill inserts a "quick human screen" step (`6_bulkToReview`) between "this looks like bulk/marketing mail" and "this is done, file it." In practice Trevor treats essentially all cold newsletters, vendor marketing blasts, and webinar invites the same way regardless of which bucket the skill guessed — he files them directly. The screening step isn't adding a decision he actually makes; it's just an extra folder to glance through.
**Recommendations:**
1. Merge `6_bulkToReview` and `7_toBeFiled` into a single "no action needed" destination by default, and reserve a separate, explicitly-named review step only for bulk mail that also matches a `sensitive`/`protected_contact`/urgent-keyword signal (i.e., keep the screen only when there's a real reason to look).
2. If Trevor wants to keep `6_bulkToReview` as a distinct folder, track actual usage over a few weeks and consider retiring it if it consistently gets filed without being opened — evidence that a human step isn't earning its keep is more informative than an a priori design guess.
3. Loosen the requirement that `undetermined`-bucket bulk mail go straight to `7_toBeFiled` — route more of it through whichever "no action" folder is retained, consistently, rather than splitting undetermined bulk mail between two destinations based on subtle sender-pattern differences Trevor doesn't act on anyway (see Theme C for the flip side of this).

### Theme B — Sender-pattern bulk detection produces false positives on system/security alerts
**Evidence:** Contributes to the 20 `6_bulkToReview → 2_review` mismatches. Examples: repeated **"PIM: A privileged directory role was assigned outside of PIM"** (`MSSecurity-noreply@microsoft.com`), **"Your organization is out of SharePoint Online storage space"** (`no-reply@sharepointonline.com`, appearing *five times* across the sample), **"GiveInteractiveSupport_v2 PROD"** pipeline report (`data-studio-noreply@google.com`), **"Is Wanting Lower Taxes Wrong?"** (`info@thesignatry.com` — an internal Signatry newsletter, not vendor marketing).
**Root cause:** `triage.py`'s bulk-mail sender-pattern match (`no-?reply`, generic automation addresses) doesn't distinguish "cold marketing blast" from "recurring operational/security system alert." Trevor actually wants to at least glance at security posture alerts (PIM role assignments, storage warnings) even though they're automated and repetitive — he put every one of them in `2_review`, never in the bulk-screen folder.
**Recommendations:**
1. Add a distinct sender/subject-pattern allowlist for known operational-alert senders (`MSSecurity-noreply@microsoft.com`, `no-reply@sharepointonline.com`, `Office365Alerts@microsoft.com`, internal `*@thesignatry.com` senders even when they look automated) that routes straight to `2_review`, bypassing the bulk-mail check entirely regardless of the generic `no-?reply` pattern match.
2. Treat `@thesignatry.com` sender domain as a strong signal against the bulk/marketing bucket — internal senders essentially never need a "is this even worth Trevor's time" screen the way external cold outreach does.

### Theme C — Decline-template matching misses obvious cold-outreach pitches
**Evidence:** 8 mismatches where the skill filed a message as `undetermined` (bulk or toBeFiled) but Trevor moved it to `4_autorespond` — his de facto "decline" bucket (see Theme H). Examples: **"The Signatry / Data & AI"** cold pitch, **"RE: Built For Nonprofits"**, **"Free sessions this month on Agentforce Nonprofit"**, **"Network monitoring - The Signatry"**, **"Demo Review"** ("just reply Yes"), **"quick check"** (an address-verification spam probe), **"Augusta Experience"**, **"Why teams choose Onspring for GRC."**
**Root cause:** `triage.py`'s decline-template matcher isn't catching a real, recognizable category of cold B2B sales pitch and low-effort verification spam that a human recognizes instantly. These messages don't match the existing decline keyword/pattern set, so they default to `undetermined` and get filed or bulk-flagged instead of being routed toward a decline draft.
**Recommendations:**
1. Expand the decline-template match patterns using these 8 examples as a labeled seed set — look for the common shape (unsolicited pitch to a `*@thesignatry.com` non-personal inbox, offering a demo/call/free session, from a sender with no prior thread history).
2. Add a lightweight "email verification probe" pattern (very short message, generic greeting, asking only "is this the right email for you?") — these are reconnaissance for future spam and are safe to auto-decline or file without review.

### Theme D — VIP-sender priority detection is sender-driven, not content-driven (highest-severity theme)
**Evidence:** This is the two-way high-severity split — 12 `2_review → 1_priority` (skill under-escalated) and 6 `1_priority → 2_review` (skill over-escalated), for 18 of the 26 high-severity misses.
- Under-escalated (skill said review, Trevor said priority): **"Termination Workflow Notification"**, **"Invoice INV-19611"** (x2, an AP invoice needing action), **"Re: Update on Service Desk Analytics Beta Access"** (active vendor thread), **"August 12th meeting"** (vendor trying to reschedule), **"The University of Texas... Recommendation Request"** (a personal action item), **"Thank you"** (a farewell note from a departing intern), **"Re: The Signatry- Documents for GE100 Offering"** (x2, active deal documents).
- Over-escalated (skill said priority because the sender is on the VIP list, Trevor said review): **"NLG Intake CYTD - DVR Approved"** (an internal report digest), **"Automatic reply: Following up on the Interconfessional AI Conference"** (an out-of-office autoreply!), **"FW: Finance Lead Team"** (a routine resource-booking forward), **"Canceled: TLITKC Monthly Client Business Review"** (a meeting cancellation), **"Re: Compliance Courses are ready"**, **"Fw: Update and thoughts as promised"**.
**Root cause:** `1_priority` is currently decided almost entirely by *who sent it* (executive/VIP allowlist) rather than *what kind of message it is*. That produces both failure directions at once: VIP auto-replies and cancellations get flagged priority they don't deserve, while genuinely actionable items (invoices, live deal threads, HR terminations, personal action requests) from non-VIP senders sit in the review queue where they're one skim away from being missed.
**Recommendations:**
1. Add a negative filter on the VIP-sender priority rule: strip `Automatic reply:`, `Accepted:`, `Declined:`, `Canceled:`/`Cancelled:`, and `Tentative:` subject prefixes from priority consideration regardless of sender — these are calendar/OOO system artifacts, not judgment calls a VIP made.
2. Add positive priority signals independent of sender identity: invoice/financial-document keywords (`invoice`, `payment due`, `INV-`), active-deal-document language (attached SOW/MSA, "documents for," "signed copy of"), and HR-lifecycle keywords (`termination`, `last day of work`) — these should escalate priority even from a non-executive sender.
3. Treat personal farewell/thank-you notes from departing staff as a distinct light-touch category — not automatically `1_priority`, but flag rather than silently review-queue, since these are one-time, time-sensitive, personally addressed to Trevor.

### Theme E — HR/personnel-adjacent content from non-HR senders isn't flagged sensitive
**Evidence:** Overlaps Theme D's under-escalation examples plus **"Staff Update - Nick Bartelli"** and **"Notice of Staff Open Position: Applications Systems Administrator"**, both routed `7_toBeFiled → 2_review` mismatches (Theme F bucket) rather than being caught by the `sensitive`/`protected_contact` flag at all. A likely fourth instance: the original (now-superseded) message from Aril Brizendine requesting the Applications Systems Administrator posting — Trevor confirmed that message "would have qualified for review" (see §1, not-found case 3) — reinforcing that staffing/hiring requests from a non-HR sender (Aril is Director, Technology Operations) aren't being caught.
**Root cause:** The sensitivity/protected-contact classifier appears to key off known HR sender addresses or explicit personnel-system domains (e.g. `no-reply@rippling.com` termination workflows are presumably already tagged). It doesn't catch personnel-adjacent content forwarded or announced by a *general employee* (e.g. `bmartin@thesignatry.com` announcing a colleague's departure) rather than an HR-system sender.
**Recommendation:**
1. Add content-based sensitivity keywords (`accepted an invitation to pursue`, `last day at The Signatry`, `Notice of Staff Open Position`, `bittersweet`) that fire the sensitive/protected-contact flag regardless of sender, not just sender-domain-based detection.

### Theme F — Recurring "Action Required" boilerplate over-triggers urgency without time-decay
**Evidence:** Largest chunk of the 11 `2_review → 7_toBeFiled` mismatches: repeated **Rippling** "Action required: You have pending tasks," "A new task was recently assigned," "Excess hours run" notices; repeated **SolCyber** ticket-status pings on the same ticket number; **"A reminder for our upcoming meeting"** (x2, for meetings that had already occurred by the time Trevor filed).
**Root cause:** The urgent-keyword matcher fires on boilerplate phrasing ("Action required," "reminder") from known recurring/automated systems without any signal for whether the underlying task is still open, already resolved, or simply a template the system reuses regardless of real urgency. Trevor — who has out-of-band knowledge that these are routine or already handled — just files them without review.
**Recommendations:**
1. For known recurring-notification senders (Rippling, SolCyber, HubSpot meeting-reminder bot), either lower their default urgency weight or require a second, more specific signal (a dollar amount, a named overdue item, a ticket status change to "escalated") before routing to review instead of filing.
2. For meeting-reminder emails specifically, compare the reminder's referenced meeting time against the message's own received time — a reminder for a meeting time already in the past by the time it's processed is stale and safe to file without review.

### Theme G — No detection for signed contracts/active deal documents
**Evidence:** 4 of the 26 high-severity misses: **"Signed copy of 'SOW 10287...'"**, **"Re: The Signatry [6817] debrief with BCW Cary Humphries"**, **"Re: The Signatry- Documents for GE100 Offering"** (x2).
**Root cause:** Same gap named in Theme D's recommendation #2, called out separately because it's a clean, easy-to-target signal on its own: no keyword rule currently exists for signed/executed contract language or active-deal document threads.
**Recommendation:** (see Theme D, rec. #2 — implement as its own rule: `signed copy of`, `SOW`, `MSA`, `debrief`, `documents for [offering/engagement]` → priority, independent of sender.)

### Theme H — The `4_autorespond` folder name reads as "put declines here" to a human, contrary to its system-internal design
**Evidence:** All 9 messages found in `4_autorespond` this session are real decline-candidate cold pitches Trevor manually sorted there — none are transient system retry-state artifacts. Meanwhile `5_draftsToReview`, the folder SKILL.md actually designates for human-reviewable decline drafts, was completely empty.
**Root cause:** (identified earlier this session, restated here since Stage 2 data confirms it definitively) `4_autorespond`'s literal name — "auto respond" — reads to a human filing by hand as "things that should get an automatic reply," i.e. a decline bucket, which is a reasonable plain-English reading even though the skill's internal design treats it as a transient, always-empty retry state that should never hold resting mail.
**Recommendations:**
1. Rename `4_autorespond` to something that doesn't invite hand-filing, e.g. `4_systemRetry` or `_4_autorespond_internal`, and/or add a leading underscore or bracket convention that visually signals "not a human destination" the way `_claude` itself does at the root.
2. Since Trevor is already using this folder as his personal decline bucket in practice, consider formally repurposing it (or `5_draftsToReview`) to match his actual behavior instead of fighting it — e.g., let `4_autorespond`/renamed-equivalent be the folder that holds *sent* declines for a record, while `5_draftsToReview` holds *pending* ones, with a clear naming distinction between the two states.

### Theme I — Stage-1 dry-run artifact: decline drafts never existed
**Evidence:** 3 mismatches rooted at `5_draftsToReview → {4_autorespond, 7_toBeFiled, 6_bulkToReview}`.
**Root cause:** Stage 1 was a read-only dry run — no actual decline drafts were created, so the messages the plan tagged as decline-candidates never appeared in `5_draftsToReview` as an actual draft for Trevor to review. He instead filed the underlying source email wherever seemed reasonable. This is not a skill misjudgment; it's a byproduct of the two-stage test design and should be excluded from any accuracy figure that's meant to represent live-run performance.
**Recommendation:** None needed against the skill itself — note this caveat in any future accuracy re-test so dry-run artifacts aren't miscounted as real classification failures.

### Theme J — Delegation is an inherently human, relationship-specific judgment call
**Evidence:** 3 `2_review → 3_delegate` mismatches: **"Re: Rippling AI follow up"**, and the two **"Legacy Rising"** messages.
**Root cause:** Deciding to hand a thread to someone else depends on who Trevor delegates specific relationships/topics to — information the skill has no access to today.
**Recommendation:** If this keeps recurring, consider a small, maintained delegate-mapping list (sender or topic → delegate name) that Trevor curates directly, rather than trying to infer delegation from message content.

---

## 3. Full per-message mismatch data

The complete 281-row comparison (`id`, `subject`, `sender`, `script_bucket_hint`, `planned_target_folder`, `actual_folder`, `status`, `stage1_reason`) is saved alongside this report at `state/stage2_comparison.json` for reference or further filtering.
