#!/usr/bin/env python3
"""Advise on context/token budget for a Signatry Claude Skill package.

For a single skill (or, with --all, every skill under --path), estimates
how much content that skill loads into Claude's context and flags ways to
reduce it:

  1. Skill Composition: frontmatter description (always loaded, FYI only --
     lint_skills.py already governs its length/quality), SKILL.md body
     (loaded whenever the skill fires), and deferred content under
     reference/, references/, scripts/, assets/ (loaded only when SKILL.md
     points Claude to read it) -- each with a line count and a token count.
  2. Comparison: this skill's Typical Call and Worst Case footprint against
     the Signatry-wide median (of Typical Call, across siblings) and an
     optional user-supplied benchmark. "Worst Case" assumes every deferred
     file loads at once. "Typical Call" depends on this skill's deferred
     usage classification (see skills/deferred_usage.json):
       - deferred-alternatives: the skill's deferred files are a menu of
         mutually-exclusive options (audience personas, icons, topic
         references) -- a normal call loads roughly one, so Typical Call
         uses only the single largest deferred file, not the sum of all.
       - deferred-full-use (the default when unclassified): deferred files
         are cumulative/sequential steps that normally all run together
         (e.g. a build-script checklist) -- Typical Call equals Worst Case.
  3. Version Delta: how this skill's total lines/tokens changed versus the
     last version recorded in skill_budget_stats.json, if any.
  4. Oversized inline content: large fenced code blocks or markdown
     tables sitting directly in the SKILL.md body, which usually belong
     in scripts/ or reference(s)/ instead.
  5. Orphaned deferred files: reference(s)/scripts/assets files never
     mentioned anywhere in SKILL.md -- dead weight to delete or link.
  6. Ungated mentions: a reference/scripts/assets path mentioned with no
     nearby "load when / only if / whenever" language, so Claude may
     treat it as unconditionally relevant.

This is advisory only -- it never fails a build. Token counts are a rough
chars-per-token heuristic (no tokenizer dependency), useful for relative
comparison, not exact accounting.

In addition to printing to stdout, every analyzed skill gets a report
written to <skill>/_exclude/skill_budget_audit.md (or .json with --json).
package_skill.py excludes _exclude/ from the packaged zip. Override the
filename with --output.

Every analyzed skill's current version/lines/tokens also gets recorded to
<--path>/skill_budget_stats.json (a repo-level file, not inside any one
skill), keyed by skill name as a version history. Only skills actually
analyzed this run get a new entry recorded -- unanalyzed siblings' stored
history is left untouched, so a version bump's delta is always visible
the next time that specific skill is audited, not silently consumed by an
unrelated run.

Usage:
  python3 skills/skill_budget_audit.py signatry-style
  python3 skills/skill_budget_audit.py --all
  python3 skills/skill_budget_audit.py --all --json
  python3 skills/skill_budget_audit.py signatry-style --output my_report.md

Exit codes:
  0 - analysis printed (recommendations are advisory, not failures)
  1 - named skill not found, or has no SKILL.md
"""
import argparse
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

from lint_skills import parse_frontmatter, TEXT_EXTS

CHARS_PER_TOKEN = 4
OUTLIER_MULTIPLIER = 1.75
LARGE_CODEBLOCK_LINES = 25
LARGE_TABLE_LINES = 15
ORPHAN_GROUP_THRESHOLD = 5
DEFERRED_DIR_NAMES = ("reference", "references", "scripts", "assets")
EXCLUDE_DIR_NAME = "_exclude"
STATS_FILENAME = "skill_budget_stats.json"

DEFERRED_ALTERNATIVES = "deferred-alternatives"
DEFERRED_FULL_USE = "deferred-full-use"
# Default when a skill has no entry in deferred_usage.json: assume the more
# conservative case (typical call == worst case) until a human explicitly
# documents that this skill's deferred files are mutually-exclusive
# alternatives -- mirrors lint_allowlist.json's "suppression requires a
# reason" convention, just inverted (the lenient reading requires the reason).
DEFAULT_DEFERRED_CLASSIFICATION = DEFERRED_FULL_USE
DEFERRED_USAGE_CONFIG_FILENAME = "deferred_usage.json"

# Fixed reference points for the Comparison table's Benchmark column.
BENCHMARK_LINES = 501
BENCHMARK_TOKENS = 8100

