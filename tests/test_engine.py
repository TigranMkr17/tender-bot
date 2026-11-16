"""Offline checks. Run with:  python -m unittest discover -s tests -v

The site itself is not contacted. Pages are rebuilt from real notices saved in
tools/seed_2026-11-13.json, in more than one plausible HTML shape, to make sure
the reader depends on the data's shape and not on a particular markup.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import armeps, digest, main, store, telegram  # noqa: E402
from bot import textproc as tp  # noqa: E402

with open(os.path.join(ROOT, "tools", "seed_2026-11-13.json"), encoding="utf-8") as _fh:
    SEED = json.load(_fh)
BY_ID = {t["id"]: t for t in SEED["tenders"]}
AT = datetime(2026, 11, 13, 19, 10)


def list_page(tenders, style="table"):
    rows = []
    for t in tenders:
        link = f'/hy/public/tender_details/by_end_bid_time/2/tid/{t["id"]}/'
        if style == "table":
            rows.append(
                f'<tr class="odd"><td>{t["id"]}</td><td>{escape(t["code"])}</td>'
                f'<td>\n   {escape(t["title"])}\n</td><td>{t["lots"]}</td>'
                f'<td><span class="st">{escape(t["status"])}</span></td>'
                f'<td>{t["deadline"]}</td><td><a href="{link}">Մանրամասն</a></td></tr>')
        else:  # sloppy markup: no closing tags, id only inside the link
            rows.append(
                f'<tr><td><a href="{link}"><b>{t["id"]}</b></a><td>{escape(t["code"])}'
                f'<td><div>{escape(t["title"])}</div><td>{t["lots"]}<td>{escape(t["status"])}'
                f'<td>{t["deadline"]}<td><a href="{link}">…</a>')
    head = ("<tr><th>Հ/հ</th><th>Ծածկագիր</th><th>Վերնագիր</th><th>Չափաբաժինների քանակ</th>"
            "<th>Կարգավիճակ</th><th>Վերջնաժամկետ</th><th></th></tr>")
    return ("<html><head><title>x</title><script>var a='<td>';</script></head><body>"
            f"<div>Ընդամենը 31197</div><table>{head}{''.join(rows)}</table>"
            '<div class="pages"><a href="/hy/public/tender/by_end_bid_time/2/start/2">2</a></div>'
            "</body></html>")


def detail_page(t, style="table"):
    pairs = [("Ծածկագիր", t["code"]), ("Վերնագիր", t["title"]), ("Գնորդ", t["buyer"]),
             ("Գնման տեսակ", t["kind"]), ("Հրապարակման ժամանակ", t["published"]),
             ("Հայտերի ընդունման վերջնաժամկետ", t["deadline"]),
             ("Հակադարձ աճուրդ", t["auction"]),
             ("Դուք կարող եք ուղարկել հարցում նախքան", t["questions_until"]),
             ("Կարգավիճակ", t["status"])]
    inv = f'/application/documents/public_invitation/tender_{t["id"]}.zip'
    if style == "table":
        body = "".join(f"<tr><td class='l'>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in pairs)
        body = f"<table>{body}<tr><td>Հրավեր</td><td><a href='{inv}'>Բեռնել</a></td></tr></table>"
    elif style == "divs":
        body = "".join(f"<div class='row'><label>{escape(k)}</label>\n<span>\n  {escape(v)}\n</span></div>"
                       for k, v in pairs)
        body += f"<div><label>Հրավեր</label><a href='https://eauction.armeps.am{inv}'>Բեռնել</a></div>"
    else:  # "Label: value" in one piece of text, title broken over lines
        body = "".join(f"<p>{escape(k)}: {escape(v)}</p>" for k, v in pairs if k != "Վերնագիր")
        half = len(t["title"]) // 2
        body = (f"<p><b>Վերնագիր</b><br>{escape(t['title'][:half])}<br>{escape(t['title'][half:])}</p>"
                + body + f"<a href='{inv}'>Հրավեր</a>")
    return (f"<html><body><a href='/hy/public/tender/'>Ցուցակ</a>{body}"
            "<h3>Պատասխաններ և պարզաբանումներ</h3><table><tr><th>Հարցում</th><th>Ժամանակ</th>"
            "<th>Պարզաբանում</th></tr></table></body></html>")


class ListPages(unittest.TestCase):
    def check(self, style):
        rows = armeps.parse_list(list_page(SEED["tenders"], style))
        self.assertEqual(len(rows), len(SEED["tenders"]))
        for r in rows:
            src = BY_ID[r.id]
            self.assertEqual(r.code, src["code"])
            self.assertEqual(r.title, src["title"])
            self.assertEqual(r.lots, src["lots"])
            self.assertEqual(r.status, src["status"])
            self.assertEqual(r.deadline, src["deadline"].replace(" ", "T")[:16])

    def test_clean_table(self):
        self.check("table")

    def test_sloppy_table(self):
        self.check("sloppy")

    def test_no_rows_in_unrelated_page(self):
        self.assertEqual(armeps.parse_list("<html><body><p>Սպասարկման աշխատանքներ</p></body></html>"), [])


class NoticePages(unittest.TestCase):
    def check(self, style):
        for t in SEED["tenders"]:
            if "buyer" not in t:
                continue
            d = armeps.parse_detail(detail_page(t, style))
            self.assertEqual(d.get("code"), t["code"], style)
            self.assertEqual(d.get("buyer"), t["buyer"], style)
            self.assertEqual(d.get("kind"), t["kind"], style)
            self.assertEqual(d.get("published"), t["published"].replace(" ", "T")[:16], style)
            self.assertEqual(d.get("deadline"), t["deadline"].replace(" ", "T")[:16], style)
            self.assertEqual(d.get("auction"), t["auction"].replace(" ", "T")[:16], style)
            self.assertEqual(d.get("questions_until"), t["questions_until"].replace(" ", "T")[:16], style)
            self.assertTrue(d.get("invitation").endswith(f"tender_{t['id']}.zip"), style)
            self.assertTrue(d.get("invitation").startswith("https://eauction.armeps.am/"), style)
            if style != "inline":
                self.assertEqual(d.get("title"), t["title"], style)

    def test_table_layout(self):
        self.check("table")

    def test_div_layout(self):
        self.check("divs")

    def test_inline_layout(self):
        self.check("inline")


class Wording(unittest.TestCase):
    def test_subjects(self):
        cases = {
            48927: ("Մալուխի ձեռքբերում", None),
            48954: ("Ռեգուլյար բենզինի ձեռքբերում",
                    "Քաղաքաշինության, տեխնիկական և հրդեհային անվտանգության տեսչական մարմնի"),
            48950: ("Կահավորման աշխատանքների ձեռքբերում", None),
            48939: ("Խմածությունը չափող սարքերի պահեստամասերի ձեռքբերում", None),
            48892: ("Դեղորայքի ձեռքբերում", None),
            48946: ("Բնական սեղմված գազ", None),
            48913: ("Դիսպենսերի զուգարանի թղթի ձեռքբերում", None),
            48932: (None, None),  # the title never says what is being bought
            48934: ("Սննդամթերքի ձեռքբերում",
                    "«Սիսիան համայնքի նախադպրոցական ուսումնական հաստատություն» համայնքային "
                    "ոչ առևտրային կազմակերպությունների"),
        }
        data = _built()
        for tid, (subject, for_whom) in cases.items():
            self.assertEqual(data[tid].get("subject"), subject, tid)
            self.assertEqual(data[tid].get("for"), for_whom, tid)

    def test_buyer_names_are_readable(self):
        data = _built()
        self.assertEqual(data[48927]["buyer"], "Կարեն Դեմիրճյանի անվան Երևանի մետրոպոլիտեն ՓԲԸ")
        self.assertEqual(data[48956]["buyer"],
                         "ՀՀ բարձր տեխնոլոգիական արդյունաբերության և արհեստական բանականության նախարարություն")
        self.assertEqual(data[48938]["buyer"], "Վանաձորի բժշկական կենտրոն ՓԲԸ")
        self.assertEqual(data[48954]["buyer"], "Վարչապետի աշխատակազմ")  # already fine: untouched

    def test_sectors(self):
        want = {48927: "elec", 48956: "it", 48954: "fuel", 48953: "home", 48946: "fuel",
                48941: "office", 48938: "med", 48934: "food", 48933: "cloth", 48815: "auto",
                48913: "home", 48647: "med", 48883: "furn", 48932: "other"}
        data = _built()
        for tid, sector in want.items():
            self.assertEqual(data[tid]["sector"], sector, tid)

    def test_gas_turbine_is_not_fuel(self):
        self.assertEqual(tp.classify("գազատուրբինի ABB գրգռման համակարգի բլոկի"), "equip")
        self.assertEqual(tp.classify("հեղուկ գազի ձեռքբերում"), "fuel")

    def test_kind_from_code(self):
        self.assertEqual(tp.kind_from_code("ՍՀԱԿ-ԷԱՃԱՇՁԲ-26/1"), "works")
        self.assertEqual(tp.kind_from_code("ԴԴ-ԷԱՃԾՁԲ-26/05"), "services")
        self.assertEqual(tp.kind_from_code("ՀՀՇՄԳՀՀԿՀ-ԷԱ-ԱՊՁԲ-115/26"), "goods")


def _built():
    with tempfile.TemporaryDirectory() as tmp:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import build_seed_data
        out = build_seed_data.build(os.path.join(ROOT, "tools", "seed_2026-11-13.json"),
                                    os.path.join(tmp, "t.json"))
    return {t["id"]: t for t in out["tenders"]}


class Messages(unittest.TestCase):
    def setUp(self):
        self.tenders = list(_built().values())

    def test_morning(self):
        text = digest.build(self.tenders, AT, datetime(2026, 11, 12, 19, 0), "morning")
        self.assertIn("Նոր՝ <b>18</b>", text)
        self.assertIn("Ընդամենը բաց՝ <b>29</b>", text)
        self.assertIn("…և ևս 11 մրցույթ", text)
        self.assertLess(len(text), 3500)  # Telegram allows 4096

    def test_evening_silent_when_nothing_new(self):
        self.assertIsNone(digest.build(self.tenders, AT, AT, "evening"))

    def test_cancelled_is_never_announced(self):
        text = digest.build(self.tenders, AT, datetime(2026, 11, 1), "morning")
        self.assertNotIn("Հրազդանի", text)

    def test_html_is_escaped(self):
        t = dict(self.tenders[0], subject="A <b> & B", pub="2026-11-13T19:00", id=1)
        text = digest.build([t], AT, datetime(2026, 11, 13, 18, 0), "evening")
        self.assertIn("A &lt;b&gt; &amp; B", text)


class Secrets(unittest.TestCase):
    def test_round_trip(self):
        state = {"subs": [123456789, -100200300], "offset": 42}
        sealed = telegram.seal(state, "123:ABC")
        self.assertNotIn("123456789", sealed)
        self.assertEqual(telegram.unseal(sealed, "123:ABC"), state)

    def test_wrong_token_or_tampering(self):
        sealed = telegram.seal({"subs": [1]}, "123:ABC")
        self.assertIsNone(telegram.unseal(sealed, "999:XYZ"))
        self.assertIsNone(telegram.unseal(sealed[:-6] + "AAAAA=", "123:ABC"))
        self.assertIsNone(telegram.unseal("not base64 at all", "123:ABC"))


class EndToEnd(unittest.TestCase):
    """A whole run against rebuilt pages, without the network or Telegram."""

    def test_scrape_then_rerun(self):
        open_ones = [t for t in SEED["tenders"]]
        old = {"id": 40001, "code": "ՀԻՆ-ԷԱՃԱՊՁԲ-26/1", "title": "հին մրցույթ", "lots": 1,
               "status": "Հրապարակված", "deadline": "2026-10-19 11:00:00"}
        pages = {armeps.list_url(1): list_page(open_ones),
                 armeps.list_url(2): list_page([old], "sloppy")}
        calls = []

        def fake(url):
            calls.append(url)
            if url in pages:
                return pages[url]
            tid = int(url.rstrip("/").rsplit("/", 1)[1])
            return detail_page(BY_ID[tid], "divs" if tid % 2 else "table")

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                data = main.update_data(AT, fetch=fake, pause=0)
                by_id = {t["id"]: t for t in data["tenders"]}
                self.assertEqual(len(by_id), 30)           # the October tender is ignored
                self.assertNotIn(40001, by_id)
                self.assertEqual(data["meta"]["open"], 29)
                self.assertEqual(by_id[48927]["subject"], "Մալուխի ձեռքբերում")
                self.assertEqual(by_id[48927]["pub"], "2026-11-13T11:23")
                self.assertEqual(by_id[48808]["status"], "cancelled")
                self.assertNotIn("pub", by_id[48808])      # cancelled: notice not fetched
                first = len(calls)
                self.assertEqual(first, 2 + 29)            # two list pages + 29 notices

                with open(store.DATA_PATH, encoding="utf-8") as fh:
                    shown = {t["id"]: t for t in json.load(fh)["tenders"]}
                self.assertEqual(len(shown), 30)
                self.assertEqual(shown[48927]["inv"], 1)   # the app rebuilds the usual links itself
                self.assertNotIn("url", shown[48927])
                self.assertNotIn("buyer_official", shown[48927])
                self.assertNotIn("dt", shown[48927])
                self.assertEqual(shown[48927]["buyer"], "Կարեն Դեմիրճյանի անվան Երևանի մետրոպոլիտեն ՓԲԸ")
                self.assertTrue(os.path.exists(store.STATE_PATH))

                data = main.update_data(AT, fetch=fake, pause=0)
                self.assertEqual(len(calls) - first, 2)    # second run: lists only
                self.assertEqual(len(data["tenders"]), 30)
            finally:
                os.chdir(cwd)

    def test_layout_change_is_reported(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with self.assertRaises(armeps.ScrapeError):
                    main.update_data(AT, fetch=lambda url: "<html><body>503</body></html>", pause=0)
                self.assertTrue(os.path.exists(os.path.join("debug", "list_1.html")))
            finally:
                os.chdir(cwd)


class TelegramFlow(unittest.TestCase):
    """A full digest run with Telegram replaced by a recorder."""

    def run_bot(self, updates, mode="digest", period="morning"):
        calls = []

        def fake_call(token, method, **params):
            calls.append((method, params))
            if method == "getUpdates":
                return [u for u in updates if u["update_id"] >= params.get("offset", 0)]
            if method == "sendMessage" and params["chat_id"] == 666:
                raise telegram.TelegramError(403, "Forbidden: bot was blocked by the user")
            return True

        pages = {armeps.list_url(1): list_page(SEED["tenders"])}

        def fake_fetch(url):
            if url in pages:
                return pages[url]
            if "/start/" in url:
                return "<html><body><table></table></body></html>"
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        real_call, real_now = telegram.call, store.now
        telegram.call, store.now = fake_call, lambda: AT
        env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "GITHUB_REPOSITORY": "Tigran/tender-bot"}
        old_env = {k: os.environ.get(k) for k in list(env) + ["APP_URL", "TELEGRAM_CHAT_ID"]}
        os.environ.update(env)
        os.environ.pop("APP_URL", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        try:
            code = main.run(mode, period, fetch=fake_fetch, pause=0)
        finally:
            telegram.call, store.now = real_call, real_now
            for k, v in old_env.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        return code, calls

    def test_start_then_digest_then_blocked(self):
        def msg(uid, chat, text, kind="private"):
            return {"update_id": uid, "message": {"chat": {"id": chat, "type": kind}, "text": text}}

        updates = [msg(10, 111, "/start"), msg(11, 666, "/start"), msg(12, -500, "hello", "group"),
                   msg(13, 222, "բարև"), msg(14, 222, "/stop")]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                code, calls = self.run_bot(updates)
                self.assertEqual(code, 0)
                methods = [m for m, _ in calls]
                self.assertIn("setChatMenuButton", methods)
                menu = dict(calls)["setChatMenuButton"]["menu_button"]
                self.assertEqual(menu["web_app"]["url"], "https://tigran.github.io/tender-bot/")
                sends = [p for m, p in calls if m == "sendMessage"]
                to_111 = [p for p in sends if p["chat_id"] == 111]
                self.assertEqual(len(to_111), 2)                       # welcome + morning message
                self.assertIn("Բարև Ձեզ", to_111[0]["text"])
                self.assertIn("Ընդամենը բաց՝ <b>29</b>", to_111[1]["text"])
                button = to_111[1]["reply_markup"]["inline_keyboard"][0][0]
                self.assertEqual(button["web_app"]["url"], "https://tigran.github.io/tender-bot/")
                self.assertFalse([p for p in sends if p["chat_id"] == -500])   # group chatter ignored
                state = telegram.load_state("123:ABC")
                self.assertEqual(state["subs"], [111])                 # 666 blocked the bot, 222 left
                self.assertEqual(state["offset"], 15)
                self.assertEqual(state["last_digest"], "2026-11-13T19:10")
                with open(telegram.STATE_PATH, encoding="utf-8") as fh:
                    self.assertNotIn("111", fh.read())
                self.assertEqual(len([p for p in sends if p["chat_id"] == 222]), 1)   # one goodbye only

                # an hour later: nothing new in the inbox, nothing is sent, nothing is fetched
                code, calls = self.run_bot(updates, mode="inbox")
                self.assertEqual(code, 0)
                self.assertFalse([m for m, _ in calls if m == "sendMessage"])
                self.assertEqual(dict(calls)["getUpdates"]["offset"], 15)

                # evening with nothing new since the morning message: silent
                code, calls = self.run_bot(updates, period="evening")
                self.assertFalse([m for m, _ in calls if m == "sendMessage"])
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
