#!/usr/bin/env python3
"""Unattended research through the Claude Message Batches API, merged back into state.

  export ANTHROPIC_API_KEY=...
  python api_batch_runner.py --run-dir state/ submit [--batch N] [--dry-run]
  python api_batch_runner.py --run-dir state/ collect --batch-id msgbatch_...

Model routing by identifiability tier (change with --model-thin / --model-standard):
  placeholder -> no request; a fixed "not researchable" research block is written locally
  thin        -> claude-haiku-4-5   web_search max_uses 2
  standard    -> claude-fable-5-1   web_search max_uses 6, web_fetch max_uses 4
The standard-tier default is Fable 5.1: in the September 2026 side-by-side on a real donor, Fable was the only model
to reach both scores at High and it stopped at 3 searches; Sonnet 5 and Opus 5 stayed thin or stopped at "None" on
the same state. Re-evaluate once the search recipe and household gate have been in use; to escalate or economize,
re-submit specific IDs with --model-standard claude-opus-5 or --model-standard claude-sonnet-5.

Why batches: 50% of standard price, built-in web-search throttling, and the static system prompt (from
references/research_prompt.md) is marked cache_control so it is cached across the batch. Results come back as JSONL
keyed by custom_id = hs_object_id; `collect` validates each with merge_state.py before writing.

Requires: anthropic (pip install anthropic --break-system-packages)
"""
import argparse, os, sys, json, re, subprocess, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import list_contacts, load_manifest, save_manifest, contact_path, load_json, save_json, now

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_MD = os.path.join(HERE, "..", "references", "research_prompt.md")


def system_prompt():
    md = open(PROMPT_MD, encoding="utf-8").read()
    m = re.search(r"```\n(.*?)\n```", md, re.S)
    return m.group(1)


def not_researchable(ct):
    first = ((ct.get("hubspot") or {}).get("properties") or {}).get("firstname") or ct["input"].get("firstname")
    return {
        "match_confidence": "None",
        "confidence_rationale": f"Placeholder first name '{first}'; no real name to research.",
        "identity": {"full_name_public": None, "location": None, "linkedin_url": None, "other_web": []},
        "household": {"spouse_name": None, "spouse_source": None, "spouse_in_hubspot": "unknown", "spouse_hubspot_id": None, "notes": None},
        "company": {"name": None, "role_title": None, "hq_address": None, "website": None, "revenue_estimate": None,
                    "revenue_source": None, "ownership_type": None, "owners_principals": None, "ownership_source": None,
                    "is_candidate_only": False, "company_slug": None},
        "nonprofit_role_associations": [], "referral_context": None,
        "data_quality_flags": ["Placeholder record – replace with the real name and add a household association"],
        "overview": f"This record carries the placeholder first name \"{first}\" and no researchable identity. "
                    f"It was most likely created as a guest entry for another registrant. No public research was attempted.",
        "notes": "Not researchable.", "sources": [], "search_count": 0, "fetch_count": 0,
        "navigation": "none", "model": "none",
    }


