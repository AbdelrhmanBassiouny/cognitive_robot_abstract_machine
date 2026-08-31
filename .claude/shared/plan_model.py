"""
The parts of a plan's data model that more than one tool has to agree on.

Everything here is deliberately stdlib-only: a hook reads it, and so does the dashboard
build, which imports jinja2 and markdown of its own. The dependency runs one way only.
"""

from __future__ import annotations

from enum import StrEnum


class ItemStatus(StrEnum):
    """
    The statuses ``plan.yaml``'s ``status`` field accepts.

    Deliberately thin: everything about a pull request's actual GitHub state - open,
    draft, merged, its checks, its reviews - is never stored in the manifest. It is
    live-fetched and represented separately.
    """

    NOT_STARTED = "not_started"
    """
    Nothing has begun.
    """

    IN_PROGRESS = "in_progress"
    """
    The work is underway - what bootstrapping an item sets.
    """

    BLOCKED = "blocked"
    """
    Something outside the item has to move first.
    """

    DEFERRED = "deferred"
    """
    Deliberately parked rather than stuck.
    """

    DONE = "done"
    """
    Landed.
    """
