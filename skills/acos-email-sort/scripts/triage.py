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
  classify        Score a batch of messages: priority match, decline-template
                   match, HR/personnel-adjacent sensitivity flag. Read-only
                   against the ledger (no mutation).
  record-decline  Called once per message AFTER its decline draft was created
                   successfully. Updates the ledger and reports whether the
                   repeat-decline threshold was just reached.
  render-template Fill a matched template's {first_name} placeholder for a
                   given sender display name and append the standing
                   AI-assistance disclosure footer, returning the subject/
                   html body to hand to outlook_create_reply_draft.

No subcommand here ever calls an O365 tool, sends mail, or creates a filter —
this script only ever reads its own config/ledger/template files and stdin/
argument data, and prints JSON to stdout.
"""
import argparse
import json
import re
import sys
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

GENERIC_SENDER_NAME_TOKENS = {
    "the", "team", "support", "sales", "marketing", "newsletter", "newsletters",
    "notifications", "noreply", "no-reply", "info", "hello", "admin", "updates",
    "help", "billing", "accounts", "office", "service", "services", "care",
}

REQUIRED_FOLDER_KEYS = [
    "priority", "review", "delegate", "autorespond", "drafts_review", "to_be_filed",
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
    config.setdefault("decline_threshold", 3)
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


def score_priority(message, config):
    reasons = []
    address = (message.get("sender") or {}).get("address") or message.get("senderAddress") or ""
    domain = _sender_domain(address)
    vip_addresses = {v.get("email", "").lower() for v in config.get("vip_senders", []) if v.get("email")}
    vip_domains = {v.get("domain", "").lower() for v in config.get("vip_senders", []) if v.get("domain")}

    if address.lower() in vip_addresses:
        reasons.append(f"sender {address} is on the executive/VIP list")
    elif domain and domain in vip_domains:
        reasons.append(f"sender domain {domain} is on the executive/VIP list")

    if (message.get("importance") or "").lower() == "high":
        reasons.append("message flagged high importance")

    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"
    for pattern in _compile_all(config.get("urgent_keyword_patterns", DEFAULT_URGENT_KEYWORD_PATTERNS)):
        if pattern.search(haystack):
            reasons.append(f"deadline/approval keyword match: /{pattern.pattern}/")
            break

    return reasons


def score_sensitive(message, config):
    haystack = f"{message.get('subject', '')}\n{message.get('bodyPreview', '')}"
    for pattern in _compile_all(config.get("sensitive_keyword_patterns", DEFAULT_SENSITIVE_KEYWORD_PATTERNS)):
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

    protected_reason = find_protected_match(message, config)
    if protected_reason:
        return {
            "id": message.get("id"),
            "bucket_hint": "undetermined",
            "sensitive": False,
            "protected_contact": True,
            "reasons": [f"{protected_reason} — decline suppressed, needs human judgment"],
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
        "reasons": ["no deterministic match — needs LLM judgment (2_review / 3_delegate / 6_toBeFiled) or leave in Inbox if still not confident"],
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
