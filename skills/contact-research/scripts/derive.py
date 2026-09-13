#!/usr/bin/env python3
"""Compute deterministic facts from the HubSpot blocks and write the `derived` block.

  python derive.py --run-dir state/ [--ids 1,2,3]

Derivations:
  email_handle / email_domain / is_corporate_domain
  identifiability_tier: placeholder | thin | standard
  record_source_event: cleaned-up hs_object_source_detail_1
  company classification: referral | role | household | unknown  (nonprofit rule; a company with type
    "Family" -- The Signatry's donor-household grouping convention, not an employer -- is always "household"
    and is excluded from role_companies)
  household_pair_candidate: same surname + same form + createdate within 120 s, checked against both the
    current batch and any associated contacts that carry a createdate
  spouse_in_hubspot: association label (Path A only) > shared "Family"-type company with exactly one other
    distinct person > household_pair_candidate, in that priority order
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
    roles, refs, household_companies = [], [], []
    for co in assoc.get("companies") or []:
        labels = {str(l).lower() for l in (co.get("labels") or [])}
        gid = str(co.get("give_recipient_id") or "").strip() or None
        co_type = (co.get("type") or "").strip().lower()
        if co_type == "family":
            cls = "household"
        elif (ref_gid and gid and ref_gid == gid) or (labels & REFERRAL_LABELS):
            cls = "referral"
        elif labels & ROLE_LABELS:
            cls = "role"
        elif ref_channel.lower() == "nonprofit partner" and co_type == "grant recipient":
            cls = "referral"
        else:
            cls = "unknown"
        co["classification"] = cls
        if cls == "referral":
            refs.append(co)
        elif cls == "household":
            household_companies.append(co)
        elif cls == "role":
            roles.append(co)
        else:
            roles.append(dict(co, note="association label not available – treat as unconfirmed role"))
    d["role_companies"] = [{"id": c["id"], "name": c.get("name"), "labels": c.get("labels", []), "note": c.get("note")} for c in roles]
    d["referral_company"] = "; ".join(f"{c.get('name')} (Give ID {c.get('give_recipient_id')}) – referral only; not a role" for c in refs) or None
    if ref_gid and not refs:
        d["referral_company"] = f"Give ID {ref_gid} (company not associated) – referral only"
    d["household_company"] = {"id": household_companies[0]["id"], "name": household_companies[0].get("name")} if household_companies else None

    # ---- household pair by form timing (checks the current batch, then any associated contact that carries a createdate)
    pair = assoc.get("household_pair_candidate") or {}
    if not pair.get("id"):
        my_ts = parse_ts(props.get("createdate"))
        my_src = props.get("hs_object_source_detail_1")
        best = None
        candidates = [(o["hs_object_id"], ((o.get("hubspot") or {}).get("properties")) or {}) for o in all_contacts
                      if o["hs_object_id"] != ct["hs_object_id"]]
        candidates += [(c["id"], c) for c in (assoc.get("contacts") or []) if c.get("createdate")]
        for oid, op in candidates:
            cand_last = op.get("lastname")
            if not cand_last and op.get("name"):
                cand_last = op["name"].split()[-1]
            if not last or (cand_last or "").strip().lower() != last.lower():
                continue
            if my_src and op.get("hs_object_source_detail_1") and op.get("hs_object_source_detail_1") != my_src:
                continue
            ots = parse_ts(op.get("createdate"))
            if my_ts and ots:
                gap = abs((my_ts - ots).total_seconds())
                if gap <= 120 and (best is None or gap < best[1]):
                    name = f"{op.get('firstname','')} {op.get('lastname','')}".strip() or op.get("name")
                    best = ({"id": oid, "name": name, "seconds_apart": int(gap)}, gap)
        if best:
            pair = best[0]
    assoc["household_pair_candidate"] = pair or {"id": None, "name": None, "seconds_apart": None}

    hh_members = assoc.get("household_members") or []
    distinct_others, seen_ids = [], set()
    for m in hh_members:
        if m.get("id") in seen_ids or m.get("id") == ct["hs_object_id"]:
            continue
        mname = (m.get("name") or "").strip().lower()
        if mname and mname == f"{first} {last}".strip().lower():
            continue  # likely a duplicate record of this same person, not a distinct household member
        seen_ids.add(m.get("id"))
        distinct_others.append(m)

    sp = assoc.get("spouse_in_hubspot") or {"id": None, "name": None, "evidence": "none"}
    if not sp.get("id"):
        for c in assoc.get("contacts") or []:
            if any(str(l).lower() in ("spouse", "partner", "husband", "wife") for l in c.get("labels") or []):
                sp = {"id": c["id"], "name": c.get("name"), "evidence": "association label"}
                break
        else:
            if d.get("household_company") and len(distinct_others) == 1:
                m = distinct_others[0]
                sp = {"id": m["id"], "name": m.get("name"),
                      "evidence": f"shared 'Family'-type company \"{d['household_company']['name']}\" – probable, not confirmed"}
            elif pair.get("id"):
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
    if d.get("household_company") and len(distinct_others) > 1:
        others = ", ".join(f"{m.get('name')} (ID {m.get('id')})" for m in distinct_others)
        flags.append(f"{len(distinct_others)} other people share the '{d['household_company']['name']}' household company ({others}) – relationship to each is ambiguous, review manually")
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
