# Fixtures

- `sample_input.csv` – minimal valid input (ID + name + email). Feed to `init_run.py`.
- `239596421482_paul_brown.state.json` – a completed state file for the pilot's sample case (Low confidence, candidate-only
  fields, referral channel "Family Office", two same-surname duplicates). Copy it into `state/contacts/` of a run initialized with
  the same ID to test `build_workbook.py` and `build_profiles.py` without doing any HubSpot or web calls:

```bash
python scripts/init_run.py --input evals/fixtures/sample_input.csv --run-dir /tmp/cr_demo --naming 2
cp evals/fixtures/239596421482_paul_brown.state.json /tmp/cr_demo/contacts/239596421482.json
python scripts/build_workbook.py --run-dir /tmp/cr_demo --out /tmp/cr_demo_out/Demo_Enriched.xlsx
python scripts/build_profiles.py --run-dir /tmp/cr_demo --out /tmp/cr_demo_out/profiles
```
