"""Shared helpers for the contact_research skill: state I/O, validation, redaction, naming."""
import json, os, re, datetime, csv

STAGES = ["init", "hubspot", "associations", "activity", "derived", "research", "rendered"]

CHARACTERIZATION_BLOCKLIST = [
    "personality", "mindset", "demeanor", "prefers", "preference", "responds best",
    "approach him", "approach her", "discreet", "temperament", "engage him by", "engage her by",
    "topics to avoid",
]

RESTRICTED_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "ssn"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "card_or_account_number"),
    (re.compile(r"\b(?:acct|account|routing|aba)\b[^\n]{0,30}\b\d{6,}\b", re.I), "account_number"),
]
HEALTH_HARDSHIP_LEXICON = [
    "cancer", "diagnos", "hospice", "surgery", "chemo", "dementia", "alzheimer", "depression", "rehab",
    "addiction", "bankrupt", "foreclos", "divorce", "terminal", "illness", "disability", "medical",
]

ROLE_LABELS = {"employee", "board member", "officer", "founder", "owner", "staff", "volunteer leader",
               "director", "trustee", "executive"}
REFERRAL_LABELS = {"referred by", "referral", "referrer"}
PLACEHOLDER_FIRSTNAMES = {"husband", "wife", "spouse", "guest", "unknown", "tbd", "partner", "plus one", ""}


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def contact_path(run_dir, hid):
    return os.path.join(run_dir, "contacts", f"{hid}.json")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_manifest(run_dir):
    m = load_json(os.path.join(run_dir, "manifest.json"))
    if m is None:
        raise SystemExit(f"No manifest.json in {run_dir}; run init_run.py first.")
    return m


def save_manifest(run_dir, m):
    save_json(os.path.join(run_dir, "manifest.json"), m)


def list_contacts(run_dir):
    d = os.path.join(run_dir, "contacts")
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            out.append(load_json(os.path.join(d, fn)))
    return out


def valid_id(hid):
    return isinstance(hid, str) and hid.isdigit()


def normalize_id(raw):
    """Return a clean string ID or None. Rejects scientific notation / decimals (Excel damage)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if re.fullmatch(r"\d+", s):
        return s
    if re.fullmatch(r"\d+\.0+", s):
        return s.split(".")[0]
    return None  # e.g. "2.44057E+11"


def recount(run_dir):
    m = load_manifest(run_dir)
    cs = list_contacts(run_dir)
    c = {"total": len(cs), "init": 0, "hubspot": 0, "researched": 0, "rendered": 0, "rejected": m["counts"].get("rejected", 0)}
    for ct in cs:
        st = ct.get("status", {}).get("stages", {})
        c["init"] += 1
        if st.get("hubspot"):
            c["hubspot"] += 1
        if st.get("research"):
            c["researched"] += 1
        if st.get("rendered"):
            c["rendered"] += 1
    m["counts"] = c
    save_manifest(run_dir, m)
    return c


# ------------------------------------------------------------------ redaction
def screen_text(text):
    """Return (clean_text, hit_reason or None)."""
    if not text:
        return text, None
    for pat, reason in RESTRICTED_PATTERNS:
        if pat.search(text):
            return "[redacted – possible Restricted content]", reason
    low = text.lower()
    for w in HEALTH_HARDSHIP_LEXICON:
        if w in low:
            return "[redacted – possible Restricted content]", f"lexicon:{w}"
    return text, None


def contains_characterization(text):
    if not text:
        return None
    low = text.lower()
    for w in CHARACTERIZATION_BLOCKLIST:
        if w in low:
            return w
    return None


# ------------------------------------------------------------------ naming
def safe(s):
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(s or "")).strip("_")
    return s or "Unknown"


def profile_filename(ct, convention):
    hid = ct["hs_object_id"]
    props = (ct.get("hubspot") or {}).get("properties") or {}
    inp = ct.get("input") or {}
    first = safe(props.get("firstname") or inp.get("firstname"))
    last = safe(props.get("lastname") or inp.get("lastname"))
    owner = safe(props.get("owner_name") or "Unassigned")
    if convention == 2:
        return f"{last}_{first}_{hid}_profile.pdf"
    if convention == 3:
        return f"{owner}_{last}_{first}_{hid}_profile.pdf"
    return f"{hid}_{first}_{last}_profile.pdf"


def read_table(path):
    """Read CSV or XLSX into list of dicts (header row = keys)."""
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        hdr = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [dict(zip(hdr, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
