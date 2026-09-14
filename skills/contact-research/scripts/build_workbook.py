#!/usr/bin/env python3
"""Render the enrichment workbook from the state folder. Safe to re-run at any time.

  python build_workbook.py --run-dir state/ --out outputs/RM_Enriched.xlsx [--ids 1,2,3] [--batch N]

Sheets:
  Contact Enrichment   – one row per contact; HS: (blue) | Spouse (purple) | Research: (green) | Ownership: (gold)
  Summary              – counts by confidence tier and stage
  Upload Prep – Contacts – HubSpot import headers; research values pre-filled only for High/Moderate; Accept? column
  Upload Prep – Notes  – one composed, sourced note per contact for a Notes import
  Methodology          – how the data was produced, rules applied, review requirement
  Sources              – every URL used, by contact
"""
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import list_contacts, load_manifest, load_json, now, contact_path, save_json, recount
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = load_json(os.path.join(HERE, "..", "assets", "upload_template_columns.json"))
HS_URL = "https://app.hubspot.com/contacts/{portal}/record/0-1/{id}"
NA = "—"

A = "Arial"
F_HDR = Font(name=A, bold=True, color="FFFFFF", size=10)
F_BODY = Font(name=A, size=10)
F_BOLD = Font(name=A, size=10, bold=True)
F_TITLE = Font(name=A, size=14, bold=True)
F_NOTE = Font(name=A, size=9, italic=True)
F_LINK = Font(name=A, size=10, color="0563C1", underline="single")
FILL = {"KEY": "404040", "HS": "1F4E78", "SP": "7030A0", "R": "375623", "OWN": "7F6000", "UP": "833C0B"}
BODY = {"KEY": None, "HS": "DDEBF7", "SP": "EDE3F5", "R": "E2EFDA", "OWN": "FFF2CC", "UP": "FBE5D6"}
WARN = PatternFill("solid", fgColor="FCE4D6")
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def pf(hex_):
    return PatternFill("solid", fgColor=hex_)


def get(ct, path, default=NA):
    cur = ct
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = None
        if cur is None:
            return default
    if isinstance(cur, list):
        return "; ".join(str(x) if not isinstance(x, dict) else json.dumps(x, ensure_ascii=False) for x in cur) or default
    return cur if cur not in ("", None) else default


def joined(ct, *paths, sep=", "):
    vals = [get(ct, p, None) for p in paths]
    return sep.join(v for v in vals if v) or NA


def confirmed(ct):
    return get(ct, "research.match_confidence", "None") in ("High", "Moderate")


def compose_note(ct):
    r = ct.get("research") or {}
    if not r:
        return NA
    lines = [f"Contact research ({r.get('researched_at', '')[:10]}), match confidence: {r.get('match_confidence')}. AI-assisted; reviewed by: ______."]
    if r.get("overview"):
        lines.append(r["overview"])
    c = r.get("company") or {}
    if c.get("name"):
        lines.append(f"Company: {c.get('name')} — {c.get('role_title') or 'role not published'}. Ownership: {c.get('ownership_type') or 'n/a'}; {c.get('owners_principals') or ''}".rstrip("; ") + ".")
    h = r.get("household") or {}
    if h.get("spouse_name"):
        lines.append(f"Spouse (per {h.get('spouse_source') or 'public source'}): {h['spouse_name']}. In HubSpot: {h.get('spouse_in_hubspot')}.")
    sc = h.get("spouse_company") or {}
    if sc.get("name"):
        lines.append(f"Spouse's employer (household context, confidence {r.get('household_confidence')}): {sc['name']} — {sc.get('role_title') or 'role not published'}. Ownership: {sc.get('ownership_type') or 'n/a'}.")
    if r.get("data_quality_flags"):
        lines.append("Flags: " + " | ".join(r["data_quality_flags"]))
    if r.get("sources"):
        lines.append("Sources: " + "; ".join(s.get("url", "") for s in r["sources"] if s.get("url")))
    return "\n".join(lines)


