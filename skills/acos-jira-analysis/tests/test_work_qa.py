#!/usr/bin/env python3
"""Tests for the Work Boards QA report. Run from the skill directory:

    python3 -m unittest discover -s tests

The fixture in fixtures/work_qa_2026-10-24/ was reconstructed from the
prototype's _exclude/work_qa_data.json: raw.json in the fetched-issue shape
(500 issues in 5 pages, unikuzoso the 5 TT netebojup the report excludes),
raw Slack directory results for the 6 non-roster assignees, a profile holding
the 12-name Technology roster, and plan.json built from acos-aboutme's
shipped defaults.
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

import qa_common  # noqa: E402
import work_qa as wq  # noqa: E402

FIX = HERE / "fixtures" / "work_qa_2026-10-24"
TODAY = date(2026, 10, 24)
DEFAULTS = SKILL.parent / "acos-aboutme" / "references" / "defaults.json"
PROTO = SKILL / "_exclude" / "work_qa_data.json"
ORDER = ["cp", "ic", "ee", "si", "bc", "ua", "od", "rp", "vr", "bh", "fe", "ot", "br"]


def load():
    return json.loads((FIX / "plan.json").read_text()), json.loads((FIX / "raw.json").read_text())


class FixtureAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.raw = load()
        cls.p = wq.build_work_report(cls.plan, cls.raw, TODAY)
        cls.v = cls.p["views"][""]
        cls.items = {t["key"]: t for t in cls.p["items"]}

    def test_matches_golden_payload(self):
        expected = json.loads((FIX / "expected_payload.json").read_text())
        self.assertEqual(json.loads(json.dumps(self.p, ensure_ascii=False)), expected)

    def test_totals(self):
        self.assertEqual(self.p["counts"]["open"], 495)
        self.assertEqual(self.p["excluded"], {"Template": 5})
        self.assertEqual({b["key"]: b["count"] for b in self.p["boards"]}, {"TT": 342, "GE": 110, "DVR": 27, "HSER": 15, "IL": 1})
        self.assertEqual(self.v["laneTotals"], {"ours": 116, "vendor": 88, "backlog": 291})

    def test_lane_buckets(self):
        # The prototype showed ours 0–30 as 24: TT-1404 was updated after noon
        # today, its day count came out -1, and the chart dropped it. The
        # report clamps day counts at zero, so it lands in 0–30.
        self.assertEqual(self.v["bucketCounts"], {"ours": [25, 25, 14, 18, 34], "vendor": [3, 3, 2, 72, 8],
                                                  "backlog": [75, 33, 29, 57, 97]})
        self.assertEqual(self.items["TT-1404"]["updDays"], 0)

    def test_check_counts(self):
        self.assertEqual([c["id"] for c in self.p["checks"]], ORDER)
        self.assertEqual([self.v["checkCounts"][k] for k in ORDER], [87, 22, 18, 91, 5, 2, 64, 5, 2, 8, 29, 3, 157])

    def test_verdicts(self):
        self.assertEqual(self.v["verdictCounts"], {"close": 121, "vendor_risk": 5, "reassign": 13, "blocked": 11,
                                                   "stalled": 60, "groom": 87, "ok": 198})

    def test_headlines(self):
        self.assertEqual(self.v["headline"], "121 open items can be closed or cleaned up now, and 91 started items haven’t moved in a month.")
        self.assertEqual(self.p["views"]["GE"]["headline"],
                         "Three open items can be closed or cleaned up now, and seven started items haven’t moved in a month.")
        self.assertIn("88 items are with Give Interactive", self.v["subhead"])

    def test_ge_release_passed(self):
        rows = sorted(k for k, t in self.items.items() if t["board"] == "GE" and t["qa"]["rp"])
        self.assertEqual(rows, ["GE-116", "GE-121", "GE-136", "GE-160", "GE-25"])

    def test_specific_items(self):
        for k in ("GE-245", "GE-262"):
            self.assertTrue(self.items[k]["qa"]["vr"], k)
        for k in ("GE-116", "GE-121"):
            self.assertTrue(self.items[k]["qa"]["rp"] and self.items[k]["qa"]["ic"], k)
            self.assertEqual(self.items[k]["verdict"], "close", k)
        tt48 = self.items["TT-48"]
        self.assertEqual(tt48["qaTips"]["cp"], "Child of a closed parent: TT-21 is ARCHIVED")
        self.assertTrue(tt48["qa"]["fe"])
        self.assertFalse(any(t["qa"]["fe"] and t["qa"]["ot"] for t in self.p["items"]))

    def test_outward_blocks_is_not_a_blocker(self):
        self.assertEqual(self.items["TT-1401"]["blockers"], [])

    def test_owner_labels(self):
        labels = self.p["ownerLabels"]
        for n in ("Acosta Ramsey", "Ambrose Talbot", "Merritt Wakefield", "Stanhope G. Nadine"):
            self.assertEqual(labels[n], "Not in Slack directory")
        for n in ("Brennan Rockwell", "Hawthorne Thornton"):
            self.assertEqual(labels[n], "Outside Technology")
        for n in ("Draper Lowell", "Emery Percival", "Jessop Yardley"):
            self.assertNotIn(n, labels)

    def test_diagnostics(self):
        titles = [f[0] for f in self.p["findings"]]
        self.assertEqual(titles, ["Vendor staleness is saturated", "Most cleanup is leftover sub-tasks", "TT is mostly backlog",
                                  "Due dates are a TT habit", "Time in status isn’t available for GE", "Fix versions aren’t used",
                                  "Departed owners still hold work", "IL barely registers"])

    def test_matches_prototype_item_by_item(self):
        if not PROTO.exists():
            self.skipTest("_exclude/work_qa_data.json not present")
        proto = {i["key"]: i for i in json.loads(PROTO.read_text())["items"]}
        for t in self.p["items"]:
            a = proto[t["key"]]
            for f in ("lane", "ageDays", "due", "parent", "ideas", "blockers", "release", "vendorRef", "qa", "verdict", "assignee"):
                self.assertEqual(a[f], t[f], f"{t['key']} {f}")
            if t["key"] != "TT-1404":
                self.assertEqual(a["updDays"], t["updDays"], t["key"])

    def test_html(self):
        html = wq.render_html(self.p, self.plan)
        self.assertNotRegex(html, r"__(DATA|TITLE|LORA|MUL\d{3}|BASE_CSS)__|/\*__|<!--__")
        self.assertEqual(html.count('<symbol id="g-'), 13)
        self.assertIn("repeat(7,1fr)", html)
        self.assertIn("--board-TT:", html)


class DirectoryVariants(unittest.TestCase):
    def setUp(self):
        self.plan, self.raw = load()

    def test_disabled(self):
        self.plan["work_qa"]["directory_check"]["enabled"] = False
        p = wq.build_work_report(self.plan, self.raw, TODAY)
        v = p["views"][""]
        self.assertEqual(p["directoryState"], "disabled")
        self.assertTrue(next(c for c in p["checks"] if c["id"] == "fe")["notRun"])
        self.assertEqual((v["checkCounts"]["fe"], v["checkCounts"]["ot"]), (0, 32))
        self.assertEqual(v["verdictCounts"], {"close": 121, "vendor_risk": 5, "reassign": 13, "blocked": 11,
                                              "stalled": 60, "groom": 87, "ok": 198})
        self.assertNotIn("Departed owners still hold work", [f[0] for f in p["findings"]])
        self.assertIn("turned off", p["footNote"])
        self.assertEqual(wq.directory_lookups(self.plan, self.raw, {}, TODAY), [])

    def test_slack_not_connected(self):
        del self.raw["directory"]
        p = wq.build_work_report(self.plan, self.raw, TODAY)
        self.assertEqual(p["directoryState"], "unavailable")
        self.assertEqual(p["views"][""]["checkCounts"]["ot"], 32)
        self.assertIn("Slack wasn’t connected", p["footNote"])
        self.assertEqual(p["ownerLabels"]["Acosta Ramsey"], "Outside Technology")

    def test_cache(self):
        self.assertEqual(len(wq.directory_lookups(self.plan, self.raw, {}, TODAY)), 6)
        cache = wq.updated_cache({}, wq.normalize_directory(self.raw["directory"]), TODAY)
        self.assertEqual(wq.directory_lookups(self.plan, self.raw, cache, TODAY), [])
        stale = wq.updated_cache({}, wq.normalize_directory(self.raw["directory"]), date(2026, 10, 10))
        self.assertEqual(len(wq.directory_lookups(self.plan, self.raw, stale, TODAY)), 6)
        # A warm cache alone satisfies the report.
        del self.raw["directory"]
        p = wq.build_work_report(self.plan, self.raw, TODAY, cache)
        self.assertEqual(p["views"][""]["checkCounts"]["fe"], 29)

    def test_lookup_shape(self):
        first = wq.directory_lookups(self.plan, self.raw, {}, TODAY)[0]
        self.assertEqual(first, {"name": "Acosta Ramsey", "tool": "slack_search_users", "query": "Acosta",
                                 "natural_language_query": "Acosta Ramsey"})

    def test_match_rule(self):
        self.assertTrue(wq.resolve_match("Jessop Yardley", ["Jessop Yardley WG/TE/DI"])["found"])
        self.assertFalse(wq.resolve_match("Stanhope G. Nadine", ["Gilmore Stanhope"])["found"])
        self.assertFalse(wq.resolve_match("Jessop Yardley", ["Jessop Wrightson"])["found"])
        self.assertTrue(wq.resolve_match("brennan rockwell", [{"display_name": "Brennan Rockwell"}])["found"])


class ConfigVariants(unittest.TestCase):
    def setUp(self):
        self.plan, self.raw = load()

    def test_disable_check_shrinks_ledger(self):
        for c in self.plan["work_qa"]["checks"]:
            if c["id"] == "od":
                c["enabled"] = False
        p = wq.build_work_report(self.plan, self.raw, TODAY)
        self.assertNotIn("od", p["views"][""]["checkCounts"])
        html = wq.render_html(p, self.plan)
        self.assertIn("repeat(6,1fr)", html)

    def test_second_vendor_is_config(self):
        self.plan["work_qa"]["vendors"]["DVR"] = {"name": "Example Vendor", "statuses": ["Consideration"]}
        p = wq.build_work_report(self.plan, self.raw, TODAY)
        dvr = [t for t in p["items"] if t["board"] == "DVR" and t["status"] == "Consideration"]
        self.assertTrue(dvr and all(t["lane"] == "vendor" and t["laneLabel"] == "With Example Vendor" for t in dvr))
        self.assertFalse(any(t["qa"]["vr"] or t["qa"]["rp"] for t in dvr))  # no ref field or pattern on that board
        self.assertIn("items are with Example Vendor", p["views"]["DVR"]["subhead"])

    def test_markdown(self):
        md = wq.render_markdown(wq.build_work_report(self.plan, self.raw, TODAY))
        self.assertIn("| ID | Board | Summary | Status | Assignee | Opened | Last update | Due | QA |", md)
        self.assertIn("## Close the loop (121)", md)


class Validation(unittest.TestCase):
    def setUp(self):
        plan, _ = load()
        self.wq, self.wf, self.keys = copy.deepcopy(plan["work_qa"]), plan["work_fields"], plan["work_keys"]

    def fails(self, pattern):
        with self.assertRaisesRegex(qa_common.QAError, pattern):
            wq.validate_work_config(self.wq, self.wf, self.keys)

    def test_unknown_type(self):
        self.wq["checks"][0]["type"] = "vibes"
        self.fails("check 'cp' has unknown type")

    def test_unknown_lane(self):
        self.wq["verdicts"][4]["when"] = ["si@elsewhere"]
        self.fails("unknown lane 'elsewhere'")

    def test_unknown_vendor_board(self):
        self.wq["vendors"]["ZZ"] = {"name": "X", "statuses": []}
        self.fails("unknown board 'ZZ'")

    def test_unknown_ref_field(self):
        self.wq["vendors"]["GE"]["ticket_ref_field"] = "nope"
        self.fails("ticket_ref_field 'nope'")

    def test_malformed_svg(self):
        self.wq["checks"][2]["svg"] = "<g><path></g>"
        self.fails("check 'ee' has malformed svg")


class Plan(unittest.TestCase):
    @unittest.skipUnless(DEFAULTS.exists(), "acos-aboutme defaults not beside this skill")
    def test_plan_from_shipped_defaults(self):
        ws = dict(json.loads(DEFAULTS.read_text())["jira_workspaces"], work=["TT", "GE", "DVR", "HSER", "IL"])
        plan = wq.build_work_plan(ws, qa_common.resolve_fields(ws["work_fields"]),
                                  {"owner": {"full_name": "Example Owner"}, "team": [{"name": "Emery Example"}]}, ws["cloud_id"], TODAY)
        q = plan["queries"][0]
        self.assertEqual(q["jql"], "project in (TT, GE, DVR, HSER, IL) AND statusCategory != Done ORDER BY project ASC, created ASC")
        self.assertIn("customfield_10071", q["fields"])
        self.assertNotIn("Template", q["jql"])
        self.assertEqual(plan["roster"], ["Emery Example", "Example Owner"])
        self.assertEqual(plan["timezone"], "America/Chicago")
        self.assertIn("board_IL", plan["palette"])

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            out, cache = Path(d) / "w.md", Path(d) / "cache.json"
            r = subprocess.run([sys.executable, str(SKILL / "scripts" / "jira_report.py"), "work-qa-report",
                                "--plan", str(FIX / "plan.json"), "--raw", str(FIX / "raw.json"), "--format", "md",
                                "--out", str(out), "--cache", str(cache), "--today", "2026-10-24"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["close"], 121)
            self.assertEqual(len(json.loads(cache.read_text())), 6)
            r = subprocess.run([sys.executable, str(SKILL / "scripts" / "jira_report.py"), "work-qa-lookups",
                                "--plan", str(FIX / "plan.json"), "--raw", str(FIX / "raw.json"), "--cache", str(cache),
                                "--today", "2026-10-24"], capture_output=True, text=True)
            self.assertEqual(json.loads(r.stdout)["lookups"], [])


if __name__ == "__main__":
    unittest.main()
