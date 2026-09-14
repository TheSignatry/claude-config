#!/usr/bin/env python3
"""Render one Signatry-branded PDF profile per contact from the state folder.

  python build_profiles.py --run-dir state/ --out outputs/profiles/ [--naming 1|2|3] [--ids 1,2,3] [--batch N]

Naming conventions (--naming overrides manifest.naming_convention):
  1  {HubSpotContactId}_{FirstName}_{LastName}_profile.pdf
  2  {LastName}_{FirstName}_{HubSpotContactId}_profile.pdf
  3  {ContactOwner}_{LastName}_{FirstName}_{HubSpotContactId}_profile.pdf

Brand: uses the signatry-pdf-brand skill (fonts, palette, logo) when present at /mnt/skills/organization/signatry-pdf-brand
or $SIGNATRY_PDF_BRAND_DIR; otherwise falls back to Helvetica with the same palette and prints a warning.
"""
import argparse, os, sys, json, html, re
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import list_contacts, load_manifest, contact_path, save_json, now, profile_filename, recount, skill_version
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

BRAND_DIR = os.environ.get("SIGNATRY_PDF_BRAND_DIR", "/mnt/skills/organization/signatry-pdf-brand")
FONT_BODY, FONT_BODY_B, FONT_BODY_SB, FONT_HEAD = "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica"
LOGO_W = None
C = {"legacy": colors.HexColor("#2b7a78"), "glacier": colors.HexColor("#37a49f"), "ice": colors.HexColor("#def2f1"),
     "midnight": colors.HexColor("#17242a"), "dusk": colors.HexColor("#d77900"), "dawn": colors.HexColor("#f2a65a")}


def tint(hex_, pct):
    h = hex_.lstrip("#"); r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16); p = pct / 100
    return colors.Color((255 + (r - 255) * p) / 255, (255 + (g - 255) * p) / 255, (255 + (b - 255) * p) / 255)


if os.path.isdir(BRAND_DIR):
    try:
        sys.path.insert(0, os.path.join(BRAND_DIR, "scripts"))
        from signatry_pdf_brand import register_signatry_fonts, SIGNATRY_COLORS
        register_signatry_fonts()
        C.update(SIGNATRY_COLORS)
        FONT_BODY, FONT_BODY_B, FONT_BODY_SB, FONT_HEAD = "Mulish", "Mulish-Bold", "Mulish-SemiBold", "Lora"
        LOGO_W = os.path.join(BRAND_DIR, "assets", "logos", "logo_white_1C.png")
    except Exception as e:
        print(f"WARNING: brand skill present but failed to load ({e}); using Helvetica", file=sys.stderr)
else:
    print("WARNING: signatry-pdf-brand skill not found; rendering with Helvetica and no logo", file=sys.stderr)

NA = "—"
SHORT = {"High": "HIGH", "Moderate": "MODERATE", "Low": "CANDIDATE ONLY", "None": "NOT IDENTIFIED", "N/A": "N/A", None: "NOT YET RESEARCHED"}
CONF_COLOR = {"High": C["glacier"], "Moderate": C["glacier"], "Low": C["dawn"], "None": C["dusk"], "N/A": C["dusk"], None: colors.grey}
RANK = {"High": 4, "Moderate": 3, "Low": 2, "None": 1, "N/A": 0, None: 0}


def P(name, **kw):
    base = dict(fontName=FONT_BODY, fontSize=9.5, leading=13, textColor=C["midnight"]); base.update(kw)
    return ParagraphStyle(name, **base)


S = dict(sec=P("sec", fontName=FONT_HEAD, fontSize=14, leading=18, textColor=C["legacy"], spaceBefore=10, spaceAfter=4),
         body=P("body"), small=P("small", fontSize=8, leading=10.5, textColor=tint("#17242a", 70)),
         label=P("label", fontName=FONT_BODY_SB, fontSize=9, leading=12, textColor=C["legacy"]), val=P("val"),
         src=P("src", fontSize=8, leading=10.5, textColor=tint("#17242a", 80)))


def esc(t):
    return html.escape(str(t if t not in (None, "") else NA))


def g(d, *path, default=NA):
    cur = d
    for p in path:
        cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return default
    if isinstance(cur, list):
        return "; ".join(str(x) if not isinstance(x, dict) else json.dumps(x, ensure_ascii=False) for x in cur) or default
    return cur if cur not in ("",) else default


def kv(rows, col1=1.7 * inch):
    data = [[Paragraph(esc(k), S["label"]), Paragraph(esc(v), S["val"])] for k, v in rows]
    t = Table(data, colWidths=[col1, 7.0 * inch - col1])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -2), 0.4, tint("#2b7a78", 20)),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    return t


