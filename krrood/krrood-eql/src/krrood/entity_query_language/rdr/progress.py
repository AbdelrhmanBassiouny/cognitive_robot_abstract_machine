"""
An optional :class:`ProgressReporter` for RDR fitting, and a :mod:`tqdm`-backed
implementation for IPython.

An interface obtains one from :meth:`ExpertInterface.make_progress_reporter`, which
returns ``None`` when it wants no progress output.
"""

from __future__ import annotations

import tqdm
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import List, Tuple, Dict


class ProgressReporter(ABC):
    """
    Reports batch progress during RDR fitting.

    Lifecycle::

        start(total, description) -> update() * N
            -> [reset(new_total) -> update() * M] -> finish()
    """

    @abstractmethod
    def start(self, *, total: int, description: str = "") -> None:
        """
        Begin tracking progress toward *total* items.

        :param total: The number of items to track.
        :param description: A label shown alongside the bar.
        """

    @abstractmethod
    def update(self, *, n: int = 1) -> None:
        """
        Advance the counter by *n* completed items.

        :param n: How many items to advance by (default 1).
        """

    @abstractmethod
    def reset(self, *, total: int) -> None:
        """
        Reset the counter for a new pass with an updated *total*.

        :param total: The new item total for the next pass.
        """

    @abstractmethod
    def finish(self) -> None:
        """
        Mark progress complete and clean up the display.
        """


@dataclass(kw_only=True)
class IPythonProgressBar(ProgressReporter):
    """
    A terminal progress bar, green when coloured and plain ASCII otherwise, backed by
    :class:`tqdm.tqdm`.
    """

    use_color: bool = True
    """
    Whether the bar uses ANSI colour (green) or plain ASCII.
    """

    _progress_bar: tqdm.tqdm | None = field(default=None, init=False, repr=False)
    """
    The wrapped :class:`tqdm.tqdm` instance, or ``None`` before :meth:`start`.
    """

    def start(self, *, total: int, description: str = "") -> None:
        self._progress_bar = _make_tqdm(total, description, self.use_color)

    def update(self, *, n: int = 1) -> None:
        if self._progress_bar is not None:
            self._progress_bar.update(n)

    def reset(self, *, total: int) -> None:
        if self._progress_bar is not None:
            self._progress_bar.reset(total)

    def finish(self) -> None:
        if self._progress_bar is not None:
            self._progress_bar.close()
            self._progress_bar = None


def _make_tqdm(total: int, description: str, use_color: bool) -> tqdm.tqdm:
    """
    :param total: The number of cases the bar counts up to.
    :param description: The label shown beside the bar.
    :param use_color: Whether the bar is green rather than plain ASCII.
    :return: A new progress bar.
    """
    return tqdm.tqdm(
        total=total,
        desc=description,
        colour="green" if use_color else None,
        ascii=not use_color,
        unit="case",
        leave=True,
        dynamic_ncols=True,
    )


@dataclass(kw_only=True)
class RecordedCall:
    """
    One lifecycle call captured by :class:`SpyProgressReporter`.
    """

    method_name: str
    """
    The name of the :class:`ProgressReporter` method that was called.
    """

    kwargs: Dict
    """
    The keyword arguments the method was called with.
    """


@dataclass(kw_only=True)
class SpyProgressReporter(ProgressReporter):
    """
    A test double that records calls to :class:`ProgressReporter` without displaying
    anything.

    Useful for verifying that the fitting loop calls the expected lifecycle methods in
    the right order.
    """

    events: List[RecordedCall] = field(init=False, default_factory=list)
    """
    The ordered sequence of recorded lifecycle calls.
    """

    def start(self, *, total: int, description: str = "") -> None:
        self.events.append(
            RecordedCall(
                method_name="start",
                kwargs={"total": total, "description": description},
            )
        )

    def update(self, *, n: int = 1) -> None:
        self.events.append(RecordedCall(method_name="update", kwargs={"n": n}))

    def reset(self, *, total: int) -> None:
        self.events.append(RecordedCall(method_name="reset", kwargs={"total": total}))

    def finish(self) -> None:
        self.events.append(RecordedCall(method_name="finish", kwargs={}))
