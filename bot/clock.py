"""Keeps the time for the site's updates, because GitHub starts scheduled jobs late or not at all.

    python -m bot.clock            one tick: wait for the slot, start the next tick and what is due
    python -m bot.clock --watch    start the clock again if it has stopped (the update jobs end with this)
    python -m bot.clock --trial    try the wiring once, without waiting

The Clock workflow runs one tick at a time. GitHub holds a tick's job in the "clock" environment for that
environment's wait timer (175 minutes, set in Settings -> Environments); nothing runs while it is held. The tick
then wakes a few minutes before one of eight moments a day, three hours apart, sleeps the rest, starts the next
tick and, at 08:50, 11:50, 14:50 and 17:50 Yerevan time from Monday to Saturday, the two update jobs. At the
four night slots it starts the long reading that works back through the past year.

Standard library only. Times are UTC inside; Yerevan is four hours ahead all year.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

STEP = timedelta(hours=3)                  # slots are three hours apart ...
FIRST = timedelta(hours=1, minutes=50)     # ... from 01:50 UTC: 05:50, 08:50, 11:50 ... in Yerevan
WAIT = 175                                 # minutes GitHub holds a tick: the environment's wait timer
MIN_WAIT = 150                             # a tick held for less was not held by the timer
EARLY = timedelta(minutes=20)              # a slot this near is waited for
LATE = timedelta(minutes=30)               # a slot this recently passed is served at once
PROBE = timedelta(hours=6)                 # how often to try again while the timer is not set
# What the Tenders job does at a slot, Monday to Saturday (UTC hour and minute): 08:50 to 17:50 in Yerevan.
UPDATES = {(4, 50): "digest", (7, 50): "refresh", (10, 50): "refresh", (13, 50): "digest"}
HISTORY_MINUTES = "15"                     # with each of those, a short look inside new invitations and at fresh results
# Every night at 20:50, 23:50, 02:50 and 05:50 in Yerevan: the History job's long reading, back through the past year.
NIGHTS = {(16, 50), (19, 50), (22, 50), (1, 50)}
NIGHT_MINUTES = "170"                    # nearly the whole three hours, so the reading hardly pauses at night
TICK = "Tick"                              # the run name of a tick, set in the workflow


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def slot_before(at: datetime) -> datetime:
    """The last slot at or before `at`."""
    day = at.replace(hour=0, minute=0, second=0, microsecond=0)
    return day + FIRST + ((at - day - FIRST) // STEP) * STEP


def due(slot: datetime) -> str | None:
    """What the Tenders job should do at this slot; None when it has nothing to do then."""
    if slot.weekday() == 6:                # Sunday
        return None
    return UPDATES.get((slot.hour, slot.minute))


def reading(slot: datetime) -> str | None:
    """How many minutes the History job should read at this slot; None when it has nothing to do then."""
    if (slot.hour, slot.minute) in NIGHTS:
        return NIGHT_MINUTES
    return HISTORY_MINUTES if due(slot) else None


@dataclass
class Plan:
    slot: datetime                         # the slot this tick serves
    sleep: float                           # seconds to wait for it
    missed: datetime | None = None         # an update that is overdue and is started before waiting


def plan(now: datetime, last_update: datetime | None = None) -> Plan:
    """What a tick does when it wakes at `now`. Usually the next slot is a few minutes ahead. A tick that wakes
    late serves the slot it missed at once. One that is out of step (the first after a start) waits for the next
    slot, however far, and first starts an update that was due and has not run."""
    prev = slot_before(now)
    nxt = prev + STEP
    if now - prev <= LATE:
        return Plan(prev, 0.0)
    if nxt - now <= EARLY:
        return Plan(nxt, (nxt - now).total_seconds())
    missed = prev if due(prev) and (last_update is None or last_update < prev) else None
    return Plan(nxt, (nxt - now).total_seconds(), missed)


def should_restart(runs: list[dict], now: datetime) -> bool:
    """Whether the update jobs should start a tick. `runs` are the Clock workflow's, newest first."""
    ticks = [r for r in runs if r.get("display_title") == TICK]
    if any(r.get("status") != "completed" for r in ticks):
        return False                       # one is held or running
    for r in ticks:
        if r.get("conclusion") == "cancelled":
            continue
        ended = when(r["updated_at"])
        held = ended - when(r["created_at"])
        if held >= timedelta(minutes=MIN_WAIT):
            return True                    # the timer is set, so the chain broke: mend it
        return now - ended >= PROBE        # the timer was not set then: look again from time to time
    return True                            # never started


