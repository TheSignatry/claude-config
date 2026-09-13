# Fixtures

- `sample_input.csv` – the five-contact screening set (ID + name + email + owner) used by eval 4 to compare models on identical state; the first row alone is eval 1's single-contact case. Feed to `init_run.py`.
- `228031919697_melanie_cook.expected.json` – golden expectations for the Cook household case: what Step 2 must produce deterministically (household company, spouse, duplicate) and what research must produce (contact None, household High, spouse's employer in `household.spouse_company`, never in the contact's `company` block). Written after the September 2026 side-by-side in which three models produced High, Moderate, and None on the same facts.
- `239596421482_paul_brown.state.json` – a completed state file for the pilot's sample case (Low confidence, candidate-only
  fields, referral channel "Family Office", two same-surname duplicates). Copy it into `state/contacts/` of a run initialized with
  the same ID to test `build_workbook.py` and `build_profiles.py` without doing any HubSpot or web calls:

```bash
python scripts/init_run.py --input evals/fixtures/sample_input.csv --run-dir /tmp/cr_demo --naming 2
cp evals/fixtures/239596421482_paul_brown.state.json /tmp/cr_demo/contacts/239596421482.json
python scripts/build_workbook.py --run-dir /tmp/cr_demo --out /tmp/cr_demo_out/Demo_Enriched.xlsx
python scripts/build_profiles.py --run-dir /tmp/cr_demo --out /tmp/cr_demo_out/profiles
```
