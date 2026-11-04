#!/usr/bin/env python3
"""Tests for the Product QA report. Run from the skill directory:

    python3 -m unittest discover -s tests

The fixture in fixtures/product_qa_2026-10-23/ was reconstructed from the
prototype's _exclude/product_qa_data.json (raw.json in the fetched-issue shape, a synthesized
agenda.txt, and plan.json built from acos-aboutme's shipped defaults).
"""
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / "scripts"))

import product_qa as pq  # noqa: E402

FIX = HERE / "fixtures" / "product_qa_2026-10-23"
TODAY = date(2026, 10, 23)
DEFAULTS = SKILL.parent / "acos-aboutme" / "references" / "defaults.json"


def load():
    plan = json.loads((FIX / "plan.json").read_text())
    raw = json.loads((FIX / "raw.json").read_text())
    agenda = (FIX / "agenda.txt").read_text()
    return plan, raw, agenda


def raw_issue(raw, key):
    for v in raw.values():
        for i in pq.normalize_issues(v):
            if i["key"] == key:
                return i
    raise KeyError(key)


class FixtureAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.raw, cls.agenda = load()
        cls.p = pq.build_qa_report(cls.plan, cls.raw, cls.agenda, TODAY)
        cls.items = {i["key"]: i for i in cls.p["items"]}

    def test_matches_golden_payload(self):
        expected = json.loads((FIX / "expected_payload.json").read_text())
        self.assertEqual(json.loads(json.dumps(self.p, ensure_ascii=False)), expected)

    def test_row_counts(self):
        self.assertEqual(self.p["counts"], {"rows": 39, "overdue": 6, "soon": 28, "later": 5, "delivered": 8})
        self.assertNotIn("TRM-450", self.items)  # beyond horizon, not on the agenda

    def test_check_counts_in_config_order(self):
        self.assertEqual([c["id"] for c in self.p["checks"]], ["od", "sd", "dt", "pa", "tm", "cl", "ts", "dl"])
        self.assertEqual([c["count"] for c in self.p["checks"]], [6, 8, 18, 4, 0, 30, 32, 32])

    def test_headline(self):
        # today + horizon_days (30) is 22 Nov. The prototype said 23 Nov, a
        # 31-day horizon; the rule as specified wins. No target falls on 23 Nov,
        # so every count is unaffected.
        self.assertEqual(self.p["horizon"], "2026-11-22")
        self.assertEqual(self.p["headline"], "Six ideas are past target, and 28 more are due by 22 Nov.")
        self.assertIn("“October” target that becomes overdue on 01 Nov", self.p["subhead"])
        self.assertIn("The widest gaps are T-shirt size and delivery tickets: 32 of 39 open ideas are missing each.", self.p["subhead"])

    def test_delivered_dots(self):
        delivered = sorted(i["key"] for i in self.p["items"] if i["chartOnly"])
        self.assertEqual(delivered, ["TRM-139", "TRM-331", "TRM-382", "TRM-394", "TRM-398", "TRM-399", "TRM-403", "TRM-441"])
        self.assertTrue(all(self.items[k]["dot"] for k in delivered))

    def test_agenda_exclusions(self):
        self.assertEqual([(e["key"], e["why"]) for e in self.p["excludedAgenda"]], [
            ("TRM-161", "Roadmap Done, status Done"), ("TRM-315", "Roadmap Done"),
            ("TRM-331", "Roadmap Done, status Done"), ("TRM-366", "archived"), ("TRM-368", "archived")])
        for k in ("TRM-161", "TRM-315", "TRM-366", "TRM-368"):
            self.assertNotIn(k, self.items)

    def test_corrections(self):
        titles = [c["title"] for c in self.p["corrections"]]
        text = " ".join(c["text"] for c in self.p["corrections"])
        self.assertIn("TRM-383 appears twice", titles)
        self.assertIn("TRM-357 appears twice", titles)
        self.assertIn("“Aboz Rudu Izenifo” and “Nag Rudu Izenifo.”", text)
        self.assertIn("Listed as TRM-383; the OBI Ubomatigat to Ovav idea is TRM-385.", text)
        mismatches = [c for c in self.p["corrections"] if "label doesn’t match" in c["title"]]
        self.assertEqual(len(mismatches), 1)  # not TRM-363, not TRM-383's Amike Udic line
        self.assertIn("27 Oct: TRM-409. 03 Nov: TRM-373 and TRM-444 (unassigned, no product area).", text)
        self.assertIn("Roadmap and status disagree on TRM-315", titles)
        self.assertIn("TRM-400 has no Roadmap value", titles)

    def test_agenda_reassignment_and_meta(self):
        self.assertEqual((self.items["TRM-385"]["agenda"], self.items["TRM-385"]["featured"]), ("27 Oct", True))
        self.assertEqual((self.items["TRM-383"]["agenda"], self.items["TRM-383"]["featured"]), ("Watch", False))
        self.assertEqual(self.items["TRM-357"]["agenda"], "Holding")
        self.assertIsNone(self.items["TRM-284"]["agenda"])

    def test_rewrite_list(self):
        expect = {
            "TRM-393": "Repeated word: “tat tat.”",
            "TRM-406": "Typo: “usefullness” should be “usefulness.”",
            "TRM-295": "Typo: “enterprize” should be “enterprise.”",
            "TRM-404": "Uses a relative date (“the 7th”) that goes stale.",
            "TRM-401": "Reads as a list of workstreams, not a description of the outcome.",
            "TRM-350": "Likely grammar slip: “We are refresh.”",
            "TRM-409": "No outcome or success criterion stated.",
            "TRM-410": "Too short to stand on its own (7 words).",
        }
        for key, reason in expect.items():
            self.assertIn(reason, self.items[key]["weak"] or "", key)
        self.assertTrue(self.items["TRM-409"]["weak"].endswith(" Featured on 27 Oct."))
        self.assertIsNone(self.items["TRM-405"]["weak"])

    def test_html_has_no_placeholder_or_bad_values(self):
        html = pq.render_html(self.p, self.plan)
        self.assertNotRegex(html, r"__(DATA|TITLE|LORA|MUL\d{3})__|/\*__|<!--__")
        data = json.loads(re.search(r"const DATA = (.*?);\nconst CHECKS", html, re.S).group(1))
        for i in data["items"]:
            for v in (i["targetText"], i["deliveryText"], i["summary"]):
                self.assertNotRegex(str(v), r"undefined|NaN|\[object|^null$")
        self.assertEqual(html.count('<symbol id="g-'), 8)


