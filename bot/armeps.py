"""Read the public tender list and notice pages of eauction.armeps.am.

Only the Python standard library is used, so the scheduled job needs no
package installation. Parsing is deliberately tolerant: it looks for the
shape of the data (a row with a number, a code, a title and a date) rather
than for specific CSS classes, so small changes to the site do not break it.
"""
from __future__ import annotations

import http.client
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

BASE = "https://eauction.armeps.am"
LIST_FIRST = BASE + "/hy/public/tender/by_end_bid_time/2/"
LIST_PAGE = BASE + "/hy/public/tender/by_end_bid_time/2/start/{page}"
DETAIL = BASE + "/hy/public/tender_details/by_end_bid_time/2/tid/{id}/"

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0 Safari/537.36 tender-bot/1.0")

_DT = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?")
_WS = re.compile(r"\s+")
_TID = re.compile(r"tid/(\d+)")


class ScrapeError(RuntimeError):
    """The site answered, but not with anything we can read."""


def clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def norm_dt(text: str | None) -> str | None:
    """'2026-11-30 12:30:00' -> '2026-11-30T12:30' (Yerevan local time)."""
    m = _DT.search(text or "")
    return f"{m.group(1)}T{m.group(2)}" if m else None


def fetch(url: str, retries: int = 3, timeout: int = 40) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "hy,en;q=0.5",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except (OSError, http.client.HTTPException) as exc:   # URLError and timeouts are OSErrors
            last = exc
            if attempt + 1 < retries:
                time.sleep(2 + attempt * 4)
    raise ScrapeError(f"Could not open {url}: {last}.")


def fetch_notice(url: str) -> str:
    """One notice page: give up sooner, there are hundreds of them and the next run retries."""
    return fetch(url, retries=2, timeout=25)


# --------------------------------------------------------------------------
# List pages
# --------------------------------------------------------------------------

@dataclass
class Row:
    id: int
    code: str
    title: str
    lots: int
    status: str
    deadline: str  # YYYY-MM-DDTHH:MM


class _Table(HTMLParser):
    """Collects every table row as a list of cell texts plus the links inside it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def _end_cell(self) -> None:
        if self._row is not None and self._cell is not None:
            self._row["cells"].append(clean("".join(self._cell)))
        self._cell = None

    def _end_row(self) -> None:
        self._end_cell()
        if self._row is not None and self._row["cells"]:
            self.rows.append(self._row)
        self._row = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "tr":
            self._end_row()
            self._row = {"cells": [], "links": []}
        elif tag in ("td", "th") and self._row is not None:
            self._end_cell()
            self._cell = []
        elif tag == "a" and self._row is not None:
            href = dict(attrs).get("href")
            if href:
                self._row["links"].append(href)
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("td", "th"):
            self._end_cell()
        elif tag in ("tr", "table"):
            self._end_row()

    def handle_data(self, data):
        if self._cell is not None and not self._skip:
            self._cell.append(data)


def parse_list(html: str) -> list[Row]:
    """Rows of the tender table: id, code, title, lots, status, deadline."""
    parser = _Table()
    parser.feed(html)
    parser.close()
    rows: list[Row] = []
    for raw in parser.rows:
        cells = raw["cells"]
        # the deadline is the last cell that is nothing but a date and time
        d = next((i for i in range(len(cells) - 1, -1, -1) if _DT.fullmatch(cells[i])), None)
        if d is None or d < 4:
            continue
        tid = None
        for href in raw["links"]:
            m = _TID.search(href)
            if m:
                tid = int(m.group(1))
                break
        if tid is None and d >= 5 and cells[d - 5].isdigit():
            tid = int(cells[d - 5])
        if tid is None:
            continue
        lots = cells[d - 2]
        rows.append(Row(
            id=tid,
            code=cells[d - 4],
            title=cells[d - 3],
            lots=int(lots) if lots.isdigit() else 0,
            status=cells[d - 1],
            deadline=norm_dt(cells[d]) or "",
        ))
    return rows


def list_url(page: int, sort: str = "by_end_bid_time") -> str:
    """A page of the register. sort is one of the orderings its column headers link to."""
    first = f"{BASE}/hy/public/tender/{sort}/2/"
    return first if page <= 1 else f"{first}start/{page}"


_SORT = re.compile(r"/public/tender/(by_[a-z_]+)/")


def sort_keys(html: str) -> list[str]:
    """The orderings a list page offers: by_end_bid_time, by_code, ..."""
    return sorted(set(_SORT.findall(html or "")))


def list_links(html: str, limit: int = 8) -> list[str]:
    """The distinct list addresses a page links to (for the log, when an ordering is missing)."""
    found = re.findall(r"""href=["']([^"']*/public/tender/[^"']*)["']""", html or "")
    return sorted({re.sub(r"/start/\d+/?$", "/start/N", link) for link in found})[:limit]


