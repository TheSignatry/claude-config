#!/usr/bin/env python3
"""Pull HubSpot data for contacts in a run via the HubSpot REST API (Private App token in HUBSPOT_TOKEN).

  export HUBSPOT_TOKEN=pat-na1-...
  python hubspot_pull.py --run-dir state/ [--batch N | --ids 1,2,3] [--sleep 0.15]

Writes the hubspot / associations / activity blocks (with redaction screen) and then runs derive.py logic.
If HUBSPOT_TOKEN is not set, prints the connector-path instructions from references/hubspot_extraction.md and exits 3.

Requires: requests (pip install requests --break-system-packages)
"""
import argparse, os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import (list_contacts, load_manifest, save_manifest, contact_path, load_json, save_json, now,
                       screen_text, recount)

BASE = "https://api.hubapi.com"
PROPS = ["firstname", "lastname", "salutation", "email", "phone", "mobilephone", "address", "street_address_2", "city",
         "state", "zip", "country", "jobtitle", "company", "hs_linkedin_url", "twitterhandle", "marital_status",
         "lifecyclestage", "hs_lead_status", "hubspot_owner_id", "createdate", "relationship_start_date",
         "hs_object_source_label", "hs_object_source_detail_1", "hs_object_source_detail_2", "hs_analytics_source",
         "hs_latest_source", "referral_channel", "referral_company_give_id", "daf_application_referrer_name",
         "daf_application_referral_type", "num_notes", "notes_last_updated", "hs_last_sales_activity_type",
         "guest_first_name", "guest_last_name", "guest_email", "associatedcompanyid", "direct_fund_balance_tier_min"]
COMPANY_PROPS = ["name", "domain", "type", "give_recipient_id", "city", "state"]
FUND_OBJECT = "2-24861263"  # custom object "Fund" (object-type ID); associated to Contact
FUND_PROPS = ["current_balance"]
ENGAGEMENTS = {
    "notes": ["hs_note_body", "hs_timestamp", "hubspot_owner_id"],
    "emails": ["hs_email_subject", "hs_email_text", "hs_email_direction", "hs_timestamp"],
    "calls": ["hs_call_title", "hs_call_body", "hs_timestamp", "hs_call_direction"],
    "meetings": ["hs_meeting_title", "hs_meeting_body", "hs_internal_meeting_notes", "hs_timestamp"],
    "tasks": ["hs_task_subject", "hs_task_body", "hs_timestamp", "hs_task_status"],
    "tickets": ["subject", "content", "hs_pipeline_stage", "createdate"],
}


def to_num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


