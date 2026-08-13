#!/usr/bin/env python3
"""Deterministic engine for acos-email-sort.

Everything that must produce the same answer for the same input every run
lives here, not in per-run LLM reasoning: urgency scoring, decline/template
matching, precedence resolution, the repeat-decline ledger, and the
folder-existence gate. Claude (via SKILL.md) does the actual O365 tool
calls (fetching messages, moving mail, creating drafts) and only the
genuinely fuzzy calls this script can't resolve (is this 2_review-ambiguous,
is this 3_delegate-worthy) are left to LLM judgment.

Subcommands (each reads/writes plain JSON so Claude can pass data via files):

  check-folders   Compare the folder names Claude found under _claude against
                   config's expected names. Reports missing folders; never
                   creates anything itself.
  classify        Score a batch of messages: priority match (sender/
                   importance/urgent-keyword, plus sender-independent
                   financial-document, deal-document, and HR-lifecycle
                   keyword signals, all suppressed for calendar/OOO subject
                   artifacts), decline-template match, HR/personnel-adjacent
                   sensitivity flag (generic HR jargon plus sender-
                   independent personnel-content keywords), the farewell-
                   note flag, the routine_notification bucket that routes
                   meeting reminders and routine Rippling payroll/task pings
                   straight to 7_toBeFiled, the internal-domain /
                   operational-alert-sender flag that routes straight to
                   2_review ahead of the bulk-mail check, and the
                   EA-scheduling flag that routes straight to 3_delegate.
                   Read-only against the ledger (no mutation).
  record-decline  Called once per message AFTER its decline draft was created
                   successfully. Updates the ledger and reports whether the
                   repeat-decline threshold was just reached.
  render-template Fill a matched template's {first_name} placeholder for a
                   given sender display name and append the standing
                   AI-assistance disclosure footer, returning the subject/
                   html body to hand to outlook_create_reply_draft.
  match-declines  Resolve which decline-template topic applies to a batch of
                   messages already sitting in 4_autorespond (Trevor's own
                   manual "this is a decline" landing zone) -- unlike
                   classify, this never re-runs the sensitive/priority/
                   protected/bulk checks, since Trevor's own placement there
                   already is the judgment call. Falls back to config's
                   fallback_decline_topic when no template's keywords match.
  record-filed    Called once per message AFTER an undetermined message is
                   judged routine and filed to 7_toBeFiled. Tracks a
                   separate filed_senders ledger section and reports whether
                   filed_without_action_threshold was just reached -- the
                   signal behind the "consider unsubscribing" run-summary
                   recommendation (Theme A rec 4).
  bulk-review-status  Diffs 6_bulkToReview's current contents against the
                   previous run's saved snapshot (count, oldest-item age,
                   moved-out/added since last run) and overwrites the
                   snapshot for next time. Purely observational -- never
                   moves or acts on anything (Theme A rec 2).

No subcommand here ever calls an O365 tool, sends mail, or creates a filter —
this script only ever reads its own config/ledger/template files and stdin/
argument data, and prints JSON to stdout.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

DEFAULT_URGENT_KEYWORD_PATTERNS = [
    r"\bapprove(d|s|al)?\b",
    r"\bsign[- ]?off\b",
    r"\bneeds? your (signature|approval|decision)\b",
    r"\bdeadline\b",
    r"\btime[- ]sensitive\b",
    r"\brespond by\b",
    r"\bby (end of day|eod|cob|tomorrow|noon)\b",
    r"\burgent\b",
    r"\bASAP\b",
    r"\bwaiting on you\b",
]

DEFAULT_SENSITIVE_KEYWORD_PATTERNS = [
    r"\bsalary\b",
    r"\btermination\b",
    r"\bterminat(e|ed|ing)\b",
    r"\bleave of absence\b",
    r"\bFMLA\b",
    r"\bmedical\b",
    r"\bdisability\b",
    r"\bharassment\b",
    r"\binvestigation\b",
    r"\bperformance improvement\b",
    r"\bPIP\b",
    r"\bbackground check\b",
    r"\bsocial security\b",
    r"\bssn\b",
    r"\bbenefits enrollment\b",
    r"\bworkers[' ]?comp\b",
    r"\bgrievance\b",
    r"\bboard confidential\b",
    r"\bexecutive session\b",
    r"\bsuccession plan\b",
]

BULK_SENDER_ADDRESS_PATTERNS = [
    r"newsletter", r"no-?reply", r"do-?not-?reply", r"marketing", r"campaign",
    r"\bnews\b", r"digest", r"bulletin", r"webinars?", r"publications",
    r"substack",
]

# Unicode categories used by bulk-send platforms (Marketo, Mailchimp,
# Salesforce Marketing Cloud, Iterable, HubSpot, Substack) to pad the
# preheader with invisible characters and control inbox preview-text
# length: Cf = format characters (zero-width space/joiner, word joiner,
# soft hyphen, etc.), Mn = nonspacing marks. See _has_esp_padding_signature.
_ESP_PADDING_CATEGORIES = {"Cf", "Mn"}


def _has_esp_padding_signature(text, min_invisible=6):
    """True if `text` contains many invisible/format characters (Cf/Mn)
    that are isolated by plain whitespace rather than attached to a
    letter. Real prose essentially never does this -- a combining mark
    or soft hyphen in genuine text sits directly against a letter (e.g.
    a word-wrap hint inside "diffi-cult"), never floating between spaces.
    ESP padding scatters these between spaces to control inbox preview
    length, but different platforms vary how many plain spaces separate
    each invisible character (Substack uses several, others use one), so
    this counts total isolated occurrences rather than requiring them to
    sit immediately adjacent to each other."""
    count = 0
    for i, ch in enumerate(text):
        if unicodedata.category(ch) not in _ESP_PADDING_CATEGORIES:
            continue
        prev = text[i - 1] if i > 0 else " "
        if prev == " " or unicodedata.category(prev) in _ESP_PADDING_CATEGORIES:
            count += 1
            if count >= min_invisible:
                return True
    return False


def is_bulk_or_newsletter(message):
    """Returns (True, reason) if this message looks like a bulk send
    (newsletter/marketing blast) rather than a direct, one-to-one
    solicitation -- used to suppress the decline flow, since drafting a
    personalized decline reply to a bulk sender is pointless (often nobody
    reads it) and this pattern was observed to false-positive on generic
    keyword overlap with newsletter copy (e.g. a CIO newsletter that just
    happens to mention "cybersecurity")."""
    address = ((message.get("sender") or {}).get("address") or message.get("senderAddress") or "").lower()
    for pattern in BULK_SENDER_ADDRESS_PATTERNS:
        if re.search(pattern, address):
            return True, f"sender address matches bulk-mail pattern /{pattern}/"

    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"
    if _has_esp_padding_signature(haystack):
        return True, "body preview contains ESP preheader-padding characters (bulk-send signature)"

    return False, None


GENERIC_SENDER_NAME_TOKENS = {
    "the", "team", "support", "sales", "marketing", "newsletter", "newsletters",
    "notifications", "noreply", "no-reply", "info", "hello", "admin", "updates",
    "help", "billing", "accounts", "office", "service", "services", "care",
}

REQUIRED_FOLDER_KEYS = [
    "priority", "review", "delegate", "autorespond", "drafts_review", "bulk_review", "to_be_filed",
]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_config(path):
    config = load_json(path)
    if not config.get("urgent_keyword_patterns"):
        config["urgent_keyword_patterns"] = DEFAULT_URGENT_KEYWORD_PATTERNS
    if not config.get("sensitive_keyword_patterns"):
        config["sensitive_keyword_patterns"] = DEFAULT_SENSITIVE_KEYWORD_PATTERNS
    config.setdefault("vip_senders", [])
    config.setdefault("partner_vendors", [])
    config.setdefault("protected_senders", [])
    config.setdefault("internal_domain", "")
    config.setdefault("operational_alert_senders", [])
    config.setdefault("ea_name", "")
    config.setdefault("ea_email", "")
    config.setdefault("ea_scheduling_keywords", [])
    config.setdefault("financial_document_keyword_patterns", [])
    config.setdefault("financial_document_excluded_senders", [])
    config.setdefault("deal_document_keyword_patterns", [])
    config.setdefault("hr_lifecycle_keyword_patterns", [])
    config.setdefault("farewell_note_keyword_patterns", [])
    config.setdefault("personnel_content_keyword_patterns", [])
    config.setdefault("meeting_reminder_keyword_patterns", [])
    config.setdefault("routine_payroll_notification_keyword_patterns", [])
    config.setdefault("urgent_keyword_excluded_senders", [])
    config.setdefault("personal_action_request_keyword_patterns", [])
    config.setdefault("vendor_onboarding_keyword_patterns", [])
    config.setdefault("decline_threshold", 3)
    config.setdefault("fallback_decline_topic", "generic_vendor_demo_pitch")
    config.setdefault("filed_without_action_threshold", 3)
    return config


def load_aboutme(path):
    """Returns {} if the acos-aboutme profile doesn't exist — that skill may
    not be installed or enrolled, and this must degrade gracefully rather
    than fail (see acos-aboutme's "For skill authors" section)."""
    if not path or not Path(path).exists():
        return {}
    return load_json(path)


def merge_aboutme(config, aboutme):
    """acos-aboutme's data wins over this skill's own local fallback fields
    whenever it's present and non-empty, per acos-aboutme's own guidance to
    consuming skills — a single source of truth avoids the two drifting out
    of sync. Local fields still work standalone if acos-aboutme isn't
    installed or a given list is empty there."""
    merged = dict(config)
    for key in ("vip_senders", "partner_vendors", "protected_senders"):
        if aboutme.get(key):
            merged[key] = aboutme[key]
    owner = aboutme.get("owner") or {}
    merged["signoff"] = owner.get("signoff") or config.get("signature_first_name") or ""
    owner_email = owner.get("email") or ""
    if "@" in owner_email:
        merged["internal_domain"] = owner_email.split("@", 1)[1].lower()

    staff = aboutme.get("staff") or []
    ea = next((s for s in staff if "executive assistant" in (s.get("role") or "").lower()), None)
    if ea:
        full_name = (ea.get("name") or "").strip()
        merged["ea_name"] = full_name.split()[0] if full_name else merged.get("ea_name", "")
        if ea.get("email"):
            merged["ea_email"] = ea["email"]
    return merged


def load_ledger(path):
    if not Path(path).exists():
        return {"version": 1, "senders": {}}
    return load_json(path)


# --- Minimal YAML-subset parser for references/rejection_templates.yaml ----
# Deliberately narrow: handles only this file's own fixed shape (a top-level
# `templates:` list of flat mappings, each value a plain scalar, a flow list
# `[a, b]`, or a `|` block scalar). Not general YAML. Kept dependency-free
# so template matching stays reproducible even where PyYAML isn't installed.


def _parse_flow_list(value):
    inner = value.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1].strip()
    if not inner:
        return []
    items = []
    for raw in inner.split(","):
        item = raw.strip()
        if len(item) >= 2 and item[0] == item[-1] and item[0] in ("'", '"'):
            item = item[1:-1]
        if item:
            items.append(item)
    return items


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] == '"':
        # Double-quoted YAML scalar: only backslash-escaping we need to
        # honor for this file's content is `\\` -> `\`, so regex patterns
        # like "\\bfoo\\b" decode to the literal `\bfoo\b` word-boundary form.
        return value[1:-1].replace("\\\\", "\\")
    if len(value) >= 2 and value[0] == value[-1] and value[0] == "'":
        return value[1:-1]
    return value