class Hub:
    """The few GitHub calls the clock makes, as the workflow's own token."""

    def __init__(self, repo: str, token: str, branch: str, run_id: str = "", pause=time.sleep):
        self.repo, self.token, self.branch, self.run_id, self.pause = repo, token, branch, run_id, pause

    def _call(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}{path}", method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tender-bot-clock"})
        last: Exception | None = None
        for wait in (0, 5, 20):
            if wait:
                self.pause(wait)
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                return json.loads(data) if data else None
            except urllib.error.HTTPError as e:
                last = RuntimeError(f"GitHub answered {e.code} to {method} {path}: {e.read()[:200].decode('utf-8', 'replace')}")
                if e.code < 500 and e.code != 429:
                    break                  # asking again will not change the answer
            except (urllib.error.URLError, TimeoutError) as e:
                last = RuntimeError(f"GitHub could not be reached for {method} {path}: {e}")
        raise last

    def start(self, workflow: str, **inputs: str) -> None:
        self._call("POST", f"/actions/workflows/{workflow}/dispatches", {"ref": self.branch, "inputs": inputs})

    def runs(self, workflow: str, count: int) -> list[dict]:
        return self._call("GET", f"/actions/workflows/{workflow}/runs?per_page={count}")["workflow_runs"]

    def this_run(self) -> dict:
        return self._call("GET", f"/actions/runs/{self.run_id}")


def hhmm(at: datetime) -> str:
    return (at + timedelta(hours=4)).strftime("%H:%M")      # as a clock in Yerevan shows it


def start_updates(hub, slot: datetime, say) -> bool:
    ok = True
    for workflow, inputs in (("tenders.yml", {"mode": due(slot)}), ("history.yml", {"minutes": reading(slot)})):
        if not list(inputs.values())[0]:
            continue                       # at night only the reading runs
        try:
            hub.start(workflow, **inputs)
            say(f"Started {workflow} for {hhmm(slot)}: {inputs}")
        except RuntimeError as e:
            ok = False
            say(f"::error::{workflow} could not be started: {e}")
    return ok


def tick(hub, now=lambda: datetime.now(timezone.utc), sleep=time.sleep, say=print) -> int:
    held = now() - when(hub.this_run()["created_at"])
    if held < timedelta(minutes=MIN_WAIT):
        # Without the timer every tick would start the next at once, for ever. Stop here instead.
        say(f"::warning::This tick was held for {int(held.total_seconds() // 60)} minutes, so the clock environment has no "
            f"wait timer yet. Set it to {WAIT} minutes in Settings -> Environments -> clock. Nothing was started.")
        return 0
    newest = hub.runs("tenders.yml", 1)
    p = plan(now(), when(newest[0]["created_at"]) if newest else None)
    ok = True
    if p.missed:
        say(f"The {hhmm(p.missed)} update has not run. Starting it now.")
        ok = start_updates(hub, p.missed, say)
    if p.sleep:
        say(f"Waiting {int(p.sleep // 60)} min {int(p.sleep % 60)} s for {hhmm(p.slot)}.")
        sleep(p.sleep)
    try:
        hub.start("clock.yml", do="tick")       # first, so that the chain does not depend on what follows
        say(f"The next tick is set: it wakes in about {WAIT} minutes.")
    except RuntimeError as e:
        ok = False
        say(f"::error::The next tick could not be started: {e}")
    if reading(p.slot):
        ok = start_updates(hub, p.slot, say) and ok
    else:
        say(f"Nothing is due at {hhmm(p.slot)}.")
    return 0 if ok else 1


def watch(hub, now=lambda: datetime.now(timezone.utc), say=print) -> int:
    """Never fails: it is the last step of jobs that have other work to report."""
    try:
        if should_restart(hub.runs("clock.yml", 20), now()):
            hub.start("clock.yml", do="tick")
            say("The clock was not running. Started a tick.")
        else:
            say("The clock is running, or is waiting for its timer to be set.")
    except (RuntimeError, KeyError, ValueError) as e:
        say(f"::warning::The clock could not be checked: {e}")
    return 0


def trial(hub, say=print) -> int:
    hub.start("tenders.yml", mode="inbox")
    say("Started tenders.yml in inbox mode (it reads nothing).")
    hub.start("clock.yml", do="nothing")
    say("Started one more Clock run that does nothing.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--trial", action="store_true")
    args = ap.parse_args(argv)
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and token):
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are not set: this runs inside the repository's workflows.")
        return 0 if args.watch else 2
    hub = Hub(repo, token, os.environ.get("GITHUB_REF_NAME", "main"), os.environ.get("GITHUB_RUN_ID", ""))
    if args.watch:
        return watch(hub)
    if args.trial:
        return trial(hub)
    return tick(hub)


if __name__ == "__main__":
    sys.exit(main())
