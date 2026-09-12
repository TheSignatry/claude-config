# HubSpot extraction

Two paths produce the same state blocks. Use the API when a Private App token is available (`HUBSPOT_TOKEN`); it is the only path that returns association **labels**. Use the connector path interactively in Claude.ai.

## Property set (pull all of these every time)

Identity and contact: `firstname, lastname, salutation, email, phone, mobilephone, address, street_address_2, city, state, zip, country`

Profile: `jobtitle, company, hs_linkedin_url, twitterhandle, marital_status, lifecyclestage, hs_lead_status, hubspot_owner_id`

Provenance (the most informative fields in the pilot): `createdate, relationship_start_date, hs_object_source_label, hs_object_source_detail_1, hs_object_source_detail_2, hs_analytics_source, hs_latest_source, referral_channel, referral_company_give_id, daf_application_referrer_name, daf_application_referral_type`

Activity counters and guest fields: `num_notes, notes_last_updated, hs_last_sales_activity_type, guest_first_name, guest_last_name, guest_email`

Company properties for every associated company: `name, domain, type, give_recipient_id, city, state`

## Why provenance beats activity

In the 12-contact pilot there were two notes and zero emails, calls, meetings, or tasks. What actually identified people was: `hs_object_source_detail_1` (an Iowa event form placed 10 of 12 contacts in one geography), `referral_channel` ("Family Office" surfaced a financial-adviser candidate), `referral_company_give_id` (proved five company associations were referrals), and `createdate` deltas (two registrant + guest pairs created seconds apart). Always pull these and pass them to the research step.

## Referral vs role (the nonprofit rule)

A nonprofit that referred a contact to an event often ends up as the contact's associated company. That misleads a reader into thinking the donor works there. Classify each company association:

- **referral** if `contact.referral_company_give_id == company.give_recipient_id`, or the association label is `Referred By` / `Referral`, or `referral_channel == "Nonprofit Partner"` and the company `type` is `Grant Recipient` with no role label.
- **role** if the label is one of `Employee, Board Member, Officer, Founder, Owner, Staff, Volunteer Leader` (map to the portal's actual labels once; keep the list in `derive.py`).
- **unknown** otherwise; the research step may resolve it (e.g., a public bio showing the person is on that board).

Only **role** companies populate the company/role columns. Referral companies go to `derived.referral_company` and are mentioned in the PDF's referral field.

## Household pair rule

Same `lastname` + same `hs_object_source_detail_1` + `createdate` within 120 seconds → registrant + guest from one form. Record as `household_pair_candidate`; it is stronger than a surname match but not a confirmed marriage. A confirmed spouse is only (a) a contact↔contact association labeled Spouse/Partner, or (b) a public source naming the spouse.

Surname matches (other contacts with the same last name) are listed for the reviewer but are **not** treated as spouses unless geography or a public source supports it. Two "Recker" records in Iowa and Texas are not a couple.

## Path A — HubSpot API (scripts/hubspot_pull.py)

Scopes: `crm.objects.contacts.read`, `crm.objects.companies.read`, `crm.objects.notes.read`, plus engagement read scopes. Calls, per contact ID:

| Purpose | Endpoint |
|---|---|
| Properties | `GET /crm/v3/objects/contacts/{id}?properties=…` (or `POST /crm/v3/objects/contacts/batch/read`) |
| Contact↔contact associations with labels | `GET /crm/v4/objects/contacts/{id}/associations/contacts` |
| Contact↔company associations with labels | `GET /crm/v4/objects/contacts/{id}/associations/companies` |
| Company details | `POST /crm/v3/objects/companies/batch/read` |
| Engagement IDs | `GET /crm/v4/objects/contacts/{id}/associations/{notes|emails|calls|meetings|tasks}` |
| Engagement bodies | `POST /crm/v3/objects/{notes|…}/batch/read` |
| Surname screen | `POST /crm/v3/objects/contacts/search` filter `lastname EQ` (limit 6) |
| Owner names | `GET /crm/v3/owners` |

Rate limits: HubSpot private apps allow roughly 100 requests per 10 seconds; the script sleeps on 429 and processes one batch (default 10 contacts) per invocation.

## Path B — HubSpot connector in Claude.ai

1. **Batch read** the contacts: `get_crm_objects(objectType=CONTACT, objectIds=[…], properties=[property set])`. Up to ~50 IDs per call.
2. **Same-surname screen**: one `search_crm_objects` with `lastname IN [surnames]` (limit 50) requesting `firstname, lastname, email, city, state`. For very common surnames add a `firstname EQ` filter to avoid flooding.
3. **Associated contacts**: `search_crm_objects(objectType=CONTACT, filterGroups=[{associatedWith:[{objectType:"contacts", objectIdValues:[…], operator:"IN"}]}])`. Labels are not returned; record `labels: []` and let `derive.py` infer household pairs from timing instead.
4. **Associated companies**: read the `associatedcompanyid` property, then `get_crm_objects(objectType=COMPANY, …, properties=[name, domain, type, give_recipient_id, city, state])`.
5. **Engagements**: one `search_crm_objects` per type (NOTE, EMAIL, CALL, MEETING, TASK) with the same `associatedWith` filter and `limit 100`. Properties: notes `hs_note_body, hs_timestamp, hubspot_owner_id`; emails `hs_email_subject, hs_email_text, hs_email_direction, hs_timestamp`; calls `hs_call_title, hs_call_body, hs_timestamp`; meetings `hs_meeting_title, hs_meeting_body, hs_internal_meeting_notes, hs_timestamp`; tasks `hs_task_subject, hs_task_body, hs_timestamp`. Results are not tagged with the contact ID; match them by timestamp against `notes_last_updated`/`hs_last_sales_activity_date` or re-query per contact when ambiguous.
6. **Owner name**: `search_owners` or the `hubspot_owner_id` → name map in `manifest.owners`. Write it as `owner_name` *inside* the `hubspot` fragment's `properties` object, not as a sibling key — `build_profiles.py`'s naming convention 3 and the workbook's Contact Owner column both read `hubspot.properties.owner_name`; a sibling-level `owner_name` is silently ignored and renders as "Unassigned".
7. Write each contact's blocks with `merge_state.py --stage hubspot|associations|activity`.

## Redaction screen (both paths)

Before an engagement body is written to state, `derive.py`/`hubspot_pull.py` apply the redaction helper in `scripts/cr_common.py`: SSN pattern, card pattern, 9+ digit runs near "account/routing/acct", and a health/hardship lexicon. A hit replaces the whole body with `[redacted – possible Restricted content]`, increments `activity.redactions`, and adds a flag. Remind the user to report hits to the Technology Team (IT14 Policy 10) so the source record can be cleaned.
