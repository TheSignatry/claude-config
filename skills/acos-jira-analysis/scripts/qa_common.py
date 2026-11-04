#!/usr/bin/env python3
"""Shared machinery for the Product QA and Support QA reports.

Pure functions only: date formatting, config validation helpers, the
fetched-issue loader, owner-table aggregation, and HTML assembly (base
stylesheet, palette tokens, glyph sprite, fonts, embedded payload). Neither
report hardcodes a project key, field ID, check, icon, or color; those arrive
through the plan.
"""
import base64
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

SKILL_DIR = Path(__file__).resolve().parent.parent
BASE_CSS_PATH = SKILL_DIR / "assets" / "qa_base.css"
DEFAULT_FONTS_DIR = SKILL_DIR.parent / "signatry-brand-core" / "assets" / "fonts"
FONT_FILES = {
    "__LORA__": ("Lora", "Lora-Regular.ttf"),
    "__MUL400__": ("Mulish", "Mulish-Regular.ttf"),
    "__MUL600__": ("Mulish", "Mulish-SemiBold.ttf"),
    "__MUL700__": ("Mulish", "Mulish-Bold.ttf"),
    "__MUL800__": ("Mulish", "Mulish-ExtraBold.ttf"),
}
SUPPORTED_DATE_FORMAT = "dd MMM yyyy"

# Palette key -> CSS custom property, where the name isn't simply --key-with-dashes.
PALETTE_VARS = {
    "highlight": "--hi", "runway_overdue": "--c-over", "runway_in_flight": "--c-flight",
    "runway_not_started": "--c-wait", "runway_delivered": "--c-done", "runway_today": "--c-today",
    "dot_waiting_on_us": "--c-wfs", "dot_waiting_on_customer": "--c-wfc",
    "dot_pending_linked": "--c-pend", "dot_pending_unlinked": "--c-bad", "stale_line": "--c-line",
}
# Progress-bar track; not a brand-palette role, so it has a fixed pair unless
# the palette names one.
TRACK_DEFAULT = ["#e8eaea", "#2a3a40"]
SVG_TAGS = {"g", "path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
NUM_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


class QAError(Exception):
    """Config or input problem; jira_report.py turns it into a one-line JSON error."""


# --- dates ------------------------------------------------------------------

def _d(iso):
    return date.fromisoformat(iso)


def fmt_date(iso):
    if not iso:
        return None
    d = _d(iso)
    return f"{d.day:02d} {MON[d.month - 1]} {d.year}"


def fmt_short(iso):
    d = _d(iso)
    return f"{d.day:02d} {MON[d.month - 1]}"


def fmt_range(r):
    """dd MMM yyyy, compressing shared parts: 01–31 Oct 2026, 01 Oct–31 Dec 2026."""
    if not r:
        return None
    a, b = r
    if a == b:
        return fmt_date(a)
    A, B = _d(a), _d(b)
    if A.year != B.year:
        return f"{fmt_date(a)}–{fmt_date(b)}"
    if A.month == B.month:
        return f"{A.day:02d}–{B.day:02d} {MON[B.month - 1]} {B.year}"
    return f"{A.day:02d} {MON[A.month - 1]}–{B.day:02d} {MON[B.month - 1]} {B.year}"


def month_end(d):
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$")


# --- time -------------------------------------------------------------------

def resolve_tz(name):
    if not name:
        return timezone.utc
    if ZoneInfo is None:
        raise QAError("Python 3.9+ is required for timezone support (zoneinfo).")
    try:
        return ZoneInfo(name)
    except Exception:
        raise QAError(f"Unknown timezone {name!r}; use an IANA name such as America/Chicago.")


def parse_ts(raw, tz):
    """Jira timestamps ("2026-10-23T15:02:11.000-0500") or bare dates (midnight in `tz`)."""
    if not raw or not isinstance(raw, str):
        return None
    m = TS_RE.match(raw.strip())
    if not m:
        return None
    d = date.fromisoformat(m.group(1))
    if m.group(2) is None:
        return datetime(d.year, d.month, d.day, tzinfo=tz)
    off = m.group(5)
    if off is None:
        zone = tz
    elif off == "Z":
        zone = timezone.utc
    else:
        off = off.replace(":", "")
        sign = -1 if off[0] == "-" else 1
        zone = timezone(sign * timedelta(hours=int(off[1:3]), minutes=int(off[3:5])))
    return datetime(d.year, d.month, d.day, int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), tzinfo=zone)