COLS = [
    ("KEY", "HubSpot Record ID", lambda c, m: c["hs_object_id"], 16),
    ("KEY", "HubSpot Record URL", lambda c, m: HS_URL.format(portal=m.get("portal_id", "44656601"), id=c["hs_object_id"]), 26),
    ("KEY", "Batch", lambda c, m: c["status"].get("batch"), 7),
    ("HS", "HS: Full Name", lambda c, m: joined(c, "hubspot.properties.firstname", "hubspot.properties.lastname", sep=" "), 18),
    ("HS", "HS: Contact Owner", lambda c, m: get(c, "hubspot.properties.owner_name"), 16),
    ("HS", "HS: Email", lambda c, m: get(c, "hubspot.properties.email"), 28),
    ("HS", "HS: Phone", lambda c, m: joined(c, "hubspot.properties.phone", "hubspot.properties.mobilephone", sep=" / "), 14),
    ("HS", "HS: Street", lambda c, m: joined(c, "hubspot.properties.address", "hubspot.properties.street_address_2"), 20),
    ("HS", "HS: City", lambda c, m: get(c, "hubspot.properties.city"), 12),
    ("HS", "HS: State", lambda c, m: get(c, "hubspot.properties.state"), 8),
    ("HS", "HS: ZIP", lambda c, m: get(c, "hubspot.properties.zip"), 8),
    ("HS", "HS: Job Title", lambda c, m: get(c, "hubspot.properties.jobtitle"), 14),
    ("HS", "HS: Company (property)", lambda c, m: get(c, "hubspot.properties.company"), 16),
    ("HS", "HS: LinkedIn / Twitter", lambda c, m: joined(c, "hubspot.properties.hs_linkedin_url", "hubspot.properties.twitterhandle", sep=" / "), 16),
    ("HS", "HS: Associated Company (role-based only)", lambda c, m: "; ".join(f"{x.get('name')}{' – ' + x['note'] if x.get('note') else ''}" for x in (get(c, "derived.role_companies", None) and (c.get("derived") or {}).get("role_companies") or [])) or NA, 26),
    ("HS", "HS: Referral Company (Give ID)", lambda c, m: get(c, "derived.referral_company"), 26),
    ("HS", "HS: Referral Channel", lambda c, m: get(c, "hubspot.properties.referral_channel"), 14),
    ("HS", "HS: Record Source / Event", lambda c, m: joined(c, "hubspot.properties.hs_object_source_label", "derived.record_source_event", sep=" – "), 28),
    ("HS", "HS: Created", lambda c, m: get(c, "hubspot.properties.createdate"), 18),
    ("HS", "HS: Associated Contacts", lambda c, m: "; ".join(f"{x.get('name')} ({', '.join(x.get('labels') or []) or 'no label'})" for x in ((c.get("associations") or {}).get("contacts") or [])) or NA, 26),
    ("HS", "HS: Possible Duplicate Records", lambda c, m: "; ".join(f"{x.get('name')} (ID {x.get('id')}{', ' + (x.get('email') or x.get('email_domain')) if (x.get('email') or x.get('email_domain')) else ''}) – {', '.join(x.get('seen_in') or [])}" for x in ((c.get("derived") or {}).get("duplicate_candidates") or [])) or NA, 30),
    ("HS", "HS: Logged Activity", lambda c, m: get(c, "activity.summary"), 30),
    ("HS", "DAF: Fund Count", lambda c, m: get(c, "derived.daf.fund_count", 0), 12),
    ("HS", "DAF: Tier", lambda c, m: get(c, "hubspot.properties.direct_fund_balance_tier_min"), 14),
    ("HS", "DAF: Fund Balance", lambda c, m: f"${get(c, 'derived.daf.fund_balance_sum', 0):,.2f}", 16),
    ("SP", "Spouse in HubSpot", lambda c, m: (lambda s: f"{s.get('name')} (ID {s.get('id')}) – {s.get('evidence')}" if s and s.get("id") else NA)((c.get("associations") or {}).get("spouse_in_hubspot")), 30),
    ("SP", "Household Pair (same form)", lambda c, m: (lambda p: f"{p.get('name')} (ID {p.get('id')}, {p.get('seconds_apart')} s apart)" if p and p.get("id") else NA)((c.get("associations") or {}).get("household_pair_candidate")), 26),
    ("SP", "Household Company (HubSpot)", lambda c, m: (lambda h: f"{h.get('name')} (ID {h.get('id')})" if h else NA)((c.get("derived") or {}).get("household_company")), 26),
    ("SP", "Same-Surname Records", lambda c, m: "; ".join(f"{x.get('firstname')} (ID {x.get('id')}, {x.get('city') or '?'} {x.get('state') or ''})".strip() for x in ((c.get("associations") or {}).get("surname_matches") or [])) or NA, 30),
    ("SP", "Research: Spouse Identified", lambda c, m: get(c, "research.household.spouse_name"), 24),
    ("SP", "Research: Spouse Source / In HubSpot?", lambda c, m: joined(c, "research.household.spouse_source", "research.household.spouse_in_hubspot", sep=" | "), 30),
    ("SP", "Research: Spouse Employer", lambda c, m: get(c, "research.household.spouse_company.name"), 24),
    ("SP", "Research: Spouse Role / Title", lambda c, m: get(c, "research.household.spouse_company.role_title"), 24),
    ("SP", "Research: Spouse Company Ownership", lambda c, m: joined(c, "research.household.spouse_company.ownership_type", "research.household.spouse_company.owners_principals", sep=" – "), 30),
    ("R", "Research: Match Confidence (contact)", lambda c, m: get(c, "research.match_confidence"), 14),
    ("R", "Research: Household Confidence", lambda c, m: get(c, "research.household_confidence"), 14),
    ("R", "Research: Confidence Rationale", lambda c, m: get(c, "research.confidence_rationale"), 34),
    ("R", "Research: Navigation", lambda c, m: get(c, "research.navigation"), 14),
    ("R", "Research: Model", lambda c, m: get(c, "research.model"), 18),
    ("R", "Research: Public Name / Location", lambda c, m: joined(c, "research.identity.full_name_public", "research.identity.location", sep=" – "), 28),
    ("R", "Research: LinkedIn URL", lambda c, m: get(c, "research.identity.linkedin_url"), 36),
    ("R", "Research: Other Web", lambda c, m: get(c, "research.identity.other_web"), 30),
    ("R", "Research: Company", lambda c, m: get(c, "research.company.name"), 28),
    ("R", "Research: Role / Title", lambda c, m: get(c, "research.company.role_title"), 30),
    ("R", "Research: Company Address", lambda c, m: get(c, "research.company.hq_address"), 30),
    ("R", "Research: Website", lambda c, m: get(c, "research.company.website"), 24),
    ("R", "Research: Est. Annual Revenue", lambda c, m: get(c, "research.company.revenue_estimate"), 32),
    ("R", "Research: Revenue Source", lambda c, m: get(c, "research.company.revenue_source"), 26),
    ("R", "Research: Nonprofit Role Associations", lambda c, m: "; ".join(f"{x.get('name')} – {x.get('role')} ({x.get('source')})" for x in ((c.get("research") or {}).get("nonprofit_role_associations") or [])) or NA, 30),
    ("OWN", "Ownership: Type", lambda c, m: get(c, "research.company.ownership_type"), 26),
    ("OWN", "Ownership: Owner(s) / Principals", lambda c, m: get(c, "research.company.owners_principals"), 36),
    ("OWN", "Ownership: Source", lambda c, m: get(c, "research.company.ownership_source"), 30),
    ("R", "Research: Referral Context", lambda c, m: get(c, "research.referral_context"), 30),
    ("R", "Data-Quality Flags", lambda c, m: "\n".join(((c.get("derived") or {}).get("data_quality_flags") or []) + ((c.get("research") or {}).get("data_quality_flags") or [])) or NA, 44),
    ("R", "Research: Notes", lambda c, m: get(c, "research.notes"), 34),
    ("R", "Review Decision", lambda c, m: joined(c, "review.decision", "review.reviewed_by", sep=" – "), 18),
]


