#!/usr/bin/env python3
"""Support QA report for acos-jira-analysis.

Reviews every open ticket in the owner's `support` workspace group, team-wide,
and answers one question per ticket: is it stuck? It also enforces the
internal rule that an enhancement delivered on another board is put in
Pending and linked to the delivery ticket. Pure functions only: jira_report.py
owns the CLI and calls build_support_plan() / build_support_report() /
render_*() here.

Every check, verdict, and diagnostic is an explicit rule driven by
jira_workspaces.support_qa, so the same plan + raw + today always produce the
same payload. Comment bodies are never read: only each comment's `created`
timestamp and author display name are used.
"""
import re
from datetime import date, datetime, timedelta

from qa_common import (
    SKILL_DIR, QAError, aggregate_owners, cap, display_value, fmt_date, join, key_sort,
    load_design_spec, local_date, md_cell, normalize_issues, num_word, parse_ts, render_page,
    resolve_tz as _tz, validate_buckets, validate_check_ids, validate_palette, whole_days,
)

TEMPLATE_PATH = SKILL_DIR / "assets" / "support_qa_template.html"
DESIGN_PATH = SKILL_DIR / "references" / "support_qa_design.md"
LEDGER_MAX_COLS = 5
ROLES = {"ink", "risk", "good"}
STATUS_GROUPS = ("waiting_on_us", "waiting_on_customer", "pending")
SORTS = {
    "upd_days_desc": "updDays",
    "in_status_days_desc": "inStatusDays",
    "age_days_desc": "ageDays",
}
CHECK_TYPES = {
    "stale_on_us", "customer_quiet", "no_team_comment", "pending_no_link", "pending_empty_field",
    "linked_unscheduled", "enhancement_not_routed", "due_before_today", "linked_all_done",
}
# Owner-table columns that count a check, keyed by check type so a renamed id still works.
OWNER_COLUMNS = [("stale_on_us", "Stalled on us"), ("customer_quiet", "Customer quiet"),
                 ("pending_no_link", "Pending, no link")]
DOT_ORDER = {"unlinked": 0, "us": 1, "customer": 2, "linked": 3}


# --- config -----------------------------------------------------------------

def validate_support_config(sq, sf, palette):
    if not isinstance(sq, dict) or not sq.get("checks"):
        raise QAError("jira_workspaces.support_qa is missing or has no checks configured.")
    for key in ("stale_days", "customer_quiet_days", "customer_update_days", "enhancement_grace_days", "month_untouched_days"):
        if not isinstance(sq.get(key), int) or sq[key] < 0:
            raise QAError(f"support_qa.{key} must be a non-negative integer.")
    groups = sq.get("status_names") or {}
    for g in STATUS_GROUPS:
        if not isinstance(groups.get(g), list):
            raise QAError(f"support_qa.status_names.{g} must be a list of status names.")
    if sq.get("delivery_link_scope", "any_non_support") != "any_non_support":
        raise QAError(f"support_qa.delivery_link_scope {sq.get('delivery_link_scope')!r} is not supported; use 'any_non_support'.")
    validate_buckets("support_qa", sq.get("aging_buckets"))

    validate_check_ids("support_qa", sq["checks"])
    ids = set()
    enabled = []
    for c in sq["checks"]:
        cid, ctype = c["id"], c.get("type")
        ids.add(cid)
        if ctype not in CHECK_TYPES:
            raise QAError(f"support_qa check {cid!r} has unknown type {ctype!r}.")
        if ctype == "pending_empty_field" and not isinstance(sf.get(c.get("field")), str):
            raise QAError(f"support_qa check {cid!r} references unknown field key {c.get('field')!r} (not in support_fields).")
        if c.get("color_role", "ink") not in ROLES:
            raise QAError(f"support_qa check {cid!r} has color_role {c.get('color_role')!r}; use ink, risk, or good.")
        if c.get("enabled", True):
            enabled.append(c)
    if not enabled:
        raise QAError("support_qa has no enabled checks.")

    verdicts = sq.get("verdicts") or []
    vids = [v.get("id") for v in verdicts]
    if not verdicts or len(set(vids)) != len(vids) or not all(vids):
        raise QAError("support_qa.verdicts must be a non-empty list with unique ids.")
    if "*" not in verdicts[-1].get("when", []):
        raise QAError("support_qa.verdicts must end with a fallback verdict whose when is ['*'].")
    for v in verdicts:
        if v.get("sort", "upd_days_desc") not in SORTS:
            raise QAError(f"support_qa verdict {v['id']!r} has unknown sort {v.get('sort')!r}.")
        for tok in v.get("when") or []:
            if tok == "*":
                continue
            cid, _, grp = tok.partition("@")
            if cid not in ids:
                raise QAError(f"support_qa verdict {v['id']!r} references unknown check {cid!r}.")
            if grp and grp not in STATUS_GROUPS:
                raise QAError(f"support_qa verdict {v['id']!r} references unknown status group {grp!r}.")
    for s in sq.get("stuck_verdicts") or []:
        if s not in vids:
            raise QAError(f"support_qa.stuck_verdicts names unknown verdict {s!r}.")
    validate_palette("support_qa.palette_extra", sq.get("palette_extra") or {},
                     ["dot_waiting_on_us", "dot_waiting_on_customer", "dot_pending_linked", "dot_pending_unlinked", "stale_line"])
    for k in ("request_type", "time_to_resolution"):
        if not isinstance(sf.get(k), str):
            raise QAError(f"support_fields.{k} is not set; the Support QA report needs it.")
    return enabled


