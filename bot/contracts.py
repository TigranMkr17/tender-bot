"""Reads the contracts register: every contract a state buyer has signed, whatever the procedure.

    python -m bot.contracts --days 45       contracts signed in the last 45 days, in whole months
    python -m bot.contracts --days 400      a year back; months already stored and long closed are skipped

The register is the public page www.armeps.am/ppcm/public/contracts, which loads its rows as JSON. A row has far
more than this keeps: only the contract, its buyer, its supplier and its value are stored, one contract a line, in
bot/state/contracts/<year>-<month>.jsonl. Bank accounts, e-mail addresses and staff names are never stored, and a
sole proprietor's tax number is left out. The site gets them as docs/data/k/<year>-<month>.json.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
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
PUBLIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data", "k")
# What the site is given: the procedures suppliers compete in, and purchases from one supplier when they are large.
FORMS = {"ԷԱՃ": "Էլեկտրոնային աճուրդ", "ԳՀ": "Գնանշման հարցում", "ԲՄ": "Բաց մրցույթ", "ՀԲՄ": "Հրատապ բաց մրցույթ",
         "ԵՄ": "Երկփուլ մրցույթ", "ՄԱ": "Մեկ անձից գնում", "ՀՄԱ": "Հրատապ գնում մեկ անձից"}
ONE_SOURCE = {"ՄԱ", "ՀՄԱ"}
ONE_SOURCE_FROM = 1_000_000
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


def published(r: dict) -> bool:
    form = r.get("f")
    return form in FORMS and (form not in ONE_SOURCE or (r.get("v") or 0) >= ONE_SOURCE_FROM)


def month_page(month: str, rows: list[dict]) -> dict:
    """A month as the site loads it: names once, rows as short lists.
    R: [day, buyer, supplier, value, estimate, form, kind, subject, tender]; the buyer, supplier, form and tender
    are positions in B, S, F and T, and the tender is -1 when the register lists no participants for it."""
    buyers, suppliers, forms, tenders = {}, {}, {}, {}
    B, S, F, T, R = [], [], [], [], []

    def at(table: dict, rowset: list, key, row) -> int:
        if key not in table:
            table[key] = len(rowset)
            rowset.append(row)
        return table[key]

    for r in sorted(rows, key=lambda r: (r.get("d") or "", r.get("n") or "", r["id"])):
        if not published(r) or not r.get("d"):
            continue
        b = at(buyers, B, r.get("bt") or r.get("b"), [r.get("bt") or "", r.get("b") or ""])
        sup = at(suppliers, S, r.get("si") or r.get("sn"), [r.get("si") or "", r.get("sn") or "", r.get("st") or "", 1 if r.get("p") else 0])
        f = at(forms, F, r["f"], r["f"])
        t = at(tenders, T, r.get("tc"), [r.get("tc"), r["ps"]]) if r.get("ps") and r.get("tc") else -1
        value = r.get("v") or 0
        R.append([int(r["d"][8:10]), b, sup, value, round(value + r["sv"]) if r.get("sv") else 0, f, r.get("k") or "",
                  r.get("s") or "", t])
    return {"m": month, "B": B, "S": S, "F": F, "T": T, "R": R}


# ---------- the group's own slice, so its page can open without the whole year ----------
HOME = "docs/my/home.json"
LOOK = {"a": "ա", "h": "հ", "o": "օ", "u": "ս", "p": "ր", "n": "ո", "g": "ց", "q": "զ"}


def norm(text) -> str:
    """Text as the page compares it (the same steps as norm() in docs/my/app.js)."""
    s = str(text or "").lower()
    s = re.sub(r"[a-z](?=[\u0561-\u0587])", lambda m: LOOK.get(m.group(0), m.group(0)), s)
    s = re.sub(r"([\u0561-\u0587])([a-z])", lambda m: m.group(1) + LOOK.get(m.group(2), m.group(2)), s)
    s = s.replace("\u0587", "եվ")
    s = re.sub(r"[^0-9a-z\u0561-\u0586]+", " ", s).strip()
    return " " + s + " "


def unpack_lines(text: str) -> list[list[str]]:
    """The stems of each line, from Name:stem|stem;Name:stem (as unpackLines() in the page)."""
    out = []
    for part in str(text or "").split(";"):
        name, _, keys = part.partition(":")
        ks = [norm(k).strip() for k in (keys if _ else name).split("|")]
        ks = [k for k in ks if k]
        if name.strip() and ks:
            out.append(ks[:12])
    return out[:16]


def home_pack(pages: list[dict], home: dict) -> dict:
    """Every row the group's page uses with its own companies and lines: the group's contracts, contracts in its
    lines, and every contract of a tender any of those belong to or the group entered. Suppliers named among such a
    tender's participants come along without their rows, every buyer comes along for matching open tenders by name,
    and each supplier's totals for the year come along so they read as they would from the whole year."""
    tins = set(str(home.get("c", "")).split("."))
    lines = [k for keys in unpack_lines(home.get("w", "")) for k in keys]
    hit = lambda n: any(all((" " + w) in n for w in key.split(" ")) for key in lines)
    ours = {sid for p in pages for sid, _, tin, _ in p["S"] if tin in tins and sid}
    codes = {code for p in pages for code, parts in p["T"] if ours & set(parts)}
    for p in pages:                                       # tenders that hold a row of ours or of our lines
        for r in p["R"]:
            if r[8] >= 0 and (p["S"][r[2]][2] in tins or hit(norm(r[7]))):
                codes.add(p["T"][r[8]][0])
    named, buyers, totals, spelt = {}, {}, {}, {}
    skey = lambda tin, sid, name, person: tin or (("p:" + sid) if person else "n:" + norm(name))
    for p in pages:                                        # the page keeps the newest spelling of every name
        for sid, name, tin, person in p["S"]:
            if sid:
                named[sid] = [sid, name, tin, person]
            spelt[skey(tin, sid, name, person)] = name
        for tin, name in p["B"]:
            buyers[tin or "n:" + norm(name)] = [tin, name]
        for r in p["R"]:
            sid, name, tin, person = p["S"][r[2]]
            key = tin or (("p:" + sid) if person else "n:" + norm(name))
            t = totals.setdefault(key, [0, 0, set()])
            t[0] += 1
            t[1] += 0 if r[3] > 5e11 else r[3]
            if sid:
                t[2].add(sid)
    months, people = [], set()
    for p in pages:
        keep = [r for r in p["R"] if p["S"][r[2]][2] in tins or hit(norm(r[7])) or (r[8] >= 0 and p["T"][r[8]][0] in codes)]
        B, S, F, T, idx = [], [], [], [], {}

        def at(kind, table, key, row):
            k = (kind, key)
            if k not in idx:
                idx[k] = len(table)
                table.append(row)
            return idx[k]
        R = []
        for r in keep:
            b = at("b", B, r[1], p["B"][r[1]])
            s = at("s", S, r[2], p["S"][r[2]])
            f = at("f", F, r[5], p["F"][r[5]])
            t = at("t", T, r[8], p["T"][r[8]]) if r[8] >= 0 else -1
            if t >= 0:
                people.update(p["T"][r[8]][1])
            R.append([r[0], b, s, r[3], r[4], f, r[6], r[7], t])
        months.append({"m": p["m"], "B": B, "S": S, "F": F, "T": T, "R": R})
    last = {}                                              # one entry per supplier in the slice, with its newest name
    for m in months:
        for sid, name, tin, person in m["S"]:
            last[skey(tin, sid, name, person)] = [sid, name, tin, person]
    for sid in sorted(people):
        if sid in named:
            sid_, name, tin, person = named[sid]
            last.setdefault(skey(tin, sid, name, person), named[sid])
    S_last = [[sid, spelt.get(k, name), tin, person] for k, (sid, name, tin, person) in last.items()]
    extra = {"m": "", "B": sorted(buyers.values()), "S": [named[s] for s in sorted(people) if s in named] + S_last, "F": [], "T": [], "R": []}
    here = {row[0] for m in months + [extra] for row in m["S"]}
    tot = {}
    for n, v, sids in totals.values():
        for sid in sids & here:
            tot[sid] = [n, round(v)]
    return {"home": {"c": home.get("c", ""), "w": home.get("w", "")}, "months": months + [extra], "tot": tot}


