"""The slow work, kept apart from the hourly run.

  python -m bot.deep --minutes 30

1. Open tenders: read each invitation archive once and publish what is inside it
   (lots, quantities, what a bid has to carry) as docs/data/t/<id>.json.
2. Finished tenders: read the lots and every bid from the tender's page, newest first and
   then back through the past year, and publish them as small files under docs/data/h/.

Everything here writes its own files (bot/state/lots.json, bot/state/history.json,
bot/state/results/*, docs/data/lots.json, docs/data/t/*, docs/data/h/*), so it can run next
to the hourly job without the two overwriting each other.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import armeps, invite, results, store
from . import textproc as tp

LOTS_STATE = os.path.join("bot", "state", "lots.json")
HIST_STATE = os.path.join("bot", "state", "history.json")
RESULTS_DIR = os.path.join("bot", "state", "results")
OUT_T = os.path.join("docs", "data", "t")
OUT_H = os.path.join("docs", "data", "h")
OUT_LOTS = os.path.join("docs", "data", "lots.json")

WORKERS = 2
PAUSE = 0.6                # seconds each worker rests after a request
INVITE_TRIES = 3
HISTORY_DAYS = 400         # how far back finished tenders are read
RETRY_HOURS = 20           # a page that was not final yet is looked at again after this long
RECHECK_HOURS = 48         # while the winner is being chosen a bid can still be turned down: look again
RECHECK_DAYS = 120         # ...but not for ever
KEEP_LOTS_DAYS = 75        # how long a closed tender's lot list is kept while its result is awaited
GIVE_UP_AFTER = 12
RECENT = 400
CHUNK = 50                 # finished tenders per docs/data/h/r/<n>.json
PERSON_LABEL = "անհատ ձեռնարկատեր"
READER = 2                 # raise it when invite.py learns something: every open invitation is read again
RULES = 2                  # raise it when "is this page a result yet?" changes: waiting pages are read again
CLOSED = (("չեղարկ", "c"), ("cancel", "c"), ("չկայաց", "f"), ("failed", "f"), ("ավարտ", ""), ("finish", ""))
AWARDING = ("շնորհ", "award")
REPLACED = ("փոփոխ", "modified", "changed")     # the notice was amended: it lives on under a new number


def say(text: str) -> None:
    print(text, flush=True)


def _load(path: str, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path: str, obj) -> bool:
    """Write JSON only when it changed. True when the file was written."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.read() == text:
                return False
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return True


class Clock:
    def __init__(self, minutes: float, now=time.monotonic) -> None:
        self.now, self.start, self.total = now, now(), minutes * 60

    def left(self) -> float:
        return self.total - (self.now() - self.start)

    def used_share(self) -> float:
        return (self.now() - self.start) / self.total if self.total else 1.0


def _each(items, work, clock: Clock, until_share: float = 1.0):
    """Run work(item) on two threads, yielding (item, result, error) in order. Stops asking
    when time is up or when the register stops answering."""
    stop = threading.Event()
    lock = threading.Lock()
    failing = [0]

    def one(item):
        if stop.is_set() or clock.left() <= 0 or clock.used_share() >= until_share:
            return None, "later"
        try:
            out, err = work(item), ""
        except armeps.Missing:
            out, err = None, "missing"
        except armeps.ScrapeError as exc:
            out, err = None, str(exc)
        with lock:
            failing[0] = failing[0] + 1 if err and err != "missing" else 0
            if failing[0] >= GIVE_UP_AFTER:
                stop.set()
        time.sleep(PAUSE)
        return out, err

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for item, (out, err) in zip(items, pool.map(one, items)):
            yield item, out, err
    if stop.is_set():
        say("! The register stopped answering: the rest is left for the next run.")


# --------------------------------------------------------------------------
# 1. invitations of open tenders
# --------------------------------------------------------------------------

