# Support QA report: design decisions

Recorded so the next person doesn't relitigate them. `scripts/support_qa.py` reads the top-level bullets below into the report's "Design notes" panel, so keep each decision as one `- **Title.** body` bullet (nested bullets fold into their parent).

- **Shared visual system.** Same as the Product QA report: bands, hairlines, Lora and Mulish embedded as base64, dd MMM yyyy dates, one QA cell showing only failing glyphs, ledger and owner filters, and print rules. Both reports inline the shared stylesheet assets/qa_base.css.
- **Chart.** An aging strip, not a target-date runway. Support tickets have no planned target, and how long it has been since anyone touched a ticket is the stuck signal. Tickets are bucketed by days since last update; the stale line and wash mark where slow becomes stuck.
- **Dot colors encode whose move it is.** Dawn is us, Legacy is the customer, and grey is Pending with linked work. Jubilee is Pending with no linked work, which is the internal-rule violation.
- **Glyph meanings.**
  - Hourglass: stalled on us (the only risk-colored glyph, in Jubilee).
  - Envelope: customer gone quiet.
  - Speech bubble with "!": no customer update in 30 days.
  - Broken link: pending with no link, the same meaning as in the Product report.
  - Pause: pending with no reason.
  - Boxed P: linked work is parked.
  - Light bulb: enhancement not routed.
  - Calendar with "!": past due.
  - Check: ready to resolve, in Legacy.
- **Verdict.** Each ticket lands in exactly one section, the first matching verdict in config order. The healthy section is collapsed by default and opens automatically while a filter is active.
- **Why "No customer update in 30 days" and not the Timely Updates SLA.** The owner chose the relabel on 24 Oct 2026. The check is computed from the newest comment by a team member, because the Timely Updates SLA measures time in Pending: on SUP-1107 its cycle started when the ticket entered Pending, ran through six comments, and stopped only when the status changed.
- **Why time to resolution isn't a check.** It is saturated (breached on most open tickets) and pauses during Pending, so a ticket parked for months never trips it.
- **Width decisions.** The page is 1360px wide and Summary absorbs the remaining width; every other column is fixed. Measured average row height dropped from 92px to 68px at 1280px. Prose is capped at 780px so it stays readable.
- **Known limits.** Public and internal comments can't be told apart, so an internal note counts as an update. The team roster matches comment authors by display name, because that is all the connector returns. Due dates may be set by automation at intake.
