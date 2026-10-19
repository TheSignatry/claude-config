# HubSpot extraction

Two paths produce the same state blocks. Use the API when a Private App token is available (`HUBSPOT_TOKEN`); it is the only path that returns association **labels**. Use the connector path interactively in Claude.ai.

## Property set (pull all of these every time)

Identity and contact: `firstname, lastname, salutation, email, phone, mobilephone, address, street_address_2, city, state, zip, country`

Profile: `jobtitle, company, hs_linkedin_url, twitterhandle, marital_status, lifecyclestage, hs_lead_status, hubspot_owner_id`

Provenance (the most informative fields in the pilot): `createdate, relationship_start_date, hs_object_source_label, hs_object_source_detail_1, hs_object_source_detail_2, hs_analytics_source, hs_latest_source, referral_channel, referral_company_give_id, daf_application_referrer_name, daf_application_referral_type`

DAF: `direct_fund_balance_tier_min` — a coarse balance-tier bucket, passed through to the DAF section as-is (no independent tier logic in this skill).

Activity counters and guest fields: `num_notes, notes_last_updated, hs_last_sales_activity_type, guest_first_name, guest_last_name, guest_email`

Company properties for every associated company: `name, domain, type, give_recipient_id, city, state`. Confirmed `type` values on this portal: `Commercial, Custodian, Family, Foundation, Grant Recipient, Prospect` — `Family` is the donor-household convention (see "Referral vs role" below), not an employer.

Fund properties for every associated Fund (custom object, object-type ID `2-24861263`): `current_balance`. This is the one exception to the data-minimization rule in `governance.md` — only the aggregate fund count and current-balance sum feed the DAF section; no transaction-level giving history, gift dates, or fund-level detail beyond the balance is pulled.

## Why provenance beats activity

In the 12-contact pilot there were two notes and zero emails, calls, meetings, or tasks. What actually identified people was: `hs_object_source_detail_1` (an Iowa event form placed 10 of 12 contacts in one geography), `referral_channel` ("Family Office" surfaced a financial-adviser candidate), `referral_company_give_id` (proved five company associations were referrals), and `createdate` deltas (two registrant + guest pairs created seconds apart). Always pull these and pass them to the research step.

## Referral vs role (the nonprofit rule)

A nonprofit that referred a contact to an event often ends up as the contact's associated company. That misleads a reader into thinking the donor works there. Classify each company association:

