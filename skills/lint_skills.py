#!/usr/bin/env python3
"""Lint and validate Signatry Claude Skill packages under skills/.

For every immediate subdirectory of skills/ (each a skill package), checks:

  1. SKILL.md exists and its frontmatter validates against
     ../schemas/skill-schema.json (required: name, description, version,
     release_date). Edit that file, not this script, to change required
     fields.
  2. Description quality heuristics per Anthropic's guidance that a
     description must clearly signal WHEN Claude should use the skill.
     Vague descriptions are flagged as warnings for human review, not
     hard failures.
  3. Markdown link integrity: relative [text](path) links must resolve,
     and any references/<file> path named in SKILL.md must exist. A
     mentioned assets/ or scripts/ path that doesn't exist in the skill is
     an informational warning (it may belong to a different skill/tool) —
     to mark a specific one as expected/acceptable, add an entry
     {"path": ..., "reason": ...} to lint_allowlist.json under that skill's
     name. A non-empty reason is required per entry (explain *why* the
     path is expected, not just that it is) — entries missing one, and
     entries that no longer appear anywhere in the skill's text (stale),
     are both flagged.
  4. A Restricted-data scan (per IT15) of every text file in the skill:
     SSNs, payment card numbers, bank/account/routing numbers, and
     credentials/keys/private-key blocks. Any hit hard-fails the build.
     Matched values are never printed in full, only masked.

Usage:
  python3 skills/lint_skills.py [--path skills] [--strict] [--json]

Exit codes:
  0 - no errors or restricted-data findings (warnings may still print)
  1 - one or more errors, or any restricted-data finding
      (also returned for warnings when --strict is passed)
"""
import argparse
import json
import re
import sys
from pathlib import Path

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"  # restricted-data findings (IT15)

TEXT_EXTS = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".js", ".ts", ".sh", ".svg"}

SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)[^)]*\)")
REFERENCES_MENTION_RE = re.compile(r"\breferences/[A-Za-z0-9_\-./]+\.\w+")
ASSETS_SCRIPTS_MENTION_RE = re.compile(r"\b(?:assets|scripts)/[A-Za-z0-9_\-./]+\.\w+")

TRIGGER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\buse (this|whenever|when|if)\b",
        r"\btrigger\b",
        r"\bwhenever\b",
        r"\bshould be used\b",
        r"\bcall(ed)? (whenever|when)\b",
    ]
]

# --- Restricted-data detection (IT15) --------------------------------------
# Findings here hard-fail the build. Matched values are masked before
# printing so the lint output itself never becomes a leak.

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
CREDENTIAL_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)\b"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9_\-/+.=]{8,})"
)
BANK_ACCOUNT_RE = re.compile(
    r"(?i)\b(account|routing|iban|acct)\s*(number|no\.?|#)?\s*[:#]?\s*(\d{6,})"
)
CARD_SEQUENCE_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")


def luhn_ok(digits):
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def mask(value):
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def scan_restricted_data(path, text):
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if SSN_RE.search(line):
            findings.append((path, lineno, "Possible SSN"))
        if AWS_KEY_RE.search(line):
            findings.append((path, lineno, "Possible AWS access key"))
        if PRIVATE_KEY_RE.search(line):
            findings.append((path, lineno, "Private key block"))
        m = CREDENTIAL_RE.search(line)
        if m:
            findings.append((path, lineno, f"Possible credential ({m.group(1)}={mask(m.group(2))})"))
        m = BANK_ACCOUNT_RE.search(line)
        if m:
            findings.append((path, lineno, f"Possible bank/account number ({mask(m.group(3))})"))
        for m in CARD_SEQUENCE_RE.finditer(line):
            digits = re.sub(r"[ \-]", "", m.group())
            if 13 <= len(digits) <= 19 and luhn_ok(digits):
                findings.append((path, lineno, f"Possible payment card number ({mask(digits)})"))
    return findings


# --- Minimal frontmatter parsing (no PyYAML dependency required) -----------


def parse_frontmatter(text):
    """Parse simple flat `key: value` YAML frontmatter. Uses PyYAML if
    available for correctness; otherwise falls back to a line parser
    sufficient for the scalar-only frontmatter used in this repo."""
    if not text.startswith("---"):
        return None, "SKILL.md does not start with a '---' frontmatter block"
    end = text.find("\n---", 3)
    if end == -1:
        return None, "SKILL.md frontmatter block is not closed with '---'"
    block = text[3:end].strip("\n")

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(block)
        if not isinstance(data, dict):
            return None, "Frontmatter did not parse to a mapping"
        return data, None
    except ImportError:
        pass

    data = {}
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            return None, f"Could not parse frontmatter line: {raw_line!r}"
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        data[key] = value
    return data, None


# --- Minimal JSON Schema validation (subset: type/required/properties/ -----
# minLength/maxLength/pattern) so this script has no third-party dependency.