FENCE_RE = re.compile(r"^\s*```")
TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
GATING_KEYWORDS_RE = re.compile(
    r"\b(load(?:ed)?\s+when|load\s+only|only\s+if|only\s+when|"
    r"if\s+(?:you|the user|it'?s)\s+need|whenever|when\s+relevant|"
    r"when\s+(?:actually\s+)?needed|read\s+(?:this\s+)?before|"
    r"do(?:es)?\s+not\s+need)\b",
    re.IGNORECASE,
)


def estimate_tokens(text):
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def load_skill_md(skill_dir):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        alt = skill_dir / "skill.md"
        if not alt.exists():
            return None, f"no SKILL.md found in {skill_dir}"
        skill_md = alt
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    return text, None


def split_frontmatter_body(text):
    """Returns (frontmatter_or_None, body_text, parse_error)."""
    frontmatter, error = parse_frontmatter(text)
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            rest = text[end + 4 :]
            newline = rest.find("\n")
            body = rest[newline + 1 :] if newline != -1 else ""
    return frontmatter, body, error


def iter_deferred_files(skill_dir):
    """Returns [(relpath, is_text)] under reference(s)/scripts/assets."""
    files = []
    for dir_name in DEFERRED_DIR_NAMES:
        base = skill_dir / dir_name
        if not base.is_dir():
            continue
        for file_path in sorted(base.rglob("*")):
            if not file_path.is_file():
                continue
            relpath = file_path.relative_to(skill_dir)
            files.append((relpath, file_path.suffix.lower() in TEXT_EXTS))
    return files


def find_codeblock_ranges(lines):
    """Returns ([(start_idx, end_idx), ...], unbalanced_bool) for every
    fenced code block, regardless of size (used to exclude code-block
    lines from table detection, and as input to oversized-block checks).
    An unclosed fence at EOF is treated as closed there and flagged."""
    ranges = []
    in_block = False
    start_idx = None
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            if not in_block:
                in_block = True
                start_idx = i
            else:
                in_block = False
                ranges.append((start_idx, i))
    unbalanced = in_block
    if in_block:
        ranges.append((start_idx, len(lines) - 1))
    return ranges, unbalanced


def find_oversized_codeblocks(lines, codeblock_ranges):
    blocks = []
    for start_idx, end_idx in codeblock_ranges:
        num_lines = end_idx - start_idx + 1
        if num_lines >= LARGE_CODEBLOCK_LINES:
            block_text = "\n".join(lines[start_idx : end_idx + 1])
            blocks.append((start_idx + 1, num_lines, estimate_tokens(block_text)))
    return blocks


def find_oversized_tables(lines, codeblock_ranges):
    """Large markdown tables in the body, skipping lines inside fenced code
    blocks (a code example containing '|' shell pipes shouldn't count)."""
    in_code = [False] * len(lines)
    for start_idx, end_idx in codeblock_ranges:
        for i in range(start_idx, min(end_idx + 1, len(lines))):
            in_code[i] = True

    tables = []
    i = 0
    n = len(lines)
    while i < n:
        if not in_code[i] and TABLE_ROW_RE.match(lines[i]):
            start = i
            has_sep = False
            j = i
            while j < n and not in_code[j] and TABLE_ROW_RE.match(lines[j]):
                if TABLE_SEP_RE.match(lines[j]):
                    has_sep = True
                j += 1
            run_len = j - start
            if run_len >= LARGE_TABLE_LINES and has_sep:
                block_text = "\n".join(lines[start:j])
                tables.append((start + 1, run_len, estimate_tokens(block_text)))
            i = j
        else:
            i += 1
    return tables


def find_mentions(full_text, relpath):
    """Line numbers (1-indexed) where relpath or its basename appears
    anywhere in SKILL.md (not just the body -- a note near the frontmatter
    still counts)."""
    posix_path = relpath.as_posix()
    basename = relpath.name
    path_re = re.compile(re.escape(posix_path))
    base_re = re.compile(re.escape(basename))
    mentions = []
    for lineno, line in enumerate(full_text.splitlines(), start=1):
        if path_re.search(line) or base_re.search(line):
            mentions.append(lineno)
    return mentions


