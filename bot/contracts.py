"""Reads the contracts register: every contract a state buyer has signed, whatever the procedure.

    python -m bot.contracts --days 45       contracts signed in the last 45 days, in whole months
    python -m bot.contracts --days 400      a year back; months already stored and long closed are skipped

The register is the public page www.armeps.am/ppcm/public/contracts, which loads its rows as JSON. A row has far
more than this keeps: only the contract, its buyer, its supplier and its value are stored, one contract a line, in
bot/state/contracts/<year>-<month>.jsonl. Bank accounts, e-mail addresses and staff names are never stored, and a
sole proprietor's tax number is left out.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

from . import armeps, results, textproc

BASE = "https://www.armeps.am/ppcm/public/contracts/"
PAGE = 500
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "contracts")
KINDS = {"GOODS": "g", "SERVICES": "s", "WORKS": "w"}
YEREVAN = timedelta(hours=4)


def say(text: str) -> None:
    print(text, flush=True)


def post(path: str, body: dict, retries: int = 4, timeout: int = 90):
    """One question to the register. Returns the answer's data."""
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode("utf-8"), headers={
        "User-Agent": armeps.USER_AGENT, "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*"})
    last: Exception | None = None
    for attempt in range(retries):
        if attempt:
            time.sleep(4 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                answer = json.loads(r.read().decode("utf-8"))
            if answer.get("status") != 0:
                raise ValueError(f"the register answered status {answer.get('status')}")
            return answer["data"]
        except (OSError, ValueError) as e:                 # URLError, timeouts and broken answers
            last = e
    raise RuntimeError(f"{path}: {last}")


def day(ms) -> str | None:
    """The register stamps a date as midnight in Yerevan."""
    if not ms:
        return None
    return (datetime.fromtimestamp(ms / 1000, timezone.utc) + YEREVAN).strftime("%Y-%m-%d")


def short(uid: str | None) -> str:
    return (uid or "").replace("-", "")[:10]


def slim(c: dict) -> dict:
    """What is kept of a contract. Short keys, because there are tens of thousands a year."""
    name = textproc.company_name(c.get("supplierName") or "")
    person = results.is_person(name)
    total, latest = c.get("contractValueTotal") or c.get("contractValue"), c.get("latestValue")
    subject = " ".join((c.get("procurementSubject") or "").split())
    out = {
        "id": c["id"], "n": c.get("number"), "d": day(c.get("dateSigned")), "v": total,
        "lv": latest if latest and latest != total else None,
        "s": subject[:300] + ("…" if len(subject) > 300 else ""),
        "tc": c.get("tenderCode"), "f": c.get("formAbbrHy"), "k": KINDS.get(c.get("tenderProcurementType") or ""),
        "b": " ".join((c.get("authorityNameHy") or "").split()), "bt": c.get("authorityTin"),
        "sn": name, "st": None if person else c.get("supplierTaxpayerId"), "p": 1 if person else None,
        "si": short(c.get("supplierId")),
        "ps": [short(x) for x in (c.get("tenderSupplierList") or "").split("|") if x] or None,
        "sv": c.get("contractSaving") or None, "end": day(c.get("deadline")),
        "x": None if c.get("state") == "ACTIVE" else c.get("state"),
    }
    return {k: v for k, v in out.items() if v not in (None, "")}


def question(first: date, last: date) -> dict:
    """Contracts signed from `first` to `last`, both days included."""
    return {"periods": [], "contracts": [], "authorities": [], "suppliers": [], "forms": [],
            "totalValue": {"min": None, "max": None}, "latestValue": {"min": None, "max": None},
            "dateSigned": {"min": f"{first}T00:00:00", "max": f"{last}T23:59:59"},     # Yerevan time, as the register reads it
            "dateSubmitted": {"min": None, "max": None}, "number": None, "procurementSubject": None,
            "procurementSubjectCode": None, "procurementSubjectObj": None, "year": None}


def read_day(d: date, ask=post, pause: float = 0.2) -> dict[str, dict]:
    """Every contract signed on one day. A day nearly always fits one page. When it does not, the pages are read in
    both directions, because the register's order can shift between two pages, and the count is checked."""
    f, rows, index = question(d, d), {}, 0
    while True:
        page = ask("list", {"filter": f, "order": {"field": "date_signed", "ascending": True},
                            "page": {"index": index, "size": PAGE}})
        for c in page:
            rows[c["id"]] = slim(c)
        if pause:
            time.sleep(pause)
        if len(page) < PAGE:
            break
        index += 1
    if index:
        count = ask("count", {"filter": f})
        back = 0
        while len(rows) < count and back <= index:
            for c in ask("list", {"filter": f, "order": {"field": "date_signed", "ascending": False},
                                  "page": {"index": back, "size": PAGE}}):
                rows[c["id"]] = slim(c)
            back += 1
        if len(rows) != count:
            say(f"{d}: the register counts {count} contracts and handed out {len(rows)}.")
    return rows


def read_days(first: date, last: date, ask=post, pause: float = 0.2) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    d = first
    while d <= last:
        rows.update(read_day(d, ask, pause))
        d += timedelta(days=1)
    return rows


def month_file(month: str) -> str:
    return os.path.join(STATE, month + ".jsonl")


def load_month(month: str) -> dict[str, dict]:
    try:
        with open(month_file(month), encoding="utf-8") as fh:
            return {r["id"]: r for r in map(json.loads, filter(None, map(str.strip, fh)))}
    except FileNotFoundError:
        return {}


def save_month(month: str, rows: dict[str, dict]) -> None:
    os.makedirs(STATE, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r.get("d") or "", r.get("n") or "", r["id"]))
    with open(month_file(month), "w", encoding="utf-8") as fh:
        for r in ordered:
            fh.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


def months(first: date, last: date) -> list[tuple[date, date]]:
    """Whole calendar months from the one that holds `first` to the one that holds `last`."""
    out, d = [], first.replace(day=1)
    while d <= last:
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append((d, nxt - timedelta(days=1)))
        d = nxt
    return out


def run(days: int, today: date | None = None, ask=post, pause: float = 0.2, again: bool = False) -> int:
    """Newest month first. A month that ended more than 45 days ago and is already stored is not read again,
    unless `again`: late entries and corrections arrive within weeks, not later."""
    today = today or (datetime.now(timezone.utc) + YEREVAN).date()
    total = 0
    for first, last in reversed(months(today - timedelta(days=days), today)):
        month = first.strftime("%Y-%m")
        was = load_month(month)
        if was and not again and last < today - timedelta(days=45):
            say(f"{month}: {len(was)} contracts, stored already")
            continue
        try:
            rows = read_days(first, min(last, today), ask, pause)
        except RuntimeError as e:
            say(f"{month}: could not be read ({e}); what was stored stays.")
            continue
        if len(rows) < len(was) // 2:
            say(f"{month}: only {len(rows)} contracts came where {len(was)} were stored; what was stored stays.")
            continue
        save_month(month, rows)
        total += len(rows)
        say(f"{month}: {len(rows)} contracts" + (f" ({len(rows) - len(was):+d})" if was else ""))
    say(f"Read {total} contracts.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=45, help="how far back to read, in whole months")
    ap.add_argument("--again", action="store_true", help="read old months again even if they are stored")
    args = ap.parse_args(argv)
    return run(args.days, again=args.again)


if __name__ == "__main__":
    sys.exit(main())