# --------------------------------------------------------------------------
# Notice (detail) pages
# --------------------------------------------------------------------------

LABELS = {
    "code": ["Ծածկագիր", "Code"],
    "title": ["Վերնագիր", "Title"],
    "buyer": ["Գնորդ", "Procurer"],
    "kind": ["Գնման տեսակ", "Procurement Type"],
    "published": ["Հրապարակման ժամանակ", "Publish time"],
    "deadline": ["Հայտերի ընդունման վերջնաժամկետ", "Bid end time"],
    "auction": ["Հակադարձ աճուրդ", "Reverse auction"],
    "questions_until": ["Դուք կարող եք ուղարկել հարցում նախքան", "Deadline to send requests"],
    "status": ["Կարգավիճակ", "Status"],
}
#: Other fixed words on the page that end a value.
STOPS = ["Պատասխաններ և պարզաբանումներ", "Answer and clarification", "Հրավեր", "Invitation",
         "Հայտարարություն", "Statement", "Բեռնել", "Download", "Հարցում", "Request",
         "Ժամանակ", "Logdate", "Պարզաբանում", "Clarification", "Ցուցակ", "List"]
_DATE_FIELDS = {"published", "deadline", "auction", "questions_until"}
_LONG_FIELDS = {"title", "buyer"}


def _key(text: str) -> str:
    return clean(text).strip(" :՝․.").lower()


_LABEL_KEYS = {_key(lbl): name for name, lbls in LABELS.items() for lbl in lbls}
_STOP_KEYS = {_key(s) for s in STOPS}


class _Tokens(HTMLParser):
    """Flattens a page to its visible text chunks and its links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[str] = []
        self.links: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._skip:
            return
        for part in re.split(r"[\r\n]+", data):
            text = clean(part)
            if text:
                self.tokens.append(text)


@dataclass
class Detail:
    fields: dict = field(default_factory=dict)

    def get(self, name: str):
        return self.fields.get(name)


def parse_detail(html: str) -> Detail:
    """Label/value pairs of a notice page, whatever tags they sit in."""
    parser = _Tokens()
    parser.feed(html)
    parser.close()
    tokens = parser.tokens
    out: dict = {}

    def label_of(tok: str):
        """(field, value written after a colon in the same piece of text) or (None, None)."""
        name = _LABEL_KEYS.get(_key(tok))
        if name:
            return name, None
        low = tok.lower()
        for lbl_key, lbl_name in _LABEL_KEYS.items():
            if low.startswith(lbl_key + ":") or low.startswith(lbl_key + " :"):
                return lbl_name, clean(tok[tok.index(":") + 1:])
        return None, None

    i = 0
    while i < len(tokens):
        name, inline = label_of(tokens[i])
        if name is None or name in out:
            i += 1
            continue
        values: list[str] = [inline] if inline else []
        j = i + 1
        # short fields take the next piece of text; titles and names may span several
        while j < len(tokens) and (not values or name in _LONG_FIELDS):
            if label_of(tokens[j])[0] or _key(tokens[j]) in _STOP_KEYS:
                break
            values.append(tokens[j])
            j += 1
            if len(values) >= 8:
                break
        if values:
            text = clean(" ".join(values))
            if name in _DATE_FIELDS:
                text = norm_dt(text)
            if text:
                out[name] = text
        i = max(j, i + 1)

    for href in parser.links:
        url = href if href.startswith("http") else BASE + "/" + href.lstrip("/")
        if "public_invitation" in href and "invitation" not in out:
            out["invitation"] = url
        elif "all_statement" in href and "statement" not in out:
            out["statement"] = url
    return Detail(out)


def detail_url(tid: int) -> str:
    return DETAIL.format(id=tid)
