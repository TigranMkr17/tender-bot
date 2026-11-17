"""Offline checks of the clock that starts the updates. GitHub is not contacted: a stand-in records what would
have been started, and time is a number that the test moves."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import clock  # noqa: E402

UTC = timezone.utc


def at(day, hour, minute, second=0):
    return datetime(2026, 11, day, hour, minute, second, tzinfo=UTC)      # 16 November 2026 is a Monday


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class Time:
    def __init__(self, now):
        self.t, self.slept = now, 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept += seconds
        self.t += timedelta(seconds=seconds)


class Hub:
    def __init__(self, created, last_update=None, clock_runs=(), broken=()):
        self.created, self.last_update, self.clock_runs, self.broken = created, last_update, list(clock_runs), broken
        self.started, self.said = [], []

    def this_run(self):
        return {"created_at": stamp(self.created)}

    def runs(self, workflow, count):
        if workflow == "clock.yml":
            return self.clock_runs
        return [{"created_at": stamp(self.last_update)}] if self.last_update else []

    def start(self, workflow, **inputs):
        if workflow in self.broken:
            raise RuntimeError("GitHub answered 500")
        self.started.append((workflow, inputs))

    def say(self, text):
        self.said.append(text)


def tick(woke, held=175, **hub):
    time, h = Time(woke), Hub(woke - timedelta(minutes=held), **hub)
    code = clock.tick(h, now=time.now, sleep=time.sleep, say=h.say)
    return code, h, time


class Slots(unittest.TestCase):
    def test_eight_a_day_three_hours_apart(self):
        day = [clock.hhmm(clock.slot_before(at(17, h, 55))) for h in range(24)]
        self.assertEqual(sorted(set(day)), ["02:50", "05:50", "08:50", "11:50", "14:50", "17:50", "20:50", "23:50"])
        self.assertEqual(clock.slot_before(at(17, 4, 50)), at(17, 4, 50))
        self.assertEqual(clock.slot_before(at(17, 4, 49, 59)), at(17, 1, 50))
        self.assertEqual(clock.slot_before(at(17, 0, 10)), at(16, 22, 50))

    def test_four_updates_from_monday_to_saturday(self):
        def day(d):
            return [clock.due(at(d, h, 50)) for h in (1, 4, 7, 10, 13, 16, 19, 22)]
        for d in range(16, 22):                                             # Monday to Saturday
            self.assertEqual(day(d), [None, "digest", "refresh", "refresh", "digest", None, None, None])
        self.assertEqual(day(22), [None] * 8)                               # Sunday


class Ticks(unittest.TestCase):
    def test_without_the_timer_nothing_starts(self):
        code, h, time = tick(at(17, 4, 45), held=1)
        self.assertEqual((code, h.started, time.slept), (0, [], 0.0))
        self.assertIn("175 minutes", h.said[0])

    def test_a_morning_tick_waits_for_its_minute_then_starts_the_next_tick_first(self):
        code, h, time = tick(at(17, 4, 45, 10))
        self.assertEqual(code, 0)
        self.assertEqual(time.slept, 290)
        self.assertEqual(time.now(), at(17, 4, 50))
        self.assertEqual(h.started, [("clock.yml", {"do": "tick"}), ("tenders.yml", {"mode": "digest"}),
                                     ("history.yml", {"minutes": "15"})])

    def test_midday_updates_refresh_and_the_evening_one_sends_the_digest(self):
        self.assertEqual(tick(at(17, 7, 46))[1].started[1], ("tenders.yml", {"mode": "refresh"}))
        self.assertEqual(tick(at(17, 10, 46))[1].started[1], ("tenders.yml", {"mode": "refresh"}))
        self.assertEqual(tick(at(21, 13, 46))[1].started[1], ("tenders.yml", {"mode": "digest"}))     # Saturday

    def test_at_night_it_starts_the_long_reading_and_on_sunday_nothing_else(self):
        for woke in (at(17, 16, 45), at(17, 19, 46), at(17, 22, 47), at(18, 1, 44), at(22, 22, 45)):
            code, h, _ = tick(woke)
            self.assertEqual((code, h.started), (0, [("clock.yml", {"do": "tick"}), ("history.yml", {"minutes": "95"})]))
        for woke in (at(22, 4, 45), at(22, 7, 45), at(22, 10, 45), at(22, 13, 45)):          # Sunday, by day
            code, h, _ = tick(woke)
            self.assertEqual((code, h.started), (0, [("clock.yml", {"do": "tick"})]))

    def test_every_slot_of_the_week_has_its_work(self):
        week = [at(16, 1, 50) + i * clock.STEP for i in range(56)]
        self.assertEqual(sum(1 for s in week if clock.due(s)), 24)                             # four a day, six days
        self.assertEqual(sum(1 for s in week if clock.reading(s) == "95"), 28)                 # four a night
        self.assertEqual(sum(1 for s in week if clock.reading(s) == "15"), 24)
        self.assertEqual(sum(1 for s in week if not clock.reading(s)), 4)                      # Sunday by day

    def test_a_tick_that_wakes_late_does_not_wait_three_hours(self):
        code, h, time = tick(at(17, 7, 58), held=183)
        self.assertEqual(time.slept, 0)
        self.assertEqual([w for w, _ in h.started], ["clock.yml", "tenders.yml", "history.yml"])

    def test_out_of_step_it_runs_the_overdue_update_then_falls_into_step(self):
        code, h, time = tick(at(17, 6, 0), last_update=at(17, 2, 35))
        self.assertEqual(code, 0)
        self.assertEqual(h.started[:2], [("tenders.yml", {"mode": "digest"}), ("history.yml", {"minutes": "15"})])
        self.assertEqual(time.now(), at(17, 7, 50))
        self.assertEqual(h.started[2:], [("clock.yml", {"do": "tick"}), ("tenders.yml", {"mode": "refresh"}),
                                         ("history.yml", {"minutes": "15"})])

    def test_out_of_step_it_does_not_repeat_an_update_that_ran(self):
        code, h, time = tick(at(17, 6, 0), last_update=at(17, 4, 52))
        self.assertEqual(h.started[0], ("clock.yml", {"do": "tick"}))
        self.assertEqual(time.now(), at(17, 7, 50))

    def test_updates_start_even_if_the_next_tick_cannot(self):
        code, h, _ = tick(at(17, 4, 46), broken=("clock.yml",))
        self.assertEqual(code, 1)
        self.assertEqual([w for w, _ in h.started], ["tenders.yml", "history.yml"])

    def test_the_next_tick_starts_even_if_an_update_cannot(self):
        code, h, _ = tick(at(17, 4, 46), broken=("tenders.yml",))
        self.assertEqual(code, 1)
        self.assertEqual([w for w, _ in h.started], ["clock.yml", "history.yml"])

    def test_in_step_a_tick_wakes_five_minutes_before_the_next_slot(self):
        # the next tick is started at the slot and held for 175 minutes: it wakes inside the waiting window
        woke = at(17, 4, 50) + timedelta(minutes=clock.WAIT, seconds=40)
        p = clock.plan(woke)
        self.assertEqual((p.slot, p.missed), (at(17, 7, 50), None))
        self.assertLess(p.sleep, 5 * 60)


def run(title="Tick", status="completed", conclusion="success", created=None, minutes=176):
    created = created or at(17, 4, 50)
    return {"display_title": title, "status": status, "conclusion": conclusion,
            "created_at": stamp(created), "updated_at": stamp(created + timedelta(minutes=minutes))}


class Watch(unittest.TestCase):
    def test_a_held_or_running_tick_is_left_alone(self):
        for status in ("waiting", "pending", "queued", "in_progress"):
            self.assertFalse(clock.should_restart([run(status=status, conclusion=None), run()], at(17, 9, 0)))

    def test_a_broken_chain_is_mended(self):
        self.assertTrue(clock.should_restart([run(), run(created=at(17, 1, 50))], at(17, 9, 0)))
        self.assertTrue(clock.should_restart([run(conclusion="failure")], at(17, 9, 0)))

    def test_before_the_timer_is_set_it_looks_again_only_now_and_then(self):
        stopped = run(minutes=1)                                            # ended at 04:51
        self.assertFalse(clock.should_restart([stopped], at(17, 6, 0)))
        self.assertTrue(clock.should_restart([stopped], at(17, 11, 0)))

    def test_it_starts_a_clock_that_never_ran(self):
        self.assertTrue(clock.should_restart([], at(17, 9, 0)))
        self.assertTrue(clock.should_restart([run(title="Trial", minutes=1), run(title="Nothing", minutes=1)], at(17, 9, 0)))

    def test_a_cancelled_tick_says_nothing_about_the_timer(self):
        self.assertTrue(clock.should_restart([run(conclusion="cancelled", minutes=2), run()], at(17, 9, 0)))
        self.assertFalse(clock.should_restart([run(conclusion="cancelled", minutes=2), run(minutes=1)], at(17, 6, 0)))

    def test_watching_starts_a_tick_and_never_fails_the_job_it_ends(self):
        h = Hub(at(17, 9, 0), clock_runs=[run()])
        self.assertEqual(clock.watch(h, now=lambda: at(17, 9, 0), say=h.say), 0)
        self.assertEqual(h.started, [("clock.yml", {"do": "tick"})])
        h = Hub(at(17, 9, 0), clock_runs=[run(status="waiting", conclusion=None)])
        self.assertEqual(clock.watch(h, now=lambda: at(17, 9, 0), say=h.say), 0)
        self.assertEqual(h.started, [])
        h = Hub(at(17, 9, 0), clock_runs=[run()], broken=("clock.yml",))
        self.assertEqual(clock.watch(h, now=lambda: at(17, 9, 0), say=h.say), 0)
        self.assertIn("could not be checked", h.said[-1])

    def test_a_trial_starts_one_harmless_run_of_each(self):
        h = Hub(at(17, 9, 0))
        self.assertEqual(clock.trial(h, say=h.say), 0)
        self.assertEqual(h.started, [("tenders.yml", {"mode": "inbox"}), ("clock.yml", {"do": "nothing"})])


if __name__ == "__main__":
    unittest.main()
