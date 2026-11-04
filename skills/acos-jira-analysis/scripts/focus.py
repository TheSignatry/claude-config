#!/usr/bin/env python3
"""Personal Focus dashboard for acos-jira-analysis.

Only the items assigned to the profile owner, across every key in the owner's
product, support, and work groups, sorted into whose move it is (mine,
waiting, parked) and ranked by a published formula from
jira_workspaces.focus.score. Pure functions only: jira_report.py owns the CLI
and calls build_focus_plan() / focus_comments_query() / build_focus_report() /
render_*() here.

Roadmap data gaps use the Product QA report's own check functions, the vendor
lane uses work_qa.vendors, and the roster is the same union the Work Boards
report reads. Comment bodies are never read: only each comment's author
display name and `created` timestamp.
"""
from datetime import date, datetime, timedelta

import product_qa
from qa_common import (
    SKILL_DIR, QAError, cap, display_value, fmt_date, fmt_range, join, key_sort,
    load_design_spec, local_date, md_cell, month_end, normalize_issues, num_word, parse_ts,
    render_page, resolve_tz, validate_check_ids, validate_palette, whole_days,
)

TEMPLATE_PATH = SKILL_DIR / "assets" / "focus_template.html"
DESIGN_PATH = SKILL_DIR / "references" / "focus_design.md"
LEDGER_MAX_COLS = 8
ROLES = {"ink", "risk", "good"}
WORKSPACES = ["product", "support", "work"]
WS_NAMES = {"product": "Product", "support": "Support", "work": "Work"}
LANES = [("mine", "Your move"), ("waiting", "Waiting on someone else"), ("parked", "Parked")]
CHECK_TYPES = {"date_passed", "date_within", "requester_spoke_last", "no_owner_comment", "no_movement",
               "product_qa_gaps", "contradiction", "parked_untouched"}
PRODUCT_MINE_RULES = {"status_category_indeterminate", "date_within_window"}
WORK_MINE_RULES = {"status_category_indeterminate", "has_due_date", "updated_within_recent"}
CONTRADICTIONS = {"roadmap_wont_do_open", "roadmap_now_parking_status", "pending_reason_not_pending"}
SCORE_KEYS = ["past_due_base", "past_due_per_day", "past_due_cap_days", "week_base", "week_per_day_closer", "soon",
              "requester_waiting_base", "requester_waiting_per_day", "requester_waiting_cap_days", "owner_update",
              "no_movement", "high_urgency", "contradiction"]


# --- config -----------------------------------------------------------------

def validate_focus_config(fc):
    if not isinstance(fc, dict) or not fc.get("checks"):
        raise QAError("jira_workspaces.focus is missing or has no checks configured.")
    for k in ("next_moves_count", "timeline_months", "week_days", "soon_days", "no_movement_days", "owner_update_days",
              "parked_untouched_days", "product_mine_window_days", "work_recent_days"):
        if not isinstance(fc.get(k), int) or fc[k] < 0:
            raise QAError(f"focus.{k} must be a non-negative integer.")
    if fc.get("timeline_start", "first_of_current_month") != "first_of_current_month":
        raise QAError(f"focus.timeline_start {fc.get('timeline_start')!r} is not supported; use 'first_of_current_month'.")
    for ws in fc.get("comment_check_workspaces") or []:
        if ws not in WORKSPACES:
            raise QAError(f"focus.comment_check_workspaces has unknown workspace {ws!r}.")
    lanes = fc.get("lanes") or {}
    for rule in (lanes.get("product") or {}).get("mine_if") or []:
        if rule not in PRODUCT_MINE_RULES:
            raise QAError(f"focus.lanes.product.mine_if has unknown rule {rule!r}.")
    for rule in (lanes.get("work") or {}).get("mine_if") or []:
        if rule not in WORK_MINE_RULES:
            raise QAError(f"focus.lanes.work.mine_if has unknown rule {rule!r}.")
    if (lanes.get("work") or {}).get("waiting_from", "work_qa.vendors") != "work_qa.vendors":
        raise QAError("focus.lanes.work.waiting_from must be 'work_qa.vendors'.")
    for c in fc.get("contradictions") or []:
        if c.get("id") not in CONTRADICTIONS:
            raise QAError(f"focus.contradictions has unknown id {c.get('id')!r}.")
    score = fc.get("score") or {}
    for k in SCORE_KEYS:
        if not isinstance(score.get(k), (int, float)):
            raise QAError(f"focus.score.{k} must be a number.")
    validate_check_ids("focus", fc["checks"])
    enabled = []
    for c in fc["checks"]:
        if c.get("type") not in CHECK_TYPES:
            raise QAError(f"focus check {c['id']!r} has unknown type {c.get('type')!r}.")
        if c.get("color_role", "ink") not in ROLES:
            raise QAError(f"focus check {c['id']!r} has color_role {c.get('color_role')!r}; use ink, risk, or good.")
        if c.get("enabled", True):
            enabled.append(c)
    if not enabled:
        raise QAError("focus has no enabled checks.")
    validate_palette("focus.palette_extra", fc.get("palette_extra") or {},
                     ["lane_mine", "lane_waiting", "lane_parked", "ws_product", "ws_support", "ws_work", "today_line"])
    return enabled


