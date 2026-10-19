#!/usr/bin/env python3
"""Parallel research orchestration for interactive (Claude Code) runs: queue, dispatch, ledger, recovery, stats.

Every bulk run before v1.0 rebuilt this by hand in a scratch folder. It is the tooling that lets one session drive
many research subagents at once, record what each one cost, recover from a killed agent, and report time and
tokens by stage at the end. All state lives in <work-dir> (default: a folder named `orchestration` next to the
state folder); the contact state itself stays in <run-dir> exactly as the sequential path writes it.

  python orchestrate.py queue    --run-dir state/ [--group-size 5] [--model claude-fable-5-1]
  python orchestrate.py dispatch --run-dir state/ [--n 1]          # pops N groups, writes prompts, logs start
  python orchestrate.py finish   --run-dir state/ --group b0g1 --tokens 121628 --tool-uses 43 --duration-ms 504921 [--report "..."]
  python orchestrate.py fail     --run-dir state/ --group b3g2 [--reason "API 429"]   # re-queues its unresearched contacts
  python orchestrate.py status   --run-dir state/
  python orchestrate.py pack     --run-dir state/ --id 239596421482  # one contact's research payload (fallback)
  python orchestrate.py verify   --run-dir state/ [--model claude-fable-5-1]
  python orchestrate.py stats    --run-dir state/

Concurrency: hold 8 groups in flight and dispatch one replacement per hand-back. Sixteen at once exhausted the
session-wide WebSearch allowance mid-run; eight has run 88 groups without a stall.
"""
import argparse, os, sys, json, re, glob, datetime, collections
sys.path.insert(0, os.path.dirname(__file__))
from cr_common import (list_contacts, contact_path, load_json, save_json, load_manifest, URL_RE,
                       HEALTH_HARDSHIP_LEXICON, SHARED_DOMAINS, PERSONAL_DOMAINS, model_policy_flag)

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PAYLOAD_BODY_CAP = 400  # characters of engagement body per item embedded in a prompt
RECOMMENDED_CONCURRENCY = 8


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_dur(seconds):
    s = int(seconds)
    return f"{s // 3600}h {s % 3600 // 60:02d}m {s % 60:02d}s" if s >= 3600 else f"{s // 60}m {s % 60:02d}s"


def work_dir(a):
    wd = a.work_dir or os.path.join(os.path.dirname(os.path.abspath(a.run_dir.rstrip("/"))), "orchestration")
    for sub in ("", "prompts", "fragments"):
        os.makedirs(os.path.join(wd, sub), exist_ok=True)
    return wd


def load_ledger(wd):
    return load_json(os.path.join(wd, "ledger.json"), {"created_at": utcnow(), "agents": [], "notes": []})


def save_ledger(wd, l):
    save_json(os.path.join(wd, "ledger.json"), l)


def load_queue(wd):
    return load_json(os.path.join(wd, "queue.json"), [])


def save_queue(wd, q):
    save_json(os.path.join(wd, "queue.json"), q)


# ------------------------------------------------------------------ payload
def _strip_html(s):
    return re.sub(r"<[^>]+>", " ", s or "")


