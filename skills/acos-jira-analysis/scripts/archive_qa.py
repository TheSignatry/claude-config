#!/usr/bin/env python3
"""Archive QA report for acos-jira-analysis.

Reviews every archived idea in the owner's `product` workspace group and
answers one question per idea: does it rest in a concluding state? Archiving
hides an idea in Jira Product Discovery but leaves its Roadmap value and
workflow status untouched, so an idea archived from "Now" or "In Progress"
still reads as live work to anything that queries those fields. Pure functions
only: jira_report.py owns the CLI and calls build_archive_plan() /
build_archive_report() / render_*() here.

What counts as concluding is config (jira_workspaces.archive_qa), so the same
plan + raw + today always produce the same payload.
"""
import re

from qa_common import (
    SKILL_DIR, QAError, aggregate_owners, display_value, fmt_date, join, key_sort,
    load_design_spec, md_cell, normalize_issues, render_page, validate_check_ids,
)

TEMPLATE_PATH = SKILL_DIR / "assets" / "archive_qa_template.html"
DESIGN_PATH = SKILL_DIR / "references" / "archive_qa_design.md"
LEDGER_MAX_COLS = 4
ROLES = {"ink", "risk", "good"}
CHECK_TYPES = {"roadmap_not_concluding", "status_not_concluding"}
CUSTOMFIELD_RE = re.compile(r"^customfield_(\d+)$")
# Fixed sections: which concluding fields an idea is still missing.
SECTIONS = [
    ("both", "Neither concluded", "Roadmap and status both still read as live work."),
    ("roadmap", "Needs a Roadmap value", "The status is closed, but the Roadmap value is empty or still active."),
    ("status", "Needs the status closed", "The Roadmap value is concluded, but the workflow status was never closed."),
    ("clear", "Concluded", "Roadmap and status both rest in a concluding state. Nothing to do."),
]


# --- config -----------------------------------------------------------------

def validate_archive_config(aq):
    if not isinstance(aq, dict) or not aq.get("checks"):
        raise QAError("jira_workspaces.archive_qa is missing or has no checks configured.")
    for key in ("concluding_roadmap", "concluding_status_categories"):
        vals = aq.get(key)
        if not isinstance(vals, list) or not vals or not all(isinstance(v, str) and v for v in vals):
            raise QAError(f"archive_qa.{key} must be a non-empty list of strings.")
    validate_check_ids("archive_qa", aq["checks"])
    enabled = []
    for c in aq["checks"]:
        if c.get("type") not in CHECK_TYPES:
            raise QAError(f"archive_qa check {c['id']!r} has unknown type {c.get('type')!r}.")
        if c.get("color_role", "ink") not in ROLES:
            raise QAError(f"archive_qa check {c['id']!r} has color_role {c.get('color_role')!r}; use ink, risk, or good.")
        if c.get("enabled", True):
            enabled.append(c)
    if not enabled:
        raise QAError("archive_qa has no enabled checks.")
    return enabled


def _rule_text(c, aq):
    """A rule may say {values}; fill it from the list its check reads, so the
    page can't drift from the config."""
    vals = aq["concluding_roadmap"] if c["type"] == "roadmap_not_concluding" else aq["concluding_status_categories"]
    shown = [v.capitalize() if c["type"] == "status_not_concluding" else v for v in vals]
    return c["rule"].replace("{values}", _join_or(shown))


def _join_or(items):
    if len(items) <= 2:
        return " or ".join(items)
    return ", ".join(items[:-1]) + ", or " + items[-1]


# --- plan -------------------------------------------------------------------

