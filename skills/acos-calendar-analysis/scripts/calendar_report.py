#!/usr/bin/env python3
"""Deterministic engine for acos-calendar-analysis.

Two-stage pipeline, mirroring acos-jira-analysis's plan/report split:

  plan     Resolves the requested period (day/week/month) against a reference
             date and emits the exact outlook_calendar_search parameters to
             fetch, plus the relevant acos-aboutme profile carried forward
             so `report` never re-reads that file itself.
  report   Takes the plan plus every fetched event (all pages concatenated)
             and computes the full structured result: primary-category
             classification (Step 3, 1-5b), tags (Step 4), conflicts,
             schedule health, meetings-needing-prep, and -- for week/month
             periods only -- the free-time gap-found time-allocation
             breakdown and benchmark comparison. Prints JSON (default) or
             renders markdown.

Ported from agentic-cos/src/cos/workflows/weekly_preview.py, adjusted for
this connector's actual data shape (confirmed empirically 2026-08-10 against
a live outlook_calendar_search call, not assumed):

  - Attendees are bare email strings (`event["attendees"] == ["a@x.com", ...]`
    or null), never `{emailAddress: {name, address}}` objects. All matching
    is by email/domain, never by name, per this skill's ground rules.
  - `recurrence` is populated as null on every event checked, INCLUDING
    obviously-recurring series ("Monday AM Devotional", "DVR Weekly Call",
    "Department Reports", "StratOp Scrub"). Confirmed unreliable -- Cadence's
    recurring/ad-hoc base signal comes from a known_meeting_series match
    instead, per Step 2's own fallback instruction.
  - `categories` (Outlook's own category tags) is also null on every event
    checked, including a `showAs: "oof"` PTO event. Capacity-unavailable
    detection still checks it defensively (for whenever it does get used)
    but in practice leans on `showAs`/subject keywords.
  - `start`/`end` `dateTime` strings are wall-clock in the paired `timeZone`
    (the mailbox's own tz, e.g. "Eastern Standard Time" -- a Windows tz
    name, not IANA), per outlook_calendar_search's own tool description.
    No UTC attach/convert dance is needed or done here -- every dateTime is
    parsed as a naive local datetime and compared directly, since working
    hours (acos-aboutme) are configured in that same local frame.
  - The connector strips attendee type/status metadata entirely (no
    "resource" flag for room bookings, unlike the raw Graph API shape
    weekly_preview.py assumed) -- a room resource booked as an attendee
    will count as a participant here. Known limitation, not worked around.
  - The organizer is sometimes included in `attendees` and sometimes not
    (observed both ways on real data). `_participants()` builds the
    participant set from organizer + attendees + the owner's own email,
    unioned, so "total attendees" and "other participants" are correct
    regardless of which shape a given event happens to use.

Deliberate corrections made to a literal reading of the build spec, each
because real calendar data broke the literal ordering (call these out if
they ever look wrong against more data -- they were judgment calls, not
copied verbatim from the spec):

  - Step 3.5b lists its three audience-default rules as Shepherd, then
    spans-multiple-areas, then Team/Reports-only, in that textual order.
    Implemented here as Shepherd, then Team/Reports-only, THEN
    spans-multiple-areas -- because Trevor's own `reports`/`team` already
    spans multiple functional areas internally (Security + Systems +
    Engineering + Data), so his own "Hump Day Huddle" (entirely
    reports/team) would otherwise misclassify as Stakeholder partnership
    before ever reaching the Operating-rhythm check. The narrower rule
    (a subset match) is checked before the broader one.
  - The Audience tag's Shepherd/board checks only count a match whose
    email domain is the owner's own internal domain. `vip_senders` mixes
    internal executives with external partner contacts kept there for
    email-priority reasons (e.g. Lucas Cherry, Give Interactive) -- without
    this restriction, a meeting with an external VIP-listed partner alone
    would misread as "Shepherd/executive" instead of "existing partner".
  - `_is_schedulable` (the "real meeting" predicate feeding conflict
    detection, schedule health, and prep flags) excludes both Focused
    production AND Capacity unavailable categories, not just Focused
    production as the spec's conflicts section literally says. A
    Capacity-unavailable block is not itself a "real meeting" that can
    double-book in the traditional sense; its overlap with real meetings
    is handled by the dedicated PTO-interruption check instead.
  - Time-allocation percentages are computed only over each day's
    configured working-hours window, with every event's duration clipped
    to that window before counting. This was necessary for internal
    consistency: the denominator is explicitly defined as
    scheduled-plus-free time WITHIN working hours (free time can only be
    gap-found inside a bounded window), so counting an after-hours
    meeting's full duration in the numerator while the denominator stays
    working-hours-bounded would let percentages exceed the whole. After-
    hours time is already tracked separately under schedule_health.
  - Category hours within that window are attributed via a sweep (see
    `_accumulate_category_seconds`), not by summing each event's clipped
    duration independently. Found via smoke test: summing independently
    double-counts every second of overlap between events (a real meeting
    double-booked against another, or a real meeting during a Focused-
    production block) once per overlapping event, so the total inflated
    3.6h beyond the true 45h weekday window on a single 3-day sample.
    Focused production always loses an overlap to a real, more specific
    commitment (a double-booked "focus" hour was actually spent on
    whatever else was scheduled); among same-priority overlaps the
    earlier-starting event wins -- an arbitrary but deterministic
    tie-break, since which of two mutually double-booked meetings gets
    the credited hour is inherently ambiguous (that ambiguity itself is
    surfaced separately via the conflicts double-bookings list).
  - Personal travel/lodging blocks (a booked flight, a hotel stay, a rental
    car) very often don't contain the word "travel" at all -- found via a
    real June sample where a 4-day hotel stay ("Bellagio Resort & Casino")
    and flight blocks ("SW 1102: BWI to LAS", "Southwest Airlines flight
    1102 to Las Vegas (A6OR2V)") all fell through to Focused production
    instead of Capacity unavailable, since none matched any subject
    keyword. Added two more zero-attendee-only signals alongside the
    existing solo keywords: a confirmation/reservation-number pattern
    checked against subject AND body (these auto-generated or
    self-booked events reliably carry one, e.g. "Confirmation code:
    A6OR2V", "Acknowledgement Number: 3P6JQFY10"), and a bare
    3-letter-airport-code pair in the subject ("BWI to LAS") for the
    shorthand style that has no useful body text to scan. Also moved bare
    "travel" (previously only the narrower phrase "travel to") into the
    zero-attendee-only bucket rather than the unconditional one -- it's a
    real, intentional signal on a solo block ("Travel - BWI") but too
    generic to trust against a real multi-person meeting (a travel-policy
    or travel-budget discussion legitimately has "travel" in its subject
    too).

No subcommand here calls an O365 tool or creates/edits/deletes a calendar
event -- calendar access itself is read-only, always. The one deliberate
exception to "never writes to acos-aboutme's profile" is the `correct`
subcommand (Step 4): it writes ONLY to `calendar_analysis.known_meeting_series`
in that shared profile, exactly the single sub-key acos-aboutme's own SKILL.md
already documents as this skill's to write -- every other field there stays
untouched and unread-by-write. `correct` is for STICKY corrections on a
recurring series only; a one-off correction on a non-recurring event belongs
in an `--llm-resolutions` file for `report` instead (Step 3's mechanism,
reused here) and should never call `correct` at all -- that judgment call
(is this actually recurring?) is the orchestration layer's (SKILL.md, Step 5),
not something this script infers on its own.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_ABOUTME_PATH = "../acos-aboutme/state/profile.json"

WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

PRIMARY_CATEGORIES = [
    "Capacity unavailable",
    "Focused production",
    "People leadership",
    "External ecosystem",
    "Operating rhythm",
    "Strategy and transformation",
    "Stakeholder partnership",
]
BENCHMARK_CATEGORIES = [c for c in PRIMARY_CATEGORIES if c != "Capacity unavailable"]

# --- Structural signal patterns (Step 3 categories 1-2, Step 4 tags) -------

WORKING_BLOCK_PATTERN = re.compile(r"\bworking block\b", re.IGNORECASE)

CAPACITY_UNAVAILABLE_KEYWORDS = re.compile(
    r"\b(vacation|pto|holiday|medical leave|personal day|personal appt|"
    r"personal appointment|sick day|bereavement|jury duty|out of office|ooo|"
    r"commute|recovery block)\b",
    re.IGNORECASE,
)
# Zero-attendee-only: these are far too generic to trust unconditionally --
# found via real data that "Dr. B Mid month zoom meeting" is a genuine work
# meeting (Ben Clarke, Aril Brizendine, and an external security consultant
# nicknamed "Dr. B") that would misclassify as a personal doctor's
# appointment if this fired regardless of attendees. Scoped exactly to what
# was actually asked for: a signal for a *personal appointment*, which by
# definition has no real attendees -- a meeting with people on the calendar
# is not a personal appointment no matter what word appears in its subject.
# Bare "travel" lives here rather than in the unconditional bucket above for
# the same reason -- "Travel - BWI" (zero attendees) should match, but a real
# travel-policy or travel-budget meeting with real attendees legitimately
# has "travel" in its subject too.
CAPACITY_UNAVAILABLE_SOLO_KEYWORDS = re.compile(
    r"\b(dr\.?|doctor|dentist|dental|appointment|travel)\b", re.IGNORECASE
)
# Auto-generated (or self-booked) travel/lodging/rental-car confirmations
# reliably carry a confirmation/reservation code even when the subject gives
# no other hint -- e.g. "Confirmation code: A6OR2V", "Acknowledgement
# Number: 3P6JQFY10". Requiring a digit in the trailing token is what keeps
# this from matching ordinary prose ("Confirmation needed by Friday" has no
# digit-bearing token within range). Zero-attendee-only, same as above.
CONFIRMATION_NUMBER_PATTERN = re.compile(
    r"\b(?:confirmation|acknowledg(?:e)?ment|booking|reservation)\b"
    r"[^.\n]{0,25}?\b[A-Za-z0-9]*\d[A-Za-z0-9]{2,}\b",
    re.IGNORECASE,
)
# A bare "XXX to YYY" / "XXX-YYY" airport-code pair, for the shorthand
# flight-notation style ("SW 1102: BWI to LAS") that has no useful body text
# to scan. Deliberately case-sensitive -- real airport codes are written in
# caps, and an IGNORECASE version would match ordinary lowercase phrasing
# like "aim to win". Residual risk, accepted: a genuine 3-letter-acronym-
# "to"-3-letter-acronym subject (this org has a few 3-letter workspace
# codes, e.g. "DVR") could coincidentally match, but only ever fires
# alongside zero real attendees, which every real example of this shape in
# practice has none of.
AIRPORT_CODE_PAIR_PATTERN = re.compile(r"\b[A-Z]{3}\b\s*(?:to|-)\s*\b[A-Z]{3}\b")
TRAVEL_SIGNAL_PATTERN = re.compile(r"\b(flight|transit|airport)\b|\btravel to\b", re.IGNORECASE)

PEOPLE_MANAGEMENT_KEYWORDS = re.compile(
    r"\bperformance review\b|\bcoaching\b|\bsuccession plan(ning)?\b|\bskip[- ]level\b|"
    r"\binterview\b|\b1[\s\-:]?1\b|\b1 on 1\b|\bboss chat\b",
    re.IGNORECASE,
)

DECISION_WORDS = re.compile(
    r"\bdecide\b|\bdecision\b|\bapprov(e|al|ed|es)\b|\bsign[- ]?off\b|\bgo[/\- ]no[- ]go\b|\bvote\b",
    re.IGNORECASE,
)
REVIEW_WORDS = re.compile(
    r"\breview\b|\bretro(spective)?\b|\bqbr\b|\baudit\b|\bassessment\b|\bpost[- ]mortem\b",
    re.IGNORECASE,
)
WORKSHOP_WORDS = re.compile(
    r"\bworkshop\b|\bworking session\b|\bdesign session\b|\bbrainstorm\b|\bdeep dive\b",
    re.IGNORECASE,
)
PLANNING_WORDS = re.compile(r"\bplanning\b|\broadmap\b|\bkick[- ]?off\b", re.IGNORECASE)
LEARNING_WORDS = re.compile(
    r"\btraining\b|\bcourse\b|\bwebinar\b|\bconference session\b|\bcertification\b|\bonboarding\b",
    re.IGNORECASE,
)
SOLO_LEARNING_WORDS = re.compile(
    r"\bread(ing)?\b|\bresearch\b|\bcourse\b|\btraining\b|\bstudy\b|\bcertification\b",
    re.IGNORECASE,
)

INCIDENT_WORDS = re.compile(r"\bincident\b", re.IGNORECASE)
ANNUAL_QUARTERLY_WORDS = re.compile(r"\bannual\b|\bquarterly\b", re.IGNORECASE)

PREP_SIGNAL_KEYWORDS = [
    "review", "planning", "strategy", "board", "executive", "client",
    "interview", "presentation", "demo", "kickoff", "kick-off",
    "quarterly", "annual", "budget", "proposal", "negotiat",
]
# Leading-word-boundary only (no trailing \b) -- keeps inflections matching
# ("review" still catches "reviewed"/"reviewing", "negotiat" still catches
# "negotiate"/"negotiation") while rejecting a match that starts mid-word,
# which plain substring containment doesn't: found via smoke test, "board"
# matched inside "onboarding" on a real "ISG ... Weekly Onboarding" event.
# "demo" keeps the same pre-existing risk of matching "democracy"/
# "demographic" that the original substring check already had -- a full
# trailing boundary would lose legitimate "demoing"/"demoed" matches, so
# that specific tradeoff is inherited unchanged, not introduced here.
PREP_SIGNAL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in PREP_SIGNAL_KEYWORDS) + r")", re.IGNORECASE
)

# Step 3.5c: the only three categories an event can still be resolved as once
# it reaches LLM judgment. Not an arbitrary subset -- by construction, any
# event reaching this point already failed categories 1-4 (so it's internal,
# multi-person, and has no real attendees issue) AND failed 5a/5b's Shepherd
# check AND failed 5b's all-Team/Reports check AND failed 5b's span-multiple-
# areas check. So the LLM is never actually choosing among all seven
# categories -- only ever among these three. Definitions kept verbatim from
# the build spec so the fallback stays self-contained without depending on
# a caller remembering them from elsewhere.
CATEGORY_OPTIONS_5C = ["Operating rhythm", "Strategy and transformation", "Stakeholder partnership"]
CATEGORY_DEFINITIONS_5C = {
    "Operating rhythm": (
        "Running the current business -- coordination, delivery, decisions, "
        "escalation management, approvals, execution of committed work. "
        "Examples: weekly leadership meeting, project stand-up, incident call, "
        "change advisory board, sprint planning, budget approval."
    ),
    "Strategy and transformation": (
        "Shaping the future -- long-range decisions, organizational change, "
        "investment priorities, architecture, governance, major initiatives, "
        "STRATOP sessions. Examples: roadmap work, AI governance design, "
        "security strategy, annual planning, enterprise architecture review, "
        "board-prep."
    ),
    "Stakeholder partnership": (
        "Building alignment and advancing shared work with internal groups "
        "outside one's own team. Examples: a meeting with Finance on "
        "forecasting, a working session with HR, an executive leadership "
        "team meeting, cross-department collaboration."
    ),
}

OUTCOME_RULES = [
    ("decision", DECISION_WORDS),
    ("alignment", re.compile(r"\balign(ment)?\b|\bsync\b", re.IGNORECASE)),
    ("coaching", re.compile(r"\bcoaching\b|\bmentor(ing)?\b|\bfeedback session\b", re.IGNORECASE)),
    ("delivery", re.compile(r"\bdeliver(y|able)?\b|\blaunch\b|\bship\b|\brelease\b|\bdeployment\b", re.IGNORECASE)),
    ("discovery", re.compile(r"\bdiscovery\b|\bexplor(e|ation)\b", re.IGNORECASE)),
    ("relationship", re.compile(r"\brelationship\b|\bcheck[- ]?in\b|\bcatch up\b|\brapport\b", re.IGNORECASE)),
]

# Functional-area subject-keyword rules, IN ORDER (Step 4.3). Legal and
# Revenue get special-cased inline in compute_functional_area_tags for the
# governance/pipeline disambiguation the spec calls for; Systems also checks
# attendee domains, not just keywords.
FUNCTIONAL_AREA_KEYWORD_RULES = [
    ("Security", re.compile(r"\bsecurity\b|\bmfa\b|\bphishing\b|\bsoc\b|\bpenetration test\b|\bvulnerabilit(y|ies)\b", re.IGNORECASE)),
    ("Data", re.compile(r"\bdata\b|\banalytics\b|\bbi\b|\breporting pipeline\b|\betl\b|\bdashboard\b", re.IGNORECASE)),
    ("Finance", re.compile(r"\bbudget\b|\bforecast\b|\binvoice\b|\bap\b|\bar\b|\bfinancial audit\b", re.IGNORECASE)),
    ("HR", re.compile(r"\bhiring\b|\bonboarding\b|\bperformance review\b|\bbenefits\b|\bcompensation\b|\btalent\b", re.IGNORECASE)),
    ("Legal", re.compile(r"\bcontract\b|\bdue diligence\b|\bgovernance\b|\bterm sheet\b|\bnda\b", re.IGNORECASE)),
    ("Compliance", re.compile(r"\bcompliance\b|\bpolicy\b|\btax\b|\bregulat(ion|ory)\b", re.IGNORECASE)),
    ("Revenue", re.compile(
        r"\bdonor\b|\bgift\b|\bdaf\b|\bgrant\b|\bcampaign\b|\bstewardship\b|\bmoves management\b|"
        r"\bnonliquid gift\b|\bpipeline\b|\brev.it.up\b", re.IGNORECASE)),
    ("Engineering", re.compile(
        r"\bdev team\b|\bengineering\b|\bsprint\b|\bcode\b|\bdeploy\b|\bbacklog\b|\baws\b|\bgcp\b|"
        r"\binfrastructure\b|\bserver\b|\bnetwork\b", re.IGNORECASE)),
    ("Systems", re.compile(r"\bhubspot\b|\bcrm\b|\bgive interactive\b|\bjira\b|\btalentlms\b|\brippling\b", re.IGNORECASE)),
    ("Operations", re.compile(r"\bdonor care\b|\badvisor\b|\bfamily generosity services\b|\bnonprofit success\b", re.IGNORECASE)),
]
AI_DATA_GOVERNANCE_PATTERN = re.compile(r"\b(ai|artificial intelligence|data|model|algorithm)\s+governance\b", re.IGNORECASE)
LEGAL_NON_GOVERNANCE_PATTERN = re.compile(r"\bcontract\b|\bdue diligence\b|\bterm sheet\b|\bnda\b", re.IGNORECASE)
REVENUE_NON_PIPELINE_PATTERN = re.compile(
    r"\bdonor\b|\bgift\b|\bdaf\b|\bgrant\b|\bcampaign\b|\bstewardship\b|\bmoves management\b|"
    r"\bnonliquid gift\b|\brev.it.up\b", re.IGNORECASE)
BARE_PIPELINE_PATTERN = re.compile(r"\bpipeline\b", re.IGNORECASE)


# --- Small helpers ----------------------------------------------------------


def _fail(message):
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(1)


def load_json(path):
    p = Path(path)
    if not p.exists():
        _fail(f"file not found: {path}")
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        _fail(f"{path} is not valid JSON: {e}")


_MULTILINE_STRING_ARRAY = re.compile(r'\[\s*\n(\s*"(?:[^"\\]|\\.)*"(?:,\s*\n\s*"(?:[^"\\]|\\.)*")*)\s*\n\s*\]')


def _compact_scalar_arrays(text):
    """json.dumps with indent set always expands every list onto multiple
    lines, even a one-item list of short strings -- so re-serializing the
    whole known_meeting_series array (to update or add one entry) would
    reformat every OTHER entry's match_patterns from its original compact
    one-liner (e.g. ["department reports"]) into three lines apiece, purely
    as a side effect of entries this correction never touched. Collapse any
    array whose every element is a plain quoted string back to one line,
    matching this file's existing hand-authored style."""
    def collapse(m):
        items = re.findall(r'"(?:[^"\\]|\\.)*"', m.group(1))
        return "[" + ", ".join(items) + "]"
    return _MULTILINE_STRING_ARRAY.sub(collapse, text)