def validate_schema(instance, schema, path=""):
    errors = []
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(instance, dict):
            return [f"{path or 'root'}: expected object"]
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required field '{req}'")
        for key, value in instance.items():
            prop_schema = schema.get("properties", {}).get(key)
            if prop_schema is not None:
                errors.extend(validate_schema(value, prop_schema, f"{path}.{key}" if path else key))
        return errors

    types = schema_type if isinstance(schema_type, list) else [schema_type] if schema_type else []
    py_types = {
        "string": str,
        "boolean": bool,
        "array": list,
        "object": dict,
        "integer": int,
        "number": (int, float),
    }
    if types and not any(isinstance(instance, py_types[t]) for t in types if t in py_types):
        errors.append(f"{path}: expected type {types}, got {type(instance).__name__}")
        return errors

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: length {len(instance)} is below minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: length {len(instance)} exceeds maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: value {instance!r} does not match pattern {schema['pattern']!r}")
    return errors


# --- Per-skill checks --------------------------------------------------


def check_description_quality(description):
    warnings = []
    if not any(p.search(description) for p in TRIGGER_PATTERNS):
        warnings.append(
            "Description does not contain clear 'use when/whenever' trigger language — "
            "flag for human review to confirm Claude will invoke this skill at the right time."
        )
    return warnings


def check_markdown_links(md_path, text, skill_dir, allowed_refs=frozenset()):
    issues = []
    for match in MD_LINK_RE.finditer(text):
        target = match.group(1)
        if SCHEME_RE.match(target) or target.startswith("#"):
            continue
        target_clean = target.split("#", 1)[0]
        resolved = (md_path.parent / target_clean).resolve()
        if not resolved.exists():
            issues.append((SEVERITY_ERROR, f"{md_path.relative_to(skill_dir.parent)}: broken link -> {target}"))
    for match in REFERENCES_MENTION_RE.finditer(text):
        ref = match.group()
        resolved = (skill_dir / ref).resolve()
        if not resolved.exists():
            issues.append(
                (SEVERITY_ERROR, f"{md_path.relative_to(skill_dir.parent)}: references missing file -> {ref}")
            )
    for match in ASSETS_SCRIPTS_MENTION_RE.finditer(text):
        ref = match.group()
        if ref in allowed_refs:
            continue
        resolved = (skill_dir / ref).resolve()
        if not resolved.exists():
            issues.append(
                (
                    SEVERITY_WARNING,
                    f"{md_path.relative_to(skill_dir.parent)}: mentions '{ref}' not found in this skill "
                    "(informational — path may belong to a different skill/tool; "
                    "add it to lint_allowlist.json to mark it as expected)",
                )
            )
    return issues


def check_no_nested_metadata(frontmatter, skill_md):
    """Frontmatter version/release_date/custom fields must be flat top-level
    keys, never nested under a 'metadata:' block. A nested block relies on
    this module's hand-rolled fallback parser accidentally flattening it
    (see parse_frontmatter) -- it would silently break if PyYAML were ever
    installed. "metadata" ends up a dict key either way (nested dict under
    real YAML, or an empty-string value under the fallback parser), so a
    simple key-presence check catches it regardless of which parser ran."""
    if isinstance(frontmatter, dict) and "metadata" in frontmatter:
        return [
            (
                SEVERITY_ERROR,
                f"{skill_md}: frontmatter has a nested 'metadata:' block — version/release_date "
                "and any custom fields must be flat top-level keys (see signatry-brand-core).",
            )
        ]
    return []


INLINE_CHANGELOG_HEADING_RE = re.compile(
    r"(?im)^#{1,6}\s+(?:change\s?log|revision\s+history|version\s+history|release\s+notes)\b"
)


def check_no_inline_changelog(md_path, text, skill_dir):
    issues = []
    for match in INLINE_CHANGELOG_HEADING_RE.finditer(text):
        lineno = text.count("\n", 0, match.start()) + 1
        issues.append(
            (
                SEVERITY_ERROR,
                f"{md_path.relative_to(skill_dir.parent)}:{lineno}: inline changelog/revision-history "
                "heading in SKILL.md body — move this content to _exclude/CHANGELOG.md.",
            )
        )
    return issues


def check_changelog_exists(skill_dir):
    changelog = skill_dir / "_exclude" / "CHANGELOG.md"
    if not changelog.exists():
        return [(SEVERITY_ERROR, f"{skill_dir}: missing required _exclude/CHANGELOG.md")]
    if changelog.stat().st_size == 0:
        return [(SEVERITY_ERROR, f"{changelog}: exists but is empty")]
    return []