def has_gating_language(full_text):
    """Whether ANY "load when / only if / whenever" phrasing appears
    anywhere in SKILL.md, not just near a specific file mention.

    A skill often states a gating rule once for a whole family of deferred
    files -- e.g. a routing table listing several references/<x>.md paths,
    with "load only the one selected" spelled out once in a separate
    procedural section rather than repeated next to every table row (the
    mention and the rule can be dozens of lines apart, and the rule may use
    a templated path like `references/<audience>.md` that never literally
    repeats the real filename). A per-mention proximity window misses that
    entirely, so this checks the whole document instead. The tradeoff: a
    skill that gates most files carefully but truly forgets one won't be
    caught -- acceptable for an advisory tool where false alarms on
    already-well-gated skills are the more common, more annoying failure."""
    return bool(GATING_KEYWORDS_RE.search(full_text))


def analyze_deferred_files(skill_dir, full_text, body_text):
    """Returns (total_tokens, total_lines, largest_file, per_file, orphaned,
    ungated_mentions). largest_file is {"path", "tokens", "lines"} for the
    single biggest deferred text file, or None if there are none -- this
    feeds the "Typical Call" estimate for deferred-alternatives skills.

    Binary files (fonts, images, pptx templates, etc.) are skipped entirely:
    they're never read into Claude's context as text regardless of whether
    SKILL.md mentions them by name -- build scripts typically discover them
    by directory glob, not by prose reference -- so "orphaned"/"ungated"
    framing doesn't apply and would just be noise.

    Mentions are searched across full_text (frontmatter included -- rare,
    but a file path could appear there), while gating language is searched
    only in body_text: every skill's frontmatter description is required by
    lint_skills.py to contain "use this whenever ..." trigger language, which
    answers "when should Claude invoke this skill at all" -- an unrelated
    question from "when should this specific deferred file be read" -- and
    would otherwise make every skill in the corpus look gated everywhere."""
    total_tokens = 0
    total_lines = 0
    largest_file = None
    per_file = []
    orphaned = []
    ungated = []
    doc_has_gating_language = has_gating_language(body_text)
    for relpath, is_text in iter_deferred_files(skill_dir):
        if not is_text:
            continue
        content = (skill_dir / relpath).read_text(encoding="utf-8", errors="replace")
        tokens = estimate_tokens(content)
        file_lines = len(content.splitlines())
        total_tokens += tokens
        total_lines += file_lines
        if largest_file is None or tokens > largest_file["tokens"]:
            largest_file = {"path": relpath.as_posix(), "tokens": tokens, "lines": file_lines}
        mentions = find_mentions(full_text, relpath)
        per_file.append({"path": relpath.as_posix(), "tokens": tokens, "lines": file_lines, "mentions": mentions})
        if not mentions:
            orphaned.append({"path": relpath.as_posix(), "tokens": tokens})
        elif tokens > 0 and not doc_has_gating_language:
            ungated.append({"path": relpath.as_posix(), "tokens": tokens, "line": mentions[0]})
    return total_tokens, total_lines, largest_file, per_file, orphaned, ungated


def build_corpus_index(root):
    """One shared read/analysis pass over every skill dir under root. Every
    skill's full composition (description/body/deferred lines+tokens) is
    computed here, not just the target skill's -- the Signatry-wide median
    used for the Comparison table needs every sibling regardless of mode."""
    index = {}
    errors = {}
    skill_dirs = sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))
    for skill_dir in skill_dirs:
        text, error = load_skill_md(skill_dir)
        if error:
            errors[skill_dir.name] = error
            continue
        frontmatter, body, parse_error = split_frontmatter_body(text)

        description = frontmatter.get("description", "") if isinstance(frontmatter, dict) else ""
        description = description if isinstance(description, str) else ""
        description_tokens = estimate_tokens(description)
        description_lines = max(1, len(description.splitlines())) if description else 0

        body_tokens = estimate_tokens(body)
        body_lines = len(body.splitlines())

        deferred_tokens, deferred_lines, largest_file, per_file, orphaned, ungated = analyze_deferred_files(
            skill_dir, text, body
        )

        index[skill_dir.name] = {
            "skill_dir": skill_dir,
            "text": text,
            "frontmatter": frontmatter,
            "body": body,
            "parse_error": parse_error,
            "description_tokens": description_tokens,
            "description_lines": description_lines,
            "body_tokens": body_tokens,
            "body_lines": body_lines,
            "deferred_tokens": deferred_tokens,
            "deferred_lines": deferred_lines,
            "deferred_file_count": len(per_file),
            "largest_deferred_file": largest_file,
            "orphaned_files": orphaned,
            "ungated_mentions": ungated,
            "total_tokens": description_tokens + body_tokens + deferred_tokens,
            "total_lines": description_lines + body_lines + deferred_lines,
        }
    return index, errors


