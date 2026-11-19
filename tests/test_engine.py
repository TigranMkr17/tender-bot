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
from datetime import datetime, timedelta
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

    def test_titles_met_in_live_notices(self):
        """Wording taken from real notices: typos, capitals, codes and serial numbers included."""
        cases = [
            ("ՀՀ ԱՆ «Հանրապետական շտապ օգնության ծառայություն» ՓԲԸ-ի 2027 թվականի կարիքների համար "
             "դեղորայքի ձեռբերման նպատակով հայտարարված ՀՀԱՆՇՕԾ-ԷԱՃԱՊՁԲ-2027/1 ծածկագրով գնման ընթացակարգ",
             "ՀՀԱՆՇՕԾ-ԷԱՃԱՊՁԲ-2027/1", "Դեղորայքի ձեռքբերում",
             "ՀՀ ԱՆ «Հանրապետական շտապ օգնության ծառայություն» ՓԲԸ-ի"),
            ("«Կարեն Դեմիրճյանի անվան Երևանի մետրոպոլիտեն» ՓԲԸ-ի փայտակոճի ձեռքբերման նպատակով "
             "ԵՄ-ԷԱՃԱՊՁԲ-26/138 ծածկագրով գնման ընթացակարգի հայտարարություն և հրավեր",
             "ԵՄ-ԷԱՃԱՊՁԲ-26/138", "Փայտակոճի ձեռքբերում",
             "«Կարեն Դեմիրճյանի անվան Երևանի մետրոպոլիտեն» ՓԲԸ-ի"),
            ("«Կանաչապատում և շրջակա միջավայրի պահպանություն» ՀՈԱԿ-ի 2027 թվականի կարիքների համար "
             "ԿՇՄՊ-ԷԱՃԱՊՁԲ-27/02 ծածկագրով էլեկտրոնային աճուրդ ընթացակարգով ծառհան մեքենայի ձեռքբերման հրավեր",
             "ԿՇՄՊ-ԷԱՃԱՊՁԲ-27/02", "Ծառհան մեքենայի ձեռքբերում",
             "«Կանաչապատում և շրջակա միջավայրի պահպանություն» ՀՈԱԿ-ի"),
            ("Սիսիանի ԲԿ 2027թ․ կարիքների համար դեղորայքի ձեռքբերում 27/01", "ՍԲԿ-ԷԱՃԱՊՁԲ-27/01",
             "Դեղորայքի ձեռքբերում", "Սիսիանի ԲԿ"),
            ("Էջմիածնի բժշկական կենտրոն ՓԲԸ-ի կարիքների համար կազմակերպված ԷԲԿ-ԷԱՃԱՊՁԲ-27/01 ծածկագրով "
             "դեղորայքի ձեռքբերում ՀՀ Գնումների օրենքի 15/6կետով", "ԷԲԿ-ԷԱՃԱՊՁԲ-27/01",
             "Դեղորայքի ձեռքբերում", "Էջմիածնի բժշկական կենտրոն ՓԲԸ-ի"),
            ("Վարչապետի աշխատակազմի (Սննդամթերքի անվտանգության տեսչական մարմնի) կարիքների համար` մուտքի "
             "հսկողության համակարգի և կռունկաձև պրոյեկտորների N ՎԱ-ՍԱՏՄ-ԷԱՃԱՊՁԲ-27/18 ծածկագրով ձեռքբերում",
             "ՎԱ-ՍԱՏՄ-ԷԱՃԱՊՁԲ-27/18", "Մուտքի հսկողության համակարգի և կռունկաձև պրոյեկտորների ձեռքբերում",
             "Վարչապետի աշխատակազմի (Սննդամթերքի անվտանգության տեսչական մարմնի)"),
            ("Արտաշատի համայնքապետարանի ենթակայությամբ գործող մանկապարտեզների Կենտրոնացված կարգով "
             "2027 թվականի Սննդամթերքի ձեռքբերում", "ԱՄԱՀ-ԷԱՃԱՊՁԲ-27/1", "Սննդամթերքի ձեռքբերում",
             "Արտաշատի համայնքապետարանի ենթակայությամբ գործող մանկապարտեզների"),
            ("ՀՀ ԱՆ Այրվածքաբանության և Մաշկաբանության ազգային կենտրոն փակ բաժնետիրական ընկերության "
             "2027 թվականի կարիքների լվացքի հավաքման ծառայությունների ձեռքբերման հրավեր", "",
             "Լվացքի հավաքման ծառայությունների ձեռքբերում",
             "ՀՀ ԱՆ Այրվածքաբանության և Մաշկաբանության ազգային կենտրոն փակ բաժնետիրական ընկերության"),
            ("ՀՀ Շիրակի մարզի Արթիկ համայնքի կարիքների համար՝ Արթիկ համայնքի կարիքների համար "
             "գրասենյակային գույքի ձեռքբերում", "", "Գրասենյակային գույքի ձեռքբերում",
             "ՀՀ Շիրակի մարզի Արթիկ համայնքի"),
            ("«Կապանի բժշկական կենտրոն»ՓԲԸ-ի 2027թ․կարիքների համար բժշկական նշանակության ապրանքների ձեռք բերում",
             "", "Բժշկական նշանակության ապրանքների ձեռքբերում", "«Կապանի բժշկական կենտրոն»ՓԲԸ-ի"),
            ("Ծաղկաձորի համայնքապետարանի կարիքների համար «ԾՔ-ԷԱՃԱՊՁԲ-26/15» ծածկագրով էլեկտրոնային աճուրդի "
             "ընթացակարգով «Անվավոր տրակտոր»-ի ձեռքբերման հայտարարություն և հրավեր", "ԾՔ-ԷԱՃԱՊՁԲ-26/15",
             "Անվավոր տրակտոր", "Ծաղկաձորի համայնքապետարանի"),
            ("ՀՀ Կոտայքի մարզի Ակունքի համայնքապետարանի կարիքների համար < < Փողոցային լուսավորության "
             "ապահովման համար արտաքին լուսավորման լամպերի՝ լեդ լուսատուների ձեռքբերում>>", "",
             "Փողոցային լուսավորության ապահովման համար արտաքին լուսավորման լամպերի՝ լեդ լուսատուների ձեռքբերում",
             "ՀՀ Կոտայքի մարզի Ակունքի համայնքապետարանի"),
            ("Վարդենիսի ԲԿ ՓԲԸ-ի համար գույքագրման ծառայությունների ձեռքբերում", "",
             "Գույքագրման ծառայությունների ձեռքբերում", "Վարդենիսի ԲԿ ՓԲԸ-ի"),
            ("Կահույքի ձեռքբերման մրցույթ", "", "Կահույքի ձեռքբերում", None),
            ("ԲԺշկական պարագաներ և նյութեր", "", "Բժշկական պարագաներ և նյութեր", None),
            ("hաշվապահական ծառայությունների ձեռքբերում", "", "Հաշվապահական ծառայությունների ձեռքբերում", None),
            ("«ՀԱԷԿ» ՓԲԸ տարածքի դեռատիզացիոն, դեզինսեկցիոն, դեզինֆեկցիոն ծառայությունների մատուցում", "",
             "«ՀԱԷԿ» ՓԲԸ տարածքի դեռատիզացիոն, դեզինսեկցիոն, դեզինֆեկցիոն ծառայությունների մատուցում", None),
            ("Ամանորյա նվերների ձեռքբերում ԿՄՆՀՀ էԱՃԱՊՁԲ26/71", "ԿՄՆՀՀ-ԷԱՃԱՊՁԲ-26/71",
             "Ամանորյա նվերների ձեռքբերում", None),
        ]
        for title, code, subject, for_whom in cases:
            self.assertEqual(tp.split_title(title, code), (subject, for_whom), title)

    def test_shouting_titles_met_in_live_notices(self):
        cases = [
            ("«ԲԵՌԼԻՆ ՊՈԼԻԿԼԻՆԻԿԱ» ՓԲԸ-Ի ԿԱՐԻՔՆԵՐԻ ՀԱՄԱՐ` «ԲԺՇԿԱԿԱՆ ՆՇԱՆԱԿՈՒԹՅԱՆ ՊԱՐԱԳԱՆԵՐԻ» ԳՆՄԱՆ ՆՊԱՏԱԿՈՎ "
             "ՀԱՅՏԱՐԱՐՎԱԾ ԷԼԵԿՏՐՈՆԱՅԻՆ ԱՃՈՒՐԴ", "", "Բժշկական նշանակության պարագաների ձեռքբերում"),
            ("Հ Ր Ա Վ Ե Ր « ՀՐԱԶԴԱՆԻ ԲԺՇԿԱԿԱՆ ԿԵՆՏՐՈՆ ՓԲԸ »-Ի ԿԱՐԻՔՆԵՐԻ ՀԱՄԱՐ` « ԴԵՂՈՐԱՅՔԻ » ՁԵՌՔԲԵՐՄԱՆ "
             "ՆՊԱՏԱԿՈՎ ՀԱՅՏԱՐԱՐՎԱԾ ԷԼԵԿՏՐՈՆԱՅԻՆ ԱՃՈՒՐԴԻ", "", "Դեղորայքի ձեռքբերում"),
            ("ՃԱՄԲԱՐԱԿԻ ԱԿ ՓԲԸ ԿԱՐԻՔՆԵՐԻ ՀԱՄԱՐ ԱՆՀՐԱԺԵՇՏՈՒԹՅՈՒՆ Է ԱՌԱՋԱՑԵԼ ՃԱԿ-ԷԱՃԱՊՁԲ-26/23 ԾԱԾԿԱԳՐՈՎ "
             "համակարգիչների, բազմաֆունկցիոնալ և ջերմային տպիչների ձեռքբերումը", "ՃԱԿ-ԷԱՃԱՊՁԲ-26/23",
             "Համակարգիչների, բազմաֆունկցիոնալ և ջերմային տպիչների ձեռքբերում"),
            ("ՀԱՅԱՍՏԱՆԻ ԱԶԳԱՅԻՆ ՊՈԼԻՏԵԽՆԻԿԱԿԱՆ ՀԱՄԱԼՍԱՐԱՆ ՀԻՄՆԱԴՐԱՄԻ ԵՐԵՎԱՆԻ ՀԻՄՆԱԿԱՆ ԳՏՃԱՄ ԴՊՐՈՑԻ ԿԱՐԻՔՆԵՐԻ "
             "ՀԱՄԱՐ ՀԱՊՀ-ԷԱԱՊՁԲ-26/44 ԾԱԾԿԱԳՐՈՎ ԿՐԹԱԿԱՆ ՌՈԲՈՏԱՇԻՆՈՒԹՅԱՆ ՀԱՎԱՔԱԾՈՒՆԵՐԻ ԳՆՄԱՆ ՀՐԱՎԵՐ",
             "ՀԱՊՀ-ԷԱՃԱՊՁԲ-26/44", "Կրթական ռոբոտաշինության հավաքածուների գնում"),
            ("ՀՀ ԱՆ «ԻՆՖԵԿՑԻՈՆ ՀԻՎԱՆԴՈՒԹՅՈՒՆՆԵՐԻ ԱԶԳԱՅԻՆ ԿԵՆՏՐՈՆ» ՓԱԿ ԲԱԺՆԵՏԻՐԱԿԱՆ ԸՆԿԵՐՈՒԹՅԱՆ 2027Թ. ԿԱՐԻՔՆԵՐԻ "
             "ՀԱՄԱՐ ԱՆՎՏԱՆԳՈՒԹՅԱՆ ԱՊԱՀՈՎՄԱՆ ԾԱՌԱՅՈՒԹՅԱՆ ՁԵՌՔԲԵՐՈՒՄ 27/13", "",
             "Անվտանգության ապահովման ծառայության ձեռքբերում"),
        ]
        casing = tp.Casing().learn(["Վանաձորի բժշկական կենտրոն ՓԲԸ-ի կարիքների համար դեղորայքի ձեռքբերում"])
        for title, code, subject in cases:
            self.assertEqual(tp.split_title(casing.fix(title, "title"), code)[0], subject, title)

    def test_organisation_names_keep_their_quotes(self):
        self.assertEqual(tp.clean_name("«Կանաչապատում և շրջակա միջավայրի պահպանություն» ՀՈԱԿ"),
                         "«Կանաչապատում և շրջակա միջավայրի պահպանություն» ՀՈԱԿ")
        self.assertEqual(tp.clean_name("«Վանաձորի բժշկական կենտրոն»"), "Վանաձորի բժշկական կենտրոն")
        self.assertEqual(tp.clean_name("Մատենադարան» հիմնադրամ"), "Մատենադարան հիմնադրամ")
        casing = tp.Casing().learn(["Վանաձորում Սուրբ Ծննդյան միջոցառումների կազմակերպում"])
        self.assertEqual(casing.fix("Գյումրու ՍՈՒՐԲ Գրիգոր Նարեկացու անվան պոլիկլինիկա ՓԲԸ", "name"),
                         "Գյումրու Սուրբ Գրիգոր Նարեկացու անվան պոլիկլինիկա ՓԲԸ")

    def test_sector_words_met_in_live_notices(self):
        want = {"Ջեռուցման կաթսայի ձեռքբերում": "equip", "Մսի ձեռքբերում": "food",
                "Օդորակիչների ձեռքբերում": "equip", "Բազալտե խճի ձեռքբերում": "build",
                "Շարժիչի յուղի ձեռքբերում": "fuel", "Հեմոդիալիզի ձեռքբերում": "med",
                "Գեներատորի ձեռքբերում": "elec", "Կաթի ձեռքբերում": "food",
                "Ծառհան մեքենայի ձեռքբերում": "auto", "Ապրանքների ձեռքբերում": "other"}
        for text, sector in want.items():
            self.assertEqual(tp.classify(text, "goods"), sector, text)

    def test_buyer_names_are_readable(self):
        data = _built()
        self.assertEqual(data[48927]["buyer"], "Կարեն Դեմիրճյանի անվան Երևանի մետրոպոլիտեն ՓԲԸ")
        self.assertEqual(data[48956]["buyer"],
                         "ՀՀ բարձր տեխնոլոգիական արդյունաբերության և արհեստական բանականության նախարարություն")
        self.assertEqual(data[48938]["buyer"], "Վանաձորի բժշկական կենտրոն ՓԲԸ")
        self.assertEqual(data[48954]["buyer"], "Վարչապետի աշխատակազմ")  # already fine: untouched

    def test_bidder_names_are_written_as_names(self):
        for raw, want in [
            ("«ՆԵՔՍՏ ՋԵՆԵՐԵՅՇՆ» ՍՊԸ", "«Նեքստ Ջեներեյշն» ՍՊԸ"),
            ("ՍԵՎ-ԱՐՏ ԳՐՈՒՊ ՍՊԸ", "Սև-Արտ Գրուպ ՍՊԸ"),
            ("«ՍԵՅՖ ՎԻԺՆ» ՍԱՀՄԱՆԱՓԱԿ ՊԱՏԱՍԽԱՆԱՏՎՈՒԹՅԱՄԲ ԸՆԿԵՐՈՒԹՅՈՒՆ(ՍՊԸ)", "«Սեյֆ Վիժն» ՍՊԸ"),
            ('"ՆԱՏԱԼԻ ՖԱՐՄ" ՓԱԿ ԲԱԺՆԵՏԻՐԱԿԱՆ ԸՆԿԵՐՈՒԹՅՈՒՆ', "«Նատալի Ֆարմ» ՓԲԸ"),
            ("ՖԱՐՄ ԵՎ ՄԵԴ ՍՊԸ", "Ֆարմ և Մեդ ՍՊԸ"),
            ("«ՄԵԳԱ-ՖԱՐՄ»ՍՊԸ", "«Մեգա-Ֆարմ» ՍՊԸ"),
            ("«Արմինե Հովսեփյան Էլբեկի» Ա/Ձ", "«Արմինե Հովսեփյան Էլբեկի» ԱՁ"),
            ("Տեքստիլ Փիփ ՍՊԸ", "Տեքստիլ Փիփ ՍՊԸ"),               # already written as a name: untouched
            ("UNICOMP ՓԲԸ", "UNICOMP ՓԲԸ"),                     # Latin capitals are a trade mark
            ("ԲՍՏ ՍՊԸ", "ԲՍՏ ՍՊԸ"),                             # no vowel: an abbreviation
        ]:
            self.assertEqual(tp.company_name(raw), want, raw)

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

    def test_slow_site_is_cut_short_and_finished_next_run(self):
        pages = {armeps.list_url(1): list_page(SEED["tenders"])}
        calls = []

        def fake(url):
            calls.append(url)
            if url in pages:
                return pages[url]
            if "/start/" in url:
                return "<html><body><table></table></body></html>"
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        ticks = iter(range(0, 100000, 10))            # every look at the clock costs 10 "seconds"
        tenders: dict = {}
        stats = main.scrape(tenders, AT, fetch=fake, pause=0, budget=200, clock=lambda: next(ticks))
        self.assertEqual(stats["rows"], 30)           # every tender is known from the list
        self.assertGreater(stats["details"], 0)
        self.assertGreater(stats["postponed"], 0)     # but some notices had to wait
        self.assertEqual(stats["details"] + stats["postponed"], 29)
        waiting = [t for t in tenders.values() if t["status"] == "open" and not t.get("pub")]
        self.assertEqual(len(waiting), stats["postponed"])
        self.assertTrue(all("dt" not in t for t in waiting))   # not counted as a failed try

        stats = main.scrape(tenders, AT, fetch=fake, pause=0)  # next run, no hurry
        self.assertEqual(stats["details"], len(waiting))
        self.assertEqual(stats["postponed"], 0)
        self.assertTrue(all(t.get("pub") for t in tenders.values() if t["status"] == "open"))

    def test_dead_notice_pages_do_not_hold_the_run(self):
        pages = {armeps.list_url(1): list_page(SEED["tenders"])}
        asked = []

        def fake(url):
            if url in pages:
                return pages[url]
            if "/start/" in url:
                return "<html><body><table></table></body></html>"
            asked.append(url)
            raise armeps.ScrapeError("Could not open the notice.")

        tenders: dict = {}
        stats = main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual(stats["rows"], 30)
        self.assertEqual(stats["details"], 0)
        self.assertGreaterEqual(stats["detail_failed"], main.GIVE_UP_AFTER)
        self.assertLess(len(asked), 29)               # it stopped asking
        self.assertEqual(stats["detail_failed"] + stats["postponed"], 29)

    def test_a_later_list_page_failing_keeps_the_first_pages(self):
        def fake(url):
            if url == armeps.list_url(1):
                return list_page(SEED["tenders"])
            if "/start/" in url:
                raise armeps.ScrapeError("Could not open the list.")
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        tenders: dict = {}
        stats = main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual(stats["rows"], 30)
        self.assertEqual(stats["details"], 29)

    def test_a_tender_skipped_by_the_deadline_list_is_found_by_number(self):
        """Rows with the same deadline have no fixed order, so a page can leave one out."""
        everything = sorted(SEED["tenders"], key=lambda t: -t["id"])
        skipped = next(t for t in everything if t["status"] == "Հրապարակված")
        by_deadline = [t for t in SEED["tenders"] if t["id"] != skipped["id"]]
        header = '<a href="/hy/public/tender/by_id/2/">Հ/հ</a><a href="/hy/public/tender/by_code/2/">Ծածկագիր</a>'
        pages = {armeps.list_url(1): header + list_page(by_deadline),
                 armeps.list_url(1, "by_id"): header + list_page(everything)}
        asked = []

        def fake(url):
            asked.append(url)
            if url in pages:
                return pages[url]
            if "/start/" in url:
                return "<html><body><table></table></body></html>"
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        tenders: dict = {}
        stats = main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertIn(skipped["id"], tenders)
        self.assertEqual(stats["rows"], 30)
        self.assertTrue(tenders[skipped["id"]].get("pub"))            # and its notice was read
        self.assertIn(armeps.list_url(1, "by_id"), asked)
        self.assertEqual(armeps.sort_keys(pages[armeps.list_url(1)]),
                         ["by_code", "by_end_bid_time", "by_id"])

    def test_a_list_by_number_out_of_order_is_not_trusted(self):
        header = '<a href="/hy/public/tender/by_id/2/">Հ/հ</a><a href="/hy/public/tender/by_code/2/">Ծածկագիր</a>'
        shuffled = sorted(SEED["tenders"], key=lambda t: t["id"] % 7)
        pages = {armeps.list_url(1): header + list_page(SEED["tenders"][:20]),
                 armeps.list_url(1, "by_id"): list_page(shuffled)}

        def fake(url):
            if url in pages:
                return pages[url]
            if "/start/" in url:
                return "<html><body><table></table></body></html>"
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        tenders: dict = {}
        main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual(len(tenders), 20)

    def test_an_auction_taken_off_the_list_stops_looking_open(self):
        """An open auction missing from two whole walks of the list by number is marked as taken off."""
        header = '<a href="/hy/public/tender/by_id/2/">Հ/հ</a><a href="/hy/public/tender/by_code/2/">Ծածկագիր</a>'
        everything = sorted(SEED["tenders"], key=lambda t: -t["id"])
        open_ids = [t["id"] for t in everything if t["status"] == "Հրապարակված"]
        gone_id = open_ids[len(open_ids) // 2]              # not the oldest: the walk must reach past it
        rest = [t for t in everything if t["id"] != gone_id]
        lists = {"all": everything}

        def fake(url):
            if url == armeps.list_url(1):
                return header + list_page(lists["all"])
            if url == armeps.list_url(1, "by_id"):
                return header + list_page(lists["all"])
            if "/start/" in url:
                return "<html><body><table></table></body></html>"
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        tenders: dict = {}
        main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual(tenders[gone_id]["status"], "open")
        lists["all"] = rest
        stats = main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual((tenders[gone_id]["status"], tenders[gone_id].get("miss"), stats["gone"]), ("open", 1, 0))
        stats = main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual((tenders[gone_id]["status"], stats["gone"]), ("other", 1))
        self.assertTrue(tenders[gone_id]["gone"])
        self.assertTrue(all(tenders[i]["status"] == "open" for i in open_ids if i != gone_id))
        lists["all"] = everything                           # back on the list: open again
        main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual(tenders[gone_id]["status"], "open")
        self.assertNotIn("gone", tenders[gone_id])

    def test_a_walk_cut_short_marks_nothing(self):
        header = '<a href="/hy/public/tender/by_id/2/">Հ/հ</a>'
        everything = sorted(SEED["tenders"], key=lambda t: -t["id"])
        open_ids = [t["id"] for t in everything if t["status"] == "Հրապարակված"]
        gone_id = open_ids[0]
        top = [t for t in everything[:10] if t["id"] != gone_id]  # the list by number breaks after one page
        broken = {"on": False}

        def fake(url):
            if url == armeps.list_url(1):
                return header + list_page([t for t in everything if not broken["on"] or t["id"] != gone_id])
            if url == armeps.list_url(1, "by_id"):
                return header + list_page(top if broken["on"] else everything)
            if "/start/" in url:
                raise armeps.ScrapeError("HTTP Error 500")
            return detail_page(BY_ID[int(url.rstrip("/").rsplit("/", 1)[1])])

        tenders: dict = {}
        main.scrape(tenders, AT, fetch=fake, pause=0)
        broken["on"] = True
        for _ in range(3):
            main.scrape(tenders, AT, fetch=fake, pause=0)
        self.assertEqual(tenders[gone_id]["status"], "open")
        self.assertNotIn("miss", tenders[gone_id])

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


# --------------------------------------------------------------------------
# invitations and results
# --------------------------------------------------------------------------

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx(body: str) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {W_NS}><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def _p(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _tbl(rows) -> str:
    return "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in r) + "</w:tr>" for r in rows) + "</w:tbl>"


def invitation_zip() -> bytes:
    """A small invitation shaped like the real ones: the list of lots sits in a table inside a paragraph."""
    import io
    import zipfile
    lots = _tbl([["Ապրանքի"],
                 ["Հրավերով նախատեսված չափաբաժնի համարը", "միջանցիկ ծածկագիրը` ըստ ԳՄԱ դասակարգման (CPV)",
                  "Ամբողջական անվանումը", "Տեխնիկական բնութագիրը"],
                 ["1", "09132200/514", "բենզին, ռեգուլյար", "Արտաքին տեսքը` մաքուր և պարզ, օկտանային թիվը 91"],
                 ["2", "09134200/3", "դիզելային վառելիք", "Հայտ-տեխնիկական բնութագիր-կցված"]])
    plan = _tbl([["Ապրանքի"],
                 ["չափաբաժնի համարը", "Չափման միավորը", "Միավոր գինը", "Ընդհանուր գինը", "Ընդհանուր քանակը", "Մատակարարման"],
                 ["", "", "", "", "", "Հասցեն", "Ենթակա քանակը", "Ժամկետը"],
                 ["1", "լիտր", "", "", "8 670", "ք. Երևան, Ռոստոմի 30", "8670", "20 օրվա ընթացքում"],
                 ["2", "լիտր", "", "", "1200,5", "ք. Երևան, Ռոստոմի 30", "1200,5", "20 օրվա ընթացքում"]])
    body = (_p("ՀԱՅՏԱՐԱՐՈՒԹՅՈՒՆ") + _p("կարող եք դիմել գնահատող հանձնաժողովի քարտուղար Ա. Բ.-ին") + _p("Հեռախոս 010 51-56-91")
            + _p("Էլ. փոստ gnumner@example.am") + _p("Հ Ր Ա Վ Ե Ր")
            + f"<w:p><w:r><w:t>ՀՀ դրամ</w:t></w:r>{lots}</w:p>" + plan
            + _p("10.2 Որակավորման ապահովման չափը հավասար է սույն ընթացակարգի շրջանակում գնվելիք ապրանքի գնման գնի 15 տոկոսին:")
            + _p("10.3. Պայմանագրի ապահովման չափը կազմում է գնման գնի 10 տոկոսը:"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hraver_ru.docx", _docx(_p("ПРИГЛАШЕНИЕ")))
        z.writestr("hraver.docx", _docx(body))
    return buf.getvalue()


RESULT_PAGE = """<html><body>
<div class="fe_t">Ծածկագիր</div><div class="fe_v">ՓՈՐՁ-ԷԱՃԱՊՁԲ-26/7</div>
<div class="fe_t">Վերնագիր</div><div class="fe_v">Փորձնական հիմնարկի կարիքների համար վառելիքի ձեռքբերում</div>
<div class="fe_t">Գնորդ</div><div class="fe_v">«Փորձնական հիմնարկ» ՊՈԱԿ</div>
<div class="fe_t">Գնման տեսակ</div><div class="fe_v">Ապրանք</div>
<div class="fe_t">Պատասխաններ և պարզաբանումներ</div><table class="tb"><thead><tr><td>Հարցում</td><td>Ժամանակ</td></tr><thead><tbody></tbody></table>
<div class="fe_t">Հրապարակման ժամանակ</div><div class="fe_v">2026-10-01 10:00:00</div>
<div class="fe_t">Հայտերի ընդունման վերջնաժամկետ</div><div class="fe_v">2026-10-12 10:00:00</div>
<div class="fe_t">Հակադարձ աճուրդ</div><div class="fe_v">2026-10-13 10:00:00</div>
<div class="de_t">Կարգավիճակ</div><div class="de_v">Ավարտված</div>
<table class="tb"><thead><tr><td rowspan="2">Չափաբաժնի համար</td><td rowspan="2">Զբաղեցրած տեղ</td><td rowspan="2">Ներկայացված հայտեր</td>
<td rowspan="2">Նախահաշվային գին</td><td colspan="3">Նախնական առաջարկ</td><td colspan="3">Վերջին առաջարկ</td><td rowspan="2">Մասնակցի կարգավիճակ</td></tr>
<tr><td>Արժեք</td><td>ԱԱՀ</td><td>Գին</td><td>Արժեք</td><td>ԱԱՀ</td><td>Գին</td></tr></thead>
<tr><td>1</td><td>1</td><td><a href="https://eauction.armeps.am/hy/procurer/bo_details/by_end_bid_time/2/tid/900/id/11/.">«ԱՌԱՋԻՆ» ՍՊԸ</a>
 <a href='https://eauction.armeps.am/hy/dms/specification/bid_id/1'>Ապրանքի ամբողջական նկարագիր</a></td>
 <td>1200000 AMD</td><td>990000 AMD</td><td>20 %</td><td>1188000 AMD</td><td>800000 AMD</td><td>20 %</td><td>960000.00 AMD</td><td></td></tr>
<tr><td>1</td><td>2</td><td><a href="https://eauction.armeps.am/hy/procurer/bo_details/by_end_bid_time/2/tid/900/id/12/.">Երկրորդ ՓԲԸ</a></td>
 <td>1200000 AMD</td><td>1000000 AMD</td><td>20 %</td><td>1200000 AMD</td><td>810000 AMD</td><td>20 %</td><td>972000.00 AMD</td><td></td></tr>
<tr><td>2</td><td>1</td><td><a href="https://eauction.armeps.am/hy/procurer/bo_details/by_end_bid_time/2/tid/900/id/13/.">Անուն Ազգանուն ԱՁ</a></td>
 <td>500000 AMD</td><td>400000 AMD</td><td>0 %</td><td>400000 AMD</td><td>300000 AMD</td><td>0 %</td><td>300000.00 AMD</td><td>Մերժված</td></tr>
<tr><td>2</td><td>2</td><td><a href="https://eauction.armeps.am/hy/procurer/bo_details/by_end_bid_time/2/tid/900/id/12/.">Երկրորդ ՓԲԸ</a></td>
 <td>500000 AMD</td><td>500000 AMD</td><td>20 %</td><td>500000 AMD</td><td>375000 AMD</td><td>20 %</td><td>450000.00 AMD</td><td></td></tr>
</table>
<table class="tb"><thead><tr><td>Չափաբաժնի համար</td><td>CPV</td><td>Անվանում</td><td>Գնառաջարկներ</td></tr></thead><tbody>
<tr><td>1</td><td>09132200/514</td><td>բենզին, ռեգուլյար</td><td><table class="tb"><tr><td>«ԱՌԱՋԻՆ» ՍՊԸ</td><td>800000 AMD</td><td>2026-10-13 10:05:00</td></tr></table>
<tr><td>2</td><td>09134200/3</td><td>դիզելային վառելիք</td><td><table class="tb"><tr><td>Երկրորդ ՓԲԸ</td><td>375000 AMD</td><td>2026-10-13 10:06:00</td></tr></table>
</tbody></table></body></html>"""


class Invitations(unittest.TestCase):
    def test_lots_quantities_and_guarantees(self):
        from bot import invite
        info = invite.read(invitation_zip())
        self.assertEqual([(l["n"], l["cpv"], l["name"]) for l in info["lots"]],
                         [(1, "09132200", "բենզին, ռեգուլյար"), (2, "09134200", "դիզելային վառելիք")])
        self.assertEqual((info["lots"][0]["unit"], info["lots"][0]["qty"]), ("լիտր", 8670.0))
        self.assertEqual(info["lots"][1]["qty"], 1200.5)
        self.assertTrue(info["lots"][0]["spec"].startswith("Արտաքին տեսքը"))
        self.assertEqual(info["lots"][1]["spec"], "")           # "see the attached file" is not a description
        self.assertEqual(info["sec"], {"qual": 15.0, "contract": 10.0})
        self.assertEqual(info["ask"], {"phone": "010515691", "mail": "gnumner@example.am"})
        self.assertEqual(info["files"], ["hraver_ru.docx", "hraver.docx"])

    def test_a_broken_archive_is_not_an_error(self):
        from bot import invite
        self.assertIsNone(invite.read(b"not a zip"))

    def test_the_schedule_of_a_service_has_one_column_fewer(self):
        import io
        import zipfile
        from bot import invite
        lots = _tbl([["Ծառայության"],
                     ["Հրավերով նախատեսված չափաբաժնի համարը", "միջանցիկ ծածկագիրը` ըստ ԳՄԱ դասակարգման (CPV)", "Անվանումը", "Տեխնիկական բնութագիրը"],
                     ["1", "79711130/1", "պահնորդական ծառայություններ", "Շուրջօրյա պահպանություն"]])
        long_term = "Պայմանագիրն ուժի մեջ մտնելու օրվանից " + "շատ երկար պայման " * 30
        plan = _tbl([["Ծառայության"],
                     ["չափաբաժնի համարը", "Չափման միավորը", "Միավոր գինը", "Ընդհանուր գինը", "Ընդհանուր քանակը", "Մատուցման"],
                     ["", "", "", "", "", "Հասցեն", "Ժամկետը**"],
                     ["1", "դրամ", "", "", "1", "ք. Աբովյան, Հանրապետության 1ք. Աբովյան, Հանրապետության 1", long_term]])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("hraver.docx", _docx(f"<w:p>{lots}</w:p>" + plan))
        lot = invite.read(buf.getvalue())["lots"][0]
        self.assertEqual(lot["addr"], "ք. Աբովյան, Հանրապետության 1")      # a merged cell read twice is said once
        self.assertTrue(lot["when"].startswith("Պայմանագիրն ուժի մեջ մտնելու օրվանից"))
        self.assertTrue(lot["when"].endswith("…") and len(lot["when"]) <= 401)


class Results(unittest.TestCase):
    def test_lots_and_bids(self):
        from bot import results
        out = results.parse(RESULT_PAGE)
        self.assertEqual(out["lots"], {1: {"cpv": "09132200", "title": "բենզին, ռեգուլյար"},
                                       2: {"cpv": "09134200", "title": "դիզելային վառելիք"}})
        self.assertEqual(len(out["bids"]), 4)
        first = out["bids"][0]
        self.assertEqual((first["lot"], first["place"], first["cid"], first["name"]), (1, 1, 11, "«ԱՌԱՋԻՆ» ՍՊԸ"))
        self.assertEqual((first["est"], first["fp"], first["lv"], first["lp"], first["rej"]),
                         (1200000.0, 1188000.0, 800000.0, 960000.0, 0))
        self.assertEqual(out["bids"][2]["rej"], 1)
        self.assertTrue(results.is_person("Անուն Ազգանուն ԱՁ"))
        self.assertTrue(results.is_person("ԱՁ Անուն Ազգանուն"))
        self.assertFalse(results.is_person("«ԱՌԱՋԻՆ» ՍՊԸ"))

    def test_the_slow_job_end_to_end(self):
        from bot import deep
        at = datetime(2026, 11, 16, 14, 0)
        asked = []

        def fetch_page(url):
            asked.append(url)
            if url.rstrip("/").endswith("/900"):
                return RESULT_PAGE
            raise armeps.Missing("no such tender")

        def fetch_bytes(url):
            asked.append(url)
            return invitation_zip()

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                store.save({"meta": {}, "tenders": [
                    {"id": 905, "code": "Ա-ԷԱՃԱՊՁԲ-26/9", "title": "վառելիքի ձեռքբերում", "status": "open",
                     "end": "2026-11-25T10:00"}]})
                with open(deep.HIST_STATE, "w", encoding="utf-8") as fh:
                    json.dump({"floor": 897}, fh)
                deep.PAUSE = 0
                ticks = iter(range(10 ** 7))
                clock = lambda: next(ticks) * 0.001
                deep.run(30, at, fetch_bytes, fetch_page, now=clock)

                with open(os.path.join(deep.OUT_T, "905.json"), encoding="utf-8") as fh:
                    page = json.load(fh)
                self.assertEqual(len(page["lots"]), 2)
                self.assertEqual(page["addr"], "ք. Երևան, Ռոստոմի 30")     # the same for both lots: said once
                self.assertNotIn("addr", page["lots"][0])
                with open(deep.OUT_LOTS, encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh)["t"]["905"]["cpv"], ["09132200", "09134200"])

                with open(os.path.join(deep.OUT_H, "r", "18.json"), encoding="utf-8") as fh:
                    rec = json.load(fh)["900"]
                self.assertEqual(rec["subject"], "Վառելիքի ձեռքբերում")
                self.assertEqual(rec["lots"][0]["bids"][0]["nm"], "«Առաջին» ՍՊԸ")
                with open(os.path.join(deep.OUT_H, "companies.json"), encoding="utf-8") as fh:
                    companies = json.load(fh)
                self.assertEqual(companies["12"][1:], [2, 1])           # bid on two lots, best accepted on one
                self.assertNotIn("13", companies)                       # a sole proprietor gets no page
                with open(os.path.join(deep.OUT_H, "recent.json"), encoding="utf-8") as fh:
                    row = json.load(fh)["rows"][0]
                self.assertEqual(row[:1] + row[6:10], [900, 2, 3, 1700000, 1410000])
                with open(os.path.join(deep.OUT_H, "v", "09134.json"), encoding="utf-8") as fh:
                    lot = json.load(fh)["rows"][0]
                self.assertEqual(lot[7], 450000.0)                      # the rejected lower bid does not count
                self.assertEqual([c[1] for c in lot[9]], ["Երկրորդ ՓԲԸ"])

                before = len(asked)
                deep.run(30, at, fetch_bytes, fetch_page, now=clock)
                self.assertEqual(len(asked), before)                    # nothing is read twice
            finally:
                os.chdir(cwd)


class ResultsLater(unittest.TestCase):
    """What the page of a finished tender leaves out, and what can still change on it."""

    def _run(self, page, at, hist=None, zips=None):
        from bot import deep
        asked = []

        def fetch_page(url):
            asked.append(url)
            if url.rstrip("/").endswith("/900"):
                return page
            raise armeps.Missing("no such tender")

        def fetch_bytes(url):
            asked.append(url)
            if zips is not None and "tender_900" in url:
                zips.append(url)
            return invitation_zip()

        if hist is not None:
            os.makedirs(os.path.dirname(deep.HIST_STATE), exist_ok=True)
            with open(deep.HIST_STATE, "w", encoding="utf-8") as fh:
                json.dump(hist, fh)
        deep.PAUSE = 0
        ticks = iter(range(10 ** 7))
        deep.run(30, at, fetch_bytes, fetch_page, now=lambda: next(ticks) * 0.001)
        return asked

    def _in_tmp(self, body):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                store.save({"meta": {}, "tenders": [
                    {"id": 905, "code": "Ա-ԷԱՃԱՊՁԲ-26/9", "title": "վառելիքի ձեռքբերում", "status": "open",
                     "end": "2026-12-25T10:00"}]})
                body()
            finally:
                os.chdir(cwd)

    def test_an_amended_notice_is_not_waited_for(self):
        from bot import deep
        old = RESULT_PAGE[:RESULT_PAGE.index('<table class="tb"><thead><tr><td rowspan="2">')].replace('<div class="de_v">Ավարտված</div>', '<div class="de_v">Փոփոխված</div>')

        def body():
            at = datetime(2026, 11, 16, 14, 0)
            self._run(old, at, {"floor": 897})
            with open(deep.HIST_STATE, encoding="utf-8") as fh:
                hist = json.load(fh)
            self.assertEqual((hist["done"].count(900), hist["retry"]), (1, {}))
            self.assertFalse(os.path.exists(os.path.join(deep.OUT_H, "r", "18.json")))
        self._in_tmp(body)

    def test_a_lot_with_one_bidder_is_named_from_the_invitation(self):
        from bot import deep
        # only lots that went to auction are listed with a name; lot 2 here is not
        page = RESULT_PAGE.replace('<tr><td>2</td><td>09134200/3</td><td>դիզելային վառելիք</td>', '<tr><td>7</td><td>09134200/3</td><td>այլ</td>')

        def body():
            zips = []
            self._run(page, datetime(2026, 11, 16, 14, 0), {"floor": 897}, zips)
            self.assertEqual(len(zips), 1)                              # asked once, for the tender with the nameless lot
            with open(os.path.join(deep.OUT_H, "r", "18.json"), encoding="utf-8") as fh:
                lots = json.load(fh)["900"]["lots"]
            self.assertEqual((lots[1]["cpv"], lots[1]["t"], lots[1]["q"], lots[1]["u"]), ("09134200", "դիզելային վառելիք", 1200.5, "լիտր"))
            self.assertEqual((lots[0]["t"], lots[0]["q"]), ("բենզին, ռեգուլյար", 8670.0))
            with open(os.path.join(deep.OUT_H, "v", "09134.json"), encoding="utf-8") as fh:
                row = json.load(fh)["rows"][0]
            self.assertEqual(row[10:12], [1200.5, "լիտր"])
        self._in_tmp(body)

    def test_an_invitation_that_did_not_come_is_asked_for_again_a_few_times(self):
        from bot import deep
        page = RESULT_PAGE.replace('<tr><td>2</td><td>09134200/3</td><td>դիզելային վառելիք</td>', '<tr><td>7</td><td>09134200/3</td><td>այլ</td>')
        calls = []

        def run(at, hist=None):
            def fetch_page(url):
                if url.rstrip("/").endswith("/900"):
                    return page
                raise armeps.Missing("no such tender")

            def fetch_bytes(url):
                if "tender_900" in url:
                    calls.append(url)
                    raise armeps.ScrapeError("connection reset")
                return invitation_zip()

            if hist is not None:
                os.makedirs(os.path.dirname(deep.HIST_STATE), exist_ok=True)
                with open(deep.HIST_STATE, "w", encoding="utf-8") as fh:
                    json.dump(hist, fh)
            deep.PAUSE = 0
            ticks = iter(range(10 ** 7))
            deep.run(30, at, fetch_bytes, fetch_page, now=lambda: next(ticks) * 0.001)

        def body():
            at = datetime(2026, 11, 16, 14, 0)
            run(at, {"floor": 897})
            for days in (3, 6, 9, 12):
                run(at + timedelta(days=days))
            self.assertEqual(len(calls), 3)                             # three tries, then the lot stays unnamed
            with open(deep.HIST_STATE, encoding="utf-8") as fh:
                hist = json.load(fh)
            self.assertEqual((hist["recheck"], hist["done"].count(900)), ({}, 1))
            with open(os.path.join(deep.OUT_H, "r", "18.json"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["900"]["lots"][1]["t"], "")
        self._in_tmp(body)

    def test_a_tender_still_being_awarded_is_shown_and_read_again(self):
        from bot import deep
        awarding = RESULT_PAGE.replace('<div class="de_v">Ավարտված</div>', '<div class="de_v">Շնորհում</div>')
        # later the buyer turns the first bidder down and the tender is closed
        closed = RESULT_PAGE.replace('<td>960000.00 AMD</td><td></td>', '<td>960000.00 AMD</td><td>Մերժված</td>')
        self.assertEqual((deep.stage("Շնորհում"), deep.stage("Ավարտված"), deep.stage("Չկայացած"), deep.stage("Չեղարկված"),
                          deep.stage("Նախաաճուրդային")), ("award", "", "f", "c", "early"))
        # between the auction and the award the stage has other names; with bids on the page it is a result all the same
        odd = deep.record_from(900, RESULT_PAGE.replace('<div class="de_v">Ավարտված</div>', '<div class="de_v">Դիմում-Հայտարարության գնահատում</div>'))
        self.assertEqual((deep.stage(odd["st"]), deep.shown_stage(odd)), ("early", "award"))

        def recent():
            with open(os.path.join(deep.OUT_H, "recent.json"), encoding="utf-8") as fh:
                return json.load(fh)["rows"][0]

        def hist():
            with open(deep.HIST_STATE, encoding="utf-8") as fh:
                return json.load(fh)

        def body():
            at = datetime(2026, 11, 16, 14, 0)
            self._run(awarding, at, {"floor": 897})
            self.assertEqual((recent()[10], recent()[12]), ("«Առաջին» ՍՊԸ", "a"))
            self.assertEqual((list(hist()["recheck"]), hist()["done"].count(900)), (["900"], 0))
            asked = self._run(closed, at + timedelta(hours=10))
            self.assertFalse([u for u in asked if u.rstrip("/").endswith("/900")])      # too soon to look again
            self._run(closed, at + timedelta(hours=50))
            self.assertEqual((recent()[10], recent()[12]), ("Երկրորդ ՓԲԸ", ""))        # the next bidder leads now
            self.assertEqual((hist()["recheck"], hist()["done"].count(900)), ({}, 1))
        self._in_tmp(body)


if __name__ == "__main__":
    unittest.main()