def publish(now: datetime | None = None) -> dict:
    """Write every stored month for the site, and a list of them."""
    os.makedirs(PUBLIC, exist_ok=True)
    stored = sorted(f[:-6] for f in os.listdir(STATE) if f.endswith(".jsonl")) if os.path.isdir(STATE) else []
    listed, total, first, last, pages = [], 0, None, None, []
    for month in stored:
        rows = list(load_month(month).values())
        page = month_page(month, rows)
        if not page["R"]:
            continue
        pages.append(page)
        with open(os.path.join(PUBLIC, month + ".json"), "w", encoding="utf-8") as fh:
            json.dump(page, fh, ensure_ascii=False, separators=(",", ":"))
        days = [r["d"] for r in rows if r.get("d") and published(r)]
        first, last = min([first or days[0]] + days), max([last or days[0]] + days)
        listed.append([month, len(page["R"])])
        total += len(page["R"])
    for name in os.listdir(PUBLIC):                        # a month that is no longer stored is no longer offered
        if name.endswith(".json") and name not in ("meta.json", "home.json") and name[:-5] not in {m for m, _ in listed}:
            os.remove(os.path.join(PUBLIC, name))
    stamp = ((now or datetime.now(timezone.utc)) + YEREVAN).strftime("%Y-%m-%dT%H:%M")
    meta = {"updated": stamp, "from": first, "to": last, "contracts": total, "months": listed, "forms": FORMS,
            "source": "armeps.am/ppcm/public/contracts"}
    if os.path.exists(HOME):                               # the group's slice is written before the list that announces it
        with open(HOME, encoding="utf-8") as fh:
            pack = home_pack(pages, json.load(fh))
        pack["updated"] = stamp
        with open(os.path.join(PUBLIC, "home.json"), "w", encoding="utf-8") as fh:
            json.dump(pack, fh, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(PUBLIC, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, separators=(",", ":"))
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=45, help="how far back to read, in whole months")
    ap.add_argument("--again", action="store_true", help="read old months again even if they are stored")
    ap.add_argument("--publish-only", action="store_true", help="write the site's files from what is stored, read nothing")
    args = ap.parse_args(argv)
    code = 0 if args.publish_only else run(args.days, again=args.again)
    meta = publish()
    say(f"Published {meta['contracts']} contracts for the site, {meta['from']} to {meta['to']}.")
    return code


if __name__ == "__main__":
    sys.exit(main())
