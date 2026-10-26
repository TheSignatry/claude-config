#!/usr/bin/env python3
"""Work Boards QA report for acos-jira-analysis.

One report across every project key in the owner's `work` workspace group,
with a client-side board filter. It finds work that can be closed, work
stalled on us, third-party (vendor) commitments at risk, and items assigned
to former employees or to people outside the Technology team. Pure functions
only: jira_report.py owns the CLI, the directory cache file, and the calls
into build_work_plan() / directory_lookups() / build_work_report() /
render_*() here.

Who holds the next move (the lane), every check, and the verdict order come
from jira_workspaces.work_qa. Every per-board view the page can show (headline,
subhead, ledger and owner counts, lane counts) is precomputed here so the
browser only selects one.
"""
import re
from datetime import date, datetime, timedelta

from qa_common import (
    SKILL_DIR, QAError, aggregate_owners, cap, display_value, fmt_date, join, key_sort,
    load_design_spec, local_date, md_cell, normalize_issues, num_word, parse_ts, render_page,
    resolve_tz, validate_buckets, validate_check_ids, validate_palette, whole_days,
)

TEMPLATE_PATH = SKILL_DIR / "assets" / "work_qa_template.html"
DESIGN_PATH = SKILL_DIR / "references" / "work_qa_design.md"
LEDGER_MAX_COLS = 7
ROLES = {"ink", "risk", "good"}
LANES = [("ours", "Our move"), ("vendor", "Vendor’s move"), ("backlog", "Backlog")]
LANE_IDS = {l for l, _ in LANES}
SORTS = {"upd_days_desc", "assignee_then_upd_desc"}
CHECK_TYPES = {
    "parent_closed", "linked_idea_closed", "empty_epic", "stale_ours", "blocker_done",
    "unassigned_started", "due_before_today", "vendor_release_passed", "vendor_ref_missing",
    "blocked_status", "assignee_not_in_directory", "assignee_outside_roster", "backlog_rot",
}
# Standard Jira names, not site configuration.
EPIC_TYPE = "Epic"
BLOCKS_LINK = "Blocks"
# Thresholds used only in diagnostic prose.
VENDOR_QUIET_DAYS = 180
VENDOR_SATURATION_DAYS = 60


# --- config -----------------------------------------------------------------

def validate_work_config(wq, wf, keys):
    if not isinstance(wq, dict) or not wq.get("checks"):
        raise QAError("jira_workspaces.work_qa is missing or has no checks configured.")
    for k in ("stale_days", "backlog_age_days", "backlog_untouched_days"):
        if not isinstance(wq.get(k), int) or wq[k] < 0:
            raise QAError(f"work_qa.{k} must be a non-negative integer.")
    for vkey, v in (wq.get("vendors") or {}).items():
        if vkey not in keys:
            raise QAError(f"work_qa.vendors has unknown board {vkey!r} (not in jira_workspaces.work).")
        if not v.get("name") or not isinstance(v.get("statuses"), list):
            raise QAError(f"work_qa.vendors.{vkey} needs a name and a statuses list.")
        ref = v.get("ticket_ref_field")
        if ref and not isinstance(wf.get(ref), str):
            raise QAError(f"work_qa.vendors.{vkey}.ticket_ref_field {ref!r} is not in work_fields.")
        pat = v.get("release_label_pattern")
        if pat:
            try:
                if re.compile(pat).groups < 2:
                    raise QAError(f"work_qa.vendors.{vkey}.release_label_pattern needs two groups (yy, mm).")
            except re.error as e:
                raise QAError(f"work_qa.vendors.{vkey}.release_label_pattern is an invalid regex: {e}.")
    validate_buckets("work_qa", wq.get("aging_buckets"))
    dc = wq.get("directory_check") or {}
    if dc.get("enabled", True) and dc.get("source", "slack") != "slack":
        raise QAError(f"work_qa.directory_check.source {dc.get('source')!r} is not supported; use 'slack'.")

    validate_check_ids("work_qa", wq["checks"])
    ids, enabled = set(), []
    for c in wq["checks"]:
        ids.add(c["id"])
        if c.get("type") not in CHECK_TYPES:
            raise QAError(f"work_qa check {c['id']!r} has unknown type {c.get('type')!r}.")
        if c.get("color_role", "ink") not in ROLES:
            raise QAError(f"work_qa check {c['id']!r} has color_role {c.get('color_role')!r}; use ink, risk, or good.")
        if c.get("enabled", True):
            enabled.append(c)
    if not enabled:
        raise QAError("work_qa has no enabled checks.")

    verdicts = wq.get("verdicts") or []
    vids = [v.get("id") for v in verdicts]
    if not verdicts or not all(vids) or len(set(vids)) != len(vids):
        raise QAError("work_qa.verdicts must be a non-empty list with unique ids.")
    if "*" not in verdicts[-1].get("when", []):
        raise QAError("work_qa.verdicts must end with a fallback verdict whose when is ['*'].")
    for v in verdicts:
        if v.get("sort", "upd_days_desc") not in SORTS:
            raise QAError(f"work_qa verdict {v['id']!r} has unknown sort {v.get('sort')!r}.")
        for tok in v.get("when") or []:
            if tok == "*":
                continue
            cid, _, lane = tok.partition("@")
            if cid not in ids:
                raise QAError(f"work_qa verdict {v['id']!r} references unknown check {cid!r}.")
            if lane and lane not in LANE_IDS:
                raise QAError(f"work_qa verdict {v['id']!r} references unknown lane {lane!r}.")
    validate_palette("work_qa.palette_extra", wq.get("palette_extra") or {}, ["board_default", "stale_line"])
    return enabled


