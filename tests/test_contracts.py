"""Offline checks of the contracts reader. The register is a stand-in that answers from a list."""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import contracts  # noqa: E402


def stamp(d: date) -> int:
    """Midnight in Yerevan, as the register stamps a day."""
    return int((datetime(d.year, d.month, d.day, tzinfo=timezone.utc) - timedelta(hours=4)).timestamp() * 1000)


def contract(i: int, d: date, supplier="«ՕՐԻՆԱԿ» ՍՊԸ", tin="01234567") -> dict:
    return {"id": f"{i:08d}-aaaa-bbbb-cccc-000000000000", "number": f"ԵՔ-ԷԱՃԾՁԲ-26/{i}", "dateSigned": stamp(d),
            "deadline": stamp(d + timedelta(days=30)), "contractValue": 1000.0 * i, "contractValueTotal": 1000.0 * i,
            "latestValue": 1000.0 * i, "procurementSubject": "  միջոցառման   կազմակերպում ", "tenderCode": f"ԵՔ-ԷԱՃԾՁԲ-26/{i}",
            "formAbbrHy": "ԷԱՃ", "tenderProcurementType": "SERVICES", "authorityNameHy": "Երևանի քաղաքապետարան",
            "authorityTin": "02500052", "supplierName": supplier, "supplierTaxpayerId": tin,
            "supplierId": "48c888df-0f6a-4722-bf1b-299ce868b389", "supplierEmail": "someone@example.com",
            "bankAccountInfo": "1570000000000000", "tenderArmepsUserName": "someone", "contractSaving": 250.0,
            "tenderSupplierList": "3d953a28-c76e-4a0d-8b6f-2c820f7bd9c5|48c888df-0f6a-4722-bf1b-299ce868b389", "state": "ACTIVE"}


