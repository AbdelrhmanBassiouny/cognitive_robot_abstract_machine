"""
When a branch that is already under upstream review may be pushed to.

A promoted branch is being read by somebody else, and a push moves the diff under
them and starts their checks again. So one is made only at night where they are, and
never twice in quick succession - the two conditions this module answers, and
nothing else.

It imports nothing else of this workflow's, so the configuration that holds a window
can depend on it rather than the other way round.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

# %% why a branch is left alone


class WaitReason(StrEnum):
    """
    Why a branch under upstream review is not pushed yet.

    Each names a situation a caller can act on - by waiting, or by asking for the push
    anyway - without reading the sentence that explains it.
    """

    DAYTIME = "daytime"
    """It is not night where the branch's reviewers are."""

    PUSHED_RECENTLY = "pushed-recently"
    """It moved less than one interval ago, so a reviewer may still be reading it."""


# %% what the window is read from


class PushWindowSetting(StrEnum):
    """
    The configuration keys a window is read from, in either configuration file.
    """

    NIGHT_BEGINS = "review_push_night_begins"
    """When the window opens, as ``HH:MM`` in its own zone."""

    NIGHT_ENDS = "review_push_night_ends"
    """When it closes again, as ``HH:MM`` in its own zone."""

    TIME_ZONE = "review_push_time_zone"
    """The zone both of those are read in, as an IANA name."""

    HOURS_BETWEEN_PUSHES = "review_push_hours_between_pushes"
    """How long a branch is left alone after a push, in hours."""


NIGHT_BEGINS = time(22, 0)
"""When the window opens for a checkout that configures nothing."""

NIGHT_ENDS = time(6, 0)
"""When it closes again for a checkout that configures nothing."""

TIME_ZONE = "Europe/Berlin"
"""The zone a checkout that configures nothing reads those in."""

HOURS_BETWEEN_PUSHES = 4
"""How long a checkout that configures nothing leaves a branch alone after a push."""


# %% the window itself


@dataclass(frozen=True)
class PushWindow:
    """
    The hours a branch under upstream review may be pushed in, and how often.

    Both halves have to hold: a window that is open says nothing about a branch that
    has just moved, and an interval that has elapsed says nothing about the hour.
    """

    night_begins: time
    """When the window opens, read in :attr:`time_zone`."""

    night_ends: time
    """When it closes again, read in :attr:`time_zone`. Earlier than
    :attr:`night_begins` for a window that spans midnight, which is the usual case."""

    time_zone: ZoneInfo
    """The zone the two ends are read in - the reviewers', not the runner's."""

    least_time_between_pushes: timedelta
    """How long a branch is left alone after a push, however open the window is."""

    @classmethod
    def from_values(cls, values: Mapping[str, object]) -> PushWindow:
        """
        Read a window out of the layered configuration.

        :param values: The configuration, with any key absent taking its default.
        :return: The window it describes.
        """
        return cls(
            night_begins=_a_time(
                values.get(PushWindowSetting.NIGHT_BEGINS), NIGHT_BEGINS
            ),
            night_ends=_a_time(values.get(PushWindowSetting.NIGHT_ENDS), NIGHT_ENDS),
            time_zone=ZoneInfo(str(values.get(PushWindowSetting.TIME_ZONE, TIME_ZONE))),
            least_time_between_pushes=timedelta(
                hours=float(
                    values.get(
                        PushWindowSetting.HOURS_BETWEEN_PUSHES, HOURS_BETWEEN_PUSHES
                    )
                )
            ),
        )

    def reasons_to_wait(
        self, last_pushed_at: datetime, now: datetime
    ) -> tuple[WaitReason, ...]:
        """
        Say why a branch under review is not to be pushed at this moment.

        :param last_pushed_at: When the branch last moved.
        :param now: The moment the pass is judged at.
        :return: Every reason to wait, empty when there is none.
        """
        reasons = []
        if not self._is_night(now):
            reasons.append(WaitReason.DAYTIME)
        if now - last_pushed_at < self.least_time_between_pushes:
            reasons.append(WaitReason.PUSHED_RECENTLY)
        return tuple(reasons)

    def _is_night(self, now: datetime) -> bool:
        """
        :param now: The moment to place.
        :return: Whether it falls in the window, which it does from the minute the
            window opens until the minute it closes.
        """
        local = now.astimezone(self.time_zone).time()
        if self.night_begins <= self.night_ends:
            return self.night_begins <= local < self.night_ends
        return local >= self.night_begins or local < self.night_ends

    def __str__(self) -> str:
        """:return: The window as one line, for the configuration a caller reads."""
        return (
            f"{self.night_begins:%H:%M}-{self.night_ends:%H:%M} {self.time_zone}, "
            f"at least {self.least_time_between_pushes} between pushes"
        )


def _a_time(configured: object, default: time) -> time:
    """:param configured: What the configuration carries, if anything.
    :param default: What an unconfigured checkout gets.
    :return: The time of day either names."""
    if configured is None:
        return default
    return time.fromisoformat(str(configured))