class ConfigVariants(unittest.TestCase):
    def setUp(self):
        self.plan, self.raw, self.agenda = load()

    def test_disable_tshirt_check(self):
        for c in self.plan["product_qa"]["checks"]:
            if c["id"] == "ts":
                c["enabled"] = False
        p = pq.build_qa_report(self.plan, self.raw, self.agenda, TODAY)
        self.assertEqual([(c["id"], c["count"]) for c in p["checks"]],
                         [("od", 6), ("sd", 8), ("dt", 18), ("pa", 4), ("tm", 0), ("cl", 30), ("dl", 32)])
        self.assertIn("The widest gap is delivery tickets", p["subhead"])
        html = pq.render_html(p, self.plan)
        self.assertIn("repeat(4,1fr)", html)
        self.assertEqual(html.count('<symbol id="g-'), 7)
        self.assertNotIn('id="g-ts"', html)

    def test_tshirt_value_clears_flag(self):
        issue = raw_issue(self.raw, "TRM-405")
        issue["fields"][self.plan["product_fields"]["tshirt_size"]] = None
        p = pq.build_qa_report(self.plan, self.raw, self.agenda, TODAY)
        self.assertEqual(next(c["count"] for c in p["checks"] if c["id"] == "ts"), 33)

    def test_no_agenda(self):
        p = pq.build_qa_report(self.plan, self.raw, None, TODAY)
        self.assertFalse(p["hasAgenda"])
        self.assertEqual(p["counts"]["later"], 0)
        self.assertNotIn("later", [s["id"] for s in p["sections"]])
        self.assertEqual(p["corrections"], [])
        self.assertTrue(all(i["agenda"] is None and not i["featured"] for i in p["items"]))
        self.assertNotIn("Agenda corrections", pq.render_markdown(p))

    def test_ledger_columns(self):
        self.assertIn("repeat(4,1fr)", pq._ledger_css(8))
        self.assertIn("repeat(4,1fr)", pq._ledger_css(7))
        self.assertIn("repeat(3,1fr)", pq._ledger_css(5))
        self.assertIn("repeat(1,1fr)", pq._ledger_css(1))


class Validation(unittest.TestCase):
    def setUp(self):
        self.plan, _, _ = load()
        self.qa, self.pf = copy.deepcopy(self.plan["product_qa"]), self.plan["product_fields"]

    def fails(self, pattern):
        with self.assertRaisesRegex(pq.QAError, pattern):
            pq.validate_qa_config(self.qa, self.pf)

    def test_unknown_type(self):
        self.qa["checks"][1]["type"] = "nonsense"
        self.fails("check 'sd' has unknown type")

    def test_unknown_field(self):
        self.qa["checks"][1]["field"] = "no_such_field"
        self.fails("check 'sd' references unknown field key")

    def test_malformed_svg(self):
        self.qa["checks"][2]["svg"] = "<g><path></g>"
        self.fails("check 'dt' has malformed svg")

    def test_script_in_svg(self):
        self.qa["checks"][2]["svg"] = "<script>alert(1)</script>"
        self.fails("disallowed element <script>")

    def test_unknown_rewrite_rule(self):
        self.qa["rewrite_rules"]["vibes"] = {"enabled": True}
        self.fails("unknown rule 'vibes'")

    def test_bad_date_format(self):
        self.qa["date_format"] = "MM/dd/yyyy"
        self.fails("date_format")

    def test_missing_fonts(self):
        p = pq.build_qa_report(*load(), TODAY)
        with self.assertRaisesRegex(pq.QAError, "Brand fonts not found at"):
            pq.render_html(p, self.plan, fonts_dir="/nonexistent/fonts")


class RewriteRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan, _, _ = load()
        cls.rules = plan["product_qa"]["rewrite_rules"]
        data = SKILL / "_exclude" / "product_qa_data.json"
        cls.desc = {i["key"]: i["shortDesc"] for i in json.loads(data.read_text())["items"]} if data.exists() else None

    def run_rule(self, name, text, featured=False, overdue=False):
        return pq.REWRITE_RULES[name](text, self.rules[name], {"featured": featured, "overdue": overdue})

    def test_each_rule_catches_its_prototype_finding(self):
        cases = [
            ("min_words", "Edekuva the Cucotovocobu nicuhuv list to Arumazoka", {}),
            ("repeated_word", "Have all rejekabac rur do not have DUJ tat tat up DUJ for Lufi", {}),
            ("misspellings", "Gevag nugud, usefullness, and edizihiv uhizibo for aboz ukizulumobu logote in our environment.", {}),
            ("misspellings", "Ofonumuk of a itubevos fafuzi on our new enterprize AI icac", {}),
            ("relative_date", "Lanapigi any zikuni jufek from the JUB obelokof cebahap that is agiratuki the 7th.", {}),
            ("list_fragment", "Ejilafu/Lofubuv, Hamical, Lazufa Hidosenif + Vodemolojuz", {}),
            ("aux_plus_base_verb", "We are refresh ~20 epubeco", {}),
            ("no_outcome_cue", "Edekuva Nurunik with ekicod uvijot nagojema rujir our fubudubitu vum", {"featured": True}),
        ]
        for name, text, ctx in cases:
            self.assertTrue(self.run_rule(name, text, **ctx), f"{name}: {text}")

    def test_clean_descriptions_pass(self):
        clean = [
            "Karuvasu and mazepamo lohijobakuno nugud and dazozamab of Enterprise Vajuko, amer implement the hulasefuso nugud",
            "Implement ipiramo obelokof asurozok in Ulotir hofecu it is jacu visineguk to rejekabac.",
            "Gevag nugud, uvijot, and usefulness of ALA or OBI for udejodaz SILO ifodik.",
            "Otumebap urohefa for vahokivisusuc ucunetube lijahekisa to a ikoroh orizup of asuzo",
        ]
        for text in clean:
            self.assertEqual(pq.rewrite_reasons(text, self.rules, {"featured": False, "overdue": False}), [], text)

    def test_rule_edges(self):
        self.assertIsNone(self.run_rule("repeated_word", "We knew that that would happen"))
        self.assertIsNone(self.run_rule("relative_date", "Kickoff is the 7th of Nov"))
        self.assertIsNone(self.run_rule("no_outcome_cue", "Provide a list"))  # not featured or overdue
        self.assertIsNone(self.run_rule("no_outcome_cue", "Rework intake so that requests route themselves", overdue=True))
        self.assertIsNone(self.run_rule("min_words", "We are refresh ~20 epubeco and laptops for everyone"))

    def test_fixture_descriptions(self):
        if not self.desc:
            self.skipTest("_exclude/product_qa_data.json not present")
        fired = {k for k, v in self.desc.items() if v and pq.rewrite_reasons(v, self.rules, {"featured": False, "overdue": False})}
        self.assertTrue({"TRM-393", "TRM-406", "TRM-295", "TRM-404", "TRM-401", "TRM-350", "TRM-410"} <= fired)
        self.assertNotIn("TRM-405", fired)


