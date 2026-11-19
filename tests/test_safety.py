"""The safety net: one run may not close many open tenders at once."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot import main  # noqa: E402

AT = datetime(2026, 11, 19, 14, 0)


def shelf(n, start=1):
    return {i: {"id": i, "status": "open", "status_text": "Հրապարակված", "end": "2026-11-26T10:00"}
            for i in range(start, start + n)}


def snapshot(tenders):
    return {i: (t.get("status"), t.get("status_text"), t.get("gone")) for i, t in tenders.items()}


def close(tenders, ids):
    for i in ids:
        tenders[i].update(status="other", gone="2026-11-19T14:00")


class SafetyNetTest(unittest.TestCase):
    def test_many_closed_at_once_stay_open(self):
        tenders = shelf(400)
        before = snapshot(tenders)
        close(tenders, range(1, 223))
        said = []
        held = main.hold_sudden_closing(tenders, before, AT, set(), say=said.append)
        self.assertEqual(len(held), 222)
        self.assertTrue(all(t["status"] == "open" and "gone" not in t for t in tenders.values()))
        self.assertIn("Safety net", said[0])

    def test_a_second_run_closing_the_same_is_believed(self):
        tenders = shelf(400)
        before = snapshot(tenders)
        close(tenders, range(1, 101))
        held = main.hold_sudden_closing(tenders, before, AT, set(range(1, 101)), say=lambda *_: None)
        self.assertEqual(held, set())
        self.assertEqual(tenders[1]["status"], "other")

    def test_a_few_closed_is_normal(self):
        tenders = shelf(400)
        before = snapshot(tenders)
        close(tenders, range(1, 11))
        self.assertEqual(main.hold_sudden_closing(tenders, before, AT, set(), say=lambda *_: None), set())
        self.assertEqual(tenders[1]["status"], "other")

    def test_deadlines_that_passed_do_not_count(self):
        tenders = shelf(100)
        before = snapshot(tenders)
        for t in tenders.values():                     # every deadline moved into the past: not a sudden drop
            t["end"] = "2026-11-19T12:00"
        self.assertEqual(main.hold_sudden_closing(tenders, before, AT, set(), say=lambda *_: None), set())

    def test_status_text_comes_back_as_it_was(self):
        tenders = shelf(100)
        before = snapshot(tenders)
        for t in tenders.values():
            t.update(status="cancelled", status_text="Չեղարկված")
        main.hold_sudden_closing(tenders, before, AT, set(), say=lambda *_: None)
        self.assertEqual((tenders[5]["status"], tenders[5]["status_text"]), ("open", "Հրապարակված"))


if __name__ == "__main__":
    unittest.main()