def parse_allowlist_entries(raw_entries, skill_name):
    """Returns (allowed_refs set, issues list) for one skill's allowlist entries.

    Each entry must be {"path": "...", "reason": "..."} with a non-empty
    reason — a bare path string, or one with a blank reason, is flagged
    rather than silently honored, so every suppression stays documented."""
    allowed_refs = set()
    issues = []
    for entry in raw_entries:
        if isinstance(entry, str):
            allowed_refs.add(entry)
            issues.append(
                (
                    SEVERITY_WARNING,
                    f"lint_allowlist.json: entry '{entry}' for '{skill_name}' is a bare string — "
                    "convert to {\"path\": ..., \"reason\": ...} with a non-empty reason",
                )
            )
            continue
        path = entry.get("path") if isinstance(entry, dict) else None
        if not path:
            issues.append(
                (SEVERITY_WARNING, f"lint_allowlist.json: an entry for '{skill_name}' is missing a 'path'")
            )
            continue
        allowed_refs.add(path)
        reason = entry.get("reason")
        if not reason or not str(reason).strip():
            issues.append(
                (
                    SEVERITY_WARNING,
                    f"lint_allowlist.json: entry '{path}' for '{skill_name}' has no reason — "
                    "a reason explaining why this path is expected is required",
                )
            )
    return allowed_refs, issues


def lint_skill(skill_dir, schema, allowlist=None):
    issues = []  # list of (severity, message)
    allowed_refs, allowlist_issues = parse_allowlist_entries(
        (allowlist or {}).get(skill_dir.name, []), skill_dir.name
    )
    issues.extend(allowlist_issues)
    issues.extend(check_changelog_exists(skill_dir))

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        alt = skill_dir / "skill.md"
        if alt.exists():
            issues.append((SEVERITY_ERROR, f"{alt} should be named 'SKILL.md' (uppercase) per convention"))
            skill_md = alt
        else:
            issues.append((SEVERITY_ERROR, f"{skill_dir}: no SKILL.md found"))
            return issues

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter, parse_error = parse_frontmatter(text)
    if parse_error:
        issues.append((SEVERITY_ERROR, f"{skill_md}: {parse_error}"))
        frontmatter = None

    if frontmatter is not None:
        for err in validate_schema(frontmatter, schema):
            issues.append((SEVERITY_ERROR, f"{skill_md}: {err}"))
        issues.extend(check_no_nested_metadata(frontmatter, skill_md))

        name = frontmatter.get("name")
        if isinstance(name, str) and name != skill_dir.name:
            issues.append(
                (SEVERITY_WARNING, f"{skill_md}: frontmatter name '{name}' does not match directory '{skill_dir.name}'")
            )

        description = frontmatter.get("description")
        if isinstance(description, str):
            for warning in check_description_quality(description):
                issues.append((SEVERITY_WARNING, f"{skill_md}: {warning}"))

    all_texts = [text]
    issues.extend(check_markdown_links(skill_md, text, skill_dir, allowed_refs))
    issues.extend(check_no_inline_changelog(skill_md, text, skill_dir))
    for ref_md in skill_dir.glob("references/*.md"):
        ref_text = ref_md.read_text(encoding="utf-8", errors="replace")
        issues.extend(check_markdown_links(ref_md, ref_text, skill_dir, allowed_refs))
        all_texts.append(ref_text)

    if allowed_refs:
        mentioned = {
            m.group() for t in all_texts for m in ASSETS_SCRIPTS_MENTION_RE.finditer(t)
        }
        for stale_ref in sorted(allowed_refs - mentioned):
            issues.append(
                (
                    SEVERITY_WARNING,
                    f"lint_allowlist.json: entry '{stale_ref}' for '{skill_dir.name}' is not mentioned "
                    "anywhere in this skill anymore — remove it",
                )
            )

    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for path, lineno, rule in scan_restricted_data(file_path.relative_to(skill_dir.parent), content):
            issues.append((SEVERITY_CRITICAL, f"{path}:{lineno}: {rule}"))

    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=str(Path(__file__).parent), help="Path to the skills/ directory")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    schema_path = Path(__file__).parent.parent / "schemas" / "skill-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    allowlist_path = Path(__file__).parent / "lint_allowlist.json"
    allowlist = {}
    if allowlist_path.exists():
        raw_allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
        allowlist = {k: v for k, v in raw_allowlist.items() if not k.startswith("_")}

    skill_dirs = sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))

    report = {}
    has_error = False
    has_warning = False
    for skill_dir in skill_dirs:
        issues = lint_skill(skill_dir, schema, allowlist)
        report[skill_dir.name] = issues
        for severity, _ in issues:
            if severity in (SEVERITY_ERROR, SEVERITY_CRITICAL):
                has_error = True
            elif severity == SEVERITY_WARNING:
                has_warning = True

    if args.json:
        print(json.dumps({name: [{"severity": s, "message": m} for s, m in issues] for name, issues in report.items()}, indent=2))
    else:
        any_critical = False
        for name, issues in report.items():
            if not issues:
                print(f"[PASS] {name}")
                continue
            print(f"[{'FAIL' if any(s != SEVERITY_WARNING for s, _ in issues) else 'WARN'}] {name}")
            for severity, message in issues:
                print(f"    {severity:9s} {message}")
                if severity == SEVERITY_CRITICAL:
                    any_critical = True
        if any_critical:
            print(
                "\nRestricted data was detected (IT15). Do not distribute this skill. "
                "Remove the data, then report it to the Technology Team per IT14 Policy 10: "
                "https://signatry1.atlassian.net/servicedesk/customer/portal/1"
            )

    if has_error:
        return 1
    if has_warning and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