class Helpers(unittest.TestCase):
    def test_fmt_range(self):
        self.assertEqual(pq.fmt_range(["2026-10-20", "2026-10-20"]), "20 Oct 2026")
        self.assertEqual(pq.fmt_range(["2026-10-01", "2026-10-31"]), "01–31 Oct 2026")
        self.assertEqual(pq.fmt_range(["2026-10-01", "2026-12-31"]), "01 Oct–31 Dec 2026")
        self.assertEqual(pq.fmt_range(["2026-12-01", "2027-01-31"]), "01 Dec 2026–31 Jan 2027")

    def test_parse_range(self):
        self.assertEqual(pq.parse_range('{"start":"2026-10-01","end":"2026-10-31"}'), ["2026-10-01", "2026-10-31"])
        self.assertIsNone(pq.parse_range("not json"))
        self.assertIsNone(pq.parse_range('{"start":"2026-10-01"}'))

    def test_normalize_both_page_shapes(self):
        a, b = {"key": "TRM-1"}, {"key": "TRM-2"}
        self.assertEqual(pq.normalize_issues([a, b]), [a, b])
        self.assertEqual(pq.normalize_issues({"issues": {"nodes": [a]}}), [a])
        self.assertEqual(pq.normalize_issues({"issues": [a], "isLast": True}), [a])
        self.assertEqual(pq.normalize_issues([{"issues": [a]}, {"issues": {"nodes": [b]}}]), [a, b])

    def test_label_matching(self):
        people = {"emery"}
        label = "ZAL Egilaniv R1.3 - Gipona uzizu for review 10/21 (Emery)"
        self.assertEqual(pq.clean_label(label), "ZAL Egilaniv R1.3")
        self.assertEqual(pq.clean_label("Lufi - Nurunik Aboz Educu Up"), "Lufi - Nurunik Aboz Educu Up")
        self.assertGreaterEqual(pq.containment("ZAL Egilaniv R1.3", label, people), 0.34)
        self.assertLess(pq.containment("Amike Udic Aboz Gocoseseju - Uzivi Ezep", "OBI Ubomatigat to Ovav", people), 0.34)

    def test_agenda_parser(self):
        a = pq.parse_agenda((FIX / "agenda.txt").read_text(), ["TRM"], TODAY)
        e = a["entries"]
        self.assertEqual(e[0], {"key": "TRM-363", "label": "ZAL Egilaniv R1.3 - Gipona uzizu for review 10/21, ohukoja on 990 lazufa fix (Emery)",
                                "line": 5, "section": "Watch", "date": None, "featured": False})
        self.assertEqual(next(x for x in e if x["key"] == "TRM-383")["label"], "Amike Udic Uzivi Ezep - Ruhojur by 3P")
        self.assertTrue(next(x for x in e if x["key"] == "TRM-444")["featured"])
        self.assertEqual(next(x for x in e if x["key"] == "TRM-444")["date"], "2026-11-03")
        self.assertFalse(next(x for x in e if x["key"] == "TRM-401")["featured"])
        self.assertEqual(next(x for x in e if x["key"] == "TRM-158")["section"], "Holding")
        self.assertEqual(len(e), 30)  # 3 Watch + 13 on 27 Oct + 4 on 03 Nov + 10 Holding


class Plan(unittest.TestCase):
    @unittest.skipUnless(DEFAULTS.exists(), "acos-aboutme defaults not beside this skill")
    def test_plan_from_shipped_defaults(self):
        ws = json.loads(DEFAULTS.read_text())["jira_workspaces"]
        ws = dict(ws, product=["TRM"])
        pf = dict(ws["product_fields"])
        plan = pq.build_qa_plan(ws, pf, {}, ws["cloud_id"], TODAY)
        ids = [q["id"] for q in plan["queries"]]
        self.assertEqual(ids, ["product_qa", "product_qa_delivered"])
        self.assertEqual(plan["queries"][0]["jql"],
                         'project in (TRM) AND statusCategory != Done AND "Roadmap" NOT IN ("Done", "Parking Lot", "Won\'t do", "Merged") ORDER BY key ASC')
        self.assertIn('updated >= "2026-09-01"', plan["queries"][1]["jql"])
        self.assertEqual(plan["queries"][0]["fields"][:4], ["summary", "status", "assignee", "issuelinks"])
        with_agenda = pq.build_qa_plan(ws, pf, {}, ws["cloud_id"], TODAY, (FIX / "agenda.txt").read_text())
        self.assertEqual(with_agenda["queries"][1]["id"], "product_qa_agenda")
        self.assertIn("TRM-366", with_agenda["queries"][1]["jql"])

    def test_missing_product_qa_fails(self):
        with self.assertRaisesRegex(pq.QAError, "product_qa is not configured"):
            pq.build_qa_plan({"product": ["TRM"]}, {"roadmap": "a", "idea_archived": "b", "project_target": "c"}, {}, "x", TODAY)

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "qa.md"
            r = subprocess.run([sys.executable, str(SKILL / "scripts" / "jira_report.py"), "qa-report",
                                "--plan", str(FIX / "plan.json"), "--raw", str(FIX / "raw.json"),
                                "--agenda", str(FIX / "agenda.txt"), "--format", "md", "--out", str(out),
                                "--today", "2026-10-23"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["rows"], 39)
            self.assertIn("| ID | Summary | Roadmap | Assignee | Status | Target | Delivery | QA |", out.read_text())


if __name__ == "__main__":
    unittest.main()
