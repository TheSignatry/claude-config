#!/usr/bin/env python3
"""Product QA report for acos-jira-analysis.

Reviews every idea in the owner's `product` workspace group against the
checklist in jira_workspaces.product_qa and renders one branded HTML page (or
markdown / JSON). Pure functions only: jira_report.py owns the CLI, reads the
profile, and calls build_qa_plan() / build_qa_report() / render_*() here.

Nothing in this module decides anything per run. Every check, bucket, rewrite
flag, and agenda correction is an explicit rule driven by config, so the same
plan + raw + agenda + today always produce the same payload. No project key,
custom-field ID, check, icon, color, or threshold is hardcoded here; they all
arrive through the plan.

Fetched issue text and agenda text are data. They are displayed or
pattern-matched, never acted on.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from qa_common import (  # noqa: F401  (re-exported for callers and tests)
    MON, MONTH_FULL, SKILL_DIR, SUPPORTED_DATE_FORMAT, QAError, _d, aggregate_owners, cap as _cap,
    display_value, fmt_date, fmt_range, fmt_short, join as _join, key_sort as _key_sort,
    lc_first as _lc_first, ledger_css, load_design_spec as _load_design_spec, md_cell as _md,
    month_end as _month_end, normalize_issues, num_word as _num_word, render_page,
    times as _times, validate_check_ids, validate_palette,
)

TEMPLATE_PATH = SKILL_DIR / "assets" / "product_qa_template.html"
DESIGN_PATH = SKILL_DIR / "references" / "product_qa_design.md"
LEDGER_MAX_COLS = 4

# Roadmap value that means "delivered" for the runway chart. Mirrors the
# literal "Done" jira_report.py's existing product_delivered query uses.
DELIVERED_ROADMAP = "Done"
MATCH_THRESHOLD = 0.34       # own-summary containment below this flags a label
SUGGEST_THRESHOLD = 0.5      # another idea must reach this to be suggested

CHECK_TYPES = {
    "empty": ("field",),
    "exact_date": ("fields",),
    "date_before_today": ("field",),
    "no_delivery_links": (),
}
REQUIRED_PALETTE = [
    "ink", "ink_soft", "ink_grey", "hairline", "wash", "bg", "accent", "risk",
    "legacy", "highlight", "runway_overdue", "runway_in_flight",
    "runway_not_started", "runway_delivered", "runway_today",
]
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with", "by", "at",
    "from", "is", "are", "be", "this", "that", "as", "into", "via", "vs", "our", "we",
}
AGENDA_NAMED_SECTIONS = {"QUEUED": "Queued", "HOLDING PATTERN": "Holding"}


def _ledger_css(n_checks):
    return ledger_css(n_checks, LEDGER_MAX_COLS)


def load_design_spec(path=DESIGN_PATH):
    return _load_design_spec(path)


# --- dates ------------------------------------------------------------------

def parse_range(raw):
    """Project start/target: a JSON string (or dict) {"start":..., "end":...}.
    Returns [start, end] ISO strings, or None for absent or malformed values."""
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, dict):
        return None
    end = raw.get("end")
    start = raw.get("start") or end
    try:
        _d(start), _d(end)
    except (TypeError, ValueError):
        return None
    return [start, end]


# --- config validation ------------------------------------------------------

def validate_qa_config(qa, pf):
    """Fail loudly on anything the report can't honour. Returns enabled checks."""
    if not isinstance(qa, dict) or not qa.get("checks"):
        raise QAError("jira_workspaces.product_qa is missing or has no checks configured.")
    if qa.get("date_format", SUPPORTED_DATE_FORMAT) != SUPPORTED_DATE_FORMAT:
        raise QAError(f"product_qa.date_format {qa.get('date_format')!r} is not supported; only {SUPPORTED_DATE_FORMAT!r} is.")
    for key in ("horizon_days", "chart_lookback_days"):
        if not isinstance(qa.get(key), int) or qa[key] < 0:
            raise QAError(f"product_qa.{key} must be a non-negative integer.")
    palette = qa.get("palette") or {}
    validate_palette("product_qa.palette", palette, REQUIRED_PALETTE)
    validate_check_ids("product_qa", qa["checks"])

    enabled = []
    for c in qa["checks"]:
        cid = c["id"]
        ctype = c.get("type")
        if ctype not in CHECK_TYPES:
            raise QAError(f"product_qa check {cid!r} has unknown type {ctype!r}.")
        for need in CHECK_TYPES[ctype]:
            keys = c.get(need)
            keys = keys if need == "fields" else [keys]
            if not keys or not isinstance(keys, list):
                raise QAError(f"product_qa check {cid!r} ({ctype}) needs {need!r}.")
            for fk in keys:
                if not isinstance(pf.get(fk), str):
                    raise QAError(f"product_qa check {cid!r} references unknown field key {fk!r} (not in product_fields).")
        if ctype == "date_before_today" and c.get("part", "end") not in ("start", "end"):
            raise QAError(f"product_qa check {cid!r} has part {c.get('part')!r}; use 'start' or 'end'.")
        if c.get("color_role", "ink") not in palette:
            raise QAError(f"product_qa check {cid!r} has color_role {c.get('color_role')!r}, which is not in the palette.")
        if c.get("enabled", True):
            enabled.append(c)
    if not enabled:
        raise QAError("product_qa has no enabled checks.")

    rules = qa.get("rewrite_rules") or {}
    for name, rule in rules.items():
        if name.startswith("_") or name == "featured_suffix":
            continue
        if name not in REWRITE_RULES:
            raise QAError(f"product_qa.rewrite_rules has unknown rule {name!r}.")
        for pat in rule.get("patterns", []) + ([rule["pattern"]] if rule.get("pattern") else []):
            try:
                re.compile(pat)
            except re.error as e:
                raise QAError(f"product_qa.rewrite_rules.{name} has an invalid regex: {e}.")
    return enabled


