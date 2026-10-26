# Personal Focus dashboard: design decisions

Recorded so the next person doesn't relitigate them. `scripts/focus.py` reads the top-level bullets below into the dashboard's "How this is built" panel, so keep each decision as one `- **Title.** body` bullet (nested bullets fold into their parent). The score weights in that panel are generated from `jira_workspaces.focus.score`, not written here.

- **Personal, not team.** Only items assigned to the profile owner, across every key in the product, support, and work groups. Team views are the Product, Support, and Work Boards QA reports. The owner's identity comes from the profile and is checked against the connector: if Jira returns an item assigned to anyone else, the run stops and renders nothing.
- **Whose move first, then urgency.** The lesson from the Work Boards report. Every item is sorted into your move, waiting on someone else, or parked before anything is scored, using the per-workspace lane rules in focus.lanes and the vendor statuses in work_qa.vendors.
- **"Someone's waiting on you" is the new signal.** The newest comment's author is checked against the Technology roster; a requester speaking last on your move means someone is waiting. Only each comment's author and date are used; comment text is never read or shown.
- **The ranking is a published formula.** Every weight is in focus.score so the owner can audit and tune it through acos-aboutme. Claude never reorders the list or adds commentary to it.
- **Timeline.** A window of focus.timeline_months months from the first of the current month, one row per workspace, every dot labeled with its key because personal volumes are small. Rows are assigned greedily so labels never overlap. Earlier and Later gutters hold dates outside the window; month-range targets are bars. Fill is whose move it is; a Jubilee ring means the date has passed; the shaded band is the next seven days.
- **Colors.**
  - Lanes: Dusk for your move (Dawn in dark mode), Legacy for waiting (Glacier in dark mode), light grey for parked.
  - Workspace dots: Legacy for product, Dawn for support, Midnight for work (Ice in dark mode).
- **Borrowed rules.** Roadmap data gaps run the Product report's own checks; "no update in 30 days" is the Support rule; parked-and-untouched mirrors backlog rot; vendor lanes come from the Work Boards report. Same visual system, dates, and print rules.
