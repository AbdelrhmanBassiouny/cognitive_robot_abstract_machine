"""
What a build's status means to whatever ran it.

Held apart from the report it is computed from, so a caller acting on the
status alone - a scheduled job with no model in it - imports nothing else.
"""

from __future__ import annotations

from enum import IntEnum


class IntegrationExitCode(IntEnum):
    """
    What this builder's exit status tells a caller.

    The first six match :class:`maintenance.MaintenanceExitCode` value for value and
    meaning, so a caller acting on both tools' statuses never has to remember which
    produced one.
    """

    SUCCESS = 0
    """
    Every tip is in the branch, and the suite passed or was not asked for.
    """

    USAGE = 2
    """
    No such command, or the wrong arguments.
    """

    REMOTES_UNRESOLVED = 4
    """
    The fork could not be identified from this checkout's remotes.
    """

    GIT_COMMAND_FAILED = 6
    """
    A git command the build depended on failed; nothing further was attempted.
    """

    CREDENTIAL_UNAVAILABLE = 8
    """
    No GitHub token is set, so the fork's open pull requests cannot be read.
    """

    GITHUB_REQUEST_FAILED = 9
    """
    The API refused a call this build depends on; its status and reason are on stderr.
    """

    TIP_LEFT_OUT = 10
    """The branch was built, but at least one tip is missing from it - a collision, or a
    merge that refused before it began. The build is still usable; it is not whole."""

    TESTS_FAILED = 11
    """
    The branch was built and the suite failed on it.

    This is what catches the failure per-branch checks structurally cannot: two branches that each pass
    alone, merge cleanly, and break together.
    """

    SUSPECT_REPLAY = 12
    """
    The suite failed on a branch carrying a machine-written resolution, replayed without
    review.

    Distinct from an ordinary red suite because the answer differs:
    report and stop, since re-resolving into the same failure is how a build thrashes.
    """

    CANDIDATE_STILL_RUNNING = 13
    """
    The candidate's checks have not finished, so there is nothing to act on yet.

    Its own status rather than a failure: a caller waiting for a verdict asks again, and one
    that read this as red would throw away a build nothing had judged.
    """

    CANDIDATE_FAILED = 14
    """
    The candidate's checks failed, so the build is not one to hand anybody.

    The branches it was made of are where the failure is.
    """

    @property
    def name_for_a_caller(self) -> str:
        """
        What this status means, in words rather than as a number to be looked up.

        Derived from the member itself, so a status can never end up carrying a name
        belonging to a different one.

        :return: The status's name, in the form a caller reads or matches on.
        """
        return self.name.lower().replace("_", "-")
