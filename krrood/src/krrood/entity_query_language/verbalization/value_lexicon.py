from __future__ import annotations

import datetime
import enum

from typing_extensions import Any

__all__ = ["value_phrase"]


def value_phrase(value: Any) -> str:
    """
    Render a Python value as a human-readable string — the single value-lexicalisation point.

    * ``None`` → ``"nothing"`` (a genuine value-slot absence; a top-level ``== None`` comparison
      is rendered as an absence predicate, not via this function).
    * A bare ``type`` → its ``__name__`` (``Apple`` → ``"Apple"``).
    * A tuple of types → ``"A or B or C"``.
    * An ``enum`` member → its ``name`` (``OPTION_A`` rather than ``<TestEnum.OPTION_A: …>``).
    * A ``datetime`` with no time → ``"May 23, 2026"``; with a time → ``"May 23, 2026 at 14:30"``.
    * Anything else → ``repr(value)``.

    :param value: Python value from a literal node.
    :return: Human-readable string representation.

    >>> value_phrase(None)
    'nothing'
    >>> value_phrase(int)
    'int'
    >>> value_phrase((int, str))
    'int or str'
    >>> value_phrase(datetime.datetime(2026, 5, 23))
    'May 23, 2026'
    >>> value_phrase(datetime.datetime(2026, 5, 5))
    'May 5, 2026'
    >>> value_phrase(datetime.datetime(2026, 5, 23, 14, 30))
    'May 23, 2026 at 14:30'
    >>> value_phrase(42)
    '42'
    """
    if value is None:
        return "nothing"
    if isinstance(value, type):
        return value.__name__
    if isinstance(value, tuple) and all(
        isinstance(variable, type) for variable in value
    ):
        return " or ".join(variable.__name__ for variable in value)
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, datetime.datetime):
        # `value.day` (an int) gives the day with no leading zero portably -- strftime's "%-d" is a
        # glibc-only extension that raises ValueError on Windows.
        date_phrase = f"{value:%B} {value.day}, {value.year}"
        if value.time() == datetime.time.min:
            return date_phrase
        return f"{date_phrase} at {value:%H:%M}"
    return repr(value)
