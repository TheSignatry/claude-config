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
  duplicate_candidates: other HubSpot records with the same first + last name, gathered from the surname search,
    contact associations, and household-company members (so a duplicate is caught even when one source is empty)
  daf: fund_count (associated Fund records), fund_balance_sum (sum of each Fund's current_balance), tier
    (contact.direct_fund_balance_tier_min, passed through as-is)
  fund_roles / role_on_fund: from the Fund association labels ("Fund Holder - …", "Financial Advisor - …",
    "Grant Advisor - …") – holder | advisor | other | null; advisor-only contacts are flagged as professional
    advisers rather than donors
  signatry_relationship: staff | board | null (Signatry email domain or a Signatry-named company association
    with an employment or board label) – switches on the Board Confidential engagement screen
  is_vanity_domain: the email domain is the contact's own surname (thewilsoncrew.com, sollazzo.org) – personal
  data_quality_flags: ZIP/state mismatch heuristics, placeholder names, duplicate-name records, referral-as-company
"""
import argparse, os, sys, re, datetime
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import (list_contacts, contact_path, load_json, save_json, now, ROLE_LABELS, REFERRAL_LABELS,
                       PLACEHOLDER_FIRSTNAMES, PERSONAL_DOMAINS, recount, signatry_insider)


def is_vanity_domain(domain, last):
    """thewilsoncrew.com, sollazzo.org, mulcrone.net: the registrable label is the surname, optionally wrapped in
    'the…', '…family', '…crew', '…s'. A firm named after its founder (wilsonlaw.com) is deliberately NOT vanity."""
    if not domain or not last or len(last) < 3:
        return False
    sld = domain.split(".")[0].lower()
    return re.fullmatch(rf"(?:the)?{re.escape(last.lower())}(?:s|family|crew|household|home|clan|fam)?", sld) is not None

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
    d["is_vanity_domain"] = is_vanity_domain(domain, last)
    d["is_corporate_domain"] = bool(domain) and domain not in PERSONAL_DOMAINS and not d["is_vanity_domain"]
    d["signatry_relationship"] = signatry_insider(props, assoc)

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

    # ---- DAF (fund count, balance sum, tier)
    funds = assoc.get("funds") or []
    d["daf"] = {"fund_count": len(funds),
                "fund_balance_sum": sum(f["current_balance"] for f in funds if f.get("current_balance") is not None),
                "tier": props.get("direct_fund_balance_tier_min")}
    # role on the associated funds, from the association label prefix ("Fund Holder - Full Access", "Financial Advisor - Read Only")
    fund_roles = set()
    for f in funds:
        for l in f.get("labels") or []:
            head = str(l).split(" - ")[0].strip().lower()
            fund_roles.add("holder" if head.startswith("fund holder") else "advisor" if head.endswith("advisor") else "other")
    d["fund_roles"] = sorted(fund_roles)
    d["role_on_fund"] = "holder" if "holder" in fund_roles else "advisor" if "advisor" in fund_roles else "other" if fund_roles else None

    # ---- household pair by form timing (checks the current batch, then any associated contact that carries a createdate)
    # Skipped for IMPORT-sourced records: two rows of the same import file land seconds apart regardless of any
    # household link, and bulk runs produced dozens of false pairs (fathers, brothers, colleagues) from that.
    pair = assoc.get("household_pair_candidate") or {}
    imported = (props.get("hs_object_source_label") or "").upper() == "IMPORT"
    if imported:
        pair = {}  # also clears a pair computed by an earlier version on re-derive
    if not pair.get("id") and not imported:
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

    # ---- possible duplicate records: same first + last name under a different HubSpot ID, from any source Step 2 pulled
    me = f"{first} {last}".strip().lower()
    dups, seen_dup = [], {}

    def _dup(rec_id, name, email, email_domain, city, state, via):
        rec_id = str(rec_id) if rec_id is not None else None
        if not me or not rec_id or rec_id == ct["hs_object_id"] or (name or "").strip().lower() != me:
            return
        if rec_id in seen_dup:
            if via not in seen_dup[rec_id]["seen_in"]:
                seen_dup[rec_id]["seen_in"].append(via)
            return
        seen_dup[rec_id] = {"id": rec_id, "name": name, "email": email, "email_domain": email_domain,
                            "city": city, "state": state, "seen_in": [via]}
        dups.append(seen_dup[rec_id])

    for m in assoc.get("surname_matches") or []:
        _dup(m.get("id"), f"{m.get('firstname') or ''} {last}".strip(), None, m.get("email_domain"), m.get("city"), m.get("state"), "surname search")
    for c in assoc.get("contacts") or []:
        _dup(c.get("id"), c.get("name"), c.get("email"), None, c.get("city"), c.get("state"), "contact association")
    for m in hh_members:
        _dup(m.get("id"), m.get("name"), m.get("email"), None, None, None, "household company")
    d["duplicate_candidates"] = dups

    # ---- flags
    flags = []
    missing = [k for k in ("contacts", "surname_matches", "companies") if k not in assoc]
    if missing:
        flags.append(f"Step 2 incomplete – associations block is missing {', '.join(missing)}; finish the connector pull (hubspot_extraction.md Path B steps 2–5) before research")
    if tier == "placeholder":
        flags.append(f"Placeholder first name '{first}' – replace with the real name")
    st, zp = (props.get("state") or "").upper(), str(props.get("zip") or "")
    if st in ZIP_STATE_PREFIX and zp and not zp.startswith(ZIP_STATE_PREFIX[st]):
        flags.append(f"ZIP {zp} is not typical for state {st} – verify address")
    if refs:
        flags.append("Referral-only nonprofit association was stored as the associated company – removed from company/role columns")
    if dups:
        flags.append(f"{len(dups)} other HubSpot record(s) named {first} {last} (IDs {', '.join(x['id'] for x in dups)}) – review for duplicates")
    if pair.get("id"):
        if sp.get("evidence") == "association label" and str(sp.get("id")) == str(pair["id"]):
            pass  # the pair is the labeled spouse; nothing to flag
        elif sp.get("evidence") == "association label":
            flags.append(f"Probable household pair with {pair['name']} (ID {pair['id']}, created {pair['seconds_apart']} s apart) differs from the labeled spouse {sp.get('name')} (ID {sp.get('id')}) – probably a relative or import artifact")
        else:
            flags.append(f"Probable household pair with {pair['name']} (ID {pair['id']}, created {pair['seconds_apart']} s apart) – no association recorded")
    if d["role_on_fund"] == "advisor":
        flags.append("Associated to Fund records only as Financial Advisor / Grant Advisor – likely a professional adviser on a client's fund, not a donor")
    if d["signatry_relationship"]:
        flags.append(f"Signatry {d['signatry_relationship']} record – Board Confidential screen applied to engagement text (IT15); public research limited to the Signatry role")
    if d["is_vanity_domain"]:
        flags.append(f"Email domain {domain} is a personal/family domain (matches the surname) – not an employer")
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
