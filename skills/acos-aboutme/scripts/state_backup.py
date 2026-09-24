#!/usr/bin/env python3
"""Snapshot and restore the acos family's runtime state, outside the skill tree.

Why this exists
---------------
`state/` under acos-aboutme and acos-email-sort holds the only copy of a
person's profile: the org chart, VIP list, partner vendors, protected senders,
Jira project keys, and the email-sort ledger. Those files are deliberately kept
out of git and out of the packaged zip (real names and addresses belong in
neither), which means neither git nor a reinstall is a safety net for them. An
acos-aboutme profile has already been lost once to a working-tree restructure
and had to be recovered from a stray download.

Snapshots land in ~/.claude/acos-state-backups/, deliberately OUTSIDE every
skill directory, so they survive a clone, a branch switch, a clean checkout, a
restructure, `git clean -fdx`, and a Console re-sync that replaces an installed
skill folder wholesale.

Two roots, not one
------------------
The same person usually has two live copies of this state:

  * the installed skills tree, e.g. ~/.claude/skills/synced/<id>/acos-aboutme/
    -- this is what actually runs, and what a re-sync can overwrite; and
  * a development checkout, e.g. <repo>/skills/acos-aboutme/

They drift apart, so backing up only one silently loses the other. This script
discovers every acos family root it can see and snapshots all of them, keeping
each root's files separate in the snapshot and restoring them to the root they
came from.

This file ships with the acos-aboutme skill, so it is available wherever the
skill is installed -- not only in the source repository.

Usage
-----
    python3 scripts/state_backup.py                  # snapshot every root
    python3 scripts/state_backup.py --roots          # show what would be covered
    python3 scripts/state_backup.py --list           # list snapshots, newest first
    python3 scripts/state_backup.py --verify LABEL   # re-hash a snapshot's files
    python3 scripts/state_backup.py --restore LABEL  # copy a snapshot back
    python3 scripts/state_backup.py --restore LABEL --skill acos-aboutme
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

BACKUP_ROOT = Path.home() / ".claude" / "acos-state-backups"
MANIFEST_NAME = "manifest.json"
LABEL_RE = re.compile(r"^\d{8}T\d{6}Z$")
MANIFEST_VERSION = 2


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def root_id(root: Path) -> str:
    """Short stable directory name for a root, so two roots holding the same
    relative path (both have acos-aboutme/state/profile.json) never collide
    inside one snapshot."""
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:10]


def family_roots(extra: list[str] | None = None) -> list[Path]:
    """Every directory that holds acos-* skill folders side by side.

    Ordered most-authoritative-first is not meaningful here -- all roots are
    snapshotted -- but the order is kept stable so output reads the same twice.
    """
    found: list[Path] = []

    def add(cand: Path) -> None:
        try:
            resolved = cand.resolve()
        except OSError:
            return
        if resolved.is_dir() and resolved not in found and any(resolved.glob("acos-*")):
            found.append(resolved)

    for raw in extra or []:
        add(Path(raw))

    here = Path(__file__).resolve()
    # Shipped at <root>/acos-aboutme/scripts/state_backup.py; also tolerate the
    # script sitting directly in a skills directory.
    if len(here.parents) >= 3:
        add(here.parents[2])
    add(here.parent)

    # Installed skill trees. Console-synced skills land as siblings inside one
    # generated folder (~/.claude/skills/synced/<id>/), so check that depth too
    # rather than only the top level.
    skills_home = Path.home() / ".claude" / "skills"
    if skills_home.is_dir():
        for pattern in ("acos-aboutme", "*/acos-aboutme", "*/*/acos-aboutme"):
            for marker in skills_home.glob(pattern):
                if marker.is_dir():
                    add(marker.parent)

    return found


def state_files(root: Path) -> list[Path]:
    """Every real file under any acos-*/state/ in this root, .gitkeep aside."""
    out = []
    for skill_dir in sorted(root.glob("acos-*")):
        state_dir = skill_dir / "state"
        if not state_dir.is_dir():
            continue
        for src in sorted(state_dir.rglob("*")):
            if src.is_file() and src.name != ".gitkeep":
                out.append(src)
    return out


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


def show_roots(extra: list[str] | None = None) -> None:
    roots = family_roots(extra)
    if not roots:
        sys.exit("no acos family root found; pass --root PATH")
    for root in roots:
        files = state_files(root)
        total = sum(f.stat().st_size for f in files)
        print(f"{root}\n  {root_id(root)}  {len(files)} state files, {total:,} bytes")
        for f in files:
            print(f"    {f.relative_to(root)}")


def snapshot(label: str | None = None, extra: list[str] | None = None) -> Path:
    roots = family_roots(extra)
    if not roots:
        sys.exit("no acos family root found; pass --root PATH")

    label = label or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_root = BACKUP_ROOT / label
    if dest_root.exists():
        sys.exit(f"snapshot {label} already exists at {dest_root}")

    entries: list[dict] = []
    roots_meta: dict[str, str] = {}

    for root in roots:
        rid = root_id(root)
        roots_meta[rid] = str(root)
        for src in state_files(root):
            rel = src.relative_to(root)
            skill_dir = root / rel.parts[0]
            dest = dest_root / rid / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            entries.append(
                {
                    "root_id": rid,
                    "rel": str(rel),
                    "skill": rel.parts[0],
                    "skill_version": skill_version(skill_dir),
                    "bytes": src.stat().st_size,
                    "sha256": sha256(src),
                }
            )

    if not entries:
        shutil.rmtree(dest_root, ignore_errors=True)
        sys.exit(
            "nothing to back up: found "
            f"{len(roots)} acos root(s) but no state files in them"
        )

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "label": label,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "roots": roots_meta,
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
    }
    (dest_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"snapshot {label} -> {dest_root}")
    for rid, root in roots_meta.items():
        mine = [e for e in entries if e["root_id"] == rid]
        print(f"  {root}  ({len(mine)} files)")
        for e in mine:
            print(f"    {e['bytes']:>7,}B  {e['sha256'][:12]}  {e['rel']}")
    print(f"  {len(entries)} files, {manifest['total_bytes']:,} bytes")
    return dest_root


def load_manifest(label: str) -> dict:
    path = BACKUP_ROOT / label / MANIFEST_NAME
    if not path.exists():
        sys.exit(f"no manifest at {path}")
    m = json.loads(path.read_text(encoding="utf-8"))
    if m.get("manifest_version", 1) < MANIFEST_VERSION:
        sys.exit(
            f"snapshot {label} was written by an older version of this script "
            "(single-root layout). Restore it by copying files out of "
            f"{BACKUP_ROOT / label} by hand."
        )
    return m


def stored_path(label: str, entry: dict) -> Path:
    return BACKUP_ROOT / label / entry["root_id"] / entry["rel"]


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
            m = json.loads(
                (BACKUP_ROOT / label / MANIFEST_NAME).read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            print(f"  {label}  (no manifest)")
            continue
        if m.get("manifest_version", 1) < MANIFEST_VERSION:
            print(f"  {label}  {m.get('file_count', '?')} files  (legacy single-root)")
            continue
        skills = sorted({f["skill"] for f in m["files"]})
        print(
            f"  {label}  {m['file_count']:>2} files  {m['total_bytes']:>7,}B  "
            f"{len(m['roots'])} root(s)  {', '.join(skills)}"
        )


def verify(label: str) -> int:
    m = load_manifest(label)
    bad = 0
    for e in m["files"]:
        stored = stored_path(label, e)
        if not stored.exists():
            print(f"  MISSING  {e['rel']}")
            bad += 1
        elif sha256(stored) != e["sha256"]:
            print(f"  CORRUPT  {e['rel']}")
            bad += 1
    print(f"{label}: {m['file_count'] - bad}/{m['file_count']} files verified")
    return 1 if bad else 0


def restore(
    label: str,
    only_skill: str | None,
    force: bool,
    into: str | None,
    from_root: str | None,
) -> None:
    m = load_manifest(label)
    files = [f for f in m["files"] if not only_skill or f["skill"] == only_skill]
    if not files:
        sys.exit(f"snapshot {label} has nothing for skill {only_skill!r}")

    if from_root:
        matches = {
            rid for rid, path in m["roots"].items()
            if rid == from_root or from_root in path
        }
        if not matches:
            sys.exit(f"no root in snapshot {label} matches {from_root!r}; run --list-roots {label}")
        if len(matches) > 1:
            print(f"{from_root!r} matches more than one root:")
            for rid in sorted(matches):
                print(f"  {rid}  {m['roots'][rid]}")
            sys.exit("narrow it, or pass the 10-character root id")
        files = [f for f in files if f["root_id"] in matches]
        if not files:
            sys.exit("that root contributed no matching files to this snapshot")

    # Redirecting every file into one directory merges the roots. Two roots
    # normally hold the SAME relative path (each has acos-aboutme/state/
    # profile.json), so a merge would write one over the other and silently
    # keep whichever happened to come last. Refuse instead of guessing.
    if into and len({f["root_id"] for f in files}) > 1:
        print("--root redirects every file into one directory, but this selection")
        print("spans more than one source root, which would overwrite paths:")
        for rid in sorted({f["root_id"] for f in files}):
            print(f"  {rid}  {m['roots'][rid]}")
        sys.exit("pick one with --from-root <id-or-path-fragment>")

    def target_root(entry: dict) -> Path | None:
        if into:
            return Path(into).resolve()
        recorded = Path(m["roots"][entry["root_id"]])
        return recorded if recorded.is_dir() else None

    missing_roots = sorted(
        {m["roots"][f["root_id"]] for f in files if target_root(f) is None}
    )
    if missing_roots:
        print("these roots no longer exist, so their files cannot be placed:")
        for r in missing_roots:
            print(f"  {r}")
        print("re-run with --root PATH to redirect the restore, or --skill to narrow it")
        files = [f for f in files if target_root(f) is not None]
        if not files:
            sys.exit("nothing left to restore")

    # Refuse to clobber divergent live files unless explicitly forced: a restore
    # after a fresh enrollment would otherwise silently discard the new profile.
    if not force:
        clashes = []
        for f in files:
            dest = target_root(f) / f["rel"]
            if dest.exists() and sha256(dest) != f["sha256"]:
                clashes.append(dest)
        if clashes:
            print("refusing to overwrite live files that differ from the snapshot:")
            for d in clashes:
                print(f"  {d}")
            sys.exit("re-run with --force if you really mean to replace them")

    for f in files:
        dest = target_root(f) / f["rel"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stored_path(label, f), dest)
        print(f"  restored {dest}")
    print(f"{len(files)} files restored from {label}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--roots", action="store_true", help="show the roots that would be covered")
    g.add_argument("--list", action="store_true", help="list snapshots, newest first")
    g.add_argument("--verify", metavar="LABEL", help="re-hash a snapshot against its manifest")
    g.add_argument("--restore", metavar="LABEL", help="copy a snapshot back into place")
    g.add_argument("--list-roots", metavar="LABEL", help="show the roots recorded in a snapshot")
    ap.add_argument("--skill", help="with --restore: limit to one skill")
    ap.add_argument("--from-root", metavar="ID_OR_PATH",
                    help="with --restore: take files from only this recorded root")
    ap.add_argument("--force", action="store_true", help="with --restore: overwrite differing live files")
    ap.add_argument("--root", action="append", metavar="PATH",
                    help="an extra acos family root; with --restore, redirect every file here")
    ap.add_argument("--label", help="override the snapshot label (default: UTC timestamp)")
    args = ap.parse_args()

    if args.roots:
        show_roots(args.root)
    elif args.list:
        list_snapshots()
    elif args.list_roots:
        m = load_manifest(args.list_roots)
        for rid, path in sorted(m["roots"].items(), key=lambda kv: kv[1]):
            n = sum(1 for f in m["files"] if f["root_id"] == rid)
            print(f"  {rid}  {n:>2} files  {path}")
    elif args.verify:
        sys.exit(verify(args.verify))
    elif args.restore:
        if not LABEL_RE.match(args.restore) and not (BACKUP_ROOT / args.restore).is_dir():
            sys.exit(f"unknown snapshot {args.restore!r}; run --list")
        into = args.root[-1] if args.root else None
        restore(args.restore, args.skill, args.force, into, args.from_root)
    else:
        snapshot(args.label, args.root)


if __name__ == "__main__":
    main()
