#!/usr/bin/env python3
"""Batch orchestration for a contact_research run.

  python batch.py --run-dir state/ status              # counts by stage and batch
  python batch.py --run-dir state/ next [--stage research] [--limit N]
                                                       # IDs in the current batch still needing <stage>
  python batch.py --run-dir state/ advance             # move to the next batch once current is researched
  python batch.py --run-dir state/ pending --stage hubspot   # all IDs across batches missing a stage
  python batch.py --run-dir state/ set-batch-size 20   # re-chunk unresearched contacts

Why batches: the HubSpot connector, HubSpot API, and web search are all rate-limited, and a long run can be
interrupted. Working a batch at a time (default 10) keeps any failure small and makes 'resume' trivial – state
files already record which stages are complete.
"""
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import list_contacts, load_manifest, save_manifest, recount, contact_path, load_json, save_json

ORDER = ["init", "hubspot", "derived", "research", "rendered"]


def needs(ct, stage):
    st = ct["status"]["stages"]
    return not st.get(stage)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("cmd", choices=["status", "next", "advance", "pending", "set-batch-size"])
    ap.add_argument("--stage", default="research", choices=["hubspot", "derived", "research", "rendered"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("value", nargs="?")
    a = ap.parse_args()

    m = load_manifest(a.run_dir)
    cs = list_contacts(a.run_dir)
    counts = recount(a.run_dir)

    if a.cmd == "status":
        by_batch = {}
        for ct in cs:
            b = ct["status"].get("batch")
            row = by_batch.setdefault(b, {"total": 0, "hubspot": 0, "derived": 0, "research": 0, "rendered": 0, "errors": 0})
            row["total"] += 1
            for s in ("hubspot", "derived", "research", "rendered"):
                row[s] += 0 if needs(ct, s) else 1
            row["errors"] += len(ct["status"].get("errors") or [])
        print(json.dumps({"run_id": m["run_id"], "current_batch": m["current_batch"], "batch_size": m["batch_size"],
                          "naming_convention": m["naming_convention"], "counts": counts,
                          "batches": {str(k): v for k, v in sorted(by_batch.items(), key=lambda x: (x[0] is None, x[0]))}}, indent=2))
        return

    if a.cmd == "set-batch-size":
        size = int(a.value)
        m["batch_size"] = size
        i = 0
        for ct in cs:
            if needs(ct, "research"):
                ct["status"]["batch"] = m["current_batch"] + i // size
                save_json(contact_path(a.run_dir, ct["hs_object_id"]), ct)
                i += 1
        save_manifest(a.run_dir, m)
        print(f"batch size set to {size}; {i} unresearched contacts re-chunked")
        return

    if a.cmd in ("next", "pending"):
        pool = [ct for ct in cs if needs(ct, a.stage) and (a.cmd == "pending" or ct["status"].get("batch") == m["current_batch"])]
        # research requires derived; derived requires hubspot
        if a.stage == "research":
            pool = [ct for ct in pool if not needs(ct, "derived")]
        if a.stage == "derived":
            pool = [ct for ct in pool if not needs(ct, "hubspot")]
        if a.limit:
            pool = pool[:a.limit]
        out = []
        for ct in pool:
            p = ct.get("hubspot", {}) or {}
            props = p.get("properties", {}) if isinstance(p, dict) else {}
            out.append({"id": ct["hs_object_id"], "name": f"{props.get('firstname') or ct['input'].get('firstname') or ''} "
                                                          f"{props.get('lastname') or ct['input'].get('lastname') or ''}".strip(),
                        "tier": (ct.get("derived") or {}).get("identifiability_tier"),
                        "batch": ct["status"].get("batch"), "file": contact_path(a.run_dir, ct["hs_object_id"])})
        print(json.dumps({"stage": a.stage, "current_batch": m["current_batch"], "count": len(out), "contacts": out}, indent=2))
        return

    if a.cmd == "advance":
        cur = [ct for ct in cs if ct["status"].get("batch") == m["current_batch"]]
        remaining = [ct["hs_object_id"] for ct in cur if needs(ct, "research")]
        if remaining:
            print(json.dumps({"advanced": False, "current_batch": m["current_batch"], "still_unresearched": remaining}, indent=2))
            sys.exit(1)
        m["current_batch"] += 1
        save_manifest(a.run_dir, m)
        nxt = [ct["hs_object_id"] for ct in cs if ct["status"].get("batch") == m["current_batch"]]
        print(json.dumps({"advanced": True, "current_batch": m["current_batch"], "contacts_in_batch": nxt}, indent=2))


if __name__ == "__main__":
    main()
