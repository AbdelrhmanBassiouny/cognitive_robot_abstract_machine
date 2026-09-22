"""
Tests for the window a branch under upstream review may be pushed in.

The window is pure - it is handed two instants and says why it is closed - so
everything about it is asserted here, against instants written out in full rather
than derived from the clock the tests run on.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from basstler.push_window import PushWindow, PushWindowSetting, WaitReason

BERLIN = ZoneInfo("Europe/Berlin")
"""
The zone the committed defaults name, which every instant here is written in.
"""


def a_window(
    night_begins: time = time(22, 0),
    night_ends: time = time(6, 0),
    least_time_between_pushes: timedelta = timedelta(hours=4),
) -> PushWindow:
    """
    :param night_begins: When the window opens, in its own zone.
    :param night_ends: When it closes again.
    :param least_time_between_pushes: How long a branch is left alone after a push.
    :return: A window over Berlin, so a test names only what it is about.
    """
    return PushWindow(
        night_begins=night_begins,
        night_ends=night_ends,
        time_zone=BERLIN,
        least_time_between_pushes=least_time_between_pushes,
    )


def berlin(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """
    :param year: The year in Berlin.
    :param month: The month in Berlin.
    :param day: The day in Berlin.
    :param hour: The hour in Berlin.
    :param minute: The minute in Berlin.
    :return: That local moment as an instant.
    """
    return datetime(year, month, day, hour, minute, tzinfo=BERLIN)


# %% when the window is open


def test_a_branch_left_alone_all_day_is_pushed_at_night():
    assert (
        a_window().reasons_to_wait(
            last_pushed_at=berlin(2026, 1, 14, 9),
            now=berlin(2026, 1, 14, 23),
        )
        == ()
    )


def test_the_window_is_open_after_midnight_as_well_as_before_it():
    """
    The window spans midnight, so the hours after it are the same night as the hours
    before - not a day the window never opened on.
    """
    assert (
        a_window().reasons_to_wait(
            last_pushed_at=berlin(2026, 1, 14, 9),
            now=berlin(2026, 1, 15, 2),
        )
        == ()
    )


# %% why it is closed


def test_a_branch_is_left_alone_while_its_reviewers_are_awake():
    assert a_window().reasons_to_wait(
        last_pushed_at=berlin(2026, 1, 14, 3),
        now=berlin(2026, 1, 14, 14),
    ) == (WaitReason.DAYTIME,)


def test_a_branch_pushed_within_the_interval_is_left_alone_though_it_is_night():
    assert a_window().reasons_to_wait(
        last_pushed_at=berlin(2026, 1, 14, 23),
        now=berlin(2026, 1, 15, 1),
    ) == (WaitReason.PUSHED_RECENTLY,)


def test_both_reasons_are_reported_when_both_hold():
    assert a_window().reasons_to_wait(
        last_pushed_at=berlin(2026, 1, 14, 13),
        now=berlin(2026, 1, 14, 14),
    ) == (WaitReason.DAYTIME, WaitReason.PUSHED_RECENTLY)


@pytest.mark.parametrize(
    "hour, expected",
    [
        (21, (WaitReason.DAYTIME,)),
        (22, ()),
        (5, ()),
        (6, (WaitReason.DAYTIME,)),
    ],
)
def test_the_window_includes_the_hour_it_opens_and_excludes_the_one_it_closes(
    hour: int, expected: tuple[WaitReason, ...]
):
    """
    A window carrying both its ends would be open for a minute longer than the one
    carrying neither, so which end is which is asserted rather than left to read off the
    comparison.
    """
    now = berlin(2026, 1, 15, hour)
    assert (
        a_window().reasons_to_wait(last_pushed_at=now - timedelta(days=1), now=now)
        == expected
    )


# %% the zone is the reviewers', not the runner's


@pytest.mark.parametrize("month", [1, 7])
def test_night_begins_at_the_same_local_hour_whichever_side_of_the_clock_change(
    month: int,
):
    """
    A runner keeps UTC, and Berlin is an hour further from it in summer.

    Reading the window in its own zone is what makes 22:00 mean 22:00 in both halves of
    the year.
    """
    an_hour_before_night = berlin(2026, month, 15, 21).astimezone(timezone.utc)
    the_hour_night_begins = berlin(2026, month, 15, 22).astimezone(timezone.utc)
    window = a_window()
    a_day_earlier = timedelta(days=1)

    assert window.reasons_to_wait(
        last_pushed_at=an_hour_before_night - a_day_earlier, now=an_hour_before_night
    ) == (WaitReason.DAYTIME,)
    assert (
        window.reasons_to_wait(
            last_pushed_at=the_hour_night_begins - a_day_earlier,
            now=the_hour_night_begins,
        )
        == ()
    )


# %% reading it out of the configuration


def test_an_unconfigured_checkout_gets_the_committed_defaults():
    window = PushWindow.from_values({})

    assert window.night_begins == time(22, 0)
    assert window.night_ends == time(6, 0)
    assert window.time_zone == BERLIN
    assert window.least_time_between_pushes == timedelta(hours=4)


def test_every_setting_can_be_overridden():
    window = PushWindow.from_values(
        {
            PushWindowSetting.NIGHT_BEGINS: "23:30",
            PushWindowSetting.NIGHT_ENDS: "05:15",
            PushWindowSetting.TIME_ZONE: "America/New_York",
            PushWindowSetting.HOURS_BETWEEN_PUSHES: 2,
        }
    )

    assert window.night_begins == time(23, 30)
    assert window.night_ends == time(5, 15)
    assert window.time_zone == ZoneInfo("America/New_York")
    assert window.least_time_between_pushes == timedelta(hours=2)


def test_a_fractional_interval_is_read_as_written():
    """
    The interval is hours because that is how it is discussed, not because it has to be
    whole ones.
    """
    window = PushWindow.from_values({PushWindowSetting.HOURS_BETWEEN_PUSHES: 0.5})

    assert window.least_time_between_pushes == timedelta(minutes=30)