def _atomic_write(path, text):
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, p)


def save_known_series_atomic(path, new_series_list, full_profile):
    """Splices ONLY the known_meeting_series array's own text span back into
    the file, leaving every other byte untouched -- found via smoke test that
    a blanket `json.dumps(full_profile, indent=2)` rewrite (the first version
    of this function) expanded every compact one-line record in staff/
    vip_senders/partner_vendors/functional_areas into multi-line and escaped
    every non-ASCII character, turning a 265-line file into 660 lines on a
    single correction. acos-aboutme's profile.json is hand-curated and shared
    across the whole acos family; reformatting it wholesale on every write
    here would make every future correction an unreviewable diff.

    Locates the key textually, then uses json.JSONDecoder.raw_decode (the
    real parser, not a hand-rolled bracket matcher) to find exactly where its
    value ends even with nested braces/brackets/escaped strings inside it.
    Re-indents the rendered replacement to match the existing key's own
    indentation, so the spliced-in block reads consistently with the rest of
    the file. Falls back to a full-profile write only if the key doesn't
    exist yet at all (nothing to preserve the formatting of in that case)."""
    text = Path(path).read_text()
    key_match = re.search(r'"known_meeting_series"\s*:\s*', text)
    if not key_match:
        _atomic_write(path, json.dumps(full_profile, indent=2, ensure_ascii=False) + "\n")
        return

    value_start = key_match.end()
    try:
        _, value_end = json.JSONDecoder().raw_decode(text, value_start)
    except json.JSONDecodeError as e:
        _fail(f"could not locate the existing known_meeting_series array in {path}: {e}")

    line_start = text.rfind("\n", 0, key_match.start()) + 1
    base_indent = text[line_start:key_match.start()]

    rendered = _compact_scalar_arrays(json.dumps(new_series_list, indent=2, ensure_ascii=False))
    lines = rendered.split("\n")
    reindented = lines[0] + "\n" + "\n".join(base_indent + line for line in lines[1:])

    _atomic_write(path, text[:value_start] + reindented + text[value_end:])