def callout(text, fill):
    t = Table([[Paragraph(text, S["body"])]], colWidths=[7.0 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fill), ("BOX", (0, 0), (-1, -1), 0.5, tint("#2b7a78", 40)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


HDR_H = 1.55 * inch


def fmt_dup(x):
    who = x.get("email") or x.get("email_domain")
    where = " ".join(p for p in [x.get("city"), x.get("state")] if p)
    extra = "".join(f", {v}" for v in (who, where) if v)
    return f"{x.get('name')} (ID {x.get('id')}{extra}) – seen in {', '.join(x.get('seen_in') or [])}"


def on_page_factory(name, location, conf, hh_conf, owner, rendered_date, model, sk_ver):
    def on_page(canv, doc):
        w, h = letter
        canv.saveState()
        canv.setFillColor(C["legacy"]); canv.rect(0, h - HDR_H, w, HDR_H, stroke=0, fill=1)
        canv.setFillColor(C["glacier"]); canv.rect(0, h - HDR_H - 4, w, 4, stroke=0, fill=1)
        if LOGO_W and os.path.exists(LOGO_W):
            canv.drawImage(LOGO_W, w - 0.75 * inch - 1.55 * inch, h - 0.94 * inch, width=1.55 * inch, height=0.52 * inch, mask="auto")
        x = 0.75 * inch
        canv.setFillColor(C["dawn"]); canv.setFont(FONT_BODY_SB, 8.5)
        canv.drawString(x, h - 0.48 * inch, "CONTACT RESEARCH PROFILE  ·  INTERNAL  ·  CONFIDENTIAL (IT15)")
        canv.setFillColor(colors.white); canv.setFont(FONT_HEAD, 22); canv.drawString(x, h - 0.86 * inch, name)
        canv.setFillColor(C["ice"]); canv.setFont(FONT_BODY, 10.5); canv.drawString(x, h - 1.10 * inch, location[:80])
        label = (f"CONTACT: {SHORT.get(conf, SHORT[None])}   ·   HOUSEHOLD: {SHORT.get(hh_conf, SHORT[None])}"
                 if (conf or hh_conf) else SHORT[None])
        best = max([conf, hh_conf], key=lambda k: RANK.get(k, 0))
        canv.setFont(FONT_BODY_B, 8); tw = canv.stringWidth(label, FONT_BODY_B, 8)
        canv.setFillColor(CONF_COLOR.get(best, colors.grey)); canv.roundRect(x, h - 1.45 * inch, tw + 16, 15, 3, stroke=0, fill=1)
        canv.setFillColor(colors.white); canv.drawString(x + 8, h - 1.41 * inch, label)
        owner_label = f"OWNER: {(owner or 'UNASSIGNED').upper()}"
        canv.setFont(FONT_BODY_B, 8); ow = canv.stringWidth(owner_label, FONT_BODY_B, 8)
        canv.setFillColor(tint("#17242a", 45)); canv.roundRect(w - 0.75 * inch - ow - 16, h - 1.45 * inch, ow + 16, 15, 3, stroke=0, fill=1)
        canv.setFillColor(colors.white); canv.drawString(w - 0.75 * inch - ow - 8, h - 1.41 * inch, owner_label)
        canv.setFillColor(tint("#17242a", 60)); canv.setFont(FONT_BODY, 7.5)
        canv.drawString(0.75 * inch, 0.62 * inch, "The Signatry  ·  Internal contact research  ·  Confidential (IT15)")
        canv.drawString(0.75 * inch, 0.48 * inch, "AI-assisted; a human must review and verify before use in decisions affecting donors (IT14 Policy 1).")
        canv.drawRightString(w - 0.75 * inch, 0.62 * inch, f"Skill v{sk_ver}  ·  Model: {model}  ·  Rendered {rendered_date}  ·  Page {doc.page}")
        canv.restoreState()
    return on_page


def build(ct, out_dir, naming, rendered_date):
    props = (ct.get("hubspot") or {}).get("properties") or {}
    inp = ct.get("input") or {}
    r = ct.get("research") or {}
    d = ct.get("derived") or {}
    assoc = ct.get("associations") or {}
    act = ct.get("activity") or {}
    name = f"{props.get('firstname') or inp.get('firstname') or ''} {props.get('lastname') or inp.get('lastname') or ''}".strip()
    location = re.sub(r"\s*\(.*$", "", g(r, "identity", "location")) if len(g(r, "identity", "location")) > 60 else g(r, "identity", "location")
    conf = r.get("match_confidence")
    hh_conf = r.get("household_confidence") or ("N/A" if r else None)
    sc = (r.get("household") or {}).get("spouse_company") or {}
    model = r.get("model") or "not yet researched"
    owner = props.get("owner_name") or inp.get("owner")
    sk_ver = skill_version() or "?"
    fn = os.path.join(out_dir, profile_filename(ct, naming))
    doc = BaseDocTemplate(fn, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=HDR_H + 0.35 * inch,
                          bottomMargin=0.8 * inch, title=f"Contact Research Profile – {name}", author="The Signatry",
                          subject="Internal donor research; Confidential (IT15); AI-assisted")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f", leftPadding=0, rightPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page_factory(
        name, location if location != NA else "", conf, hh_conf, owner, rendered_date, model, sk_ver))])
    st = []
    nsrc = len(r.get("sources") or [])
    st.append(callout(f"<b>Sources checked:</b> HubSpot contact record, associations, and logged activity; HubSpot record-source and referral fields; "
                      f"{nsrc} public web source{'s' if nsrc != 1 else ''} (navigation: {esc(r.get('navigation'))}).", C["ice"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("Overview", S["sec"]))
    st.append(Paragraph(esc(r.get("overview") or "Not yet researched."), S["body"]))
    st.append(Paragraph("About", S["sec"]))
    st.append(kv([("Full name", name), ("Public spelling", g(r, "identity", "full_name_public")), ("Location", g(r, "identity", "location")),
                  ("Match confidence (contact)", f"{conf or 'Not yet researched'} – {g(r, 'confidence_rationale')}"),
                  ("Household confidence", f"{hh_conf or 'Not yet researched'} – {g(r, 'household_confidence_rationale')}"),
                  ("HubSpot record", f"ID {ct['hs_object_id']}"),
                  ("Possible duplicate records", "; ".join(fmt_dup(x) for x in d.get("duplicate_candidates") or []) or "None found in HubSpot"),
                  ("Record source", f"{props.get('hs_object_source_label') or NA} – {d.get('record_source_event') or props.get('hs_object_source_detail_1') or NA}"),
                  ("Created", props.get("createdate") or NA)]))
    st.append(Paragraph("Contact", S["sec"]))
    addr = ", ".join(p for p in [props.get("address"), props.get("city"), props.get("state"), props.get("zip")] if p) or inp.get("address") or "— (not on file)"
    st.append(kv([("Email (HubSpot)", props.get("email") or inp.get("email")), ("Phone (HubSpot)", props.get("phone") or props.get("mobilephone") or inp.get("phone")),
                  ("Mailing address (HubSpot)", addr)]))
    st.append(Paragraph("DAF", S["sec"]))
    daf = d.get("daf") or {}
    st.append(kv([("Fund count", daf.get("fund_count", 0)),
                  ("Tier", daf.get("tier") or NA),
                  ("Fund balance (sum, current)", f"${daf.get('fund_balance_sum', 0):,.2f}")]))
    st.append(Paragraph("Social Media and Web", S["sec"]))
    st.append(kv([("LinkedIn", g(r, "identity", "linkedin_url")), ("Other", g(r, "identity", "other_web")),
                  ("In HubSpot", props.get("hs_linkedin_url") or props.get("twitterhandle") or "No LinkedIn URL or Twitter handle on the record")]))
    st.append(Paragraph("Household and Spouse", S["sec"]))
    sp = assoc.get("spouse_in_hubspot") or {}
    pair = assoc.get("household_pair_candidate") or {}
    st.append(kv([("Spouse identified (public)", (f"{g(r, 'household', 'spouse_name')} – source: {g(r, 'household', 'spouse_source')}" if g(r, 'household', 'spouse_name') != NA else NA)),
                  ("Spouse in HubSpot?", f"{g(r, 'household', 'spouse_in_hubspot')}" + (f" – {sp.get('name')} (ID {sp.get('id')}; {sp.get('evidence')})" if sp.get("id") else "")),
                  ("Household pair (same form)", f"{pair.get('name')} (ID {pair.get('id')}, {pair.get('seconds_apart')} s apart)" if pair.get("id") else NA),
                  ("Household company (HubSpot)", f"{d['household_company']['name']} (ID {d['household_company']['id']})" if d.get("household_company") else NA),
                  ("Same-surname records", "; ".join(f"{x.get('firstname')} (ID {x.get('id')}, {x.get('city') or '?'} {x.get('state') or ''})".strip() for x in assoc.get("surname_matches") or []) or NA),
                  ("Notes", g(r, "household", "notes")),
                  ("Spouse's employer (public)", sc.get("name")),
                  ("Spouse's role / title", sc.get("role_title")),
                  ("Spouse's company address / website", " / ".join(v for v in [sc.get("hq_address"), sc.get("website")] if v) or NA),
                  ("Spouse's company revenue", " – ".join(v for v in [sc.get("revenue_estimate"), sc.get("revenue_source")] if v) or NA),
                  ("Spouse's company ownership", " – ".join(v for v in [sc.get("ownership_type"), sc.get("owners_principals"), sc.get("ownership_source")] if v) or NA)]))
    st.append(Paragraph("Career and Company", S["sec"]))
    co = r.get("company") or {}
    st.append(kv([("Company", co.get("name")), ("Role / title", co.get("role_title")), ("Company address", co.get("hq_address")), ("Website", co.get("website")),
                  ("Est. annual revenue", co.get("revenue_estimate")), ("Revenue source", co.get("revenue_source")),
                  ("Nonprofit roles (public)", "; ".join(f"{x.get('name')} – {x.get('role')} ({x.get('source')})" for x in r.get("nonprofit_role_associations") or []) or NA)]))
    st.append(Paragraph("Business Ownership (public sources)", S["sec"]))
    st.append(kv([("Ownership type", co.get("ownership_type")), ("Owner(s) / principals", co.get("owners_principals")), ("Source", co.get("ownership_source"))]))
    st.append(Paragraph("HubSpot Activity and Referral", S["sec"]))
    notes_txt = "; ".join(f"{n.get('timestamp','')[:10]}: {n.get('body')}" for n in (act.get("notes") or [])[:5]) or None
    tickets_txt = "; ".join(f"{t.get('timestamp','')[:10]}: {t.get('subject')}" for t in (act.get("tickets") or [])[:5]) or None
    st.append(kv([("Logged activity", act.get("summary") or NA), ("Recent notes", notes_txt or NA), ("Recent tickets", tickets_txt or NA),
                  ("Referral channel", props.get("referral_channel") or NA), ("Referral company", d.get("referral_company") or NA),
                  ("Associated company (role-based)", "; ".join(x.get("name") or "" for x in d.get("role_companies") or []) or NA),
                  ("Associated contacts", "; ".join(f"{x.get('name')} ({', '.join(x.get('labels') or []) or 'no label'})" for x in assoc.get("contacts") or []) or NA),
                  ("Referral context (research)", r.get("referral_context") or NA)]))
    st.append(Paragraph("Notes and Data-Quality Flags", S["sec"]))
    flags = (d.get("data_quality_flags") or []) + (r.get("data_quality_flags") or [])
    st.append(callout(esc("\n".join(flags) or "None"), tint("#f2a65a", 20)))
    if r.get("notes"):
        st.append(Spacer(1, 4)); st.append(Paragraph("<b>Research notes:</b> " + esc(r["notes"]), S["small"]))
    if ct.get("review", {}).get("decision"):
        st.append(Spacer(1, 4)); st.append(Paragraph(f"<b>Review:</b> {esc(ct['review'].get('decision'))} by {esc(ct['review'].get('reviewed_by'))} – {esc(ct['review'].get('notes'))}", S["small"]))
    st.append(Paragraph("Sources", S["sec"]))
    srcs = r.get("sources") or []
    if not srcs:
        st.append(Paragraph("No public sources could be tied to this record. HubSpot record and activity reviewed.", S["src"]))
    for i, s in enumerate(srcs, 1):
        st.append(Paragraph(f"{i}. {esc(s.get('title'))} – {esc(s.get('used_for'))}<br/><font color='#2b7a78'>{esc(s.get('url'))}</font>", S["src"]))
        st.append(Spacer(1, 2))
    st.append(Paragraph(f"HubSpot data pulled {str((ct.get('hubspot') or {}).get('pulled_at', ''))[:10] or 'n/a'}; research {str(r.get('researched_at', ''))[:10] or 'n/a'}. "
                        f"No Restricted data (IT15) was accessed or recorded. Third-party AI-generated behavioral content, if any, is excluded by policy.", S["src"]))
    doc.build(st)
    return fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--naming", type=int, choices=[1, 2, 3], default=None)
    ap.add_argument("--ids", default=None); ap.add_argument("--batch", type=int, default=None)
    a = ap.parse_args()
    m = load_manifest(a.run_dir)
    naming = a.naming or m.get("naming_convention")
    if not naming:
        sys.exit("No naming convention: pass --naming 1|2|3 (1={Id}_{First}_{Last}, 2={Last}_{First}_{Id}, 3={Owner}_{Last}_{First}_{Id})")
    cs = list_contacts(a.run_dir)
    if a.ids:
        want = set(a.ids.split(",")); cs = [c for c in cs if c["hs_object_id"] in want]
    if a.batch is not None:
        cs = [c for c in cs if c["status"].get("batch") == a.batch]
    os.makedirs(a.out, exist_ok=True)
    rd = now()[:10]
    files = []
    for ct in cs:
        files.append(build(ct, a.out, naming, rd))
        if ct.get("research"):
            ct["status"]["stages"]["rendered"] = now(); save_json(contact_path(a.run_dir, ct["hs_object_id"]), ct)
    recount(a.run_dir)
    print(json.dumps({"naming_convention": naming, "files": files}, indent=2))


if __name__ == "__main__":
    main()