# --- plan -------------------------------------------------------------------

def _owner_name(profile):
    o = profile.get("owner") or {}
    return (o.get("full_name") or o.get("name") or "").strip()


def build_focus_plan(workspaces, pf, sf, wf, profile, cloud_id, today):
    fc = workspaces.get("focus")
    if not fc:
        raise QAError("jira_workspaces.focus is not configured in acos-aboutme (profile or defaults).")
    validate_focus_config(fc)
    owner = _owner_name(profile)
    if not owner:
        raise QAError("acos-aboutme profile has no owner.full_name; the Focus dashboard can't tell whose items are yours.")
    groups = {ws: list(workspaces.get(ws) or []) for ws in WORKSPACES}
    keys = [k for ws in WORKSPACES for k in groups[ws]]
    if not keys:
        raise QAError("jira_workspaces has no product, support, or work project keys.")
    pq, wq = workspaces.get("product_qa") or {}, workspaces.get("work_qa") or {}
    palette = pq.get("palette")
    if not palette:
        raise QAError("jira_workspaces.product_qa.palette is missing; the Focus dashboard shares its color tokens.")
    if groups["product"]:
        product_qa.validate_qa_config(pq, pf)
    tz_name = (profile.get("owner") or {}).get("timezone") or (workspaces.get("support_qa") or {}).get("timezone")
    resolve_tz(tz_name)
    acct = (profile.get("owner") or {}).get("jira_account_id")
    who = f'"{acct}"' if acct else "currentUser()"
    fields = ["summary", "status", "issuetype", "created", "updated", "duedate", "parent", "issuelinks", "labels", "assignee"]
    for src, names in ((pf, ["roadmap", "project_target", "project_start", "short_description", "product_area", "teams",
                             "commitment_level", "tshirt_size", "idea_archived"]),
                       (sf, ["request_type", "pending_reason", "urgency"]),
                       (wf, ["give_ticket_id"])):
        for n in names:
            if isinstance(src.get(n), str) and src[n] not in fields:
                fields.append(src[n])
    roster = set()
    for srcname in (wq.get("team_roster_sources") or ["owner", "staff", "reports", "team"]):
        if srcname == "owner":
            roster.add(owner)
            continue
        for p in profile.get(srcname) or []:
            if (p or {}).get("name"):
                roster.add(p["name"].strip())
    return {
        "report": "focus",
        "cloud_id": cloud_id,
        "site": f"https://{cloud_id}/browse/",
        "owner": owner,
        "groups": groups,
        "product_fields": pf, "support_fields": sf, "work_fields": wf,
        "focus": fc,
        "product_qa": pq,
        "work_qa": {"vendors": wq.get("vendors") or {}, "exclude_statuses": wq.get("exclude_statuses") or []},
        "palette": {**palette, **{k: v for k, v in (fc.get("palette_extra") or {}).items() if not k.startswith("_")}},
        "roster": sorted(roster),
        "pending_statuses": ((workspaces.get("support_qa") or {}).get("status_names") or {}).get("pending") or ["Pending"],
        "timezone": tz_name,
        "queries": [{
            "id": "focus_items",
            "jql": f"project in ({', '.join(keys)}) AND assignee = {who} AND statusCategory != Done ORDER BY project ASC, updated DESC",
            "fields": fields,
            "description": "Everything open assigned to the profile owner. After it returns, run focus-comments for the second query.",
        }],
    }