# --- plan -------------------------------------------------------------------

def roster_names(profile, sources):
    names = set()
    for src in sources:
        if src == "owner":
            n = (profile.get("owner") or {}).get("full_name")
            if n:
                names.add(n.strip())
            continue
        for p in profile.get(src) or []:
            if (p or {}).get("name"):
                names.add(p["name"].strip())
    return sorted(names)


def work_fields_list(wf, wq):
    ids = []
    for v in (wq.get("vendors") or {}).values():
        ref = v.get("ticket_ref_field")
        if ref and wf.get(ref) not in ids:
            ids.append(wf[ref])
    for k in ("priority_ranking", "sprint"):
        if isinstance(wf.get(k), str) and wf[k] not in ids:
            ids.append(wf[k])
    return ["summary", "status", "assignee", "issuetype", "created", "updated", "duedate",
            "parent", "issuelinks", "labels", "fixVersions"] + ids


def build_work_plan(workspaces, wf, profile, cloud_id, today):
    keys = workspaces.get("work") or []
    if not keys:
        raise QAError("jira_workspaces.work has no project keys; the Work Boards QA report has nothing to review.")
    wq = workspaces.get("work_qa")
    if not wq:
        raise QAError("jira_workspaces.work_qa is not configured in acos-aboutme (profile or defaults).")
    palette = (workspaces.get("product_qa") or {}).get("palette")
    if not palette:
        raise QAError("jira_workspaces.product_qa.palette is missing; the Work Boards QA report shares its color tokens.")
    validate_work_config(wq, wf, keys)
    tz_name = ((profile.get("owner") or {}).get("timezone") or wq.get("timezone")
               or (workspaces.get("support_qa") or {}).get("timezone"))
    resolve_tz(tz_name)
    extra = {k: v for k, v in (wq.get("palette_extra") or {}).items() if not k.startswith("_")}
    for k in keys:
        extra.setdefault(f"board_{k}", extra["board_default"])
    return {
        "report": "work_qa",
        "cloud_id": cloud_id,
        "site": f"https://{cloud_id}/browse/",
        "work_keys": keys,
        "work_fields": wf,
        "work_qa": wq,
        "palette": {**palette, **extra},
        "roster": roster_names(profile, wq.get("team_roster_sources") or []),
        "timezone": tz_name,
        "queries": [{
            "id": "work_qa",
            "jql": f"project in ({', '.join(keys)}) AND statusCategory != Done ORDER BY project ASC, created ASC",
            "fields": work_fields_list(wf, wq),
            "description": "Every open item on the work boards, team-wide. Excluded statuses are dropped in Python so the report can count them.",
        }],
    }


# --- directory --------------------------------------------------------------

def _assignees(issues):
    return {display_value((i.get("fields") or {}).get("assignee")) for i in issues} - {None}


def directory_lookups(plan, raw, cache=None, today=None):
    """The slack_search_users calls still needed: each distinct non-roster
    assignee without a fresh cache entry. First name as the keyword (Slack
    display names can carry suffixes), full name as the natural-language query."""
    wq = plan["work_qa"]
    dc = wq.get("directory_check") or {}
    if not dc.get("enabled", True):
        return []
    today = today or date.today()
    fresh = _fresh(cache or {}, dc.get("cache_days", 7), today)
    roster = set(plan.get("roster") or [])
    names = sorted(n for n in _assignees(_kept(plan, raw)) if n not in roster and n not in fresh)
    return [{"name": n, "tool": "slack_search_users", "query": n.split()[0], "natural_language_query": n} for n in names]


