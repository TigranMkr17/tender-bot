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
GIVE_UP_AFTER = 12
RECENT = 400
CHUNK = 50                 # finished tenders per docs/data/h/r/<n>.json
PERSON_LABEL = "անհատ ձեռնարկատեր"
FINAL = ("ավարտված", "շնորհում", "չկայացած", "չեղարկված", "finished", "award", "failed", "cancel")


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
    todo = [t for t in tenders if store.is_open(t, at)
            and not known.get(str(t["id"]), {}).get("ok")
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
        entry.update(ok=1, n=len(lots), ln=lot_names(lots), cpv=sorted({lot["cpv"] for lot in lots})[:12])
        page = {"id": t["id"], "lots": lots, "sec": info["sec"], "ask": info["ask"], "files": info["files"]}
        for field in ("addr", "when"):                      # the same for every lot: say it once
            values = {lot.get(field) for lot in lots}
            if len(lots) > 1 and len(values) == 1 and None not in values:
                page[field] = values.pop()
                for lot in lots:
                    del lot[field]
        _write(os.path.join(OUT_T, f"{key}.json"), page)
        stats["read"] += 1

    alive = {str(t["id"]) for t in tenders}                 # forget tenders the hourly job dropped
    for key in [k for k in known if k not in alive]:
        del known[key]
        try:
            os.remove(os.path.join(OUT_T, f"{key}.json"))
        except FileNotFoundError:
            pass
    _write(OUT_LOTS, {"t": {k: {"n": v.get("n", 0), "ln": v.get("ln", ""), "cpv": v.get("cpv", [])}
                            for k, v in sorted(known.items()) if v.get("ok")}})
    return stats


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


def is_final(status: str | None) -> bool:
    low = (status or "").lower()
    return any(word in low for word in FINAL)


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
                 fetch_page=armeps.fetch_page) -> dict:
    """Newest finished tenders first, then back through the past year."""
    done = set(hist.get("done", []))
    retry = {int(k): v for k, v in hist.get("retry", {}).items()}
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
    fresh = sorted((tid for tid in state_ids
                    if tid not in done and tid not in open_ids and tid not in just_closed
                    and not waiting(tid)), reverse=True)
    stats = {"new": 0, "not_final": 0, "missing": 0, "failed": 0, "later": 0}

    def work(tid):
        return record_from(tid, fetch_page(armeps.detail_url(tid)))

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
        if not is_final(rec["st"]):
            stats["not_final"] += 1
            retry[tid] = stamp_now
            return None
        for cid, name in rec.pop("names").items():
            companies[str(cid)] = name
        records[tid] = rec
        done.add(tid)
        retry.pop(tid, None)
        stats["new"] += 1
        return rec.get("end")

    for tid, rec, err in _each(fresh, work, clock):
        take(tid, rec, err)

    # then backwards from the newest number that is neither open nor read
    cursor = hist["top"]
    while clock.left() > 20 and cursor > max(floor, 1):
        batch = []
        while cursor > max(floor, 1) and len(batch) < 40:
            if cursor not in done and cursor not in open_ids and cursor not in just_closed \
                    and not waiting(cursor):
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
    return stats


# --------------------------------------------------------------------------
# what the site reads
# --------------------------------------------------------------------------

def _leader(bids: list) -> list | None:
    """The best-placed bid that was not rejected."""
    ok = [b for b in bids if not b[5]]
    return min(ok, key=lambda b: b[1]) if ok else None


def publish_history(records: dict[int, dict], companies: dict, at: datetime) -> dict:
    casing = tp.Casing().learn([r.get("title") for r in records.values()]
                               + [r.get("buyer") for r in records.values()]
                               + list(companies.values()))
    cname: dict[int, str] = {}
    person: dict[int, bool] = {}
    for key, raw in companies.items():
        cid = int(key)
        cname[cid] = casing.fix(tp.clean_name(raw), "name")
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
        for n, cpv, title, est, bids in rec["lots"]:
            lead = _leader(bids)
            for b in bids:
                bidders.add(b[0])
            if lead and est:
                est_sum += est
                low_sum += lead[3] or 0
                leaders[lead[0]] = leaders.get(lead[0], 0) + 1
            lots_out.append({"n": n, "cpv": cpv, "t": title, "est": est,
                             "bids": [{"c": b[0], "nm": cname.get(b[0], ""), "p": b[1], "lv": b[2], "lp": b[3],
                                       "fp": b[4], "rej": b[5], **({"per": 1} if person.get(b[0]) else {})}
                                      for b in bids]})
            ok = [b for b in bids if not b[5]]
            row = [cpv, title, rec["id"], bkey, buyer, date, est, lead[3] if lead else None, len(ok),
                   [[b[0], cname.get(b[0], ""), b[1]] for b in ok[:4] if not person.get(b[0])]]
            if cpv:
                by_cpv.setdefault(cpv[:5], []).append(row)
            by_buyer.setdefault(bkey, {"name": buyer, "rows": [], "lots": []})["lots"].append(
                [cpv, title, rec["id"], date, est, lead[3] if lead else None, len(ok),
                 shown(lead[0]) if lead else ""])
            for b in bids:
                if person.get(b[0]):
                    continue                                # sole proprietors get no page of their own
                by_company.setdefault(b[0], []).append(
                    [rec["id"], n, cpv, title, buyer, date, b[1], b[3], est, b[5]])
                t = tally.setdefault(b[0], [0, 0])
                t[0] += 1
                if lead and lead[0] == b[0]:
                    t[1] += 1
        top = max(leaders, key=leaders.get) if leaders else None
        summary = [rec["id"], subject or "", buyer, bkey, date, sector, len(rec["lots"]), len(bidders),
                   round(est_sum) or None, round(low_sum) or None,
                   shown(top), 0 if rec["lots"] and bidders else 1]
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
                      "from": next((d for d in all_dates if d), None), "to": dates[0] if dates else None})

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

    backlog = any(not lots_state.get("t", {}).get(str(t["id"]), {}).get("ok") for t in tenders if store.is_open(t, at))
    inv = read_invitations(tenders, lots_state, at, clock, fetch_bytes, until_share=0.6 if backlog else 1.0)
    _write(LOTS_STATE, lots_state)
    say(f"Invitations: {inv['read']} read" + (f", {inv['failed']} failed" if inv["failed"] else "")
        + (f", {inv['later']} left for later" if inv["later"] else ""))

    res = read_results(tenders, hist, records, at, clock, fetch_page)
    save_results(records)
    _write(HIST_STATE, hist)
    say(f"Results: {res['new']} finished tenders read, {res['not_final']} not decided yet"
        + (f", {res['failed']} failed" if res["failed"] else "") + f"; {len(records)} kept in all")

    out = publish_history(records, hist.get("companies", {}), at)
    say(f"Published {out['files']} history files" + (f", removed {out['removed']}" if out["removed"] else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--minutes", type=float, default=20, help="how long this run may read the register")
    args = ap.parse_args(argv)
    return run(args.minutes)


if __name__ == "__main__":
    sys.exit(main())
