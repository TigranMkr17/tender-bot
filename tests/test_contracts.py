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
    """Answers `count` and `list` like the register. With `shuffle`, pages overlap, as an unstable order makes them."""

    def __init__(self, rows, shuffle=False):
        self.rows, self.shuffle, self.asked = rows, shuffle, []

    def __call__(self, path, body):
        f = body["filter"]["dateSigned"]
        lo, hi = f["min"][:10], f["max"][:10]
        hit = [c for c in self.rows if lo <= contracts.day(c["dateSigned"]) <= hi]
        self.asked.append((path, lo, hi))
        if path == "count":
            return len(hit)
        i, size = body["page"]["index"], body["page"]["size"]
        if self.shuffle and len(hit) > size and lo != hi:
            return hit[:size]                              # every page the same: the count cannot add up
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

    def test_pages_are_gathered_until_the_count_is_reached(self):
        rows = [contract(i, date(2026, 11, 1) + timedelta(days=i % 9)) for i in range(1, 12)]
        reg = Register(rows)
        got = contracts.read_days(date(2026, 11, 1), date(2026, 11, 30), reg, pause=0)
        self.assertEqual(len(got), 11)
        self.assertEqual([a[0] for a in reg.asked], ["count", "list", "list", "list"])

    def test_a_stretch_that_does_not_add_up_is_read_day_by_day(self):
        rows = [contract(i, date(2026, 11, 1) + timedelta(days=i % 9)) for i in range(1, 12)]
        reg = Register(rows, shuffle=True)
        got = contracts.read_days(date(2026, 11, 1), date(2026, 11, 9), reg, pause=0)
        self.assertEqual(len(got), 11)
        self.assertIn(("count", "2026-11-03", "2026-11-03"), reg.asked)

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

    def test_months_cover_the_stretch_whole(self):
        self.assertEqual(contracts.months(date(2025, 12, 20), date(2026, 2, 3)),
                         [(date(2025, 12, 1), date(2025, 12, 31)), (date(2026, 1, 1), date(2026, 1, 31)),
                          (date(2026, 2, 1), date(2026, 2, 28))])


if __name__ == "__main__":
    unittest.main()