# --- items ------------------------------------------------------------------

def _ws_of(key, groups):
    proj = key.split("-")[0]
    for ws in WORKSPACES:
        if proj in groups[ws]:
            return ws
    return None


def _excluded(issue, plan):
    f = issue.get("fields") or {}
    pf = plan["product_fields"]
    ws = _ws_of(issue["key"], plan["groups"])
    if ws == "product":
        ex = plan["product_qa"].get("exclude_from_qa") or {}
        if display_value(f.get(pf.get("idea_archived", ""))) is not None:
            return True
        if display_value(f.get(pf.get("roadmap", ""))) in (ex.get("roadmap_values") or []):
            return True
    if ws == "work" and ((f.get("status") or {}).get("name") in plan["work_qa"]["exclude_statuses"]):
        return True
    return False


def _kept(plan, raw):
    return [i for i in normalize_issues(raw.get("focus_items")) if _ws_of(i["key"], plan["groups"]) and not _excluded(i, plan)]


def _target(f, pf):
    return product_qa.parse_range(f.get(pf.get("project_target", "")))


def _base(issue, plan, today, now, tz):
    """The parts of an item that don't need comments: workspace, lane, date."""
    fc, pf, sf, wf = plan["focus"], plan["product_fields"], plan["support_fields"], plan["work_fields"]
    lanes = fc.get("lanes") or {}
    f = issue.get("fields") or {}
    key = issue["key"]
    ws = _ws_of(key, plan["groups"])
    board = key.split("-")[0]
    status = (f.get("status") or {}).get("name") or ""
    cat = ((f.get("status") or {}).get("statusCategory") or {}).get("key") or ""
    roadmap = display_value(f.get(pf.get("roadmap", ""))) if ws == "product" else None
    target = _target(f, pf) if ws == "product" else None
    if ws == "product":
        d, kind = (target[1], "target" if target[0] == target[1] else "target range") if target else (None, None)
    else:
        d, kind = (f.get("duedate"), "due") if f.get("duedate") else (None, None)
    days_to = (date.fromisoformat(d) - today).days if d else None
    updated = parse_ts(f.get("updated"), tz)
    upd_days = whole_days(updated, now) or 0
    waiting_on = None
    if ws == "product":
        pl = lanes.get("product") or {}
        rules = pl.get("mine_if") or []
        if roadmap in (pl.get("parked_roadmap") or []):
            lane = "parked"
        elif ("status_category_indeterminate" in rules and cat == "indeterminate") or \
             ("date_within_window" in rules and days_to is not None and abs(days_to) <= fc["product_mine_window_days"]):
            lane = "mine"
        else:
            lane = "parked"
    elif ws == "support":
        sl = lanes.get("support") or {}
        if status in (sl.get("mine_statuses") or []):
            lane = "mine"
        elif status in (sl.get("waiting_statuses") or []):
            lane, waiting_on = "waiting", "requester"
        else:
            lane = "parked"
    else:
        vend = plan["work_qa"]["vendors"].get(board) or {}
        rules = (lanes.get("work") or {}).get("mine_if") or []
        if status in (vend.get("statuses") or []):
            lane, waiting_on = "waiting", vend["name"]
        elif (("status_category_indeterminate" in rules and cat == "indeterminate")
              or ("has_due_date" in rules and f.get("duedate"))
              or ("updated_within_recent" in rules and upd_days < fc["work_recent_days"])):
            lane = "mine"
        else:
            lane = "parked"
    return {"ws": ws, "board": board, "status": status, "cat": cat, "roadmap": roadmap, "target": target,
            "date": d, "dateKind": kind, "daysTo": days_to, "lane": lane, "waitingOn": waiting_on,
            "updated": updated, "updDays": upd_days}