def style_header_row(ws, row, cols, fills):
    for i, (grp, hdr, width) in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=i, value=hdr)
        cell.font = F_HDR; cell.fill = pf(FILL[grp]); cell.alignment = CENTER; cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = width


def sheet_enrichment(wb, cs, m):
    ws = wb.active
    ws.title = "Contact Enrichment"
    ws["A1"] = f"Contact Research – {m['run_id']}"; ws["A1"].font = F_TITLE
    ws["A2"] = (f"Rendered {now()[:10]}. Confidential (IT15). AI-assisted; a human must review and verify before use in decisions "
                f"affecting donors (IT14 Policy 1). Blue = HubSpot data; green/gold = inferred from public sources; purple = spouse evaluation.")
    ws["A2"].font = F_NOTE
    ws.merge_cells("A1:H1"); ws.merge_cells("A2:R2")
    HDR, FIRST = 4, 5
    style_header_row(ws, HDR, [(g, h, w) for g, h, _, w in COLS], FILL)
    ws.row_dimensions[HDR].height = 34
    for r, ct in enumerate(cs, start=FIRST):
        for i, (grp, hdr, fn, w) in enumerate(COLS, start=1):
            try:
                v = fn(ct, m)
            except Exception as e:
                v = f"[render error: {e}]"
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = F_BODY; cell.alignment = WRAP; cell.border = BORDER
            if BODY[grp]:
                cell.fill = pf(BODY[grp])
            if hdr == "HubSpot Record URL":
                cell.hyperlink = v; cell.font = F_LINK
            if hdr == "HS: Full Name":
                cell.font = F_BOLD
            if hdr == "Research: Match Confidence" and str(v).startswith(("Low", "None", "—")):
                cell.fill = WARN
        ws.row_dimensions[r].height = 120
    ws.freeze_panes = ws.cell(row=FIRST, column=5)
    ws.auto_filter.ref = f"A{HDR}:{get_column_letter(len(COLS))}{FIRST + len(cs) - 1}"