def build_archive_plan(workspaces, pf, cloud_id):
    keys = workspaces.get("product") or []
    if not keys:
        raise QAError("jira_workspaces.product has no project keys; the Archive QA report has nothing to review.")
    aq = workspaces.get("archive_qa")
    if not aq:
        raise QAError("jira_workspaces.archive_qa is not configured in acos-aboutme (profile or defaults).")
    palette = (workspaces.get("product_qa") or {}).get("palette")
    if not palette:
        raise QAError("jira_workspaces.product_qa.palette is missing; the Archive QA report shares its color tokens.")
    validate_archive_config(aq)
    for k in ("roadmap", "idea_archived", "project_target"):
        if not isinstance(pf.get(k), str):
            raise QAError(f"product_fields.{k} is not set; the Archive QA report needs it.")
    m = CUSTOMFIELD_RE.match(pf["idea_archived"])
    if not m:
        raise QAError(f"product_fields.idea_archived {pf['idea_archived']!r} is not a customfield_N id, so it can't be queried.")
    return {
        "report": "archive_qa",
        "cloud_id": cloud_id,
        "site": f"https://{cloud_id}/browse/",
        "product_keys": keys,
        "product_fields": pf,
        "archive_qa": aq,
        "palette": palette,
        "queries": [{
            "id": "archive_qa",
            "jql": f"project in ({', '.join(keys)}) AND cf[{m.group(1)}] is not EMPTY ORDER BY key ASC",
            "fields": ["summary", "status", "assignee", "updated", pf["roadmap"], pf["project_target"], pf["idea_archived"]],
            "description": "Every archived idea in the product group, whatever its Roadmap value or status.",
        }],
    }


# --- report -----------------------------------------------------------------

def _target_text(raw):
    """Project target is a JSON string {"start": ..., "end": ...}; show the end."""
    if not raw:
        return ""
    m = re.search(r'"end"\s*:\s*"(\d{4}-\d{2}-\d{2})"', raw if isinstance(raw, str) else "")
    return fmt_date(m.group(1)) if m else ""


def parse_idea(issue, pf, aq):
    f = issue.get("fields") or {}
    status = f.get("status") or {}
    roadmap = display_value(f.get(pf["roadmap"]))
    cat = (status.get("statusCategory") or {}).get("key") or ""
    cat_name = (status.get("statusCategory") or {}).get("name") or cat
    updated = (f.get("updated") or "")[:10]
    return {
        "key": issue["key"],
        "url": issue.get("webUrl") or "",
        "summary": f.get("summary") or "",
        "assignee": display_value(f.get("assignee")) or "Unassigned",
        "roadmap": roadmap or "",
        "status": status.get("name") or "",
        "statusCategory": cat_name,
        "target": _target_text(f.get(pf["project_target"])),
        "updated": fmt_date(updated) if updated else "",
        "roadmapOpen": roadmap not in aq["concluding_roadmap"],
        "statusOpen": cat not in aq["concluding_status_categories"],
        "archived": display_value(f.get(pf["idea_archived"])) is not None,
    }


def _section(i):
    if i["roadmapOpen"] and i["statusOpen"]:
        return "both"
    return "roadmap" if i["roadmapOpen"] else "status" if i["statusOpen"] else "clear"