def focus_comments_query(plan, raw, today=None):
    """Second-stage query: comments only, for the owner's items whose workspace
    is in comment_check_workspaces and whose lane is mine or waiting."""
    today = today or date.today()
    tz = resolve_tz(plan.get("timezone"))
    now = datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz)
    wanted = set(plan["focus"].get("comment_check_workspaces") or [])
    keys = []
    for issue in _kept(plan, raw):
        b = _base(issue, plan, today, now, tz)
        if b["ws"] in wanted and b["lane"] in ("mine", "waiting"):
            keys.append(issue["key"])
    keys.sort(key=key_sort)
    if not keys:
        return None
    return {"id": "focus_comments", "jql": f"key in ({', '.join(keys)}) ORDER BY key ASC", "fields": ["comment"],
            "description": "Comments for the owner's support items in play. Only author and created are used."}


def _gap_label(check):
    if check["type"] == "exact_date":
        return "exact dates"
    name = check["name"]
    return name[3:] if name.startswith("No ") else product_qa._lc_first(name)


def _ref_label(field_key):
    return " ".join("ID" if w.lower() == "id" else w.capitalize() for w in field_key.split("_"))


def _plural_days(n):
    return f"{n} day" if n == 1 else f"{n} days"


# --- payload ----------------------------------------------------------------

