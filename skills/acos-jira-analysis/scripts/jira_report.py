#!/usr/bin/env python3
"""Deterministic engine for acos-jira-analysis.

This skill has no content judgment anywhere in it: every rule below — which
JQL to run, what counts as overdue vs. upcoming, how a row is formatted —
must produce the same answer for the same input every run. Claude's only job
(via SKILL.md) is to call the Atlassian MCP connector's
searchJiraIssuesUsingJql with the JQL this script hands back, then feed the
raw results back in here. No LLM reasoning ever touches the filtering,
counting, or markdown formatting.

Two-stage pipeline, each stage its own subcommand so the pieces stay
separately callable (e.g. by a future acos-orchestration skill importing
build_report()/render_markdown() directly instead of parsing markdown):

  plan     Reads jira_workspaces out of acos-aboutme's profile.json and
            emits the exact JQL + field list for each fetch Claude needs to
            run via searchJiraIssuesUsingJql. Deterministic query-building,
            no Jira access itself — this script never calls Jira directly.
  report   Takes the plan plus the raw issues Claude fetched for each query
            id, computes the structured result (build_report), and either
            prints that structured JSON or renders it to markdown
            (render_markdown) depending on --format.

Field mapping (confirmed against signatry1.atlassian.net 2026-08-10):
  Standard fields (support + work groups): summary, status.name,
    priority.name, duedate (ISO date or null), assignee.displayName
    (falls back to "Unassigned" when null).
  Custom fields (product group only — Jira Product Discovery projects like
    TRM; re-verify these field IDs if `product` ever includes a
    differently-configured project):
    customfield_10149 "Project target" — JSON string {"start":...,"end":
      "YYYY-MM-DD"}; the parsed `end` date is this group's due-date
      equivalent (standard duedate is not populated on these issues).
    customfield_10156 "Product Area" — multi-select; rendered as a
      comma-joined list of each entry's `value`.
  customfield_10139 "Roadmap" is used only in the product-detail JQL filter
    (`"Roadmap" NOT IN ("Done", "Parking Lot")`) — not fetched or rendered,
    since the filtering already happens server-side in JQL.

Known wrinkle: TRM has a workflow *status* literally named "Parking lot",
distinct from the Roadmap *custom field*'s "Parking Lot" value. The JQL
below filters on the Roadmap field specifically (quoted field name) — never
on status name — to avoid conflating the two. Verified live 2026-08-10 that
"Roadmap" NOT IN (...) filters correctly without excluding items whose
*status* happens to also be called "Parking lot".

Unverified, flagged rather than assumed:
  - Whether the product-detail Roadmap exclusion should also exclude
    sub-tasks or other issue types. All TRM data observed so far is the
    "Idea" issue type, so this hasn't mattered in practice; revisit if the
    product group ever includes a project with a mixed issue-type set.
  - Whether IL/HSER/GE/DVR all use standard duedate uniformly the way TT
    does. Spot-checked live 2026-08-10: duedate is populated (if sparsely —
    IL had 3 issues, HSER had 2, against TT's several hundred) across all
    five, so the same query shape works, but a newly added `work` project
    should get the same spot-check before being trusted.

No subcommand here ever calls a Jira MCP tool, creates/edits/transitions an
issue, or writes anything back to acos-aboutme's profile — this script only
ever reads its input files/arguments and prints JSON or markdown to stdout.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_ABOUTME_PATH = "../acos-aboutme/state/profile.json"
DEFAULT_CLOUD_ID = "signatry1.atlassian.net"
DEFAULT_WINDOW_DAYS = 14

GROUP_ORDER = ["product", "support", "work"]
GROUP_LABELS = {"product": "Product", "support": "Support", "work": "Work/Tasks"}


def _fail(message):
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(1)


def load_jira_workspaces(aboutme_path):
    """Read jira_workspaces out of acos-aboutme's profile.json. Raises a
    clear, catchable error rather than a stack trace if the profile doesn't
    exist or hasn't been enrolled with this section yet — this skill has no
    meaningful default project keys to fall back on."""
    path = Path(aboutme_path)
    if not path.exists():
        _fail(
            f"acos-aboutme profile not found at {aboutme_path}. This skill has no "
            "project keys to report on until jira_workspaces is set up there — "
            "ask the person to enroll in acos-aboutme first, or add a "
            "jira_workspaces section to an existing profile."
        )
    try:
        profile = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        _fail(f"acos-aboutme profile at {aboutme_path} is not valid JSON: {e}")

    workspaces = profile.get("jira_workspaces")
    if not workspaces or not any(workspaces.get(g) for g in GROUP_ORDER):
        _fail(
            f"acos-aboutme profile at {aboutme_path} has no jira_workspaces groups "
            "configured (product/support/work). Nothing to report on until at "
            "least one group has a project key."
        )
    return workspaces


def _quote_jql_list(keys):
    return ", ".join(keys)


def build_plan(aboutme_path, cloud_id):
    """Deterministic query builder: given jira_workspaces config, return the
    exact JQL + fields Claude must fetch via searchJiraIssuesUsingJql. Builds
    no more than one query per group, except product, which needs a second,
    differently-scoped query for its team-wide detail list (see mission:
    output 2 is deliberately not assignee-scoped, unlike every other output)."""
    workspaces = load_jira_workspaces(aboutme_path)
    window_days = workspaces.get("upcoming_window_days", DEFAULT_WINDOW_DAYS)
    groups = {g: workspaces.get(g) or [] for g in GROUP_ORDER}

    queries = []

    if groups["product"]:
        keys = _quote_jql_list(groups["product"])
        queries.append({
            "id": "product",
            "group": "product",
            "scope": "assignee",
            "jql": f"assignee = currentUser() AND project in ({keys}) AND statusCategory != Done ORDER BY key ASC",
            "fields": ["customfield_10149"],
            "used_for": ["summary"],
            "description": "Product group, current user's own assignments — feeds the Summary row's overdue/upcoming counts only.",
        })
        queries.append({
            "id": "product_detail",
            "group": "product",
            "scope": "team",
            "jql": (
                f'project in ({keys}) AND statusCategory != Done '
                'AND "Roadmap" NOT IN ("Done", "Parking Lot") ORDER BY key ASC'
            ),
            "fields": ["summary", "customfield_10149", "customfield_10156", "assignee", "status"],
            "used_for": ["product_detail"],
            "description": "Product group, whole team (deliberately NOT assignee-scoped) — feeds the Product detail list.",
        })

    if groups["support"]:
        keys = _quote_jql_list(groups["support"])
        queries.append({
            "id": "support",
            "group": "support",
            "scope": "assignee",
            "jql": f"assignee = currentUser() AND project in ({keys}) AND statusCategory != Done ORDER BY key ASC",
            "fields": ["summary", "status", "priority", "duedate"],
            "used_for": ["summary", "support_detail"],
            "description": "Support group, current user's own assignments — feeds both the Summary row and the Support detail list.",
        })

    if groups["work"]:
        keys = _quote_jql_list(groups["work"])
        queries.append({
            "id": "work",
            "group": "work",
            "scope": "assignee",
            "jql": f"assignee = currentUser() AND project in ({keys}) AND statusCategory != Done ORDER BY key ASC",
            "fields": ["summary", "status", "priority", "duedate"],
            "used_for": ["summary", "work_detail"],
            "description": "Work group (all configured project keys), current user's own assignments — feeds both the Summary row and the Work/Tasks detail list.",
        })

    return {
        "cloud_id": cloud_id,
        "window_days": window_days,
        "groups": groups,
        "queries": queries,
    }


def _parse_project_target_end(raw):
    """Extract the 'end' date from Project target JSON:
    '{"start":"...","end":"YYYY-MM-DD"}'. Returns None for absent, null, or
    malformed values rather than raising — a malformed custom field is data
    to skip, not a reason to crash the whole report."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed.get("end")


