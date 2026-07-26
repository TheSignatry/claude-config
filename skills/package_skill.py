#!/usr/bin/env python3
"""Package a single Signatry Claude Skill into an upload-ready zip artifact.

Builds a zip with SKILL.md at the zip root (Anthropic's upload requirement —
no wrapping folder inside the archive) and saves it as
{skill-slug}-{version}.zip inside that skill's own directory. Refuses to
package a skill that fails skills/lint_skills.py with an ERROR or CRITICAL
finding; run that script directly to see why.

Usage:
  python3 skills/package_skill.py signatry-style
  python3 skills/package_skill.py signatry-style --dry-run

Exit codes:
  0 - skill packaged (or --dry-run shown)
  1 - skill not found, or failed lint and was not packaged
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

from lint_skills import SEVERITY_CRITICAL, SEVERITY_ERROR, lint_skill, parse_frontmatter

EXCLUDE_DIR_NAMES = {"__pycache__", ".git"}
EXCLUDE_FILE_NAMES = {".DS_Store"}
EXCLUDE_SUFFIXES = {".zip", ".pyc"}


def build_zip(skill_dir, slug, version):
    for old in skill_dir.glob(f"{slug}-*.zip"):
        old.unlink()

    out_path = skill_dir / f"{slug}-{version}.zip"
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(skill_dir.rglob("*")):
            if file_path.is_dir():
                continue
            if EXCLUDE_DIR_NAMES & set(file_path.relative_to(skill_dir).parts[:-1]):
                continue
            if file_path.name in EXCLUDE_FILE_NAMES or file_path.suffix.lower() in EXCLUDE_SUFFIXES:
                continue
            zf.write(file_path, file_path.relative_to(skill_dir))
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("skill", help="Skill directory name to package, e.g. signatry-style")
    parser.add_argument("--path", default=str(Path(__file__).parent), help="Path to the skills/ directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be packaged without writing a zip")
    args = parser.parse_args()

    skills_root = Path(args.path).resolve()
    schema_path = Path(__file__).parent.parent / "schemas" / "skill-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    skill_dir = skills_root / args.skill
    if not skill_dir.is_dir():
        print(f"{args.skill}: not a skill directory under {skills_root}", file=sys.stderr)
        return 1

    issues = lint_skill(skill_dir, schema)
    blocking = [(sev, msg) for sev, msg in issues if sev in (SEVERITY_ERROR, SEVERITY_CRITICAL)]
    if blocking:
        print(f"[SKIP] {args.skill}: failed lint, run skills/lint_skills.py for details")
        for severity, message in blocking:
            print(f"    {severity:9s} {message}")
        return 1

    frontmatter, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    slug = frontmatter.get("name", skill_dir.name)
    version = frontmatter["version"]

    if args.dry_run:
        print(f"[DRY-RUN] would package {args.skill} -> {slug}-{version}.zip")
        return 0

    out_path = build_zip(skill_dir, slug, version)
    print(f"[OK] {args.skill} -> {out_path.relative_to(skills_root.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
