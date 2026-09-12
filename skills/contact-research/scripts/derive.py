#!/usr/bin/env python3
"""Compute deterministic facts from the HubSpot blocks and write the `derived` block.

  python derive.py --run-dir state/ [--ids 1,2,3]

Derivations:
  email_handle / email_domain / is_corporate_domain
  identifiability_tier: placeholder | thin | standard
  record_source_event: cleaned-up hs_object_source_detail_1
  company classification: referral | role | unknown  (nonprofit rule)
  household_pair_candidate: same surname + same form + createdate within 120 s (needs other contacts in the run)
  data_quality_flags: ZIP/state mismatch heuristics, placeholder names, duplicate-name records, referral-as-company
"""
import argparse, os, sys, re, datetime
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import (list_contacts, contact_path, load_json, save_json, now, ROLE_LABELS, REFERRAL_LABELS,
                       PLACEHOLDER_FIRSTNAMES, recount)

FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "msn.com",
             "live.com", "me.com", "comcast.net", "att.net", "sbcglobal.net", "protonmail.com", "mac.com"}

ZIP_STATE_PREFIX = {  # first digit(s) of ZIP -> plausible states (coarse sanity check only)
    "TN": ("37", "38"), "TX": ("75", "76", "77", "78", "79", "73"), "IA": ("50", "51", "52"),
    "NE": ("68", "69"), "MN": ("55", "56"), "IL": ("60", "61", "62"), "KS": ("66", "67"), "MO": ("63", "64", "65"),
}


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def clean_event(detail):
    if not detail:
        return None
    d = re.sub(r"\s*-\s*Event Registration Form.*$", "", detail)
    d = re.sub(r"\s*\(SimpleEvents\.io\)", "", d)
    return d.replace(" - ", " ").strip() or detail