def _bucket(due_date_str, today, window_end):
    """Returns 'overdue', 'upcoming', or None (not in window / no date)."""
    if not due_date_str:
        return None
    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    if due < today:
        return "overdue"
    if due <= window_end:
        return "upcoming"
    return None


def _display_name(assignee_field):
    if not assignee_field:
        return "Unassigned"
    return assignee_field.get("displayName") or "Unassigned"


def _product_area_str(product_area_field):
    if not product_area_field:
        return ""
    return ", ".join(entry.get("value", "") for entry in product_area_field if entry.get("value"))


def _group_label(group, keys):
    return f"{GROUP_LABELS[group]} ({', '.join(keys)})"


def build_report(plan, raw, today=None):
    """Structured, JSON-serializable result — the intermediate step a future
    acos-orchestration skill can consume directly without parsing markdown.
    `raw` maps each plan query id to the list of issue nodes Claude fetched
    for it (each node the same shape searchJiraIssuesUsingJql returns:
    key, webUrl, fields)."""
    today = today or date.today()
    window_days = plan["window_days"]
    window_end = today + timedelta(days=window_days)
    groups = plan["groups"]

    summary = []
    product_detail = []
    support_detail = []
    work_detail = []

    if groups.get("product"):
        overdue = upcoming = 0
        for issue in raw.get("product", []):
            due = _parse_project_target_end(issue.get("fields", {}).get("customfield_10149"))
            bucket = _bucket(due, today, window_end)
            if bucket == "overdue":
                overdue += 1
            elif bucket == "upcoming":
                upcoming += 1
        summary.append({"group": "product", "label": _group_label("product", groups["product"]), "overdue": overdue, "upcoming": upcoming})

        for issue in raw.get("product_detail", []):
            fields = issue.get("fields", {})
            due = _parse_project_target_end(fields.get("customfield_10149"))
            bucket = _bucket(due, today, window_end)
            if bucket is None:
                continue
            product_detail.append({
                "key": issue["key"],
                "url": issue.get("webUrl", ""),
                "summary": fields.get("summary", ""),
                "product_area": _product_area_str(fields.get("customfield_10156")),
                "assignee": _display_name(fields.get("assignee")),
                "target_end": due,
                "status": (fields.get("status") or {}).get("name", ""),
                "bucket": bucket,
            })
        product_detail.sort(key=lambda r: r["target_end"])

    if groups.get("support"):
        overdue = upcoming = 0
        for issue in raw.get("support", []):
            fields = issue.get("fields", {})
            due = fields.get("duedate")
            bucket = _bucket(due, today, window_end)
            if bucket == "overdue":
                overdue += 1
            elif bucket == "upcoming":
                upcoming += 1
            if bucket is not None:
                support_detail.append({
                    "key": issue["key"],
                    "url": issue.get("webUrl", ""),
                    "summary": fields.get("summary", ""),
                    "status": (fields.get("status") or {}).get("name", ""),
                    "priority": (fields.get("priority") or {}).get("name", ""),
                    "due": due,
                    "bucket": bucket,
                })
        summary.append({"group": "support", "label": _group_label("support", groups["support"]), "overdue": overdue, "upcoming": upcoming})
        support_detail.sort(key=lambda r: r["due"])

    if groups.get("work"):
        overdue = upcoming = 0
        for issue in raw.get("work", []):
            fields = issue.get("fields", {})
            due = fields.get("duedate")
            bucket = _bucket(due, today, window_end)
            if bucket == "overdue":
                overdue += 1
            elif bucket == "upcoming":
                upcoming += 1
            if bucket is not None:
                work_detail.append({
                    "key": issue["key"],
                    "url": issue.get("webUrl", ""),
                    "summary": fields.get("summary", ""),
                    "status": (fields.get("status") or {}).get("name", ""),
                    "priority": (fields.get("priority") or {}).get("name", ""),
                    "due": due,
                    "bucket": bucket,
                })
        summary.append({"group": "work", "label": _group_label("work", groups["work"]), "overdue": overdue, "upcoming": upcoming})
        work_detail.sort(key=lambda r: r["due"])

    return {
        "generated_date": today.isoformat(),
        "window_days": window_days,
        "summary": summary,
        "product_detail": product_detail,
        "support_detail": support_detail,
        "work_detail": work_detail,
    }


