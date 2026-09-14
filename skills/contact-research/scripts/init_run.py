#!/usr/bin/env python3
"""Initialize a contact_research run.

Usage:
  python init_run.py --input contacts.csv --run-dir state/ --naming 1 [--batch-size 10] [--run-id NAME]
  python init_run.py --input '[{"hs_object_id":"239596421482","firstname":"Paul","lastname":"Brown","email":"pabrown54@gmail.com"}]' --run-dir state/ --naming 2

Input columns (case-insensitive, flexible): Record ID / hs_object_id / Contact ID; First Name / firstname;
Last Name / lastname (or a single "Name" column); Email; Phone; Address/City/State/Zip; Contact Owner (optional).
Each row needs an ID, a name, and at least one of email / phone / address. Others go to rejected.csv with a reason.
"""
import argparse, json, os, sys, csv, re
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import (normalize_id, save_json, load_json, save_manifest, contact_path, now, recount, read_table)

ALIASES = {
    "hs_object_id": ["record id", "hs_object_id", "contact id", "hubspot contactid", "hubspot contact id", "id", "contactid"],
    "firstname": ["first name", "firstname", "first"],
    "lastname": ["last name", "lastname", "last"],
    "name": ["name", "full name", "contact name"],
    "email": ["email", "email address", "e-mail"],
    "phone": ["phone", "phone number", "mobile", "mobile phone", "mobilephone"],
    "address": ["address", "street address", "street"],
    "city": ["city"], "state": ["state", "state/region", "state region"], "zip": ["zip", "postal code", "zip code"],
    "owner": ["contact owner", "owner", "hubspot owner"],
}


def pick(row, key):
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for a in ALIASES[key]:
        if a in low and low[a] not in (None, ""):
            return str(low[a]).strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV/XLSX/JSON file path or inline JSON array")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--naming", type=int, choices=[1, 2, 3], default=None)
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--run-id", default=None)
    a = ap.parse_args()

    if a.input.strip().startswith("["):
        rows = json.loads(a.input)
    elif a.input.lower().endswith(".json"):
        rows = load_json(a.input)
    else:
        rows = read_table(a.input)

    os.makedirs(os.path.join(a.run_dir, "contacts"), exist_ok=True)
    os.makedirs(os.path.join(a.run_dir, "companies"), exist_ok=True)
    manifest = load_json(os.path.join(a.run_dir, "manifest.json")) or {
        "run_id": a.run_id or f"{now()[:10]}_contact_research",
        "created_at": now(), "naming_convention": a.naming, "batch_size": a.batch_size,
        "current_batch": 0, "navigation_mode": None,
        "counts": {"total": 0, "init": 0, "hubspot": 0, "researched": 0, "rendered": 0, "rejected": 0},
        "owners": {}, "notes": [],
    }
    if a.naming:
        manifest["naming_convention"] = a.naming
    manifest["batch_size"] = a.batch_size

    rejected, added, skipped = [], 0, 0
    for i, row in enumerate(rows, start=2):
        hid = normalize_id(pick(row, "hs_object_id"))
        first, last = pick(row, "firstname"), pick(row, "lastname")
        if not (first or last):
            nm = pick(row, "name")
            if nm:
                parts = nm.split()
                first, last = parts[0], " ".join(parts[1:]) or None
        email, phone = pick(row, "email"), pick(row, "phone")
        addr = ", ".join([p for p in [pick(row, "address"), pick(row, "city"), pick(row, "state"), pick(row, "zip")] if p]) or None

        reason = None
        if not hid:
            reason = "Missing or unusable HubSpot Contact ID (Excel scientific notation such as 2.44057E+11 must be re-exported as text)"
        elif not (first or last):
            reason = "Missing name"
        elif not (email or phone or addr):
            reason = "Needs at least one more data point (email, phone, or address)"
        if reason:
            rejected.append({"row": i, "id": pick(row, "hs_object_id"), "name": f"{first or ''} {last or ''}".strip(), "reason": reason})
            continue

        p = contact_path(a.run_dir, hid)
        if os.path.exists(p):
            skipped += 1
            continue
        ct = {
            "hs_object_id": hid,
            "input": {"firstname": first, "lastname": last, "email": email, "phone": phone, "address": addr,
                      "owner": pick(row, "owner"), "source_row": i},
            "hubspot": None, "associations": None, "activity": None, "derived": None, "research": None,
            "review": {"reviewed_by": None, "decision": None, "notes": None, "reviewed_at": None},
            "status": {"stages": {"init": now()}, "batch": None, "errors": []},
        }
        save_json(p, ct)
        added += 1

    # assign batches by insertion order
    ids = sorted([fn[:-5] for fn in os.listdir(os.path.join(a.run_dir, "contacts")) if fn.endswith(".json")],
                 key=lambda x: load_json(contact_path(a.run_dir, x))["status"]["stages"]["init"] + x)
    for n, hid in enumerate(ids):
        p = contact_path(a.run_dir, hid)
        ct = load_json(p)
        if ct["status"].get("batch") is None:
            ct["status"]["batch"] = n // a.batch_size
            save_json(p, ct)

    rej_path = os.path.join(a.run_dir, "rejected.csv")
    with open(rej_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row", "id", "name", "reason"])
        if f.tell() == 0:
            w.writeheader()
        for r in rejected:
            w.writerow(r)
    manifest["counts"]["rejected"] = manifest["counts"].get("rejected", 0) + len(rejected)
    save_manifest(a.run_dir, manifest)
    counts = recount(a.run_dir)
    print(json.dumps({"added": added, "skipped_existing": skipped, "rejected": len(rejected),
                      "counts": counts, "naming_convention": manifest["naming_convention"],
                      "batch_size": a.batch_size, "rejected_file": rej_path if rejected else None}, indent=2))
    if manifest["naming_convention"] is None:
        print("NOTE: no naming convention set. Ask the user (1/2/3) and pass --naming when rendering.", file=sys.stderr)


if __name__ == "__main__":
    main()
