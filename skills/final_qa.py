#!/usr/bin/env python3
"""Run the full pre-commit/pre-PR QA pass across every skill under skills/.

Combines what skill_budget_audit.py/lint_skills.py/package_skill.py already
do individually, plus two cross-cutting checks that only make sense once
every skill's data is in hand:

  1. Lint every skill (lint_skills.py's lint_skill()) -- structural/schema/
     changelog-standard validation, IT15 Restricted-data scan.
  2. Budget-audit every skill (skill_budget_audit.py's analyze_skill()) --
     advisory context/token-budget check. Refreshes every skill's
     _exclude/skill_budget_audit.md and skills/skill_budget_stats.json,
     not just the ones with findings.
  3. Flag any skill with deferred content but no entry in
     skills/deferred_usage.json (silently defaulting to the more
     conservative deferred-full-use classification, unreviewed).
  4. Flag any skill whose frontmatter version/release_date don't match
     README.md's version table.
  5. Package every skill that passes lint (package_skill.py's build_zip())
     -- also refreshes any zip left over from a prior version, since
     build_zip() deletes old {slug}-*.zip files before writing the new one.

This does NOT check org-instructions/ (that needs an actual regenerate-
and-diff, not a static comparison) or whether README's prose descriptions
still read accurately (a judgment call, not something a script can
verify) -- see CLAUDE.md's "Final QA pass" section for those steps.

Usage:
  python3 skills/final_qa.py
  python3 skills/final_qa.py --path path/to/skills

Exit codes:
  0 - no skill has an ERROR/CRITICAL lint finding (warnings may still print)
  1 - at least one skill has an ERROR/CRITICAL lint finding
"""
import argparse
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

from lint_skills import SEVERITY_CRITICAL, SEVERITY_ERROR, SEVERITY_WARNING, lint_skill
from skill_budget_audit import (
    STATS_FILENAME,
    analyze_skill,
    build_corpus_index,
    classify_deferred_usage,
    load_deferred_usage_config,
    load_stats_store,
    record_skill_snapshot,
    render_markdown,
    save_stats_store,
    typical_total_for,
    write_report,
)
from package_skill import build_zip

README_SLUG_RE = re.compile(r"`([a-z0-9\-]+)`")


def discover_skills(root):
    return sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))


def run_lint_phase(skill_dirs, schema, allowlist):
    return {d.name: lint_skill(d, schema, allowlist) for d in skill_dirs}


def parse_readme_table(readme_text):
    """Returns {slug: (version, release_date)} parsed from the Skills table.
    Matches any table row whose first cell has a backtick-quoted slug --
    naturally skips the header/separator rows, which have neither."""
    entries = {}
    for line in readme_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        m = README_SLUG_RE.search(cells[0])
        if not m:
            continue
        entries[m.group(1)] = (cells[-2], cells[-1])
    return entries


def check_readme_freshness(root, budget_index):
    """Compares each skill's actual frontmatter version/release_date against
    README.md's version table. README.md is always resolved relative to
    this script's own location (matching how lint_skills.py resolves
    schemas/skill-schema.json) -- it's a repo-level file, not something
    that exists relative to an arbitrary --path fixture root."""
    readme_path = Path(__file__).parent.parent / "README.md"
    if not readme_path.exists():
        return ["README.md not found"]
    table = parse_readme_table(readme_path.read_text(encoding="utf-8"))

    issues = []
    for name, entry in sorted(budget_index.items()):
        frontmatter = entry.get("frontmatter")
        if not isinstance(frontmatter, dict):
            continue
        actual_version = str(frontmatter.get("version", ""))
        actual_date = str(frontmatter.get("release_date", ""))
        if name not in table:
            issues.append(f"{name}: missing from README.md's version table")
            continue
        readme_version, readme_date = table[name]
        if readme_version != actual_version or readme_date != actual_date:
            issues.append(
                f"{name}: README shows {readme_version}/{readme_date}, actual is {actual_version}/{actual_date}"
            )
    return issues


def check_deferred_usage_gap(budget_results, deferred_usage_config):
    issues = []
    for name in sorted(budget_results):
        deferred_tokens = budget_results[name]["composition"]["deferred"]["tokens"]
        if deferred_tokens > 0 and name not in deferred_usage_config:
            issues.append(
                f"{name}: {deferred_tokens:,} deferred tokens, no deferred_usage.json entry "
                "(defaults to deferred-full-use, unreviewed)"
            )
    return issues


def run_package_phase(skill_dirs, lint_results, budget_index):
    """Packages every skill that passes lint, returning {name: {"status", "note"/"reason"}}.
    Notes any pre-existing zip's version before build_zip() deletes and
    replaces it, so the summary can distinguish a stale rebuild from a
    first-time packaging or an already-current one."""
    results = {}
    for skill_dir in skill_dirs:
        name = skill_dir.name
        blocking = [i for i in lint_results.get(name, []) if i[0] in (SEVERITY_ERROR, SEVERITY_CRITICAL)]
        if blocking:
            results[name] = {"status": "skipped", "reason": "failed lint"}
            continue

        entry = budget_index.get(name)
        frontmatter = entry.get("frontmatter") if entry else None
        if not isinstance(frontmatter, dict) or not frontmatter.get("version"):
            results[name] = {"status": "skipped", "reason": "no usable frontmatter/version"}
            continue

        slug = frontmatter.get("name", name)
        version = str(frontmatter["version"])
        existing = sorted(skill_dir.glob(f"{slug}-*.zip"))
        previous_version = existing[0].stem[len(slug) + 1 :] if existing else None

        build_zip(skill_dir, slug, version)

        if previous_version is None:
            note = "packaged for the first time"
        elif previous_version == version:
            note = "already current"
        else:
            note = f"stale {previous_version}->{version}, refreshed"
        results[name] = {"status": "packaged", "note": note}
    return results