def sheet_summary(wb, cs, m):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Summary"; ws["A1"].font = F_TITLE
    conf = {"High": 0, "Moderate": 0, "Low": 0, "None": 0, "Not yet researched": 0}
    for c in cs:
        conf[(c.get("research") or {}).get("match_confidence") or "Not yet researched"] += 1
    rows = [("Contacts in run", len(cs)),
            ("With HubSpot data pulled", sum(1 for c in cs if c.get("hubspot"))),
            ("With a mailing address in HubSpot", sum(1 for c in cs if get(c, "hubspot.properties.address", None))),
            ("With an email in HubSpot", sum(1 for c in cs if get(c, "hubspot.properties.email", None))),
            ("With a spouse association or probable household pair", sum(1 for c in cs if ((c.get("associations") or {}).get("spouse_in_hubspot") or {}).get("id"))),
            ("Referral-only nonprofit associations removed from company columns", sum(1 for c in cs if (c.get("derived") or {}).get("referral_company"))),
            ("Records flagged as placeholders", sum(1 for c in cs if (c.get("derived") or {}).get("identifiability_tier") == "placeholder"))] + \
           [(f"Match confidence: {k}", v) for k, v in conf.items()] + \
           [("Rejected input rows (see rejected.csv)", m["counts"].get("rejected", 0)),
            ("Naming convention for PDFs", m.get("naming_convention"))]
    ws["A3"], ws["B3"] = "Metric", "Value"
    for c_ in ("A3", "B3"):
        ws[c_].font = F_HDR; ws[c_].fill = pf(FILL["HS"]); ws[c_].border = BORDER
    for i, (k, v) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=k).font = F_BODY
        ws.cell(row=i, column=2, value=v).font = F_BODY
        for cc in (1, 2):
            ws.cell(row=i, column=cc).border = BORDER
    ws.column_dimensions["A"].width = 68; ws.column_dimensions["B"].width = 14


def sheet_upload_contacts(wb, cs, m):
    ws = wb.create_sheet("Upload Prep – Contacts")
    ws["A1"] = "HubSpot contact import – review, type Y in Accept?, then export accepted rows to CSV"; ws["A1"].font = F_TITLE
    ws["A2"] = ("Headers match HubSpot import labels; 'Record ID' updates the existing record. Research values are pre-filled only where "
                "match confidence is High or Moderate. Low/None rows are left blank so nothing inferred reaches HubSpot without a deliberate decision. "
                "Custom properties (e.g., Spouse Name) must exist or be mapped in the import wizard.")
    ws["A2"].font = F_NOTE; ws.merge_cells("A2:L2")
    cols = UPLOAD["contacts"]
    hdrs = UPLOAD["review_columns"] + [c["header"] for c in cols] + ["Match Confidence", "Source URLs"]
    for i, h in enumerate(hdrs, start=1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = F_HDR; cell.fill = pf(FILL["UP"] if i > 3 else FILL["KEY"]); cell.alignment = CENTER; cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = 16 if i <= 3 else 24
    for r, ct in enumerate(cs, start=5):
        ok = confirmed(ct)
        vals = ["", "", ""]
        for c in cols:
            v = get(ct, c["state_path"], None)
            if c["state_path"] == "research.identity.city" or c["state_path"] == "research.identity.state":
                loc = get(ct, "research.identity.location", None)
                if loc and ok and "," in loc:
                    parts = [p.strip() for p in loc.split("(")[0].split(",")]
                    v = parts[0] if c["state_path"].endswith("city") else parts[1] if len(parts) > 1 else None
                else:
                    v = None
            if c.get("requires_confirmed") and not ok:
                v = None
            if isinstance(v, str) and v.startswith("Candidate"):
                v = None
            vals.append(v if v not in (None, NA) else "")
        vals += [get(ct, "research.match_confidence"), "; ".join(s.get("url", "") for s in ((ct.get("research") or {}).get("sources") or []))]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=i, value=v); cell.font = F_BODY; cell.alignment = WRAP; cell.border = BORDER
            if i <= 3:
                cell.fill = pf("FFF2CC")
            elif not ok:
                cell.fill = WARN
    ws.freeze_panes = "E5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(hdrs))}{4 + len(cs)}"