# --- Deferred-usage classification (skills/deferred_usage.json) ------------


def load_deferred_usage_config():
    config_path = Path(__file__).parent / DEFERRED_USAGE_CONFIG_FILENAME
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def classify_deferred_usage(name, config):
    """Returns (classification, reason_or_None) for a skill. Falls back to
    DEFAULT_DEFERRED_CLASSIFICATION with no reason when unlisted or the
    listed classification isn't one of the two recognized values."""
    entry = config.get(name)
    if isinstance(entry, dict) and entry.get("classification") in (DEFERRED_ALTERNATIVES, DEFERRED_FULL_USE):
        return entry["classification"], entry.get("reason")
    return DEFAULT_DEFERRED_CLASSIFICATION, None


def compute_typical_deferred(entry, classification):
    """Returns (typical_deferred_tokens, typical_deferred_lines): the sum of
    all deferred content for deferred-full-use (or when there's no deferred
    content to distinguish), or just the single largest deferred file for
    deferred-alternatives."""
    if classification == DEFERRED_FULL_USE or entry["largest_deferred_file"] is None:
        return entry["deferred_tokens"], entry["deferred_lines"]
    largest = entry["largest_deferred_file"]
    return largest["tokens"], largest["lines"]


def typical_total_for(entry, classification):
    """Returns (typical_tokens, typical_lines) -- description+body+typical-deferred."""
    d_tokens, d_lines = compute_typical_deferred(entry, classification)
    return (
        entry["description_tokens"] + entry["body_tokens"] + d_tokens,
        entry["description_lines"] + entry["body_lines"] + d_lines,
    )


def analyze_skill(name, entry, median_typical_lines, median_typical_tokens, sibling_count, deferred_usage_config):
    skill_dir = entry["skill_dir"]
    body = entry["body"]
    lines = body.splitlines()
    codeblock_ranges, unbalanced = find_codeblock_ranges(lines)
    codeblocks = find_oversized_codeblocks(lines, codeblock_ranges)
    tables = find_oversized_tables(lines, codeblock_ranges)

    classification, classification_reason = classify_deferred_usage(name, deferred_usage_config)
    typical_tokens, typical_lines = typical_total_for(entry, classification)

    tokens_ratio = (typical_tokens / median_typical_tokens) if median_typical_tokens else None
    lines_ratio = (typical_lines / median_typical_lines) if median_typical_lines else None
    is_outlier = bool(median_typical_tokens and typical_tokens > median_typical_tokens * OUTLIER_MULTIPLIER)

    frontmatter = entry["frontmatter"] or {}
    version = frontmatter.get("version") if isinstance(frontmatter, dict) else None
    release_date = frontmatter.get("release_date") if isinstance(frontmatter, dict) else None

    return {
        "skill": name,
        "version": version,
        "release_date": release_date,
        "composition": {
            "description": {"lines": entry["description_lines"], "tokens": entry["description_tokens"]},
            "body": {"lines": entry["body_lines"], "tokens": entry["body_tokens"]},
            "deferred": {
                "lines": entry["deferred_lines"],
                "tokens": entry["deferred_tokens"],
                "file_count": entry["deferred_file_count"],
            },
            "total": {"lines": entry["total_lines"], "tokens": entry["total_tokens"]},
        },
        "comparison": {
            "sibling_count": sibling_count,
            "median_typical_lines": median_typical_lines,
            "median_typical_tokens": median_typical_tokens,
            "typical_lines": typical_lines,
            "typical_tokens": typical_tokens,
            "lines_ratio": lines_ratio,
            "tokens_ratio": tokens_ratio,
            "is_outlier": is_outlier,
            "benchmark_lines": BENCHMARK_LINES,
            "benchmark_tokens": BENCHMARK_TOKENS,
            "deferred_classification": classification,
            "deferred_classification_reason": classification_reason,
        },
        "oversized_blocks": [{"line": l, "lines": n, "tokens": t} for l, n, t in codeblocks],
        "oversized_tables": [{"line": l, "lines": n, "tokens": t} for l, n, t in tables],
        "unbalanced_fence": unbalanced,
        "orphaned_files": entry["orphaned_files"],
        "ungated_mentions": entry["ungated_mentions"],
    }


