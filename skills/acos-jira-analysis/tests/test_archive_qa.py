#!/usr/bin/env python3
"""Tests for the Archive QA report and the standard report's archived-idea
filter. Run from the skill directory:

    python3 -m unittest discover -s tests

All ideas and names here are synthetic. The plan is built from acos-aboutme's
shipped defaults, so a change to archive_qa there shows up here.
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

import archive_qa as aq  # noqa: E402
import jira_report  # noqa: E402
from qa_common import QAError  # noqa: E402

TODAY = date(2026, 11, 1)
DEFAULTS = SKILL.parent / "acos-aboutme" / "references" / "defaults.json"
FONTS = SKILL.parent / "signatry-brand-core" / "assets" / "fonts"
CAT = {"Parking lot": ("new", "To Do"), "In Progress": ("indeterminate", "In Progress"),
       "Done": ("done", "Done"), "CANCELED": ("done", "Done")}


def workspaces():
    ws = json.loads(DEFAULTS.read_text())["jira_workspaces"]
    return dict(ws, product=["TRM"])


def idea(key, roadmap, status, who="Pat Quill", archived=True, end="2026-10-31"):
    pf = jira_report.DEFAULT_PRODUCT_FIELDS
    ck, cn = CAT[status]
    return {"key": key, "webUrl": f"https://example.atlassian.net/browse/{key}", "fields": {
        "summary": f"Idea {key}", "status": {"name": status, "statusCategory": {"key": ck, "name": cn}},
        "assignee": {"displayName": who} if who else None, "updated": "2026-10-02T09:00:00.000-0500",
        pf["roadmap"]: {"value": roadmap} if roadmap else None,
        pf["project_target"]: json.dumps({"start": "2026-10-01", "end": end}) if end else None,
        pf["idea_archived"]: {"value": "Yes"} if archived else None}}


IDEAS = [
    idea("TRM-1", "Now", "In Progress"),                 # both open
    idea("TRM-2", None, "Parking lot", who=None),        # both open, empty roadmap
    idea("TRM-3", "Parking Lot", "Parking lot"),         # both open: Parking Lot is not concluding
    idea("TRM-4", "Won't do", "Parking lot", who="Lee Marsh"),  # status only
    idea("TRM-5", "Done", "Parking lot"),                # status only
    idea("TRM-6", "Next", "Done", who="Lee Marsh"),      # roadmap only
    idea("TRM-7", "Merged", "CANCELED"),                 # concluded
    idea("TRM-8", "Done", "Done", end=None),             # concluded
    idea("TRM-9", "Now", "In Progress", archived=False),  # not archived: dropped
]


@unittest.skipUnless(DEFAULTS.exists(), "acos-aboutme defaults not beside this skill")
class ArchivePlan(unittest.TestCase):
    def test_plan_from_shipped_defaults(self):
        plan = aq.build_archive_plan(workspaces(), jira_report.resolve_product_fields(workspaces()), "example.atlassian.net")
        q = plan["queries"][0]
        self.assertEqual(q["id"], "archive_qa")
        self.assertEqual(q["jql"], "project in (TRM) AND cf[10261] is not EMPTY ORDER BY key ASC")
        self.assertIn("customfield_10261", q["fields"])
        self.assertEqual(plan["archive_qa"]["concluding_roadmap"], ["Done", "Won't do", "Merged"])

    def test_config_errors(self):
        ws = workspaces()
        pf = jira_report.resolve_product_fields(ws)
        bad = copy.deepcopy(ws)
        bad["archive_qa"]["checks"][0]["type"] = "nope"
        with self.assertRaisesRegex(QAError, "unknown type 'nope'"):
            aq.build_archive_plan(bad, pf, "x")
        bad = copy.deepcopy(ws)
        bad["archive_qa"]["concluding_roadmap"] = []
        with self.assertRaisesRegex(QAError, "concluding_roadmap must be a non-empty list"):
            aq.build_archive_plan(bad, pf, "x")
        with self.assertRaisesRegex(QAError, "not a customfield_N id"):
            aq.build_archive_plan(ws, dict(pf, idea_archived="archived"), "x")
        with self.assertRaisesRegex(QAError, "has no project keys"):
            aq.build_archive_plan(dict(ws, product=[]), pf, "x")


@unittest.skipUnless(DEFAULTS.exists(), "acos-aboutme defaults not beside this skill")
class ArchiveReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ws = workspaces()
        cls.plan = aq.build_archive_plan(ws, jira_report.resolve_product_fields(ws), "example.atlassian.net")
        cls.p = aq.build_archive_report(cls.plan, {"archive_qa": IDEAS}, TODAY)
        cls.by = {i["key"]: i for i in cls.p["items"]}

    def test_sections_and_counts(self):
        self.assertNotIn("TRM-9", self.by)
        self.assertEqual(self.p["counts"], {"archived": 8, "flagged": 6, "both": 3, "roadmap": 1, "status": 2, "clear": 2})
        self.assertEqual({k: i["section"] for k, i in self.by.items()},
                         {"TRM-1": "both", "TRM-2": "both", "TRM-3": "both", "TRM-4": "status",
                          "TRM-5": "status", "TRM-6": "roadmap", "TRM-7": "clear", "TRM-8": "clear"})
        self.assertEqual([c["count"] for c in self.p["checks"]], [4, 5])

    def test_rule_text_fills_values(self):
        self.assertEqual(self.p["checks"][0]["rule"], "Roadmap is empty, or not Done, Won't do, or Merged.")
        self.assertEqual(self.p["checks"][1]["rule"], "Status is not in a Done category.")

    def test_headline_and_tips(self):
        self.assertEqual(self.p["headline"], "6 of 8 archived ideas still read as live work.")
        self.assertEqual(self.p["subhead"], "3 have neither a concluding Roadmap value nor a closed status, "
                                            "1 only needs the Roadmap value set, and 2 only need the status closed.")
        self.assertEqual(self.by["TRM-2"]["qaTips"]["rm"], "Roadmap is empty")
        self.assertEqual(self.by["TRM-1"]["qaTips"]["so"], "Status is In Progress (In Progress)")

    def test_owners(self):
        rows = {o["name"]: o for o in self.p["owners"]}
        self.assertEqual(rows["Pat Quill"], {"name": "Pat Quill", "archived": 5, "flagged": 3, "rm": 2, "so": 3})
        self.assertEqual(rows["Unassigned"]["flagged"], 1)

    def test_disabled_check_moves_ideas_toward_concluded(self):
        plan = copy.deepcopy(self.plan)
        plan["archive_qa"]["checks"][1]["enabled"] = False
        p = aq.build_archive_report(plan, {"archive_qa": IDEAS}, TODAY)
        self.assertEqual(p["counts"], {"archived": 8, "flagged": 4, "both": 0, "roadmap": 4, "status": 0, "clear": 4})

    def test_all_concluded(self):
        p = aq.build_archive_report(self.plan, {"archive_qa": IDEAS[6:8]}, TODAY)
        self.assertEqual(p["headline"], "All 2 archived ideas rest in a concluding state.")

    def test_markdown(self):
        md = aq.render_markdown(self.p)
        self.assertIn("## Neither concluded (3)", md)
        self.assertIn("| [TRM-2](https://example.atlassian.net/browse/TRM-2) | Idea TRM-2 | _empty_ | Parking lot |", md)
        self.assertIn("## Needs a Roadmap value (1)", md)
        self.assertIn("## Needs the status closed (2)", md)

    @unittest.skipUnless(FONTS.is_dir(), "signatry-brand-core fonts not beside this skill")
    def test_cli_html(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "plan.json").write_text(json.dumps(self.plan))
            (d / "raw.json").write_text(json.dumps({"archive_qa": IDEAS}))
            r = subprocess.run([sys.executable, str(SKILL / "scripts" / "jira_report.py"), "archive-qa-report",
                                "--plan", str(d / "plan.json"), "--raw", str(d / "raw.json"), "--out", str(d / "a.html"),
                                "--today", "2026-11-01"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["flagged"], 6)
            html = (d / "a.html").read_text()
            self.assertIn("<title>Archive QA (TRM), 01 Nov 2026</title>", html)
            self.assertIn('<symbol id="g-rm"', html)
            self.assertNotIn("__DATA__", html)


class StandardReportArchivedFilter(unittest.TestCase):
    PF = jira_report.DEFAULT_PRODUCT_FIELDS

    def plan(self, **kw):
        return {"window_days": 14, "groups": {"product": ["TRM"], "support": [], "work": []},
                "product_fields": dict(self.PF), "since": kw.get("since"), "until": kw.get("until")}

    def test_archived_ideas_are_dropped_everywhere(self):
        raw = {
            "product": [idea("TRM-1", "Now", "In Progress"), idea("TRM-9", "Now", "In Progress", archived=False)],
            "product_detail": [idea("TRM-1", "Now", "In Progress"), idea("TRM-9", "Now", "In Progress", archived=False)],
            "product_delivered": [idea("TRM-5", "Done", "Done"), idea("TRM-8", "Done", "Done", archived=False)],
        }
        r = jira_report.build_report(self.plan(since="2026-10-01", until="2026-10-31"), raw, today=TODAY)
        self.assertEqual(r["summary"][0]["overdue"], 1)
        self.assertEqual([d["key"] for d in r["product_detail"]], ["TRM-9"])
        self.assertEqual([d["key"] for d in r["delivered_in_range"]["items"]], ["TRM-8"])

    def test_plan_without_archived_field_does_not_filter(self):
        plan = self.plan()
        del plan["product_fields"]["idea_archived"]
        r = jira_report.build_report(plan, {"product_detail": [idea("TRM-1", "Now", "In Progress")]}, today=TODAY)
        self.assertEqual([d["key"] for d in r["product_detail"]], ["TRM-1"])

    @unittest.skipUnless(DEFAULTS.exists(), "acos-aboutme defaults not beside this skill")
    def test_product_queries_fetch_the_archived_field_and_skip_merged(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "state" / "profile.json"
            prof.parent.mkdir()
            prof.write_text(json.dumps({"jira_workspaces": {"product": ["TRM"], "support": [], "work": []}}))
            # load_acos_profile reads ../references/defaults.json beside the profile's state folder.
            (Path(d) / "references").mkdir()
            (Path(d) / "references" / "defaults.json").write_text(DEFAULTS.read_text())
            plan = jira_report.build_plan(str(prof), None, since="2026-10-01", until="2026-10-31")
        qs = {q["id"]: q for q in plan["queries"]}
        for qid in ("product", "product_detail", "product_delivered"):
            self.assertIn("customfield_10261", qs[qid]["fields"], qid)
        self.assertIn('"Roadmap" NOT IN ("Done", "Parking Lot", "Merged")', qs["product_detail"]["jql"])


if __name__ == "__main__":
    unittest.main()