def _fresh(cache, days, today):
    out = {}
    for name, e in (cache or {}).items():
        try:
            checked = date.fromisoformat(e.get("checked", ""))
        except ValueError:
            continue
        if (today - checked).days < days:
            out[name] = e
    return out


def resolve_match(name, results):
    """Found when a result's display name equals the Jira name ignoring case,
    after stripping any trailing suffix ("Jane Doe WG/TE/DI")."""
    target = name.strip().lower()
    for r in results or []:
        disp = (r if isinstance(r, str) else (r or {}).get("display_name") or (r or {}).get("name") or "").strip()
        low = disp.lower()
        if low == target or low.startswith(target + " "):
            return {"found": True, "matched": disp}
    return {"found": False, "matched": None}


def normalize_directory(entries):
    out = {}
    for name, e in (entries or {}).items():
        if isinstance(e, dict) and "found" in e:
            out[name] = {"found": bool(e["found"]), "matched": e.get("matched")}
        elif isinstance(e, dict) and "results" in e:
            out[name] = resolve_match(name, e["results"])
        elif isinstance(e, list):
            out[name] = resolve_match(name, e)
    return out


def updated_cache(cache, directory, today):
    out = dict(cache or {})
    for name, e in directory.items():
        out[name] = {**e, "checked": today.isoformat()}
    return out


# --- per-item ---------------------------------------------------------------

def _kept(plan, raw):
    ex = set(plan["work_qa"].get("exclude_statuses") or [])
    return [i for i in normalize_issues(raw.get("work_qa"))
            if ((i.get("fields") or {}).get("status") or {}).get("name") not in ex]


def _rel(other):
    st = (other.get("fields") or {}).get("status") or {}
    return {"key": other.get("key", ""), "status": st.get("name", ""),
            "cat": (st.get("statusCategory") or {}).get("key") or "new"}


def _dedupe(rows):
    seen, out = set(), []
    for r in rows:
        if r["key"] not in seen:
            seen.add(r["key"])
            out.append(r)
    return out


def _lane(board, status, cat, vendors):
    v = vendors.get(board)
    if v and status in v.get("statuses", []):
        return "vendor"
    return "backlog" if cat == "new" else "ours"


def _release(labels, pattern):
    if not pattern:
        return None, None
    rx = re.compile(pattern)
    for lab in labels or []:
        m = rx.match(lab)
        if m:
            return lab, (2000 + int(m.group(1)), int(m.group(2)))
    return None, None


def pick_verdict(t, verdicts):
    for v in verdicts:
        for tok in v.get("when") or []:
            if tok == "*":
                return v["id"]
            cid, _, lane = tok.partition("@")
            if t["qa"].get(cid) and (not lane or t["lane"] == lane):
                return v["id"]
    return verdicts[-1]["id"]


# --- payload ----------------------------------------------------------------

