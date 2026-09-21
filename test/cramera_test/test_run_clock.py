"""
Tests for the clock the viewer's timeline measures a run along.

Time is handed in rather than waited for, so a pause of an hour costs nothing to test.
"""

from __future__ import annotations

import threading

import pytest

from cramera.live.run_clock import RunClock, RunClockReading

from .dataset.wound_clock import WoundClock


@pytest.fixture()
def run_time() -> WoundClock:
    return WoundClock()


@pytest.fixture()
def clock(run_time) -> RunClock:
    return RunClock(monotonic_seconds=run_time.read)


# %% a run nobody interferes with
class TestAClockLeftRunning:
    def test_a_fresh_clock_reads_zero(self, clock):
        assert clock.elapsed_seconds() == 0.0

    def test_it_reads_exactly_the_time_that_has_passed(self, clock, run_time):
        run_time.advance(12.5)

        assert clock.elapsed_seconds() == 12.5

    def test_a_fresh_clock_is_running(self, clock):
        assert clock.reading().running is True


# %% pausing
class TestAPausedClock:
    def test_it_stops_where_it_stood(self, clock, run_time):
        run_time.advance(3.0)

        clock.pause()
        run_time.advance(60.0)

        assert clock.elapsed_seconds() == 3.0

    def test_it_says_it_is_no_longer_running(self, clock):
        clock.pause()

        assert clock.reading().running is False

    def test_pausing_a_paused_clock_leaves_the_first_pause_standing(
        self, clock, run_time
    ):
        """
        A second pause that re-stamped when it stopped would swallow the wait between.
        """
        run_time.advance(3.0)
        clock.pause()

        run_time.advance(60.0)
        clock.pause()
        clock.resume()
        run_time.advance(1.0)

        assert clock.elapsed_seconds() == 4.0


# %% resuming
class TestAResumedClock:
    def test_it_carries_on_without_counting_the_pause(self, clock, run_time):
        run_time.advance(3.0)
        clock.pause()
        run_time.advance(60.0)

        clock.resume()
        run_time.advance(2.0)

        assert clock.elapsed_seconds() == 5.0

    def test_it_says_it_is_running_again(self, clock):
        clock.pause()

        clock.resume()

        assert clock.reading().running is True

    def test_resuming_a_running_clock_changes_nothing(self, clock, run_time):
        run_time.advance(3.0)

        clock.resume()

        assert clock.elapsed_seconds() == 3.0


# %% restarting
class TestARestartedClock:
    def test_it_reads_zero_again(self, clock, run_time):
        run_time.advance(30.0)

        clock.restart()

        assert clock.elapsed_seconds() == 0.0

    def test_a_paused_clock_restarts_running(self, clock, run_time):
        """
        A restart is a run beginning, and a beginning run is going.
        """
        clock.pause()

        clock.restart()

        assert clock.reading().running is True

    def test_the_pauses_of_the_previous_run_are_forgotten(self, clock, run_time):
        clock.pause()
        run_time.advance(60.0)
        clock.resume()

        clock.restart()
        run_time.advance(4.0)

        assert clock.elapsed_seconds() == 4.0


# %% the wire shape
class TestTheReadingOnTheWire:
    def test_the_payload_names_exactly_the_readings_own_fields(self):
        assert set(RunClockReading(elapsed=1.0, running=True).to_payload()) == {
            "elapsed",
            "running",
        }

    def test_the_payload_carries_the_reading(self):
        payload = RunClockReading(elapsed=2.5, running=False).to_payload()

        assert payload == {"elapsed": 2.5, "running": False}


class TestReadingWhileTheRunDrivesIt:
    def test_every_pause_is_counted_once_however_often_it_is_read(
        self, clock, run_time
    ):
        """
        The timeline reads on an HTTP thread while the run pauses and resumes on its
        own, so neither may lose or double-count the other's work.
        """
        cycles = 200
        stop_reading = threading.Event()

        def keep_reading():
            while not stop_reading.is_set():
                clock.reading()

        reader = threading.Thread(target=keep_reading)
        reader.start()
        try:
            for _ in range(cycles):
                clock.pause()
                run_time.advance(1.0)
                clock.resume()
        finally:
            stop_reading.set()
            reader.join()

        assert clock.elapsed_seconds() == 0.0
