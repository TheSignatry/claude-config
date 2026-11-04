#!/usr/bin/env python3
"""Tests for the other-department rule, the recurring-series signal, the 5c
name fallback, and intentional overlaps. Run from the skill directory:

    python3 -m unittest discover -s tests

Every person, address, and subject here is synthetic. Event ids are built
in the two Exchange shapes `_series_occurrence` reads: a header of 0x0009
then 0x01 for a series occurrence, 0x00 for a single item.
"""
import base64
import itertools
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))

import calendar_report as cr  # noqa: E402

OWNER = "owner@example.org"
_ids = itertools.count(1)


def _id(occurrence):
    head = b"\x00\x09\x01\x39" if occurrence else b"\x00\x09\x00\x2e"
    body = next(_ids).to_bytes(4, "big") * 8
    return base64.urlsafe_b64encode(head + body).decode()


def event(subject, attendees, occurrence=False, start="2026-11-04T10:00:00", end="2026-11-04T11:00:00", eid=None):
    return {
        "id": eid or _id(occurrence),
        "subject": subject,
        "organizer": OWNER,
        "attendees": [OWNER] + attendees,
        "start": {"dateTime": start, "timeZone": "Central Standard Time"},
        "end": {"dateTime": end, "timeZone": "Central Standard Time"},
        "showAs": "busy",
        "isAllDay": False,
        "isCancelled": False,
    }


def profile(owner_areas=("Systems", "Engineering")):
    return {
        "owner": {"email": OWNER, "functional_areas": list(owner_areas)},
        "staff": [{"name": "Staff Person", "email": "staff@example.org", "role": "Analyst"}],
        "reports": [{"name": "Report One", "email": "report1@example.org"}],
        "team": [{"name": "Report One", "email": "report1@example.org"}],
        "functional_areas": {
            "Finance": [{"name": "Fin One", "email": "fin1@example.org"},
                        {"name": "Fin Two", "email": "fin2@example.org"}],
            "Engineering": [{"name": "Eng One", "email": "eng1@example.org"}],
            "Systems": [{"name": "Sys One", "email": "sys1@example.org"}],
            "Revenue": [{"name": "Rev One", "email": "rev1@example.org"}],
        },
        "calendar_analysis": {
            "intentional_overlaps": [
                {"name": "Paired retros", "match_patterns": ["alpha retro", "beta retro"]},
            ],
        },
    }


def classify(ev, prof=None):
    return cr.classify_primary_category(ev, cr.build_lookups(prof or profile()))


class SeriesOccurrenceTest(unittest.TestCase):
    def test_shapes(self):
        self.assertIs(cr._series_occurrence({"id": _id(True)}), True)
        self.assertIs(cr._series_occurrence({"id": _id(False)}), False)

    def test_unknown_shapes_return_none(self):
        for eid in ("", "not-base64!!", base64.urlsafe_b64encode(b"\x00\x08\x01xyz").decode(),
                    base64.urlsafe_b64encode(b"\x00\x09\x07xyz").decode()):
            self.assertIsNone(cr._series_occurrence({"id": eid}), eid)


class OtherDepartmentRuleTest(unittest.TestCase):
    def test_one_off_finance_meeting_is_stakeholder_partnership(self):
        r = classify(event("Ticket 123 discussion", ["fin1@example.org", "fin2@example.org"]))
        self.assertEqual(r["category"], "Stakeholder partnership")
        self.assertFalse(r["needs_llm"])
        self.assertIn("one-off", r["reason"])

    def test_recurring_finance_meeting_is_operating_rhythm(self):
        r = classify(event("Finance sync", ["fin1@example.org", "fin2@example.org"], occurrence=True))
        self.assertEqual(r["category"], "Operating rhythm")
        self.assertIn("recurring", r["reason"])

    def test_untagged_attendee_with_other_department_still_counts(self):
        r = classify(event("Planning", ["fin1@example.org", "nobody@example.org"]))
        self.assertEqual(r["category"], "Stakeholder partnership")

    def test_only_owner_areas_does_not_fire(self):
        r = classify(event("Eng chat", ["eng1@example.org", "nobody@example.org"]))
        self.assertTrue(r["needs_llm"])

    def test_off_when_owner_areas_unset(self):
        r = classify(event("Ticket 123 discussion", ["fin1@example.org"]), profile(owner_areas=()))
        self.assertTrue(r["needs_llm"])

    def test_unknown_id_falls_through_to_judgment(self):
        r = classify(event("Ticket 123 discussion", ["fin1@example.org"], eid="opaque-id"))
        self.assertTrue(r["needs_llm"])

    def test_fires_only_when_another_department_is_present(self):
        r = classify(event("Team sync", ["report1@example.org", "sys1@example.org"]))
        self.assertNotIn("other department", r["reason"])
        r = classify(event("Joint sync", ["report1@example.org", "fin1@example.org"]))
        self.assertIn("other department", r["reason"])


class NameFallbackTest(unittest.TestCase):
    def test_directory_name_used_when_not_in_staff(self):
        lookups = cr.build_lookups(profile())
        d = cr._describe_participant("fin1@example.org", lookups)
        self.assertEqual(d["name"], "Fin One")
        self.assertIsNone(d["role"])
        self.assertEqual(d["functional_areas"], ["Finance"])

    def test_staff_entry_wins(self):
        lookups = cr.build_lookups(profile())
        d = cr._describe_participant("staff@example.org", lookups)
        self.assertEqual((d["name"], d["role"]), ("Staff Person", "Analyst"))


class IntentionalOverlapTest(unittest.TestCase):
    def _conflicts(self, subj_a, subj_b):
        a = event(subj_a, ["report1@example.org"], start="2026-11-06T09:30:00", end="2026-11-06T10:30:00")
        b = event(subj_b, ["report1@example.org"], start="2026-11-06T09:30:00", end="2026-11-06T10:30:00")
        lookups = cr.build_lookups(profile())
        return cr.detect_conflicts([(a, "Operating rhythm"), (b, "Operating rhythm")],
                                   lookups["intentional_overlaps"])

    def test_declared_pair_is_not_a_double_booking(self):
        c = self._conflicts("Alpha Retro", "Beta Retro")
        self.assertEqual(c["double_bookings"], [])
        self.assertEqual([o["series"] for o in c["intentional_overlaps"]], ["Paired retros"])

    def test_one_sided_match_is_still_flagged(self):
        c = self._conflicts("Alpha Retro", "Vendor call")
        self.assertEqual(len(c["double_bookings"]), 1)
        self.assertEqual(c["intentional_overlaps"], [])


if __name__ == "__main__":
    unittest.main()
