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
                       screen_text, recount, model_policy_flag, signatry_insider)

CONF = {"High", "Moderate", "Low", "None"}
CORROBORATION = {"address", "city", "employer", "phone", "email_domain", "age_band"}


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)


def validate_research(frag, ct):
    errs = []
    mc = frag.get("match_confidence")
    if mc not in CONF:
        errs.append(f"match_confidence must be one of {sorted(CONF)}")
    if not frag.get("overview"):
        errs.append("overview is required")
    if "sources" not in frag or not isinstance(frag.get("sources"), list):
        errs.append("sources (list) is required")
    mdl = str(frag.get("model") or "").strip().lower()
    if not mdl or mdl in ("interactive", "unspecified", "none", "unknown", "n/a", "claude"):
        errs.append("model must be the exact model ID of the model that did the research (e.g. claude-fable-5-1) – it prints in the PDF footer")
    # household score and the household-research gate
    hh = frag.get("household") or {}
    hc = frag.get("household_confidence")
    if hc not in CONF:
        errs.append(f"household_confidence must be one of {sorted(CONF)} (use 'None' when no spouse or household member is known)")
    if hc in ("High", "Moderate") and not frag.get("sources"):
        errs.append("High/Moderate household_confidence requires at least one source")
    sc = hh.get("spouse_company") or {}
    if hc in ("Low", "None"):
        for k, v in sc.items():
            if isinstance(v, str) and v and not (v.startswith("Candidate") or v.startswith("N/A") or v.startswith("Not ")
                                                 or v.startswith("Likely") or v.startswith("Unknown")):
                errs.append(f"household.spouse_company.{k} must be prefixed 'Candidate only:' when household_confidence is {hc}: '{v[:40]}'")
    # a public source naming a spouse only supports High when it corroborates a HubSpot fact – same-name wedding pages are not enough
    ev = str((((ct.get("associations") or {}).get("spouse_in_hubspot") or {}).get("evidence")) or "").lower()
    if hc == "High" and hh.get("spouse_name") and "association label" not in ev:
        corr = [str(c).lower() for c in (hh.get("spouse_corroboration") or []) if str(c).lower() in CORROBORATION]
        if not corr:
            errs.append("household_confidence High requires household.spouse_corroboration: list the HubSpot fact(s) the public spouse "
                        f"source corroborates ({', '.join(sorted(CORROBORATION))}). A same-name wedding page or bio that matches no "
                        "HubSpot fact supports Moderate at most")
    spouse_known = hh.get("spouse_name") or (((ct.get("associations") or {}).get("spouse_in_hubspot") or {}).get("id"))
    if spouse_known and mc in ("Low", "None") and not sc.get("name"):
        errs.append("household research required: a spouse/household member is known but the contact is Low/None – research the spouse's "
                    "employer, role, and ownership and set household.spouse_company.name (or 'Not found – <what was tried>')")
    if mc in ("High", "Moderate") and not frag.get("sources"):
        errs.append("High/Moderate confidence requires at least one source")
    if "deceased_per_public_source" in frag and not isinstance(frag.get("deceased_per_public_source"), (bool, type(None))):
        errs.append("deceased_per_public_source must be true, false, or null (record only the fact and date of death, never the cause)")
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
        _, hit = screen_text(s, lexicon=False)  # patterns only: research prose legitimately says "medical device" or "Terminal Ave"
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
        errs = validate_research(frag, ct)
        if errs:
            print(json.dumps({"ok": False, "errors": errs}, indent=2))
            sys.exit(2)
    if a.stage == "activity":
        insider = signatry_insider((ct.get("hubspot") or {}).get("properties"), ct.get("associations"))
        red, board_red = 0, 0
        for k in ("notes", "emails", "calls", "meetings", "tasks", "tickets"):
            for e in frag.get(k) or []:
                for fld in ("body", "subject", "title"):
                    if e.get(fld):
                        clean, hit = screen_text(e[fld], insider=bool(insider))
                        if hit:
                            e[fld] = clean
                            red += 1
                            if hit.startswith("board:"):
                                board_red += 1
        frag["redactions"] = frag.get("redactions", 0) + red
        if red:
            ct["status"]["errors"].append(f"{red} engagement field(s) redacted as possible Restricted content – report to Technology Team (IT14 Policy 10)")
        if board_red:
            ct["status"]["errors"].append(f"{board_red} engagement field(s) redacted as possible Board Confidential content (Signatry {insider} record, IT15) – report to Technology Team (IT14 Policy 10)")
        n = sum(len(frag.get(k) or []) for k in ("notes", "emails", "calls", "meetings", "tasks", "tickets"))
        frag.setdefault("summary", f"{n} activities." if n else "0 activities. No notes, emails, calls, meetings, tasks, or tickets logged.")

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
        pol = model_policy_flag(frag.get("model"), (ct.get("derived") or {}).get("identifiability_tier"))
        if pol:
            flags = [f for f in (frag.get("data_quality_flags") or []) if not str(f).startswith("Researched by an off-policy model")]
            frag["data_quality_flags"] = flags + [pol]
            print(f"WARNING: {pol}", file=sys.stderr)
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
