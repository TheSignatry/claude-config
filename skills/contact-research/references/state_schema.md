# State folder schema

```
state/
├── manifest.json          # run-level settings and counters
├── rejected.csv           # input rows that failed validation, with reason
├── companies/<slug>.json  # shared company research (one per domain/company), reused across contacts
└── contacts/<hs_object_id>.json
```

All IDs are strings. Timestamps are ISO-8601 UTC. `null` means "not known"; never write an empty string to mean unknown.

## manifest.json

```json
{
  "run_id": "2026-09-12_rm_batch_01",
  "created_at": "2026-09-12T14:02:11Z",
  "naming_convention": 1,
  "batch_size": 10,
  "current_batch": 0,
  "navigation_mode": "playwright | web_tools_fallback | mixed",
  "counts": {"total": 0, "init": 0, "hubspot": 0, "researched": 0, "rendered": 0, "rejected": 0},
  "owners": {"85144252": "Dale Armstrong"},
  "notes": []
}
```

## contacts/<id>.json

Stages are written in order: `init` → `hubspot` → `associations`/`activity` → `derived` → `research` → `rendered`. Each stage is a top-level block; `status.stages` records when each was completed so `batch.py` can find the next unit of work.

```json
{
  "hs_object_id": "239596421482",
  "input": {
    "firstname": "Paul", "lastname": "Brown", "email": "pabrown54@gmail.com",
    "phone": null, "address": null, "source_row": 9
  },

  "hubspot": {
    "pulled_at": "2026-09-12T14:05:00Z",
    "properties": {
      "firstname": "Paul", "lastname": "Brown", "salutation": null,
      "email": "pabrown54@gmail.com", "phone": null, "mobilephone": null,
      "address": null, "street_address_2": null, "city": null, "state": null, "zip": null, "country": null,
      "jobtitle": null, "company": null, "hs_linkedin_url": null, "twitterhandle": null, "marital_status": null,
      "lifecyclestage": "1020243823", "hs_lead_status": null,
      "hubspot_owner_id": "85144252", "owner_name": "Dale Armstrong",
      "createdate": "2026-08-03T15:12:46Z", "relationship_start_date": "2026-08-03",
      "hs_object_source_label": "FORM",
      "hs_object_source_detail_1": "2026-08 - Iowa NASCAR Race (YL) - VIP - Event Registration Form (SimpleEvents.io)",
      "hs_analytics_source": "OFFLINE",
      "referral_channel": "Family Office", "referral_company_give_id": null,
      "daf_application_referrer_name": null, "daf_application_referral_type": null,
      "num_notes": "0", "notes_last_updated": null,
      "guest_first_name": null, "guest_last_name": null, "guest_email": null
    }
  },

  "associations": {
    "companies": [
      {"id": "21373824583", "name": "Young Life National Headquarters", "domain": "younglife.org",
       "type": "Grant Recipient", "give_recipient_id": "3389679", "labels": [], "classification": "referral | role | household | unknown"}
    ],
    "contacts": [
      {"id": "127436451620", "name": "Caleb Scott", "labels": ["Colleague"], "email": null,
       "createdate": null, "hs_object_source_detail_1": null}
    ],
    "household_members": [
      {"id": "158301137978", "name": "Andrew Cook", "email": "acook@onexia.com"}
    ],
    "spouse_in_hubspot": {"id": null, "name": null,
      "evidence": "association label | shared 'Family'-type company | household pair (same form, registrant + guest) | none"},
    "household_pair_candidate": {"id": null, "name": null, "seconds_apart": null},
    "surname_matches": [
      {"id": "37137002849", "firstname": "Paul", "city": null, "state": null, "email_domain": "outlook.com"}
    ]
  },

  "activity": {
    "notes":    [{"id": "…", "timestamp": "…", "owner": "…", "body": "…"}],
    "emails":   [{"id": "…", "timestamp": "…", "direction": "…", "subject": "…", "body": "…"}],
    "calls": [], "meetings": [], "tasks": [],
    "tickets":  [{"id": "…", "timestamp": "…", "subject": "…", "body": "…", "stage": "…"}],
    "redactions": 0,
    "summary": "0 activities. No notes, emails, calls, meetings, or tasks logged."
  },

  "derived": {
    "email_handle": "pabrown54", "email_domain": "gmail.com", "is_corporate_domain": false,
    "identifiability_tier": "placeholder | thin | standard",
    "record_source_event": "2026-08 Iowa NASCAR Race (YL) VIP registration",
    "referral_company": "Young Life National Headquarters (Give ID 3389679) – referral only; not a role",
    "role_companies": [],
    "household_company": null,
    "duplicate_candidates": [
      {"id": "37137002849", "name": "Paul Brown", "email": null, "email_domain": "outlook.com", "city": null, "state": null,
       "seen_in": ["surname search"]}
    ],
    "data_quality_flags": ["Two other Paul Brown records in HubSpot with different emails – review for duplicates"]
  },

  "research": {
    "researched_at": "2026-09-12T15:20:00Z",
    "navigation": "playwright | web_tools_fallback",
    "model": "claude-fable-5-1  (exact model ID of the model that did the research; interactive runs write their own ID, api_batch_runner.py fills it from the API response; printed in the PDF footer and the workbook – merge_state.py rejects placeholders like 'interactive')",
    "match_confidence": "High | Moderate | Low | None   (the contact's own public identification)",
    "confidence_rationale": "…",
    "household_confidence": "High | Moderate | Low | None   (the spouse/household; 'None' when no household member is known)",
    "household_confidence_rationale": "…",
    "identity": {"full_name_public": null, "location": null, "linkedin_url": null, "other_web": []},
    "household": {"spouse_name": null, "spouse_source": null,
                  "spouse_in_hubspot": "confirmed | probable | surname-only | no | unknown",
                  "spouse_hubspot_id": null, "notes": null,
                  "spouse_corroboration": ["address | city | employer | phone | email_domain | age_band  (which HubSpot fact the public spouse source matches; required for household_confidence High unless the spouse comes from an association label)"],
                  "spouse_company": {"name": null, "role_title": null, "hq_address": null, "website": null,
                                     "revenue_estimate": null, "revenue_source": null,
                                     "ownership_type": null, "owners_principals": null, "ownership_source": null,
                                     "company_slug": null}},
    "company": {"name": null, "role_title": null, "hq_address": null, "website": null,
                "revenue_estimate": null, "revenue_source": null,
                "ownership_type": null, "owners_principals": null, "ownership_source": null,
                "is_candidate_only": false, "company_slug": null},
    "nonprofit_role_associations": [{"name": "…", "role": "…", "source": "…"}],
    "referral_context": null,
    "data_quality_flags": [],
    "overview": "3–6 sentences of plain factual prose.",
    "notes": null,
    "sources": [{"title": "…", "url": "https://…", "used_for": "…"}],
    "search_count": 0, "fetch_count": 0
  },

  "review": {"reviewed_by": null, "decision": "accept | reject | edit | null", "notes": null, "reviewed_at": null},

  "status": {
    "stages": {"init": "…", "hubspot": "…", "associations": "…", "activity": "…", "derived": "…", "research": "…", "rendered": "…"},
    "batch": 0,
    "errors": []
  }
}
```