# --- plan -------------------------------------------------------------------

def _name_tokens(profile):
    names = [((profile.get("owner") or {}).get("full_name") or "")]
    for group in ("staff", "reports", "team"):
        names += [(p or {}).get("name") or "" for p in profile.get(group) or []]
    return sorted({t for n in names for t in re.findall(r"[a-z0-9]+", n.lower()) if len(t) > 1})


def qa_fields(pf, enabled_checks):
    """summary/status/assignee/issuelinks, every field an enabled check reads,
    plus the fields the report itself always needs (target, roadmap, archived)."""
    keys = ["project_target", "roadmap", "idea_archived"]
    for c in enabled_checks:
        if c.get("field"):
            keys.append(c["field"])
        keys += c.get("fields") or []
    ids = []
    for k in keys:
        if isinstance(pf.get(k), str) and pf[k] not in ids:
            ids.append(pf[k])
    return ["summary", "status", "assignee", "issuelinks"] + ids


def build_qa_plan(workspaces, pf, profile, cloud_id, today, agenda_text=None):
    product_keys = workspaces.get("product") or []
    if not product_keys:
        raise QAError("jira_workspaces.product has no project keys; the Product QA report has nothing to review.")
    qa = workspaces.get("product_qa")
    if not qa:
        raise QAError("jira_workspaces.product_qa is not configured in acos-aboutme (profile or defaults).")
    for k in ("roadmap", "idea_archived", "project_target"):
        if not isinstance(pf.get(k), str):
            raise QAError(f"product_fields.{k} is not set; the Product QA report needs it.")
    enabled = validate_qa_config(qa, pf)
    fields = qa_fields(pf, enabled)
    keys = ", ".join(product_keys)
    roadmap_ex = ", ".join(f'"{v}"' for v in qa.get("qa_roadmap_exclude") or [])
    roadmap_clause = f' AND "Roadmap" NOT IN ({roadmap_ex})' if roadmap_ex else ""
    lookback = (today - timedelta(days=qa["chart_lookback_days"] + 30)).isoformat()
    agenda = parse_agenda(agenda_text, product_keys) if agenda_text else None
    agenda_keys = sorted({e["key"] for e in agenda["entries"]}, key=_key_sort) if agenda else []

    queries = [{
        "id": "product_qa",
        "jql": f"project in ({keys}) AND statusCategory != Done{roadmap_clause} ORDER BY key ASC",
        "fields": fields,
        "description": "Product group ideas that may need QA (whole team).",
    }]
    if agenda_keys:
        queries.append({
            "id": "product_qa_agenda",
            "jql": f"key in ({', '.join(agenda_keys)}) ORDER BY key ASC",
            "fields": fields,
            "description": "Every agenda key, including closed, archived, or Roadmap-excluded ideas, so the corrections section can name them.",
        })
    queries.append({
        "id": "product_qa_delivered",
        "jql": f'project in ({keys}) AND "Roadmap" = "{DELIVERED_ROADMAP}" AND updated >= "{lookback}" ORDER BY key ASC',
        "fields": fields,
        "description": "Ideas delivered inside the chart window. The updated bound is a fetch-volume guard; the real filter (exact Project target between chart start and today) runs in Python.",
    })
    return {
        "report": "product_qa",
        "cloud_id": cloud_id,
        "site": f"https://{cloud_id}/browse/",
        "product_keys": product_keys,
        "product_fields": pf,
        "product_qa": qa,
        "people_tokens": _name_tokens(profile or {}),
        "agenda_keys": agenda_keys,
        "queries": queries,
    }


