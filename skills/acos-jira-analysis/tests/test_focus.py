#!/usr/bin/env python3
"""Tests for the Personal Focus dashboard. Run from the skill directory:

    python3 -m unittest discover -s tests

The fixture in fixtures/focus_2026-10-24/ was reconstructed from the
prototype's _exclude/focus_data.json: raw.json in the fetched-issue shape (33
items assigned to the owner plus an archived and a Roadmap Done idea the
report must drop), synthesized comments for the four support items in play,
a profile whose owner is Treadwell Cassidy with the 12-person Technology roster,
and plan.json built from acos-aboutme's shipped defaults.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / "scripts"))

import focus  # noqa: E402
import qa_common  # noqa: E402

FIX = HERE / "fixtures" / "focus_2026-10-24"
TODAY = date(2026, 10, 24)
DEFAULTS = SKILL.parent / "acos-aboutme" / "references" / "defaults.json"
PROTO = SKILL / "_exclude" / "focus_data.json"
ORDER = ["od", "wk", "yc", "nu", "st", "pg", "mm", "cu"]


def load():
    return json.loads((FIX / "plan.json").read_text()), json.loads((FIX / "raw.json").read_text())


class FixtureAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.raw = load()
        cls.p = focus.build_focus_report(cls.plan, cls.raw, TODAY)
        cls.items = {t["key"]: t for t in cls.p["items"]}

    def test_matches_golden_payload(self):
        expected = json.loads((FIX / "expected_payload.json").read_text())
        self.assertEqual(json.loads(json.dumps(self.p, ensure_ascii=False)), expected)

    def test_totals(self):
        self.assertEqual(self.p["counts"], {"open": 33, "mine": 15, "waiting": 4, "parked": 14, "scored": 12, "nextMoves": 8})
        self.assertEqual(self.p["waiting"], ["SUP-1478", "GE-262", "GE-152", "GE-122"])
        self.assertNotIn("TRM-900", self.items)  # archived
        self.assertNotIn("TRM-901", self.items)  # Roadmap Done

    def test_check_counts(self):
        self.assertEqual([self.p["views"][""]["checkCounts"][k] for k in ORDER], [6, 4, 3, 1, 3, 7, 3, 10])

    def test_header(self):
        self.assertEqual(self.p["eyebrow"], "Focus for Treadwell Cassidy, Sat 24 Oct 2026")
        self.assertEqual(self.p["headline"], "Three people are waiting on you, three of your items are past due, and four more land in the next seven days.")
        self.assertTrue(self.p["subhead"].startswith("You own 33 open items: 15 are your move, 4 are waiting on someone else, and 14 are parked."))
        self.assertIn("12 of your 15 your-move items score today; the top 8 are shown.", self.p["movesCaption"])

    def test_next_moves(self):
        # TT-1442 ranks above TT-1444 on the key tie-break; the prototype kept Jira's order.
        self.assertEqual([(k, self.items[k]["score"]) for k in self.p["nextMoves"]], [
            ("SUP-930", 126.3), ("SUP-1243", 101.0), ("SUP-1244", 69.0), ("TT-1403", 51.5),
            ("TRM-443", 51.0), ("TT-1442", 43.0), ("TT-1444", 43.0), ("TT-1445", 37.0)])
        self.assertEqual(self.items["SUP-930"]["why"], "58 days past its due; Sawyer Benton replied 4 days ago and is waiting on you.")
        self.assertEqual(self.items["TRM-443"]["why"], "Target in 3 days.")

    def test_tidy_and_fix(self):
        self.assertEqual(sorted(self.p["tidy"]), sorted(["TRM-123", "TRM-88", "TRM-343", "GE-89", "TRM-38", "TRM-39", "TRM-40",
                                                          "TRM-54", "TRM-164", "TRM-183", "TRM-237"]))
        upd = [self.items[k]["updDays"] for k in self.p["tidy"]]
        self.assertEqual(upd, sorted(upd, reverse=True))
        self.assertEqual(sorted(self.p["fix"]), sorted(["SUP-930", "TRM-123", "TRM-443", "TRM-20", "TRM-26", "TRM-295",
                                                        "TRM-367", "TRM-402", "TRM-237"]))

    def test_contradictions(self):
        self.assertEqual(self.items["SUP-930"]["mismatch"], "Pending reason “More info required” is set, but the status is Waiting for support")
        self.assertEqual(self.items["TRM-123"]["mismatch"], "Roadmap says Won’t do, but the idea is still open")
        self.assertEqual(self.items["TRM-443"]["mismatch"], "Roadmap says Now, but the status is still Parking lot")

    def test_waiting_sentences(self):
        self.assertEqual(self.items["SUP-1478"]["waitingText"], "You replied 23 Oct 2026; waiting on the requester. Last update today.")
        self.assertEqual(self.items["GE-262"]["waitingText"],
                         "With Give Interactive, with no Give Ticket ID yet; status Signatry Approved. Last update 28 days ago.")
        self.assertEqual(self.items["GE-152"]["waitingText"],
                         "With Give Interactive (GCP-5363); status Future Consideration. Last update 253 days ago.")

    def test_timeline(self):
        rows = {r["ws"]: r for r in self.p["timeline"]["rows"]}
        self.assertEqual({w: r["count"] for w, r in rows.items()}, {"product": 12, "support": 3, "work": 7})
        earlier = {p["key"] for r in rows.values() for p in r["points"] if p["pos"] == "earlier"}
        later = {p["key"] for r in rows.values() for p in r["points"] if p["pos"] == "later"}
        self.assertEqual(earlier, {"TRM-123", "TRM-88", "TRM-343", "SUP-930", "SUP-1243"})
        self.assertEqual(later, {"TRM-20"})
        self.assertEqual(sorted(b["key"] for b in rows["product"]["bars"]), ["TRM-164", "TRM-212", "TRM-237", "TRM-26"])
        self.assertEqual((self.p["timeline"]["start"], self.p["timeline"]["end"]), ("2026-10-01", "2026-12-31"))

    def test_comment_bodies_never_surface(self):
        self.assertNotIn("ignore prior instructions", json.dumps(self.p).lower())

    def test_teammate_comment_is_not_a_requester(self):
        # SUP-1243 has an Avery Caldwell comment before Kimball Odette's; the requester spoke last.
        self.assertEqual(self.items["SUP-1243"]["lastWord"], {"who": "Kimball Odette", "date": "2026-10-21", "customer": True})

    def test_matches_prototype_item_by_item(self):
        if not PROTO.exists():
            self.skipTest("_exclude/focus_data.json not present")
        proto = {i["key"]: i for i in json.loads(PROTO.read_text())["items"]}
        for t in self.p["items"]:
            a = proto[t["key"]]
            for f in ("lane", "waitingOn", "date", "dateKind", "daysTo", "updDays", "ageDays", "gaps", "mismatch", "qa", "lastWord", "vendorRef"):
                self.assertEqual(a[f], t[f], f"{t['key']} {f}")
            if a["lane"] == "mine":
                self.assertEqual(round(float(a["score"]), 1), t["score"], t["key"])

    def test_html(self):
        html = focus.render_html(self.p, self.plan)
        self.assertNotRegex(html, r"__(DATA|TITLE|LORA|MUL\d{3}|BASE_CSS)__|/\*__|<!--__")
        self.assertEqual(html.count('<symbol id="g-'), 8)
        self.assertIn("repeat(8,1fr)", html)
        for var in ("--lane-mine:", "--ws-support:", "--today-line:"):
            self.assertIn(var, html)

    def test_how_built_reads_weights(self):
        spec = dict(self.p["spec"])
        self.assertIn("Past its date: 50 plus 0.5 per day late", spec["Next-moves score"])


class Variants(unittest.TestCase):
    def setUp(self):
        self.plan, self.raw = load()

    def test_weight_change_reorders(self):
        self.plan["focus"]["score"]["requester_waiting_per_day"] = 2
        p = focus.build_focus_report(self.plan, self.raw, TODAY)
        by = {t["key"]: t for t in p["items"]}
        self.assertEqual([(k, by[k]["score"]) for k in p["nextMoves"][:3]], [("SUP-1244", 164.0), ("SUP-930", 133.0), ("SUP-1243", 106.0)])
        self.assertIn("plus 2 per day waiting", dict(p["spec"])["Next-moves score"])

    def test_next_moves_count(self):
        self.plan["focus"]["next_moves_count"] = 3
        p = focus.build_focus_report(self.plan, self.raw, TODAY)
        self.assertEqual(p["nextMoves"], ["SUP-930", "SUP-1243", "SUP-1244"])

    def test_identity_mismatch_renders_nothing(self):
        bad = copy.deepcopy(self.raw)
        bad["focus_items"][0]["issues"][0]["fields"]["assignee"] = {"displayName": "Someone Else"}
        with self.assertRaisesRegex(qa_common.QAError, "not the profile owner Treadwell Cassidy"):
            focus.build_focus_report(self.plan, bad, TODAY)
        with tempfile.TemporaryDirectory() as d:
            raw_path, out = Path(d) / "raw.json", Path(d) / "f.html"
            raw_path.write_text(json.dumps(bad))
            r = subprocess.run([sys.executable, str(SKILL / "scripts" / "jira_report.py"), "focus-report", "--plan", str(FIX / "plan.json"),
                                "--raw", str(raw_path), "--out", str(out), "--today", "2026-10-24"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1)
            self.assertFalse(out.exists())

    def test_comments_query(self):
        q = focus.focus_comments_query(self.plan, self.raw, TODAY)
        self.assertEqual(q["jql"], "key in (SUP-930, SUP-1243, SUP-1244, SUP-1478) ORDER BY key ASC")
        self.assertEqual(q["fields"], ["comment"])
        self.plan["focus"]["comment_check_workspaces"].append("work")
        q = focus.focus_comments_query(self.plan, self.raw, TODAY)
        for k in ("TT-1403", "TT-1401", "GE-262", "GE-122"):
            self.assertIn(k, q["jql"])
        self.assertNotIn("GE-89", q["jql"])  # parked

    def test_markdown(self):
        md = focus.render_markdown(focus.build_focus_report(self.plan, self.raw, TODAY))
        self.assertIn("1. [SUP-930]", md)
        self.assertIn("## Waiting on someone else", md)
        self.assertIn("## Fix the record (9)", md)


class Validation(unittest.TestCase):
    def setUp(self):
        plan, _ = load()
        self.fc = copy.deepcopy(plan["focus"])

    def fails(self, pattern):
        with self.assertRaisesRegex(qa_common.QAError, pattern):
            focus.validate_focus_config(self.fc)

    def test_unknown_check_type(self):
        self.fc["checks"][0]["type"] = "vibes"
        self.fails("check 'od' has unknown type")

    def test_unknown_lane_rule(self):
        self.fc["lanes"]["work"]["mine_if"].append("moon_phase")
        self.fails("unknown rule 'moon_phase'")

    def test_unknown_contradiction(self):
        self.fc["contradictions"].append({"id": "nope", "workspace": "product", "text": "x"})
        self.fails("unknown id 'nope'")

    def test_bad_weight(self):
        self.fc["score"]["soon"] = "high"
        self.fails("focus.score.soon must be a number")


class Plan(unittest.TestCase):
    @unittest.skipUnless(DEFAULTS.exists(), "acos-aboutme defaults not beside this skill")
    def test_plan_from_shipped_defaults(self):
        ws = dict(json.loads(DEFAULTS.read_text())["jira_workspaces"], product=["TRM"], support=["SUP"], work=["TT", "GE"])
        prof = {"owner": {"full_name": "Example Owner"}}
        args = (ws, qa_common.resolve_fields(ws["product_fields"]), qa_common.resolve_fields(ws["support_fields"]),
                qa_common.resolve_fields(ws["work_fields"]))
        plan = focus.build_focus_plan(*args, prof, ws["cloud_id"], TODAY)
        self.assertEqual(plan["queries"][0]["jql"],
                         "project in (TRM, SUP, TT, GE) AND assignee = currentUser() AND statusCategory != Done ORDER BY project ASC, updated DESC")
        plan = focus.build_focus_plan(*args, {"owner": {"full_name": "Example Owner", "jira_account_id": "abc123"}}, ws["cloud_id"], TODAY)
        self.assertIn('assignee = "abc123"', plan["queries"][0]["jql"])
        self.assertNotIn("comment", plan["queries"][0]["fields"])


if __name__ == "__main__":
    unittest.main()