# --- plan -------------------------------------------------------------------

def _roster(profile, sources):
    names = set()
    for group in sources:
        for p in profile.get(group) or []:
            if (p or {}).get("name"):
                names.add(p["name"].strip())
    return sorted(names)


def support_fields_list(sf, enabled):
    keys = ["request_type", "pending_reason", "urgency", "software_affected", "system_data_source", "time_to_resolution"]
    keys += [c["field"] for c in enabled if c.get("field")]
    ids = []
    for k in keys:
        if isinstance(sf.get(k), str) and sf[k] not in ids:
            ids.append(sf[k])
    return ["summary", "status", "assignee", "reporter", "created", "updated", "duedate",
            "statuscategorychangedate", "issuelinks"] + ids


def build_support_plan(workspaces, sf, profile, cloud_id, today):
    keys = workspaces.get("support") or []
    if not keys:
        raise QAError("jira_workspaces.support has no project keys; the Support QA report has nothing to review.")
    sq = workspaces.get("support_qa")
    if not sq:
        raise QAError("jira_workspaces.support_qa is not configured in acos-aboutme (profile or defaults).")
    palette = (workspaces.get("product_qa") or {}).get("palette")
    if not palette:
        raise QAError("jira_workspaces.product_qa.palette is missing; the Support QA report shares its color tokens.")
    enabled = validate_support_config(sq, sf, palette)
    tz_name = (profile.get("owner") or {}).get("timezone") or sq.get("timezone")
    _tz(tz_name)
    kl = ", ".join(keys)
    base = f"project in ({kl}) AND statusCategory != Done"
    # A ticket created on or after this date is under customer_update_days old
    # at noon today, so it can't fail the no-team-comment rule. One day of
    # slack covers the gap between the Jira user's timezone and the owner's.
    cutoff = (today - timedelta(days=sq["customer_update_days"] - 1)).isoformat()
    return {
        "report": "support_qa",
        "cloud_id": cloud_id,
        "site": f"https://{cloud_id}/browse/",
        "support_keys": keys,
        "support_fields": sf,
        "support_qa": sq,
        "palette": {**palette, **{k: v for k, v in (sq.get("palette_extra") or {}).items() if not k.startswith("_")}},
        "roster": _roster(profile, sq.get("team_roster_sources") or []),
        "timezone": tz_name,
        "queries": [
            {"id": "support_qa", "jql": f"{base} ORDER BY created ASC", "fields": support_fields_list(sf, enabled),
             "description": "Every open support ticket, team-wide (deliberately not assignee-scoped)."},
            {"id": "support_qa_comments", "jql": f'{base} AND created <= "{cutoff}" ORDER BY created ASC', "fields": ["comment"],
             "description": "Comments only, kept separate so the main pages stay under the connector's size limit. Newer tickets can't fail the no-team-comment rule, so they're skipped."},
        ],
    }