def whole_days(ts, now):
    """Whole days from ts to now, floored, never negative."""
    if ts is None:
        return None
    return max(0, int((now - ts).total_seconds() // 86400))


def local_date(ts, tz):
    return ts.astimezone(tz).date().isoformat() if ts else None


def validate_buckets(block, buckets):
    """Contiguous [low, high] day buckets from 0, ending with an open [low, null]."""
    buckets = buckets or []
    prev = -1
    for b in buckets:
        if not (isinstance(b, list) and len(b) == 2 and isinstance(b[0], int) and b[0] == prev + 1
                and (b[1] is None or (isinstance(b[1], int) and b[1] >= b[0]))):
            raise QAError(f"{block}.aging_buckets must be contiguous [low, high] pairs starting at 0; only the last high may be null.")
        prev = b[1] if b[1] is not None else 10**9
    if not buckets or buckets[-1][1] is not None:
        raise QAError(f"{block}.aging_buckets must end with an open [low, null] bucket.")


# --- small text helpers -----------------------------------------------------

def key_sort(k):
    proj, _, num = k.partition("-")
    return (proj, int(num) if num.isdigit() else 0)


def num_word(n):
    return NUM_WORDS[n] if 0 < n < 10 else str(n)


def cap(s):
    return s[:1].upper() + s[1:]


def lc_first(s):
    return s[:1].lower() + s[1:]


def join(items):
    items = list(items)
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def times(n):
    return {1: "once", 2: "twice"}.get(n, f"{num_word(n)} times")


def display_value(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, dict):
        return display_value(v.get("value") or v.get("name") or v.get("displayName"))
    if isinstance(v, list):
        vals = [x for x in (display_value(i) for i in v) if x]
        return ", ".join(vals) or None
    return str(v)


# --- validation -------------------------------------------------------------

def validate_svg(block, cid, svg):
    if not isinstance(svg, str) or not svg.strip():
        raise QAError(f"{block} check {cid!r} has no svg.")
    try:
        root = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{svg}</svg>')
    except ET.ParseError as e:
        raise QAError(f"{block} check {cid!r} has malformed svg: {e}.")
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if el is not root and tag not in SVG_TAGS:
            raise QAError(f"{block} check {cid!r} svg uses disallowed element <{tag}>.")
        for attr in el.attrib:
            name = attr.split("}")[-1].lower()
            if name.startswith("on") or name == "href":
                raise QAError(f"{block} check {cid!r} svg uses disallowed attribute {name!r}.")


def validate_palette(block, palette, required=()):
    for key in required:
        if key not in palette:
            raise QAError(f"{block} is missing {key!r}.")
    for key, pair in palette.items():
        if key.startswith("_"):
            continue
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(h, str) and HEX_RE.match(h) for h in pair)):
            raise QAError(f"{block}.{key} must be a [light, dark] pair of #rrggbb values.")


def validate_check_ids(block, checks):
    seen = set()
    for c in checks:
        cid = c.get("id")
        if not cid or not re.match(r"^[a-z0-9_-]+$", str(cid)) or cid in seen:
            raise QAError(f"{block} check id {cid!r} is missing, malformed, or duplicated.")
        seen.add(cid)
        if not c.get("name") or not c.get("rule"):
            raise QAError(f"{block} check {cid!r} needs both 'name' and 'rule'.")
        validate_svg(block, cid, c.get("svg"))


def resolve_fields(configured, fallback=None):
    """Field IDs merged key by key, so a profile that sets one still gets the rest."""
    resolved = dict(fallback or {})
    for key, value in (configured or {}).items():
        if value:
            resolved[key] = value
    return resolved


# --- fetched-issue loader ---------------------------------------------------

def normalize_issues(value):
    """Accept a flat issue list, a page ({"issues": [...]} or {"issues":
    {"nodes": [...]}}), or a list of pages. The Rovo connector has returned
    both page shapes."""
    if value is None:
        return []
    if isinstance(value, dict):
        inner = value.get("issues", value.get("nodes"))
        if isinstance(inner, dict):
            inner = inner.get("nodes")
        return normalize_issues(inner) if inner is not None else ([value] if "key" in value else [])
    out = []
    for v in value:
        if isinstance(v, dict) and "key" in v:
            out.append(v)
        else:
            out.extend(normalize_issues(v))
    return out


