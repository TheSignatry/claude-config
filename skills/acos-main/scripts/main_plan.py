#!/usr/bin/env python3
"""Orchestration + composition engine for acos-main.

Like every sibling in the acos family, this script never calls an MCP tool
itself — Claude does that, following the exact instructions each subcommand
hands back. Two kinds of subcommands:

  morning-plan / week-plan / month-retro
      Resolve the relevant date range(s) and emit an explicit orchestration
      checklist: which sibling skill commands to run, with what parameters,
      in what order, and which steps are independent (parallelizable) versus
      sequential. This script never runs acos-calendar-analysis,
      acos-jira-analysis, or acos-email-sort itself — it only names them.

  compose
      Takes the already-fetched sibling outputs (each sibling's own `report`
      JSON, already computed by that sibling's own script) and derives the
      few genuinely new pieces of cross-cutting logic that belong in none of
      them: which meetings/emails count as "important" for the highlight
      list, the category-to-color mapping applied to real hours (see
      references/visual_system.md), and — for month-retro — the prior-month
      diff and the email-history rollup. It returns structured JSON; Claude
      authors the actual HTML/SVG/prose from that, exactly as the real
      `/morning` skill does (no script anywhere in this family builds HTML).

Date resolution conventions:
  morning-plan -- "today," unless a --date override is given.
  week-plan    -- the Monday-Sunday week containing --date, but if --date
                  (or today, when no override is given) falls on a day other
                  than Monday, resolve to the *next* Monday-Sunday week
                  instead -- same rule the retired `cos` skill used, kept
                  here for continuity since this is the forward planning
                  ritual it replaces.
  month-retro  -- the calendar month *before* --date's month (or before
                  today's month, with no override) -- i.e. the last fully
                  completed month by default. The "prior month" used for
                  comparison is the one before that.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_ABOUTME_PATH = "../acos-aboutme/state/profile.json"

CATEGORY_COLORS = {
    "Focused production": "#2b7a78",
    "People leadership": "#d77900",
    "External ecosystem": "#37a49f",
    "Operating rhythm": "#8a1e41",
    "Strategy and transformation": "#fd4a5c",
    "Stakeholder partnership": "#f2a65a",
    "Capacity unavailable": "#a2a7aa",
    "Margin / Flex capacity": "#def2f1",
}


def _fail(message):
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(1)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _ref_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()


def resolve_week(ref_date):
    """This week if ref_date is Monday, otherwise the coming one -- see
    module docstring."""
    days_until_monday = (7 - ref_date.weekday()) % 7
    start = ref_date if ref_date.weekday() == 0 else ref_date + timedelta(days=days_until_monday)
    return start, start + timedelta(days=6)


def resolve_retro_month(ref_date):
    """Returns (target_start, target_end, prior_start, prior_end) -- the
    last fully completed month before ref_date's month, and the one before
    that."""
    this_month_start = ref_date.replace(day=1)
    target_end = this_month_start - timedelta(days=1)
    target_start = target_end.replace(day=1)
    prior_end = target_start - timedelta(days=1)
    prior_start = prior_end.replace(day=1)
    return target_start, target_end, prior_start, prior_end


# --- CLI commands: orchestration checklists -----------------------------------


def cmd_morning_plan(args):
    today = _ref_date(args.date)
    checklist = {
        "perspective": "morning-plan",
        "date": today.isoformat(),
        "steps": [
            {
                "order": 1,
                "skill": "acos-email-sort",
                "action": (
                    "Run the full live-sort flow exactly as documented in acos-email-sort/SKILL.md "
                    "(folder gate, sweep 4_autorespond, gather/classify/move the Inbox, monitor "
                    "6_bulkToReview) -- this is the one step in acos-main that mutates anything, "
                    "and only morning-plan ever triggers it."
                ),
                "then": [
                    "Write state/last_run_summary.json and append to state/run_history.jsonl, per that skill's own SKILL.md.",
                    "Do one lightweight, read-only outlook_email_search on the just-sorted 1_priority folder (and 2_review, if anything there looks worth surfacing) to get the actual message list -- last_run_summary.json only carries bucket counts, not per-message detail.",
                ],
            },
            {
                "order": 2,
                "parallel_with": 3,
                "skill": "acos-calendar-analysis",
                "action": f"Run scripts/calendar_report.py plan --period day --date {today.isoformat()} --aboutme {DEFAULT_ABOUTME_PATH}, fetch, then report --format json.",
                "note": "Day mode has no time_allocation/benchmark section -- that's expected, not a gap.",
            },
            {
                "order": 3,
                "parallel_with": 2,
                "skill": "acos-jira-analysis",
                "action": f"Run scripts/jira_report.py plan --aboutme {DEFAULT_ABOUTME_PATH}, fetch, then report --format json.",
                "note": "No --since/--until needed here -- morning-plan only needs the standard overdue/upcoming buckets, filtered to today by `compose`.",
            },
            {
                "order": 4,
                "action": (
                    "Run scripts/main_plan.py compose --perspective morning-plan --calendar <calendar report.json> "
                    "--jira <jira report.json> --email-run <last_run_summary.json> --email-current <1_priority/2_review "
                    "messages.json> --today " + today.isoformat() + " to get the highlight sets, then author the HTML "
                    "artifact per references/visual_system.md."
                ),
            },
        ],
    }
    print(json.dumps(checklist, indent=2))


def cmd_week_plan(args):
    ref = _ref_date(args.date)
    start, end = resolve_week(ref)
    checklist = {
        "perspective": "week-plan",
        "week": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "steps": [
            {
                "order": 1,
                "parallel_with": 2,
                "skill": "acos-calendar-analysis",
                "action": f"Run scripts/calendar_report.py plan --period week --date {start.isoformat()} --aboutme {DEFAULT_ABOUTME_PATH}, fetch, then report --format json.",
                "note": "Week mode includes time_allocation + benchmark -- the source for the segmented day bars.",
            },
            {
                "order": 2,
                "parallel_with": 1,
                "skill": "acos-jira-analysis",
                "action": f"Run scripts/jira_report.py plan --aboutme {DEFAULT_ABOUTME_PATH}, fetch, then report --format json.",
                "note": "product_detail's window is already 14 days by the profile's own default (jira_workspaces.upcoming_window_days) -- matches the '2-week product window' ask with no override needed. If that default is ever changed to something other than 14, pass an explicit note in the artifact rather than silently reporting a different window than what was asked for.",
            },
            {
                "order": 3,
                "action": (
                    "Read-only outlook_email_search on 1_priority and 2_review (current contents -- "
                    "no email-sort run triggered here; only morning-plan mutates mail)."
                ),
            },
            {
                "order": 4,
                "action": (
                    "Run scripts/main_plan.py compose --perspective week-plan --calendar <calendar report.json> "
                    "--jira <jira report.json> --email-current <1_priority/2_review messages.json> to get the "
                    "per-day category-segment data and benchmark-status summary, then author the HTML artifact "
                    "per references/visual_system.md."
                ),
            },
        ],
    }
    print(json.dumps(checklist, indent=2))


def cmd_month_retro(args):
    ref = _ref_date(args.date)
    target_start, target_end, prior_start, prior_end = resolve_retro_month(ref)
    checklist = {
        "perspective": "month-retro",
        "target_month": {"start_date": target_start.isoformat(), "end_date": target_end.isoformat()},
        "prior_month": {"start_date": prior_start.isoformat(), "end_date": prior_end.isoformat()},
        "steps": [
            {
                "order": 1,
                "parallel_with": 2,
                "skill": "acos-calendar-analysis",
                "action": f"Run scripts/calendar_report.py plan --period month --date {target_start.isoformat()} --aboutme {DEFAULT_ABOUTME_PATH}, fetch, then report --format json.",
            },
            {
                "order": 2,
                "parallel_with": 1,
                "skill": "acos-calendar-analysis",
                "action": f"Repeat for the prior month: plan --period month --date {prior_start.isoformat()} --aboutme {DEFAULT_ABOUTME_PATH}, fetch, then report --format json.",
                "note": "Two independent report calls, not a sibling-skill change -- Outlook retains full history, so any past month can be recomputed live.",
            },
            {
                "order": 3,
                "skill": "acos-jira-analysis",
                "action": (
                    f"Run scripts/jira_report.py plan --aboutme {DEFAULT_ABOUTME_PATH} "
                    f"--since {target_start.isoformat()} --until {target_end.isoformat()}, fetch (including the "
                    "extra product_delivered/support_resolved queries this adds), then report --format json."
                ),
            },
            {
                "order": 4,
                "skill": "acos-email-sort",
                "action": (
                    "Read state/run_history.jsonl, filter lines whose \"date\" falls within the target month."
                ),
                "note": (
                    "Thin or empty until enough real runs accumulate after this shipped -- an inherent bootstrap "
                    "limitation, not a bug. Say so plainly in the artifact rather than presenting a sparse result "
                    "as a real trend."
                ),
            },
            {
                "order": 5,
                "action": (
                    "Run scripts/main_plan.py compose --perspective month-retro --calendar <target month report.json> "
                    "--prior-calendar <prior month report.json> --jira <jira report.json with delivered/resolved "
                    "sections> --email-history <filtered run_history.jsonl lines, as a JSON array> to get the "
                    "category deltas, delivered-products list, support-ticket-performance stats, and email-volume "
                    "rollup, then author the HTML artifact per references/visual_system.md."
                ),
            },
        ],
    }
    print(json.dumps(checklist, indent=2))


# --- compose: cross-cutting composition logic ---------------------------------


def _meeting_is_important(event, conflicts, needing_prep_ids):
    if event.get("id") in needing_prep_ids:
        return True
    for c in conflicts.get("double_bookings", []):
        if event.get("id") in (c["event_a"].get("id"), c["event_b"].get("id")):
            return True
    return False


def _jira_urgent(jira_report, today_str):
    """Overdue items, or upcoming items due exactly today -- the 'urgent or
    due' framing morning-plan asks for. Works across whichever of
    product_detail/support_detail/work_detail are present."""
    urgent = []
    for group_key, date_key in (("product_detail", "target_end"), ("support_detail", "due"), ("work_detail", "due")):
        for row in jira_report.get(group_key, []):
            if row["bucket"] == "overdue" or (row["bucket"] == "upcoming" and row.get(date_key) == today_str):
                urgent.append(dict(row, group=group_key.replace("_detail", "")))
    return urgent


def _day_breakdown(events, daily_time_allocation=None):
    """Per-day category-hours plus the raw per-event list, for week-plan's
    time-of-day-axis day chart -- the week-level time_allocation
    calendar_report.py already computes has no day-by-day split, so a
    day-by-day view is new cross-cutting logic that belongs here, not in a
    sibling.

    2026-08-14: this function originally summed each event's own duration
    per day, subtracting only documented deep-work-block infringements. That
    still double-counted any overlap between two real (non-block) meetings
    -- e.g. Tuesday's 15-minute HubSpot/Weekly-Boss-Chat overlap -- because
    it isn't a "deep work infringement," just two real meetings double
    booked. calendar_report.py's own compute_time_allocation already solves
    this whole class of problem with a priority-ordered interval sweep
    (_accumulate_category_seconds); compute_daily_time_allocation reuses
    that exact logic per day. So category-hour totals below come straight
    from the sibling's daily_time_allocation report field, matched by
    weekday name -- do not re-derive hour totals from raw event durations
    here again.

    The raw per-event list is unrelated to that fix and still reflects real
    (possibly overlapping) calendar events, since the time-axis chart is
    meant to show overlaps visually -- e.g. two meetings sharing a lane --
    not hide them."""
    hours_by_weekday = {d["weekday"]: d for d in (daily_time_allocation or [])}

    days = {}
    for e in events:
        if e.get("is_all_day"):
            continue
        date_str = e.get("date", "")
        day_name = date_str.split(",")[0] if date_str else "Unknown"
        day = days.setdefault(day_name, {"date": date_str, "day_name": day_name, "events": []})
        day["events"].append({
            "id": e.get("id"), "subject": e.get("subject"), "category": e.get("category"),
            "start": e.get("start"), "end": e.get("end"), "duration_minutes": e.get("duration_minutes") or 0,
        })

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = []
    for day_name in order:
        if day_name not in days:
            continue
        day = days[day_name]
        alloc = hours_by_weekday.get(day_name, {})
        day["categories"] = alloc.get("categories", {})
        day["free_hours"] = alloc.get("free_hours", 0)
        day["total_hours"] = round(sum(day["categories"].values()), 2)
        out.append(day)
    return out


def _category_bars(time_allocation, benchmark=None):
    """One entry per category with its color, hours, pct, and (if a
    benchmark was computed) status -- ready for a segmented bar or mini-chart,
    no further lookup needed at render time."""
    bars = []
    for cat, color in CATEGORY_COLORS.items():
        if cat == "Margin / Flex capacity":
            hours = time_allocation.get("free_time", {}).get("hours", 0)
            pct = time_allocation.get("free_time", {}).get("pct", 0)
        elif cat == "Capacity unavailable":
            hours = time_allocation.get("capacity_unavailable_hours", 0)
            pct = None
        else:
            cat_data = time_allocation.get("categories", {}).get(cat, {})
            hours = cat_data.get("hours", 0)
            pct = cat_data.get("pct", 0)
        entry = {"category": cat, "color": color, "hours": hours, "pct": pct}
        if benchmark and cat in benchmark.get("categories", {}):
            entry["benchmark_status"] = benchmark["categories"][cat]["status"]
            entry["target_range"] = benchmark["categories"][cat]["target_range"]
        bars.append(entry)
    return bars


def cmd_compose(args):
    perspective = args.perspective
    calendar_report = load_json(args.calendar) if args.calendar else None
    jira_report = load_json(args.jira) if args.jira else None
    email_run = load_json(args.email_run) if args.email_run else None
    email_current = load_json(args.email_current) if args.email_current else None

    result = {"perspective": perspective}

    if perspective == "morning-plan":
        today_str = args.today or date.today().isoformat()
        needing_prep_ids = {m["id"] for m in calendar_report.get("meetings_needing_prep", [])} if calendar_report else set()
        important_meetings = [
            e for e in (calendar_report.get("events", []) if calendar_report else [])
            if _meeting_is_important(e, calendar_report.get("conflicts", {}), needing_prep_ids)
        ]
        result["important_meetings"] = important_meetings
        result["conflicts"] = calendar_report.get("conflicts", {}) if calendar_report else {}
        result["jira_urgent"] = _jira_urgent(jira_report, today_str) if jira_report else []
        result["email_run_summary"] = email_run
        result["email_current"] = email_current or []

    elif perspective == "week-plan":
        time_allocation = calendar_report.get("time_allocation", {}) if calendar_report else {}
        benchmark = calendar_report.get("benchmark") if calendar_report else None
        schedule_health = calendar_report.get("schedule_health", {}) if calendar_report else {}
        deep_work_infringements = schedule_health.get("deep_work_infringements")
        result["category_bars"] = _category_bars(time_allocation, benchmark)
        result["day_breakdown"] = _day_breakdown(
            calendar_report.get("events", []) if calendar_report else [],
            calendar_report.get("daily_time_allocation", []) if calendar_report else [],
        )
        needing_prep_ids = {m["id"] for m in calendar_report.get("meetings_needing_prep", [])} if calendar_report else set()
        result["key_meetings"] = [
            e for e in (calendar_report.get("events", []) if calendar_report else [])
            if _meeting_is_important(e, calendar_report.get("conflicts", {}), needing_prep_ids)
        ]
        result["double_bookings"] = calendar_report.get("conflicts", {}).get("double_bookings", []) if calendar_report else []
        # Deep-work and personal-time infringements, straight from
        # calendar_report.py's own schedule_health -- no new computation
        # needed, just surfaced as its own section per Trevor's request.
        result["calendar_infringements"] = {
            "deep_work": deep_work_infringements or {"blocks": [], "total_infringements": 0},
            "after_hours": schedule_health.get("personal_time_infringement", {}).get("after_hours", {"count": 0, "total_hours": 0, "events": []}),
            "pto_interruptions": schedule_health.get("personal_time_infringement", {}).get("pto_interruptions", {"total_infringements": 0, "blocks": []}),
        }
        result["product_deliveries"] = jira_report.get("product_detail", []) if jira_report else []
        result["support_tickets"] = jira_report.get("support_detail", []) if jira_report else []
        result["critical_emails"] = email_current or []

    elif perspective == "month-retro":
        prior_calendar_report = load_json(args.prior_calendar) if args.prior_calendar else None
        target_bars = _category_bars(
            calendar_report.get("time_allocation", {}) if calendar_report else {},
            calendar_report.get("benchmark") if calendar_report else None,
        )
        prior_bars = _category_bars(
            prior_calendar_report.get("time_allocation", {}) if prior_calendar_report else {},
        )
        prior_by_cat = {b["category"]: b for b in prior_bars}
        for b in target_bars:
            prior = prior_by_cat.get(b["category"], {})
            b["prior_month_pct"] = prior.get("pct")
            b["prior_month_delta"] = (
                round(b["pct"] - prior["pct"], 1)
                if b.get("pct") is not None and prior.get("pct") is not None
                else None
            )
        result["category_bars"] = target_bars
        result["delivered_products"] = (jira_report.get("delivered_in_range", {}).get("items", []) if jira_report else [])
        result["support_ticket_performance"] = (jira_report.get("resolved_in_range", {}).get("support", {}) if jira_report else {})

        email_history = load_json(args.email_history) if args.email_history else []
        totals = {}
        for entry in email_history:
            for bucket, n in entry.get("counts", {}).items():
                totals[bucket] = totals.get(bucket, 0) + n
        result["email_volume"] = {
            "runs_in_month": len(email_history),
            "totals_by_bucket": totals,
            "total_declines": sum(e.get("declines", 0) for e in email_history),
            "total_filed_without_action": sum(e.get("filed_without_action", 0) for e in email_history),
            "thin_data": len(email_history) < 5,
        }

    else:
        _fail(f"unknown perspective: {perspective}")

    print(json.dumps(result, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_morning = sub.add_parser("morning-plan", help="Emit the orchestration checklist for a single day's brief")
    p_morning.add_argument("--date", default=None, help="Reference date YYYY-MM-DD (default: today)")
    p_morning.set_defaults(func=cmd_morning_plan)

    p_week = sub.add_parser("week-plan", help="Emit the orchestration checklist for the upcoming Mon-Sun week")
    p_week.add_argument("--date", default=None, help="Reference date YYYY-MM-DD (default: today)")
    p_week.set_defaults(func=cmd_week_plan)

    p_month = sub.add_parser("month-retro", help="Emit the orchestration checklist for the last completed month")
    p_month.add_argument("--date", default=None, help="Reference date YYYY-MM-DD (default: today)")
    p_month.set_defaults(func=cmd_month_retro)

    p_compose = sub.add_parser("compose", help="Merge already-fetched sibling reports into the cross-cutting composition JSON")
    p_compose.add_argument("--perspective", required=True, choices=["morning-plan", "week-plan", "month-retro"])
    p_compose.add_argument("--calendar", default=None, help="Path to acos-calendar-analysis's report.json")
    p_compose.add_argument("--prior-calendar", default=None, dest="prior_calendar", help="Path to the prior month's report.json (month-retro only)")
    p_compose.add_argument("--jira", default=None, help="Path to acos-jira-analysis's report.json")
    p_compose.add_argument("--email-run", default=None, dest="email_run", help="Path to acos-email-sort's last_run_summary.json (morning-plan only)")
    p_compose.add_argument("--email-current", default=None, dest="email_current", help="Path to a JSON array of current 1_priority/2_review messages")
    p_compose.add_argument("--email-history", default=None, dest="email_history", help="Path to a JSON array of run_history.jsonl lines filtered to the target month (month-retro only)")
    p_compose.add_argument("--today", default=None, help="Override today's date, YYYY-MM-DD (for testing / explicit runs)")
    p_compose.set_defaults(func=cmd_compose)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
