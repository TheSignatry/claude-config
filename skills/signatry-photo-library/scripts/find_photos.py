#!/usr/bin/env python3
"""
Search The Signatry photo library.

Prints matching photos with their absolute paths, ready to hand to pptxgenjs,
python-docx, or WeasyPrint. Run with no filters to see the whole library.

Examples:
    python3 find_photos.py --keywords family outdoor
    python3 find_photos.py --folder Roland --orientation landscape
    python3 find_photos.py --keywords "site plan" --format paths
    python3 find_photos.py --folders
"""

import argparse
import csv
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(SKILL_DIR, "assets", "photo_catalog.csv")


def load_catalog():
    if not os.path.exists(CATALOG):
        sys.exit(f"Catalog not found at {CATALOG}")
    with open(CATALOG, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["Absolute Path"] = os.path.join(SKILL_DIR, r["Relative Path"])
    return rows


def matches(row, args):
    if args.family and row["Family"].lower() != args.family.lower():
        return False
    if args.source and row["Source"].lower() != args.source.lower():
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
    if args.exclude:
        if any(x.lower() in haystack for x in args.exclude):
            return False
    return True


def score(row, keywords):
    """Rank by how often the search terms appear, weighting keyword-field hits."""
    if not keywords:
        return 0
    kw = row["Keywords"].lower()
    desc = row["Description"].lower()
    return sum(3 * kw.count(k.lower()) + desc.count(k.lower()) for k in keywords)


def main():
    p = argparse.ArgumentParser(description="Search The Signatry photo library.")
    p.add_argument("--keywords", "-k", nargs="+", help="Terms to search across description, keywords, filename, colors")
    p.add_argument("--match", choices=["any", "all"], default="all", help="Require all terms (default) or any")
    p.add_argument("--exclude", "-x", nargs="+", help="Terms that disqualify a photo")
    p.add_argument("--family", "-f", help="Restrict to one donor family (Roland, Roberts, ...)")
    p.add_argument("--source", "-s", choices=["donor", "istock", "unsplash"], help="Restrict by image source")
    p.add_argument("--orientation", "-o", choices=["landscape", "portrait", "square"])
    p.add_argument("--aspect", help="Exact aspect ratio, e.g. 3:2")
    p.add_argument("--min-width", type=int, help="Minimum pixel width")
    p.add_argument("--limit", "-n", type=int, default=20, help="Max results (default 20)")
    p.add_argument("--format", choices=["table", "paths", "csv"], default="table")
    p.add_argument("--folders", "--list", action="store_true", help="List families/sources with photo counts and exit")
    args = p.parse_args()

    rows = load_catalog()

    if args.folders:
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
        print("No photos matched. Try --match any, fewer terms, or --folders to see what exists.")
        return

    if args.format == "paths":
        for r in results:
            print(r["Absolute Path"])
    elif args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    else:
        for r in results:
            tag = r["Family"] if r["Family"] else r["Source"]
            print(f"\n{r['Photo ID']}  {r['File Name']}  [{tag}]")
            print(f"  {r['Orientation']} {r['Width']}x{r['Height']} ({r['Aspect Ratio']})  colors: {r['Dominant Colors']}")
            print(f"  {r['Description']}")
            print(f"  path: {r['Absolute Path']}")
        print(f"\n{len(results)} shown.")


if __name__ == "__main__":
    main()
