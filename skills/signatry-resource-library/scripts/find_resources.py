#!/usr/bin/env python3
"""Search The Signatry's resource library (Fact Sheets and Guides) by keyword,
category, or status, without loading the full catalog.csv into context.

Examples:
    python3 scripts/find_resources.py -k QCD
    python3 scripts/find_resources.py -k "business interest" --category Guide
    python3 scripts/find_resources.py -k crypto --status current
    python3 scripts/find_resources.py --topic "Designated Funds"
    python3 scripts/find_resources.py --needs-review
    python3 scripts/find_resources.py --list
"""
import argparse, csv, os, sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(SKILL_DIR, "catalog.csv")

SEARCH_COLUMNS = ["category", "topic", "summary", "talking_points"]


def load():
    if not os.path.exists(CATALOG):
        sys.exit(f"Catalog not found: {CATALOG}")
    with open(CATALOG, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def matches(row, keywords, mode):
    hay = " ".join(row.get(c, "") for c in SEARCH_COLUMNS).lower()
    hits = [k.lower() in hay for k in keywords]
    return all(hits) if mode == "all" else any(hits)


def main():
    p = argparse.ArgumentParser(description="Search the Signatry resource library.")
    p.add_argument("-k", "--keywords", nargs="+", default=[],
                   help="Match against category, topic, summary, and talking_points")
    p.add_argument("--topic", help="Exact or partial topic match")
    p.add_argument("--category", help="Filter to one category, e.g. Guide, Fact Sheet")
    p.add_argument("--status", choices=["current", "superseded", "needs-review", "pending-review"],
                   help="Filter to one status")
    p.add_argument("--needs-review", action="store_true",
                   help="Shortcut for --status needs-review (flag figures/eligibility rules before reuse)")
    p.add_argument("--source-type", choices=["sharepoint_pdf", "webpage"],
                   help="Filter to one source type")
    p.add_argument("--match", choices=["all", "any"], default="all",
                   help="Require all keywords (default) or any")
    p.add_argument("--exclude", nargs="+", default=[], help="Drop results containing these terms")
    p.add_argument("--output", choices=["table", "fetch-refs"], default="table",
                   help="table (default) or fetch-refs (just filename + driveId/itemId/webUrl, for live-fetch step)")
    p.add_argument("--limit", type=int)
    p.add_argument("--list", action="store_true", help="List every document's filename and topic, and exit")
    a = p.parse_args()

    rows = load()

    if a.list:
        print(f"{len(rows)} documents:\n")
        for r in sorted(rows, key=lambda r: r["topic"]):
            print(f"  [{r['status']:<15}] {r['topic']:<45} {r['filename']}")
        return

    if a.needs_review:
        a.status = "needs-review"
    if a.topic:
        rows = [r for r in rows if a.topic.lower() in r["topic"].lower()]
    if a.category:
        rows = [r for r in rows if r["category"].lower() == a.category.lower()]
    if a.status:
        rows = [r for r in rows if r["status"] == a.status]
    if a.source_type:
        rows = [r for r in rows if r["source_type"] == a.source_type]
    if a.keywords:
        rows = [r for r in rows if matches(r, a.keywords, a.match)]
    if a.exclude:
        rows = [r for r in rows if not matches(r, a.exclude, "any")]

    if not rows:
        print("No documents matched. Try --match any, fewer keywords, or --list to browse.")
        return

    if a.limit:
        rows = rows[:a.limit]

    if a.output == "fetch-refs":
        for r in rows:
            if r["source_type"] == "sharepoint_pdf":
                print(f"{r['filename']} | file:///{r['driveId']}/{r['itemId']}")
            else:
                print(f"{r['filename']} | {r['webUrl']}")
        return

    print(f"{len(rows)} document(s)\n")
    for r in rows:
        flag = " [NEEDS-REVIEW]" if r["status"] == "needs-review" else \
               " [superseded]" if r["status"] == "superseded" else \
               " [pending-review]" if r["status"] == "pending-review" else ""
        print(f"  {r['topic']}{flag}")
        print(f"    {r['filename']}  ({r['source_type']}, {r['version_or_date']})")
        print(f"    {r['summary'][:160]}")
        if r["related_docs"]:
            print(f"    related: {r['related_docs'][:100]}")
        print()


if __name__ == "__main__":
    main()
