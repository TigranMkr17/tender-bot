"""Past prices: the contracts most like an open tender, from the contracts register."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot import past  # noqa: E402

AT = datetime(2026, 11, 19, 15, 0)
CITY = "ԵՐԵՎԱՆԻ ՔԱՂԱՔԱՊԵՏԱՐԱՆ"


def month(m, rows):
    """A month file as bot/contracts.py writes it, from (day, buyer, supplier, sole proprietor, value, estimate,
    form, subject) rows."""
    B, S, F, R = [], [], [], []
    for day, buyer, supplier, person, value, est, form, subject in rows:
        if [None, buyer] not in [[None, b[1]] for b in B]:
            B.append(["0" * 8, buyer])
        if supplier not in [s[1] for s in S]:
            S.append([f"{len(S):010x}", supplier, "" if person else "1234567", 1 if person else 0])
        if form not in F:
            F.append(form)
        R.append([day, [b[1] for b in B].index(buyer), [s[1] for s in S].index(supplier), value, est,
                  F.index(form), "s", subject, -1])
    return {"m": m, "B": B, "S": S, "F": F, "T": [], "R": R}


REGISTER = [
    ("2026-08", [
        (4, CITY, "Աջափնյակ Քոնսթրաքշն ՍՊԸ", 0, 1_590_000, 2_000_000, "ԲՄ",
         "Երևան քաղաքի Մալաթիա-Սեբաստիա վարչական շրջանի թիվ 77 մանկապարտեզի բակի բարեկարգման աշխատանքների "
         "նախագծանախահաշվային փաստաթղթերի կազմման խորհրդատվական ծառայություններ"),
        (5, "Բաղրամյանի համայնքապետարան", "Բի Թու Ջի ՍՊԸ", 0, 414_000, 520_000, "ԷԱՃ", "խողովակները միացնող կցորդիչ"),
        (9, "Արմավիրի համայնքապետարան", "Անուն Ազգանուն", 1, 1_200_000, 1_500_000, "ԳՀ",
         "Թիվ 3 մանկապարտեզի շենքի նախագծանախահաշվային փաստաթղթերի կազմում"),
    ]),
    ("2026-09", [(day, "Ա" * (day % 5 + 1) + " գնորդ", f"Կահույքագործ {day} ՍՊԸ", 0, 100_000 * day, 120_000 * day,
                  "ԷԱՃ", "Կահույքի ձեռքբերում") for day in range(1, 11)]),
]


class Words(unittest.TestCase):
    def test_places_endings_and_names_are_left_out(self):
        got = past.stems("Երևան քաղաքի Կենտրոն վարչական շրջանի թիվ 1 մսուր-մանկապարտեզի նախագծանախահաշվային "
                         "փաստաթղթերի կազմման ծառայությունների ձեռքբերում Տիգրան Պետրոսյան փողոցի")
        self.assertIn("մանկապար", got)
        self.assertIn("փաստաթղթ", got)
        for word in ("երեվա", "քաղաք", "կենտրո", "վարչակա", "շրջան", "պետրոսյ", "փողոց", "ծառայութ", "ձեռքբեր"):
            self.assertNotIn(word, got)

    def test_one_stem_for_all_forms(self):
        self.assertEqual(past.stem("մանկապարտեզների"), past.stem("մանկապարտեզի"))
        self.assertEqual(past.stem("կահույքի"), past.stem("կահույք"))


class Similar(unittest.TestCase):
    def setUp(self):
        rows = []
        for m, items in REGISTER:
            rows.extend(past.rows_of(month(m, items)))
        self.reg = past.Register(rows)

    def test_the_kindergarten_design_finds_its_kind(self):
        t = {"id": 12618601, "buyer": "Երևանի քաղաքապետարան",
             "subject": "Երևան քաղաքի Կենտրոն վարչական շրջանի թիվ 1 մսուր-մանկապարտեզի նոր շենքի կառուցման և բակի "
                        "բարեկարգման աշխատանքների նախագծանախահաշվային փաստաթղթերի կազմման խորհրդատվական աշխատանքներ"}
        found = self.reg.similar(t)
        subjects = [r["subj"] for _, r in found]
        self.assertTrue(subjects[0].startswith("Երևան քաղաքի Մալաթիա"))      # same buyer, most alike
        self.assertNotIn("խողովակները միացնող կցորդիչ", subjects)
        e = past.entry(t, found)
        self.assertEqual(e["r"][0][1], "")                                    # the same buyer is not repeated
        self.assertEqual(e["r"][0][2], "Աջափնյակ Քոնսթրաքշն ՍՊԸ")
        armavir = next(r for r in e["r"] if r[1] == "Արմավիրի համայնքապետարան")
        self.assertEqual(armavir[2], "")                                      # a sole proprietor is not named

    def test_one_shared_word_is_not_enough_for_a_long_subject(self):
        t = {"id": 1, "subject": "Նոր ճանապարհը միացնող հատվածի կառուցման որակի տեխնիկական հսկողություն"}
        self.assertEqual([r["subj"] for _, r in self.reg.similar(t)], [])

    def test_newest_first_and_the_usual_discount(self):
        found = self.reg.similar({"id": 2, "subject": "Կահույքի ձեռքբերում"})
        e = past.entry({"id": 2}, found)
        self.assertEqual(len(e["r"]), past.SHOWN)
        self.assertEqual([r[0] for r in e["r"]], sorted((r[0] for r in e["r"]), reverse=True))
        self.assertEqual(e["u"], [17, 10])                                    # 100 000 for 120 000: 17% lower

    def test_nothing_alike_is_nothing(self):
        self.assertIsNone(past.entry({"id": 3}, self.reg.similar({"id": 3, "subject": "Մագնիսառեզոնանսային"})))


class Publish(unittest.TestCase):
    def test_open_tenders_go_to_sixteen_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, out = os.path.join(tmp, "k"), os.path.join(tmp, "p")
            os.makedirs(folder)
            for m, items in REGISTER:
                with open(os.path.join(folder, f"{m}.json"), "w", encoding="utf-8") as fh:
                    json.dump(month(m, items), fh, ensure_ascii=False)
            tenders = [{"id": 17, "status": "open", "end": "2026-11-30T10:00", "subject": "Կահույքի ձեռքբերում"},
                       {"id": 33, "status": "open", "end": "2026-11-01T10:00", "subject": "Կահույքի ձեռքբերում"}]
            self.assertEqual(past.publish(tenders, AT, folder=folder, out=out), 1)   # the closed one is left out
            self.assertEqual(len(os.listdir(out)), past.BUCKETS)
            with open(os.path.join(out, "1.json"), encoding="utf-8") as fh:
                page = json.load(fh)
            self.assertIn("17", page["t"])
            self.assertEqual(page["from"], "2026-08-04")

    def test_no_register_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(past.publish([], AT, folder=os.path.join(tmp, "none"), out=os.path.join(tmp, "p")), 0)
            self.assertFalse(os.path.exists(os.path.join(tmp, "p")))


if __name__ == "__main__":
    unittest.main()