def summarize_orphans(orphaned):
    """Groups orphaned files by parent directory; a directory with more
    than ORPHAN_GROUP_THRESHOLD orphans collapses into one summary item,
    so an intentional asset library (e.g. dozens of icons looked up by a
    search script rather than named individually in SKILL.md) doesn't
    drown out genuinely actionable single-file findings. The JSON output
    is unaffected -- it keeps the full flat list. Returns a list of either
    {"kind": "file", "path", "tokens"} or {"kind": "group", "dir", "count", "tokens"}."""
    by_dir = {}
    for o in orphaned:
        by_dir.setdefault(str(Path(o["path"]).parent), []).append(o)
    items = []
    for parent in sorted(by_dir):
        group = by_dir[parent]
        if len(group) > ORPHAN_GROUP_THRESHOLD:
            items.append(
                {"kind": "group", "dir": parent, "count": len(group), "tokens": sum(g["tokens"] for g in group)}
            )
        else:
            items.extend({"kind": "file", "path": g["path"], "tokens": g["tokens"]} for g in group)
    return items


def format_benchmark(value):
    return f"{value:,}" if value is not None else "--"


def format_signed(value, pct):
    text = f"{value:+,}"
    return f"{text} ({pct:+.1f}%)" if pct is not None else text


# --- Persistent stats store (skill_budget_stats.json) ----------------------


def load_stats_store(path):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    data.setdefault("corpus", {})
    data.setdefault("skills", {})
    return data


def save_stats_store(path, store):
    path.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")


def record_skill_snapshot(store, name, version, release_date, composition, today):
    """Appends/refreshes this skill's entry in the stats store (mutates
    store in place) and returns a dict describing what happened:
      {"status": "first"} -- no prior snapshot existed for this skill
      {"status": "unchanged", "version", "recorded_at"} -- same version as
        the last recorded snapshot; that entry was refreshed in place
      {"status": "changed", "previous_version", "previous_release_date",
       "lines_delta", "lines_pct", "tokens_delta", "tokens_pct"} -- version
        differs from the last recorded snapshot; a new entry was appended
    """
    history = store.setdefault("skills", {}).setdefault(name, [])
    snapshot = {
        "version": version,
        "release_date": release_date,
        "recorded_at": today,
        "composition": composition,
    }

    if not history:
        history.append(snapshot)
        return {"status": "first"}

    previous = history[-1]
    if previous.get("version") == version:
        history[-1] = snapshot
        return {"status": "unchanged", "version": version, "recorded_at": previous.get("recorded_at")}

    history.append(snapshot)
    prev_total = previous["composition"]["total"]
    curr_total = composition["total"]

    def pct_change(prev_v, curr_v):
        return ((curr_v - prev_v) / prev_v * 100) if prev_v else None

    return {
        "status": "changed",
        "previous_version": previous.get("version"),
        "previous_release_date": previous.get("release_date"),
        "lines_delta": curr_total["lines"] - prev_total["lines"],
        "lines_pct": pct_change(prev_total["lines"], curr_total["lines"]),
        "tokens_delta": curr_total["tokens"] - prev_total["tokens"],
        "tokens_pct": pct_change(prev_total["tokens"], curr_total["tokens"]),
    }


# --- Rendering ---------------------------------------------------------