def pack_contact(run_dir, hid, contacts=None):
    """The research payload for one contact: its state blocks, related records in this run, and company priors.

    related_records: other contacts in the run with the same surname or the same street address (never just the
    same city), with whatever their research already found. company_prior: companies/<email domain>.json unless the
    domain is personal, a family vanity domain, or a shared broker-dealer domain. company_prior_by_employer: a company
    record whose name matches the HubSpot employer (property or role-based association), so a colleague at the same
    firm is found even when the email domain differs.
    """
    contacts = contacts if contacts is not None else list_contacts(run_dir)
    ct = next((c for c in contacts if c["hs_object_id"] == hid), None)
    if ct is None:
        raise SystemExit(f"no state for {hid}")
    props = (ct.get("hubspot") or {}).get("properties") or {}
    inp = ct.get("input") or {}
    d = ct.get("derived") or {}
    payload = {k: ct.get(k) for k in ("hs_object_id", "input", "hubspot", "associations", "derived")}
    act = json.loads(json.dumps(ct.get("activity") or {}))
    for kind in ("notes", "emails", "calls", "meetings", "tasks", "tickets"):
        for e in act.get(kind) or []:
            if isinstance(e, dict) and isinstance(e.get("body"), str):
                body = _strip_html(e["body"]).strip()
                e["body"] = body[:PAYLOAD_BODY_CAP] + ("…" if len(body) > PAYLOAD_BODY_CAP else "")
    payload["activity"] = act

    last = (props.get("lastname") or inp.get("lastname") or "").strip().lower()
    addr = (props.get("address") or "").strip().lower()
    related = []
    for o in contacts:
        if o["hs_object_id"] == hid:
            continue
        op = (o.get("hubspot") or {}).get("properties") or {}
        ol = (op.get("lastname") or (o.get("input") or {}).get("lastname") or "").strip().lower()
        oa = (op.get("address") or "").strip().lower()
        same_addr = bool(addr and oa and oa == addr)
        if (last and ol == last) or same_addr:
            r = o.get("research") or {}
            related.append({"id": o["hs_object_id"], "name": f"{op.get('firstname') or (o.get('input') or {}).get('firstname')} {op.get('lastname') or ol}".strip(),
                            "email": op.get("email") or (o.get("input") or {}).get("email"), "address": op.get("address"),
                            "city": op.get("city"), "state": op.get("state"), "same_address": same_addr,
                            "already_researched": bool(r), "their_match": r.get("match_confidence"),
                            "their_company": (r.get("company") or {}).get("name"), "their_spouse": (r.get("household") or {}).get("spouse_name")})

    dom = d.get("email_domain")
    shared = bool(dom and dom in SHARED_DOMAINS)
    prior = None
    if dom and not shared and dom not in PERSONAL_DOMAINS and not d.get("is_vanity_domain"):
        prior = load_json(os.path.join(run_dir, "companies", f"{dom}.json"))
    by_employer = None
    employer_names = {str(props.get("company") or "").strip().lower()} | {str(c.get("name") or "").strip().lower() for c in d.get("role_companies") or []}
    employer_names.discard("")
    if employer_names:
        for fn in glob.glob(os.path.join(run_dir, "companies", "*.json")):
            co = load_json(fn) or {}
            if str(co.get("name") or "").strip().lower() in employer_names and co.get("slug") != (prior or {}).get("slug"):
                by_employer = co
                break
    return {"contact": payload, "related_records": related, "company_prior": prior,
            "company_prior_by_employer": by_employer, "shared_domain": shared}


# ------------------------------------------------------------------ queue / dispatch
def cmd_queue(a):
    wd = work_dir(a)
    contacts = list_contacts(a.run_dir)
    by_batch = collections.defaultdict(list)
    for c in contacts:
        if c.get("research"):
            continue
        if not c.get("derived"):
            print(f"skip {c['hs_object_id']}: no derived block (run hubspot_pull.py / derive.py first)", file=sys.stderr)
            continue
        by_batch[c["status"].get("batch", 0)].append(c["hs_object_id"])
    q = []
    for b in sorted(by_batch):
        ids = sorted(by_batch[b])
        for i in range(0, len(ids), a.group_size):
            q.append({"name": f"b{b}g{i // a.group_size + 1}", "model": a.model, "ids": ids[i:i + a.group_size]})
    save_queue(wd, q)
    l = load_ledger(wd)
    l.setdefault("run_dir", os.path.abspath(a.run_dir))
    l.setdefault("model", a.model)
    save_ledger(wd, l)
    print(json.dumps({"work_dir": wd, "groups": len(q), "contacts": sum(len(g["ids"]) for g in q),
                      "recommended_concurrency": RECOMMENDED_CONCURRENCY}, indent=1))


def write_prompt(a, wd, group, contacts):
    tpl_path = os.path.join(SKILL_DIR, "references", "subagent_prompt.md")
    text = open(tpl_path, encoding="utf-8").read()
    m = re.search(r"```\n(.*?)\n```", text, re.S)
    body = m.group(1) if m else text
    payloads = "\n\n".join(f"### CONTACT {hid}\n" + json.dumps(pack_contact(a.run_dir, hid, contacts), ensure_ascii=False, indent=1)
                           for hid in group["ids"])
    filled = (body.replace("{MODEL_ID}", group["model"]).replace("{RUN_DIR}", os.path.abspath(a.run_dir))
              .replace("{WORK_DIR}", wd).replace("{SKILL_DIR}", SKILL_DIR)
              .replace("{IDS}", ", ".join(group["ids"])).replace("{PAYLOADS}", payloads))
    p = os.path.join(wd, "prompts", group["name"] + ".md")
    open(p, "w", encoding="utf-8").write(filled)
    return p