def build_work_report(plan, raw, today=None, cache=None):
    today = today or date.today()
    tiso = today.isoformat()
    wq, wf, keys = plan["work_qa"], plan["work_fields"], plan["work_keys"]
    checks = validate_work_config(wq, wf, keys)
    tz = resolve_tz(plan.get("timezone"))
    now = datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz)
    vendors = wq.get("vendors") or {}
    idea_projects = set(wq.get("idea_projects") or [])
    roster = set(plan.get("roster") or [])
    ex = set(wq.get("exclude_statuses") or [])
    warnings = []

    all_issues = normalize_issues(raw.get("work_qa"))
    excluded = {}
    issues = []
    for i in all_issues:
        st = ((i.get("fields") or {}).get("status") or {}).get("name")
        if st in ex:
            excluded[st] = excluded.get(st, 0) + 1
        else:
            issues.append(i)

    # Directory: cache, then this run's lookups (raw wins).
    dc = wq.get("directory_check") or {}
    needed = sorted(n for n in _assignees(issues) if n not in roster)
    if not dc.get("enabled", True):
        dir_state, directory = "disabled", {}
    else:
        directory = {**_fresh(cache or {}, dc.get("cache_days", 7), today), **normalize_directory(raw.get("directory"))}
        missing = [n for n in needed if n not in directory]
        if raw.get("directory_unavailable") or missing:
            dir_state = "unavailable"
            if missing and not raw.get("directory_unavailable"):
                warnings.append(f"No directory result for {', '.join(missing)}; the directory check was not run.")
        else:
            dir_state = "ok"
    dir_ran = dir_state == "ok"

    open_parents = set()
    for i in issues:
        p = (i.get("fields") or {}).get("parent")
        if p and p.get("key"):
            open_parents.add(p["key"])

    by_type = {c["type"]: c["id"] for c in checks}
    items = []
    for issue in issues:
        f = issue.get("fields") or {}
        board = issue["key"].split("-")[0]
        status = (f.get("status") or {}).get("name") or ""
        cat = ((f.get("status") or {}).get("statusCategory") or {}).get("key") or ""
        vend = vendors.get(board) or {}
        lane = _lane(board, status, cat, vendors)
        created, updated = parse_ts(f.get("created"), tz), parse_ts(f.get("updated"), tz)
        assignee = display_value(f.get("assignee"))
        itype = display_value((f.get("issuetype") or {}).get("name")) or ""
        parent = None
        if f.get("parent"):
            pr = f["parent"]
            parent = {**_rel(pr), "type": display_value(((pr.get("fields") or {}).get("issuetype") or {}).get("name")) or ""}
        ideas, blockers = [], []
        for link in f.get("issuelinks") or []:
            other = link.get("outwardIssue") or link.get("inwardIssue") or {}
            if other.get("key", "").split("-")[0] in idea_projects:
                ideas.append(_rel(other))
            if (link.get("type") or {}).get("name") == BLOCKS_LINK and link.get("inwardIssue"):
                blockers.append(_rel(link["inwardIssue"]))
        ideas, blockers = _dedupe(ideas), _dedupe(blockers)
        release, rel_ym = _release(f.get("labels"), vend.get("release_label_pattern"))
        ref_field = vend.get("ticket_ref_field")
        vendor_ref = display_value(f.get(wf[ref_field])) if ref_field else None
        t = {
            "key": issue["key"], "url": plan["site"] + issue["key"], "board": board,
            "summary": f.get("summary") or "", "type": itype, "status": status, "lane": lane,
            "laneLabel": f"With {vend['name']}" if lane == "vendor" else dict(LANES)[lane] if lane == "ours" else "Backlog",
            "vendor": vend.get("name") if lane == "vendor" else None,
            "assignee": assignee or "Unassigned",
            "created": local_date(created, tz), "updated": local_date(updated, tz),
            "ageDays": whole_days(created, now) or 0, "updDays": whole_days(updated, now) or 0,
            "due": f.get("duedate") or None, "parent": parent, "ideas": ideas, "blockers": blockers,
            "release": release, "vendorRef": vendor_ref,
            "priorityRanking": f.get(wf.get("priority_ranking", "")) if wf.get("priority_ranking") else None,
            "hasFixVersion": bool(f.get("fixVersions")),
            "inSprint": bool(f.get(wf["sprint"])) if wf.get("sprint") else None,
        }
        flags, tips = {}, {}
        in_roster = assignee in roster if assignee else True
        dir_entry = directory.get(assignee) if assignee else None
        for c in checks:
            cid, ctype, tip = c["id"], c["type"], c["name"]
            if ctype == "parent_closed":
                fail = bool(parent) and parent["cat"] == "done"
                if fail:
                    tip = f"{c['name']}: {parent['key']} is {parent['status']}"
            elif ctype == "linked_idea_closed":
                done = [x for x in ideas if x["cat"] == "done"]
                fail = bool(done)
                tip = f"{c['name']}: " + ", ".join(f"{x['key']} {x['status']}" for x in done)
            elif ctype == "empty_epic":
                fail = itype == EPIC_TYPE and issue["key"] not in open_parents
            elif ctype == "stale_ours":
                fail = lane == "ours" and t["updDays"] >= wq["stale_days"]
                tip = f"{c['name']}: no update in {t['updDays']} days"
            elif ctype == "blocker_done":
                done = [x for x in blockers if x["cat"] == "done"]
                fail = bool(done)
                tip = f"{c['name']}: " + ", ".join(f"{x['key']} {x['status']}" for x in done)
            elif ctype == "unassigned_started":
                fail = lane != "backlog" and not assignee
            elif ctype == "due_before_today":
                fail = bool(t["due"]) and t["due"] < tiso
                tip = f"{c['name']}: due {fmt_date(t['due'])}"
            elif ctype == "vendor_release_passed":
                fail = lane == "vendor" and bool(rel_ym) and rel_ym < (today.year, today.month)
                tip = f"{c['name']}: tagged {release}"
            elif ctype == "vendor_ref_missing":
                fail = lane == "vendor" and bool(ref_field) and not vendor_ref
            elif ctype == "blocked_status":
                fail = status in (wq.get("blocked_statuses") or [])
            elif ctype == "assignee_not_in_directory":
                fail = dir_ran and not in_roster and bool(dir_entry) and not dir_entry["found"]
                tip = f"{c['name']}: {assignee} wasn’t found in Slack"
            elif ctype == "assignee_outside_roster":
                fail = not in_roster and (not dir_ran or bool(dir_entry and dir_entry["found"]))
                tip = f"{c['name']}: {assignee}"
            else:  # backlog_rot
                fail = (lane == "backlog" and t["ageDays"] >= wq["backlog_age_days"]
                        and t["updDays"] >= wq["backlog_untouched_days"])
                tip = f"{c['name']}: {t['ageDays']} days old, untouched {t['updDays']} days"
            flags[cid] = bool(fail)
            if fail:
                tips[cid] = tip
        t["qa"], t["qaTips"] = flags, tips
        t["verdict"] = pick_verdict(t, wq["verdicts"])
        t["hot"] = lane == "ours" and t["updDays"] >= wq["stale_days"]
        t["createdText"], t["updatedText"], t["dueText"] = fmt_date(t["created"]), fmt_date(t["updated"]), fmt_date(t["due"])
        items.append(t)

    board_order = {k: n for n, k in enumerate(keys)}
    first_verdict = wq["verdicts"][0]
    si_id = by_type.get("stale_ours")

    # Sections in config order.
    sections = []
    for v in wq["verdicts"]:
        arr = [t for t in items if t["verdict"] == v["id"]]
        if v.get("sort") == "assignee_then_upd_desc":
            arr.sort(key=lambda t: (t["assignee"].lower(), -t["updDays"], key_sort(t["key"])))
        else:
            arr.sort(key=lambda t: (-t["updDays"], key_sort(t["key"])))
        sections.append({"id": v["id"], "title": v["title"], "cap": v.get("cap", ""),
                         "collapsed": bool(v.get("collapsed")), "keys": [t["key"] for t in arr]})
    order = {k: n for n, k in enumerate(k for s in sections for k in s["keys"])}
    items.sort(key=lambda t: order[t["key"]])

    # Lanes chart layout (positions use every item; counts are per view).
    chart_lanes = {}
    for lane, _ in LANES:
        lane_items = [t for t in items if t["lane"] == lane]
        cols = []
        for lo, hi in wq["aging_buckets"]:
            arr = [t for t in lane_items if t["updDays"] >= lo and (hi is None or t["updDays"] <= hi)]
            arr.sort(key=lambda t: (board_order.get(t["board"], 99), -t["updDays"], key_sort(t["key"])))
            cols.append([t["key"] for t in arr])
        chart_lanes[lane] = cols
    stale_idx = next(n for n, (lo, hi) in enumerate(wq["aging_buckets"]) if hi is None or lo <= wq["stale_days"] <= hi)
    bucket_labels = [f"{lo}–{hi} days" if hi is not None else f"{lo}+ days" for lo, hi in wq["aging_buckets"]]

    # Owner labels.
    labels = {}
    for name in needed:
        e = directory.get(name)
        labels[name] = ("Not in Slack directory" if dir_ran and e and not e["found"] else "Outside Technology")

    # Views: all boards, then each board.
    def view(subset):
        cnt = lambda cid: sum(1 for t in subset if t["qa"].get(cid))  # noqa: E731
        close = sum(1 for t in subset if t["verdict"] == first_verdict["id"])
        si = cnt(si_id) if si_id else 0
        first = (f"{cap(num_word(close))} open item can be closed or cleaned up now" if close == 1 else
                 f"{cap(num_word(close)) if close else 'No'} open items can be closed or cleaned up now")
        second = (f"{num_word(si)} started item hasn’t moved in a month" if si == 1 else
                  f"{num_word(si) if si else 'no'} started items haven’t moved in a month")
        parts = []
        by_vendor = {}
        for t in subset:
            if t["lane"] == "vendor":
                by_vendor.setdefault(t["vendor"], []).append(t)
        for vname, ven in sorted(by_vendor.items()):
            q = sum(1 for t in ven if t["updDays"] >= VENDOR_QUIET_DAYS)
            rp = sum(1 for t in ven if t["qa"].get(by_type.get("vendor_release_passed", "")))
            ic = sum(1 for t in ven if t["qa"].get(by_type.get("linked_idea_closed", "")))
            parts.append(f"{len(ven)} items are with {vname}, and {q} of them haven’t been updated in {VENDOR_QUIET_DAYS}+ days, "
                         f"so staleness alone can’t tell which vendor commitments are slipping. Release labels and closed ideas can: "
                         f"{rp} are past their release and {ic} are linked to ideas the roadmap already closed.")
        bl = [t for t in subset if t["lane"] == "backlog"]
        if bl:
            br = sum(1 for t in bl if t["qa"].get(by_type.get("backlog_rot", "")))
            parts.append(f"{len(bl)} items are still in To Do, and {br} of those are {wq['backlog_age_days']}+ days old "
                         f"and untouched for {wq['backlog_untouched_days']}+.")
        owners = aggregate_owners(subset, {
            "open": len,
            "ours": lambda a: sum(t["lane"] == "ours" for t in a),
            "vendor": lambda a: sum(t["lane"] == "vendor" for t in a),
            "backlog": lambda a: sum(t["lane"] == "backlog" for t in a),
            "close": lambda a: sum(t["verdict"] == first_verdict["id"] for t in a),
            "stalled": lambda a: sum(bool(si_id and t["qa"].get(si_id)) for t in a),
        })
        keyset = {t["key"] for t in subset}
        return {
            "total": len(subset),
            "headline": f"{first}, and {second}.",
            "subhead": " ".join(parts),
            "checkCounts": {c["id"]: cnt(c["id"]) for c in checks},
            "verdictCounts": {v["id"]: sum(t["verdict"] == v["id"] for t in subset) for v in wq["verdicts"]},
            "laneTotals": {lane: sum(t["lane"] == lane for t in subset) for lane, _ in LANES},
            "bucketCounts": {lane: [sum(k in keyset for k in col) for col in chart_lanes[lane]] for lane, _ in LANES},
            "owners": owners,
        }

    views = {"": view(items)}
    for k in keys:
        views[k] = view([t for t in items if t["board"] == k])

    findings = _diagnostics(items, keys, vendors, by_type, wq, wf, directory if dir_ran else {}, needed, first_verdict)

    def param(c):
        return {
            "parent_closed": "parent status category: done",
            "linked_idea_closed": f"idea_projects: {', '.join(sorted(idea_projects))}",
            "empty_epic": f"issue type: {EPIC_TYPE}",
            "stale_ours": f"stale_days: {wq['stale_days']}",
            "blocker_done": f"link type: {BLOCKS_LINK} (inward)",
            "unassigned_started": "lanes: ours, vendor",
            "due_before_today": "field: duedate",
            "vendor_release_passed": "release_label_pattern per vendor board",
            "vendor_ref_missing": "ticket_ref_field per vendor board",
            "blocked_status": f"blocked_statuses: {', '.join(wq.get('blocked_statuses') or [])}",
            "assignee_not_in_directory": "directory: Slack users (Jira still shows departed accounts as active)",
            "assignee_outside_roster": f"roster: profile.json {', '.join(wq.get('team_roster_sources') or [])}",
            "backlog_rot": f"backlog_age_days: {wq['backlog_age_days']}; untouched: {wq['backlog_untouched_days']}",
        }[c["type"]]

    next_move = " ".join(f"{k}: {join(v['statuses'])} {'is' if len(v['statuses']) == 1 else 'are'} with {v['name']}."
                         for k, v in vendors.items())
    next_move = (next_move + " " if next_move else "") + "Any To Do-category status is backlog. Everything else in progress is our move."
    foot = None
    if dir_state == "unavailable":
        foot = "Directory check not run: Slack wasn’t connected, so assignees outside the roster count as outside Technology."
    elif dir_state == "disabled":
        foot = "Directory check is turned off in config, so assignees outside the roster count as outside Technology."
    kl = ", ".join(keys)
    board_names = wq.get("board_names") or {}
    return {
        "generated": tiso,
        "site": plan["site"],
        "title": f"Work boards QA ({kl}), {fmt_date(tiso)}",
        "eyebrowBase": "Work boards QA review",
        "dateText": fmt_date(tiso),
        "boards": [{"key": k, "name": board_names.get(k, k), "count": views[k]["total"]} for k in keys],
        "lanes": [{"id": l, "name": n} for l, n in LANES],
        "checks": [{"id": c["id"], "name": c["name"], "rule": c["rule"], "role": c.get("color_role", "ink"),
                    "param": param(c), "notRun": c["type"] == "assignee_not_in_directory" and not dir_ran} for c in checks],
        "nextMove": next_move,
        "sections": [{k: v for k, v in s.items() if k != "keys"} for s in sections],
        "closeTitle": first_verdict["title"],
        "views": views,
        "chart": {"lanes": chart_lanes, "bucketLabels": bucket_labels, "staleIndex": stale_idx,
                  "staleLabel": f"Stale after {wq['stale_days']} days without an update"},
        "ownerLabels": labels,
        "items": items,
        "findings": findings,
        "spec": load_design_spec(DESIGN_PATH),
        "directoryState": dir_state,
        "directory": directory if dir_ran else {},
        "footNote": foot,
        "excluded": excluded,
        "sourceLine": f"Source: Jira projects {join(keys)} on {plan['cloud_id']}, read {fmt_date(tiso)}. Read-only; nothing in Jira was changed.",
        "warnings": warnings,
        "counts": {"open": len(items), "excluded": sum(excluded.values()), **views[""]["verdictCounts"]},
    }