def build_focus_report(plan, raw, today=None):
    today = today or date.today()
    tiso = today.isoformat()
    fc, pf, sf, wf = plan["focus"], plan["product_fields"], plan["support_fields"], plan["work_fields"]
    checks = validate_focus_config(fc)
    tz = resolve_tz(plan.get("timezone"))
    now = datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz)
    owner = plan["owner"]
    roster = set(plan.get("roster") or []) | {owner}
    sc = fc["score"]

    all_issues = normalize_issues(raw.get("focus_items"))
    for issue in all_issues:
        who = display_value((issue.get("fields") or {}).get("assignee"))
        if who != owner:
            raise QAError(f"Jira returned {issue['key']} assigned to {who or 'nobody'}, not the profile owner {owner}; the connector "
                          "may be signed in as someone else, so nothing was rendered.")
    issues = _kept(plan, raw)

    comments = {}
    for i in normalize_issues(raw.get("focus_comments")):
        block = (i.get("fields") or {}).get("comment") or {}
        lst = block.get("comments") if isinstance(block, dict) else block
        comments[i["key"]] = [(parse_ts(c.get("created"), tz), display_value((c.get("author") or {}).get("displayName")))
                              for c in (lst or [])]

    pq = plan["product_qa"]
    product_checks = [c for c in pq.get("checks") or [] if c.get("enabled", True) and c["type"] != "date_before_today"]
    parked_roadmap = set(((fc.get("lanes") or {}).get("product") or {}).get("parked_roadmap") or [])
    contradictions = fc.get("contradictions") or []
    vendors = plan["work_qa"]["vendors"]
    by_type = {c["type"]: c["id"] for c in checks}

    items = []
    for issue in issues:
        f = issue.get("fields") or {}
        b = _base(issue, plan, today, now, tz)
        created = parse_ts(f.get("created"), tz)
        cs = sorted((c for c in comments.get(issue["key"], []) if c[0]), key=lambda c: c[0])
        last_word = None
        if cs:
            ts, who = cs[-1]
            last_word = {"who": who, "date": local_date(ts, tz), "customer": who not in roster}
        owner_cs = [c for c in cs if c[1] == owner]
        owner_last = local_date(owner_cs[-1][0], tz) if owner_cs else None

        gaps = []
        if b["ws"] == "product" and b["roadmap"] not in parked_roadmap:
            idea = product_qa.parse_idea(issue, pf, pq, plan["groups"]["product"])
            flags, _ = product_qa.run_checks(idea, product_checks, pf, tiso, False)
            gaps = [_gap_label(c) for c in product_checks if flags.get(c["id"])]

        reason_val = display_value(f.get(sf.get("pending_reason", ""))) if b["ws"] == "support" else None
        mismatch = None
        for c in contradictions:
            if c["workspace"] != b["ws"]:
                continue
            hit = ((c["id"] == "roadmap_wont_do_open" and b["roadmap"] == "Won't do" and b["cat"] != "done")
                   or (c["id"] == "roadmap_now_parking_status" and b["roadmap"] == "Now" and b["status"] == "Parking lot")
                   or (c["id"] == "pending_reason_not_pending" and reason_val and b["status"] not in plan["pending_statuses"]))
            if hit:
                mismatch = c["text"].format(reason=reason_val or "", status=b["status"])
                break

        urgency = display_value(f.get(sf.get("urgency", ""))) if b["ws"] == "support" else None
        vend = vendors.get(b["board"]) or {}
        ref_field = vend.get("ticket_ref_field")
        vendor_ref = display_value(f.get(wf.get(ref_field, ""))) if ref_field and wf.get(ref_field) else None
        owner_age = (today - date.fromisoformat(owner_last)).days if owner_last else None
        t = {
            "key": issue["key"], "url": plan["site"] + issue["key"], "ws": b["ws"], "board": b["board"],
            "summary": f.get("summary") or "", "status": b["status"], "roadmap": b["roadmap"], "lane": b["lane"],
            "laneLabel": ("Waiting on the requester" if b["waitingOn"] == "requester" else f"With {b['waitingOn']}")
                         if b["lane"] == "waiting" else dict(LANES)[b["lane"]],
            "waitingOn": b["waitingOn"], "date": b["date"], "dateKind": b["dateKind"], "daysTo": b["daysTo"],
            "target": b["target"], "due": f.get("duedate"),
            "dateText": (fmt_range(b["target"]) if b["target"] and b["target"][0] != b["target"][1] else fmt_date(b["date"])) if b["date"] else None,
            "updated": local_date(b["updated"], tz), "updatedText": fmt_date(local_date(b["updated"], tz)),
            "updDays": b["updDays"], "ageDays": whole_days(created, now) or 0,
            "urgency": urgency, "parent": ((f.get("parent") or {}).get("key")),
            "lastWord": last_word, "ownerLastComment": owner_last,
            "gaps": gaps, "mismatch": mismatch, "vendorRef": vendor_ref,
            "refLabel": _ref_label(ref_field) if ref_field else None,
        }
        mine, dt = t["lane"] == "mine", t["daysTo"]
        flags, tips = {}, {}
        for c in checks:
            ctype, tip = c["type"], c["name"]
            if ctype == "date_passed":
                fail = dt is not None and dt < 0 and t["lane"] != "waiting"
                tip = f"{c['name']}: {t['dateKind']} {t['dateText']}"
            elif ctype == "date_within":
                fail = mine and dt is not None and 0 <= dt <= fc["week_days"]
                tip = f"{c['name']}: {t['dateKind']} {t['dateText']}"
            elif ctype == "requester_spoke_last":
                fail = mine and bool(last_word and last_word["customer"])
                if fail:
                    tip = f"{c['name']}: {last_word['who']} commented {fmt_date(last_word['date'])}"
            elif ctype == "no_owner_comment":
                fail = t["ws"] == "support" and mine and (owner_age is None or owner_age >= fc["owner_update_days"])
            elif ctype == "no_movement":
                fail = mine and t["updDays"] >= fc["no_movement_days"]
                tip = f"{c['name']}: last update {_plural_days(t['updDays'])} ago"
            elif ctype == "product_qa_gaps":
                fail = bool(gaps)
                tip = f"{c['name']}: missing {join(gaps)}"
            elif ctype == "contradiction":
                fail = bool(mismatch)
                tip = f"{c['name']}: {mismatch}"
            else:  # parked_untouched
                fail = t["lane"] == "parked" and t["updDays"] >= fc["parked_untouched_days"]
                tip = f"{c['name']}: {_plural_days(t['updDays'])}"
            flags[c["id"]] = bool(fail)
            if fail:
                tips[c["id"]] = tip
        t["qa"], t["qaTips"] = flags, tips

        # Score: your-move items only, one reason clause per term.
        score, reasons = 0.0, []
        if mine:
            word = "target" if t["ws"] == "product" else "due"
            if dt is not None and dt < 0:
                score += sc["past_due_base"] + min(-dt, sc["past_due_cap_days"]) * sc["past_due_per_day"]
                reasons.append(f"{_plural_days(-dt)} past its {word}")
            elif dt is not None and dt <= fc["week_days"]:
                score += sc["week_base"] + (fc["week_days"] - dt) * sc["week_per_day_closer"]
                reasons.append(f"{word} today" if dt == 0 else f"{word} in {_plural_days(dt)}")
            elif dt is not None and dt <= fc["soon_days"]:
                score += sc["soon"]
                reasons.append(f"{word} in {_plural_days(dt)}")
            waited = False
            if last_word and last_word["customer"]:
                n = (today - date.fromisoformat(last_word["date"])).days
                score += sc["requester_waiting_base"] + min(n, sc["requester_waiting_cap_days"]) * sc["requester_waiting_per_day"]
                reasons.append(f"{last_word['who']} replied {_plural_days(n)} ago and is waiting on you")
                waited = True
            if flags.get(by_type.get("no_owner_comment", "")):
                score += sc["owner_update"]
                reasons.append(f"no update from you in {fc['owner_update_days']}+ days")
            if not waited and t["updDays"] >= fc["no_movement_days"]:
                score += sc["no_movement"]
                reasons.append(f"no movement in {_plural_days(t['updDays'])}")
            if urgency in (sc.get("high_urgency_values") or []):
                score += sc["high_urgency"]
            if mismatch:
                score += sc["contradiction"]
        t["score"] = round(score + 1e-9, 1)
        t["reasons"] = reasons
        t["why"] = (cap("; ".join(reasons)) + ".") if reasons else ""
        items.append(t)

    def rank_key(t):
        return (-t["score"], t["daysTo"] if t["daysTo"] is not None else 10**9, key_sort(t["key"]))

    mine_items = sorted([t for t in items if t["lane"] == "mine"], key=rank_key)
    waiting = sorted([t for t in items if t["lane"] == "waiting"], key=lambda t: (t["updDays"], key_sort(t["key"])))
    parked = sorted([t for t in items if t["lane"] == "parked"], key=lambda t: (-t["updDays"], key_sort(t["key"])))
    items = mine_items + waiting + parked
    scored = [t for t in mine_items if t["score"] > 0]
    next_moves = [t["key"] for t in scored[:fc["next_moves_count"]]]

    for t in waiting:
        if t["waitingOn"] == "requester":
            lw = t["lastWord"]
            who = (f"You replied {fmt_date(lw['date'])}; waiting on the requester" if lw and lw["who"] == owner
                   else "Waiting on the requester")
        else:
            who = (f"With {t['waitingOn']} ({t['vendorRef']})" if t["vendorRef"]
                   else f"With {t['waitingOn']}, with no {t['refLabel']} yet" if t["refLabel"] else f"With {t['waitingOn']}")
            who += f"; status {t['status']}"
        ago = "today" if t["updDays"] == 0 else "yesterday" if t["updDays"] == 1 else f"{t['updDays']} days ago"
        t["waitingText"] = f"{who}. Last update {ago}."

    cu_id, od_id = by_type.get("parked_untouched"), by_type.get("date_passed")
    tidy = [t for t in parked if t["qa"].get(cu_id) or t["qa"].get(od_id)]
    for t in tidy:
        bits = []
        if t["roadmap"]:
            bits.append(f"Roadmap {t['roadmap']}")
        bits.append(f"untouched {_plural_days(t['updDays'])}")
        if t["qa"].get(od_id):
            bits.append(f"{'target' if t['ws'] == 'product' else 'due date'} passed {fmt_date(t['date'])}")
        t["tidyText"] = cap(", ".join(bits)) + "."
    mm_id, pg_id = by_type.get("contradiction"), by_type.get("product_qa_gaps")
    fix = sorted([t for t in items if t["qa"].get(mm_id) or t["qa"].get(pg_id)], key=rank_key)
    for t in fix:
        parts = ([t["mismatch"] + "."] if t["mismatch"] else []) + ([f"Missing {join(t['gaps'])}."] if t["gaps"] else [])
        t["fixText"] = " ".join(parts)

    # Timeline.
    start = today.replace(day=1)
    end = start
    for _ in range(max(1, fc["timeline_months"]) - 1):
        end = month_end(end) + timedelta(days=1)
    end = month_end(end)
    s_iso, e_iso = start.isoformat(), end.isoformat()
    timeline = {"start": s_iso, "end": e_iso, "today": tiso,
                "plusWeek": (today + timedelta(days=fc["week_days"])).isoformat(), "rows": []}
    for ws in WORKSPACES:
        dated = [t for t in items if t["ws"] == ws and t["date"]]
        pts, bars = [], []
        for t in sorted(dated, key=lambda t: (t["date"], key_sort(t["key"]))):
            rng = t["target"] if t["target"] and t["target"][0] != t["target"][1] else None
            a, z = (rng[0], rng[1]) if rng else (t["date"], t["date"])
            if rng and z >= s_iso and a <= e_iso:
                bars.append({"key": t["key"], "start": a, "end": z, "label": f"{t['key']} {fmt_range(rng)}"})
            else:
                pos = "earlier" if z < s_iso else "later" if a > e_iso else t["date"]
                pts.append({"key": t["key"], "pos": pos})
        timeline["rows"].append({"ws": ws, "name": WS_NAMES[ws], "count": len(dated), "points": pts, "bars": bars})

    def count(cid, arr):
        return sum(1 for t in arr if t["qa"].get(cid))

    views = {}
    for ws in [""] + WORKSPACES:
        sub = [t for t in items if not ws or t["ws"] == ws]
        views[ws] = {"total": len(sub), "checkCounts": {c["id"]: count(c["id"], sub) for c in checks}}

    yc = count(by_type.get("requester_spoke_last"), items)
    odm = count(od_id, mine_items)
    wk = count(by_type.get("date_within"), items)

    def nw(n):
        return num_word(n) if n else "no"
    headline = (f"{cap(nw(yc))} {'person is' if yc == 1 else 'people are'} waiting on you, {nw(odm)} of your items "
                f"{'is' if odm == 1 else 'are'} past due, and {nw(wk)} more land{'s' if wk == 1 else ''} in the next "
                f"{num_word(fc['week_days']) if fc['week_days'] < 10 else fc['week_days']} days.")
    subhead = (f"You own {len(items)} open items: {len(mine_items)} are your move, {len(waiting)} are waiting on someone else, "
               f"and {len(parked)} are parked. {count(cu_id, items)} parked items haven’t moved in {fc['parked_untouched_days']}+ days, "
               f"and {count(pg_id, items)} committed roadmap ideas are missing required fields.")
    caption = (f"Ranked by a fixed score: past-due dates first, then dates in the next {num_word(fc['week_days']) if fc['week_days'] < 10 else fc['week_days']} days, "
               f"then people waiting on a reply, then items that have gone quiet. {len(scored)} of your {len(mine_items)} your-move items "
               f"score today; the top {len(next_moves)} are shown.")

    spec = load_design_spec(DESIGN_PATH)
    spec.insert(2, ["Next-moves score", score_text(fc)])
    keys = [k for ws in WORKSPACES for k in plan["groups"][ws]]
    dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][today.weekday()]
    return {
        "generated": tiso,
        "owner": owner,
        "site": plan["site"],
        "title": f"Focus for {owner}, {fmt_date(tiso)}",
        "eyebrow": f"Focus for {owner}, {dow} {fmt_date(tiso)}",
        "headline": headline,
        "subhead": subhead,
        "movesCaption": caption,
        "workspaces": [{"id": ws, "name": WS_NAMES[ws], "count": views[ws]["total"]} for ws in WORKSPACES],
        "lanes": [{"id": l, "name": n} for l, n in LANES],
        "checks": [{"id": c["id"], "name": c["name"], "rule": c["rule"], "role": c.get("color_role", "ink")} for c in checks],
        "views": views,
        "nextMoves": next_moves,
        "waiting": [t["key"] for t in waiting],
        "tidy": [t["key"] for t in tidy],
        "fix": [t["key"] for t in fix],
        "timeline": timeline,
        "items": items,
        "spec": spec,
        "sourceLine": f"Source: Jira projects {join(keys)} on {plan['cloud_id']}, items assigned to you and not done, read {fmt_date(tiso)}. Read-only; nothing in Jira was changed.",
        "counts": {"open": len(items), "mine": len(mine_items), "waiting": len(waiting), "parked": len(parked),
                   "scored": len(scored), "nextMoves": len(next_moves)},
    }