def render_text(result):
    c = result["composition"]
    cmp = result["comparison"]
    vd = result.get("version_delta")
    out = [f"=== {result['skill']} ==="]

    out.append("Skill Composition:")
    deferred_note = (
        f"Loaded only if referenced ({c['deferred']['file_count']} files)"
        if c["deferred"]["file_count"]
        else "No reference/scripts/assets files in this skill"
    )
    rows = [
        ("Description (frontmatter)", c["description"]["lines"], c["description"]["tokens"],
         "Always loaded, every skill, every turn (FYI)"),
        ("Body (SKILL.md)", c["body"]["lines"], c["body"]["tokens"], "Loaded whenever this skill triggers"),
        ("Deferred (reference/scripts/assets)", c["deferred"]["lines"], c["deferred"]["tokens"], deferred_note),
        ("Total", c["total"]["lines"], c["total"]["tokens"], "Worst case if everything is read"),
    ]
    for label, ln, tok, note in rows:
        out.append(f"  {label:<38} lines={ln:<6,} tokens={tok:<8,} {note}")
    out.append("")

    out.append("Comparison:")
    out.append(
        f"  Deferred usage: {cmp['deferred_classification']}"
        + (f" -- {cmp['deferred_classification_reason']}" if cmp["deferred_classification_reason"]
           else " (default -- not yet reviewed for this skill)")
    )
    if cmp["sibling_count"] >= 2 and cmp["median_typical_tokens"]:
        tag = " [OUTLIER]" if cmp["is_outlier"] else ""
        out.append(
            f"  {result['skill']}'s typical-call footprint is {cmp['tokens_ratio']:.2f}x the Signatry median "
            f"({cmp['typical_tokens']:,} vs {cmp['median_typical_tokens']:,.0f} tokens "
            f"across {cmp['sibling_count']} skills){tag}"
        )
        out.append(f"  {'':8} {'Typical Call':>13} {'Worst Case':>11} {'Signatry Med':>13} {'Benchmark':>10}")
        out.append(
            f"  {'Lines':<8} {cmp['typical_lines']:>13,} {c['total']['lines']:>11,} "
            f"{cmp['median_typical_lines']:>13,.0f} {format_benchmark(cmp['benchmark_lines']):>10}"
        )
        out.append(
            f"  {'Tokens':<8} {cmp['typical_tokens']:>13,} {c['total']['tokens']:>11,} "
            f"{cmp['median_typical_tokens']:>13,.0f} {format_benchmark(cmp['benchmark_tokens']):>10}"
        )
    else:
        out.append("  Not enough sibling skills under this root to compute a Signatry median.")
    out.append("")

    out.append("Version Delta:")
    if vd is None:
        pass
    elif vd["status"] == "first":
        out.append("  No prior version on record for this skill -- this is its first tracked snapshot.")
    elif vd["status"] == "unchanged":
        out.append(
            f"  No version change since the last recorded snapshot (v{vd['version']}, recorded {vd['recorded_at']})."
        )
    else:
        out.append(
            f"  Compared to the last recorded version (v{vd['previous_version']}, "
            f"released {vd['previous_release_date']}):"
        )
        out.append(f"    total lines:  {format_signed(vd['lines_delta'], vd['lines_pct'])}")
        out.append(f"    total tokens: {format_signed(vd['tokens_delta'], vd['tokens_pct'])}")
    out.append("")

    for b in result["oversized_blocks"]:
        out.append(
            f"[INFO] oversized code block SKILL.md:{b['line']} ({b['lines']} lines, ~{b['tokens']} tok) "
            "-> consider scripts/"
        )
    if result["unbalanced_fence"]:
        out.append("[WARN] SKILL.md has an unbalanced code fence (odd number of ``` markers)")
    for tb in result["oversized_tables"]:
        out.append(
            f"[INFO] oversized table    SKILL.md:{tb['line']} ({tb['lines']} lines, ~{tb['tokens']} tok) "
            "-> consider reference(s)/"
        )
    for item in summarize_orphans(result["orphaned_files"]):
        if item["kind"] == "group":
            out.append(
                f"[WARN] {item['count']} orphaned files under {item['dir']}/ (~{item['tokens']:,} tok total) -- "
                "never individually mentioned in SKILL.md (may be intentionally found via a script rather than named)"
            )
        else:
            out.append(
                f"[WARN] orphaned file {item['path']} (~{item['tokens']:,} tok) -- never mentioned in SKILL.md"
            )
    for u in result["ungated_mentions"]:
        out.append(
            f"[WARN] {u['path']} (~{u['tokens']:,} tok) mentioned SKILL.md:{u['line']} "
            "with no load-when gating language"
        )
    return "\n".join(out)