def parse_templates_file(text):
    """Returns {"disclosure_footer": str, "templates": [...]}.

    Top-level scalar keys (e.g. `disclosure_footer: |`) sit as siblings of
    the `templates:` list — this parser tracks which of the two top-level
    sections it's in, since a top-level block scalar isn't a template field.
    """
    lines = text.splitlines()
    templates = []
    top_level = {}
    current = None
    current_key = None
    block_lines = None
    block_indent = None
    block_target = None  # "top" or "template"
    in_templates_section = False
    i = 0
    n = len(lines)

    def flush_block():
        nonlocal block_lines, block_indent, current_key, block_target
        if block_lines is not None:
            while block_lines and block_lines[-1] == "":
                block_lines.pop()
            text_value = "\n".join(block_lines) + "\n"
            if block_target == "top" and current_key is not None:
                top_level[current_key] = text_value
            elif block_target == "template" and current is not None and current_key is not None:
                current[current_key] = text_value
        block_lines = None
        block_indent = None
        current_key = None
        block_target = None

    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))

        if block_lines is not None:
            if raw.strip() == "" or indent >= block_indent:
                block_lines.append(raw[block_indent:] if len(raw) >= block_indent else "")
                i += 1
                continue
            flush_block()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if stripped == "templates:":
            in_templates_section = True
            i += 1
            continue

        if indent == 0 and not stripped.startswith("-"):
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", stripped)
            if m:
                in_templates_section = False
                key, value = m.group(1), m.group(2)
                if value == "|":
                    current_key = key
                    block_indent = indent + 2
                    block_lines = []
                    block_target = "top"
                else:
                    top_level[key] = _unquote(value)
                i += 1
                continue

        if not in_templates_section:
            i += 1
            continue

        m = re.match(r"^-\s*topic:\s*(.+)$", stripped)
        if m:
            if current is not None:
                templates.append(current)
            current = {"topic": _unquote(m.group(1))}
            i += 1
            continue

        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", stripped)
        if m and current is not None:
            key, value = m.group(1), m.group(2)
            if value == "|":
                current_key = key
                block_indent = indent + 2
                block_lines = []
                block_target = "template"
            elif value == "":
                current[key] = []
            elif value.startswith("["):
                current[key] = _parse_flow_list(value)
            else:
                current[key] = _unquote(value)
            i += 1
            continue

        m = re.match(r"^-\s*(.+)$", stripped)
        if m and current is not None and current_key is None:
            # A list item under the most recently opened list-valued key.
            last_key = next(iter(reversed(current.keys())), None)
            if last_key is not None and isinstance(current.get(last_key), list):
                current[last_key].append(_unquote(m.group(1)))
            i += 1
            continue

        i += 1

    flush_block()
    if current is not None:
        templates.append(current)

    for t in templates:
        t.setdefault("subject_patterns", [])
        t.setdefault("body_patterns", [])
        t.setdefault("sender_domains", [])
        t.setdefault("subject_prefix", "Re: ")
        t.setdefault("html_body", "")

    return {"disclosure_footer": top_level.get("disclosure_footer", ""), "templates": templates}


