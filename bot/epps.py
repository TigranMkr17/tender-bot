"""Calls for tender on ARMEPS's EPPS (www.armeps.am/epps): price quotations, open and urgent tenders,
two-stage and framework procedures. The electronic auctions live elsewhere (eauction.armeps.am, see armeps.py).

EPPS keeps a search in the visitor's session: the list of calls now taking bids opens in pages of ten, and
the pager asks for the search by a key the first page carries. A call's own page lists its facts as
label and value pairs. Everything here is public: no login is used.

    python -m bot.epps --probe 5     reads the list and five calls, and prints what it understood
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html.parser import HTMLParser

from . import armeps, store

BASE = "https://www.armeps.am/epps"
HOME = BASE + "/home.do"
SEARCH = BASE + "/viewCFTSAction.do?status=cft.status.tender.submission"
PAGER = BASE + "/pageIterator/advancedSearchCFT.do"
DETAIL = BASE + "/cft/prepareViewCfTWS.do?resourceId={id}"
PER_PAGE = 75            # the largest page the pager offers
MAX_PAGES = 30
BUDGET = 8 * 60          # seconds one run may spend on EPPS; calls not read in time wait for the next run
REREAD = timedelta(hours=20)   # a call's page is read again after this, for a moved deadline or a new date
WORKERS = 2
GIVE_UP_AFTER = 8
LIST_TRIES = 2       # a list shorter than EPPS's own count is asked for again once

_WS = re.compile(r"\s+")
_RID = re.compile(r"prepareViewCfTWS\.do\?resourceId=(\d+)")
_TOTAL = re.compile(r"<strong>\s*(\d[\d\s,.]*)\s*</strong>\s*արդյունք")
_MASTER = re.compile(r"sortForm\.masterKey\.value\s*=\s*\"([^\"]+)\"")
_ORG = re.compile(r"prepareViewCAOrganisation\.do\?id=(\d+)")


def clean(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


# ---------- reading pages ----------

class Session:
    """One visitor: cookies kept from page to page, a few tries per page, a short pause between pages."""

    def __init__(self, timeout: int = 40, retries: int = 3, pause: float = 0.4):
        self.timeout, self.retries, self.pause = timeout, retries, pause
        self.fresh()

    def fresh(self) -> None:
        """Forget the cookies: the next page opens a new visit, with a new search."""
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, url: str) -> str:
        last = None
        for attempt in range(self.retries):
            req = urllib.request.Request(url, headers={"User-Agent": armeps.USER_AGENT, "Accept-Language": "hy,en;q=0.8"})
            try:
                with self.opener.open(req, timeout=self.timeout) as r:
                    body = r.read()
                if self.pause:
                    time.sleep(self.pause)
                return body.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code == 404:
                    break
            except Exception as e:                       # timeouts, resets: try again after a breath
                last = repr(e)
            time.sleep(1.5 * (attempt + 1))
        raise armeps.ScrapeError(f"{url} did not open: {last}")


class _Results(HTMLParser):
    """Rows of the search results: each holds a link to a call, then the buyer's name."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list] = []
        self._row = None
        self._cell = None
        self._rid = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row, self._rid = [], None
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "a" and self._row is not None:
            m = _RID.search(a.get("href") or "")
            if m:
                self._rid = int(m.group(1))

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(clean("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._rid is not None:
                self.rows.append([self._rid] + self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_list(html: str) -> tuple[list[dict], int | None, str | None]:
    """The calls on one results page, the number of calls the search found, and the key the pager needs."""
    p = _Results()
    p.feed(html)
    rows, seen = [], set()
    for rid, *cells in p.rows:
        if rid in seen:
            continue
        seen.add(rid)
        texts = [c for c in cells if c and not c.isdigit()]
        rows.append({"id": rid, "title": texts[0] if texts else "", "buyer": texts[1] if len(texts) > 1 else ""})
    m = _TOTAL.search(html)
    total = int(re.sub(r"\D", "", m.group(1))) if m else None
    k = _MASTER.search(html)
    return rows, total, (k.group(1) if k else None)


def pager_url(master: str, action: str, page: int | None = None, per: int = PER_PAGE) -> str:
    """The address the results page's own pager would open (goPage2 and sortBy in its script)."""
    q = [("subKey", "results['entriesCollection']"), ("masterKey", master), ("paths", "results['entriesCollection']"),
         ("currentPath", "results[entriesCollection]"), ("actionKind", action), ("sortByField", " "),
         ("selectedPos", ""), ("hiddenPos", ""), ("paging_results_per_page", str(per)),
         ("paging_go_to_page", str(page or "")), ("type", "cft"), ("quickSearch", "null"), ("searchCriteria", "null")]
    return PAGER + "?" + urllib.parse.urlencode(q)


def _walk(session: Session) -> tuple[dict[int, dict], int | None]:
    """One pass over the search: the calls it gave, and how many EPPS says it has."""
    session.get(HOME)                                       # the search lives in the session this opens
    html = session.get(SEARCH)
    rows, total, master = parse_list(html)
    if not rows:
        raise armeps.ScrapeError("The EPPS search opened but no calls were found on it.")
    found = {r["id"]: r for r in rows}
    if total and total > len(found) and master:
        html = session.get(pager_url(master, "paging_results_per_page", 1))
        got, _, master = parse_list(html)
        found.update((r["id"], r) for r in got)
        page = 1
        while len(found) < total and master and page < MAX_PAGES:
            page += 1
            got, _, key = parse_list(session.get(pager_url(master, "paging_go_to_page", page)))
            master = key or master
            fresh = [r for r in got if r["id"] not in found]
            if not fresh:
                break
            found.update((r["id"], r) for r in fresh)
    return found, total


def list_open(session: Session, say=print) -> tuple[list[dict], bool]:
    """Every call now taking bids, and whether that is the whole list. Raises ScrapeError when even the first
    page cannot be read.

    EPPS says how many calls it has. The pager sometimes answers with an empty page, which leaves the list
    short: the search is then asked for again, once, as a new visitor. A list that stays short is used to add
    and update calls, never to decide that a call has left the site."""
    for attempt in range(1, LIST_TRIES + 1):
        found, total = _walk(session)
        whole = bool(total) and len(found) >= total
        if whole or not total:
            break
        if attempt < LIST_TRIES:
            say(f"! EPPS: {len(found)} of {total} calls could be listed; asking again.")
            session.fresh()
        else:
            say(f"! EPPS: {len(found)} of {total} calls could be listed. No call is taken off the site "
                "on a list this short.")
    return list(found.values()), whole


# ---------- one call's page ----------

LABELS = {
    "Վերնագիր": "title", "Վերնագիր (EN)": "title_en", "Վերնագիր (RU)": "title_ru",
    "Ընթացակարգի ծածկագիր": "code", "ՄՀ առանձնահատուկ հ/հ": "uid",
    "Պայմանագրային պատվիրատուի անունը": "buyer", "Նկարագրություն": "desc",
    "Գնումների տիպը": "kind", "Ընթացակարգ": "procedure", "ԳԸԲ կոդեր": "cpv",
    "Մոտավոր արժեքը (ՀԴ)": "value",
    "Ժամանակի սահմանափակում հայտերի ստացման կամ մասնակցության հայտերի համար": "deadline",
    "Հայտերի ներկայացման վերջնաժամկետ (օրերով/ժամերով)": "left",
    "Պարզաբանումների հարցում (սկսած-մինչև)": "questions", "Հայտերի բացման ամսաթիվը": "opening",
    "Հրատարակման/Հրավերի օր": "published", "Միափուլ կամ երկփուլ ներկայացում": "stages",
    "Չափաբաժիններով շնորհված պայմանագիր": "by_lots", "Գնահատման մեխանիզմ": "evaluation",
    "Հրավերների առաքման վերջնաժամկետ": "invites_until", "Շնորհման օր": "awarded",
    "է-Աճուրդների հավելումներ": "eauction",
}
_LABEL_KEYS = {clean(k).lower(): v for k, v in LABELS.items()}


class _Grid(HTMLParser):
    """The label and value pairs of <dl class="Grid">, and the buyer's organisation number."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pairs: list[tuple[str, str]] = []
        self.org = None
        self._in_dl = 0
        self._dt = None
        self._dd = None
        self._label = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "dl":
            self._in_dl += 1
        elif tag == "dt" and self._in_dl:
            self._dt = []
        elif tag == "dd" and self._in_dl:
            self._dd = []
        elif tag == "a" and self._dd is not None and self.org is None:
            m = _ORG.search(a.get("href") or "")
            if m:
                self.org = int(m.group(1))
        elif tag == "br" and self._dd is not None:
            self._dd.append(" ")

    def handle_endtag(self, tag):
        if tag == "dl" and self._in_dl:
            self._in_dl -= 1
        elif tag == "dt" and self._dt is not None:
            self._label = clean("".join(self._dt))
            self._dt = None
        elif tag == "dd" and self._dd is not None:
            if self._label is not None:
                self.pairs.append((self._label, clean("".join(self._dd))))
            self._dd, self._label = None, None

    def handle_data(self, data):
        if self._dt is not None:
            self._dt.append(data)
        elif self._dd is not None:
            self._dd.append(data)


_DATE_FORMS = [
    (re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})(?:\D+(\d{1,2}):(\d{2}))?"), ("d", "m", "y", "H", "M")),
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:\D+(\d{1,2}):(\d{2}))?"), ("y", "m", "d", "H", "M")),
]


def dates(text: str | None) -> list[str]:
    """Every date in a value, as YYYY-MM-DDTHH:MM in Yerevan time (EPPS shows Yerevan time)."""
    out = []
    for rx, order in _DATE_FORMS:
        for m in rx.finditer(text or ""):
            v = dict(zip(order, m.groups()))
            try:
                dt = datetime(int(v["y"]), int(v["m"]), int(v["d"]), int(v["H"] or 0), int(v["M"] or 0))
            except ValueError:
                continue
            out.append((m.start(), dt.strftime("%Y-%m-%dT%H:%M")))
        if out:
            break
    return [d for _, d in sorted(out)]


def amount(text: str | None) -> int | None:
    """A value in dram: '12,500,000.00' or '12 500 000' -> 12500000."""
    m = re.search(r"\d[\d\s,. ]*", text or "")
    if not m:
        return None
    s = re.sub(r"[\s ]", "", m.group(0))
    s = re.sub(r"[.,]\d{1,2}$", "", s)                     # kopecks
    s = re.sub(r"\D", "", s)
    return int(s) if s else None


def parse_detail(html: str) -> dict:
    """What a call's page says, by field. Unknown labels are kept under 'other' so a new field can be seen."""
    g = _Grid()
    g.feed(html)
    d: dict = {"other": {}}
    for label, value in g.pairs:
        key = _LABEL_KEYS.get(label.lower())
        if key is None:
            if value:
                d["other"][label] = value[:200]
            continue
        if value and not d.get(key):
            d[key] = value
    if g.org:
        d["org"] = g.org
    if not d["other"]:
        del d["other"]
    return d


PROCEDURES = [            # how EPPS names a procedure -> the short form the register uses
    ("գնանշման հարցում", "ԳՀ"), ("բաց (հրատապ)", "ՀԲՄ"), ("հրատապ", "ՀԲՄ"), ("բաց ազգային", "ԲՄ"),
    ("երկփուլ", "ԵՄ"), ("շրջանակային", "ՇՀ"), ("դրամաշնորհ", "ԴՄ"), ("մեկ անձից", "ՄԱ"),
    ("բանակցային", "ԲԸ"), ("պարզեցված", "ՊԸ"), ("սահմանափակ", "ՍԸ"), ("մրցակցային երկխոսություն", "ՄԵ"), ("բաց", "ԲՄ"),
]
KINDS = {"ապրանքներ": "goods", "ծառայություններ": "services", "աշխատանքներ": "works"}


def procedure_key(text: str | None) -> str | None:
    low = clean(text).lower()
    if not low:
        return None
    for word, key in PROCEDURES:
        if word in low:
            return key
    return None


def apply(t: dict, d: dict) -> None:
    """Put what a call's page says into the stored tender."""
    if d.get("title"):
        t["title"] = d["title"]
    en = clean(d.get("title_en"))
    if len(en) >= 12 and " " in en:                         # some calls carry a placeholder word here
        t["title_en"] = en[:300]
    if d.get("code"):
        t["code"] = d["code"]
    if d.get("buyer"):
        t["buyer_official"] = d["buyer"]
    if d.get("org"):
        t["org"] = d["org"]
    kind = KINDS.get(clean(d.get("kind")).lower())
    if kind:
        t["kind"] = kind
    pr = procedure_key(d.get("procedure"))
    if pr:
        t["pr"] = pr
    if d.get("procedure"):
        t["procedure"] = d["procedure"]
    if d.get("desc"):
        t["desc"] = d["desc"][:600]
    value = amount(d.get("value"))
    if value:
        t["est"] = value
    end = dates(d.get("deadline"))
    if end:
        t["end"] = end[-1]
    q = dates(d.get("questions"))
    if q:
        t["ask"] = q[-1]
    o = dates(d.get("opening"))
    if o:
        t["opn"] = o[0]
    p = dates(d.get("published"))
    if p:
        t["pub"] = p[0]
    if d.get("cpv"):
        t["cpv"] = d["cpv"][:300]


# ---------- one run ----------

def update(tenders: dict[int, dict], at: datetime, session: Session | None = None, budget: float = BUDGET,
           clock=time.monotonic, say=print, workers: int = WORKERS, skip: set[int] = frozenset()) -> dict:
    """Add the calls now taking bids to `tenders` (keyed by id, shared with the auctions) and read the page of
    every call that is new, or whose page was read long ago. Calls that left the list early are marked.
    `skip` holds calls already gone from the site whose deadline passed long ago but which EPPS still lists:
    they are not added again as new."""
    started = clock()
    session = session or Session()
    stats = {"listed": 0, "new": 0, "details": 0, "detail_failed": 0, "postponed": 0, "gone": 0}
    mine = {i: t for i, t in tenders.items() if t.get("src") == "epps"}
    first_run = not mine
    rows, whole = list_open(session, say=say)
    listed = {r["id"] for r in rows}
    stats["listed"] = len(rows)
    stats["ids"] = listed
    stats["whole"] = whole
    for r in rows:
        if r["id"] in skip and r["id"] not in tenders:
            continue
        t = tenders.get(r["id"])
        if t is None:
            t = tenders[r["id"]] = {"id": r["id"], "src": "epps"}
            if not first_run:
                t["seen"] = store.stamp(at)
            stats["new"] += 1
        t["src"] = "epps"
        t["status"] = "open"
        t.pop("gone", None)
        if not t.get("title") or not t.get("pub"):
            t["title"] = r["title"] or t.get("title")
        if r["buyer"] and not t.get("buyer_official"):
            t["buyer_official"] = r["buyer"]
    for i, t in mine.items():                               # taken off the list before its deadline: no longer open
        if whole and i not in listed and t.get("status") == "open":
            end = store.parse(t.get("end"))
            if end is None or end > at:
                t["status"] = "other"
                t["gone"] = store.stamp(at)
                stats["gone"] += 1

    def due(t: dict) -> bool:
        """Never read and not yet failed three times, or read long ago (a deadline may have moved)."""
        if t.get("status") != "open":
            return False
        read = store.parse(t.get("dtat"))
        return t.get("dt", 0) < 3 if read is None else at - read > REREAD

    todo = sorted((t for t in tenders.values() if t.get("src") == "epps" and due(t)), key=lambda t: (t.get("dtat") is not None, -t["id"]))
    failing = [0]

    def read(t: dict):
        if failing[0] >= GIVE_UP_AFTER or clock() - started > budget:
            return None, "later"
        try:
            d = parse_detail(session.get(DETAIL.format(id=t["id"])))
        except armeps.ScrapeError as exc:
            failing[0] += 1
            return None, str(exc)
        if not d.get("title") and not d.get("deadline"):
            failing[0] += 1
            return None, "the page opened but had no call on it"
        failing[0] = 0
        return d, ""

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for t, (d, err) in zip(todo, pool.map(read, todo)):
            if err == "later":
                stats["postponed"] += 1
                continue
            if d is None:
                t["dt"] = t.get("dt", 0) + 1
                stats["detail_failed"] += 1
                if stats["detail_failed"] <= 5:
                    say(f"! EPPS call {t['id']}: {err}")
                continue
            apply(t, d)
            t["dtat"] = store.stamp(at)
            t.pop("dt", None)
            stats["details"] += 1
    say(f"EPPS: {stats['listed']} calls taking bids, {stats['new']} new, {stats['details']} pages read"
        + (f", {stats['detail_failed']} unreadable" if stats["detail_failed"] else "")
        + (f", {stats['postponed']} left for the next run" if stats["postponed"] else "")
        + (f", {stats['gone']} taken off the list" if stats["gone"] else ""))
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probe", type=int, default=3, help="read the list and this many calls, print, save nothing")
    args = ap.parse_args(argv)
    s = Session()
    rows, whole = list_open(s)
    print("The whole list." if whole else "! Not the whole list.")
    print(f"{len(rows)} calls listed. First: {json.dumps(rows[:3], ensure_ascii=False)}")
    for r in rows[:args.probe]:
        html = s.get(DETAIL.format(id=r["id"]))
        d = parse_detail(html)
        t = {"id": r["id"]}
        apply(t, d)
        print(json.dumps({"raw": d, "stored": t}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
