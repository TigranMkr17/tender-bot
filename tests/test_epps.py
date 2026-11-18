"""The EPPS reader, on pages shaped like the live ones (www.armeps.am/epps, November 2026)."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import armeps, epps, store  # noqa: E402


def results_page(rows, total, master="abc:123", start=1):
    trs = "".join(
        f'<tr class="odd"><td>{start + i}</td><td>\n<a href="/epps/cft/prepareViewCfTWS.do?resourceId={rid}">{title}</a>\n</td>'
        f"<td>\n{buyer}\n</td></tr>" for i, (rid, title, buyer) in enumerate(rows))
    return f"""<html><body><table><tr><td>1</td><td>2</td></tr></table>
<h3>Որոնման արդյունքներ</h3>
<table class="Results"><thead><tr><th>#</th><th>
ՄՀ-ի վերնագիրը</th><th>
ՊՊ</th></tr></thead><tbody>{trs}</tbody></table>
<strong>{total}</strong> արդյունք ամբողջից: &nbsp;
<script>function sortBy(a, actionKind, c) {{
document.sortForm.masterKey.value = "{master}";
document.sortForm.actionKind.value = actionKind;
}}</script></body></html>"""


DETAIL = """<html><body><div id="Content"><h2>Դիտել ՄՀ աշխատանքային տարածքը</h2>
<dl class="Grid">
<dt>Հայտերի ներկայացման վերջնաժամկետ (օրերով/ժամերով)</dt>
<dd>
7/8
</dd>
<dt>Պայմանագրային պատվիրատուի անունը</dt>
<dd><a href="/epps/prepareViewCAOrganisation.do?id=10413">
ԵՐԵՎԱՆԻ ՔԱՂԱՔԱՊԵՏԱՐԱՆԻ ԱՇԽԱՏԱԿԱԶՄ
</a></dd>
<dt>Վերնագիր</dt>
<dd>Երևանի համայնքի կարիքների համար մանկապարտեզների գույքի ձեռքբերում</dd>
<dt>Վերնագիր (EN)</dt>
<dd>notice</dd>
<dt>Ընթացակարգի ծածկագիր</dt>
<dd>
ԵՔ-ԳՀԱՊՁԲ-26/64
</dd>
<dt>ՄՀ առանձնահատուկ հ/հ</dt>
<dd>
2026/null/10
</dd>
<dt>Նկարագրություն</dt>
<dd>մանկական կահույք</dd>
<dt>Գնումների տիպը</dt>
<dd>Ապրանքներ</dd>
<dt>Ընթացակարգ</dt>
<dd>Գնանշման հարցում</dd>
<dt>ԳԸԲ կոդեր</dt>
<dd>
39161000-մանկական կահույք
</dd>
<dt>
է-Աճուրդների հավելումներ</dt>
<dd>
Ոչ
</dd>
<dt>Մոտավոր արժեքը (ՀԴ)</dt>
<dd>
12,500,000.00
</dd>
<dt>Ժամանակի սահմանափակում հայտերի ստացման կամ մասնակցության հայտերի  համար</dt>
<dd>
26/11/2026 11:30
</dd>
<dt>Պարզաբանումների հարցում (սկսած-մինչև)</dt>
<dd>
18/11/2026 20:23 - 21/11/2026 11:30
</dd>
<dt>Հայտերի բացման ամսաթիվը</dt>
<dd>
26/11/2026 11:30
</dd>
<dt>Հրատարակման/Հրավերի օր </dt>
<dd>
18/11/2026 21:14
</dd>
<dt>Նոր դաշտ</dt>
<dd>ինչ-որ բան</dd>
</dl></div></body></html>"""


class FakeSession:
    """Answers like EPPS: a session is needed for the search; the pager serves pages of PER_PAGE."""

    def __init__(self, calls, detail=DETAIL, broken=()):
        self.calls, self.detail, self.broken, self.asked = calls, detail, set(broken), []

    def get(self, url):
        self.asked.append(url)
        if url == epps.HOME:
            return "<html>home</html>"
        if url == epps.SEARCH:
            return results_page(self.calls[:10], len(self.calls))
        if url.startswith(epps.PAGER):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(url).query, keep_blank_values=True)
            per = int(q["paging_results_per_page"][0])
            page = int(q["paging_go_to_page"][0] or 1) if q["actionKind"][0] == "paging_go_to_page" else 1
            assert q["masterKey"][0] == "abc:123" and q["subKey"][0] == "results['entriesCollection']"
            chunk = self.calls[(page - 1) * per: page * per]
            return results_page(chunk, len(self.calls), start=(page - 1) * per + 1)
        rid = int(url.rsplit("=", 1)[1])
        if rid in self.broken:
            raise armeps.ScrapeError("did not open")
        return self.detail


def calls(n, start=12_600_000):
    return [(start + i, f"Գնում {i} մանկապարտեզների համար", "ԵՐԵՎԱՆԻ ՔԱՂԱՔԱՊԵՏԱՐԱՆԻ ԱՇԽԱՏԱԿԱԶՄ") for i in range(n)]


AT = datetime(2026, 11, 19, 8, 50)            # Yerevan time, as store.now() gives it


class ListTest(unittest.TestCase):
    def test_rows_total_and_key(self):
        rows, total, key = epps.parse_list(results_page(calls(3), 363, master="f1c:-69:11a2"))
        self.assertEqual(total, 363)
        self.assertEqual(key, "f1c:-69:11a2")
        self.assertEqual([r["id"] for r in rows], [12_600_000, 12_600_001, 12_600_002])
        self.assertEqual(rows[0]["title"], "Գնում 0 մանկապարտեզների համար")
        self.assertEqual(rows[0]["buyer"], "ԵՐԵՎԱՆԻ ՔԱՂԱՔԱՊԵՏԱՐԱՆԻ ԱՇԽԱՏԱԿԱԶՄ")

    def test_every_page_is_read(self):
        s = FakeSession(calls(163))
        got = epps.list_open(s, say=lambda *_: None)
        self.assertEqual(len(got), 163)
        self.assertEqual(len({r["id"] for r in got}), 163)
        self.assertEqual(s.asked[:2], [epps.HOME, epps.SEARCH])

    def test_a_short_list_needs_no_pager(self):
        s = FakeSession(calls(7))
        self.assertEqual(len(epps.list_open(s, say=lambda *_: None)), 7)
        self.assertFalse(any(u.startswith(epps.PAGER) for u in s.asked))

    def test_an_empty_search_is_an_error(self):
        with self.assertRaises(armeps.ScrapeError):
            epps.list_open(FakeSession([]), say=lambda *_: None)


class DetailTest(unittest.TestCase):
    def test_fields(self):
        d = epps.parse_detail(DETAIL)
        self.assertEqual(d["code"], "ԵՔ-ԳՀԱՊՁԲ-26/64")
        self.assertEqual(d["buyer"], "ԵՐԵՎԱՆԻ ՔԱՂԱՔԱՊԵՏԱՐԱՆԻ ԱՇԽԱՏԱԿԱԶՄ")
        self.assertEqual(d["org"], 10413)
        self.assertEqual(d["procedure"], "Գնանշման հարցում")
        self.assertEqual(d["deadline"], "26/11/2026 11:30")       # the label has a double space on the site
        self.assertEqual(d["other"], {"Նոր դաշտ": "ինչ-որ բան"})

    def test_stored(self):
        t = {"id": 1}
        epps.apply(t, epps.parse_detail(DETAIL))
        self.assertEqual((t["end"], t["ask"], t["opn"], t["pub"]),
                         ("2026-11-26T11:30", "2026-11-21T11:30", "2026-11-26T11:30", "2026-11-18T21:14"))
        self.assertEqual((t["kind"], t["pr"], t["est"]), ("goods", "ԳՀ", 12_500_000))
        self.assertNotIn("title_en", t)                           # "notice" is a placeholder, not a title
        self.assertNotIn("uid", t)

    def test_small_readers(self):
        self.assertEqual(epps.amount("1 250 000"), 1_250_000)
        self.assertEqual(epps.amount("12,500,000.00"), 12_500_000)
        self.assertIsNone(epps.amount(""))
        self.assertEqual(epps.dates("2026-11-26 11:30"), ["2026-11-26T11:30"])
        self.assertEqual(epps.dates("26.11.2026"), ["2026-11-26T00:00"])
        for text, key in [("Բաց", "ԲՄ"), ("Բաց (հրատապ)", "ՀԲՄ"), ("Գնանշման հարցում", "ԳՀ"), ("Բաց ազգային մրցույթ", "ԲՄ"),
                          ("Շրջանակային համաձայնություն", "ՇՀ"), ("Մեկ անձից գնում", "ՄԱ"), ("", None)]:
            self.assertEqual(epps.procedure_key(text), key, text)


class UpdateTest(unittest.TestCase):
    def test_new_calls_are_read_and_marked(self):
        tenders = {48653: {"id": 48653, "status": "open", "end": "2026-11-25T10:00"}}
        stats = epps.update(tenders, AT, session=FakeSession(calls(12)), say=lambda *_: None, workers=1)
        mine = [t for t in tenders.values() if t.get("src") == "epps"]
        self.assertEqual((stats["listed"], stats["new"], stats["details"]), (12, 12, 12))
        self.assertTrue(all(t["status"] == "open" and t["pr"] == "ԳՀ" and t["dtat"] for t in mine))
        self.assertNotIn("seen", mine[0])                         # the first run marks nothing as new
        self.assertNotIn("src", tenders[48653])

    def test_second_run_reads_only_new_and_closes_the_removed(self):
        tenders = {}
        epps.update(tenders, AT, session=FakeSession(calls(12)), say=lambda *_: None, workers=1)
        later = AT.replace(hour=11)
        s = FakeSession(calls(11, start=12_600_001) + calls(1, start=12_700_000))
        stats = epps.update(tenders, later, session=s, say=lambda *_: None, workers=1)
        self.assertEqual((stats["new"], stats["details"], stats["gone"]), (1, 1, 1))
        self.assertEqual(tenders[12_700_000]["seen"], store.stamp(later))
        self.assertEqual(tenders[12_600_000]["status"], "other")
        self.assertFalse(store.is_open(tenders[12_600_000], later))

    def test_unreadable_pages_wait(self):
        tenders = {}
        stats = epps.update(tenders, AT, session=FakeSession(calls(4), broken={12_600_001}), say=lambda *_: None, workers=1)
        self.assertEqual((stats["details"], stats["detail_failed"]), (3, 1))
        self.assertEqual(tenders[12_600_001]["dt"], 1)
        self.assertNotIn("dtat", tenders[12_600_001])

    def test_a_call_also_on_the_auction_site_is_shown_once(self):
        items = [{"id": 1, "code": "ԵՔ-ԷԱՃԱՊՁԲ-26/9"}, {"id": 12_600_000, "src": "epps", "code": "ԵՔ ԷԱՃԱՊՁԲ 26/9"},
                 {"id": 12_600_001, "src": "epps", "code": "ԵՔ-ԳՀԱՊՁԲ-26/64"}]
        self.assertEqual([t["id"] for t in store.drop_doubles(items)], [1, 12_600_001])



class SectorTest(unittest.TestCase):
    def test_vehicle_repair_is_transport(self):
        from bot import textproc as tp
        self.assertEqual(tp.classify("ավտոմեքենաների վերանորոգման ծառայությունների ձեռքբերում", "services"), "auto")
        self.assertEqual(tp.classify("ավտոբուսների վերանորոգում", "services"), "auto")
        self.assertEqual(tp.classify("շենքերի ընթացիկ նորոգման աշխատանքներ", "works"), "build")
        self.assertEqual(tp.classify("ճանապարհների վերանորոգում", "works"), "build")



class ExpiredTest(unittest.TestCase):
    def test_an_expired_call_still_listed_is_not_new_again(self):
        old = {"id": 9_392_882, "src": "epps", "status": "open", "end": "2025-03-01T10:00", "dtat": "2026-11-19T03:00", "title": "Հին"}
        tenders = {9_392_882: dict(old)}
        session = FakeSession([(9_392_882, "Հին", "Գնորդ"), (12_600_000, "Նոր", "Գնորդ")])
        stats = epps.update(tenders, AT, session=session, say=lambda *_: None, workers=1, skip={9_392_882})
        self.assertIn(9_392_882, stats["ids"])
        self.assertNotIn("seen", tenders[9_392_882])            # known before: kept, not "new"
        del tenders[9_392_882]                                  # the store dropped it four days after its deadline
        epps.update(tenders, AT, session=FakeSession([(9_392_882, "Հին", "Գնորդ")]), say=lambda *_: None, workers=1, skip={9_392_882})
        self.assertNotIn(9_392_882, tenders)



class DoublesTest(unittest.TestCase):
    def test_a_double_stays_in_memory_but_not_on_the_site(self):
        import json, tempfile
        data = {"meta": {}, "tenders": [{"id": 1, "code": "ԵՔ-ԷԱՃԱՊՁԲ-26/9", "end": "2026-11-25T10:00"},
                                         {"id": 12_600_000, "src": "epps", "code": "ԵՔ-ԷԱՃԱՊՁԲ-26/9", "end": "2026-11-25T10:00"}]}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tenders.json")
            store.publish(data, path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual([t["id"] for t in json.load(fh)["tenders"]], [1])
        self.assertEqual(len(data["tenders"]), 2)


if __name__ == "__main__":
    unittest.main()