# --- per-idea evaluation ----------------------------------------------------

def _delivery(fields, link_types, product_keys):
    out, seen = [], set()
    for link in fields.get("issuelinks") or []:
        if (link.get("type") or {}).get("name") not in link_types:
            continue
        other = link.get("outwardIssue") or link.get("inwardIssue") or {}
        key = other.get("key") or ""
        if not key or key.split("-")[0] in product_keys or key in seen:
            continue
        seen.add(key)
        st = (other.get("fields") or {}).get("status") or {}
        out.append({"key": key, "done": (st.get("statusCategory") or {}).get("key") == "done", "status": st.get("name", "")})
    return out


def parse_idea(issue, pf, qa, product_keys):
    f = issue.get("fields") or {}
    status = f.get("status") or {}
    date_keys = {"project_target"}
    for c in qa["checks"]:
        if c.get("type") in ("exact_date", "date_before_today"):
            date_keys.update(c.get("fields") or [c.get("field")])
    return {
        "key": issue["key"],
        "summary": f.get("summary") or "",
        "status": status.get("name") or "",
        "status_cat": (status.get("statusCategory") or {}).get("key") or "",
        "assignee": display_value(f.get("assignee")) or "Unassigned",
        "roadmap": display_value(f.get(pf["roadmap"])),
        "archived": display_value(f.get(pf["idea_archived"])) is not None,
        "ranges": {k: parse_range(f.get(pf[k])) for k in date_keys if isinstance(pf.get(k), str)},
        "raw": f,
        "delivery": _delivery(f, qa.get("delivery_link_types") or [], product_keys),
    }


def exclusion_reasons(idea, qa):
    ex = qa.get("exclude_from_qa") or {}
    reasons = []
    if ex.get("archived", True) and idea["archived"]:
        reasons.append("archived")
    if idea["roadmap"] in (ex.get("roadmap_values") or []):
        reasons.append(f"Roadmap {idea['roadmap']}")
    if idea["status_cat"] in (ex.get("status_categories") or []):
        reasons.append(f"status {idea['status']}")
    return reasons


def _label(field_key):
    return field_key.replace("_", " ")


def run_checks(idea, checks, pf, today_iso, excluded):
    flags, tips = {}, {}
    for c in checks:
        cid, ctype, tip = c["id"], c["type"], c["name"]
        if ctype == "empty":
            fail = display_value(idea["raw"].get(pf[c["field"]])) is None
        elif ctype == "exact_date":
            parts = []
            for fk in c["fields"]:
                r = idea["ranges"].get(fk)
                if r is None:
                    parts.append(f"{_label(fk)} is empty")
                elif r[0] != r[1]:
                    parts.append(f"{_label(fk)} is {fmt_range(r)}")
            fail = bool(parts)
            tip = f"{c['name']}: " + "; ".join(parts)
        elif ctype == "date_before_today":
            r = idea["ranges"].get(c["field"])
            v = r[0 if c.get("part", "end") == "start" else 1] if r else None
            fail = bool(v) and v < today_iso and not excluded
            if fail:
                tip = f"{c['name']}: {_label(c['field'])} was {fmt_range(r)}"
        else:  # no_delivery_links
            fail = not idea["delivery"]
        flags[cid] = fail
        if fail:
            tips[cid] = tip
    return flags, tips


# --- rewrite rules ----------------------------------------------------------

def _words(text):
    return [t for t in text.split() if re.search(r"[A-Za-z]", t)]


def _rule_min_words(text, rule, ctx):
    n = len(_words(text))
    return rule["message"].format(n=n) if n < rule["value"] else None


def _rule_repeated_word(text, rule, ctx):
    for m in re.finditer(r"\b(\w+)\s+\1\b", text, re.IGNORECASE):
        if m.group(1).lower() not in ("that", "had"):
            return rule["message"].format(match=m.group(0))
    return None


def _rule_misspellings(text, rule, ctx):
    fixes = {k.lower(): v for k, v in (rule.get("map") or {}).items()}
    for word in re.findall(r"[A-Za-z']+", text):
        if word.lower() in fixes:
            return rule["message"].format(word=word, fix=fixes[word.lower()])
    return None