def load_templates(path):
    return parse_templates_file(Path(path).read_text(encoding="utf-8"))["templates"]


def load_disclosure_footer(path):
    return parse_templates_file(Path(path).read_text(encoding="utf-8"))["disclosure_footer"]


# --- classification -----------------------------------------------------


def _compile_all(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _sender_domain(address):
    return address.split("@", 1)[-1].lower().strip() if "@" in (address or "") else ""


CALENDAR_OOO_SUBJECT_PREFIX_PATTERN = re.compile(
    r"^(automatic reply|accepted|declined|tentative|cancell?ed):", re.IGNORECASE
)
CALENDAR_RSVP_SUBJECT_PREFIX_PATTERN = re.compile(
    r"^(accepted|declined|tentative|cancell?ed):", re.IGNORECASE
)


def is_calendar_or_ooo_artifact(message):
    """True if the subject carries an Outlook-generated calendar/OOO prefix
    (Accepted:, Declined:, Tentative:, Canceled:/Cancelled:, Automatic
    reply:) -- these are system artifacts of a meeting response or an
    out-of-office autoreply, never a judgment call the sender made, so they
    should never trigger priority regardless of who sent them or what
    keyword happens to appear in the boilerplate body text. Added
    2026-08-12 (Theme D of state/stage2_accuracy_report.md) after finding a
    VIP's meeting-cancellation notice (flagged via the high-importance flag)
    and an out-of-office autoreply that happened to contain the word
    'urgent' in its own boilerplate (flagged via the urgent-keyword scan)
    both getting marked priority, when Trevor filed both as routine review/
    no-action mail."""
    subject = message.get("subject") or ""
    return bool(CALENDAR_OOO_SUBJECT_PREFIX_PATTERN.match(subject.strip()))


def is_calendar_rsvp_artifact(message):
    """True only for the pure calendar-RSVP subset of is_calendar_or_ooo_
    artifact -- Accepted:/Declined:/Tentative:/Canceled:/Cancelled:, NOT
    Automatic reply:. Added 2026-08-12 (Stage 3 regression, follow-up round
    2 of state/stage3_accuracy_report.md) after score_priority's VIP-sender
    exemption from calendar/OOO suppression (added the same day to fix
    VIP executives' Automatic-reply messages tied to a live initiative)
    turned out to be too broad: it also let a VIP's calendar-accept
    notification ("Accepted: TreisD Meeting") escalate to 1_priority
    purely because a VIP clicked Accept, with zero actual content. An
    Automatic reply is a generated MESSAGE that can carry real content
    (why someone's away, who to contact instead); an RSVP prefix is pure
    attendance metadata and never carries anything worth surfacing,
    regardless of who sent it -- so the VIP exemption only applies when
    this is False."""
    subject = message.get("subject") or ""
    return bool(CALENDAR_RSVP_SUBJECT_PREFIX_PATTERN.match(subject.strip()))


def score_priority(message, config):
    reasons = []
    address = (message.get("sender") or {}).get("address") or message.get("senderAddress") or ""
    domain = _sender_domain(address)
    vip_addresses = {v.get("email", "").lower() for v in config.get("vip_senders", []) if v.get("email")}
    vip_domains = {v.get("domain", "").lower() for v in config.get("vip_senders", []) if v.get("domain")}

    # Guarded by `not is_calendar_rsvp_artifact` (added 2026-08-12, follow-up
    # round 2) -- a VIP's Automatic-reply message can carry real content and
    # survives calendar/OOO suppression below, but a VIP's pure calendar RSVP
    # (Accepted:/Declined:/Tentative:/Canceled:) never does; without this
    # guard a VIP simply clicking "Accept" on a meeting invite was escalating
    # to 1_priority with zero actual content ("Accepted: TreisD Meeting").
    if not is_calendar_rsvp_artifact(message):
        if address.lower() in vip_addresses:
            reasons.append(f"sender {address} is on the executive/VIP list")
        elif domain and domain in vip_domains:
            reasons.append(f"sender domain {domain} is on the executive/VIP list")

    if is_calendar_or_ooo_artifact(message):
        # Narrowed 2026-08-12 (Stage 3 regression #3 of
        # state/stage3_accuracy_report.md): this used to suppress every
        # priority signal unconditionally, including the VIP-sender one
        # above. Real data showed that was too broad -- three separate
        # executives' auto-replies tied to a live internal initiative
        # ("Stewarding AI at The Signatry") were still priority-worthy to
        # Trevor despite being auto-generated. A VIP sender is a judgment
        # about WHO sent it, not an artifact of HOW the message was
        # generated, so it survives this suppression *for Automatic-reply
        # subjects only* (see is_calendar_rsvp_artifact's guard above); the
        # importance flag, urgent-keyword scan, and the sender-independent
        # financial/deal/HR-lifecycle keyword scans below -- all either
        # inherited/templated boilerplate or a content-based false-positive
        # risk -- are suppressed here regardless of sender.
        return reasons

    if (message.get("importance") or "").lower() == "high":
        reasons.append("message flagged high importance")

    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"
    # urgent_keyword_excluded_senders (added 2026-08-12, Stage 3
    # high-severity review, Group F): mirrors financial_document_excluded_
    # senders below -- a small allowlist for senders whose automated report
    # titles reuse a status word ("...DVR Approved") that reads as an
    # approval keyword out of context but is just a trailing label, not a
    # request. Scoped to only this one loop, not the other keyword checks.
    urgent_excluded_senders = {s.lower() for s in config.get("urgent_keyword_excluded_senders", []) if s}
    if address.lower() not in urgent_excluded_senders:
        for pattern in _compile_all(config.get("urgent_keyword_patterns", DEFAULT_URGENT_KEYWORD_PATTERNS)):
            if pattern.search(haystack):
                reasons.append(f"deadline/approval keyword match: /{pattern.pattern}/")
                break

    # The three loops below are sender-independent positive priority
    # signals -- added 2026-08-12 (Theme D rec #2, with Theme G's
    # deal-document enhancement folded in) after the Stage 2 accuracy test
    # found invoices, active deal/contract documents, and HR-lifecycle
    # notices from non-VIP, non-urgent-keyword senders all sitting in
    # 2_review or 7_toBeFiled when Trevor filed every one of them as
    # 1_priority by hand.
    #
    # financial_document_excluded_senders (added 2026-08-12, Stage 3
    # regression #5): a small allowlist of known auto-pay-confirmation
    # senders whose recurring, fully-automated "invoice" notices need no
    # review or action -- e.g. Rippling's weekly spend-management
    # replenishment receipt, which isn't a bill so much as a record that a
    # payment already happened. Only excludes this one signal for that
    # sender, not the deal-document or HR-lifecycle checks below.
    excluded_senders = {s.lower() for s in config.get("financial_document_excluded_senders", []) if s}
    if address.lower() not in excluded_senders:
        for pattern in _compile_all(config.get("financial_document_keyword_patterns", [])):
            if pattern.search(haystack):
                reasons.append(f"financial/invoice document keyword match: /{pattern.pattern}/")
                break

    for pattern in _compile_all(config.get("deal_document_keyword_patterns", [])):
        if pattern.search(haystack):
            reasons.append(f"active deal/contract document keyword match: /{pattern.pattern}/")
            break

    for pattern in _compile_all(config.get("hr_lifecycle_keyword_patterns", [])):
        if pattern.search(haystack):
            reasons.append(f"HR-lifecycle keyword match: /{pattern.pattern}/")
            break

    # personal_action_request_keyword_patterns (added 2026-08-12, Stage 3
    # high-severity review, Group D): a direct, personal ask that names
    # Trevor specifically and needs a reply only he can give -- a letter of
    # recommendation request, a GitHub mention blocking his own project's
    # merge. Distinct from the generic urgent_keyword_patterns list (which
    # is about deadline/approval language in general) -- these are narrow,
    # specific phrasings chosen from real examples, not a broad category.
    for pattern in _compile_all(config.get("personal_action_request_keyword_patterns", [])):
        if pattern.search(haystack):
            reasons.append(f"personal action request keyword match: /{pattern.pattern}/")
            break

    # vendor_onboarding_keyword_patterns (added 2026-08-12, Stage 3
    # high-severity review, Group G): catches a known partner vendor's own
    # account-setup/invitation notice even when it arrives via an unrelated
    # third-party platform (e.g. TeamLogic IT's "You've been invited to join
    # TeamLogic IT Kansas City" sent from notifications.ui.com, not
    # teamlogicit.com) -- the sender-domain-based partner_vendors/
    # protected_contact check never sees these. Deliberately requires BOTH
    # the vendor's own name (reusing partner_vendors' "name" field directly,
    # no separate list to maintain) AND onboarding/invitation language --
    # a bare vendor-name mention (e.g. in a signature block) is not itself
    # priority-worthy, only paired with an actual setup/access action is.
    vendor_names = [v.get("name") for v in config.get("partner_vendors", []) if v.get("name")]
    mentions_vendor_name = any(
        re.search(rf"\b{re.escape(name)}\b", haystack, re.IGNORECASE) for name in vendor_names
    )
    if mentions_vendor_name:
        for pattern in _compile_all(config.get("vendor_onboarding_keyword_patterns", [])):
            if pattern.search(haystack):
                reasons.append(f"known-vendor name + onboarding/invitation keyword match: /{pattern.pattern}/")
                break

    return reasons


def score_sensitive(message, config):
    """personnel_content_keyword_patterns (added 2026-08-12, Theme E of
    state/stage2_accuracy_report.md) is checked as an addition to, not a
    replacement for, sensitive_keyword_patterns -- it exists because the
    generic HR-jargon list above only fires on messages that already sound
    like an HR-system notice (termination, FMLA, PIP, etc.), and misses
    personnel-adjacent content a general employee announces in plain
    language (a colleague's departure, a staff opening) regardless of
    sender domain. Deliberately does NOT include 'accepted an invitation to
    pursue' despite that phrasing appearing in the real Stage 2 example this
    was built from ("Staff Update - Nick Bartelli") -- Trevor pointed out
    that phrase is ambiguous with cybersecurity/access-grant language (a
    real example in the same mailbox: "Invitation accepted - Google Play
    Console", an external contractor being granted account access, not a
    personnel departure), and the Nick Bartelli message is still caught by
    'bittersweet'/'last day at' below regardless, so nothing is lost by
    leaving it out."""
    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"
    for pattern in _compile_all(config.get("sensitive_keyword_patterns", DEFAULT_SENSITIVE_KEYWORD_PATTERNS)):
        if pattern.search(haystack):
            return True, pattern.pattern
    for pattern in _compile_all(config.get("personnel_content_keyword_patterns", [])):
        if pattern.search(haystack):
            return True, pattern.pattern
    return False, None


def find_protected_match(message, config):
    """Returns a reason string if the sender is a known partner vendor or a
    specifically protected contact — either one means never auto-decline,
    regardless of how strongly the message reads like a form pitch."""
    address = ((message.get("sender") or {}).get("address") or message.get("senderAddress") or "").lower()
    domain = _sender_domain(address)

    for partner in config.get("partner_vendors", []):
        partner_domain = (partner.get("domain") or "").lower()
        if partner_domain and partner_domain == domain:
            return f"sender domain {domain} is a known partner vendor ({partner.get('name', partner_domain)}), not a cold vendor"

    for protected in config.get("protected_senders", []):
        protected_email = (protected.get("email") or "").lower()
        if protected_email and protected_email == address:
            reason = protected.get("reason", "protected contact")
            return f"sender {address} is a protected contact: {reason}"

    return None


def find_internal_or_operational_alert(message, config):
    """Returns a reason string if the sender is either on Trevor's own
    internal domain, or a known automated security/service-level alert
    sender for one of our own systems -- both cases should always land in
    2_review for a human glance, never get swept into bulk_review's
    marketing-screen lane or filed sight-unseen. Added 2026-08-12 after the
    Stage 2 real-mailbox accuracy test (see state/stage2_accuracy_report.md,
    Theme B) showed MSSecurity-noreply@microsoft.com PIM alerts, SharePoint
    storage warnings, and internal @thesignatry.com sends all getting caught
    by is_bulk_or_newsletter's no-reply/ESP-padding signature and swept
    toward 6_bulkToReview or 7_toBeFiled, when Trevor consistently filed
    every one of them into 2_review by hand instead.

    Skips calendar/OOO artifacts (2026-08-12, Stage 3 regression #2 of
    state/stage3_accuracy_report.md) -- a calendar accept/decline notice
    from an internal sender (e.g. "Accepted: FirstRate - Dev Kickoff") was
    being forced into 2_review by this check even though is_calendar_or_ooo_
    artifact already establishes these are system artifacts, not judgment
    calls, for the priority check. The same reasoning applies here: this
    check exists to make sure a human sees mail that's actually worth
    seeing, and a calendar-response artifact isn't that, regardless of
    whose mailbox it came from."""
    if is_calendar_or_ooo_artifact(message):
        return None

    address = ((message.get("sender") or {}).get("address") or message.get("senderAddress") or "").lower()
    domain = _sender_domain(address)

    internal_domain = (config.get("internal_domain") or "").lower()
    if internal_domain and domain == internal_domain:
        return f"sender domain {domain} is Trevor's own internal domain — always routed to 2_review, never bulk-screened or filed automatically"

    alert_senders = {s.lower() for s in config.get("operational_alert_senders", []) if s}
    if address in alert_senders:
        return f"sender {address} is a known security/service-level alert sender for our own systems — routed to 2_review, not bulk mail"

    return None


def find_farewell_note(message, config):
    """Returns a reason string if the message reads like a one-time,
    personally-addressed farewell/thank-you note from someone leaving The
    Signatry. A distinct, lighter-touch signal than the HR-lifecycle
    priority keywords in score_priority above (Theme D rec #3 of
    state/stage2_accuracy_report.md): escalating every goodbye note straight
    to 1_priority would be overkill for what's usually a one-time personal
    moment, not an action item, but letting it fall silently into 2_review
    alongside routine review mail with no distinguishing flag risks it being
    skimmed past unanswered. Deliberately narrow patterns -- a bare 'thank
    you' is far too common in ordinary business mail to use as a signal on
    its own."""
    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"
    for pattern in _compile_all(config.get("farewell_note_keyword_patterns", [])):
        if pattern.search(haystack):
            return f"reads like a personal farewell/thank-you note from someone leaving: /{pattern.pattern}/"
    return None


def find_routine_notification(message, config):
    """Returns a reason string if the message matches a known recurring/
    automated notification pattern Trevor has confirmed isn't worth a
    review pass: a meeting reminder, or one of Rippling's routine payroll/
    task-tracking pings. Confirmed by Trevor 2026-08-12 (Theme F of
    state/stage2_accuracy_report.md) -- accepting the report's meeting-
    reminder recommendation in its simpler form (any meeting reminder is
    safe to file, no need to compare the reminder's referenced meeting time
    against the message's own received time). Deliberately narrow content
    patterns, not a blanket rippling.com/hubspot.com sender rule: Trevor was
    explicit that a Rippling notification asking HIM to act (e.g. missing
    receipts on a card transaction) should stay on its normal path toward
    2_review, only the routine payroll/task-tracking boilerplate should be
    filed. Checked before find_protected_match so a reminder from a
    protected/partner-vendor sender (rippling.com and hubspot.com are both
    partner_vendors; a couple of specific senders are also protected_senders)
    doesn't get claimed by that check first."""
    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"

    for pattern in _compile_all(config.get("meeting_reminder_keyword_patterns", [])):
        if pattern.search(haystack):
            return f"meeting-reminder pattern match: /{pattern.pattern}/ — safe to file without review"

    for pattern in _compile_all(config.get("routine_payroll_notification_keyword_patterns", [])):
        if pattern.search(haystack):
            return f"routine Rippling payroll/task-notification pattern match: /{pattern.pattern}/ — not helpful, file without review"

    return None


def find_ea_scheduling_delegate(message, config):
    """Returns a reason string if the message explicitly asks Trevor's
    Executive Assistant to handle scheduling. Confirmed by Trevor
    (2026-08-12, Theme J of state/stage2_accuracy_report.md) as the one
    delegation signal clear enough to be deterministic -- every other
    delegate-worthy judgment (travel logistics, general coordination) stays
    an LLM call, see SKILL.md's Judgment calls section. Requires BOTH an EA
    mention (her configured name, or the generic 'Executive Assistant'
    title) AND separate scheduling language -- neither alone is a reliable
    signal (a message can mention the EA in passing with no scheduling ask,
    or use scheduling language that has nothing to do with her)."""
    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"

    ea_name = (config.get("ea_name") or "").strip()
    mentions_ea = bool(ea_name and re.search(rf"\b{re.escape(ea_name)}\b", haystack, re.IGNORECASE))
    if not mentions_ea:
        mentions_ea = bool(re.search(r"\bexecutive assistant\b", haystack, re.IGNORECASE))
    if not mentions_ea:
        return None

    for pattern in _compile_all(config.get("ea_scheduling_keywords", [])):
        if pattern.search(haystack):
            return f"mentions {ea_name or 'the Executive Assistant'} alongside scheduling language (/{pattern.pattern}/) — a direct ask for the EA to schedule"

    return None


def match_decline_template(message, templates):
    address = (message.get("sender") or {}).get("address") or message.get("senderAddress") or ""
    domain = _sender_domain(address)
    subject = message.get("subject", "")
    body = message.get("bodyPreview", "")

    for template in templates:
        allowed_domains = [d.lower() for d in template.get("sender_domains", [])]
        if allowed_domains and domain not in allowed_domains:
            continue

        subject_patterns = _compile_all(template.get("subject_patterns", []))
        body_patterns = _compile_all(template.get("body_patterns", []))

        subject_hit = next((p.pattern for p in subject_patterns if p.search(subject)), None)
        body_hit = None
        if subject_hit is None:
            body_hit = next((p.pattern for p in body_patterns if p.search(body)), None)

        if subject_hit or body_hit:
            return {
                "topic": template["topic"],
                "matched_on": "subject" if subject_hit else "body",
                "pattern": subject_hit or body_hit,
            }
    return None


def classify_message(message, config, templates, ledger):
    is_sensitive, sensitive_pattern = score_sensitive(message, config)
    priority_reasons = score_priority(message, config)

    if priority_reasons:
        return {
            "id": message.get("id"),
            "bucket_hint": "priority",
            "sensitive": is_sensitive,
            "reasons": priority_reasons,
        }

    if is_sensitive:
        return {
            "id": message.get("id"),
            "bucket_hint": "undetermined",
            "sensitive": True,
            "reasons": [f"personnel/HR-adjacent keyword match: /{sensitive_pattern}/ — never auto-decline; human judgment required"],
        }

    ea_delegate_reason = find_ea_scheduling_delegate(message, config)
    if ea_delegate_reason:
        return {
            "id": message.get("id"),
            "bucket_hint": "undetermined",
            "sensitive": False,
            "ea_scheduling_delegate": True,
            "reasons": [f"{ea_delegate_reason} — route straight to 3_delegate"],
        }

    farewell_reason = find_farewell_note(message, config)
    if farewell_reason:
        return {
            "id": message.get("id"),
            "bucket_hint": "undetermined",
            "sensitive": False,
            "farewell_note": True,
            "reasons": [f"{farewell_reason} — route to 2_review, call out distinctly rather than filing silently"],
        }

    routine_reason = find_routine_notification(message, config)
    if routine_reason:
        return {
            "id": message.get("id"),
            "bucket_hint": "routine_notification",
            "sensitive": False,
            "reasons": [routine_reason],
        }

    protected_reason = find_protected_match(message, config)
    if protected_reason:
        return {
            "id": message.get("id"),
            "bucket_hint": "undetermined",
            "sensitive": False,
            "protected_contact": True,
            "reasons": [f"{protected_reason} — decline suppressed, needs human judgment"],
        }

    internal_alert_reason = find_internal_or_operational_alert(message, config)
    if internal_alert_reason:
        return {
            "id": message.get("id"),
            "bucket_hint": "undetermined",
            "sensitive": False,
            "internal_or_operational_alert": True,
            "reasons": [f"{internal_alert_reason} — bulk screen and decline both skipped, route straight to 2_review"],
        }

    is_bulk, bulk_reason = is_bulk_or_newsletter(message)
    if is_bulk:
        reasons = [f"{bulk_reason} — routed to bulk_review for a quick manual screen before final filing"]
        decline_match = match_decline_template(message, templates)
        if decline_match:
            reasons.append(
                f"note: also matched decline template '{decline_match['topic']}' on {decline_match['matched_on']} "
                f"pattern /{decline_match['pattern']}/, but no decline draft was attempted since this looks like "
                "bulk/newsletter mail, not a direct solicitation"
            )
        return {
            "id": message.get("id"),
            "bucket_hint": "bulk_review",
            "sensitive": False,
            "reasons": reasons,
        }

    decline_match = match_decline_template(message, templates)
    if decline_match:
        address = ((message.get("sender") or {}).get("address") or message.get("senderAddress") or "").lower()
        ledger_entry = ledger.get("senders", {}).get(address)
        return {
            "id": message.get("id"),
            "bucket_hint": "decline",
            "sensitive": False,
            "reasons": [f"matched decline template '{decline_match['topic']}' on {decline_match['matched_on']} pattern /{decline_match['pattern']}/"],
            "template_topic": decline_match["topic"],
            "sender_address": address,
            "prior_decline_count": ledger_entry.get("count", 0) if ledger_entry else 0,
        }

    return {
        "id": message.get("id"),
        "bucket_hint": "undetermined",
        "sensitive": False,
        "reasons": ["no deterministic match — needs LLM judgment (2_review / 3_delegate / 7_toBeFiled) or leave in Inbox if still not confident"],
    }


def cmd_classify(args):
    config = load_config(args.config)
    config = merge_aboutme(config, load_aboutme(args.aboutme))
    templates = load_templates(args.templates)
    ledger = load_ledger(args.ledger)
    messages = load_json(args.messages)

    results = [classify_message(m, config, templates, ledger) for m in messages]
    counts = {}
    for r in results:
        counts[r["bucket_hint"]] = counts.get(r["bucket_hint"], 0) + 1

    print(json.dumps({"results": results, "counts": counts}, indent=2, sort_keys=True))


def cmd_match_declines(args):
    """For messages Trevor has already placed in 4_autorespond by hand (see
    SKILL.md's "Sweep 4_autorespond"), resolve which decline template applies
    -- his own placement there is the judgment call that this is a decline,
    so this deliberately skips classify_message's sensitive/priority/
    protected/bulk checks and goes straight to template matching, falling
    back to config's fallback_decline_topic when no template's keywords
    match at all."""
    config = load_config(args.config)
    templates = load_templates(args.templates)
    messages = load_json(args.messages)
    fallback_topic = config.get("fallback_decline_topic", "generic_vendor_demo_pitch")

    if not any(t["topic"] == fallback_topic for t in templates):
        print(json.dumps({
            "error": f"fallback_decline_topic '{fallback_topic}' has no matching template in {args.templates}"
        }), file=sys.stderr)
        sys.exit(1)

    results = []
    for m in messages:
        match = match_decline_template(m, templates)
        if match:
            results.append({
                "id": m.get("id"),
                "topic": match["topic"],
                "matched_on": match["matched_on"],
                "pattern": match["pattern"],
                "fallback_used": False,
            })
        else:
            results.append({
                "id": m.get("id"),
                "topic": fallback_topic,
                "matched_on": None,
                "pattern": None,
                "fallback_used": True,
            })

    print(json.dumps({"results": results}, indent=2, sort_keys=True))


def cmd_check_folders(args):
    config = load_config(args.config)
    found = set(json.loads(args.found_folders))
    expected_names = {key: config["folder_names"][key] for key in REQUIRED_FOLDER_KEYS}
    missing = {key: name for key, name in expected_names.items() if name not in found}
    print(json.dumps({
        "ok": not missing,
        "expected": expected_names,
        "found": sorted(found),
        "missing": missing,
    }, indent=2, sort_keys=True))


def cmd_record_decline(args):
    ledger = load_ledger(args.ledger)
    config = load_config(args.config)
    threshold = config.get("decline_threshold", 3)
    sender = args.sender.lower()

    entry = ledger.setdefault("senders", {}).setdefault(sender, {"count": 0})
    entry["count"] += 1
    entry["last_declined"] = args.date
    entry["template"] = args.template
    count = entry["count"]

    save_json(args.ledger, ledger)

    print(json.dumps({
        "sender": sender,
        "count": count,
        "threshold": threshold,
        "threshold_reached_this_run": count == threshold,
        "recommend_native_rule": count >= threshold,
    }, indent=2, sort_keys=True))


def cmd_record_filed(args):
    """Confirmed by Trevor 2026-08-12 (Theme A rec 4 of
    state/stage2_accuracy_report.md). Mirrors cmd_record_decline's shape
    exactly, but tracks a different, softer signal in a separate ledger
    section (filed_senders, not senders): a sender whose mail keeps reaching
    the 'routine, no ambiguity, file it' judgment call and landing in
    7_toBeFiled with no action taken. This is deliberately behavior-based
    rather than content-based -- it doesn't try to decide whether a message
    "is marketing"; a sender that keeps recurring here regardless of why is
    exactly the signal Trevor wants surfaced."""
    ledger = load_ledger(args.ledger)
    config = load_config(args.config)
    threshold = config.get("filed_without_action_threshold", 3)
    sender = args.sender.lower()

    entry = ledger.setdefault("filed_senders", {}).setdefault(sender, {"count": 0})
    entry["count"] += 1
    entry["last_filed"] = args.date
    count = entry["count"]

    save_json(args.ledger, ledger)

    print(json.dumps({
        "sender": sender,
        "count": count,
        "threshold": threshold,
        "threshold_reached_this_run": count == threshold,
        "recommend_unsubscribe": count >= threshold,
    }, indent=2, sort_keys=True))


def cmd_record_run(args):
    """Append-only per-run digest for acos-main's month-retro email-volume
    trend -- added 2026-08-13. Deliberately separate from
    state/last_run_summary.json, which stays a single overwritten snapshot
    per this skill's own "a simple, legible pair is enough" philosophy (see
    SKILL.md's Run summary section) -- this file is the only place run-over-
    run history survives at all. One compact line per run (JSON Lines, not
    pretty-printed) so appending never requires re-parsing the whole file."""
    try:
        counts = json.loads(args.counts)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"--counts is not valid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)

    entry = {
        "date": args.date,
        "counts": counts,
        "declines": args.declines,
        "filed_without_action": args.filed_without_action,
    }
    path = Path(args.history)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    print(json.dumps({"recorded": True, "date": args.date, "history_file": str(path)}, indent=2, sort_keys=True))


def cmd_bulk_review_status(args):
    """Confirmed by Trevor 2026-08-12 (Theme A rec 2 of
    state/stage2_accuracy_report.md): 6_bulkToReview stays a distinct
    folder, monitored over time rather than assumed to be earning its keep.
    This never moves or reads full message content -- just id +
    receivedDateTime for a lightweight headcount/age check -- and never
    acts on what it finds; it only reports. Diffs the current contents
    against the snapshot saved by the previous run, then overwrites that
    snapshot with today's contents for next time."""
    from datetime import date as _date

    messages = load_json(args.messages)
    today = _date.fromisoformat(args.today)

    first_run = not Path(args.snapshot).exists()
    prev = load_json(args.snapshot) if not first_run else {"as_of": None, "messages": []}

    prev_ids = {m["id"] for m in prev.get("messages", [])}
    current_ids = {m["id"] for m in messages}

    oldest_item_age_days = None
    if messages:
        oldest_received = min(m["receivedDateTime"] for m in messages)
        oldest_item_age_days = (today - _date.fromisoformat(oldest_received[:10])).days

    result = {
        "currently_in_bulk_review": len(messages),
        "oldest_item_age_days": oldest_item_age_days,
        "moved_out_since_last_run": len(prev_ids - current_ids),
        "added_since_last_run": len(current_ids - prev_ids),
        "first_run": first_run,
    }

    save_json(args.snapshot, {"as_of": args.today, "messages": messages})

    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_record_failure(args):
    print(json.dumps({
        "sender": args.sender.lower(),
        "template": args.template,
        "note": "draft creation failed — message should remain (or be placed) in 4_autorespond and be reported as a processing error in the run summary, not retried silently",
    }, indent=2, sort_keys=True))


def _extract_first_name(sender_name):
    if not sender_name:
        return "there"
    first = sender_name.strip().split()[0] if sender_name.strip() else ""
    cleaned = re.sub(r"[^A-Za-z\-']", "", first)
    if not cleaned or cleaned.lower() in GENERIC_SENDER_NAME_TOKENS or not cleaned[0].isupper():
        return "there"
    return cleaned


def cmd_render_template(args):
    parsed = parse_templates_file(Path(args.templates).read_text(encoding="utf-8"))
    template = next((t for t in parsed["templates"] if t["topic"] == args.topic), None)
    if template is None:
        print(json.dumps({"error": f"no template with topic '{args.topic}'"}), file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    config = merge_aboutme(config, load_aboutme(args.aboutme))
    signoff = config.get("signoff") or ""

    first_name = _extract_first_name(args.sender_name)
    html_body = template["html_body"].replace("{first_name}", first_name).replace("{signoff}", signoff)
    footer = parsed["disclosure_footer"]
    if footer:
        html_body = html_body.rstrip("\n") + "\n<br>\n" + footer
    subject = f"{template.get('subject_prefix', 'Re: ')}{args.original_subject}"

    print(json.dumps({
        "topic": template["topic"],
        "subject": subject,
        "html_body": html_body,
        "signoff_used": signoff,
        "first_name_used": first_name,
    }, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check-folders", help="Verify the six _claude/* folders exist")
    p_check.add_argument("--config", required=True)
    p_check.add_argument("--found-folders", required=True, help="JSON array of folder display names Claude found under _claude")
    p_check.set_defaults(func=cmd_check_folders)

    p_classify = sub.add_parser("classify", help="Score a batch of messages")
    p_classify.add_argument("--config", required=True)
    p_classify.add_argument("--aboutme", default=None, help="Path to acos-aboutme's state/profile.json, if installed and enrolled")
    p_classify.add_argument("--templates", required=True)
    p_classify.add_argument("--ledger", required=True)
    p_classify.add_argument("--messages", required=True, help="Path to a JSON array of message objects")
    p_classify.set_defaults(func=cmd_classify)

    p_match = sub.add_parser("match-declines", help="Resolve a decline template topic (with fallback) for messages sitting in 4_autorespond")
    p_match.add_argument("--config", required=True)
    p_match.add_argument("--templates", required=True)
    p_match.add_argument("--messages", required=True, help="Path to a JSON array of message objects sitting in 4_autorespond")
    p_match.set_defaults(func=cmd_match_declines)

    p_record = sub.add_parser("record-decline", help="Update the ledger after a decline draft was created successfully")
    p_record.add_argument("--config", required=True)
    p_record.add_argument("--ledger", required=True)
    p_record.add_argument("--sender", required=True)
    p_record.add_argument("--template", required=True)
    p_record.add_argument("--date", required=True, help="ISO date (YYYY-MM-DD) of this decline, supplied by the caller")
    p_record.set_defaults(func=cmd_record_decline)

    p_fail = sub.add_parser("record-failure", help="Emit a structured note for a failed draft attempt (does not touch the ledger)")
    p_fail.add_argument("--sender", required=True)
    p_fail.add_argument("--template", required=True)
    p_fail.set_defaults(func=cmd_record_failure)

    p_filed = sub.add_parser("record-filed", help="Update the filed-without-action ledger after routine mail is judged and filed to 7_toBeFiled")
    p_filed.add_argument("--config", required=True)
    p_filed.add_argument("--ledger", required=True)
    p_filed.add_argument("--sender", required=True)
    p_filed.add_argument("--date", required=True, help="ISO date (YYYY-MM-DD), supplied by the caller")
    p_filed.set_defaults(func=cmd_record_filed)

    p_run = sub.add_parser("record-run", help="Append a compact per-run digest to state/run_history.jsonl (for acos-main's month-retro)")
    p_run.add_argument("--history", required=True, help="Path to state/run_history.jsonl (created if missing)")
    p_run.add_argument("--date", required=True, help="ISO date (YYYY-MM-DD) of this run")
    p_run.add_argument("--counts", required=True, help='JSON object string, same shape as last_run_summary.json\'s "counts" field: {"1_priority":N,"2_review":N,"3_delegate":N,"5_draftsToReview":N,"6_bulkToReview":N,"7_toBeFiled":N,"unclassified_in_inbox":N}')
    p_run.add_argument("--declines", type=int, default=0, help="Number of decline drafts created this run (sweep + Gather combined)")
    p_run.add_argument("--filed-without-action", type=int, default=0, dest="filed_without_action", help="Number of record-filed calls made this run")
    p_run.set_defaults(func=cmd_record_run)

    p_bulk = sub.add_parser("bulk-review-status", help="Diff current 6_bulkToReview contents against the last run's snapshot and report monitoring stats")
    p_bulk.add_argument("--snapshot", required=True, help="Path to the persisted snapshot file (read, then overwritten)")
    p_bulk.add_argument("--messages", required=True, help="Path to a JSON array of {id, receivedDateTime} for everything currently in 6_bulkToReview")
    p_bulk.add_argument("--today", required=True, help="ISO date (YYYY-MM-DD) 'today', supplied by the caller")
    p_bulk.set_defaults(func=cmd_bulk_review_status)

    p_render = sub.add_parser("render-template", help="Fill a matched template's placeholder for one message")
    p_render.add_argument("--config", required=True)
    p_render.add_argument("--aboutme", default=None, help="Path to acos-aboutme's state/profile.json, if installed and enrolled")
    p_render.add_argument("--templates", required=True)
    p_render.add_argument("--topic", required=True)
    p_render.add_argument("--sender-name", default="", help="Display name of the original sender, if known")
    p_render.add_argument("--original-subject", required=True)
    p_render.set_defaults(func=cmd_render_template)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