def render_markdown(result):
    """Renders the same findings as render_text, but as an actual Markdown
    document (tables, headers, bold labels, code spans) -- this is what
    gets written to <skill>/_exclude/skill_budget_audit.md."""
    c = result["composition"]
    cmp = result["comparison"]
    vd = result.get("version_delta")
    md = [f"# Skill Budget Audit: {result['skill']}", ""]

    md.append("## Skill Composition")
    md.append("")
    md.append("| Skill Section | Lines | Tokens | Notes |")
    md.append("|---|---|---|---|")
    md.append(
        f"| Description (frontmatter) | {c['description']['lines']:,} | {c['description']['tokens']:,} | "
        "Always loaded, every skill, every turn (FYI — length/quality governed by lint) |"
    )
    md.append(
        f"| Body (`SKILL.md`) | {c['body']['lines']:,} | {c['body']['tokens']:,} | "
        "Loaded whenever this skill triggers |"
    )
    deferred_note = (
        f"Loaded only if `SKILL.md` points Claude to it ({c['deferred']['file_count']} file"
        f"{'s' if c['deferred']['file_count'] != 1 else ''})"
        if c["deferred"]["file_count"]
        else "No `reference/`, `scripts/`, or `assets/` files in this skill"
    )
    md.append(f"| Deferred (`reference/`, `scripts/`, `assets/`) | {c['deferred']['lines']:,} | {c['deferred']['tokens']:,} | {deferred_note} |")
    md.append(
        f"| **Total** | **{c['total']['lines']:,}** | **{c['total']['tokens']:,}** | "
        "Worst case if everything is read |"
    )
    md.append("")

    md.append("## Comparison")
    md.append("")
    classification = cmp["deferred_classification"]
    reason = cmp["deferred_classification_reason"]
    md.append(
        f"**Deferred usage:** `{classification}`"
        + (f" — {reason}" if reason else " (default — not yet reviewed for this skill)")
    )
    md.append("")
    if cmp["sibling_count"] >= 2 and cmp["median_typical_tokens"]:
        tag = " **[OUTLIER]**" if cmp["is_outlier"] else ""
        md.append(
            f"`{result['skill']}`'s typical-call footprint is {cmp['tokens_ratio']:.2f}x the Signatry median "
            f"({cmp['typical_tokens']:,} vs {cmp['median_typical_tokens']:,.0f} tokens "
            f"across {cmp['sibling_count']} skills){tag}."
        )
        md.append("")
        md.append("| | Skill Typical Call | Skill Worst Case | Signatry Median | Benchmark |")
        md.append("|---|---|---|---|---|")
        md.append(
            f"| Lines | {cmp['typical_lines']:,} | {c['total']['lines']:,} | {cmp['median_typical_lines']:,.0f} | "
            f"{format_benchmark(cmp['benchmark_lines'])} |"
        )
        md.append(
            f"| Tokens | {cmp['typical_tokens']:,} | {c['total']['tokens']:,} | {cmp['median_typical_tokens']:,.0f} | "
            f"{format_benchmark(cmp['benchmark_tokens'])} |"
        )
    else:
        md.append("Not enough sibling skills under this root to compute a Signatry median.")
    md.append("")

    md.append("## Version Delta")
    md.append("")
    if vd is None:
        md.append("Not tracked this run.")
    elif vd["status"] == "first":
        md.append("No prior version on record for this skill — this is its first tracked snapshot.")
    elif vd["status"] == "unchanged":
        md.append(f"No version change since the last recorded snapshot (v{vd['version']}, recorded {vd['recorded_at']}).")
    else:
        md.append(
            f"Compared to the last recorded version (v{vd['previous_version']}, "
            f"released {vd['previous_release_date']}): total lines "
            f"**{format_signed(vd['lines_delta'], vd['lines_pct'])}**, total tokens "
            f"**{format_signed(vd['tokens_delta'], vd['tokens_pct'])}**."
        )
    md.append("")

    md.append("## Findings")
    md.append("")

    findings = []
    for b in result["oversized_blocks"]:
        findings.append(
            f"- **[INFO]** oversized code block `SKILL.md:{b['line']}` ({b['lines']} lines, ~{b['tokens']} tok) "
            "-> consider `scripts/`"
        )
    if result["unbalanced_fence"]:
        findings.append("- **[WARN]** SKILL.md has an unbalanced code fence (odd number of ``` markers)")
    for tb in result["oversized_tables"]:
        findings.append(
            f"- **[INFO]** oversized table `SKILL.md:{tb['line']}` ({tb['lines']} lines, ~{tb['tokens']} tok) "
            "-> consider `reference(s)/`"
        )
    for item in summarize_orphans(result["orphaned_files"]):
        if item["kind"] == "group":
            findings.append(
                f"- **[WARN]** {item['count']} orphaned files under `{item['dir']}/` "
                f"(~{item['tokens']:,} tok total) -- never individually mentioned in SKILL.md "
                "(may be intentionally found via a script rather than named)"
            )
        else:
            findings.append(
                f"- **[WARN]** orphaned file `{item['path']}` (~{item['tokens']:,} tok) "
                "-- never mentioned in SKILL.md"
            )
    for u in result["ungated_mentions"]:
        findings.append(
            f"- **[WARN]** `{u['path']}` (~{u['tokens']:,} tok) mentioned `SKILL.md:{u['line']}` "
            "with no load-when gating language"
        )

    if findings:
        md.extend(findings)
    else:
        md.append("No recommendations -- this skill's context/token footprint looks efficiently structured.")
    md.append("")
    md.append("---")
    md.append("_Generated by `skills/skill_budget_audit.py`. Advisory only -- does not affect lint or packaging._")
    return "\n".join(md)