# --- per-ticket -------------------------------------------------------------

def _links(fields, keys, link_types):
    out, seen = [], set()
    for link in fields.get("issuelinks") or []:
        ltype = (link.get("type") or {}).get("name") or ""
        if link_types and ltype not in link_types:
            continue
        other = link.get("outwardIssue") or link.get("inwardIssue") or {}
        key = other.get("key") or ""
        if not key or key.split("-")[0] in keys or (key, ltype) in seen:
            continue
        seen.add((key, ltype))
        st = (other.get("fields") or {}).get("status") or {}
        out.append({"key": key, "type": ltype, "status": st.get("name", ""),
                    "cat": (st.get("statusCategory") or {}).get("key") or "new"})
    return out


def _group(status, groups):
    for g in STATUS_GROUPS:
        if status in (groups.get(g) or []):
            return g
    return None


def run_checks(t, checks, sq):
    flags, tips = {}, {}
    for c in checks:
        cid, ctype, tip = c["id"], c["type"], c["name"]
        if ctype == "stale_on_us":
            fail = t["group"] == "waiting_on_us" and t["updDays"] >= sq["stale_days"]
            tip = f"{c['name']}: no update in {t['updDays']} days"
        elif ctype == "customer_quiet":
            fail = t["group"] == "waiting_on_customer" and t["inStatusDays"] >= sq["customer_quiet_days"]
            tip = f"{c['name']}: waiting {t['inStatusDays']} days"
        elif ctype == "no_team_comment":
            n = sq["customer_update_days"]
            in_scope = t["status"] in (sq.get("customer_update_statuses") or [])
            if t["teamCommentDays"] is not None:
                fail = in_scope and t["teamCommentDays"] >= n
                tip = f"{c['name']}: last team comment {fmt_date(t['lastTeamComment'])} ({t['teamCommentDays']} days ago)"
            else:
                fail = in_scope and t["ageDays"] >= n
                tip = f"{c['name']}: no team comment since it opened {t['ageDays']} days ago"
        elif ctype == "pending_no_link":
            fail = t["group"] == "pending" and not t["links"]
        elif ctype == "pending_empty_field":
            fail = t["group"] == "pending" and t["fieldValues"].get(c["field"]) is None
        elif ctype == "linked_unscheduled":
            parked = [l for l in t["links"] if l["cat"] == "new"]
            fail = bool(parked)
            tip = f"{c['name']}: " + ", ".join(f"{l['key']} {l['status']}" for l in parked)
        elif ctype == "enhancement_not_routed":
            routed = t["group"] == "pending" and bool(t["links"])
            fail = (t["requestType"] in (sq.get("enhancement_request_types") or [])
                    and t["ageDays"] >= sq["enhancement_grace_days"] and not routed)
        elif ctype == "due_before_today":
            fail = bool(t["due"]) and t["due"] < t["_today"]
            tip = f"{c['name']}: due {fmt_date(t['due'])}"
        else:  # linked_all_done
            fail = bool(t["links"]) and all(l["cat"] == "done" for l in t["links"])
        flags[cid] = bool(fail)
        if fail:
            tips[cid] = tip
    return flags, tips


def pick_verdict(t, verdicts):
    for v in verdicts:
        for tok in v.get("when") or []:
            if tok == "*":
                return v["id"]
            cid, _, grp = tok.partition("@")
            if t["qa"].get(cid) and (not grp or t["group"] == grp):
                return v["id"]
    return verdicts[-1]["id"]


