#!/usr/bin/env python3
"""Snapshot and restore the acos family's runtime state, outside the git tree.

Why this exists
---------------
`state/` under acos-aboutme and acos-email-sort holds the only copy of a
person's profile: the org chart, VIP list, partner vendors, protected senders,
Jira project keys, and the email-sort ledger. Those files are gitignored on
purpose (real names and addresses do not belong in the repo), which means git
is not a safety net for them. An acos-aboutme profile has already been lost
once to a working-tree restructure and had to be recovered from a stray
download.

Snapshots therefore land in ~/.claude/acos-state-backups/, deliberately
OUTSIDE the repository, so they survive a clone, a branch switch, a clean
checkout, a restructure, or `git clean -fdx`.

This is repo tooling, not part of any skill — it lives beside package_skill.py
and is never packaged or shipped.

Usage
-----
    python3 skills/acos_state_backup.py                 # snapshot every acos state/ dir
    python3 skills/acos_state_backup.py --list          # list snapshots, newest first
    python3 skills/acos_state_backup.py --verify LABEL  # re-hash a snapshot's files
    python3 skills/acos_state_backup.py --restore LABEL # copy a snapshot back into the repo
    python3 skills/acos_state_backup.py --restore LABEL --skill acos-aboutme
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
BACKUP_ROOT = Path.home() / ".claude" / "acos-state-backups"
MANIFEST_NAME = "manifest.json"
LABEL_RE = re.compile(r"^\d{8}T\d{6}Z$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def skill_version(skill_dir: Path) -> str | None:
    """Best-effort frontmatter version, recorded so a restore can be judged."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.split("\n", 40)[:40]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


def state_dirs() -> list[Path]:
    """Every acos-* skill that actually has a state/ directory."""
    return sorted(
        d / "state"
        for d in SKILLS_DIR.glob("acos-*")
        if d.is_dir() and (d / "state").is_dir()
    )


def snapshot(label: str | None = None) -> Path:
    label = label or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_root = BACKUP_ROOT / label
    if dest_root.exists():
        sys.exit(f"snapshot {label} already exists at {dest_root}")

    dirs = state_dirs()
    if not dirs:
        sys.exit(f"no acos-*/state/ directories found under {SKILLS_DIR}")

    entries: list[dict] = []
    for state_dir in dirs:
        skill_dir = state_dir.parent
        for src in sorted(state_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(SKILLS_DIR)
            dest = dest_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            entries.append(
                {
                    "path": str(rel),
                    "skill": skill_dir.name,
                    "skill_version": skill_version(skill_dir),
                    "bytes": src.stat().st_size,
                    "sha256": sha256(src),
                }
            )

    manifest = {
        "label": label,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source_root": str(SKILLS_DIR),
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
    }
    (dest_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"snapshot {label} -> {dest_root}")
    for e in entries:
        print(f"  {e['bytes']:>7,}B  {e['sha256'][:12]}  {e['path']}")
    print(f"  {len(entries)} files, {manifest['total_bytes']:,} bytes")
    return dest_root


def load_manifest(label: str) -> dict:
    path = BACKUP_ROOT / label / MANIFEST_NAME
    if not path.exists():
        sys.exit(f"no manifest at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots() -> None:
    if not BACKUP_ROOT.exists():
        print(f"no snapshots yet ({BACKUP_ROOT} does not exist)")
        return
    labels = sorted((p.name for p in BACKUP_ROOT.iterdir() if p.is_dir()), reverse=True)
    if not labels:
        print(f"no snapshots yet under {BACKUP_ROOT}")
        return
    print(f"{BACKUP_ROOT}")
    for label in labels:
        try:
            m = load_manifest(label)
            skills = sorted({f["skill"] for f in m["files"]})
            print(
                f"  {label}  {m['file_count']:>2} files  {m['total_bytes']:>7,}B  "
                f"{', '.join(skills)}"
            )
        except SystemExit:
            print(f"  {label}  (no manifest)")


def verify(label: str) -> int:
    m = load_manifest(label)
    bad = 0
    for e in m["files"]:
        stored = BACKUP_ROOT / label / e["path"]
        if not stored.exists():
            print(f"  MISSING  {e['path']}")
            bad += 1
        elif sha256(stored) != e["sha256"]:
            print(f"  CORRUPT  {e['path']}")
            bad += 1
    print(f"{label}: {m['file_count'] - bad}/{m['file_count']} files verified")
    return 1 if bad else 0


def restore(label: str, only_skill: str | None, force: bool) -> None:
    m = load_manifest(label)
    files = [f for f in m["files"] if not only_skill or f["skill"] == only_skill]
    if not files:
        sys.exit(f"snapshot {label} has nothing for skill {only_skill!r}")

    # Refuse to clobber divergent live files unless explicitly forced: a restore
    # after a fresh enrollment would otherwise silently discard the new profile.
    if not force:
        clashes = [
            f for f in files
            if (SKILLS_DIR / f["path"]).exists()
            and sha256(SKILLS_DIR / f["path"]) != f["sha256"]
        ]
        if clashes:
            print("refusing to overwrite live files that differ from the snapshot:")
            for f in clashes:
                print(f"  {f['path']}")
            sys.exit("re-run with --force if you really mean to replace them")

    for f in files:
        src = BACKUP_ROOT / label / f["path"]
        dest = SKILLS_DIR / f["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  restored {f['path']}")
    print(f"{len(files)} files restored from {label}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--list", action="store_true", help="list snapshots, newest first")
    g.add_argument("--verify", metavar="LABEL", help="re-hash a snapshot against its manifest")
    g.add_argument("--restore", metavar="LABEL", help="copy a snapshot back into the repo")
    ap.add_argument("--skill", help="with --restore: limit to one skill")
    ap.add_argument("--force", action="store_true", help="with --restore: overwrite differing live files")
    ap.add_argument("--label", help="override the snapshot label (default: UTC timestamp)")
    args = ap.parse_args()

    if args.list:
        list_snapshots()
    elif args.verify:
        sys.exit(verify(args.verify))
    elif args.restore:
        if not LABEL_RE.match(args.restore) and not (BACKUP_ROOT / args.restore).is_dir():
            sys.exit(f"unknown snapshot {args.restore!r}; run --list")
        restore(args.restore, args.skill, args.force)
    else:
        snapshot(args.label)


if __name__ == "__main__":
    main()