def cmd_dispatch(a):
    wd = work_dir(a)
    q = load_queue(wd)
    l = load_ledger(wd)
    contacts = list_contacts(a.run_dir)
    in_flight = sum(1 for x in l["agents"] if not x.get("end"))
    if in_flight + a.n > RECOMMENDED_CONCURRENCY:
        print(f"WARNING: {in_flight} in flight + {a.n} requested exceeds the recommended {RECOMMENDED_CONCURRENCY}", file=sys.stderr)
    out = []
    for g in q[:a.n]:
        p = write_prompt(a, wd, g, contacts)
        l["agents"].append({"name": g["name"], "model": g["model"], "ids": g["ids"], "start": utcnow(), "prompt": p})
        out.append({"group": g["name"], "model": g["model"], "prompt": p, "ids": g["ids"]})
    save_queue(wd, q[a.n:])
    save_ledger(wd, l)
    print(json.dumps({"dispatched": out, "remaining_in_queue": max(0, len(q) - a.n), "in_flight": in_flight + len(out)}, indent=1))


def cmd_finish(a):
    wd = work_dir(a)
    l = load_ledger(wd)
    hit = False
    for x in l["agents"]:
        if x["name"] == a.group and not x.get("end"):
            x["end"] = utcnow()
            x["wall_s"] = (parse_ts(x["end"]) - parse_ts(x["start"])).total_seconds()
            x["usage"] = {"subagent_tokens": a.tokens, "tool_uses": a.tool_uses, "duration_ms": a.duration_ms}
            if a.report:
                x["report"] = a.report
            hit = True
    if not hit:
        sys.exit(f"no open agent named {a.group}")
    save_ledger(wd, l)
    print(json.dumps({"finished": a.group}))


def cmd_fail(a):
    """Mark an agent failed (API error, killed session) and re-queue only its contacts that were not merged."""
    wd = work_dir(a)
    l = load_ledger(wd)
    q = load_queue(wd)
    x = next((x for x in l["agents"] if x["name"] == a.group and not x.get("end")), None)
    if x is None:
        sys.exit(f"no open agent named {a.group}")
    merged = [i for i in x["ids"] if (load_json(contact_path(a.run_dir, i)) or {}).get("research")]
    todo = [i for i in x["ids"] if i not in merged]
    x["end"] = utcnow()
    x["failed"] = True
    x["reason"] = a.reason
    x["merged_before_failure"] = merged
    x["report"] = f"FAILED: {a.reason}. {len(merged)}/{len(x['ids'])} contacts merged before failure; {len(todo)} re-queued."
    n = 1 + sum(1 for g in q for _ in [0] if g["name"].startswith(a.group + "-r")) + sum(1 for y in l["agents"] if y["name"].startswith(a.group + "-r"))
    if todo:
        q.insert(0, {"name": f"{a.group}-r{n}", "model": x["model"], "ids": todo, "rerun_of": a.group})
    save_queue(wd, q)
    save_ledger(wd, l)
    print(json.dumps({"failed": a.group, "merged_before_failure": merged, "requeued": todo, "queue_len": len(q)}, indent=1))


def cmd_status(a):
    wd = work_dir(a)
    l = load_ledger(wd)
    q = load_queue(wd)
    contacts = list_contacts(a.run_dir)
    print(json.dumps({"contacts": len(contacts), "researched": sum(1 for c in contacts if c.get("research")),
                      "agents_started": len(l["agents"]), "agents_finished": sum(1 for x in l["agents"] if x.get("end") and not x.get("failed")),
                      "agents_failed": sum(1 for x in l["agents"] if x.get("failed")),
                      "in_flight": [x["name"] for x in l["agents"] if not x.get("end")],
                      "queue": [g["name"] for g in q]}, indent=1))