def _parse_dt(dt_str):
    """Connector dateTime strings are wall-clock in the paired timeZone
    already -- see this module's docstring. Parse the naive string directly,
    no UTC attach/convert."""
    return datetime.fromisoformat(dt_str.split(".")[0])


def _has_concrete_time(event):
    return bool((event.get("start") or {}).get("dateTime")) and bool((event.get("end") or {}).get("dateTime"))


def _event_times(event):
    return _parse_dt(event["start"]["dateTime"]), _parse_dt(event["end"]["dateTime"])


def _format_date(dt):
    return f"{dt.strftime('%A')}, {dt.year}-{dt.strftime('%b').upper()}-{dt.strftime('%d')}"


def _merge_intervals(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _subtract_intervals(start, end, blocking):
    """Returns the parts of [start, end) not covered by any interval in
    `blocking` (any order, overlaps allowed). Used to strip a Capacity-
    unavailable block's span out of a real meeting that overlaps it (a PTO
    interruption), before that meeting's remaining, non-PTO portion (if any)
    is counted toward time allocation -- see compute_time_allocation's own
    comment for why this was necessary."""
    pieces = [(start, end)]
    for b_start, b_end in blocking:
        next_pieces = []
        for p_start, p_end in pieces:
            if b_end <= p_start or b_start >= p_end:
                next_pieces.append((p_start, p_end))
                continue
            if b_start > p_start:
                next_pieces.append((p_start, b_start))
            if b_end < p_end:
                next_pieces.append((b_end, p_end))
        pieces = next_pieces
    return pieces


def _accumulate_category_seconds(occupied_intervals, category_seconds):
    """Attributes every second of a day's occupied window to exactly one
    category, even when events overlap (e.g. a real meeting double-booked
    against another, or a real meeting during a Focused-production block --
    a deep-work infringement). Without this, summing each event's clipped
    duration independently double-counts overlapping seconds across
    categories, inflating the total beyond the window's real size -- found
    via smoke test: Working Block Q3 (Focused production, 08:00-13:00) fully
    contains BLOCK, a Sprint Review, and WhiteStone (three different
    categories), and HubSpot/Boss Chat overlap 15 minutes; category hours
    summed 3.6h higher than the true 45h weekday window before this fix.

    Sweeps events in priority order -- Focused production last, then by
    start time, then longer duration first -- painting each event's clipped
    interval only where nothing higher-priority has already claimed it.
    Focused production deliberately loses any overlap to a real, more
    specific commitment: a double-booked "focus" hour was actually spent on
    whatever else was scheduled, not on focused work."""
    def sort_key(item):
        start, end, cat = item
        return (cat == "Focused production", start, -(end - start).total_seconds())

    painted = []
    for start, end, cat in sorted(occupied_intervals, key=sort_key):
        free_pieces = [(start, end)]
        for p_start, p_end in painted:
            next_pieces = []
            for f_start, f_end in free_pieces:
                if p_end <= f_start or p_start >= f_end:
                    next_pieces.append((f_start, f_end))
                    continue
                if p_start > f_start:
                    next_pieces.append((f_start, p_start))
                if p_end < f_end:
                    next_pieces.append((p_end, f_end))
            free_pieces = next_pieces
        for f_start, f_end in free_pieces:
            category_seconds[cat] += (f_end - f_start).total_seconds()
        painted = [tuple(iv) for iv in _merge_intervals(painted + free_pieces)]


def _working_window_for_day(working_hours, weekday_name):
    override = (working_hours.get("overrides") or {}).get(weekday_name)
    spec = override or working_hours.get("default") or {"start": "08:00", "end": "17:00"}
    start_t = datetime.strptime(spec["start"], "%H:%M").time()
    end_t = datetime.strptime(spec["end"], "%H:%M").time()
    return start_t, end_t


def is_working_block_subject(subject):
    return bool(WORKING_BLOCK_PATTERN.search(subject or ""))


GOOGLE_CALENDAR_ARTIFACT_DOMAIN = re.compile(r"@(?:group|resource)\.calendar\.google\.com$")


def _participants(event, owner_email, ignored_addresses=frozenset()):
    """Robust to the connector's inconsistent inclusion of the organizer in
    `attendees` (observed both ways on real data) -- unions organizer,
    attendees, and the owner's own email, then derives "others" from that.
    Two things get filtered out here, at this single earliest point, so
    every downstream computation -- category, external-domain detection,
    Audience tag, Functional Area tag, prep-flag attendee counts -- treats
    them as if they were never on the invite at all:

    - `ignored_addresses` (acos-aboutme's calendar_analysis.ignored_addresses)
      -- personal/family addresses (a staff or board member's spouse, or
      their own personal email, cc'd alongside their corporate one on a
      company-wide or board event), found via real data on "Department
      Reports" and the Annual Board Meeting alike.
    - Google Calendar sync-artifact addresses (`...@group.calendar.google.com`,
      `...@resource.calendar.google.com`) -- these are the calendar system's
      own plumbing for an event synced from a personal Google Calendar or a
      room-resource booking, not a real attendee. Found via real data: a
      genuine personal doctor's appointment ("Trevor - Eye dr appointment")
      is organized by one of these and would otherwise register as a real
      external participant, misclassifying a personal appointment as
      External ecosystem. Unlike `ignored_addresses`, this is a structural
      domain pattern, not a curated list -- these addresses are random
      per-event identifiers, impossible to enumerate in advance."""
    organizer = (event.get("organizer") or "").lower()
    attendees = {(a or "").lower() for a in (event.get("attendees") or [])}
    participants = {
        p for p in ({organizer} | attendees | {owner_email})
        if p and p not in ignored_addresses and not GOOGLE_CALENDAR_ARTIFACT_DOMAIN.search(p)
    }
    others = participants - {owner_email}
    return organizer, participants, others


def _external_domains(other_participants, owner_domain):
    return {p.split("@")[-1] for p in other_participants if "@" in p and p.split("@")[-1] != owner_domain}


# --- Profile lookups ---------------------------------------------------------


def build_lookups(profile):
    owner = profile.get("owner", {}) or {}
    owner_email = (owner.get("email") or "").lower()
    owner_domain = owner_email.split("@")[-1] if "@" in owner_email else ""
    staff_position_type = owner.get("staff_position_type") or "c_suite_executive"

    reports_emails = {p["email"].lower() for p in profile.get("reports", []) if p.get("email")}
    team_emails = {p["email"].lower() for p in profile.get("team", []) if p.get("email")}

    staff_by_email = {}
    for s in profile.get("staff", []):
        email = (s.get("email") or "").lower()
        if email:
            staff_by_email[email] = {"name": s.get("name"), "role": s.get("role")}

    shepherd_by_email = {}
    shepherd_domains = set()
    for v in profile.get("vip_senders", []):
        email = (v.get("email") or "").lower()
        if email:
            shepherd_by_email[email] = v
        if v.get("domain"):
            shepherd_domains.add(v["domain"].lower())

    partner_by_domain = {}
    for p in profile.get("partner_vendors", []):
        d = (p.get("domain") or "").lower()
        if d:
            partner_by_domain[d] = p

    functional_area_emails = {}
    for area, people in (profile.get("functional_areas") or {}).items():
        functional_area_emails[area] = {p["email"].lower() for p in (people or []) if p.get("email")}

    cal = profile.get("calendar_analysis") or {}
    known_series = [s for s in cal.get("known_meeting_series", []) if s.get("match_patterns")]
    working_hours = cal.get("working_hours") or {"default": {"start": "08:00", "end": "17:00"}, "overrides": {}}
    time_allocation_targets = cal.get("time_allocation_targets") or {}
    time_allocation_target_overrides = cal.get("time_allocation_target_overrides") or {}
    ignored_addresses = {a.lower() for a in cal.get("ignored_addresses", [])}

    return {
        "owner_email": owner_email,
        "owner_domain": owner_domain,
        "staff_position_type": staff_position_type,
        "reports_emails": reports_emails,
        "team_emails": team_emails,
        "staff_by_email": staff_by_email,
        "shepherd_by_email": shepherd_by_email,
        "shepherd_domains": shepherd_domains,
        "partner_by_domain": partner_by_domain,
        "functional_area_emails": functional_area_emails,
        "known_series": known_series,
        "working_hours": working_hours,
        "time_allocation_targets": time_allocation_targets,
        "time_allocation_target_overrides": time_allocation_target_overrides,
        "ignored_addresses": ignored_addresses,
    }


def _shepherd_matches(other_participants, lookups):
    """Internal-domain matches only -- see module docstring's "deliberate
    corrections" note on why an external VIP-listed partner contact (kept on
    vip_senders for email-priority reasons) must not trigger a Shepherd/board
    read here."""
    matched = []
    for p in other_participants:
        if not p.endswith("@" + lookups["owner_domain"]):
            continue
        v = lookups["shepherd_by_email"].get(p)
        if v:
            matched.append(v)
        elif p.split("@")[-1] in lookups["shepherd_domains"]:
            matched.append({"email": p, "domain": p.split("@")[-1]})
    return matched


def _functional_areas_for(other_participants, lookups):
    """Directory-only signal (Step 1's functional_areas), in the directory's
    own key order for determinism. Used both by 5b's span check and as step 1
    of the Functional Area tag waterfall."""
    areas = []
    for area, emails in lookups["functional_area_emails"].items():
        if other_participants & emails:
            areas.append(area)
    return areas


def _describe_participant(email, lookups):
    """Enough context for an LLM to reason about a Step 3.5c event without
    re-deriving org-chart facts itself: name/role from `staff` if known,
    Reports/Team membership, and any functional areas the directory has
    them tagged with. `name`/`role` are null for an internal participant
    who isn't in `staff` at all -- a real signal in itself (an org-chart gap,
    same shape as the Eric Galante case that surfaced via this exact path)."""
    info = lookups["staff_by_email"].get(email) or {}
    return {
        "email": email,
        "name": info.get("name"),
        "role": info.get("role"),
        "on_reports": email in lookups["reports_emails"],
        "on_team": email in lookups["team_emails"],
        "functional_areas": [area for area, emails in lookups["functional_area_emails"].items() if email in emails],
    }


def _match_known_series(subject, known_series):
    subj_lower = (subject or "").lower()
    for entry in known_series:
        for pattern in entry.get("match_patterns", []):
            if pattern.lower() in subj_lower:
                return entry
    return None


# --- Step 3: primary category classification (1-5b), first match wins -----


def _is_capacity_unavailable(event, other_participants):
    if (event.get("showAs") or "").lower() == "oof":
        return True, "showAs is out-of-office"
    for c in (event.get("categories") or []):
        if re.search(r"\b(pto|travel|personal)\b", c or "", re.IGNORECASE):
            return True, f"Outlook category {c!r}"
    subject = event.get("subject") or ""
    m = CAPACITY_UNAVAILABLE_KEYWORDS.search(subject)
    if m:
        return True, f"subject keyword match: {m.group(0)!r}"
    if not other_participants:
        m = CAPACITY_UNAVAILABLE_SOLO_KEYWORDS.search(subject)
        if m:
            return True, f"subject keyword match (solo block): {m.group(0)!r}"
        m = AIRPORT_CODE_PAIR_PATTERN.search(subject)
        if m:
            return True, f"subject airport-code pair (solo block): {m.group(0)!r}"
        body = event.get("summary") or ""
        m = CONFIRMATION_NUMBER_PATTERN.search(f"{subject}\n{body}")
        if m:
            return True, f"confirmation/reservation number match (solo block): {m.group(0)!r}"
    return False, None


def _is_focused_production(other_participants, subject):
    if not other_participants:
        return True, "no real attendees besides the owner"
    if is_working_block_subject(subject):
        return True, "subject matches the working-block pattern"
    return False, None


def _check_people_leadership(subject, participants, other_participants, lookups):
    if len(participants) == 2 and len(other_participants) == 1:
        other = next(iter(other_participants))
        if other in lookups["reports_emails"]:
            return True, f"exactly two total attendees and the other ({other}) is on the Reports list"
    if PEOPLE_MANAGEMENT_KEYWORDS.search(subject or ""):
        matched = other_participants & (lookups["reports_emails"] | lookups["team_emails"])
        if matched:
            return True, f"attendee(s) {sorted(matched)} on Reports/Team AND subject matches a people-management keyword"
    return False, None


def classify_primary_category(event, lookups):
    """`external_domains` is computed once, unconditionally, and carried in
    every returned dict -- not just the External-ecosystem branch. It was
    previously hardcoded to [] on every other branch, which silently zeroed
    out the Audience tag's partner/external signal for any event resolved by
    an earlier category despite genuinely having an external attendee (found
    via real-data smoke test: an "Interview" event correctly classifies as
    People leadership via the interview keyword, but its external candidate
    should still surface as "prospective external" on the Audience tag).

    Known-series match (5a) is checked BEFORE External ecosystem (4), not
    after as a literal reading of the spec would order them -- also found via
    the same smoke test: a real "Department Reports" occurrence cc's a board
    member's personal email alongside his corporate one, and without this
    reordering that single incidental external address would flip the whole
    known, seeded series to External ecosystem instead of Strategy and
    transformation every time it recurs. A recurring series is supposed to
    classify "consistently" (the known-series table's whole point) regardless
    of which random address happens to be cc'd that week."""
    subject = event.get("subject") or ""
    _, participants, others = _participants(event, lookups["owner_email"], lookups["ignored_addresses"])
    ext_domains = sorted(_external_domains(others, lookups["owner_domain"]))

    cap_unavail, cap_reason = _is_capacity_unavailable(event, others)
    if cap_unavail:
        return {"category": "Capacity unavailable", "reason": cap_reason, "needs_llm": False,
                "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    focused, focus_reason = _is_focused_production(others, subject)
    if focused:
        return {"category": "Focused production", "reason": focus_reason, "needs_llm": False,
                "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    pl, pl_reason = _check_people_leadership(subject, participants, others, lookups)
    if pl:
        return {"category": "People leadership", "reason": pl_reason, "needs_llm": False,
                "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    series = _match_known_series(subject, lookups["known_series"])
    if series:
        return {"category": series["category"], "reason": f"known-series match: {series['name']}",
                "needs_llm": False, "matched_series": series["name"], "series_tags": series.get("tags") or {},
                "external_domains": ext_domains}

    if ext_domains:
        return {"category": "External ecosystem", "reason": f"external domain(s) present: {ext_domains}",
                "needs_llm": False, "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    shepherd_hits = _shepherd_matches(others, lookups)
    if shepherd_hits:
        names = [h.get("name") or h.get("email") for h in shepherd_hits]
        return {"category": "Strategy and transformation", "reason": f"Shepherd/VIP present: {names}",
                "needs_llm": False, "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    if others and others <= (lookups["reports_emails"] | lookups["team_emails"]):
        return {"category": "Operating rhythm", "reason": "all attendees are the owner plus Team/Reports members",
                "needs_llm": False, "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    areas = _functional_areas_for(others, lookups)
    if len(areas) > 1:
        return {"category": "Stakeholder partnership", "reason": f"attendees span multiple functional areas: {areas}",
                "needs_llm": False, "matched_series": None, "series_tags": {}, "external_domains": ext_domains}

    return {"category": None, "reason": "no deterministic match (5a/5b) -- needs LLM judgment (5c)",
            "needs_llm": True, "matched_series": None, "series_tags": {}, "external_domains": ext_domains}


# --- Step 4: tags ------------------------------------------------------------


def compute_audience_tag(other_participants, ext_domains, lookups):
    if not other_participants:
        return None
    shepherd_hits = _shepherd_matches(other_participants, lookups)
    if shepherd_hits:
        for h in shepherd_hits:
            if "board" in (h.get("title") or "").lower():
                return "board"
        return "Shepherd/executive"
    if ext_domains:
        partner_domains = set(lookups["partner_by_domain"].keys())
        if ext_domains <= partner_domains:
            return "existing partner"
        return "prospective external"
    if other_participants <= lookups["reports_emails"]:
        return "direct team"
    if other_participants <= lookups["team_emails"]:
        return "broader internal"
    return "peer"


def compute_functional_area_tags(subject, other_participants, category, ext_domains, lookups):
    """For External-ecosystem events, the partner's own domain-tag is
    checked BEFORE the internal-attendee directory -- reversed from a literal
    reading of the spec's step order. Found via real data: an internal
    staffer who routinely sits in on vendor calls (e.g. Aril Brizendine, who
    owns most vendor relationships and is tagged Systems/Operations herself)
    would otherwise crowd out the vendor's own tag on every single one of
    those calls purely by attending -- a Rippling meeting tagged
    "Systems, Operations" instead of Rippling's own "HR", a Leet meeting
    tagged "Systems, Operations" instead of Leet's own "Security". The
    vendor's own designation is the more relevant "what is this meeting
    fundamentally about" signal for an External-ecosystem event; the
    directory still runs right after to fill a second slot when the meeting
    is genuinely also cross-functional on the internal side."""
    subject = subject or ""
    found = []

    def add(area):
        if area not in found:
            found.append(area)
        return len(found) >= 2

    if category == "External ecosystem":
        for d in ext_domains:
            partner = lookups["partner_by_domain"].get(d)
            area = partner.get("functional_area") if partner else None
            if area and add(area):
                return found[:2]

    for area in _functional_areas_for(other_participants, lookups):
        if add(area):
            return found[:2]

    for area, pattern in FUNCTIONAL_AREA_KEYWORD_RULES:
        if area == "Legal":
            has_governance = bool(re.search(r"\bgovernance\b", subject, re.IGNORECASE))
            credit_governance = has_governance and not AI_DATA_GOVERNANCE_PATTERN.search(subject)
            if credit_governance or LEGAL_NON_GOVERNANCE_PATTERN.search(subject):
                if add("Legal"):
                    return found[:2]
            continue
        if area == "Revenue":
            if REVENUE_NON_PIPELINE_PATTERN.search(subject):
                if add("Revenue"):
                    return found[:2]
                continue
            if BARE_PIPELINE_PATTERN.search(subject) and "Data" not in found:
                if add("Revenue"):
                    return found[:2]
            continue
        if area == "Systems":
            domain_hit = any(
                (lookups["partner_by_domain"].get(p.split("@")[-1]) or {}).get("functional_area") == "Systems"
                for p in other_participants if "@" in p
            )
            if pattern.search(subject) or domain_hit:
                if add("Systems"):
                    return found[:2]
            continue
        if pattern.search(subject):
            if add(area):
                return found[:2]

    return found[:2]


def compute_work_mode(subject, category, other_participants):
    subject = subject or ""
    if category == "Focused production" and not other_participants:
        return "Learning" if SOLO_LEARNING_WORDS.search(subject) else "Execution"
    if category == "Capacity unavailable" and (
        TRAVEL_SIGNAL_PATTERN.search(subject) or AIRPORT_CODE_PAIR_PATTERN.search(subject)
    ):
        return "Travel"
    if DECISION_WORDS.search(subject):
        return "Decision"
    if REVIEW_WORDS.search(subject):
        return "Review"
    if WORKSHOP_WORDS.search(subject):
        return "Workshop"
    if PLANNING_WORDS.search(subject):
        return "Planning"
    if LEARNING_WORDS.search(subject):
        return "Learning"
    return "Meeting"


def compute_cadence(subject, matched_series):
    subject = subject or ""
    if INCIDENT_WORDS.search(subject):
        return "incident"
    if ANNUAL_QUARTERLY_WORDS.search(subject):
        return "annual/quarterly"
    return "recurring" if matched_series else "ad hoc"


def compute_time_context(start, end, working_hours, weekday, category, is_travel, overlaps_capacity_unavailable):
    if category == "Capacity unavailable" and is_travel:
        return "travel"
    if category != "Capacity unavailable" and overlaps_capacity_unavailable:
        return "PTO interruption"
    win_start, win_end = _working_window_for_day(working_hours, weekday)
    if start.time() >= win_start and end.time() <= win_end:
        return "normal hours"
    return "after-hours"


def compute_outcome(subject):
    for label, pattern in OUTCOME_RULES:
        if pattern.search(subject or ""):
            return label
    return None


# --- Conflicts / schedule health / prep flags (ported from weekly_preview.py) ---


def _is_schedulable(event, category):
    """"Real meeting" predicate. Excludes Focused production AND Capacity
    unavailable (see module docstring) -- neither can meaningfully
    double-book in the traditional sense; Capacity-unavailable's overlap
    with real meetings is handled by the dedicated PTO-interruption check."""
    return (
        not event.get("isAllDay", False)
        and not event.get("isCancelled", False)
        and category not in ("Focused production", "Capacity unavailable")
        and (event.get("showAs") or "busy") not in ("free", "oof", "workingElsewhere")
        and _has_concrete_time(event)
    )


def detect_conflicts(events_with_category):
    busy = [(e, c) for e, c in events_with_category if _is_schedulable(e, c)]
    busy.sort(key=lambda ec: ec[0]["start"]["dateTime"])

    double_bookings = []
    tight_transitions = []
    for i in range(len(busy) - 1):
        cur, _c1 = busy[i]
        nxt, _c2 = busy[i + 1]
        cur_start, cur_end = _event_times(cur)
        nxt_start, nxt_end = _event_times(nxt)

        if cur_end > nxt_start:
            overlap_minutes = int((cur_end - nxt_start).total_seconds() / 60)
            double_bookings.append({
                "event_a": {"id": cur["id"], "subject": cur.get("subject", "(No title)"),
                            "start": cur_start.strftime("%H:%M"), "end": cur_end.strftime("%H:%M")},
                "event_b": {"id": nxt["id"], "subject": nxt.get("subject", "(No title)"),
                            "start": nxt_start.strftime("%H:%M"), "end": nxt_end.strftime("%H:%M")},
                "overlap_minutes": overlap_minutes,
            })
        elif (nxt_start - cur_end).total_seconds() < 600:
            gap_minutes = int((nxt_start - cur_end).total_seconds() / 60)
            tight_transitions.append({
                "event_a": {"id": cur["id"], "subject": cur.get("subject", "(No title)"), "end": cur_end.strftime("%H:%M")},
                "event_b": {"id": nxt["id"], "subject": nxt.get("subject", "(No title)"), "start": nxt_start.strftime("%H:%M")},
                "gap_minutes": gap_minutes,
            })

    return {"double_bookings": double_bookings, "tight_transitions": tight_transitions}


def _select_blocks(events_with_category, category, allow_all_day):
    blocks = []
    for e, c in events_with_category:
        if c != category or e.get("isCancelled") or not _has_concrete_time(e):
            continue
        if not allow_all_day and e.get("isAllDay"):
            continue
        blocks.append(e)
    return blocks


def _find_block_infringements(blocks, real_meetings):
    total = 0
    results = []
    for block in sorted(blocks, key=lambda e: e["start"]["dateTime"]):
        b_start, b_end = _event_times(block)
        duration_hours = round((b_end - b_start).total_seconds() / 3600, 1)
        infringements = []
        for meeting in real_meetings:
            m_start, m_end = _event_times(meeting)
            if m_start < b_end and m_end > b_start:
                overlap_minutes = int((min(m_end, b_end) - max(m_start, b_start)).total_seconds() / 60)
                infringements.append({
                    "id": meeting["id"], "subject": meeting.get("subject", "(No title)"),
                    "start": m_start.strftime("%H:%M"), "end": m_end.strftime("%H:%M"),
                    "overlap_minutes": overlap_minutes, "web_link": meeting.get("webLink", ""),
                })
        total += len(infringements)
        spans_days = b_start.date() != b_end.date()
        results.append({
            "id": block["id"], "subject": block.get("subject", "(No title)"),
            "date": _format_date(b_start),
            "start": b_start.strftime("%Y-%m-%d %H:%M") if spans_days else b_start.strftime("%H:%M"),
            "end": b_end.strftime("%Y-%m-%d %H:%M") if spans_days else b_end.strftime("%H:%M"),
            "duration_hours": duration_hours, "infringements": infringements, "web_link": block.get("webLink", ""),
        })
    return {"blocks": results, "total_infringements": total}


def flag_meetings_needing_prep(events_with_category, owner_email, owner_domain, ignored_addresses=frozenset()):
    """Ported from flag_meetings_needing_prep, unchanged signal set (external
    attendee, 3+ attendees, strategic keyword). Four adjustments beyond the
    literal port, all found via smoke test:

    - Excludes Capacity unavailable as well as Focused production. Neither
      is a "meeting" that needs prep materials; the original ported code had
      no equivalent to Capacity unavailable at all (PTO was just isAllDay).
    - Uses `_participants()` (organizer + attendees + owner, unioned) rather
      than the raw `attendees` field directly, for both the headcount and
      external-attendee signals -- the connector sometimes omits the
      organizer from `attendees` (observed on real data), which silently
      undercounted both signals whenever that happened.
    - Same `_participants()` call also drops `ignored_addresses` (personal/
      family addresses cc'd on a company-wide event), so those don't inflate
      the attendee count or trigger a false "external attendee" signal either.
    - Keyword matching uses a leading-word-boundary regex instead of plain
      substring containment, to reject a match starting mid-word ("board"
      inside "onboarding") while still catching inflections ("review" in
      "reviewed") -- see PREP_SIGNAL_PATTERN's own comment."""
    flagged = []
    for e, c in events_with_category:
        if (e.get("isAllDay") or e.get("isCancelled") or c in ("Focused production", "Capacity unavailable")
                or not _has_concrete_time(e)):
            continue
        _, participants, others = _participants(e, owner_email, ignored_addresses)
        subject = e.get("subject") or ""
        signals = []

        if len(participants) >= 3:
            signals.append(f"{len(participants)} attendees")

        external = [p for p in others if "@" in p and p.split("@")[-1] != owner_domain]
        if external:
            signals.append(f"{len(external)} external attendee(s)")

        m = PREP_SIGNAL_PATTERN.search(subject)
        if m:
            signals.append(f'keyword "{m.group(1).lower()}"')

        if signals:
            start, _end = _event_times(e)
            flagged.append({
                "id": e["id"], "subject": e.get("subject", "(No title)"),
                "start": start.strftime("%H:%M"), "date": _format_date(start),
                "attendee_count": len(participants), "prep_signals": signals,
                "web_link": e.get("webLink", ""),
            })
    return flagged


def compute_schedule_health(events_with_category, working_hours):
    real_meetings = [e for e, c in events_with_category if _is_schedulable(e, c)]
    deep_work_blocks = _select_blocks(events_with_category, "Focused production", allow_all_day=False)
    capacity_blocks = _select_blocks(events_with_category, "Capacity unavailable", allow_all_day=True)

    deep_work = _find_block_infringements(deep_work_blocks, real_meetings)
    pto_interruptions = _find_block_infringements(capacity_blocks, real_meetings)

    after_hours_events = []
    after_hours_seconds = 0.0
    for e in real_meetings:
        start, end = _event_times(e)
        weekday = WEEKDAY_NAMES[start.weekday()]
        win_start, win_end = _working_window_for_day(working_hours, weekday)
        if not (start.time() >= win_start and end.time() <= win_end):
            after_hours_events.append({
                "id": e["id"], "subject": e.get("subject", "(No title)"),
                "date": _format_date(start), "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M"),
                "web_link": e.get("webLink", ""),
            })
            after_hours_seconds += (end - start).total_seconds()

    travel_events = [
        e for e, c in events_with_category
        if c == "Capacity unavailable" and not e.get("isCancelled") and _has_concrete_time(e)
        and TRAVEL_SIGNAL_PATTERN.search(e.get("subject") or "")
    ]
    travel_seconds = sum((_event_times(e)[1] - _event_times(e)[0]).total_seconds() for e in travel_events)

    return {
        "deep_work_infringements": deep_work,
        "personal_time_infringement": {
            "after_hours": {
                "count": len(after_hours_events),
                "total_hours": round(after_hours_seconds / 3600.0, 1),
                "events": after_hours_events,
            },
            "pto_interruptions": pto_interruptions,
        },
        "travel_burden": {
            "count": len(travel_events),
            "total_hours": round(travel_seconds / 3600.0, 1),
        },
    }


# --- Free-time gap-finding + excluded-denominator percentages --------------


def compute_time_allocation(events_with_category, period_start_date, period_end_date, working_hours):
    """Walks each day in [period_start_date, period_end_date]: finds that
    day's working-hours window, subtracts any Capacity-unavailable overlap
    from the window entirely (excluded from the denominator), then finds the
    actual open gaps within what's left (free time) versus every other
    category's clipped occupied time. See module docstring for why every
    event's contribution is clipped to the working-hours window.

    Real meetings are also clipped AGAINST the day's Capacity-unavailable
    overlap, not just against the working-hours window -- found via a full
    real month: a PTO week still had real meetings on the calendar (a PTO
    interruption, correctly flagged separately under schedule_health), and
    without this second clip those meetings' hours were being counted twice
    -- once implicitly erased when available_seconds was reduced for that
    day, and again explicitly added to category_seconds -- inflating the
    denominator by the total of every meeting that happened to overlap a
    Capacity-unavailable block (22.55h on that one real month). A meeting
    during PTO was never real "available capacity" to attribute to a
    category in the first place, regardless of the fact that it happened."""
    category_seconds = defaultdict(float)
    free_seconds = 0.0

    day = period_start_date
    while day <= period_end_date:
        weekday = WEEKDAY_NAMES[day.weekday()]
        win_start_t, win_end_t = _working_window_for_day(working_hours, weekday)
        win_start = datetime.combine(day, win_start_t)
        win_end = datetime.combine(day, win_end_t)
        if win_end <= win_start:
            day += timedelta(days=1)
            continue

        cap_intervals = []
        for e, c in events_with_category:
            if c != "Capacity unavailable" or e.get("isCancelled") or not _has_concrete_time(e):
                continue
            s, en = _event_times(e)
            if en <= win_start or s >= win_end:
                continue
            cap_intervals.append((max(s, win_start), min(en, win_end)))
        cap_intervals = _merge_intervals(cap_intervals)
        cap_overlap_seconds = sum((b - a).total_seconds() for a, b in cap_intervals)
        available_seconds = (win_end - win_start).total_seconds() - cap_overlap_seconds

        occupied_intervals = []
        for e, c in events_with_category:
            if c == "Capacity unavailable" or e.get("isCancelled") or e.get("isAllDay") or not _has_concrete_time(e):
                continue
            s, en = _event_times(e)
            if en <= win_start or s >= win_end:
                continue
            clip_s, clip_e = max(s, win_start), min(en, win_end)
            if clip_e <= clip_s:
                continue
            for piece_s, piece_e in _subtract_intervals(clip_s, clip_e, cap_intervals):
                occupied_intervals.append((piece_s, piece_e, c or "Unresolved"))

        _accumulate_category_seconds(occupied_intervals, category_seconds)

        merged_occupied = _merge_intervals([(s, e) for s, e, _c in occupied_intervals])
        occupied_seconds = sum((b - a).total_seconds() for a, b in merged_occupied)
        free_seconds += max(0.0, available_seconds - occupied_seconds)

        day += timedelta(days=1)

    cap_full_intervals = []
    for e, c in events_with_category:
        if c != "Capacity unavailable" or e.get("isCancelled") or not _has_concrete_time(e):
            continue
        cap_full_intervals.append(_event_times(e))
    cap_full_merged = _merge_intervals(cap_full_intervals)
    capacity_unavailable_hours = sum((b - a).total_seconds() for a, b in cap_full_merged) / 3600.0

    denominator_seconds = sum(category_seconds.values()) + free_seconds

    categories_out = {}
    for cat in BENCHMARK_CATEGORIES:
        seconds = category_seconds.get(cat, 0.0)
        pct = (seconds / denominator_seconds * 100.0) if denominator_seconds > 0 else 0.0
        categories_out[cat] = {"hours": round(seconds / 3600.0, 1), "pct": round(pct, 1)}

    unresolved_seconds = category_seconds.get("Unresolved", 0.0)
    free_pct = (free_seconds / denominator_seconds * 100.0) if denominator_seconds > 0 else 0.0

    return {
        "denominator_hours": round(denominator_seconds / 3600.0, 1),
        "categories": categories_out,
        "free_time": {"hours": round(free_seconds / 3600.0, 1), "pct": round(free_pct, 1)},
        "unresolved_hours": round(unresolved_seconds / 3600.0, 1),
        "capacity_unavailable_hours": round(capacity_unavailable_hours, 1),
    }


MARGIN_FLEX_CATEGORY = "Margin / Flex capacity"


def _benchmark_row(actual_pct, rng):
    if not rng:
        return {"actual_pct": actual_pct, "target_range": None, "status": "no target configured", "delta_points": None}
    lo, hi = rng
    if actual_pct < lo:
        status, delta = "below", round(lo - actual_pct, 1)
    elif actual_pct > hi:
        status, delta = "above", round(actual_pct - hi, 1)
    else:
        status, delta = "within", 0.0
    return {"actual_pct": actual_pct, "target_range": [lo, hi], "status": status, "delta_points": delta}


def compute_benchmark(time_allocation, lookups):
    targets = lookups["time_allocation_targets"].get(lookups["staff_position_type"], {})
    overrides = lookups["time_allocation_target_overrides"] or {}
    out = {}
    for cat in BENCHMARK_CATEGORIES:
        rng = overrides.get(cat) or targets.get(cat)
        actual_pct = time_allocation["categories"].get(cat, {}).get("pct", 0.0)
        out[cat] = _benchmark_row(actual_pct, rng)

    # Margin / Flex capacity is not a classification category -- no event is ever
    # tagged into it -- it's the benchmark counterpart of `free_time` (leftover
    # capacity not consumed by any classified event). Handled here rather than via
    # BENCHMARK_CATEGORIES so it can never become a selectable classification target.
    margin_rng = overrides.get(MARGIN_FLEX_CATEGORY) or targets.get(MARGIN_FLEX_CATEGORY)
    if margin_rng:
        out[MARGIN_FLEX_CATEGORY] = _benchmark_row(time_allocation["free_time"]["pct"], margin_rng)

    return {"staff_position_type": lookups["staff_position_type"], "categories": out}


# --- Period resolution -------------------------------------------------------


def resolve_period(period_type, ref_date):
    if period_type == "day":
        return ref_date, ref_date
    if period_type == "week":
        start = ref_date - timedelta(days=ref_date.weekday())
        return start, start + timedelta(days=6)
    if period_type == "month":
        start = ref_date.replace(day=1)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, next_month - timedelta(days=1)
    raise ValueError(f"unknown period type: {period_type}")


# --- CLI commands -------------------------------------------------------------


def cmd_plan(args):
    profile = load_json(args.aboutme)
    ref_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    start, end = resolve_period(args.period, ref_date)
    after_dt = datetime.combine(start, datetime.min.time())
    before_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())

    plan = {
        "period": {"type": args.period, "start_date": start.isoformat(), "end_date": end.isoformat()},
        "fetch": {
            "tool": "outlook_calendar_search",
            "query": "*",
            "afterDateTime": after_dt.isoformat(),
            "beforeDateTime": before_dt.isoformat(),
            "limit": 25,
            "note": ("Paginate via `offset` using each response's `nextOffset` until "
                     "`moreResults` is false; concatenate every event across every page "
                     "into one JSON array before calling `report`."),
        },
        "profile": profile,
    }
    print(json.dumps(plan, indent=2))


def _md_table(headers, rows):
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def _escape(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


_MONTH_ABBR_ORDER = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}


def _date_sort_key(date_str):
    # e["date"] is "<Weekday>, YYYY-MON-DD" (see _format_date) -- sorting on that
    # string directly sorts alphabetically by weekday name (Friday < Monday <
    # Thursday < ...), not chronologically. Parse back to (year, month, day).
    if not date_str:
        return (0, 0, 0)
    _, ymd = date_str.split(", ", 1)
    y, mon, d = ymd.split("-")
    return (int(y), _MONTH_ABBR_ORDER[mon], int(d))


def render_markdown(report):
    period = report["period"]
    parts = [f"# Calendar Analysis -- {period['type'].title()} ({period['start_date']} to {period['end_date']})\n"]

    parts.append("## Classified schedule\n")
    timed_events = sorted(
        (e for e in report["events"] if not e["is_all_day"] and e["start"]),
        key=lambda e: (_date_sort_key(e["date"]), e["start"] or ""),
    )
    if not timed_events:
        parts.append("_No timed events in this period._\n")
    else:
        headers = ["Date", "Time", "Subject", "Category", "Audience", "Functional Area", "Work Mode", "Cadence", "Time Context"]
        rows = []
        for e in timed_events:
            t = e["tags"]
            rows.append([
                e["date"] or "", f"{e['start']}-{e['end']}",
                _escape(e["subject"]), e["category"] or "_needs review (5c)_",
                t["audience"] or "", ", ".join(t["functional_areas"]) or "",
                t["work_mode"] or "", t["cadence"] or "", t["time_context"] or "",
            ])
        parts.append(_md_table(headers, rows))

    if report["unresolved_events"]:
        parts.append(f"\n**{len(report['unresolved_events'])} event(s) need LLM judgment (Step 3.5c)** -- not yet resolved:\n")
        for e in report["unresolved_events"]:
            parts.append(f"- [{_escape(e['subject'])}]({e['web_link']}) -- {e['date']} {e['start']}\n")

    parts.append("\n## Conflicts\n")
    db, tt = report["conflicts"]["double_bookings"], report["conflicts"]["tight_transitions"]
    if not db and not tt:
        parts.append("_No double-bookings or tight transitions._\n")
    else:
        if db:
            parts.append("**Double-bookings**\n\n")
            for c in db:
                parts.append(f"- {_escape(c['event_a']['subject'])} ({c['event_a']['start']}-{c['event_a']['end']}) "
                              f"overlaps {_escape(c['event_b']['subject'])} ({c['event_b']['start']}-{c['event_b']['end']}) "
                              f"by {c['overlap_minutes']} min\n")
        if tt:
            parts.append("\n**Tight transitions**\n\n")
            for c in tt:
                parts.append(f"- {_escape(c['event_a']['subject'])} ends {c['event_a']['end']}, "
                              f"{_escape(c['event_b']['subject'])} starts {c['event_b']['start']} "
                              f"({c['gap_minutes']} min gap)\n")

    parts.append("\n## Schedule health\n")
    sh = report["schedule_health"]
    dw = sh["deep_work_infringements"]
    parts.append(f"\n**Deep-work infringements**: {dw['total_infringements']} across {len(dw['blocks'])} Focused-production block(s)\n\n")
    for b in dw["blocks"]:
        if b["infringements"]:
            detail = "; ".join(f"{_escape(i['subject'])} overlaps {i['overlap_minutes']} min" for i in b["infringements"])
            parts.append(f"- {_escape(b['subject'])} ({b['date']} {b['start']}-{b['end']}): {detail}\n")

    ah = sh["personal_time_infringement"]["after_hours"]
    parts.append(f"\n**After-hours work**: {ah['count']} meeting(s), {ah['total_hours']}h total\n\n")
    for e in ah["events"]:
        parts.append(f"- [{_escape(e['subject'])}]({e['web_link']}) -- {e['date']} {e['start']}-{e['end']}\n")

    pto = sh["personal_time_infringement"]["pto_interruptions"]
    parts.append(f"\n**PTO interruptions**: {pto['total_infringements']} across {len(pto['blocks'])} Capacity-unavailable block(s)\n\n")
    for b in pto["blocks"]:
        if b["infringements"]:
            detail = "; ".join(f"{_escape(i['subject'])} overlaps {i['overlap_minutes']} min" for i in b["infringements"])
            parts.append(f"- {_escape(b['subject'])} ({b['date']}): {detail}\n")

    tb = sh["travel_burden"]
    parts.append(f"\n**Travel burden**: {tb['count']} block(s), {tb['total_hours']}h total\n")

    parts.append("\n## Meetings needing prep\n")
    if not report["meetings_needing_prep"]:
        parts.append("_None flagged._\n")
    else:
        for m in report["meetings_needing_prep"]:
            parts.append(f"- [{_escape(m['subject'])}]({m['web_link']}) -- {m['date']} {m['start']}, {', '.join(m['prep_signals'])}\n")

    if "time_allocation" in report:
        ta = report["time_allocation"]
        parts.append(f"\n## Time allocation (denominator: {ta['denominator_hours']}h scheduled+free within working hours, Capacity unavailable excluded)\n\n")
        headers = ["Category", "Hours", "% of denominator"]
        rows = [[cat, str(ta["categories"][cat]["hours"]), f"{ta['categories'][cat]['pct']}%"] for cat in BENCHMARK_CATEGORIES]
        rows.append(["Free time", str(ta["free_time"]["hours"]), f"{ta['free_time']['pct']}%"])
        parts.append(_md_table(headers, rows))
        if ta["unresolved_hours"]:
            parts.append(f"\n_{ta['unresolved_hours']}h still needs LLM judgment (5c) and isn't attributed to a category above yet._\n")
        parts.append(f"\n_Capacity unavailable (raw, not benchmarked): {ta['capacity_unavailable_hours']}h_\n")

    if "benchmark" in report:
        bm = report["benchmark"]
        parts.append(f"\n## Benchmark -- {bm['staff_position_type']}\n\n")
        headers = ["Category", "Actual %", "Target range", "Status", "Delta from nearest bound"]
        rows = []
        for cat in BENCHMARK_CATEGORIES:
            b = bm["categories"][cat]
            rng = f"{b['target_range'][0]}-{b['target_range'][1]}%" if b["target_range"] else "not configured"
            delta = f"{b['delta_points']} pts" if b["delta_points"] else "--"
            rows.append([cat, f"{b['actual_pct']}%", rng, b["status"], delta])
        if MARGIN_FLEX_CATEGORY in bm["categories"]:
            b = bm["categories"][MARGIN_FLEX_CATEGORY]
            rng = f"{b['target_range'][0]}-{b['target_range'][1]}%" if b["target_range"] else "not configured"
            delta = f"{b['delta_points']} pts" if b["delta_points"] else "--"
            rows.append([MARGIN_FLEX_CATEGORY, f"{b['actual_pct']}%", rng, b["status"], delta])
        parts.append(_md_table(headers, rows))

    return "\n".join(parts) + "\n"


def build_llm_context(event, lookups):
    """Step 3.5c's entire fallback layer: enough self-contained context for
    an LLM to resolve one event without re-deriving org-chart facts or
    recalling category definitions from elsewhere. `category_options` is
    always exactly the three from CATEGORY_OPTIONS_5C -- see that constant's
    comment for why reaching this function at all already rules out the
    other four categories."""
    _, _participants_set, others = _participants(event, lookups["owner_email"], lookups["ignored_addresses"])
    return {
        "participants_detail": [_describe_participant(p, lookups) for p in sorted(others)],
        "functional_areas_touched": _functional_areas_for(others, lookups),
        "category_options": CATEGORY_OPTIONS_5C,
    }


def cmd_report(args):
    plan = load_json(args.plan)
    events = load_json(args.events)
    llm_resolutions = load_json(args.llm_resolutions) if args.llm_resolutions else {}

    profile = plan["profile"]
    lookups = build_lookups(profile)
    period = plan["period"]
    period_start = datetime.strptime(period["start_date"], "%Y-%m-%d").date()
    period_end = datetime.strptime(period["end_date"], "%Y-%m-%d").date()

    # Defensive: only report on events that actually overlap the requested
    # period, even though `plan`'s own fetch parameters should already have
    # scoped `--events` correctly. Found via testing: reusing a broader
    # events file (e.g. a full month) against a single-day plan silently
    # included every day's events instead of failing loudly -- worth a cheap
    # safety net here rather than trusting the caller never passes a stale
    # or over-broad file. A multi-day event (a PTO block spanning outside
    # the period) still counts if any part of it overlaps the period.
    range_start = datetime.combine(period_start, datetime.min.time())
    range_end = datetime.combine(period_end + timedelta(days=1), datetime.min.time())

    def _overlaps_period(e):
        if not _has_concrete_time(e):
            return False
        s, en = _event_times(e)
        return s < range_end and en > range_start

    events = [e for e in events if not e.get("isCancelled") and _overlaps_period(e)]

    classified = []
    for e in events:
        result = classify_primary_category(e, lookups)
        if result["needs_llm"] and e.get("id") in llm_resolutions:
            resolved = llm_resolutions[e["id"]]
            result = dict(result, category=resolved.get("category"),
                          reason=resolved.get("reason", "resolved via LLM judgment (5c)"), needs_llm=False)
        classified.append((e, result))

    events_with_category = [(e, r["category"]) for e, r in classified]

    tagged_events = []
    for e, r in classified:
        category = r["category"]
        subject = e.get("subject") or ""
        _, _participants_set, others = _participants(e, lookups["owner_email"], lookups["ignored_addresses"])
        ext_domains = set(r.get("external_domains", []))

        start = end = None
        if _has_concrete_time(e):
            start, end = _event_times(e)

        # A known-series entry's own `tags` field pre-sets any Step 4 tag,
        # overriding the computed value for that key -- e.g. "Give Triage"
        # (Operating rhythm via known-series) pre-set to Functional Area
        # Systems, since its attendee-driven computed tag would otherwise
        # reflect whichever internal staffer happens to attend that week
        # rather than the meeting's own consistent subject matter.
        series_tags = r.get("series_tags") or {}
        computed_tags = {
            "audience": compute_audience_tag(others, ext_domains, lookups) if category else None,
            "functional_areas": compute_functional_area_tags(subject, others, category, ext_domains, lookups) if category else [],
            "work_mode": compute_work_mode(subject, category, others) if category else None,
            "cadence": compute_cadence(subject, r.get("matched_series")),
            "time_context": None,
            "outcome": compute_outcome(subject),
        }
        tags = {k: (series_tags[k] if k in series_tags else v) for k, v in computed_tags.items()}

        tagged_events.append({
            "id": e.get("id"), "subject": e.get("subject", "(No title)"),
            "date": _format_date(start) if start else None,
            "start": start.strftime("%H:%M") if start else None,
            "end": end.strftime("%H:%M") if end else None,
            "duration_minutes": int((end - start).total_seconds() / 60) if start and end else None,
            "is_all_day": e.get("isAllDay", False),
            "category": category,
            "category_reason": r["reason"],
            "needs_llm": r["needs_llm"],
            "matched_series": r.get("matched_series"),
            "participants": sorted(_participants_set),
            "tags": tags,
            "web_link": e.get("webLink", ""),
        })

    capacity_blocks_raw = [e for e, c in events_with_category if c == "Capacity unavailable" and _has_concrete_time(e)]
    for te, (e, r) in zip(tagged_events, classified):
        if not te["start"] or "time_context" in (r.get("series_tags") or {}):
            continue
        start, end = _event_times(e)
        category = r["category"]
        is_travel = bool(TRAVEL_SIGNAL_PATTERN.search(e.get("subject") or ""))
        if e.get("isAllDay"):
            # normal-hours/after-hours is a same-day time-of-day comparison and
            # doesn't mean anything for a block that spans whole days (found via
            # smoke test: a multi-day all-day PTO block was nonsensically tagged
            # "after-hours" because its 00:00 start time falls before the working
            # window). Still surface "travel" when it applies; otherwise unset.
            te["tags"]["time_context"] = "travel" if (category == "Capacity unavailable" and is_travel) else None
            continue
        weekday = WEEKDAY_NAMES[start.weekday()]
        overlaps_cap = category != "Capacity unavailable" and any(
            start < _event_times(b)[1] and end > _event_times(b)[0] for b in capacity_blocks_raw
        )
        te["tags"]["time_context"] = compute_time_context(
            start, end, lookups["working_hours"], weekday, category, is_travel, overlaps_cap
        )

    unresolved_events = []
    for te, (e, r) in zip(tagged_events, classified):
        if te["needs_llm"]:
            te = dict(te, **build_llm_context(e, lookups))
            unresolved_events.append(te)

    report = {
        "period": period,
        "events": tagged_events,
        "unresolved_events": unresolved_events,
        "conflicts": detect_conflicts(events_with_category),
        "schedule_health": compute_schedule_health(events_with_category, lookups["working_hours"]),
        "meetings_needing_prep": flag_meetings_needing_prep(
            events_with_category, lookups["owner_email"], lookups["owner_domain"], lookups["ignored_addresses"]),
    }

    if unresolved_events:
        report["category_definitions_for_5c"] = CATEGORY_DEFINITIONS_5C
        report["resolution_instructions"] = (
            "For each entry in unresolved_events, choose exactly one of its own "
            "category_options (always Operating rhythm / Strategy and transformation / "
            "Stakeholder partnership) based on subject, cadence, and participants_detail "
            "(each attendee's name/role/Reports-Team-membership/functional_areas), reasoning "
            "against category_definitions_for_5c. Write the choices as a JSON object mapping "
            "event id -> {\"category\": <choice>, \"reason\": <one sentence>} to a file and pass "
            "it to `report --llm-resolutions <file>` to get the fully resolved output. Use the "
            "exact ids given here -- never guess one. If a genuinely recurring pattern emerges "
            "(the same subject keeps landing in 5c), that's a known_meeting_series candidate, "
            "not something to keep resolving by hand every time -- see acos-aboutme's sticky-"
            "correction flow rather than re-answering the same event's series indefinitely."
        )

    if period["type"] in ("week", "month"):
        time_allocation = compute_time_allocation(events_with_category, period_start, period_end, lookups["working_hours"])
        report["time_allocation"] = time_allocation
        report["benchmark"] = compute_benchmark(time_allocation, lookups)

    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, indent=2))


def cmd_correct(args):
    """Step 4: the ONLY write this whole skill ever performs, and it touches
    exactly one sub-key of acos-aboutme's shared profile -- see this module's
    docstring for why. Update-in-place if an existing known_meeting_series
    entry already shares any of the given match_patterns (or matches
    --series-name); otherwise append a new entry. Either way, every other
    field and every other byte of the profile round-trips untouched -- see
    save_known_series_atomic's own comment for why a targeted splice replaced
    this function's first version (a full-file rewrite)."""
    profile = load_json(args.aboutme)
    cal = profile.setdefault("calendar_analysis", {})
    series_list = cal.setdefault("known_meeting_series", [])

    patterns = [p.lower() for p in args.match_pattern]
    tags = {}
    if args.tags:
        try:
            tags = json.loads(args.tags)
        except json.JSONDecodeError as e:
            _fail(f"--tags is not valid JSON: {e}")
        if not isinstance(tags, dict):
            _fail("--tags must be a JSON object, e.g. '{\"functional_areas\": [\"Systems\"]}'")

    existing = None
    for entry in series_list:
        entry_patterns = {p.lower() for p in entry.get("match_patterns", [])}
        if entry_patterns & set(patterns):
            existing = entry
            break
        if args.series_name and (entry.get("name") or "").lower() == args.series_name.lower():
            existing = entry
            break

    today = date.today().isoformat()

    if existing:
        action = "updated"
        if args.category:
            existing["category"] = args.category
        if tags:
            existing["tags"] = {**existing.get("tags", {}), **tags}
        if args.notes:
            existing["notes"] = args.notes
        existing_patterns = {p.lower() for p in existing.get("match_patterns", [])}
        existing.setdefault("match_patterns", [])
        for p in patterns:
            if p not in existing_patterns:
                existing["match_patterns"].append(p)
        existing["last_corrected"] = today
        result_entry = existing
    else:
        if not args.category:
            _fail("no existing known-series entry matches these patterns -- creating a new one needs --category")
        action = "created"
        new_entry = {
            "name": args.series_name or patterns[0],
            "match_patterns": patterns,
            "category": args.category,
            "tags": tags,
            "notes": args.notes,
            "last_corrected": today,
        }
        series_list.append(new_entry)
        result_entry = new_entry

    save_known_series_atomic(args.aboutme, series_list, profile)
    print(json.dumps({"action": action, "entry": result_entry}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Resolve the period and emit the outlook_calendar_search params to fetch")
    p_plan.add_argument("--period", choices=["day", "week", "month"], required=True)
    p_plan.add_argument("--date", help="Reference date YYYY-MM-DD (default: today). Anchors the resolved day/week/month.")
    p_plan.add_argument("--aboutme", default=DEFAULT_ABOUTME_PATH, help="Path to acos-aboutme's state/profile.json")
    p_plan.set_defaults(func=cmd_plan)

    p_report = sub.add_parser("report", help="Classify events and compute the full structured report")
    p_report.add_argument("--plan", required=True, help="Path to the JSON emitted by the plan subcommand")
    p_report.add_argument("--events", required=True, help="Path to a JSON array of every fetched event, all pages concatenated")
    p_report.add_argument("--llm-resolutions", default=None,
                           help="Optional path to a JSON object mapping event id -> {category, reason}, "
                                "for events flagged needs_llm (Step 3.5c). Omit on a first pass.")
    p_report.add_argument("--format", choices=["json", "markdown"], default="json")
    p_report.set_defaults(func=cmd_report)

    p_correct = sub.add_parser(
        "correct",
        help="Sticky correction: create or update a known_meeting_series entry (the one write this skill ever makes)")
    p_correct.add_argument("--aboutme", default=DEFAULT_ABOUTME_PATH, help="Path to acos-aboutme's state/profile.json")
    p_correct.add_argument("--match-pattern", action="append", required=True, dest="match_pattern",
                            help="Lowercase substring checked against the event subject. Repeat for aliases "
                                 "(e.g. --match-pattern 'tech/marketing weekly pow-wow' --match-pattern martech). "
                                 "If any of these already matches an existing entry, that entry is updated in place "
                                 "instead of creating a duplicate.")
    p_correct.add_argument("--series-name", default=None, help="Human-readable name; also used to find an existing "
                                                                 "entry by name if no pattern matches. Defaults to "
                                                                 "the first --match-pattern when creating a new entry.")
    p_correct.add_argument("--category", choices=PRIMARY_CATEGORIES, default=None,
                            help="Required when creating a new entry; optional when updating one (omit to leave "
                                 "the existing category as-is and only touch tags/notes).")
    p_correct.add_argument("--tags", default=None,
                            help="JSON object of Step-4 tag overrides to merge in, e.g. "
                                 "'{\"functional_areas\": [\"Systems\"]}'. Merged into any existing tags, not replaced.")
    p_correct.add_argument("--notes", default=None, help="Free-text note, replaces any existing note on this entry.")
    p_correct.set_defaults(func=cmd_correct)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