def build_request(ct, related, prior, model_thin, model_standard, sys_prompt):
    tier = (ct.get("derived") or {}).get("identifiability_tier", "standard")
    model = model_thin if tier == "thin" else model_standard
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2 if tier == "thin" else 6}]
    if tier == "standard":
        tools.append({"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 4})
    payload = {k: ct.get(k) for k in ("hs_object_id", "input", "hubspot", "associations", "activity", "derived")}
    user = ("Research the contact below and return the output JSON.\n\n<contact>\n" + json.dumps(payload, ensure_ascii=False) +
            "\n</contact>\n\n<related_records>\n" + json.dumps(related, ensure_ascii=False) +
            "\n</related_records>\n\n<company_prior>\n" + json.dumps(prior, ensure_ascii=False) + "\n</company_prior>")
    return {"custom_id": ct["hs_object_id"],
            "params": {"model": model, "max_tokens": 3000,
                       "system": [{"type": "text", "text": sys_prompt, "cache_control": {"type": "ephemeral"}}],
                       "tools": tools,
                       "messages": [{"role": "user", "content": user}]}}, model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("cmd", choices=["submit", "collect"])
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--model-thin", default="claude-haiku-4-5")
    ap.add_argument("--model-standard", default="claude-fable-5-1")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    m = load_manifest(a.run_dir)
    cs = list_contacts(a.run_dir)
    by_id = {c["hs_object_id"]: c for c in cs}

    if a.cmd == "submit":
        pool = [c for c in cs if not c["status"]["stages"].get("research") and c.get("derived")]
        if a.ids:
            want = set(a.ids.split(","))
            pool = [c for c in pool if c["hs_object_id"] in want]
        elif a.batch is not None:
            pool = [c for c in pool if c["status"].get("batch") == a.batch]
        sp = system_prompt()
        reqs, local = [], 0
        for ct in pool:
            tier = ct["derived"]["identifiability_tier"]
            if tier == "placeholder":
                ct["research"] = not_researchable(ct) | {"researched_at": now()}
                ct["status"]["stages"]["research"] = now()
                save_json(contact_path(a.run_dir, ct["hs_object_id"]), ct)
                local += 1
                continue
            pair = ((ct.get("associations") or {}).get("household_pair_candidate") or {}).get("id")
            related = {k: by_id[pair].get(k) for k in ("hs_object_id", "input", "hubspot", "derived")} if pair in by_id else None
            slug = (ct["derived"].get("email_domain") or "").lower()
            prior = load_json(os.path.join(a.run_dir, "companies", f"{slug}.json")) if slug else None
            req, model = build_request(ct, related, prior, a.model_thin, a.model_standard, sp)
            reqs.append(req)
        print(f"{local} placeholder record(s) written locally; {len(reqs)} request(s) prepared")
        if a.dry_run or not reqs:
            if reqs:
                print(json.dumps(reqs[0]["params"]["messages"][0]["content"][:800]))
            return
        import anthropic
        client = anthropic.Anthropic()
        mb = client.messages.batches.create(requests=reqs)
        m.setdefault("notes", []).append({"api_batch_id": mb.id, "submitted_at": now(), "count": len(reqs),
                                          "models": {a.model_thin: "thin", a.model_standard: "standard"}})
        save_manifest(a.run_dir, m)
        print(json.dumps({"api_batch_id": mb.id, "status": mb.processing_status, "count": len(reqs)}))
        return

    # collect
    import anthropic
    client = anthropic.Anthropic()
    bid = a.batch_id or next((n["api_batch_id"] for n in reversed(m.get("notes", [])) if isinstance(n, dict) and n.get("api_batch_id")), None)
    if not bid:
        sys.exit("no batch id")
    mb = client.messages.batches.retrieve(bid)
    if mb.processing_status != "ended":
        print(json.dumps({"api_batch_id": bid, "status": mb.processing_status, "counts": mb.request_counts.model_dump()}))
        return
    ok, bad = 0, 0
    for res in client.messages.batches.results(bid):
        hid = res.custom_id
        if res.result.type != "succeeded":
            ct = by_id.get(hid)
            if ct:
                ct["status"]["errors"].append(f"API batch {bid}: {res.result.type}")
                save_json(contact_path(a.run_dir, hid), ct)
            bad += 1
            continue
        msg = res.result.message
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        try:
            frag = json.loads(text)
        except Exception:
            by_id[hid]["status"]["errors"].append(f"API batch {bid}: non-JSON response")
            save_json(contact_path(a.run_dir, hid), by_id[hid])
            bad += 1
            continue
        frag["model"] = msg.model
        frag["navigation"] = "web_tools"
        usage = getattr(msg, "usage", None)
        if usage:
            frag["usage"] = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(frag, f)
            path = f.name
        r = subprocess.run([sys.executable, os.path.join(HERE, "merge_state.py"), "--run-dir", a.run_dir, "--id", hid,
                            "--stage", "research", "--file", path], capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
            slug = frag.get("company", {}).get("company_slug")
            if slug and frag["company"].get("name") and not frag["company"].get("is_candidate_only"):
                comp = {k: frag["company"].get(k) for k in ("name", "hq_address", "website", "revenue_estimate", "revenue_source",
                                                            "ownership_type", "owners_principals", "ownership_source")}
                comp.update({"slug": slug, "used_by": [hid], "sources": frag.get("sources", [])})
                subprocess.run([sys.executable, os.path.join(HERE, "merge_state.py"), "--run-dir", a.run_dir, "--stage", "company",
                                "--json", json.dumps(comp)], capture_output=True)
        else:
            bad += 1
            by_id[hid]["status"]["errors"].append(f"API batch {bid}: validation failed – {r.stdout[:300]}")
            save_json(contact_path(a.run_dir, hid), by_id[hid])
        os.unlink(path)
    print(json.dumps({"api_batch_id": bid, "merged": ok, "failed": bad}))


if __name__ == "__main__":
    main()