- **household** if the company `type` is `Family` — this is The Signatry's own donor-household grouping convention (a "Cook Family"-style company record linking related contacts), never an employer. Always excluded from the company/role columns; feeds household/spouse detection instead (see "Household pair rule" below).
- **referral** if `contact.referral_company_give_id == company.give_recipient_id`, or the association label is `Referred By` / `Referral`, or `referral_channel == "Nonprofit Partner"` and the company `type` is `Grant Recipient` with no role label.
- **role** if the label is one of `Employee, Board Member, Officer, Founder, Owner, Staff, Volunteer Leader` (map to the portal's actual labels once; keep the list in `derive.py`).
- **unknown** otherwise; the research step may resolve it (e.g., a public bio showing the person is on that board).

Only **role** companies populate the company/role columns. Referral companies go to `derived.referral_company` and are mentioned in the PDF's referral field. Household companies go to `derived.household_company` and are never treated as an employer.

## Household pair rule

Three signals feed `spouse_in_hubspot`, checked in this priority order (Path A can reach all three; Path B can only reach the second and third, since it cannot read association labels — see Path B step 3):

1. **Association label** — a contact↔contact association labeled Spouse/Partner. Confirmed, not just probable. Only visible via the API path.
2. **Shared "Family"-type company** — when exactly one other, distinct person is associated with the same `Family`-type company (after excluding likely duplicate records of the same person by name), record them as `spouse_in_hubspot` with evidence citing the shared company. Probable, not confirmed — a Family company can in principle hold more than a married couple (e.g., an adult child), so treat it the same as the timing-based pair below: surfaced for review, not asserted as fact. If more than one distinct other person shares the company, do not guess which one — flag all of them for manual review instead (`derive.py` does this automatically).
3. **Household pair by form timing** — same `lastname` + same `hs_object_source_detail_1` + `createdate` within 120 seconds → registrant + guest from one form. Record as `household_pair_candidate`. Weaker than either signal above.

Surname matches (other contacts with the same last name) are listed for the reviewer but are **not** treated as spouses unless geography, a shared household company, or a public source supports it. Two "Recker" records in Iowa and Texas are not a couple.

## Path A — HubSpot API (scripts/hubspot_pull.py)

Scopes: `crm.objects.contacts.read`, `crm.objects.companies.read`, `crm.objects.notes.read`, plus engagement read scopes. Calls, per contact ID:

| Purpose | Endpoint |
|---|---|
| Properties | `GET /crm/v3/objects/contacts/{id}?properties=…` (or `POST /crm/v3/objects/contacts/batch/read`) |
| Contact↔contact associations with labels | `GET /crm/v4/objects/contacts/{id}/associations/contacts` |
| Contact↔company associations with labels | `GET /crm/v4/objects/contacts/{id}/associations/companies` |
| Company details | `POST /crm/v3/objects/companies/batch/read` |
| Contact↔Fund associations | `GET /crm/v4/objects/contacts/{id}/associations/2-24861263` |
| Fund details | `POST /crm/v3/objects/2-24861263/batch/read` (property: `current_balance`) |
| Engagement IDs | `GET /crm/v4/objects/contacts/{id}/associations/{notes|emails|calls|meetings|tasks}` |
| Engagement bodies | `POST /crm/v3/objects/{notes|…}/batch/read` |
| Surname screen | `POST /crm/v3/objects/contacts/search` filter `lastname EQ` (limit 6) |
| Owner names | `GET /crm/v3/owners` |

Rate limits: HubSpot private apps allow roughly 100 requests per 10 seconds; the script sleeps on 429 and processes one batch (default 10 contacts) per invocation.

## Path B — HubSpot connector in Claude.ai

1. **Batch read** the contacts: `get_crm_objects(objectType=CONTACT, objectIds=[…], properties=[property set])`. Up to ~50 IDs per call.
2. **Same-surname screen**: one `search_crm_objects` with `lastname IN [surnames]` (limit 50) requesting `firstname, lastname, email, city, state`. For very common surnames add a `firstname EQ` filter to avoid flooding.
3. **Associated contacts**: `search_crm_objects(objectType=CONTACT, filterGroups=[{associatedWith:[{objectType:"contacts", objectIdValues:[…], operator:"IN"}]}], properties=[firstname, lastname, email, city, state, createdate, hs_object_source_detail_1])`. Labels are not returned by this call on any portal — confirmed by direct testing, not just an assumption — so record `labels: []`; the extra properties requested here let `derive.py`'s household-pair-by-timing check use these already-known associated contacts, not just other contacts in the current batch.
4. **Associated companies**: do **not** rely on the `associatedcompanyid` contact property — on this portal it is frequently empty even when a real company association exists (confirmed: a contact with no `associatedcompanyid` still had a company association findable the other way). Instead search directly: `search_crm_objects(objectType=COMPANY, filterGroups=[{associatedWith:[{objectType:"contacts", objectIdValues:[…], operator:"EQUAL"}]}], properties=[name, domain, type, give_recipient_id, city, state])`.
5. **Household members (when a `Family`-type company is found in step 4)**: run one more query, `search_crm_objects(objectType=CONTACT, filterGroups=[{associatedWith:[{objectType:"companies", objectIdValues:[family_company_id], operator:"EQUAL"}]}], properties=[firstname, lastname, email])`, and record the results (minus the contact itself) as `associations.household_members`. This is the connector path's substitute for the unreadable Spouse label — see "Household pair rule" above for how `derive.py` uses it.
6. **Associated Funds**: `search_crm_objects(objectType="2-24861263", filterGroups=[{associatedWith:[{objectType:"contacts", objectIdValues:[…], operator:"EQUAL"}]}], properties=[current_balance])`, and record the results as `associations.funds` (`[{id, labels: [], current_balance}]`). Pull `current_balance` only — no fund name, gift history, or transaction detail; that is the whole point of the DAF-section carve-out in `governance.md`.
7. **Engagements**: one `search_crm_objects` per type (NOTE, EMAIL, CALL, MEETING, TASK, **TICKET**) with the same `associatedWith` filter and `limit 100`. Tickets are included because on this portal the decisive facts (a donor naming a spouse, an account-access request) have turned up in ticket threads that the NOTE search never returned. Ticket properties: `subject, content, hs_pipeline_stage, createdate` — write them to `activity.tickets` as `{id, timestamp, subject, body (= content), stage}`. For emails request `hs_email_subject, hs_email_direction, hs_timestamp` first and pull `hs_email_text` only when the subject suggests relationship content; donor-care threads on this portal have contained plaintext portal credentials, and the redaction screen only protects what is written to state, not what you read. Other properties: notes `hs_note_body, hs_timestamp, hubspot_owner_id`; emails `hs_email_subject, hs_email_text, hs_email_direction, hs_timestamp`; calls `hs_call_title, hs_call_body, hs_timestamp`; meetings `hs_meeting_title, hs_meeting_body, hs_internal_meeting_notes, hs_timestamp`; tasks `hs_task_subject, hs_task_body, hs_timestamp`. Results are not tagged with the contact ID; match them by timestamp against `notes_last_updated`/`hs_last_sales_activity_date` or re-query per contact when ambiguous. If a contact's `num_notes`/etc. counters are non-zero but a query here returns nothing, don't treat that as confirmed "no activity" — this has been observed to happen (possibly search-index lag); say so in a flag rather than asserting zero activity.
8. **Owner name**: `search_owners` or the `hubspot_owner_id` → name map in `manifest.owners`. Write it as `owner_name` *inside* the `hubspot` fragment's `properties` object, not as a sibling key — `build_profiles.py`'s naming convention 3 and the workbook's Contact Owner column both read `hubspot.properties.owner_name`; a sibling-level `owner_name` is silently ignored and renders as "Unassigned".
9. Write each contact's blocks with `merge_state.py --stage hubspot|associations|activity`. The `associations` fragment must carry **all** of these keys, as empty lists when nothing was found — `batch.py next` refuses to hand a contact to research while any of `contacts`, `surname_matches`, or `companies` is missing, and `derive.py` flags it:

   ```json
   {
     "contacts": [{"id": "158301137978", "name": "Andrew Cook", "labels": [], "email": "acook@onexia.com",
                   "city": "Newton Square", "state": "PA", "createdate": "2025-09-25T06:34:05.270Z",
                   "hs_object_source_detail_1": "give-sync-create_contact-2025-09-25"}],
     "companies": [{"id": "58339120715", "name": "Cook Family", "domain": null, "type": "Family",
                    "give_recipient_id": null, "city": null, "state": null, "labels": []}],
     "household_members": [{"id": "158301137978", "name": "Andrew Cook", "email": "acook@onexia.com"}],
     "surname_matches": [{"id": "244790763082", "firstname": "Melanie", "city": null, "state": null, "email_domain": "hotmail.com"}],
     "funds": [{"id": "9821457", "labels": [], "current_balance": 125000.0}]
   }
   ```

   `household_members` and `funds` may be omitted when none were found; `spouse_in_hubspot` and `household_pair_candidate` are computed by `derive.py` — do not hand-write them.

## Redaction screen (both paths)

Before an engagement body or subject is written to state, `merge_state.py`/`hubspot_pull.py` apply the redaction helper in `scripts/cr_common.py`: SSN pattern, card pattern (URLs removed first, so a press-release or EDGAR ID in a link does not trip it), 6+ digit runs near "account/routing/acct", PIN and wire/ACH-instruction patterns, credential patterns (`password: …`, `username: …`), and a health/hardship/bereavement lexicon matched at word starts. Research fragments get the pattern screen only — the lexicon is for notes about a person, not for prose about a company's sector or a street name. A hit replaces the whole body with `[redacted – possible Restricted content]`, increments `activity.redactions`, and adds a flag. When the contact is Signatry staff or a board member (`cr_common.signatry_insider`: a Signatry email domain, or a Signatry-named company association with an employment or board label), the Board Confidential lexicon is applied as well and hits are counted separately as `[redacted – possible Board Confidential content]`. Remind the user to report hits to the Technology Team (IT14 Policy 10) so the source record can be cleaned. Public registration identifiers (EIN, CRD, license numbers) are not screened; they are public data.