def print_summary(skill_dirs, lint_results, budget_results, package_results, deferred_gap_issues, readme_issues):
    print(f"{'Skill':<30} {'Lint':<8} {'Budget':<10} Package")
    for skill_dir in skill_dirs:
        name = skill_dir.name
        issues = lint_results.get(name, [])
        blocking = [i for i in issues if i[0] in (SEVERITY_ERROR, SEVERITY_CRITICAL)]
        lint_status = "FAIL" if blocking else ("WARN" if issues else "PASS")

        budget_result = budget_results.get(name)
        if budget_result is None:
            budget_status = "n/a"
        else:
            budget_status = "OUTLIER" if budget_result["comparison"]["is_outlier"] else "ok"

        pkg = package_results.get(name, {})
        pkg_note = pkg.get("note") or pkg.get("reason") or "n/a"
        print(f"{name:<30} {lint_status:<8} {budget_status:<10} {pkg_note}")

    total = len(skill_dirs)
    blocking_lines = [
        f"{name}: {severity} {message}"
        for name, issues in lint_results.items()
        for severity, message in issues
        if severity in (SEVERITY_ERROR, SEVERITY_CRITICAL)
    ]
    clean = total - len({name for name, issues in lint_results.items()
                          for severity, _ in issues if severity in (SEVERITY_ERROR, SEVERITY_CRITICAL)})

    warnings = [
        f"{name}: {message}"
        for name, issues in lint_results.items()
        for severity, message in issues
        if severity == SEVERITY_WARNING
    ]
    warnings.extend(
        f"{name}: token-budget outlier (see _exclude/skill_budget_audit.md)"
        for name, result in sorted(budget_results.items())
        if result["comparison"]["is_outlier"]
    )
    warnings.extend(deferred_gap_issues)
    warnings.extend(f"README.md: {msg}" for msg in readme_issues)

    print()
    print(f"{clean}/{total} linted clean.  {len(blocking_lines)} blocking, {len(warnings)} warnings.")
    if blocking_lines:
        print()
        print("BLOCKING:")
        for line in blocking_lines:
            print(f"  - {line}")
    if warnings:
        print()
        print("WARNINGS:")
        for line in warnings:
            print(f"  - {line}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=str(Path(__file__).parent), help="Path to the skills/ directory")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"{root}: not a directory", file=sys.stderr)
        return 1

    schema_path = Path(__file__).parent.parent / "schemas" / "skill-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    allowlist_path = Path(__file__).parent / "lint_allowlist.json"
    allowlist = {}
    if allowlist_path.exists():
        raw_allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
        allowlist = {k: v for k, v in raw_allowlist.items() if not k.startswith("_")}

    skill_dirs = discover_skills(root)
    lint_results = run_lint_phase(skill_dirs, schema, allowlist)

    deferred_usage_config = load_deferred_usage_config()
    budget_index, budget_load_errors = build_corpus_index(root)
    for name, error in sorted(budget_load_errors.items()):
        print(f"[SKIP] {name}: {error}", file=sys.stderr)

    typical_pairs = [
        typical_total_for(entry, classify_deferred_usage(name, deferred_usage_config)[0])
        for name, entry in budget_index.items()
    ]
    sibling_count = len(budget_index)
    median_typical_tokens = statistics.median([t for t, l in typical_pairs]) if sibling_count >= 2 else None
    median_typical_lines = statistics.median([l for t, l in typical_pairs]) if sibling_count >= 2 else None

    today = datetime.date.today().isoformat()
    stats_path = root / STATS_FILENAME
    store = load_stats_store(stats_path)
    store["corpus"] = {
        "recorded_at": today,
        "sibling_count": sibling_count,
        "median_typical_lines": median_typical_lines,
        "median_typical_tokens": median_typical_tokens,
    }

    budget_results = {}
    for name, entry in sorted(budget_index.items()):
        result = analyze_skill(
            name, entry, median_typical_lines, median_typical_tokens, sibling_count, deferred_usage_config
        )
        result["version_delta"] = record_skill_snapshot(
            store, name, result["version"], result["release_date"], result["composition"], today
        )
        write_report(entry["skill_dir"], "skill_budget_audit.md", render_markdown(result))
        budget_results[name] = result
    save_stats_store(stats_path, store)

    deferred_gap_issues = check_deferred_usage_gap(budget_results, deferred_usage_config)
    readme_issues = check_readme_freshness(root, budget_index)
    package_results = run_package_phase(skill_dirs, lint_results, budget_index)

    print_summary(skill_dirs, lint_results, budget_results, package_results, deferred_gap_issues, readme_issues)

    has_error = any(
        severity in (SEVERITY_ERROR, SEVERITY_CRITICAL) for issues in lint_results.values() for severity, _ in issues
    )
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