def _rule_relative_date(text, rule, ctx):
    for pat in rule.get("patterns") or []:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return rule["message"].format(match=m.group(0))
    return None


def _rule_list_fragment(text, rule, ctx):
    segs = [s for s in re.split(r"[,;/\n]", text) if s.strip()]
    if len(segs) >= rule["min_segments"] and all(len(_words(s)) <= rule["max_words_per_segment"] for s in segs):
        return rule["message"]
    return None


def _rule_aux_plus_base_verb(text, rule, ctx):
    m = re.search(rule["pattern"], text, re.IGNORECASE)
    return rule["message"].format(match=m.group(0)) if m else None


def _rule_no_outcome_cue(text, rule, ctx):
    if rule.get("applies_to") == "featured_or_overdue" and not (ctx["featured"] or ctx["overdue"]):
        return None
    low = text.lower()
    return None if any(c.lower() in low for c in rule.get("cues") or []) else rule["message"]


# One handler per rule name. A new rule is a config entry plus one function here.
REWRITE_RULES = {
    "min_words": _rule_min_words,
    "repeated_word": _rule_repeated_word,
    "misspellings": _rule_misspellings,
    "relative_date": _rule_relative_date,
    "list_fragment": _rule_list_fragment,
    "aux_plus_base_verb": _rule_aux_plus_base_verb,
    "no_outcome_cue": _rule_no_outcome_cue,
}


def rewrite_reasons(text, rules, ctx):
    reasons = []
    for name, rule in rules.items():
        if name in REWRITE_RULES and isinstance(rule, dict) and rule.get("enabled", True):
            r = REWRITE_RULES[name](text, rule, ctx)
            if r:
                reasons.append(r)
    return reasons


# --- agenda -----------------------------------------------------------------

_SHORTCODE_RE = re.compile(r":[a-z0-9_+\-]+:", re.IGNORECASE)
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")
_MON_RE = "(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\\.?"


def _agenda_date(line, today):
    m = re.match(rf"^(\d{{1,2}})\s+{_MON_RE}$", line, re.IGNORECASE) or None
    if m:
        day, mon = int(m.group(1)), m.group(2)
    else:
        m = re.match(rf"^{_MON_RE}\s+(\d{{1,2}})$", line, re.IGNORECASE)
        if not m:
            return None
        mon, day = m.group(1), int(m.group(2))
    month = MON.index(mon[:3].title()) + 1
    today = today or date.today()
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.isoformat() if best else None


def parse_agenda(text, product_keys, today=None):
    """Deterministic agenda parser. Lines with no key are headers or ignored
    narrative; lines with keys become entries. Nothing is interpreted."""
    key_re = re.compile(rf"\b(?:{'|'.join(re.escape(k) for k in product_keys)})-\d+\b")
    named = dict(AGENDA_NAMED_SECTIONS)
    for k in product_keys:
        named[f"CREATE {k.upper()}"] = f"Create {k}"
    section, sec_date, sub = "Watch", None, None
    entries = []
    for n, raw in enumerate((text or "").splitlines(), 1):
        line = _EMOJI_RE.sub("", _SHORTCODE_RE.sub("", raw)).strip()
        line = re.sub(r"^(?:[-*•·]+|\d+[.)])\s*", "", line).strip()
        if not line:
            continue
        keys = list(key_re.finditer(line))
        if not keys:
            bare = line.rstrip(":").strip()
            iso = _agenda_date(bare, today)
            if iso:
                section, sec_date, sub = fmt_short(iso), iso, None
            elif bare.upper() in named:
                section, sec_date, sub = named[bare.upper()], None, None
            elif bare.lower() in ("featured", "other") and sec_date:
                sub = bare.lower()
            continue
        for i, m in enumerate(keys):
            end = keys[i + 1].start() if i + 1 < len(keys) else len(line)
            label = re.sub(r"\s+", " ", line[m.end():end]).strip(" -:–—\t")
            entries.append({
                "key": m.group(0), "label": label, "line": n, "section": section,
                "date": sec_date, "featured": bool(sec_date and sub == "featured"),
            })
    return {"entries": entries}


def clean_label(label):
    """Drop parentheticals, then status chatter after the first ' - ' that
    follows at least two opening words ("Intake Portal R2.1 - Aiming for...")."""
    s = re.sub(r"\([^)]*\)", " ", label)
    s = re.sub(r"\s+", " ", s).strip()
    for m in re.finditer(r"\s[-–—]\s", s):
        if len(re.findall(r"[A-Za-z0-9]+", s[:m.start()])) >= 2:
            return s[:m.start()].strip()
    return s