def derive_one(ct, all_contacts):
    props = ((ct.get("hubspot") or {}).get("properties")) or {}
    inp = ct.get("input") or {}
    assoc = ct.get("associations") or {}
    d = {}

    first = (props.get("firstname") or inp.get("firstname") or "").strip()
    last = (props.get("lastname") or inp.get("lastname") or "").strip()
    email = (props.get("email") or inp.get("email") or "").strip().lower()
    handle, domain = (email.split("@") + [""])[:2] if email else ("", "")
    d["email_handle"] = handle or None
    d["email_domain"] = domain or None
    d["is_corporate_domain"] = bool(domain) and domain not in FREE_MAIL

    has_locator = any([email, props.get("phone"), props.get("mobilephone"), props.get("address"), props.get("city"),
                       inp.get("phone"), inp.get("address")])
    if first.lower() in PLACEHOLDER_FIRSTNAMES:
        tier = "placeholder"
    elif not has_locator:
        tier = "thin"
    else:
        tier = "standard"
    d["identifiability_tier"] = tier
    d["record_source_event"] = clean_event(props.get("hs_object_source_detail_1"))

    # ---- company classification (nonprofit rule)
    ref_gid = str(props.get("referral_company_give_id") or "").strip() or None
    ref_channel = (props.get("referral_channel") or "").strip()
    roles, refs = [], []
    for co in assoc.get("companies") or []:
        labels = {str(l).lower() for l in (co.get("labels") or [])}
        gid = str(co.get("give_recipient_id") or "").strip() or None
        if (ref_gid and gid and ref_gid == gid) or (labels & REFERRAL_LABELS):
            cls = "referral"
        elif labels & ROLE_LABELS:
            cls = "role"
        elif ref_channel.lower() == "nonprofit partner" and (co.get("type") or "").lower() == "grant recipient":
            cls = "referral"
        else:
            cls = "unknown"
        co["classification"] = cls
        (refs if cls == "referral" else roles if cls == "role" else roles).append(co) if cls != "unknown" else None
        if cls == "unknown":
            roles.append(dict(co, note="association label not available – treat as unconfirmed role"))
    d["role_companies"] = [{"id": c["id"], "name": c.get("name"), "labels": c.get("labels", []), "note": c.get("note")} for c in roles]
    d["referral_company"] = "; ".join(f"{c.get('name')} (Give ID {c.get('give_recipient_id')}) – referral only; not a role" for c in refs) or None
    if ref_gid and not refs:
        d["referral_company"] = f"Give ID {ref_gid} (company not associated) – referral only"

    # ---- household pair by form timing
    pair = assoc.get("household_pair_candidate") or {}
    if not pair.get("id"):
        my_ts = parse_ts(props.get("createdate"))
        my_src = props.get("hs_object_source_detail_1")
        best = None
        for o in all_contacts:
            if o["hs_object_id"] == ct["hs_object_id"]:
                continue
            op = ((o.get("hubspot") or {}).get("properties")) or {}
            if (op.get("lastname") or "").strip().lower() != last.lower() or not last:
                continue
            if my_src and op.get("hs_object_source_detail_1") != my_src:
                continue
            ots = parse_ts(op.get("createdate"))
            if my_ts and ots:
                gap = abs((my_ts - ots).total_seconds())
                if gap <= 120 and (best is None or gap < best[1]):
                    best = (o, gap)
        if best:
            o, gap = best
            op = o["hubspot"]["properties"]
            pair = {"id": o["hs_object_id"], "name": f"{op.get('firstname','')} {op.get('lastname','')}".strip(), "seconds_apart": int(gap)}
    assoc["household_pair_candidate"] = pair or {"id": None, "name": None, "seconds_apart": None}
    sp = assoc.get("spouse_in_hubspot") or {"id": None, "name": None, "evidence": "none"}
    if not sp.get("id"):
        for c in assoc.get("contacts") or []:
            if any(str(l).lower() in ("spouse", "partner", "husband", "wife") for l in c.get("labels") or []):
                sp = {"id": c["id"], "name": c.get("name"), "evidence": "association label"}
                break
        else:
            if pair.get("id"):
                sp = {"id": pair["id"], "name": pair["name"], "evidence": "household pair (same form, registrant + guest) – probable, not confirmed"}
    assoc["spouse_in_hubspot"] = sp
    ct["associations"] = assoc

    # ---- flags
    flags = []
    if tier == "placeholder":
        flags.append(f"Placeholder first name '{first}' – replace with the real name")
    st, zp = (props.get("state") or "").upper(), str(props.get("zip") or "")
    if st in ZIP_STATE_PREFIX and zp and not zp.startswith(ZIP_STATE_PREFIX[st]):
        flags.append(f"ZIP {zp} is not typical for state {st} – verify address")
    if refs:
        flags.append("Referral-only nonprofit association was stored as the associated company – removed from company/role columns")
    dup = [m for m in (assoc.get("surname_matches") or []) if (m.get("firstname") or "").lower() == first.lower() and m.get("id") != ct["hs_object_id"]]
    if dup:
        flags.append(f"{len(dup)} other HubSpot record(s) named {first} {last} with different emails (IDs {', '.join(m['id'] for m in dup)}) – review for duplicates")
    if pair.get("id"):
        flags.append(f"Probable household pair with {pair['name']} (ID {pair['id']}, created {pair['seconds_apart']} s apart) – no association recorded")
    if (ct.get("activity") or {}).get("redactions"):
        flags.append("Engagement text redacted as possible Restricted content – report to Technology Team (IT14 Policy 10)")
    d["data_quality_flags"] = flags
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--ids", default=None)
    a = ap.parse_args()
    all_c = list_contacts(a.run_dir)
    want = set(a.ids.split(",")) if a.ids else None
    n = 0
    for ct in all_c:
        if want and ct["hs_object_id"] not in want:
            continue
        if not ct.get("hubspot"):
            print(f"skip {ct['hs_object_id']}: no hubspot block yet", file=sys.stderr)
            continue
        ct["derived"] = derive_one(ct, all_c)
        ct["status"]["stages"]["derived"] = now()
        save_json(contact_path(a.run_dir, ct["hs_object_id"]), ct)
        n += 1
        print(f"{ct['hs_object_id']}: tier={ct['derived']['identifiability_tier']} handle={ct['derived']['email_handle']} "
              f"referral={bool(ct['derived']['referral_company'])} flags={len(ct['derived']['data_quality_flags'])}")
    recount(a.run_dir)
    print(f"derived {n} contact(s)")


if __name__ == "__main__":
    main()
