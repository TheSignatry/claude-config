#!/usr/bin/env python3
"""Search The Signatry's icon library by keyword, name, or description.

Examples:
    python3 scripts/find_icons.py -k generosity
    python3 scripts/find_icons.py -k family giving --match any
    python3 scripts/find_icons.py --name Advisor --format png_512
    python3 scripts/find_icons.py -k stewardship --output paths --format svg
    python3 scripts/find_icons.py --list
"""
import argparse, csv, os, sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(SKILL_DIR, "assets", "icon_catalog.csv")

# Every baked format ships in Glacier only. SVG has no baked color at all —
# it recolors at use time via the root `color` attribute (see SKILL.md).
COLUMN = {
    "svg": "svg",
    "png_512": "png512_glacier",
}


def load():
    if not os.path.exists(CATALOG):
        sys.exit(f"Catalog not found: {CATALOG}")
    with open(CATALOG, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def matches(row, keywords, mode):
    hay = " ".join([row["stem"], row["name"], row["display_name"], row["description"]]).lower()
    hits = [k.lower() in hay for k in keywords]
    return all(hits) if mode == "all" else any(hits)


def main():
    p = argparse.ArgumentParser(description="Search the Signatry icon library.")
    p.add_argument("-k", "--keywords", nargs="+", default=[],
                   help="Match against name and description")
    p.add_argument("--name", help="Exact icon name, e.g. Advisor")
    p.add_argument("--match", choices=["all", "any"], default="all",
                   help="Require all keywords (default) or any")
    p.add_argument("--exclude", nargs="+", default=[], help="Drop results containing these terms")
    p.add_argument("--format", choices=["svg", "png_512"], default="svg",
                   help="Asset format to return (default: svg). png_512 is Glacier only.")
    p.add_argument("--output", choices=["table", "paths"], default="table")
    p.add_argument("--limit", type=int)
    p.add_argument("--list", action="store_true", help="List every icon name and exit")
    a = p.parse_args()

    rows = load()

    if a.list:
        print(f"{len(rows)} icons:\n")
        names = sorted(r["display_name"] for r in rows)
        for i in range(0, len(names), 4):
            print("  " + "".join(n.ljust(22) for n in names[i:i + 4]))
        return

    if a.name:
        rows = [r for r in rows if r["name"].lower() == a.name.lower()
                or r["display_name"].lower() == a.name.lower()]
    if a.keywords:
        rows = [r for r in rows if matches(r, a.keywords, a.match)]
    if a.exclude:
        rows = [r for r in rows if not matches(r, a.exclude, "any")]

    if not rows:
        print("No icons matched. Try --match any, fewer keywords, or --list to browse.")
        return

    if a.limit:
        rows = rows[:a.limit]

    col = COLUMN[a.format]

    if a.output == "paths":
        for r in rows:
            print(os.path.join(SKILL_DIR, r[col]))
        return

    width = max(len(r["display_name"]) for r in rows)
    print(f"{len(rows)} icon(s), format={a.format}"
          f"{'' if a.format == 'svg' else ' (Glacier)'}\n")
    for r in rows:
        print(f"  {r['display_name'].ljust(width)}  {r[col]}")
        print(f"  {' ' * width}  {r['description'][:96]}")


if __name__ == "__main__":
    main()