class HS:
    def __init__(self, token, sleep):
        import requests
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        self.sleep = sleep

    def call(self, method, path, **kw):
        for attempt in range(6):
            r = self.s.request(method, BASE + path, timeout=30, **kw)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2 ** attempt))
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
            time.sleep(self.sleep)
            return r.json() if r.text else {}
        raise RuntimeError("rate limited repeatedly")

    def owners(self):
        out, after = {}, None
        while True:
            j = self.call("GET", "/crm/v3/owners", params={"limit": 100, **({"after": after} if after else {})})
            for o in j.get("results", []):
                out[str(o["id"])] = f"{o.get('firstName','')} {o.get('lastName','')}".strip() or o.get("email")
            after = (j.get("paging") or {}).get("next", {}).get("after")
            if not after:
                return out

    def batch_read(self, obj, ids, props):
        out = {}
        for i in range(0, len(ids), 100):
            j = self.call("POST", f"/crm/v3/objects/{obj}/batch/read",
                          json={"properties": props, "inputs": [{"id": x} for x in ids[i:i + 100]]})
            for r in j.get("results", []):
                out[str(r["id"])] = r.get("properties", {})
        return out

    def assoc(self, cid, to_type):
        j = self.call("GET", f"/crm/v4/objects/contacts/{cid}/associations/{to_type}", params={"limit": 500})
        out = []
        for r in j.get("results", []):
            labels = [t.get("label") for t in r.get("associationTypes", []) if t.get("label")]
            out.append({"id": str(r["toObjectId"]), "labels": labels})
        return out

    def surname(self, last, limit=6):
        j = self.call("POST", "/crm/v3/objects/contacts/search", json={
            "filterGroups": [{"filters": [{"propertyName": "lastname", "operator": "EQ", "value": last}]}],
            "properties": ["firstname", "lastname", "email", "city", "state"], "limit": limit})
        return j.get("results", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--sleep", type=float, default=0.15, help="seconds between calls (private apps: ~100 req / 10 s)")
    a = ap.parse_args()

    token = os.environ.get("HUBSPOT_TOKEN")
    if not token:
        print("HUBSPOT_TOKEN not set. Use the HubSpot connector path: see references/hubspot_extraction.md (Path B) "
              "and write blocks with merge_state.py.", file=sys.stderr)
        sys.exit(3)

    m = load_manifest(a.run_dir)
    hs = HS(token, a.sleep)
    if not m.get("owners"):
        m["owners"] = hs.owners()
        save_manifest(a.run_dir, m)

    cs = list_contacts(a.run_dir)
    if a.ids:
        want = set(a.ids.split(","))
        cs = [c for c in cs if c["hs_object_id"] in want]
    elif a.batch is not None:
        cs = [c for c in cs if c["status"].get("batch") == a.batch]
    cs = [c for c in cs if not c["status"]["stages"].get("hubspot")]
    if not cs:
        print("nothing to pull")
        return

    ids = [c["hs_object_id"] for c in cs]
    props = hs.batch_read("contacts", ids, PROPS)
    for ct in cs:
        hid = ct["hs_object_id"]
        p = props.get(hid)
        if p is None:
            ct["status"]["errors"].append("Contact ID not found in HubSpot")
            save_json(contact_path(a.run_dir, hid), ct)
            continue
        p["owner_name"] = m["owners"].get(str(p.get("hubspot_owner_id")), None)
        ct["hubspot"] = {"pulled_at": now(), "properties": p}

        # associations
        comp_links = hs.assoc(hid, "companies")
        cont_links = hs.assoc(hid, "contacts")
        cprops = hs.batch_read("companies", [c["id"] for c in comp_links], COMPANY_PROPS) if comp_links else {}
        companies = [{"id": c["id"], "labels": c["labels"], **{k: (cprops.get(c["id"]) or {}).get(k) for k in COMPANY_PROPS},
                      "classification": None} for c in comp_links]
        oprops = hs.batch_read("contacts", [c["id"] for c in cont_links], ["firstname", "lastname", "email"]) if cont_links else {}
        contacts = [{"id": c["id"], "labels": c["labels"],
                     "name": f"{(oprops.get(c['id']) or {}).get('firstname','')} {(oprops.get(c['id']) or {}).get('lastname','')}".strip(),
                     "email": (oprops.get(c["id"]) or {}).get("email")} for c in cont_links]
        fund_links = hs.assoc(hid, FUND_OBJECT)
        fprops = hs.batch_read(FUND_OBJECT, [f["id"] for f in fund_links], FUND_PROPS) if fund_links else {}
        funds = [{"id": f["id"], "labels": f["labels"], "current_balance": to_num((fprops.get(f["id"]) or {}).get("current_balance"))}
                 for f in fund_links]
        surname = []
        if p.get("lastname"):
            for r in hs.surname(p["lastname"]):
                if str(r["id"]) != hid:
                    rp = r.get("properties", {})
                    surname.append({"id": str(r["id"]), "firstname": rp.get("firstname"), "city": rp.get("city"),
                                    "state": rp.get("state"), "email_domain": (rp.get("email") or "@").split("@")[1] or None})
        ct["associations"] = {"companies": companies, "contacts": contacts, "funds": funds, "spouse_in_hubspot": None,
                              "household_pair_candidate": None, "surname_matches": surname}

        # activity with redaction
        act, red, unavailable = {"redactions": 0}, 0, []
        for kind, eprops in ENGAGEMENTS.items():
            try:
                links = hs.assoc(hid, kind)
                rows = []
                if links:
                    ep = hs.batch_read(kind, [l["id"] for l in links], eprops)
                    for eid, e in ep.items():
                        body_key = [k for k in eprops if k.endswith(("_body", "_text", "_notes")) or k == "content"]
                        body = " ".join(str(e.get(k)) for k in body_key if e.get(k)) or None
                        subj = e.get("hs_email_subject") or e.get("hs_call_title") or e.get("hs_meeting_title") or e.get("hs_task_subject") or e.get("subject")
                        clean, hit = screen_text(body)
                        if hit:
                            red += 1
                        rows.append({"id": eid, "timestamp": e.get("hs_timestamp") or e.get("createdate"), "subject": subj, "body": clean,
                                     "direction": e.get("hs_email_direction") or e.get("hs_call_direction")})
                act[kind] = rows
            except RuntimeError as err:
                msg = str(err)
                if "-> 403" in msg and "scope" in msg.lower():
                    act[kind] = []
                    unavailable.append(kind)
                else:
                    raise
        act["redactions"] = red
        n = sum(len(act[k]) for k in ENGAGEMENTS)
        act["summary"] = f"{n} activit{'y' if n == 1 else 'ies'}" + ("" if n else ". No notes, emails, calls, meetings, tasks, or tickets logged.")
        if unavailable:
            act["summary"] += f" ({', '.join(unavailable)} unavailable: app lacks HubSpot scope)"
        ct["activity"] = act
        if red:
            ct["status"]["errors"].append(f"{red} engagement body(ies) redacted as possible Restricted content – report to Technology Team (IT14 Policy 10)")
        if unavailable:
            ct["status"]["errors"].append(f"Engagement type(s) unavailable, app lacks HubSpot scope: {', '.join(unavailable)}")
        for s in ("hubspot", "associations", "activity"):
            ct["status"]["stages"][s] = now()
        save_json(contact_path(a.run_dir, hid), ct)
        print(f"{hid} {p.get('firstname')} {p.get('lastname')}: {len(companies)} companies, {len(contacts)} contacts, {len(funds)} funds, {n} activities, {red} redactions")

    recount(a.run_dir)
    # derive
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "derive.py"), "--run-dir", a.run_dir,
                    "--ids", ",".join(ids)], check=False)


if __name__ == "__main__":
    main()
