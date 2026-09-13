# Changelog — contact-research

Every substantive change to this skill. Newest first.

Format: date · what changed · why it matters.

---

## 2026-09-13 — fixed Path B company-association pull; added "Family"-company household detection

Live-tested Step 2 (HubSpot pull) against a real donor contact on the connector path and found two real gaps beyond the already-documented "connector can't read association labels" limitation:

1. **Bug**: `hubspot_extraction.md`'s Path B company-association step relied on the `associatedcompanyid` contact property, which was empty even though a real company association existed (confirmed against a live record: `search_crm_objects(COMPANY, associatedWith: contacts)` found the company; the property-based method missed it entirely). Fixed the documented method to search directly, mirroring the associated-contacts step.
2. **Gap**: The Signatry's portal uses `company.type = "Family"` as a donor-household grouping convention (not an employer). `derive.py` didn't know this and would have rendered a Family-type company as an "unconfirmed role" company — misleadingly implying employment. Added a `household` classification (excluded from `role_companies`), a new `derived.household_company` field, and a `associations.household_members` pull step (second-hop query: other contacts on that same Family company) so the connector path has a real substitute for the unreadable Spouse label. When exactly one other distinct person shares the household company, `spouse_in_hubspot` surfaces them as a probable match citing the shared company (never "confirmed" — a Family company can in principle hold more than a married couple); two or more distinct others are flagged for manual review instead of guessing.
3. Also extended the household-pair-by-timing fallback (`derive.py`) to check `associations.contacts` (already pulled in Step 2), not just other contacts in the current batch — it previously missed a directly-associated contact with a near-identical `createdate` simply because that person wasn't separately submitted as a batch member.
4. `state_schema.md` updated: `associations.contacts` entries now carry `createdate`/`hs_object_source_detail_1`; added `associations.household_members`; added `derived.household_company`; documented the confirmed `company.type` enum (`Commercial, Custodian, Family, Foundation, Grant Recipient, Prospect`). `build_workbook.py`/`build_profiles.py` updated to surface `household_company` directly instead of only inside the spouse-evidence text.

**Why it matters:** verified against a live donor record where a real "Spouse" association label existed in HubSpot (visible in the UI, confirmed by the user) but was invisible to every connector tool available — the fix means the connector path now reaches the same practical conclusion (probable spouse, flagged for review) through the household-company signal, instead of silently reporting "spouse: unknown" on a contact with a real, recorded household relationship.

## 2026-09-12 — initial version

First version of the skill. Enriches HubSpot contacts with public-web research through a JSON state folder, producing an enrichment spreadsheet (HubSpot data separated from inferred web data, with upload-prep sheets) and one branded PDF profile per contact.