# --- owners -----------------------------------------------------------------

def aggregate_owners(items, columns):
    """One row per assignee ("Unassigned" included): {"name": ..., <col>: value}.
    `columns` maps a column key to fn(list_of_items) -> value. Sorted by
    open count (len) descending, then name."""
    groups = {}
    for i in items:
        groups.setdefault(i["assignee"], []).append(i)
    rows = []
    for name, arr in groups.items():
        row = {"name": name}
        for key, fn in columns.items():
            row[key] = fn(arr)
        rows.append((len(arr), row))
    return [r for _, r in sorted(rows, key=lambda t: (-t[0], t[1]["name"]))]


# --- rendering --------------------------------------------------------------

def load_design_spec(path):
    """[[title, body], ...] from the top-level '- **Title.** body' bullets of a
    design reference; nested bullets fold into their parent."""
    if not Path(path).exists():
        return []
    spec = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?)\*\*\s*(.*)$", line)
        if m:
            spec.append([m.group(1).rstrip(".:"), m.group(2).strip()])
        elif spec and re.match(r"^\s+- ", line):
            spec[-1][1] = (spec[-1][1] + " " + line.strip()[2:].strip()).strip()
    return [[t, b.replace("`", "").replace("**", "")] for t, b in spec]


def palette_css(palette):
    def block(idx):
        decl = []
        for key, pair in palette.items():
            if key.startswith("_"):
                continue
            var = PALETTE_VARS.get(key, "--" + key.replace("_", "-"))
            decl.append(f"{var}:{pair[idx]};")
        if "track" not in palette:
            decl.append(f"--track:{TRACK_DEFAULT[idx]};")
        return "".join(decl)
    light, dark = block(0), block(1)
    return (f":root{{{light}color-scheme:light;}}\n"
            f"@media (prefers-color-scheme:dark){{:root:not([data-theme=\"light\"]){{{dark}color-scheme:dark;}}}}\n"
            f":root[data-theme=\"dark\"]{{{dark}color-scheme:dark;}}")


def ledger_css(n_checks, max_cols, single_row=False):
    cols = max(1, min(max_cols, n_checks if single_row else math.ceil(n_checks / 2)))
    return ("@media (min-width:761px){"
            f".ledger{{grid-template-columns:repeat({cols},1fr);}}"
            f".ledger button:nth-child({cols}n+1){{border-left:none;padding-left:0;}}"
            f".ledger button:nth-child(n+{cols + 1}){{border-top:1px solid var(--hairline);}}}}")


def sprite(checks):
    return "\n".join(f'    <symbol id="g-{c["id"]}" viewBox="0 0 16 16">{c["svg"]}</symbol>' for c in checks)


def _esc_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_page(template_path, payload, palette, checks, max_cols, fonts_dir=None, single_row=False):
    """Assemble one self-contained page: shared stylesheet, palette tokens,
    ledger grid, glyph sprite, embedded fonts, and the JSON payload."""
    fonts_dir = Path(fonts_dir or DEFAULT_FONTS_DIR)
    if not fonts_dir.is_dir():
        raise QAError(f"Brand fonts not found at {fonts_dir} (expected signatry-brand-core/assets/fonts beside this skill).")
    html = Path(template_path).read_text(encoding="utf-8")
    html = html.replace("/*__BASE_CSS__*/", BASE_CSS_PATH.read_text(encoding="utf-8"))
    for token, (sub, name) in FONT_FILES.items():
        f = fonts_dir / sub / name
        if not f.exists():
            raise QAError(f"Brand font missing: {f}.")
        html = html.replace(token, base64.b64encode(f.read_bytes()).decode("ascii"))
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return (html.replace("__TITLE__", _esc_html(payload["title"]))
                .replace("/*__PALETTE__*/", palette_css(palette))
                .replace("/*__LEDGER_CSS__*/", ledger_css(len(checks), max_cols, single_row))
                .replace("<!--__SPRITE__-->", sprite(checks))
                .replace("__DATA__", data))


def md_cell(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")