def write_report(skill_dir, filename, content):
    out_dir = skill_dir / EXCLUDE_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("skill", nargs="?", default=None, help="Skill directory name to analyze, e.g. signatry-style")
    parser.add_argument("--all", action="store_true", help="Analyze every skill under --path")
    parser.add_argument("--path", default=str(Path(__file__).parent), help="Path to the skills/ directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Report filename written into <skill>/_exclude/ for each analyzed skill "
            "(default: skill_budget_audit.md, or skill_budget_audit.json with --json). "
            "Any directory component is ignored -- it always lands in that skill's own _exclude/."
        ),
    )
    args = parser.parse_args()

    if bool(args.skill) == bool(args.all):
        parser.error("provide exactly one of: a skill name, or --all")

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"{root}: not a directory", file=sys.stderr)
        return 1

    index, load_errors = build_corpus_index(root)
    deferred_usage_config = load_deferred_usage_config()

    typical_pairs = []
    for name, entry in index.items():
        classification, _ = classify_deferred_usage(name, deferred_usage_config)
        typical_pairs.append(typical_total_for(entry, classification))
    typical_tokens_values = [t for t, l in typical_pairs]
    typical_lines_values = [l for t, l in typical_pairs]
    sibling_count = len(index)
    median_typical_tokens = statistics.median(typical_tokens_values) if sibling_count >= 2 else None
    median_typical_lines = statistics.median(typical_lines_values) if sibling_count >= 2 else None

    today = datetime.date.today().isoformat()
    stats_path = root / STATS_FILENAME
    store = load_stats_store(stats_path)
    store["corpus"] = {
        "recorded_at": today,
        "sibling_count": sibling_count,
        "median_typical_lines": median_typical_lines,
        "median_typical_tokens": median_typical_tokens,
    }

    report_filename = Path(args.output).name if args.output else f"skill_budget_audit.{'json' if args.json else 'md'}"

    def analyze_and_record(name, entry):
        result = analyze_skill(
            name, entry, median_typical_lines, median_typical_tokens, sibling_count, deferred_usage_config
        )
        result["version_delta"] = record_skill_snapshot(
            store, name, result["version"], result["release_date"], result["composition"], today
        )
        return result

    def write_skill_report(name, result):
        content = json.dumps({name: result}, indent=2) if args.json else render_markdown(result)
        out_path = write_report(index[name]["skill_dir"], report_filename, content)
        print(f"[WROTE] {out_path.relative_to(root.parent)}")

    if args.all:
        results = {name: analyze_and_record(name, entry) for name, entry in sorted(index.items())}
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for name in sorted(results):
                print(render_text(results[name]))
                print()
            for name, error in sorted(load_errors.items()):
                print(f"[SKIP] {name}: {error}")
        for name in sorted(results):
            write_skill_report(name, results[name])
        save_stats_store(stats_path, store)
        return 0

    skill_dir = root / args.skill
    if not skill_dir.is_dir():
        print(f"{args.skill}: not a skill directory under {root}", file=sys.stderr)
        return 1
    if args.skill in load_errors:
        print(f"{args.skill}: {load_errors[args.skill]}", file=sys.stderr)
        return 1

    result = analyze_and_record(args.skill, index[args.skill])
    if args.json:
        print(json.dumps({args.skill: result}, indent=2))
    else:
        print(render_text(result))
    write_skill_report(args.skill, result)
    save_stats_store(stats_path, store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