def _pct(n, d):
    return 100.0 * n / d if d else 0.0


def _diagnostics(items, keys, vendors, by_type, wq, wf, directory, needed, first_verdict):
    out = []
    cnt = lambda cid: sum(1 for t in items if cid and t["qa"].get(cid))  # noqa: E731
    by_board = {k: [t for t in items if t["board"] == k] for k in keys}
    n_open = len(items)

    for vkey, v in vendors.items():
        ven = [t for t in items if t["lane"] == "vendor" and t["board"] == vkey]
        n60 = sum(t["updDays"] >= VENDOR_SATURATION_DAYS for t in ven)
        if ven and _pct(n60, len(ven)) >= 75:
            n180 = sum(t["updDays"] >= VENDOR_QUIET_DAYS for t in ven)
            refs = sum(1 for t in ven if t["vendorRef"])
            out.append(["Vendor staleness is saturated",
                        f"{n60} of {len(ven)} items with {v['name']} haven’t been updated in {VENDOR_SATURATION_DAYS}+ days and {n180} in {VENDOR_QUIET_DAYS}+. "
                        f"A “vendor follow-up due” check would flag nearly all of them, so the report leans on release labels and closed ideas instead. "
                        f"The strongest next step is reconciling against {v['name']}’s own ticket export, since {refs} of these items already carry a ticket ID."])

    cp_id = by_type.get("parent_closed")
    cp = cnt(cp_id)
    if cp and _pct(cp, n_open) >= 10:
        per = {k: sum(1 for t in by_board[k] if t["qa"].get(cp_id)) for k in keys}
        top = max(keys, key=lambda k: (per[k], -keys.index(k)))
        spread = "almost all" if _pct(per[top], cp) >= 90 else "most"
        out.append(["Most cleanup is leftover sub-tasks",
                    f"{cp} open items sit under a parent that’s already Done, {spread} on {top}. Closing them would shrink the {top} board by "
                    f"about {round(_pct(per[top], len(by_board[top])))}% without losing any open work."])

    ua = cnt(by_type.get("unassigned_started"))
    for k in keys:
        arr = by_board[k]
        b = sum(t["lane"] == "backlog" for t in arr)
        if len(arr) > 2 and _pct(b, len(arr)) >= 70:
            u = sum(t["assignee"] == "Unassigned" for t in arr)
            out.append([f"{k} is mostly backlog",
                        f"{b} of {len(arr)} {k} items are in To Do and {u} are unassigned. Unassigned only counts as a QA failure once work has started, "
                        f"which is true for just {ua} item{'s' if ua != 1 else ''}."])

    dues = {k: sum(1 for t in by_board[k] if t["due"]) for k in keys}
    total_due = sum(dues.values())
    if total_due:
        ranked = sorted(keys, key=lambda k: (-dues[k], keys.index(k)))
        top = ranked[0]
        if _pct(dues[top], total_due) >= 75:
            second = ranked[1] if len(ranked) > 1 and dues[ranked[1]] else None
            rest = [k for k in ranked[1:] if k != second]
            text = f"{top} has {dues[top]} items with a due date"
            if second:
                text += f" and {second} has {dues[second]}"
            if rest:
                text += f"; {join(rest)} barely use{'s' if len(rest) == 1 else ''} them"
            out.append([f"Due dates are a {top} habit", text + f". The past-due check mostly speaks to {top}."])

    for vkey, v in vendors.items():
        first = v["statuses"][0] if v.get("statuses") else "a vendor status"
        out.append([f"Time in status isn’t available for {vkey}",
                    f"Jira only exposes when the status category last changed, and every {v['name']}-held {vkey} status shares one category. "
                    f"Showing how long an item has sat in {first} would need each issue’s change history, which is possible but slower."])

    sprint_known = bool(wf.get("sprint"))
    if not any(t["hasFixVersion"] for t in items) and not (sprint_known and any(t["inSprint"] for t in items)):
        names = [v["name"] for v in vendors.values() if v.get("release_label_pattern")]
        r = sum(1 for t in items if t["release"])
        what = ("is in a sprint or has a fix version, so neither can" if sprint_known
                else "has a fix version, so fix versions can’t")
        text = f"None of the {n_open} open items {what} stand in for a delivery commitment."
        if names:
            text += f" {join(names)} release labels are the only commitment signal, and only {r} item{'s' if r != 1 else ''} carr{'y' if r != 1 else 'ies'} one."
        out.append(["Sprints and fix versions aren’t used" if sprint_known else "Fix versions aren’t used", text])

    fe_id = by_type.get("assignee_not_in_directory")
    fe = cnt(fe_id)
    if fe:
        gone = [n for n in needed if directory.get(n) and not directory[n]["found"]]
        c = sum(1 for t in items if t["qa"].get(fe_id) and t["verdict"] == first_verdict["id"])
        out.append(["Departed owners still hold work",
                    f"{len(gone)} assignees ({join(gone)}) aren’t in the Slack directory but still hold {fe} open items, and Jira still lists all of their "
                    f"accounts as active. That’s an offboarding gap as well as a QA one: worth confirming they’ve left and deactivating the Jira accounts. "
                    f"{c} of their items can simply be closed."])

    for k in keys:
        arr = by_board[k]
        if 0 < len(arr) <= 2:
            oldest = max(t["ageDays"] for t in arr)
            unassigned = all(t["assignee"] == "Unassigned" for t in arr)
            lead = f"{k} has {len(arr)} open item, {oldest} days old" if len(arr) == 1 else f"{k} has {len(arr)} open items, the oldest {oldest} days old"
            out.append([f"{k} barely registers",
                        lead + (" and unassigned" if unassigned else "") + ". It may be worth retiring the board from the work group."])
    return out