def _tokens(text, people):
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and t not in people}


def containment(summary, label, people):
    """Share of the summary's tokens found in the label. Containment, not
    Jaccard, so extra words in a long label don't count against it."""
    s = _tokens(summary, people)
    return len(s & _tokens(label, people)) / len(s) if s else 0.0


# --- payload ----------------------------------------------------------------

def build_qa_report(plan, raw, agenda_text=None, today=None):
    today = today or date.today()
    tiso = today.isoformat()
    pf, qa, product_keys = plan["product_fields"], plan["product_qa"], plan["product_keys"]
    checks = validate_qa_config(qa, pf)
    horizon = (today + timedelta(days=qa["horizon_days"])).isoformat()
    people = set(plan.get("people_tokens") or [])
    started_statuses = set(qa.get("started_statuses") or [])

    ideas = {}
    for qid in ("product_qa", "product_qa_agenda", "product_qa_delivered"):
        for issue in normalize_issues(raw.get(qid)):
            if issue.get("key") and issue["key"] not in ideas:
                ideas[issue["key"]] = parse_idea(issue, pf, qa, product_keys)

    # Agenda: parse, score labels, and reassign a line to the idea it names.
    agenda = parse_agenda(agenda_text, product_keys, today) if agenda_text else None
    has_agenda = agenda is not None
    corrections, notes = [], {}
    entries = agenda["entries"] if agenda else []
    by_orig = {}
    for e in entries:
        by_orig.setdefault(e["key"], []).append(e)
    mismatches = []
    for e in entries:
        idea = ideas.get(e["key"])
        e["listed_as"] = e["key"]
        if not idea or not e["label"]:
            continue
        cleaned = clean_label(e["label"])
        full = re.sub(r"\([^)]*\)", " ", e["label"])
        if max(containment(idea["summary"], full, people), containment(idea["summary"], cleaned, people)) >= MATCH_THRESHOLD:
            continue
        best_key, best = None, 0.0
        for k in sorted(ideas, key=_key_sort):
            if ideas[k]["archived"]:
                continue
            s = containment(ideas[k]["summary"], cleaned, people)
            if s > best:
                best_key, best = k, s
        if best_key and best_key != e["key"] and best >= SUGGEST_THRESHOLD:
            mismatches.append((e, f"Listed as {e['key']}; the {cleaned} idea is {best_key}."))
            notes.setdefault(best_key, []).append(f"Listed on the agenda as {e['key']}")
            e["key"] = best_key
        else:
            mismatches.append((e, f"Label doesn’t match the Jira summary ({idea['summary']})."))

    agenda_by_key = {}
    for e in entries:
        agenda_by_key.setdefault(e["key"], []).append(e)

    # Evaluate every idea.
    rows, delivered, excluded_agenda = [], [], []
    for key in sorted(ideas, key=_key_sort):
        idea = ideas[key]
        reasons = exclusion_reasons(idea, qa)
        excluded = bool(reasons)
        flags, tips = run_checks(idea, checks, pf, tiso, excluded)
        target = idea["ranges"].get("project_target")
        t_end = target[1] if target else None
        ents = agenda_by_key.get(key, [])
        on_agenda = bool(ents)
        if excluded and key in by_orig:
            excluded_agenda.append({"key": key, "summary": idea["summary"], "why": ", ".join(reasons)})
        idea.update({"reasons": reasons, "flags": flags, "tips": tips, "target": target, "t_end": t_end, "ents": ents})
        if excluded:
            if (not idea["archived"] and idea["roadmap"] == DELIVERED_ROADMAP and target
                    and target[0] == target[1]):
                delivered.append(idea)
            continue
        if not ((t_end and t_end <= horizon) or on_agenda):
            continue
        idea["bucket"] = ("overdue" if t_end and t_end < tiso else
                          "soon" if t_end and t_end <= horizon else "later")
        rows.append(idea)

    chart_start = (today - timedelta(days=qa["chart_lookback_days"])).replace(day=1)
    chart_end = _month_end(_d(horizon))
    delivered = [i for i in delivered if chart_start.isoformat() <= i["t_end"] <= tiso]

    rule_cfg = qa.get("rewrite_rules") or {}
    items = []
    for idea in rows + delivered:
        is_row = idea in rows
        featured_ent = next((e for e in idea["ents"] if e["featured"]), None)
        first = featured_ent or (idea["ents"][0] if idea["ents"] else None)
        short = display_value(idea["raw"].get(pf.get("short_description", "")))
        weak = None
        if is_row and short:
            reasons = rewrite_reasons(short, rule_cfg, {"featured": bool(featured_ent), "overdue": idea["bucket"] == "overdue"})
            if reasons:
                weak = " ".join(reasons)
                if featured_ent and rule_cfg.get("featured_suffix"):
                    weak += rule_cfg["featured_suffix"].format(agenda=fmt_short(featured_ent["date"]))
        ranges = idea["ranges"]
        start = ranges.get("project_start")
        n_done = sum(d["done"] for d in idea["delivery"])
        items.append({
            "key": idea["key"],
            "url": plan["site"] + idea["key"],
            "summary": idea["summary"],
            "roadmap": idea["roadmap"],
            "assignee": idea["assignee"],
            "status": idea["status"],
            "target": idea["target"],
            "start": start,
            "targetText": fmt_range(idea["target"]),
            "delivery": idea["delivery"],
            "deliveryText": f"{n_done} of {len(idea['delivery'])}" if idea["delivery"] else "None",
            "qa": idea["flags"],
            "qaTips": idea["tips"] if is_row else {},
            "values": {k: display_value(idea["raw"].get(v)) for k, v in pf.items()
                       if isinstance(v, str) and k not in ("project_target", "project_start", "short_description")},
            "agenda": (fmt_short(first["date"]) if first and first["date"] else first["section"]) if first else None,
            "featured": bool(featured_ent),
            "note": "; ".join(notes.get(idea["key"], [])) or None,
            "shortDesc": short,
            "weak": weak,
            "chartOnly": not is_row,
            "closed": not is_row,
            "bucket": idea["bucket"] if is_row else "delivered",
            "started": idea["status"] in started_statuses,
            "tEnd": idea["t_end"],
        })

    for key, ents in by_orig.items():
        if len(ents) > 1:
            for it in items:
                if it["key"] == key:
                    dup = f"Listed {_times(len(ents))} on the agenda"
                    it["note"] = f"{it['note']}; {dup}" if it["note"] else dup

    open_items = [i for i in items if not i["chartOnly"]]
    by_bucket = {b: [i for i in open_items if i["bucket"] == b] for b in ("overdue", "soon", "later")}
    for b in by_bucket.values():
        b.sort(key=lambda i: (i["tEnd"] or "9", _key_sort(i["key"])))
    order = {i["key"]: n for n, i in enumerate(by_bucket["overdue"] + by_bucket["soon"] + by_bucket["later"])}
    items.sort(key=lambda i: (order.get(i["key"], 10**6), _key_sort(i["key"])))

    check_payload = []
    for c in checks:
        check_payload.append({
            "id": c["id"], "name": c["name"], "rule": c["rule"],
            "risk": c.get("color_role") == "risk",
            "count": sum(1 for i in open_items if i["qa"].get(c["id"])),
        })

    # Chart.
    cs, ce = chart_start.isoformat(), chart_end.isoformat()
    for i in items:
        t = i["target"]
        i["dot"] = bool(t and t[0] == t[1] and cs <= t[1] <= (tiso if i["chartOnly"] else horizon))
    groups = {}
    for i in open_items:
        t = i["target"]
        if t and t[0] != t[1] and cs <= t[1] <= ce:
            groups.setdefault((t[0], t[1]), []).append(i["key"])
    ranges = [{"start": a, "end": b, "keys": ks,
               "label": f"{fmt_range([a, b])}: {len(ks)} idea{'s' if len(ks) > 1 else ''}"}
              for (a, b), ks in sorted(groups.items())]

    # Owners.
    owner_rows = aggregate_owners(open_items, {
        "open": len,
        "overdue": lambda a: sum(i["bucket"] == "overdue" for i in a),
        "soon": lambda a: sum(i["bucket"] == "soon" for i in a),
        "notStarted": lambda a: sum((not i["started"]) and i["bucket"] != "later" for i in a),
        "flags": lambda a: sum(1 for i in a for c in checks if i["qa"].get(c["id"])),
    })

    headline, subhead = _headline(by_bucket, open_items, check_payload, today, horizon, qa["horizon_days"])

    # Agenda corrections, in fixed order.
    if has_agenda:
        for key, ents in sorted(by_orig.items(), key=lambda kv: _key_sort(kv[0])):
            if len(ents) > 1:
                labels = [f"“{e['label']}”" for e in ents]
                labels[-1] = labels[-1][:-1] + ".”"
                corrections.append({"title": f"{key} appears {_times(len(ents))}",
                                    "text": f"Agenda lines: {_join(labels)}"})
        for e, text in mismatches:
            corrections.append({"title": f"{e['listed_as']} label doesn’t match", "text": text})
        not_started = {}
        featured_dates = {i["key"]: next(e["date"] for e in agenda_by_key[i["key"]] if e["featured"])
                          for i in open_items if i["featured"]}
        for i in sorted(open_items, key=lambda i: (featured_dates.get(i["key"], ""), _key_sort(i["key"]))):
            if i["featured"] and not i["started"]:
                extra = []
                if i["assignee"] == "Unassigned":
                    extra.append("unassigned")
                if pf.get("product_area") and display_value(ideas[i["key"]]["raw"].get(pf["product_area"])) is None:
                    extra.append("no product area")
                not_started.setdefault(i["agenda"], []).append(i["key"] + (f" ({', '.join(extra)})" if extra else ""))
        if not_started:
            parts = [f"{d}: {_join(ks)}." for d, ks in not_started.items()]
            corrections.append({"title": "Featured items that haven’t started", "text": " ".join(parts)})
        if excluded_agenda:
            corrections.append({
                "title": "Closed or archived, so drop them from the agenda",
                "text": "; ".join(f"{e['key']} {e['summary']} ({e['why']})" for e in excluded_agenda) + ". They no longer appear in QA.",
            })
        scope = [ideas[k] for k in sorted(set(i["key"] for i in open_items) | set(by_orig) & set(ideas), key=_key_sort)]
        for idea in scope:
            if idea["archived"]:
                continue
            rd, sd = idea["roadmap"] == DELIVERED_ROADMAP, idea["status_cat"] == "done"
            if rd and not sd:
                corrections.append({"title": f"Roadmap and status disagree on {idea['key']}",
                                    "text": f"Roadmap is {DELIVERED_ROADMAP} while status still reads {idea['status']}, so it’s excluded from QA but still looks open on status-based boards."})
            elif sd and idea["roadmap"] and not rd:
                corrections.append({"title": f"Roadmap and status disagree on {idea['key']}",
                                    "text": f"Status is {idea['status']} while Roadmap still reads {idea['roadmap']}."})
        for idea in scope:
            if not idea["archived"] and not idea["roadmap"]:
                other = [_lc_first(c["name"]) for c in checks if idea["flags"].get(c["id"])]
                text = "Ideas without a Roadmap value drop out of roadmap views and the QA query; this one is here only because it’s on the agenda."
                if other:
                    text += f" Its QA flags: {_join(other)}."
                corrections.append({"title": f"{idea['key']} has no Roadmap value", "text": text})

    sections = [
        {"id": "overdue", "title": "Overdue", "cap": "Target end date is before today. Sorted by target date."},
        {"id": "soon", "title": f"Due by {fmt_date(horizon)}",
         "cap": f"Target end date falls within the next {qa['horizon_days']} days. Month-range targets sort by their last day."},
    ]
    if has_agenda:
        sections.append({"id": "later", "title": "On the agenda, due later",
                         "cap": f"Agenda items with a target beyond the {qa['horizon_days']}-day horizon."})

    ex = qa.get("exclude_from_qa") or {}
    ex_parts = (["Archived ideas"] if ex.get("archived", True) else []) + \
               [f"ideas with Roadmap {' or '.join(ex.get('roadmap_values'))}"] * bool(ex.get("roadmap_values")) + \
               ["ideas with a status in the Done category"] * ("done" in (ex.get("status_categories") or []))
    keys_txt = ", ".join(product_keys)
    return {
        "generated": tiso,
        "horizon": horizon,
        "horizonDays": qa["horizon_days"],
        "site": plan["site"],
        "productKeys": product_keys,
        "title": f"Product QA ({keys_txt}), {fmt_date(tiso)}",
        "eyebrow": f"Product roadmap ({keys_txt}) review, {fmt_date(tiso)}",
        "headline": headline,
        "subhead": subhead,
        "hasAgenda": has_agenda,
        "startedStatuses": sorted(started_statuses),
        "notStartedStatuses": sorted({i["status"] for i in open_items if not i["started"]}),
        "excludeText": f"{_join(ex_parts)} are left out of QA." if ex_parts else "",
        "sourceLine": f"Source: Jira Product Discovery project{'s' if len(product_keys) > 1 else ''} {keys_txt} on {plan['cloud_id']}, read {fmt_date(tiso)}. Read-only; nothing in Jira was changed.",
        "checks": check_payload,
        "sections": sections,
        "owners": owner_rows,
        "chart": {"start": cs, "end": ce, "ranges": ranges},
        "items": items,
        "excludedAgenda": excluded_agenda,
        "corrections": corrections,
        "spec": load_design_spec(),
        "counts": {"rows": len(open_items), **{b: len(v) for b, v in by_bucket.items()},
                   "delivered": len(delivered)},
    }


