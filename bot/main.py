"""Entry point.  python -m bot.main --mode digest|refresh|inbox

digest   read ARMEPS, update the app's data file, send the Telegram message
refresh  read ARMEPS and update the data file, send nothing
inbox    only answer people who wrote to the bot (pressed Start / Stop)
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

from . import armeps, digest, epps, store, telegram
from .textproc import kind_key

MAX_PAGES = 60
MAX_DETAILS = 600
DETAIL_TRIES = 3
BUDGET = 9 * 60     # seconds one run may spend reading ARMEPS; what is left waits for the next run
WORKERS = 2         # notice pages read side by side; the site resets a third connection
GIVE_UP_AFTER = 8   # notice pages failing in a row before the run stops asking for more
MAX_ID_PAGES = 40   # how deep the list ordered by number may be followed (about 20 pages reach the oldest open)
ID_ORDERINGS = ("by_id", "by_tender_id", "by_number")
SAFE_DROP = 15      # open tenders one run may close before its deadline; above it (or 5%), the safety net holds


def say(text: str) -> None:
    """Print a line at once, so a running job shows where it is."""
    print(text, flush=True)


def app_url() -> str | None:
    """Where the app is served: the APP_URL variable, or this repository's GitHub Pages."""
    url = (os.environ.get("APP_URL") or "").strip()
    if not url:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repo:
            owner, name = repo.split("/", 1)
            host = f"{owner.lower()}.github.io"
            url = f"https://{host}/" if name.lower() == host else f"https://{host}/{name}/"
    return url or None