# --- rendering --------------------------------------------------------------

def render_html(payload, plan, fonts_dir=None, template_path=TEMPLATE_PATH):
    enabled = [c for c in plan["work_qa"]["checks"] if c.get("enabled", True)]
    return render_page(template_path, payload, plan["palette"], enabled, LEDGER_MAX_COLS, fonts_dir)


def render_markdown(payload):
    names = {c["id"]: c["name"] for c in payload["checks"]}
    v = payload["views"][""]
    out = [f"# {payload['title']}", "", f"**{v['headline']}** {v['subhead']}".rstrip(), "", "| Check | Failing |", "|---|---|"]
    for c in payload["checks"]:
        out.append(f"| {c['name']} | {'not run' if c['notRun'] else str(v['checkCounts'][c['id']]) + ' of ' + str(v['total'])} |")
    for sec in payload["sections"]:
        rows = [t for t in payload["items"] if t["verdict"] == sec["id"]]
        if not rows:
            continue
        out += ["", f"## {sec['title']} ({len(rows)})", "", sec["cap"], "",
                "| ID | Board | Summary | Status | Assignee | Opened | Last update | Due | QA |",
                "|---|---|---|---|---|---|---|---|---|"]
        for t in rows:
            qa = ", ".join(names[c] for c in names if t["qa"].get(c)) or "Clear"
            out.append(f"| [{t['key']}]({t['url']}) | {t['board']} | {md_cell(t['summary'])} | {md_cell(t['status'])} ({t['laneLabel']}) | "
                       f"{md_cell(t['assignee'])} | {t['createdText']} | {t['updDays']} days | {t['dueText'] or 'None'} | {qa} |")
    out += ["", "## What the data says about the rules", ""]
    out += [f"{n}. **{t}.** {s}" for n, (t, s) in enumerate(payload["findings"], 1)] or ["_None._"]
    if payload["footNote"]:
        out += ["", f"_{payload['footNote']}_"]
    if payload["warnings"]:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in payload["warnings"]]
    return "\n".join(out) + "\n"