def _dot(t):
    if t["group"] == "pending" and not t["links"]:
        return "unlinked"
    if t["group"] == "waiting_on_us":
        return "us"
    if t["group"] == "waiting_on_customer":
        return "customer"
    return "linked"


def _median(vals):
    a = sorted(vals)
    if not a:
        return 0
    m = len(a) // 2
    return a[m] if len(a) % 2 else int((a[m - 1] + a[m]) / 2 + 0.5)


def _pct(n, d):
    return (100.0 * n / d) if d else 0.0


# --- payload ----------------------------------------------------------------

def build_support_report(plan, raw, today=None):
    today = today or date.today()
    sq, sf, keys = plan["support_qa"], plan["support_fields"], plan["support_keys"]
    checks = validate_support_config(sq, sf, plan.get("palette") or {})
    tz = _tz(plan.get("timezone"))
    now = datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz)
    tiso = today.isoformat()
    link_types = sq.get("delivery_link_types") or []
    groups = sq["status_names"]
    warnings = []

    issues = normalize_issues(raw.get("support_qa"))
    assignees = {display_value((i.get("fields") or {}).get("assignee")) for i in issues} - {None}
    roster = set(plan.get("roster") or [])
    if sq.get("team_roster_include_assignees", True):
        roster |= assignees

    comments = {}
    truncated = []
    for i in normalize_issues(raw.get("support_qa_comments")):
        block = (i.get("fields") or {}).get("comment") or {}
        lst = block.get("comments") if isinstance(block, dict) else block
        lst = lst or []
        # Only created + author are read. Bodies are never touched.
        comments[i["key"]] = [(c.get("created"), display_value((c.get("author") or {}).get("displayName"))) for c in lst]
        if isinstance(block, dict) and isinstance(block.get("total"), int) and block["total"] > len(lst):
            truncated.append(i["key"])
    if truncated:
        warnings.append(f"Comment pages truncated for {', '.join(sorted(truncated, key=key_sort))}; newest-comment logic assumes the connector returns the newest page.")

    items = []
    for issue in issues:
        f = issue.get("fields") or {}
        rt = f.get(sf["request_type"]) or {}
        created, updated = parse_ts(f.get("created"), tz), parse_ts(f.get("updated"), tz)
        sdate = ((rt.get("currentStatus") or {}).get("statusDate") or {})
        since = parse_ts(sdate.get("jira") or sdate.get("iso8601"), tz) or updated
        team = [parse_ts(ts, tz) for ts, who in comments.get(issue["key"], []) if who in roster]
        team = [x for x in team if x]
        last_team = max(team) if team else None
        ttr = f.get(sf["time_to_resolution"]) or {}
        ongoing = ttr.get("ongoingCycle") or {} if isinstance(ttr, dict) else {}
        status = (f.get("status") or {}).get("name") or ""
        t = {
            "key": issue["key"],
            "url": plan["site"] + issue["key"],
            "summary": f.get("summary") or "",
            "status": status,
            "group": _group(status, groups),
            "pendingReason": display_value(f.get(sf.get("pending_reason", ""))),
            "assignee": display_value(f.get("assignee")) or "Unassigned",
            "requestType": display_value((rt.get("requestType") or {}).get("name")) if isinstance(rt, dict) else None,
            "urgency": display_value(f.get(sf.get("urgency", ""))),
            "system": display_value(f.get(sf.get("software_affected", ""))) or display_value(f.get(sf.get("system_data_source", ""))),
            "created": local_date(created, tz),
            "updated": local_date(updated, tz),
            "statusSince": local_date(since, tz),
            "ageDays": whole_days(created, now) or 0,
            "updDays": whole_days(updated, now) or 0,
            "inStatusDays": whole_days(since, now) or 0,
            "due": f.get("duedate") or None,
            "links": _links(f, keys, link_types),
            "ttrBreached": bool(ongoing.get("breached")),
            "ttrPaused": bool(ongoing.get("paused")),
            "lastTeamComment": local_date(last_team, tz),
            "teamCommentDays": whole_days(last_team, now),
            "fieldValues": {c["field"]: display_value(f.get(sf[c["field"]])) for c in checks if c.get("field")},
            "_today": tiso,
        }
        t["qa"], t["qaTips"] = run_checks(t, checks, sq)
        t["verdict"] = pick_verdict(t, sq["verdicts"])
        t["dot"] = _dot(t)
        t["createdText"], t["updatedText"], t["dueText"] = fmt_date(t["created"]), fmt_date(t["updated"]), fmt_date(t["due"])
        del t["_today"], t["fieldValues"]
        items.append(t)

    # Sections, in config order; each sorted by its configured key, oldest first.
    sections = []
    for v in sq["verdicts"]:
        arr = [t for t in items if t["verdict"] == v["id"]]
        field = SORTS[v.get("sort", "upd_days_desc")]
        arr.sort(key=lambda t: (-t[field], key_sort(t["key"])))
        sections.append({"id": v["id"], "title": v["title"], "cap": v.get("cap", ""),
                         "collapsed": bool(v.get("collapsed")), "count": len(arr), "keys": [t["key"] for t in arr]})
    order = {k: n for n, k in enumerate(k for s in sections for k in s["keys"])}
    items.sort(key=lambda t: order[t["key"]])
    for t in items:
        t["hot"] = t["updDays"] >= sq["stale_days"] and t["verdict"] != sq["verdicts"][-1]["id"]

    by_type = {c["type"]: c["id"] for c in checks}
    stuck_ids = set(sq.get("stuck_verdicts") or [])
    owner_cols = {"open": len, "stuck": lambda a: sum(t["verdict"] in stuck_ids for t in a)}
    owner_heads = [["open", "Open"], ["stuck", "Look stuck"]]
    for ctype, label in OWNER_COLUMNS:
        if ctype in by_type:
            cid = by_type[ctype]
            owner_cols[cid] = (lambda c: lambda a: sum(bool(t["qa"].get(c)) for t in a))(cid)
            owner_heads.append([cid, label])
    owner_cols["oldest"] = lambda a: max(t["updDays"] for t in a)
    owners = aggregate_owners(items, owner_cols)

    # Aging chart.
    buckets = []
    for lo, hi in sq["aging_buckets"]:
        arr = [t for t in items if t["updDays"] >= lo and (hi is None or t["updDays"] <= hi)]
        arr.sort(key=lambda t: (DOT_ORDER[t["dot"]], -t["updDays"], key_sort(t["key"])))
        buckets.append({"label": f"{lo}–{hi} days" if hi is not None else f"{lo}+ days", "keys": [t["key"] for t in arr]})
    stale_idx = next(n for n, (lo, hi) in enumerate(sq["aging_buckets"]) if hi is None or lo <= sq["stale_days"] <= hi)

    count = lambda cid: sum(bool(t["qa"].get(cid)) for t in items)  # noqa: E731
    n_open = len(items)
    pending = [t for t in items if t["group"] == "pending"]
    stuck = sum(t["verdict"] in stuck_ids for t in items)
    untouched = sum(t["updDays"] >= sq["month_untouched_days"] for t in items)
    head = f"{cap(num_word(stuck)) if stuck else 'None'} of {n_open} open support tickets look{'s' if stuck == 1 else ''} stuck"
    if untouched:
        head += f", and {num_word(untouched)} {'hasn’t' if untouched == 1 else 'haven’t'} been touched in a month"
    headline = head + "."

    st_n = count(by_type["stale_on_us"]) if "stale_on_us" in by_type else 0
    pl_n = count(by_type["pending_no_link"]) if "pending_no_link" in by_type else 0
    clauses = []
    if st_n:
        clauses.append(f"{st_n} {'is' if st_n == 1 else 'are'} waiting on us with no update in {sq['stale_days']}+ days")
    if pl_n:
        clauses.append(f"{pl_n} of the {len(pending)} pending tickets {'has' if pl_n == 1 else 'have'} no linked delivery ticket, against the rule that parked work is linked")
    sub = (cap(", and ".join(clauses)) + ".") if clauses else ""
    diag = sq.get("diagnostics") or {}
    ttr_n = sum(t["ttrBreached"] for t in items)
    if ttr_n and _pct(ttr_n, n_open) >= diag.get("sla_saturation_pct", 101):
        sub += f" Time to resolution has already breached on {ttr_n} open tickets, so that SLA no longer separates stuck from slow."

    findings = _diagnostics(items, pending, by_type, count, sq, sf, diag, ttr_n, n_open)

    def param(c):
        t = c["type"]
        return {
            "stale_on_us": f"stale_days: {sq['stale_days']}",
            "customer_quiet": f"customer_quiet_days: {sq['customer_quiet_days']}",
            "no_team_comment": f"customer_update_days: {sq['customer_update_days']}; team = profile roster"
                               + (" plus current assignees" if sq.get("team_roster_include_assignees", True) else ""),
            "pending_no_link": "delivery links: " + (", ".join(link_types) if link_types else f"any link to a non-{'/'.join(keys)} issue"),
            "pending_empty_field": f"field: {c.get('field')}",
            "linked_unscheduled": "linked status category: new",
            "enhancement_not_routed": f"enhancement_grace_days: {sq['enhancement_grace_days']}",
            "due_before_today": "field: duedate",
            "linked_all_done": "linked status category: done",
        }[t]

    kl = ", ".join(keys)
    return {
        "generated": tiso,
        "site": plan["site"],
        "supportKeys": keys,
        "title": f"Support QA ({kl}), {fmt_date(tiso)}",
        "eyebrow": f"Support ({kl}) stuck-ticket review, {fmt_date(tiso)}",
        "headline": headline,
        "subhead": sub,
        "staleDays": sq["stale_days"],
        "checks": [{"id": c["id"], "name": c["name"], "rule": c["rule"], "role": c.get("color_role", "ink"),
                    "param": param(c), "count": count(c["id"])} for c in checks],
        "sections": [{k: v for k, v in s.items() if k != "keys"} for s in sections],
        "ownerColumns": owner_heads + [["oldest", "Oldest update"]],
        "owners": owners,
        "aging": {"buckets": buckets, "staleIndex": stale_idx,
                  "staleLabel": f"Stale after {sq['stale_days']} days without an update"},
        "items": items,
        "findings": findings,
        "spec": load_design_spec(DESIGN_PATH),
        "sourceLine": f"Source: Jira Service Management project{'s' if len(keys) > 1 else ''} {kl} on {plan['cloud_id']}, read {fmt_date(tiso)}. Read-only; nothing in Jira was changed.",
        "warnings": warnings,
        "counts": {"open": n_open, "stuck": stuck, **{s["id"]: s["count"] for s in sections}},
    }


