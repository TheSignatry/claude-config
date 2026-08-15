#!/usr/bin/env python3
"""
Search The Signatry photo library.

Default output is one compact line per result — enough to shortlist. Use
--format full on the shortlist to see full descriptions and paths, and
--format previews to get small preview images for visual checking.

Examples:
    python3 find_photos.py --keywords family outdoor
    python3 find_photos.py --source stock                # all non-donor imagery
    python3 find_photos.py --family Roland
    python3 find_photos.py -k mountains --format full -n 3
    python3 find_photos.py -k mountains --format paths   # full-res, for builds
"""

import argparse
import csv
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(SKILL_DIR, "assets", "photo_catalog.csv")

# --source accepts these; "stock" is a convenience alias for everything
# that is not donor imagery (iStock + Unsplash).
SOURCE_CHOICES = ["donor", "stock", "istock", "unsplash"]


def load_catalog():
    if not os.path.exists(CATALOG):
        sys.exit(f"Catalog not found at {CATALOG}")
    with open(CATALOG, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["Absolute Path"] = os.path.join(SKILL_DIR, r["Relative Path"])
        r["Preview Path"] = os.path.join(
            SKILL_DIR, r["Relative Path"].replace("assets/photos/", "assets/previews/", 1)
        )
    return rows


def source_matches(row, want):
    actual = row["Source"].lower()
    if want == "stock":
        return actual != "donor"
    return actual == want


def matches(row, args):
    if args.family and row["Family"].lower() != args.family.lower():
        return False
    if args.source and not source_matches(row, args.source):
        return False
    if args.orientation and row["Orientation"].lower() != args.orientation.lower():
        return False
    if args.aspect and row["Aspect Ratio"] != args.aspect:
        return False
    if args.min_width and int(row["Width"]) < args.min_width:
        return False

    haystack = " ".join([
        row["Description"], row["Keywords"], row["File Name"],
        row["Family"], row["Source"], row["Dominant Colors"],
    ]).lower()

    if args.keywords:
        terms = [k.lower() for k in args.keywords]
        hits = [t for t in terms if t in haystack]
        if args.match == "all" and len(hits) != len(terms):
            return False
        if args.match == "any" and not hits:
            return False
    if args.exclude and any(x.lower() in haystack for x in args.exclude):
        return False
    return True


def score(row, keywords):
    """Rank by term frequency, weighting keyword-field hits above description hits."""
    if not keywords:
        return 0
    kw, desc = row["Keywords"].lower(), row["Description"].lower()
    return sum(3 * kw.count(k.lower()) + desc.count(k.lower()) for k in keywords)


def compact_line(r, kw_limit=6):
    tag = r["Family"] or r["Source"]
    kws = ", ".join([k.strip() for k in r["Keywords"].split(",")][:kw_limit])
    return (f"{r['Photo ID']} | {r['File Name']} | {tag} | "
            f"{r['Orientation'][:4]} {r['Width']}x{r['Height']} | {kws}")


def main():
    p = argparse.ArgumentParser(description="Search The Signatry photo library.")
    p.add_argument("--keywords", "-k", nargs="+", help="Terms matched across description, keywords, filename, colors")
    p.add_argument("--match", choices=["any", "all"], default="all", help="Require all terms (default) or any")
    p.add_argument("--exclude", "-x", nargs="+", help="Terms that disqualify a photo")
    p.add_argument("--family", "-f", help="Restrict to one donor family (Roland, Roberts, ...)")
    p.add_argument("--source", "-s", choices=SOURCE_CHOICES,
                   help="donor | stock (all non-donor) | istock | unsplash")
    p.add_argument("--orientation", "-o", choices=["landscape", "portrait", "square"])
    p.add_argument("--aspect", help="Exact aspect ratio, e.g. 3:2")
    p.add_argument("--min-width", type=int, help="Minimum pixel width")
    p.add_argument("--limit", "-n", type=int, default=20, help="Max results (default 20)")
    p.add_argument("--format", choices=["compact", "full", "paths", "previews", "csv"],
                   default="compact",
                   help="compact (default) | full | paths (full-res) | previews (small, for checking) | csv")
    p.add_argument("--list", "--folders", dest="listing", action="store_true",
                   help="List counts by source and family, then exit")
    args = p.parse_args()

    rows = load_catalog()

    if args.listing:
        src, fam = {}, {}
        for r in rows:
            src[r["Source"]] = src.get(r["Source"], 0) + 1
            if r["Family"]:
                fam[r["Family"]] = fam.get(r["Family"], 0) + 1
        print("By source:")
        for k, v in sorted(src.items(), key=lambda x: -x[1]):
            print(f"  {k:<12} {v}")
        print("By donor family:")
        for k, v in sorted(fam.items(), key=lambda x: -x[1]):
            print(f"  {k:<12} {v}")
        return

    results = [r for r in rows if matches(r, args)]
    results.sort(key=lambda r: -score(r, args.keywords or []))
    results = results[: args.limit]

    if not results:
        print("No matches. Try --match any, fewer terms, or --list to see what exists.")
        return

    if args.format == "paths":
        for r in results:
            print(r["Absolute Path"])
    elif args.format == "previews":
        for r in results:
            print(r["Preview Path"] if os.path.exists(r["Preview Path"]) else r["Absolute Path"])
    elif args.format == "csv":
        cols = [c for c in results[0] if c not in ("Absolute Path", "Preview Path")]
        w = csv.DictWriter(sys.stdout, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    elif args.format == "full":
        for r in results:
            tag = r["Family"] or r["Source"]
            print(f"\n{r['Photo ID']}  {r['File Name']}  [{tag}]")
            print(f"  {r['Orientation']} {r['Width']}x{r['Height']} ({r['Aspect Ratio']})  colors: {r['Dominant Colors']}")
            print(f"  {r['Description']}")
            print(f"  full: {r['Absolute Path']}")
            print(f"  preview: {r['Preview Path']}")
        print(f"\n{len(results)} shown.")
    else:
        for r in results:
            print(compact_line(r))
        print(f"-- {len(results)} of {len([x for x in rows if matches(x, args)])} matches "
              f"| --format full for detail, --format previews to view")


if __name__ == "__main__":
    main()
