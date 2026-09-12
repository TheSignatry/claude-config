#!/usr/bin/env python3
"""Merge a JSON fragment into a contact's state file, with validation.

  python merge_state.py --run-dir state/ --id 239596421482 --stage hubspot --json '{"properties": {...}}'
  python merge_state.py --run-dir state/ --id 239596421482 --stage research --file /tmp/research_239596421482.json
  python merge_state.py --run-dir state/ --id 239596421482 --stage review --json '{"decision":"accept","reviewed_by":"D. Armstrong"}'

Stages: hubspot | associations | activity | research | review | company (writes state/companies/<slug>.json)
Validation (research stage):
  - match_confidence in {High, Moderate, Low, None}; overview and sources present
  - High/Moderate require >=1 source; Low/None require "Candidate only:" prefixes on non-null identity/company strings
  - overview/notes must not contain characterization language; no Restricted-data patterns anywhere
Exit code 2 on validation failure (nothing written).
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import (load_json, save_json, contact_path, now, valid_id, contains_characterization,
                       screen_text, recount)

CONF = {"High", "Moderate", "Low", "None"}


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)


def validate_research(frag):
    errs = []
    mc = frag.get("match_confidence")
    if mc not in CONF:
        errs.append(f"match_confidence must be one of {sorted(CONF)}")
    if not frag.get("overview"):
        errs.append("overview is required")
    if "sources" not in frag or not isinstance(frag.get("sources"), list):
        errs.append("sources (list) is required")
    if mc in ("High", "Moderate") and not frag.get("sources"):
        errs.append("High/Moderate confidence requires at least one source")
    if mc in ("Low", "None"):
        for blk in ("identity", "company"):
            for k, v in (frag.get(blk) or {}).items():
                if isinstance(v, str) and v and not (v.startswith("Candidate") or v.startswith("N/A") or v.startswith("Not ")
                                                     or v.startswith("Likely") or v.startswith("Unknown")):
                    errs.append(f"{blk}.{k} must be prefixed 'Candidate only:' when confidence is {mc}: '{v[:40]}'")
    for fld in ("overview", "notes", "confidence_rationale"):
        w = contains_characterization(frag.get(fld))
        if w:
            errs.append(f"{fld} contains characterization language ('{w}') – report facts only")
    for s in walk_strings(frag):
        _, hit = screen_text(s)
        if hit and not s.startswith("[redacted"):
            errs.append(f"possible Restricted data ({hit}) in research fragment – remove it")
            break
    for src in frag.get("sources") or []:
        if not isinstance(src, dict) or not str(src.get("url", "")).startswith("http"):
            errs.append("each source needs an http(s) url")
            break
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--id", required=False)
    ap.add_argument("--stage", required=True, choices=["hubspot", "associations", "activity", "research", "review", "company"])
    ap.add_argument("--json", help="inline JSON fragment")
    ap.add_argument("--file", help="path to JSON fragment")
    ap.add_argument("--force", action="store_true", help="skip validation (logs a warning into status.errors)")
    a = ap.parse_args()

    if not (a.json or a.file):
        sys.exit("Provide --json or --file")
    frag = json.loads(a.json) if a.json else load_json(a.file)

    if a.stage == "company":
        slug = frag.get("slug") or frag.get("domain") or frag.get("name")
        if not slug:
            sys.exit("company fragment needs slug/domain/name")
        slug = slug.lower().replace(" ", "_")
        p = os.path.join(a.run_dir, "companies", f"{slug}.json")
        existing = load_json(p) or {"slug": slug, "used_by": []}
        existing.update({k: v for k, v in frag.items() if k != "used_by"})
        existing["used_by"] = sorted(set(existing.get("used_by", []) + frag.get("used_by", [])))
        existing["researched_at"] = existing.get("researched_at") or now()
        save_json(p, existing)
        print(json.dumps({"written": p}))
        return

    if not a.id or not valid_id(a.id):
        sys.exit("--id must be an all-digit HubSpot Contact ID")
    p = contact_path(a.run_dir, a.id)
    ct = load_json(p)
    if ct is None:
        sys.exit(f"No state for {a.id}; run init_run.py first")

    if a.stage == "research" and not a.force:
        errs = validate_research(frag)
        if errs:
            print(json.dumps({"ok": False, "errors": errs}, indent=2))
            sys.exit(2)
    if a.stage == "activity":
        red = 0
        for k in ("notes", "emails", "calls", "meetings", "tasks"):
            for e in frag.get(k) or []:
                for fld in ("body", "subject", "title"):
                    if e.get(fld):
                        clean, hit = screen_text(e[fld])
                        if hit:
                            e[fld] = clean
                            red += 1
        frag["redactions"] = frag.get("redactions", 0) + red
        if red:
            ct["status"]["errors"].append(f"{red} engagement field(s) redacted as possible Restricted content – report to Technology Team (IT14 Policy 10)")
        n = sum(len(frag.get(k) or []) for k in ("notes", "emails", "calls", "meetings", "tasks"))
        frag.setdefault("summary", f"{n} activities." if n else "0 activities. No notes, emails, calls, meetings, or tasks logged.")

    if a.stage == "hubspot":
        frag.setdefault("pulled_at", now())
        # keep lastname/firstname from HubSpot authoritative, but never blank them out
        props = frag.get("properties") or {}
        for k in ("firstname", "lastname", "email"):
            if not props.get(k) and ct["input"].get(k):
                props[k] = ct["input"][k]
        frag["properties"] = props
    if a.stage == "research":
        frag.setdefault("researched_at", now())
        frag.setdefault("navigation", "unspecified")
    if a.stage == "review":
        frag.setdefault("reviewed_at", now())
        ct["review"].update(frag)
    else:
        existing = ct.get(a.stage) or {}
        if isinstance(existing, dict):
            existing.update(frag)
            ct[a.stage] = existing
        else:
            ct[a.stage] = frag
        ct["status"]["stages"][a.stage] = now()
    if a.force:
        ct["status"]["errors"].append(f"{a.stage} merged with --force (validation skipped) at {now()}")
    save_json(p, ct)
    recount(a.run_dir)
    print(json.dumps({"ok": True, "id": a.id, "stage": a.stage, "written": p}))


if __name__ == "__main__":
    main()