def load_config() -> dict:
    try:
        with open("config.json", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _debug_dump(name: str, html: str) -> None:
    os.makedirs("debug", exist_ok=True)
    with open(os.path.join("debug", name), "w", encoding="utf-8") as fh:
        fh.write(html)


def scrape(tenders: dict[int, dict], at: datetime, fetch=armeps.fetch, pause: float = 0.3,
           budget: float = BUDGET, clock=time.monotonic) -> dict:
    """Walk the list (latest deadline first) until the deadlines are in the past, then read
    the notice page of every open tender that has not been read yet.

    A run never spends more than `budget` seconds here: whatever is not read in time keeps
    its title and deadline from the list and gets its notice read by the next run."""
    started = clock()
    first_run = not tenders     # nothing is remembered yet: what the list holds is not "new"
    floor = at - timedelta(days=1)
    seen: set[int] = set()
    stats = {"pages": 0, "rows": 0, "new": 0, "details": 0, "detail_failed": 0, "postponed": 0, "gone": 0}
    oldest = min((i for i, t in tenders.items() if not t.get("src") and store.is_open(t, at)), default=None)

    def take(r) -> datetime | None:
        """Remember one list row if its deadline is current. Returns its deadline."""
        seen.add(r.id)
        end = store.parse(r.deadline)
        if end is None or end < floor:
            return end
        stats["rows"] += 1
        t = tenders.get(r.id)
        if t is None:
            t = tenders[r.id] = {"id": r.id}
            if not first_run:
                t["seen"] = store.stamp(at)
            stats["new"] += 1
        if t.get("end") and t["end"] != r.deadline:
            t["stale"] = True  # the deadline moved: re-read the other dates too
        t.update(code=r.code, lots=r.lots, end=r.deadline,
                 status=store.status_key(r.status), status_text=r.status)
        t.pop("miss", None)
        t.pop("gone", None)     # back on the list
        if not t.get("pub") or not t.get("title"):
            t["title"] = r.title
        return end

    orderings: list[str] = []
    links: list[str] = []
    for page in range(1, MAX_PAGES + 1):
        try:
            html = fetch(armeps.list_url(page))
        except armeps.ScrapeError as exc:
            if page == 1:
                raise
            say(f"! list page {page}: {exc} Keeping what the first {page - 1} page(s) gave.")
            break
        rows = armeps.parse_list(html)
        if page == 1 and not rows:
            _debug_dump("list_1.html", html)
            raise armeps.ScrapeError(
                "The tender list opened but no tender rows were found. The page layout may "
                "have changed; the page was saved to debug/list_1.html.")
        if page == 1:
            orderings, links = armeps.sort_keys(html), armeps.list_links(html)
        fresh_rows = [r for r in rows if r.id not in seen]
        if not fresh_rows:
            break
        stats["pages"] += 1
        ends = [e for e in (take(r) for r in fresh_rows) if e is not None]
        if ends and max(ends) < floor:
            break
        if clock() - started > budget:
            say(f"! The list is answering slowly: stopped after page {page}.")
            break
        time.sleep(pause)
    say(f"List: {stats['pages']} page(s), {stats['rows']} current tenders, {stats['new']} new")

    # Tenders with the same deadline come in no fixed order, so a page can skip one. Numbers have no ties: walk
    # the list ordered by number from the newest down to the oldest open auction. Every open auction should be on
    # it; one missing from two whole walks in a row has been taken off the list (cancelled or suspended, most
    # likely) and is no longer shown as open.
    by_number = next((k for k in ID_ORDERINGS if k in orderings), None)
    if not by_number and links:
        say("  (no ordering by number among the list's links: " + ", ".join(links) + ")")
    whole = False
    if by_number:
        before = stats["rows"]
        for page in range(1, MAX_ID_PAGES + 1):
            if clock() - started > budget:
                break
            try:
                rows = armeps.parse_list(fetch(armeps.list_url(page, by_number)))
            except armeps.ScrapeError as exc:
                say(f"! list by number, page {page}: {exc}")
                break
            ids = [r.id for r in rows]
            if not ids:
                break
            if ids != sorted(ids, reverse=True):
                say("! The list by number did not come newest first: left out.")
                break
            for r in rows:
                if r.id not in seen:
                    take(r)
            if oldest is not None and ids[-1] <= oldest:
                whole = True
                break
            time.sleep(pause)
        say(f"List by number: {stats['rows'] - before} tender(s) the first list had skipped"
            + ("" if whole or oldest is None else "; not read down to the oldest open auction"))
    if whole:
        for i, t in tenders.items():
            if t.get("src") or i in seen or not store.is_open(t, at):
                continue
            t["miss"] = t.get("miss", 0) + 1
            if t["miss"] >= 2:
                t.pop("miss")
                t.update(status="other", status_text="Հանված է ցանկից", gone=store.stamp(at))
                stats["gone"] += 1
        if stats["gone"]:
            say(f"Taken off ARMEPS's list: {stats['gone']} auction(s), no longer shown as open")

    # notice pages: full title, buyer, publication time, other dates, invitation
    todo = [t for t in tenders.values()
            if not t.get("src") and t.get("status") == "open" and (not t.get("pub") or t.get("stale"))
            and t.get("dt", 0) < DETAIL_TRIES and (store.parse(t.get("end")) or at) > at]
    todo.sort(key=lambda t: -t["id"])   # newest notices first
    todo = todo[:MAX_DETAILS]
    if not todo:
        return stats
    quick = armeps.fetch_notice if fetch is armeps.fetch else fetch
    stop = threading.Event()
    lock = threading.Lock()
    failing = [0]                       # notice pages that failed one after another

    def read(t: dict):
        if stop.is_set() or clock() - started > budget:
            return None, "later"
        try:
            d, err = armeps.parse_detail(quick(armeps.detail_url(t["id"]))), ""
        except armeps.ScrapeError as exc:
            d, err = None, str(exc)
        if d is not None and not d.get("published") and not d.get("buyer"):
            d, err = None, "the page opened but had no notice on it."
        with lock:
            failing[0] = failing[0] + 1 if d is None else 0
            if failing[0] >= GIVE_UP_AFTER:
                stop.set()
        if d is not None and pause:
            time.sleep(pause)
        return d, err

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for n, (t, (d, err)) in enumerate(zip(todo, pool.map(read, todo)), 1):
            if err == "later":
                stats["postponed"] += 1
                continue
            t["dt"] = t.get("dt", 0) + 1
            if d is None:
                stats["detail_failed"] += 1
                say(f"! notice {t['id']}: {err}")
                continue
            stats["details"] += 1
            if d.get("title") and len(d.get("title")) >= len(t.get("title") or ""):
                t["title"] = d.get("title")
            t["buyer_official"] = d.get("buyer") or t.get("buyer_official")
            t["kind"] = kind_key(d.get("kind")) or t.get("kind")
            t["pub"] = d.get("published") or t.get("pub")
            t["ask"] = d.get("questions_until") or t.get("ask")
            t["auc"] = d.get("auction") or t.get("auc")
            t["inv"] = d.get("invitation") or t.get("inv")
            t.pop("stale", None)
            if n % 50 == 0:
                say(f"  notices: {n} of {len(todo)}")
    if stop.is_set():
        say("! Notice pages stopped answering: the rest are left for the next run.")
    return stats


def hold_sudden_closing(tenders: dict[int, dict], before: dict[int, tuple], at: datetime,
                        held_last: set[int], say=say) -> set[int]:
    """The safety net. `before` holds the status of every tender that was open when the run began.

    A run that closes a few open tenders before their deadline is normal: an auction is cancelled, a call is
    withdrawn. A run that closes many at once has more likely read only part of a site (on 19 Nov 2026 a short
    EPPS list closed 222). Those tenders stay open, and are remembered: when the next run closes mostly the same
    ones again, the closing is believed. Returns the tenders held open."""
    closed = {i for i in before if i in tenders and not store.is_open(tenders[i], at)
              and (store.parse(tenders[i].get("end")) or at) > at}
    if len(closed) <= max(SAFE_DROP, len(before) // 20):
        return set()
    if held_last and len(closed & held_last) >= 0.8 * len(closed):
        say(f"! Safety net: {len(closed)} open tenders closed for the second run in a row; believed.")
        return set()
    for i in closed:
        t = tenders[i]
        for key, value in zip(("status", "status_text", "gone"), before[i]):
            if value is None:
                t.pop(key, None)
            else:
                t[key] = value
    say(f"! Safety net: this run would have closed {len(closed)} open tenders at once, before their deadlines. "
        "They stay open; a second run closing the same ones will be believed.")
    return closed


def update_data(at: datetime, fetch=armeps.fetch, pause: float = 0.3, with_epps: bool | None = None) -> dict:
    data = store.load()
    tenders = {t["id"]: t for t in data["tenders"]}
    before = {i: (t.get("status"), t.get("status_text"), t.get("gone"))
              for i, t in tenders.items() if store.is_open(t, at)}
    stats = scrape(tenders, at, fetch=fetch, pause=pause)
    if with_epps is None:
        with_epps = fetch is armeps.fetch                   # tests that pass their own pages stay off the network
    done = set(data.get("epps_done", []))                   # expired EPPS calls that EPPS still lists
    listed = None
    if with_epps:                                           # EPPS: price quotations, open tenders and the rest
        try:
            got = epps.update(tenders, at, say=say, skip=done)
            if got.get("whole"):                            # only a whole list may shorten the memory
                listed = got["ids"]
        except armeps.ScrapeError as exc:
            say(f"! EPPS: {exc} The calls already known stay as they were.")
    data["held"] = sorted(hold_sudden_closing(tenders, before, at, set(data.get("held", []))))
    items = store.prune(list(tenders.values()), at)
    kept = {t["id"] for t in items}
    done |= {i for i, t in tenders.items() if t.get("src") == "epps" and i not in kept}
    data["epps_done"] = sorted(done & listed) if listed is not None else sorted(done)
    store.enrich(items)
    data["tenders"] = [store.compact(t) for t in items]
    data["meta"] = {"updated": store.stamp(at), "source": "eauction.armeps.am, armeps.am/epps",
                    "open": sum(store.is_open(t, at) for t in store.drop_doubles(items))}
    store.save(data)       # what the bot remembers
    store.publish(data)    # what the app shows
    say(f"ARMEPS: {stats['pages']} pages, {stats['rows']} current tenders, "
        f"{stats['new']} new, {stats['details']} notices read"
        + (f", {stats['detail_failed']} notices unreadable" if stats["detail_failed"] else "")
        + (f", {stats['postponed']} left for the next run" if stats["postponed"] else ""))
    if stats["rows"] and stats["details"] == 0 and stats["detail_failed"] > 3:
        say("! No notice page could be read. Titles and deadlines are still correct, but "
            "buyer names and publication times are missing.")
    return data


def run(mode: str, period: str = "auto", dry_run: bool = False, fetch=armeps.fetch,
        pause: float = 0.3) -> int:
    at = store.now()
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    url = app_url()
    cfg = load_config()
    scrape_error = None

    if mode in ("digest", "refresh"):
        try:
            data = update_data(at, fetch=fetch, pause=pause)
        except armeps.ScrapeError as exc:
            scrape_error = exc
            print(f"! {exc}")
            data = store.load()
    else:
        data = store.load()
    tenders = data["tenders"]

    if not token:
        print("No TELEGRAM_BOT_TOKEN secret is set: "
              + ("nothing to do." if mode == "inbox" else "the data was updated, nothing was sent."))
        return 1 if scrape_error else 0

    state = telegram.load_state(token)
    if state.get("setup") != 2 or state.get("app_url") != url:
        telegram.setup(token, url, digest)
        state["setup"], state["app_url"] = 2, url

    joined, left, others = telegram.sync_inbox(token, state)
    if not dry_run:
        for chat in joined:
            _try_send(token, chat, digest.welcome(tenders, at), url)
        for chat in left:
            _try_send(token, chat, digest.GOODBYE, None)
        for chat in others:
            _try_send(token, chat, digest.HINT, url)
    if joined or left:
        print(f"Telegram: {len(joined)} joined, {len(left)} left, {len(state['subs'])} subscribed")

    if mode == "digest" and not scrape_error:
        last = store.parse(state.get("last_digest"))
        if period == "auto":                        # 08:50: the morning summary; 11:50, 14:50, 17:50: what is new
            period = "morning" if at.hour < 10 else "evening"
        if period == "morning" and last and last.date() == at.date() and last.hour >= 7:
            period = "evening"                      # the morning message went out already: only what is new
        default_since = at - timedelta(hours=24 if period == "morning" else 10)
        since = last or default_since
        since = max(since, at - timedelta(days=4))  # never dump weeks of backlog
        text = digest.build(tenders, at, since, period, cfg.get("focus_keywords"), url, digest.group_stems())
        if text is None:
            print("Nothing new since the last message: no evening message sent.")
        elif dry_run:
            print("----- message (not sent) -----\n" + text)
        else:
            sent = telegram.broadcast(token, state, text, url, digest.BUTTON)
            state["last_digest"] = store.stamp(at)
            print(f"Telegram: {period} message sent to {sent} chat(s)")
            if sent == 0:
                print("  Nobody has pressed Start in the bot yet. Open the bot in Telegram, "
                      "press Start, then run this workflow again.")

    if not dry_run:
        telegram.save_state(state, token)
    return 1 if scrape_error else 0


def _try_send(token: str, chat: int, text: str, url: str | None) -> None:
    try:
        telegram.send(token, chat, text, url, digest.BUTTON)
    except telegram.TelegramError as exc:
        print(f"! could not answer one chat: {exc.description}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--mode", choices=["digest", "refresh", "inbox"], default="digest")
    ap.add_argument("--period", choices=["auto", "morning", "evening"], default="auto")
    ap.add_argument("--dry-run", action="store_true", help="print the message instead of sending it")
    args = ap.parse_args(argv)
    try:
        return run(args.mode, args.period, args.dry_run)
    except telegram.TelegramError as exc:
        hint = ""
        if exc.code in (401, 404):
            hint = " Check the TELEGRAM_BOT_TOKEN secret: copy the token from @BotFather again."
        print(f"! {exc}.{hint}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