def _headline(by_bucket, open_items, checks, today, horizon, horizon_days):
    od, soon = len(by_bucket["overdue"]), len(by_bucket["soon"])
    first = (f"{_cap(_num_word(od))} idea is past target" if od == 1 else
             f"{_cap(_num_word(od)) if od else 'No'} ideas are past target")
    second = f"{_num_word(soon) if soon else 'none'} more {'is' if soon == 1 else 'are'} due by {fmt_short(horizon)}"
    headline = f"{first}, and {second}."

    sub = []
    if soon:
        ns = sum(1 for i in by_bucket["soon"] if not i["started"])
        part = f"{ns} of the {soon} due in the next {horizon_days} days {'hasn’t' if ns == 1 and soon == 1 else 'haven’t'} started"
        month_end = _month_end(today).isoformat()
        n = sum(1 for i in by_bucket["soon"] if i["target"] and i["target"][0] != i["target"][1] and i["target"][1] <= month_end)
        if n:
            first_next = (_month_end(today) + timedelta(days=1)).isoformat()
            part += (f", and {n} {'carries' if n == 1 else 'carry'} a “{MONTH_FULL[today.month - 1]}” target "
                     f"that becomes overdue on {fmt_short(first_next)}")
        sub.append(part + ".")
    gaps = [c for c in checks if not c["risk"]]
    if gaps and open_items:
        m = max(c["count"] for c in gaps)
        if m:
            top = [re.sub(r"^No ", "", c["name"]) for c in gaps if c["count"] == m]
            many = len(top) > 1
            sub.append(f"The widest gap{'s are' if many else ' is'} {_join(top)}: {m} of {len(open_items)} open ideas "
                       f"{'is' if m == 1 else 'are'} missing {'each' if many else 'it'}.")
    return headline, " ".join(sub)