def lot_names(lots: list[dict], limit: int = 320) -> str:
    """The distinct lot names in one short string, for the site's search."""
    seen, out, size = set(), [], 0
    for lot in lots:
        name = (lot.get("name") or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        if size + len(name) > limit:
            break
        out.append(name)
        size += len(name) + 2
    return "; ".join(out)


def read_invitations(tenders: list[dict], state: dict, at: datetime, clock: Clock,
                     fetch_bytes=armeps.fetch_bytes, until_share: float = 1.0) -> dict:
    known = state.setdefault("t", {})
    for entry in known.values():                           # read by an older reader: once more
        if entry.get("ok") and entry["ok"] != READER and entry.get("v") != READER:
            entry["v"], entry["dt"] = READER, 0
    todo = [t for t in tenders if store.is_open(t, at)
            and known.get(str(t["id"]), {}).get("ok") != READER
            and known.get(str(t["id"]), {}).get("dt", 0) < INVITE_TRIES]
    todo.sort(key=lambda t: -t["id"])
    stats = {"read": 0, "failed": 0, "later": 0, "no_lots": 0}

    def work(t):
        return invite.read(fetch_bytes(armeps.INVITATION.format(id=t["id"])))

    for t, info, err in _each(todo, work, clock, until_share):
        key = str(t["id"])
        if err == "later":
            stats["later"] += 1
            continue
        entry = known.setdefault(key, {})
        entry["dt"] = entry.get("dt", 0) + 1
        if err or info is None:
            stats["failed"] += 1
            if err and err != "missing":
                say(f"! invitation {t['id']}: {err}")
            continue
        lots = info["lots"]
        if not lots:
            stats["no_lots"] += 1
        entry.update(ok=READER, n=len(lots), ln=lot_names(lots), cpv=sorted({lot["cpv"] for lot in lots})[:12],
                     e=(t.get("end") or "")[:10], L=brief(lots))
        page = {"id": t["id"], "lots": lots, "sec": info["sec"], "ask": info["ask"], "files": info["files"]}
        for field in ("addr", "when"):                      # the same for every lot: say it once
            values = {lot.get(field) for lot in lots}
            if len(lots) > 1 and len(values) == 1 and None not in values:
                page[field] = values.pop()
                for lot in lots:
                    del lot[field]
        _write(os.path.join(OUT_T, f"{key}.json"), page)
        stats["read"] += 1

    alive = {str(t["id"]) for t in tenders}                 # tenders the hourly job dropped leave the site;
    for key in [k for k in known if k not in alive]:        # their lot lists stay until the result is read
        try:
            os.remove(os.path.join(OUT_T, f"{key}.json"))
        except FileNotFoundError:
            pass
    _write(OUT_LOTS, {"t": {k: {"n": v.get("n", 0), "ln": v.get("ln", ""), "cpv": v.get("cpv", [])}
                            for k, v in sorted(known.items()) if v.get("ok") and k in alive}})
    return stats


def brief(lots: list[dict]) -> list[list]:
    """A lot list as it is kept for later: number, item code, name, unit, quantity."""
    return [[lot["n"], lot.get("cpv") or "", lot.get("name") or "", lot.get("unit") or "", lot.get("qty")]
            for lot in lots]


def prune_lots(state: dict, tenders: list[dict], hist: dict, at: datetime) -> None:
    """Forget the lot lists of tenders that are gone from the site and whose result is in, or long overdue."""
    known = state.get("t", {})
    alive = {str(t["id"]) for t in tenders}
    done = {str(i) for i in hist.get("done", [])}
    limit = store.stamp(at - timedelta(days=KEEP_LOTS_DAYS))[:10]
    for key in [k for k in known if k not in alive]:
        if key in done or (known[key].get("e") or "9999") < limit:
            del known[key]


# --------------------------------------------------------------------------
# 2. finished tenders
# --------------------------------------------------------------------------

def _month_path(month: str) -> str:
    return os.path.join(RESULTS_DIR, f"{month}.json")


def load_results() -> dict[int, dict]:
    out: dict[int, dict] = {}
    if os.path.isdir(RESULTS_DIR):
        for name in sorted(os.listdir(RESULTS_DIR)):
            if name.endswith(".json"):
                for rec in _load(os.path.join(RESULTS_DIR, name), {}).get("r", []):
                    out[rec["id"]] = rec
    return out


def save_results(records: dict[int, dict]) -> None:
    months: dict[str, list] = {}
    for rec in records.values():
        months.setdefault((rec.get("end") or "0000-00")[:7], []).append(rec)
    for month, recs in months.items():
        _write(_month_path(month), {"r": sorted(recs, key=lambda r: r["id"])})


def stage(status: str | None) -> str:
    """'early' while bids are not on the page yet, 'award' while the winner is being chosen,
    otherwise how it closed: '' finished, 'f' failed, 'c' cancelled."""
    low = (status or "").lower()
    for word, code in CLOSED:
        if word in low:
            return code
    return "award" if any(word in low for word in AWARDING) else "early"


def is_final(status: str | None) -> bool:
    return stage(status) != "early"


def nameless(rec: dict) -> bool:
    """True when a lot that drew bids is listed without its name or item code."""
    return any(lot[4] and not (lot[1] and lot[2]) for lot in rec["lots"])


def shown_stage(rec: dict) -> str:
    """The stage as the site treats it. Between the auction and the award the register uses several
    names ("evaluation of the application" is one); once bids are on the page it is a result."""
    how = stage(rec.get("st"))
    if how == "early" and any(lot[4] for lot in rec["lots"]):
        return "award"
    return how


def name_lots(rec: dict, info: list[list] | None) -> dict:
    """Fill in what the result page leaves out. A lot that had one bidder is listed there without
    its name and item code; the invitation has both, and the quantity."""
    by_n = {row[0]: row for row in info or []}
    for lot in rec["lots"]:
        row = by_n.get(lot[0])
        if not row:
            continue
        lot[1] = lot[1] or row[1]
        lot[2] = lot[2] or row[2]
        del lot[5:]
        lot.extend([row[4], row[3]])                       # quantity, unit
    return rec


def record_from(tid: int, html: str) -> dict | None:
    """One finished tender as it is stored. None when the page is not a tender's page."""
    d = armeps.parse_detail(html)
    if not d.get("code") and not d.get("title"):
        return None
    res = results.parse(html)
    by_lot: dict[int, list] = {}
    est: dict[int, float] = {}
    names: dict[int, str] = {}
    for b in res["bids"]:
        if b["cid"] is None:
            continue
        names[b["cid"]] = b["name"]
        if b["est"] is not None:
            est[b["lot"]] = b["est"]
        by_lot.setdefault(b["lot"], []).append([b["cid"], b["place"], b["lv"], b["lp"], b["fp"], b["rej"]])
    lots = []
    for n in sorted(set(res["lots"]) | set(by_lot)):
        meta = res["lots"].get(n, {})
        lots.append([n, meta.get("cpv", ""), meta.get("title", ""), est.get(n),
                     sorted(by_lot.get(n, []), key=lambda b: b[1])])
    return {"id": tid, "code": d.get("code") or "", "title": d.get("title") or "",
            "buyer": d.get("buyer") or "", "kind": tp.kind_key(d.get("kind")),
            "pub": d.get("published"), "end": d.get("deadline"), "auc": d.get("auction"),
            "st": d.get("status") or "", "lots": lots, "names": names}


def read_results(tenders: list[dict], hist: dict, records: dict[int, dict], at: datetime, clock: Clock,
                 fetch_page=armeps.fetch_page, lots_state: dict | None = None,
                 fetch_bytes=armeps.fetch_bytes) -> dict:
    """Newest finished tenders first, then back through the past year."""
    done = set(hist.get("done", []))
    retry = {int(k): v for k, v in hist.get("retry", {}).items()}
    recheck = {int(k): v for k, v in hist.get("recheck", {}).items()}
    kept_lots = (lots_state or {}).get("t", {})
    early: dict[str, int] = {}
    if hist.get("rules") != RULES:                         # what counts as a result has changed:
        retry.clear()                                      # pages set aside under the old rules are looked at now
        hist["rules"] = RULES
    companies = hist.setdefault("companies", {})
    state_ids = {t["id"]: t for t in tenders}
    open_ids = {t["id"] for t in tenders if store.is_open(t, at)}
    top = max(state_ids) if state_ids else hist.get("top", 0)
    hist["top"] = max(top, hist.get("top", 0))
    floor = hist.get("floor", 0)
    stamp_now = at.timestamp()
    cutoff = store.stamp(at - timedelta(days=HISTORY_DAYS))

    def waiting(tid: int) -> bool:
        return stamp_now - retry.get(tid, 0) < RETRY_HOURS * 3600

    just_closed = {tid for tid, t in state_ids.items()       # the auction is held the next day
                   if tid not in open_ids and (store.parse(t.get("end")) or at) >= at - timedelta(hours=20)}
    award_limit = store.stamp(at - timedelta(days=RECHECK_DAYS))
    for tid, rec in records.items():                       # kept from before these were looked after:
        if tid in done and tid not in recheck and (        # still being awarded, or a lot without a name
                (shown_stage(rec) == "award" and (rec.get("end") or "") > award_limit)
                or (nameless(rec) and rec.get("z", 0) < 3)):
            done.discard(tid)
            recheck[tid] = 0
    again = {tid for tid, seen in recheck.items() if stamp_now - seen >= RECHECK_HOURS * 3600}
    fresh = sorted({tid for tid in state_ids
                    if tid not in done and tid not in recheck and tid not in open_ids
                    and tid not in just_closed and not waiting(tid)} | again, reverse=True)
    stats = {"new": 0, "again": 0, "not_final": 0, "replaced": 0, "missing": 0, "failed": 0, "later": 0}

    def work(tid):
        rec = record_from(tid, fetch_page(armeps.detail_url(tid)))
        if rec is None or shown_stage(rec) == "early" or not rec["lots"]:
            return rec
        info = (kept_lots.get(str(tid)) or {}).get("L")
        tries = (records.get(tid) or {}).get("z", 0)
        if info is None and nameless(rec) and tries < 3:
            try:                                            # a lot with bids and no name: ask the invitation
                got = invite.read(fetch_bytes(armeps.INVITATION.format(id=tid)))
                info = brief(got["lots"]) if got and got["lots"] else None
                tries = tries if info else 9                # an archive that cannot be read is not asked for again
            except armeps.Missing:
                tries = 9
            except armeps.ScrapeError:
                tries += 1                                  # the register did not answer: a few more tries later
        if tries:
            rec["z"] = tries
        return name_lots(rec, info)

    def take(tid, rec, err) -> str | None:
        """Store one answer. Returns the record's deadline when it is a finished tender."""
        if err == "later":
            stats["later"] += 1
            return None
        if err == "missing" or (not err and rec is None):
            stats["missing"] += 1
            done.add(tid)
            return None
        if err:
            stats["failed"] += 1
            say(f"! tender {tid}: {err}")
            return None
        how = shown_stage(rec)
        if how == "early":
            if any(word in rec["st"].lower() for word in REPLACED):
                stats["replaced"] += 1                      # nothing more will ever happen under this number
                done.add(tid)
                return None
            stats["not_final"] += 1
            retry[tid] = stamp_now
            early[rec["st"]] = early.get(rec["st"], 0) + 1
            return None
        for cid, name in rec.pop("names").items():
            companies[str(cid)] = name
        stats["again" if tid in records else "new"] += 1
        records[tid] = rec
        retry.pop(tid, None)
        if (how == "award" and (rec.get("end") or "") > award_limit) or (nameless(rec) and rec.get("z", 0) < 3):
            recheck[tid] = stamp_now                        # shown now, read again: until the winner is named,
            done.discard(tid)                               # or until the invitation has given the lots their names
        else:
            recheck.pop(tid, None)
            done.add(tid)
        return rec.get("end")

    for tid, rec, err in _each(fresh, work, clock):
        take(tid, rec, err)

    # then backwards from the newest number that is neither open nor read
    cursor = hist["top"]
    while clock.left() > 20 and cursor > max(floor, 1):
        batch = []
        while cursor > max(floor, 1) and len(batch) < 40:
            if cursor not in done and cursor not in recheck and cursor not in open_ids \
                    and cursor not in just_closed and not waiting(cursor):
                batch.append(cursor)
            cursor -= 1
        if not batch:
            continue
        old, failed_before = 0, stats["failed"]
        for tid, rec, err in _each(batch, work, clock):
            end = take(tid, rec, err)
            if end and end < cutoff:
                old += 1
        if stats["failed"] - failed_before >= GIVE_UP_AFTER:
            break                                          # the register is not answering
        if old >= 25:                                      # a whole batch older than the window: stop here
            hist["floor"] = batch[-1]
            say(f"History reaches back {HISTORY_DAYS} days: complete down to number {batch[-1]}.")
            break

    hist["done"] = sorted(done)
    hist["retry"] = {str(k): v for k, v in retry.items() if stamp_now - v < 7 * 86400}
    hist["recheck"] = {str(k): v for k, v in recheck.items()}
    if early:
        say("Not decided yet: " + ", ".join(f"{name or '?'} {n}" for name, n in sorted(early.items(), key=lambda kv: -kv[1])))
    return stats


# --------------------------------------------------------------------------
# what the site reads
# --------------------------------------------------------------------------

def _leader(bids: list) -> list | None:
    """The best-placed bid that was not rejected."""
    ok = [b for b in bids if not b[5]]
    return min(ok, key=lambda b: b[1]) if ok else None


def publish_history(records: dict[int, dict], companies: dict, at: datetime, complete: bool = False) -> dict:
    casing = tp.Casing().learn([r.get("title") for r in records.values()]
                               + [r.get("buyer") for r in records.values()]
                               + list(companies.values()))
    cname: dict[int, str] = {}
    person: dict[int, bool] = {}
    for key, raw in companies.items():
        cid = int(key)
        cname[cid] = tp.company_name(raw)
        person[cid] = results.is_person(raw)

    def shown(cid) -> str:
        """A bidder's name outside its own tender: sole proprietors are not named."""
        if cid is None:
            return ""
        return PERSON_LABEL if person.get(cid) else cname.get(cid, "")

    chunks: dict[int, dict] = {}
    by_buyer: dict[str, dict] = {}
    by_cpv: dict[str, list] = {}
    by_company: dict[int, list] = {}
    tally: dict[int, list] = {}
    recent = []

    for rec in sorted(records.values(), key=lambda r: (r.get("auc") or r.get("end") or "", r["id"]), reverse=True):
        readable = casing.fix(tp.clean_chars(rec["title"]), "title")
        subject, _ = tp.split_title(readable, rec["code"])
        buyer = casing.fix(tp.clean_name(rec["buyer"]), "name")
        bkey = tp.buyer_key(rec["buyer"])
        kind = rec.get("kind") or tp.kind_from_code(rec["code"])
        sector = tp.classify(subject or readable, kind)
        date = (rec.get("auc") or rec.get("end") or "")[:10]
        est_sum = low_sum = 0.0
        bidders: set[int] = set()
        leaders: dict[int, int] = {}
        lots_out = []
        for n, cpv, title, est, bids, *more in rec["lots"]:
            amount, unit = (more + [None, None])[:2]
            if not amount or not unit or unit == "դրամ":     # "1 դրամ" is how services are written: no quantity
                amount = unit = None
            lead = _leader(bids)
            for b in bids:
                bidders.add(b[0])
            if lead and est:
                est_sum += est
                low_sum += lead[3] or 0
                leaders[lead[0]] = leaders.get(lead[0], 0) + 1
            lots_out.append({"n": n, "cpv": cpv, "t": title, "est": est,
                             **({"q": amount, "u": unit} if amount else {}),
                             "bids": [{"c": b[0], "nm": cname.get(b[0], ""), "p": b[1], "lv": b[2], "lp": b[3],
                                       "fp": b[4], "rej": b[5], **({"per": 1} if person.get(b[0]) else {})}
                                      for b in bids]})
            ok = [b for b in bids if not b[5]]
            row = [cpv, title, rec["id"], bkey, buyer, date, est, lead[3] if lead else None, len(ok),
                   [[b[0], cname.get(b[0], ""), rank] for rank, b in enumerate(ok[:4], 1) if not person.get(b[0])],
                   amount, unit]
            if cpv:
                by_cpv.setdefault(cpv[:5], []).append(row)
            by_buyer.setdefault(bkey, {"name": buyer, "rows": [], "lots": []})["lots"].append(
                [cpv, title, rec["id"], date, est, lead[3] if lead else None, len(ok),
                 shown(lead[0]) if lead else "", lead[0] if lead and not person.get(lead[0]) else None,
                 amount, unit])
            for b in bids:
                if person.get(b[0]):
                    continue                                # sole proprietors get no page of their own
                by_company.setdefault(b[0], []).append(
                    [rec["id"], n, cpv, title, buyer, date, b[1], b[3], est, b[5], bkey,
                     1 if lead and lead[0] == b[0] else 0])
                t = tally.setdefault(b[0], [0, 0])
                t[0] += 1
                if lead and lead[0] == b[0]:
                    t[1] += 1
        top = max(leaders, key=leaders.get) if leaders else None
        summary = [rec["id"], subject or "", buyer, bkey, date, sector, len(rec["lots"]), len(bidders),
                   round(est_sum) or None, round(low_sum) or None,
                   shown(top), 0 if rec["lots"] and bidders else 1, {"award": "a", "early": "a"}.get(stage(rec.get("st")), stage(rec.get("st")))]
        by_buyer.setdefault(bkey, {"name": buyer, "rows": [], "lots": []})["rows"].append(summary)
        if len(recent) < RECENT:
            recent.append(summary)
        chunks.setdefault(rec["id"] // CHUNK, {})[str(rec["id"])] = {
            "id": rec["id"], "code": rec["code"], "subject": subject, "title": tp.clean_chars(rec["title"]),
            "buyer": buyer, "bk": bkey, "kind": kind, "sector": sector, "pub": rec.get("pub"),
            "end": rec.get("end"), "auc": rec.get("auc"), "st": rec.get("st"), "lots": lots_out}

    wanted: set[str] = set()

    def put(rel: str, obj) -> None:
        wanted.add(rel)
        _write(os.path.join(OUT_H, rel), obj)

    for n, body in chunks.items():
        put(f"r/{n}.json", body)
    for bkey, body in by_buyer.items():
        if bkey:
            body["rows"] = body["rows"][:200]
            body["lots"] = body["lots"][:1500]
            put(f"b/{bkey}.json", body)
    for prefix, rows in by_cpv.items():
        put(f"v/{prefix}.json", {"rows": rows[:2500]})
    shards: dict[int, dict] = {}
    for cid, rows in by_company.items():
        shards.setdefault(cid % 40, {})[str(cid)] = {"name": cname.get(cid, ""), "rows": rows[:200]}
    for n, body in shards.items():
        put(f"c/{n}.json", body)
    put("companies.json", {str(cid): [cname.get(cid, ""), t[0], t[1]]
                           for cid, t in sorted(tally.items(), key=lambda kv: -kv[1][0])})
    put("recent.json", {"rows": recent})
    dates = [r[4] for r in recent if r[4]]
    all_dates = sorted((rec.get("auc") or rec.get("end") or "")[:10] for rec in records.values())
    put("meta.json", {"updated": store.stamp(at), "results": len(records), "companies": len(tally),
                      "from": next((d for d in all_dates if d), None), "to": dates[0] if dates else None,
                      "complete": bool(complete)})

    removed = 0                                             # files nothing points to any more
    for folder, _, files in os.walk(OUT_H):
        for name in files:
            rel = os.path.relpath(os.path.join(folder, name), OUT_H).replace(os.sep, "/")
            if rel not in wanted:
                os.remove(os.path.join(folder, name))
                removed += 1
    return {"files": len(wanted), "removed": removed}


# --------------------------------------------------------------------------

def run(minutes: float, at: datetime | None = None, fetch_bytes=armeps.fetch_bytes,
        fetch_page=armeps.fetch_page, now=time.monotonic) -> int:
    at = at or store.now()
    clock = Clock(minutes, now)
    tenders = store.load()["tenders"]
    lots_state = _load(LOTS_STATE, {})
    hist = _load(HIST_STATE, {})
    records = load_results()

    backlog = any(lots_state.get("t", {}).get(str(t["id"]), {}).get("ok") != READER
                  for t in tenders if store.is_open(t, at))
    inv = read_invitations(tenders, lots_state, at, clock, fetch_bytes, until_share=0.6 if backlog else 1.0)
    _write(LOTS_STATE, lots_state)
    say(f"Invitations: {inv['read']} read" + (f", {inv['failed']} failed" if inv["failed"] else "")
        + (f", {inv['later']} left for later" if inv["later"] else ""))

    res = read_results(tenders, hist, records, at, clock, fetch_page, lots_state, fetch_bytes)
    save_results(records)
    _write(HIST_STATE, hist)
    prune_lots(lots_state, tenders, hist, at)
    _write(LOTS_STATE, lots_state)
    say(f"Results: {res['new']} finished tenders read" + (f", {res['again']} read again" if res["again"] else "")
        + f", {res['not_final']} not decided yet"
        + (f", {res['failed']} failed" if res["failed"] else "") + f"; {len(records)} kept in all")

    out = publish_history(records, hist.get("companies", {}), at, complete=bool(hist.get("floor")))
    say(f"Published {out['files']} history files" + (f", removed {out['removed']}" if out["removed"] else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--minutes", type=float, default=20, help="how long this run may read the register")
    args = ap.parse_args(argv)
    return run(args.minutes)


if __name__ == "__main__":
    sys.exit(main())
