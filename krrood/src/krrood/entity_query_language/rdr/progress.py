"""
An optional :class:`ProgressReporter` abstraction for RDR fitting, and an IPython
implementation backed by :mod:`tqdm`.

The ProgressReporter is obtained from an ``ExpertInterface`` via the optional factory method
:meth:`ExpertInterface.make_progress_reporter`.  Interfaces that don't want progress
simply inherit the default (returns ``None``), and ``fit()`` calls its lifecycle methods
only when a reporter is available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import List, Optional, Tuple, Dict


class ProgressReporter(ABC):
    """Reports batch progress during RDR fitting.

    Lifecycle::

        start(total, description) -> update() * N
            -> [reset(new_total) -> update() * M] -> finish()
    """

    @abstractmethod
    def start(self, total: int, description: str = "") -> None:
        """Begin tracking progress toward *total* items.

        :param total: The number of items to track.
        :param description: A label shown alongside the bar.
        """

    @abstractmethod
    def update(self, n: int = 1) -> None:
        """Advance the counter by *n* completed items.

        :param n: How many items to advance by (default 1).
        """

    @abstractmethod
    def reset(self, total: int) -> None:
        """Reset the counter for a new pass with an updated *total*.

        :param total: The new item total for the next pass.
        """

    @abstractmethod
    def finish(self) -> None:
        """Mark progress complete and clean up the display."""


@dataclass
class IPythonProgressBar(ProgressReporter):
    """A colourful terminal progress bar for use with an IPythonInterface expert.

    Wraps a :class:`tqdm.tqdm` progress bar whose colour is green for visual
    consistency with the RDR interface's :class:`~krrood.entity_query_language.rdr.interactive.Palette`
    ``good`` colour.

    When *use_color* is ``False`` the bar is rendered in plain ASCII.
    """

    use_color: bool = True
    """Whether the bar uses ANSI colour (green) or plain ASCII."""

    _progress_bar: Optional["tqdm.tqdm"] = field(  # type: ignore[name-defined]
        default=None, init=False, repr=False
    )
    """The wrapped :class:`tqdm.tqdm` instance, or ``None`` before :meth:`start`."""

    def start(self, total: int, description: str = "") -> None:
        self._progress_bar = _make_tqdm(total, description, self.use_color)

    def update(self, n: int = 1) -> None:
        if self._progress_bar is not None:
            self._progress_bar.update(n)

    def reset(self, total: int) -> None:
        if self._progress_bar is not None:
            self._progress_bar.reset(total)

    def finish(self) -> None:
        if self._progress_bar is not None:
            self._progress_bar.close()
            self._progress_bar = None


def _make_tqdm(
    total: int, description: str, use_color: bool
) -> "tqdm.tqdm":  # type: ignore[name-defined]
    import tqdm  # Lazy import: tqdm is only needed when a bar is actually created.

    return tqdm.tqdm(
        total=total,
        desc=description,
        colour="green" if use_color else None,
        ascii=not use_color,
        unit="case",
        leave=True,
        dynamic_ncols=True,
    )


class SpyProgressReporter(ProgressReporter):
    """A test double that records calls to :class:`ProgressReporter` without displaying anything.

    Useful for verifying that the fitting loop calls the expected lifecycle methods in the
    right order.
    """

    def __init__(self) -> None:
        self.events: List[Tuple[str, Tuple, Dict]] = []
        """The ordered sequence of recorded ``(method_name, args, kwargs)`` calls."""

    def start(self, total: int, description: str = "") -> None:
        self.events.append(("start", (total,), {"description": description}))

    def update(self, n: int = 1) -> None:
        self.events.append(("update", (n,), {}))

    def reset(self, total: int) -> None:
        self.events.append(("reset", (total,), {}))

    def finish(self) -> None:
        self.events.append(("finish", (), {}))
