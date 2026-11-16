"""Read what a tender's page shows once the auction is over: the lots and every bid."""
from __future__ import annotations

import re
from html.parser import HTMLParser

_ID = re.compile(r"/id/(\d+)")
_CPV = re.compile(r"\b(\d{8})(?:\s*/\s*\d+)?\b")
_PERSON = re.compile(r"(?:^|[\s«\"(])(?:ԱՁ|Ա/Ձ|Ա\\Ձ|Ա\.Ձ\.?|ա/ձ|IE|I/E|I\s*/\s*P|ИП|PE)(?:$|[\s»\").,])"
                     r"|անհատ ձեռն|individual entrepreneur|индивидуальн", re.I)


class _Tables(HTMLParser):
    """Top-level tables as rows of (text, links). What sits in nested tables is left out."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[tuple[str, list[str]]]]] = []
        self.depth = 0
        self._cell: list | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.tables.append([])
        elif self.depth == 1 and tag == "tr":
            self.tables[-1].append([])
            self._cell = None
        elif self.depth == 1 and tag in ("td", "th"):
            if not self.tables[-1]:
                self.tables[-1].append([])
            self._cell = ["", []]
            self.tables[-1][-1].append(self._cell)
        elif self.depth == 1 and tag == "a" and self._cell is not None:
            href = dict(attrs).get("href")
            if href:
                self._cell[1].append(href)

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self._cell = None

    def handle_data(self, data):
        if self.depth == 1 and self._cell is not None:
            self._cell[0] += data


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _money(text: str) -> float | None:
    m = re.search(r"-?\d[\d\s ]*(?:[.,]\d+)?", text or "")
    if not m:
        return None
    try:
        return float(re.sub(r"[\s ]", "", m.group(0)).replace(",", "."))
    except ValueError:
        return None


def is_person(name: str) -> bool:
    """True for a sole proprietor: a named person, not a company."""
    return bool(_PERSON.search(name or ""))


def parse(html: str) -> dict:
    """{'lots': {n: {'cpv', 'title'}}, 'bids': [{'lot','place','cid','name','est','fp','lv','lp','vat','rej'}]}"""
    parser = _Tables()
    parser.feed(html)
    parser.close()
    lots: dict[int, dict] = {}
    bids: list[dict] = []
    for table in parser.tables:
        head = " ".join(_clean(c[0]) for row in table[:2] for c in row).lower()
        if "cpv" in head and ("գնառաջարկ" in head or "bids" in head):
            for row in table:
                cells = [_clean(c[0]) for c in row]
                if len(cells) >= 3 and cells[0].isdigit() and _CPV.search(cells[1]):
                    lots[int(cells[0])] = {"cpv": _CPV.search(cells[1]).group(1), "title": cells[2]}
        elif "զբաղեցրած տեղ" in head or "occupied place" in head:
            for row in table:
                cells = [_clean(c[0]) for c in row]
                if len(cells) < 10 or not cells[0].isdigit() or not cells[1].isdigit():
                    continue
                links = row[2][1]
                cid = next((int(m.group(1)) for href in links for m in [_ID.search(href)] if m), None)
                name = re.sub(r"\s*(Ապրանքի ամբողջական նկարագիր\w*|Product full description)\s*$", "", cells[2]).strip()
                status = cells[10].lower() if len(cells) > 10 else ""
                bids.append({"lot": int(cells[0]), "place": int(cells[1]), "cid": cid, "name": name,
                             "est": _money(cells[3]), "fp": _money(cells[6]), "lv": _money(cells[7]),
                             "lp": _money(cells[9]), "vat": _money(cells[8]),
                             "rej": 1 if ("մերժ" in status or "reject" in status) else 0})
    return {"lots": lots, "bids": bids}