def _md_table(headers, rows):
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def _escape(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _render_detail_section(title, rows, headers, row_fn):
    overdue_rows = [r for r in rows if r["bucket"] == "overdue"]
    upcoming_rows = [r for r in rows if r["bucket"] == "upcoming"]
    out = [f"## {title}\n"]
    out.append("**Overdue**\n")
    out.append(_md_table(headers, [row_fn(r) for r in overdue_rows]))
    out.append("\n**Upcoming**\n")
    out.append(_md_table(headers, [row_fn(r) for r in upcoming_rows]))
    return "\n".join(out)


def render_markdown(report):
    parts = [f"# Jira Report — {report['generated_date']}\n"]

    parts.append(f"## Summary — my assigned items (overdue / upcoming within {report['window_days']} days)\n")
    summary_rows = [
        [_escape(r["label"]), str(r["overdue"]), str(r["upcoming"])]
        for r in report["summary"]
    ]
    parts.append(_md_table(["Workspace", "Overdue", "Upcoming"], summary_rows))

    if report["product_detail"] or any(r["group"] == "product" for r in report["summary"]):
        parts.append("")
        parts.append(_render_detail_section(
            "Product Roadmap — whole team",
            report["product_detail"],
            ["Key", "Summary", "Product Area", "Assignee", "Target End", "Status"],
            lambda r: [
                f"[{r['key']}]({r['url']})", _escape(r["summary"]), _escape(r["product_area"]),
                _escape(r["assignee"]), r["target_end"], _escape(r["status"]),
            ],
        ))

    if report["support_detail"] or any(r["group"] == "support" for r in report["summary"]):
        parts.append("")
        parts.append(_render_detail_section(
            "Support — my assignments",
            report["support_detail"],
            ["Key", "Summary", "Status", "Priority", "Due"],
            lambda r: [
                f"[{r['key']}]({r['url']})", _escape(r["summary"]), _escape(r["status"]),
                _escape(r["priority"]), r["due"],
            ],
        ))

    if report["work_detail"] or any(r["group"] == "work" for r in report["summary"]):
        parts.append("")
        parts.append(_render_detail_section(
            "Work/Tasks — my assignments",
            report["work_detail"],
            ["Key", "Summary", "Status", "Priority", "Due"],
            lambda r: [
                f"[{r['key']}]({r['url']})", _escape(r["summary"]), _escape(r["status"]),
                _escape(r["priority"]), r["due"],
            ],
        ))

    return "\n".join(parts) + "\n"


def cmd_plan(args):
    plan = build_plan(args.aboutme, args.cloud_id)
    print(json.dumps(plan, indent=2))


def cmd_report(args):
    plan = json.loads(Path(args.plan).read_text())
    raw = json.loads(Path(args.raw).read_text())
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else None
    report = build_report(plan, raw, today=today)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))


def main():
    parser = argparse.ArgumentParser(description="Deterministic engine for acos-jira-analysis.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Emit the JQL + fields Claude must fetch via searchJiraIssuesUsingJql.")
    p_plan.add_argument("--aboutme", default=DEFAULT_ABOUTME_PATH, help="Path to acos-aboutme's state/profile.json")
    p_plan.add_argument("--cloud-id", default=DEFAULT_CLOUD_ID)
    p_plan.set_defaults(func=cmd_plan)

    p_report = sub.add_parser("report", help="Compute the structured report from fetched issues and render it.")
    p_report.add_argument("--plan", required=True, help="Path to the JSON emitted by the plan subcommand")
    p_report.add_argument("--raw", required=True, help="Path to JSON mapping each plan query id to its fetched issue nodes")
    p_report.add_argument("--today", help="Override today's date, YYYY-MM-DD (for testing only)")
    p_report.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
