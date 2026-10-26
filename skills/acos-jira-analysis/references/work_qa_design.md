# Work Boards QA report: design decisions

Recorded so the next person doesn't relitigate them. `scripts/work_qa.py` reads the top-level bullets below into the report's "Design notes" panel, so keep each decision as one `- **Title.** body` bullet (nested bullets fold into their parent).

- **One report, board filters.** A single report across every key in jira_workspaces.work, with a board filter that scopes the headline, chart counts, ledger, owner table, and sections. Per-board views belong in Jira. Every per-board view is precomputed in Python; the page only selects one.
- **Lanes by whose move it is.** Work items need "who's holding this" before "how old is it". Without lanes, vendor-held GE items would read as our stalled work. The lane comes from a per-board vendor status map in config: a vendor status puts an item in the vendor lane, any To Do-category status is backlog, and everything else is our move.
- **Buckets are wider than Support's.** Work moves slower, so the aging strip runs 0–30 through 366+ days. Dots keep their positions when a board filter is active; other boards' dots fade to 12% and leave the tab order.
- **Board colors.** TT Legacy, GE Dawn, DVR Midnight (Ice in dark mode), HSER Heartfelt, IL light grey. A board without its own pair uses board_default.
- **Glyphs.**
  - Checked parent over open child: child of a closed parent.
  - Bulb with check: closed idea.
  - Bolt: empty epic.
  - Hourglass: stalled on us, the only risk-colored glyph, in Jubilee.
  - Open padlock: blocker cleared.
  - Person with plus: started, unassigned.
  - Calendar with "!": past due.
  - Box: vendor release passed.
  - Tag: no vendor ticket ID.
  - Octagon: blocked or on hold.
  - Person with ×: not in directory.
  - Person with arrow: outside Technology.
  - Drawer: backlog rot.
- **Verdict order.** Close the loop, vendor commitments at risk, reassign, blocked, stalled on us, backlog to groom, no issues found. The last two are collapsed until a filter is active.
- **Why vendor staleness isn't a check.** 80 of 88 vendor items exceeded 180 days on the 24 Oct 2026 data, so a follow-up-due check would flag nearly all of them. Release labels and closed ideas are the signal instead; reconciling against the vendor's own ticket export is the recommended future input.
- **Why Slack is the directory.** Jira reported every assignee as active, including four people who had left, and Microsoft 365 people search isn't authorized on this tenant (missing People.Read). If that permission is granted, prefer it and keep Slack as the fallback. Lookups are cached in state/directory_cache.json.
- **Known limits.** Directory matching is by display name. Parent and idea checks ignore the child's own status; nearly all 87 parent-closed items were untouched backlog on the fixture. DVR and HSER have no vendor statuses mapped yet. A day count is clamped at zero when an item was updated after noon today.