## companies/<slug>.json

```json
{
  "slug": "beamanventures.com",
  "name": "Beaman Ventures", "domain": "beamanventures.com",
  "hq_address": "…", "website": "…",
  "revenue_estimate": "…", "revenue_source": "…",
  "ownership_type": "…", "owners_principals": "…", "ownership_source": "…",
  "employee_count": "2-10", "sources": [{"title": "…", "url": "…"}],
  "researched_at": "…", "used_by": ["244057045285", "127436451620"]
}
```

## Validation rules enforced by `merge_state.py`

- `hs_object_id` must be all digits (no scientific notation, no decimals).
- A `research` fragment must include `match_confidence`, `overview`, and `sources`.
- If `match_confidence` is `High` or `Moderate`, `sources` must be non-empty.
- If `match_confidence` is `Low` or `None`, every non-null string in `identity` and `company` must begin with `Candidate only:` or `Candidate:` (or be `N/A…`).
- `overview` must not contain characterization words from the blocklist in `governance.md` (e.g., "personality", "prefers", "responds best to", "mindset").
- Any value matching the Restricted-data patterns (SSN, card, account number, credential such as `password: …` / `username: …`, health lexicon) is rejected with an error and the record is flagged.
- `model` must be the exact model ID of the model that did the research; placeholders such as `interactive` are rejected. When the ID is off-policy for the tier (anything other than Fable 5.x or Opus 5 on `standard`; Haiku 4.5 also allowed on `thin`/`placeholder`), `merge_state.py` appends a "Researched by an off-policy model …" entry to `research.data_quality_flags` — a warning, not a rejection.
- `household_confidence` is required (use `None` when no household member is known); High/Moderate requires a source; Low/None requires `Candidate only:` prefixes on `household.spouse_company` strings.
- **Spouse-corroboration rule:** `household_confidence: High` with a public spouse source requires `household.spouse_corroboration` naming at least one HubSpot fact that source matches (`address`, `city`, `employer`, `phone`, `email_domain`, `age_band`). A wedding page or bio for a same-named couple that matches none of them supports Moderate at most. Exempt when `associations.spouse_in_hubspot.evidence` is an association label (API path).
- Research fragments are screened for the Restricted-data *patterns* only (SSN, card, account, credential); the health/hardship lexicon applies to engagement bodies, not to research prose, so "medical device integrator" or a street named Terminal does not block a merge.
- **Household-research gate:** if a spouse/household member is known (`research.household.spouse_name`, or `associations.spouse_in_hubspot.id` set by `derive.py`) and the contact's `match_confidence` is Low or None, `household.spouse_company.name` must be non-null — a name, or `Not found – <what was tried>`. This is what stops a run from writing "not identifiable, 0 sources" for a donor whose spouse is a documented executive.