# --- rendering --------------------------------------------------------------

def render_html(payload, plan, fonts_dir=None, template_path=TEMPLATE_PATH):
    qa = plan["product_qa"]
    enabled = [c for c in qa["checks"] if c.get("enabled", True)]
    return render_page(template_path, payload, qa["palette"], enabled, LEDGER_MAX_COLS, fonts_dir)


def render_markdown(payload):
    out = [f"# {payload['title']}", "", f"**{payload['headline']}** {payload['subhead']}", ""]
    names = {c["id"]: c["name"] for c in payload["checks"]}
    out.append("| Check | Failing |")
    out.append("|---|---|")
    for c in payload["checks"]:
        out.append(f"| {c['name']} | {c['count']} of {payload['counts']['rows']} |")
    for sec in payload["sections"]:
        rows = [i for i in payload["items"] if i["bucket"] == sec["id"]]
        out += ["", f"## {sec['title']} ({len(rows)})", ""]
        if not rows:
            out.append("_None._")
            continue
        out.append("| ID | Summary | Roadmap | Assignee | Status | Target | Delivery | QA |")
        out.append("|---|---|---|---|---|---|---|---|")
        for i in rows:
            qa = ", ".join(names[c] for c in names if i["qa"].get(c)) or "Clear"
            out.append(f"| [{i['key']}]({i['url']}) | {_md(i['summary'])} | {_md(i['roadmap'] or 'None')} | "
                       f"{_md(i['assignee'])} | {_md(i['status'])} | {i['targetText'] or 'None'} | {i['deliveryText']} | {qa} |")
    weak = [i for i in payload["items"] if i["weak"]]
    out += ["", f"## Short descriptions that need a rewrite ({len(weak)})", ""]
    out += [f"{n}. **{i['key']}** {_md(i['summary'])}: {i['weak']}" for n, i in enumerate(weak, 1)] or ["_None._"]
    if payload["hasAgenda"]:
        out += ["", "## Agenda corrections", ""]
        out += [f"{n}. **{c['title']}.** {c['text']}" for n, c in enumerate(payload["corrections"], 1)] or ["_None._"]
    return "\n".join(out) + "\n"