def score_text(fc):
    s = fc["score"]

    def n(v):
        return f"{v:g}"
    return (f"Your-move items only. Past its date: {n(s['past_due_base'])} plus {n(s['past_due_per_day'])} per day late "
            f"(capped at {n(s['past_due_cap_days'])} days). Date within {fc['week_days']} days: {n(s['week_base'])} plus "
            f"{n(s['week_per_day_closer'])} per day closer. Date in {fc['week_days'] + 1}–{fc['soon_days']} days: {n(s['soon'])}. "
            f"Requester spoke last: {n(s['requester_waiting_base'])} plus {n(s['requester_waiting_per_day'])} per day waiting "
            f"(capped at {n(s['requester_waiting_cap_days'])} days). No update from you in {fc['owner_update_days']}+ days: "
            f"{n(s['owner_update'])}. No movement in {fc['no_movement_days']}+ days, when nobody is waiting on a reply: "
            f"{n(s['no_movement'])}. {join(s.get('high_urgency_values') or [])} urgency: {n(s['high_urgency'])}. "
            f"Contradicting record: {n(s['contradiction'])}. Ties break by nearest date, then key. Top {fc['next_moves_count']} shown.")


# --- rendering --------------------------------------------------------------

def render_html(payload, plan, fonts_dir=None, template_path=TEMPLATE_PATH):
    enabled = [c for c in plan["focus"]["checks"] if c.get("enabled", True)]
    # The prototype shows every focus check in one row.
    return render_page(template_path, payload, plan["palette"], enabled, LEDGER_MAX_COLS, fonts_dir, single_row=True)