def sheet_upload_notes(wb, cs, m):
    ws = wb.create_sheet("Upload Prep – Notes")
    ws["A1"] = "HubSpot notes import – one composed research note per contact"; ws["A1"].font = F_TITLE
    ws["A2"] = ("Edit the note text as needed, type Y in Accept?, then import accepted rows as Notes associated to the contact Record ID. "
                "Each note states its confidence, that it is AI-assisted, and lists its sources.")
    ws["A2"].font = F_NOTE; ws.merge_cells("A2:F2")
    hdrs = UPLOAD["review_columns"] + [c["header"] for c in UPLOAD["notes"]] + ["Contact"]
    for i, h in enumerate(hdrs, start=1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = F_HDR; cell.fill = pf(FILL["UP"] if i > 3 else FILL["KEY"]); cell.alignment = CENTER; cell.border = BORDER
    widths = [12, 14, 24, 22, 90, 16, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for r, ct in enumerate(cs, start=5):
        vals = ["", "", "", ct["hs_object_id"], compose_note(ct), get(ct, "research.researched_at", "")[:10],
                joined(ct, "hubspot.properties.firstname", "hubspot.properties.lastname", sep=" ")]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=i, value=v); cell.font = F_BODY; cell.alignment = WRAP; cell.border = BORDER
            if i <= 3:
                cell.fill = pf("FFF2CC")
        ws.row_dimensions[r].height = 150
    ws.freeze_panes = "E5"


def sheet_methodology(wb, cs, m):
    ws = wb.create_sheet("Methodology")
    ws["A1"] = "Methodology, rules, and review requirement"; ws["A1"].font = F_TITLE
    nav = sorted({(c.get("research") or {}).get("navigation") for c in cs if c.get("research")} - {None})
    models = sorted({(c.get("research") or {}).get("model") for c in cs if c.get("research")} - {None})
    rows = [
        ("Scope", f"{len(cs)} contact(s) in run {m['run_id']}; batch size {m['batch_size']}; {m['counts'].get('rejected', 0)} input row(s) rejected (rejected.csv). HubSpot IDs are stored as strings; Excel scientific-notation IDs are refused."),
        ("HubSpot pull", "Properties, contact and company associations (including 'Family'-type household companies and their members), and NOTE/EMAIL/CALL/MEETING/TASK/TICKET engagements were pulled per references/hubspot_extraction.md. Engagement text passed a redaction screen for Restricted content (SSN, card, account, credential, and health/hardship patterns) before being stored."),
        ("Nonprofit association rule", "A nonprofit company association is kept in the company/role columns only when the contact holds a role there. Where referral_company_give_id matches the company's Give Recipient ID (or the association is labeled Referred By), the association is a referral and is shown in 'HS: Referral Company' instead."),
        ("Spouse evaluation", "Confirmed = a Spouse/Partner association label (API path) or a public source naming the spouse. Probable = exactly one other person on the same 'Family'-type household company, or same surname created by the same form within 120 seconds (registrant + guest). Surname-only matches are listed but not treated as spouses. Two scores are reported: 'Match Confidence (contact)' for the contact's own public identification and 'Household Confidence' for the spouse/household; when the contact is not publicly identifiable but a spouse is known, the spouse's employer, role, and ownership are researched as household context and reported in the 'Research: Spouse …' columns, never in the contact's own company columns."),
        ("Public research", f"Model(s): {', '.join(models) or 'n/a'} (also per contact in 'Research: Model' and in each PDF footer). Navigation mode(s): {', '.join(nav) or 'n/a'}. Playwright is used where the environment allows; otherwise web search/fetch tools. Match standard: High = two independent signals; Moderate = one strong match on an uncommon name; Low = circumstantial candidate ('Candidate only:' prefix); None = not identified, fields left blank. No value is guessed."),
        ("Revenue and ownership", "Reported only with a named source. Third-party estimates and predecessor/parent figures are labeled. Ownership from bios or press is marked as such; confirm against Secretary of State filings before relying on it."),
        ("Upload prep", "The two 'Upload Prep' sheets carry HubSpot import headers. Research values are pre-filled only for High/Moderate matches; a reviewer types Y in Accept? and exports the accepted rows to CSV for the HubSpot import wizard. This skill writes nothing to HubSpot."),
        ("Data handling", "Confidential (IT15). No Restricted data was requested or stored; redaction counts appear in the flags column. Third-party AI-generated behavioral content is excluded by policy."),
        ("Review requirement", "AI-assisted output. A human must review and verify facts, figures, and identity matches before use in any decision affecting donors or in external communications (IT14 Policy 1)."),
    ]
    ws["A3"], ws["B3"] = "Topic", "Detail"
    for c_ in ("A3", "B3"):
        ws[c_].font = F_HDR; ws[c_].fill = pf(FILL["HS"]); ws[c_].border = BORDER
    for i, (k, v) in enumerate(rows, start=4):
        a_ = ws.cell(row=i, column=1, value=k); a_.font = F_BOLD; a_.alignment = WRAP; a_.border = BORDER
        b_ = ws.cell(row=i, column=2, value=v); b_.font = F_BODY; b_.alignment = WRAP; b_.border = BORDER
        ws.row_dimensions[i].height = 80
    ws.column_dimensions["A"].width = 26; ws.column_dimensions["B"].width = 120


def sheet_sources(wb, cs, m):
    ws = wb.create_sheet("Sources")
    ws["A1"] = "Public sources consulted"; ws["A1"].font = F_TITLE
    for i, h in enumerate(["Contact", "HubSpot ID", "Source", "Used for", "URL"], start=1):
        cell = ws.cell(row=3, column=i, value=h); cell.font = F_HDR; cell.fill = pf(FILL["HS"]); cell.border = BORDER
    r = 4
    for ct in cs:
        name = joined(ct, "hubspot.properties.firstname", "hubspot.properties.lastname", sep=" ")
        for s in ((ct.get("research") or {}).get("sources") or []):
            vals = [name, ct["hs_object_id"], s.get("title"), s.get("used_for"), s.get("url")]
            for i, v in enumerate(vals, start=1):
                cell = ws.cell(row=r, column=i, value=v); cell.font = F_BODY; cell.alignment = WRAP; cell.border = BORDER
            if s.get("url", "").startswith("http"):
                ws.cell(row=r, column=5).hyperlink = s["url"]; ws.cell(row=r, column=5).font = F_LINK
            r += 1
    for i, w in enumerate([22, 16, 60, 30, 80], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--batch", type=int, default=None)
    a = ap.parse_args()
    m = load_manifest(a.run_dir)
    cs = list_contacts(a.run_dir)
    if a.ids:
        want = set(a.ids.split(",")); cs = [c for c in cs if c["hs_object_id"] in want]
    if a.batch is not None:
        cs = [c for c in cs if c["status"].get("batch") == a.batch]
    wb = Workbook()
    sheet_enrichment(wb, cs, m)
    sheet_summary(wb, cs, m)
    sheet_upload_contacts(wb, cs, m)
    sheet_upload_notes(wb, cs, m)
    sheet_methodology(wb, cs, m)
    sheet_sources(wb, cs, m)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    wb.save(a.out)
    for ct in cs:
        if ct.get("research"):
            ct["status"]["stages"]["rendered"] = now()
            save_json(contact_path(a.run_dir, ct["hs_object_id"]), ct)
    recount(a.run_dir)
    print(json.dumps({"written": a.out, "contacts": len(cs)}))


if __name__ == "__main__":
    main()