class Register:
    """Answers `count` and `list` like the register. With `shift`, the second page going forward repeats the first,
    as an order that shifts between pages can make it."""

    def __init__(self, rows, shift=False):
        self.rows, self.shift, self.asked = rows, shift, []

    def __call__(self, path, body):
        f = body["filter"]["dateSigned"]
        lo, hi = f["min"][:10], f["max"][:10]
        hit = [c for c in self.rows if lo <= contracts.day(c["dateSigned"]) <= hi]
        if path == "count":
            self.asked.append(("count", lo))
            return len(hit)
        i, size, up = body["page"]["index"], body["page"]["size"], body["order"]["ascending"]
        self.asked.append(("list" if up else "back", lo, i))
        if not up:
            hit = hit[::-1]
        elif self.shift and i == 1:
            i = 0
        return hit[i * size:(i + 1) * size]


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.was, contracts.STATE = contracts.STATE, self.tmp.name
        self.page, contracts.PAGE = contracts.PAGE, 4

    def tearDown(self):
        contracts.STATE, contracts.PAGE = self.was, self.page
        self.tmp.cleanup()

    def test_only_the_contract_is_kept_not_the_bank_account_or_the_address(self):
        row = contracts.slim(contract(7, date(2026, 11, 16)))
        self.assertEqual(row["d"], "2026-11-16")
        self.assertEqual((row["sn"], row["st"], row["b"], row["v"], row["f"], row["k"]),
                         ("«Օրինակ» ՍՊԸ", "01234567", "Երևանի քաղաքապետարան", 7000.0, "ԷԱՃ", "s"))
        self.assertEqual(row["s"], "միջոցառման կազմակերպում")
        self.assertEqual(row["ps"], ["3d953a28c7", "48c888df0f"])
        text = json.dumps(row, ensure_ascii=False)
        for secret in ("1570000000000000", "example.com", "someone"):
            self.assertNotIn(secret, text)
        self.assertNotIn("lv", row)                        # the same as the total: not repeated

    def test_a_sole_proprietor_keeps_the_name_and_loses_the_tax_number(self):
        row = contracts.slim(contract(8, date(2026, 11, 16), supplier="ԱՐՄԵՆ ՕՐԻՆԱԿՅԱՆ ՍԱՄՎԵԼԻ Ա/Ձ", tin="43119505"))
        self.assertEqual(row.get("p"), 1)
        self.assertNotIn("st", row)
        self.assertNotIn("43119505", json.dumps(row))

    def test_a_day_is_one_question_and_a_full_page_asks_for_the_next(self):
        rows = [contract(i, date(2026, 11, 2)) for i in range(1, 4)] + [contract(i, date(2026, 11, 3)) for i in range(4, 10)]
        reg = Register(rows)
        got = contracts.read_days(date(2026, 11, 1), date(2026, 11, 3), reg, pause=0)
        self.assertEqual(len(got), 9)
        self.assertEqual(reg.asked, [("list", "2026-11-01", 0), ("list", "2026-11-02", 0), ("list", "2026-11-03", 0),
                                     ("list", "2026-11-03", 1), ("count", "2026-11-03")])

    def test_a_long_day_whose_pages_shifted_is_read_from_the_other_end_too(self):
        rows = [contract(i, date(2026, 11, 3)) for i in range(1, 8)]              # two pages of four
        reg = Register(rows, shift=True)
        got = contracts.read_day(date(2026, 11, 3), reg, pause=0)
        self.assertEqual(len(got), 7)
        self.assertIn(("back", "2026-11-03", 0), reg.asked)

    def test_whole_months_are_stored_one_contract_a_line(self):
        rows = ([contract(i, date(2026, 10, 30)) for i in range(1, 4)] + [contract(i, date(2026, 11, 2)) for i in range(4, 9)])
        said = []
        contracts.say, keep = said.append, contracts.say
        try:
            self.assertEqual(contracts.run(20, today=date(2026, 11, 17), ask=Register(rows), pause=0), 0)
        finally:
            contracts.say = keep
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["2026-10.jsonl", "2026-11.jsonl"])
        self.assertEqual(len(contracts.load_month("2026-10")), 3)
        self.assertEqual(len(contracts.load_month("2026-11")), 5)
        with open(contracts.month_file("2026-11"), encoding="utf-8") as fh:
            self.assertEqual([json.loads(line)["n"] for line in fh][:2], ["ԵՔ-ԷԱՃԾՁԲ-26/4", "ԵՔ-ԷԱՃԾՁԲ-26/5"])

    def test_a_month_that_comes_back_nearly_empty_is_not_believed(self):
        rows = [contract(i, date(2026, 11, 2)) for i in range(1, 9)]
        contracts.say, keep = (lambda text: None), contracts.say
        try:
            contracts.run(10, today=date(2026, 11, 17), ask=Register(rows), pause=0)
            contracts.run(10, today=date(2026, 11, 17), ask=Register(rows[:2]), pause=0)
        finally:
            contracts.say = keep
        self.assertEqual(len(contracts.load_month("2026-11")), 8)

    def test_newest_month_first_and_long_closed_months_are_not_read_twice(self):
        rows = [contract(1, date(2026, 6, 10)), contract(2, date(2026, 10, 20)), contract(3, date(2026, 11, 5))]
        said = []
        contracts.say, keep = said.append, contracts.say
        try:
            contracts.run(200, today=date(2026, 11, 17), ask=Register(rows), pause=0)
            first = list(said)
            del said[:]
            reg = Register(rows)
            contracts.run(200, today=date(2026, 11, 17), ask=reg, pause=0)
        finally:
            contracts.say = keep
        self.assertTrue(first[0].startswith("2026-11: 1 contracts"))
        self.assertIn("2026-06: 1 contracts, stored already", said)
        self.assertNotIn("2026-06", {a[1][:7] for a in reg.asked})          # June closed long ago
        self.assertIn("2026-10", {a[1][:7] for a in reg.asked})             # October may still change

    def test_the_site_gets_a_month_with_each_name_written_once(self):
        rows = [contracts.slim(contract(i, date(2026, 11, 2 + i % 3))) for i in range(1, 6)]
        rows.append(contracts.slim(dict(contract(6, date(2026, 11, 9)), formAbbrHy="ՄԱ", contractValueTotal=30000.0)))    # small, one source
        rows.append(contracts.slim(dict(contract(7, date(2026, 11, 9)), formAbbrHy="ՄԱ", contractValueTotal=2500000.0)))
        rows.append(contracts.slim(dict(contract(8, date(2026, 11, 9)), formAbbrHy="ԳՉԾ")))                                # not a purchase
        page = contracts.month_page("2026-11", rows)
        self.assertEqual((len(page["B"]), len(page["S"]), sorted(page["F"])), (1, 1, ["ԷԱՃ", "ՄԱ"]))
        self.assertEqual(len(page["R"]), 6)
        day, b, sup, value, est, f, kind, subject, t = page["R"][0]
        self.assertEqual((day, page["B"][b], page["S"][sup][1:], value, est, page["F"][f], kind, subject),
                         (2, ["02500052", "Երևանի քաղաքապետարան"], ["«Օրինակ» ՍՊԸ", "01234567", 0], 3000.0, 3250, "ԷԱՃ", "s",
                          "միջոցառման կազմակերպում"))
        self.assertEqual(page["T"][t], ["ԵՔ-ԷԱՃԾՁԲ-26/3", ["3d953a28c7", "48c888df0f"]])
        self.assertNotIn("1570000000000000", json.dumps(page))

    def test_publishing_lists_the_months_and_forgets_one_that_is_gone(self):
        public = tempfile.TemporaryDirectory()
        was, contracts.PUBLIC = contracts.PUBLIC, public.name
        try:
            contracts.save_month("2026-10", {r["id"]: r for r in [contracts.slim(contract(1, date(2026, 10, 5)))]})
            contracts.save_month("2026-11", {r["id"]: r for r in [contracts.slim(contract(2, date(2026, 11, 5)))]})
            meta = contracts.publish(datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc))
            self.assertEqual((meta["months"], meta["from"], meta["to"], meta["contracts"], meta["updated"]),
                             ([["2026-10", 1], ["2026-11", 1]], "2026-10-05", "2026-11-05", 2, "2026-11-17T10:00"))
            os.remove(contracts.month_file("2026-10"))
            contracts.publish(datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc))
            self.assertEqual(sorted(os.listdir(public.name)), ["2026-11.json", "meta.json"])
        finally:
            contracts.PUBLIC = was
            public.cleanup()

    def test_months_cover_the_stretch_whole(self):
        self.assertEqual(contracts.months(date(2025, 12, 20), date(2026, 2, 3)),
                         [(date(2025, 12, 1), date(2025, 12, 31)), (date(2026, 1, 1), date(2026, 1, 31)),
                          (date(2026, 2, 1), date(2026, 2, 28))])


if __name__ == "__main__":
    unittest.main()
