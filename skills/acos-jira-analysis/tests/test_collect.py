#!/usr/bin/env python3
"""Tests for `jira_report.py collect`. Run from the skill directory:

    python3 -m unittest discover -s tests

All pages here are synthetic: a few bare issue nodes in each of the two shapes
searchJiraIssuesUsingJql has returned, plus the content-block wrapper some
hosts use when they save an oversized result to a file.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / "scripts"))

import jira_report  # noqa: E402
from jira_report import CollectError, collect_pages  # noqa: E402

PLAN = {"queries": [{"id": "product_qa"}, {"id": "product_qa_delivered"}]}


def issue(key):
    return {"key": key, "webUrl": f"https://example.atlassian.net/browse/{key}", "fields": {"summary": f"Idea {key}"}}


def nodes_page(keys, more=False):
    return json.dumps({"issues": {"nodes": [issue(k) for k in keys], "pageInfo": {"hasNextPage": more, "endCursor": "c" if more else None}},
                      "context": {"toolName": "searchJiraIssuesUsingJql"}})


def flat_page(keys, more=False):
    page = {"issues": [issue(k) for k in keys], "isLast": not more}
    if more:
        page["nextPageToken"] = "t"
    return json.dumps(page)


def keys_of(raw, qid):
    return [i["key"] for i in raw[qid]]


class CollectPages(unittest.TestCase):
    def test_nodes_shape_joins_pages_in_order(self):
        raw = collect_pages([("product_qa", nodes_page(["TRM-1", "TRM-2"], more=True), "a"),
                             ("product_qa", nodes_page(["TRM-3"]), "b"),
                             ("product_qa_delivered", nodes_page(["TRM-9"]), "c")], PLAN)
        self.assertEqual(keys_of(raw, "product_qa"), ["TRM-1", "TRM-2", "TRM-3"])
        self.assertEqual(keys_of(raw, "product_qa_delivered"), ["TRM-9"])
        self.assertEqual(raw["product_qa"][0], issue("TRM-1"))  # nodes pass through unchanged

    def test_flat_shape(self):
        raw = collect_pages([("product_qa", flat_page(["TRM-1"], more=True), "a"),
                             ("product_qa", flat_page(["TRM-2"]), "b"),
                             ("product_qa_delivered", flat_page([]), "c")], PLAN)
        self.assertEqual(keys_of(raw, "product_qa"), ["TRM-1", "TRM-2"])
        self.assertEqual(raw["product_qa_delivered"], [])

    def test_flat_shape_token_without_islast(self):
        page = json.dumps({"issues": [issue("TRM-1")], "nextPageToken": "t"})
        with self.assertRaisesRegex(CollectError, "more pages follow"):
            collect_pages([("product_qa", page, "a")])

    def test_content_block_wrapper(self):
        wrapped = json.dumps([{"type": "text", "text": nodes_page(["TRM-1"])}])
        self.assertEqual(keys_of(collect_pages([("product_qa", wrapped, "a")]), "product_qa"), ["TRM-1"])

    def test_last_page_with_more_fails(self):
        with self.assertRaisesRegex(CollectError, "product_qa.*more pages follow"):
            collect_pages([("product_qa", nodes_page(["TRM-1"], more=True), "a"),
                           ("product_qa_delivered", nodes_page([]), "b")], PLAN)

    def test_missing_plan_query_fails(self):
        with self.assertRaisesRegex(CollectError, "No pages given for product_qa_delivered"):
            collect_pages([("product_qa", nodes_page(["TRM-1"]), "a")], PLAN)

    def test_unknown_query_id_fails(self):
        with self.assertRaisesRegex(CollectError, "product_q, which the plan does not list"):
            collect_pages([("product_q", nodes_page(["TRM-1"]), "a"),
                           ("product_qa", nodes_page([]), "b"),
                           ("product_qa_delivered", nodes_page([]), "c")], PLAN)

    def test_not_a_search_result_fails(self):
        with self.assertRaisesRegex(CollectError, "no `issues`"):
            collect_pages([("product_qa", json.dumps({"error": "nope"}), "a")])
        with self.assertRaisesRegex(CollectError, "is not JSON"):
            collect_pages([("product_qa", "Error: result exceeds maximum allowed tokens", "a")])

    def test_merge_keeps_base_and_counts_it_for_the_plan(self):
        base = {"product_qa": [issue("TRM-1")], "directory": {"Pat": {"results": []}}}
        raw = collect_pages([("product_qa_delivered", nodes_page(["TRM-9"]), "a")], PLAN, base)
        self.assertEqual(keys_of(raw, "product_qa"), ["TRM-1"])
        self.assertEqual(raw["directory"], base["directory"])
        self.assertEqual(keys_of(raw, "product_qa_delivered"), ["TRM-9"])


class CollectCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SKILL / "scripts" / "jira_report.py"), "collect", *args],
                              capture_output=True, text=True)

    def test_writes_raw_and_merges_second_stage(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "p1.txt").write_text(nodes_page(["TRM-1", "TRM-2"]))
            (d / "p2.txt").write_text(flat_page(["TRM-9"]))
            (d / "c.txt").write_text(flat_page(["TRM-1"]))
            (d / "plan.json").write_text(json.dumps(PLAN))
            out = d / "raw.json"
            r = self.run_cli("--plan", str(d / "plan.json"), "--page", f"product_qa={d / 'p1.txt'}",
                             "--page", f"product_qa_delivered={d / 'p2.txt'}", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["issues"], {"product_qa": 2, "product_qa_delivered": 1})
            r = self.run_cli("--merge", "--page", f"focus_comments={d / 'c.txt'}", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(sorted(json.loads(out.read_text())), ["focus_comments", "product_qa", "product_qa_delivered"])

    def test_bad_page_spec_fails_with_json_error(self):
        r = self.run_cli("--page", "product_qa", "--out", "unused.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("must be <query id>=<path>", json.loads(r.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