def build_archive_report(plan, raw, today):
    pf, aq = plan["product_fields"], plan["archive_qa"]
    enabled = validate_archive_config(aq)
    # The JQL already asks for archived ideas; the Python check keeps a stray
    # unarchived row (an agenda-style key query, a hand-built raw file) out.
    ideas = [i for i in (parse_idea(x, pf, aq) for x in normalize_issues(raw.get("archive_qa"))) if i["archived"]]
    ideas.sort(key=lambda i: key_sort(i["key"]))

    # A disabled check can't flag an idea or move it out of Concluded.
    on = {c["type"] for c in enabled}
    for i in ideas:
        i["roadmapOpen"] = i["roadmapOpen"] and "roadmap_not_concluding" in on
        i["statusOpen"] = i["statusOpen"] and "status_not_concluding" in on
        i["section"] = _section(i)
        i["qa"], i["qaTips"] = {}, {}

    checks = []
    for c in enabled:
        flag = "roadmapOpen" if c["type"] == "roadmap_not_concluding" else "statusOpen"
        for i in ideas:
            i["qa"][c["id"]] = i[flag]
            if i[flag]:
                i["qaTips"][c["id"]] = ((f"Roadmap is {i['roadmap']}" if i["roadmap"] else "Roadmap is empty")
                                        if flag == "roadmapOpen" else f"Status is {i['status']} ({i['statusCategory']})")
        checks.append({"id": c["id"], "name": c["name"], "rule": _rule_text(c, aq), "role": c.get("color_role", "ink"),
                       "count": sum(1 for i in ideas if i[flag])})

    n = len(ideas)
    by = {s: sum(1 for i in ideas if i["section"] == s) for s, _, _ in SECTIONS}
    flagged = n - by["clear"]
    keys_text = ", ".join(plan["product_keys"])
    if not n:
        headline, subhead = "No archived ideas found.", ""
    elif not flagged:
        headline = f"All {n} archived ideas rest in a concluding state."
        subhead = ""
    else:
        headline = (f"{flagged} of {n} archived ideas still read as live work." if flagged > 1
                    else f"1 of {n} archived ideas still reads as live work.")
        parts = []
        if by["both"]:
            parts.append(f"{by['both']} {'has' if by['both'] == 1 else 'have'} neither a concluding Roadmap value nor a closed status")
        if by["roadmap"]:
            parts.append(f"{by['roadmap']} only need{'s' if by['roadmap'] == 1 else ''} the Roadmap value set")
        if by["status"]:
            parts.append(f"{by['status']} only need{'s' if by['status'] == 1 else ''} the status closed")
        subhead = join(parts) + "."
    date_text = fmt_date(today.isoformat())
    owners = aggregate_owners(ideas, {
        "archived": len,
        "flagged": lambda a: sum(1 for i in a if i["section"] != "clear"),
        **{c["id"]: (lambda cid: lambda a: sum(1 for i in a if i["qa"].get(cid)))(c["id"]) for c in checks},
    })
    return {
        "generated": today.isoformat(),
        "site": plan["site"],
        "title": f"Archive QA ({keys_text}), {date_text}",
        "eyebrow": f"Archived roadmap ideas ({keys_text}), {date_text}",
        "headline": headline,
        "subhead": subhead,
        "concludingText": (f"Concluding Roadmap values: {join(aq['concluding_roadmap'])}. "
                           f"Concluding status: any status in the {join([v.capitalize() for v in aq['concluding_status_categories']])} category."),
        "sourceLine": (f"Source: Jira Product Discovery project {keys_text} on {plan['cloud_id']}, read {date_text}. "
                       "Read-only; nothing in Jira was changed."),
        "checks": checks,
        "ownerColumns": [["archived", "Archived"], ["flagged", "Needs a concluding state"]] + [[c["id"], c["name"]] for c in checks],
        "owners": owners,
        "sections": [{"id": s, "title": t, "cap": cap, "collapsed": s == "clear"} for s, t, cap in SECTIONS],
        "items": ideas,
        "counts": {"archived": n, "flagged": flagged, **by},
        "spec": load_design_spec(DESIGN_PATH),
    }


# --- render -----------------------------------------------------------------

def render_html(payload, plan, fonts_dir=None, template_path=TEMPLATE_PATH):
    enabled = [c for c in plan["archive_qa"]["checks"] if c.get("enabled", True)]
    return render_page(template_path, payload, plan["palette"], enabled, LEDGER_MAX_COLS, fonts_dir, single_row=True)


def render_markdown(payload):
    names = {c["id"]: c["name"] for c in payload["checks"]}
    out = [f"# {payload['title']}", "", f"**{payload['headline']}** {payload['subhead']}".rstrip(), "",
           payload["concludingText"], "", "| Check | Failing |", "|---|---|"]
    out += [f"| {c['name']} | {c['count']} of {payload['counts']['archived']} |" for c in payload["checks"]]
    for sec in payload["sections"]:
        rows = [i for i in payload["items"] if i["section"] == sec["id"]]
        if not rows:
            continue
        out += ["", f"## {sec['title']} ({len(rows)})", "", sec["cap"], "",
                "| ID | Summary | Roadmap | Status | Assignee | Target | Last update | QA |",
                "|---|---|---|---|---|---|---|---|"]
        for i in rows:
            qa = ", ".join(names[c] for c in names if i["qa"].get(c)) or "Clear"
            out.append(f"| [{i['key']}]({i['url']}) | {md_cell(i['summary'])} | {md_cell(i['roadmap']) or '_empty_'} | "
                       f"{md_cell(i['status'])} | {md_cell(i['assignee'])} | {i['target']} | {i['updated']} | {qa} |")
    return "\n".join(out) + "\n"
