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

from . import armeps, digest, store, telegram
from .textproc import kind_key

MAX_PAGES = 60
MAX_DETAILS = 600
DETAIL_TRIES = 3
BUDGET = 9 * 60     # seconds one run may spend reading ARMEPS; what is left waits for the next run
WORKERS = 2         # notice pages read side by side; the site resets a third connection
GIVE_UP_AFTER = 8   # notice pages failing in a row before the run stops asking for more


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
    stats = {"pages": 0, "rows": 0, "new": 0, "details": 0, "detail_failed": 0, "postponed": 0}
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
        fresh_rows = [r for r in rows if r.id not in seen]
        if not fresh_rows:
            break
        stats["pages"] += 1
        latest = None
        for r in fresh_rows:
            seen.add(r.id)
            end = store.parse(r.deadline)
            if end is None:
                continue
            latest = end if latest is None or end > latest else latest
            if end < floor:
                continue
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
            if not t.get("pub") or not t.get("title"):
                t["title"] = r.title
        if latest is not None and latest < floor:
            break
        if clock() - started > budget:
            say(f"! The list is answering slowly: stopped after page {page}.")
            break
        time.sleep(pause)
    say(f"List: {stats['pages']} page(s), {stats['rows']} current tenders, {stats['new']} new")

    # notice pages: full title, buyer, publication time, other dates, invitation
    todo = [t for t in tenders.values()
            if t.get("status") == "open" and (not t.get("pub") or t.get("stale"))
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


def update_data(at: datetime, fetch=armeps.fetch, pause: float = 0.3) -> dict:
    data = store.load()
    tenders = {t["id"]: t for t in data["tenders"]}
    stats = scrape(tenders, at, fetch=fetch, pause=pause)
    items = store.prune(list(tenders.values()), at)
    store.enrich(items)
    data["tenders"] = [store.compact(t) for t in items]
    data["meta"] = {"updated": store.stamp(at), "source": "eauction.armeps.am",
                    "open": sum(store.is_open(t, at) for t in items)}
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
        if period == "auto":
            period = "morning" if at.hour < 14 else "evening"
        default_since = at - timedelta(hours=24 if period == "morning" else 10)
        since = store.parse(state.get("last_digest")) or default_since
        since = max(since, at - timedelta(days=4))  # never dump weeks of backlog
        text = digest.build(tenders, at, since, period, cfg.get("focus_keywords"))
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