def cmd_pack(a):
    print(json.dumps(pack_contact(a.run_dir, a.id), ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ verify / stats
def cmd_verify(a):
    """Post-research sweep across the whole run. Read-only; prints JSON."""
    contacts = list_contacts(a.run_dir)
    lex = re.compile(r"\b(" + "|".join(re.escape(w) for w in HEALTH_HARDSHIP_LEXICON) + r")", re.I)
    pfx = re.compile(r"^(Candidate only:|Candidate:|N/A|Not |Unknown|Likely)")
    rep = {"contacts": len(contacts), "researched": 0, "missing": [], "off_policy_model": [], "unexpected_model": [],
           "high_mod_no_source": [], "digit_runs_outside_urls": [], "forced_merges": [], "prefix_violations": [],
           "lexicon_hits_in_prose": [], "match": collections.Counter(), "household": collections.Counter(),
           "deceased_per_public_source": 0, "advisor_only": 0, "signatry_staff_or_board": 0, "duplicate_flags": 0,
           "contacts_with_redactions": 0, "board_confidential_redactions": 0,
           "companies": len(glob.glob(os.path.join(a.run_dir, "companies", "*.json")))}
    for c in contacts:
        hid = c["hs_object_id"]
        r = c.get("research")
        d = c.get("derived") or {}
        errs = [str(e) if not isinstance(e, dict) else json.dumps(e) for e in (c.get("status") or {}).get("errors") or []]
        if any("redacted" in e for e in errs):
            rep["contacts_with_redactions"] += 1
        if any("Board Confidential" in e for e in errs):
            rep["board_confidential_redactions"] += 1
        if d.get("role_on_fund") == "advisor":
            rep["advisor_only"] += 1
        if d.get("signatry_relationship"):
            rep["signatry_staff_or_board"] += 1
        if not r:
            rep["missing"].append(hid)
            continue
        rep["researched"] += 1
        if model_policy_flag(r.get("model"), d.get("identifiability_tier")):
            rep["off_policy_model"].append(hid)
        if a.model and r.get("model") != a.model:
            rep["unexpected_model"].append(hid)
        if r.get("match_confidence") in ("High", "Moderate") and not any(str(s.get("url", "")).startswith("http") for s in r.get("sources") or []):
            rep["high_mod_no_source"].append(hid)
        if re.search(r"\b(?:\d[ -]?){13,19}\b", URL_RE.sub(" ", json.dumps(r))):
            rep["digit_runs_outside_urls"].append(hid)
        if any("--force" in e for e in errs):
            rep["forced_merges"].append(hid)
        if r.get("match_confidence") in ("Low", "None"):
            for blk in ("identity", "company"):
                for k, v in (r.get(blk) or {}).items():
                    if isinstance(v, str) and v and not pfx.match(v):
                        rep["prefix_violations"].append((hid, blk, k))
        prose = " ".join(str(r.get(k) or "") for k in ("overview", "notes", "confidence_rationale", "household_confidence_rationale"))
        m = lex.search(prose)
        if m:
            rep["lexicon_hits_in_prose"].append((hid, m.group(0)))  # review by hand: occupational uses (a surgeon) are fine
        rep["match"][r.get("match_confidence")] += 1
        rep["household"][r.get("household_confidence")] += 1
        if r.get("deceased_per_public_source") is True:
            rep["deceased_per_public_source"] += 1
        if re.search(r"duplicate", " ".join(map(str, (r.get("data_quality_flags") or []) + (d.get("data_quality_flags") or []))), re.I):
            rep["duplicate_flags"] += 1
    rep["match"], rep["household"] = dict(rep["match"]), dict(rep["household"])
    print(json.dumps(rep, indent=1, default=str))


def cmd_stats(a):
    """Time and measured token use by stage. Wall times come from the state stamps and the ledger; tokens are the
    subagents' reported usage only (no heuristic estimates)."""
    wd = work_dir(a)
    l = load_ledger(wd)
    m = load_manifest(a.run_dir)
    contacts = list_contacts(a.run_dir)

    def span(stage):
        ts = [parse_ts(((c.get("status") or {}).get("stages") or {}).get(stage)) for c in contacts]
        ts = [t for t in ts if t]
        return (min(ts), max(ts)) if ts else (None, None)

    init_start = parse_ts(m.get("created_at"))
    hs0, hs1 = span("hubspot")
    rs0, rs1 = span("research")
    agent_starts = [parse_ts(x["start"]) for x in l["agents"] if parse_ts(x.get("start"))]
    agent_ends = [parse_ts(x["end"]) for x in l["agents"] if parse_ts(x.get("end"))]
    if agent_starts:
        rs0 = min([rs0] + agent_starts) if rs0 else min(agent_starts)
    if agent_ends:
        rs1 = max([rs1] + agent_ends) if rs1 else max(agent_ends)
    rd0, rd1 = span("rendered")
    stages = []
    for name, s, e in (("init", init_start, hs0 or init_start), ("hubspot", hs0, hs1), ("research", rs0, rs1), ("render", rd0, rd1)):
        stages.append({"stage": name, "start": s.isoformat() if s else None, "end": e.isoformat() if e else None,
                       "wall": fmt_dur((e - s).total_seconds()) if s and e else None})
    ok = [x for x in l["agents"] if x.get("usage")]
    failed = [x for x in l["agents"] if x.get("failed")]
    toks = [x["usage"]["subagent_tokens"] for x in ok]
    covered = sum(len(x["ids"]) for x in ok)
    research = {"contacts_researched": sum(1 for c in contacts if c.get("research")),
                "subagents_total": len(l["agents"]), "subagents_with_usage": len(ok), "subagents_failed": len(failed),
                "failed_groups": [{"group": x["name"], "reason": x.get("reason"), "merged_before_failure": len(x.get("merged_before_failure") or [])} for x in failed],
                "rerun_groups": [x["name"] for x in l["agents"] if x.get("rerun_of") or "-r" in x["name"]],
                "measured_tokens": sum(toks), "tokens_per_contact": int(sum(toks) / covered) if covered else None,
                "tokens_mean_per_agent": int(sum(toks) / len(toks)) if toks else None,
                "tokens_min_max": [min(toks), max(toks)] if toks else None,
                "tool_uses": sum(x["usage"]["tool_uses"] for x in ok),
                "subagent_wall_total": fmt_dur(sum(x["usage"]["duration_ms"] for x in ok) / 1000) if ok else None,
                "web_searches": sum((c.get("research") or {}).get("search_count") or 0 for c in contacts),
                "web_fetches": sum((c.get("research") or {}).get("fetch_count") or 0 for c in contacts),
                "note": "Tokens are the subagents' reported usage; failed agents report none, so the true total is higher by their partial work."}
    overall = fmt_dur(((rd1 or rs1 or hs1) - init_start).total_seconds()) if init_start and (rd1 or rs1 or hs1) else None
    print(json.dumps({"run_id": m.get("run_id"), "contacts": len(contacts), "stages": stages, "overall_wall": overall,
                      "hubspot_stage": {"model_tokens": 0, "engagements": sum(sum(len((c.get("activity") or {}).get(k) or []) for k in ("notes", "emails", "calls", "meetings", "tasks", "tickets")) for c in contacts)},
                      "research_stage": research,
                      "render_stage": {"model_tokens": 0, "rendered": sum(1 for c in contacts if ((c.get("status") or {}).get("stages") or {}).get("rendered"))}}, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["queue", "dispatch", "finish", "fail", "status", "pack", "verify", "stats"])
    ap.add_argument("--run-dir", required=True, help="the state folder (state/)")
    ap.add_argument("--work-dir", default=None, help="ledger/queue/prompts/fragments folder (default: ../orchestration next to state/)")
    ap.add_argument("--group-size", type=int, default=5)
    ap.add_argument("--model", default="claude-fable-5-1")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--group")
    ap.add_argument("--id")
    ap.add_argument("--tokens", type=int, default=0)
    ap.add_argument("--tool-uses", type=int, default=0)
    ap.add_argument("--duration-ms", type=int, default=0)
    ap.add_argument("--report", default=None)
    ap.add_argument("--reason", default="unspecified")
    a = ap.parse_args()
    if a.cmd in ("finish", "fail") and not a.group:
        sys.exit("--group is required")
    if a.cmd == "pack" and not a.id:
        sys.exit("--id is required")
    {"queue": cmd_queue, "dispatch": cmd_dispatch, "finish": cmd_finish, "fail": cmd_fail, "status": cmd_status,
     "pack": cmd_pack, "verify": cmd_verify, "stats": cmd_stats}[a.cmd](a)


if __name__ == "__main__":
    main()