def render_markdown(payload):
    by = {t["key"]: t for t in payload["items"]}
    out = [f"# {payload['eyebrow']}", "", f"**{payload['headline']}** {payload['subhead']}", "", "## Your next moves", "",
           payload["movesCaption"], ""]
    out += [f"{n}. [{k}]({by[k]['url']}) {md_cell(by[k]['summary'])}: {by[k]['why']}" for n, k in enumerate(payload["nextMoves"], 1)] or ["_None._"]
    out += ["", "## Waiting on someone else", ""]
    out += [f"- [{k}]({by[k]['url']}) {md_cell(by[k]['summary'])}: {by[k]['waitingText']}" for k in payload["waiting"]] or ["_None._"]
    out += ["", f"## Close, reschedule, or hand off ({len(payload['tidy'])})", ""]
    out += [f"- [{k}]({by[k]['url']}) {md_cell(by[k]['summary'])}: {by[k]['tidyText']}" for k in payload["tidy"]] or ["_None._"]
    out += ["", f"## Fix the record ({len(payload['fix'])})", ""]
    out += [f"- [{k}]({by[k]['url']}) {md_cell(by[k]['summary'])}: {by[k]['fixText']}" for k in payload["fix"]] or ["_None._"]
    return "\n".join(out) + "\n"