def _diagnostics(items, pending, by_type, count, sq, sf, diag, ttr_n, n_open):
    out = []
    if ttr_n and _pct(ttr_n, n_open) >= diag.get("sla_saturation_pct", 101):
        out.append(["Time to resolution is saturated",
                    f"It has breached on {ttr_n} of {n_open} open tickets, and it pauses while a ticket is Pending, so a ticket parked for months never trips it. That’s why it isn’t a QA check here."])
    nu_check = next((c for c in sq["checks"] if c["type"] == "no_team_comment" and c.get("enabled", True)), None)
    if sf.get("timely_updates") and nu_check:
        out.append(["Timely Updates measures time in Pending, not updates",
                    f"Its clock starts when a ticket enters Pending and keeps running through comments, so the report computes “{nu_check['name']}” from the last team comment instead. "
                    f"{count(nu_check['id'])} tickets have gone {sq['customer_update_days']}+ days without one. The connector doesn’t expose whether a comment was public or internal, so an internal note currently counts as an update."])
    if "due_before_today" in by_type:
        with_due = [t for t in items if t["due"]]
        od = count(by_type["due_before_today"])
        if with_due and _pct(od, len(with_due)) >= diag.get("due_date_saturation_pct", 101):
            out.append(["Due dates don’t mean much yet",
                        f"{od} of the {len(with_due)} tickets with a due date are past it. If due dates are set by automation at intake, this check mostly repeats the SLA."])
    if pending:
        pl = sum(1 for t in pending if not t["links"])
        pr_id = next((c["id"] for c in sq["checks"] if c["type"] == "pending_empty_field" and c.get("enabled", True)), None)
        pr = sum(1 for t in pending if pr_id and t["qa"].get(pr_id))
        out.append(["Pending is where tickets go to wait",
                    f"Median time in Pending is {_median([t['inStatusDays'] for t in pending])} days. {pl} of {len(pending)} have no linked work and {pr} have no Pending reason."])
    enh = [t for t in items if t["requestType"] in (sq.get("enhancement_request_types") or [])]
    ok = sum(1 for t in enh if t["group"] == "pending" and t["links"])
    if enh and _pct(ok, len(enh)) < 50:
        out.append(["Enhancements mostly skip the rule",
                    f"{len(enh)} open tickets are enhancement requests; only {ok} {'is' if ok == 1 else 'are'} Pending and linked."])
    types = {}
    for t in items:
        for l in t["links"]:
            types[l["type"]] = types.get(l["type"], 0) + 1
    if len(types) > 1:
        names = [k for k, _ in sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))]
        out.append(["Link types are mixed",
                    f"Links to delivery boards use {len(names)} types ({join(names)}). Standardizing on one would let the report trust the link’s meaning."])
    owners = {}
    for t in items:
        owners[t["assignee"]] = owners.get(t["assignee"], 0) + 1
    if owners:
        name, n = sorted(owners.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if _pct(n, n_open) >= diag.get("owner_concentration_pct", 101):
            st_id = by_type.get("stale_on_us")
            st = sum(1 for t in items if t["assignee"] == name and st_id and t["qa"].get(st_id))
            out.append(["The workload is concentrated",
                        f"{n} of {n_open} open tickets sit with {name}, including {st} stalled on us."])
    return out


# --- rendering --------------------------------------------------------------

def render_html(payload, plan, fonts_dir=None, template_path=TEMPLATE_PATH):
    enabled = [c for c in plan["support_qa"]["checks"] if c.get("enabled", True)]
    return render_page(template_path, payload, plan["palette"], enabled, LEDGER_MAX_COLS, fonts_dir)


def render_markdown(payload):
    names = {c["id"]: c["name"] for c in payload["checks"]}
    out = [f"# {payload['title']}", "", f"**{payload['headline']}** {payload['subhead']}".rstrip(), "",
           "| Check | Failing |", "|---|---|"]
    out += [f"| {c['name']} | {c['count']} of {payload['counts']['open']} |" for c in payload["checks"]]
    for sec in payload["sections"]:
        rows = [t for t in payload["items"] if t["verdict"] == sec["id"]]
        if not rows:
            continue
        out += ["", f"## {sec['title']} ({len(rows)})", "", sec["cap"], "",
                "| ID | Summary | Status | Assignee | Opened | Last update | In status | QA |",
                "|---|---|---|---|---|---|---|---|"]
        for t in rows:
            qa = ", ".join(names[c] for c in names if t["qa"].get(c)) or "Clear"
            status = t["status"] + (f" ({t['pendingReason']})" if t["pendingReason"] else "")
            out.append(f"| [{t['key']}]({t['url']}) | {md_cell(t['summary'])} | {md_cell(status)} | {md_cell(t['assignee'])} | "
                       f"{t['createdText']} | {t['updDays']} days | {t['inStatusDays']} days | {qa} |")
    out += ["", "## What the data says about the rules", ""]
    out += [f"{n}. **{t}.** {s}" for n, (t, s) in enumerate(payload["findings"], 1)] or ["_None._"]
    if payload["warnings"]:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in payload["warnings"]]
    return "\n".join(out) + "\n"
