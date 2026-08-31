"""
What the integration builder's exit statuses mean.

Their own module because the rebuild that composes the commands decides on these
statuses, and a command and its composition cannot each import the other.
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

    BASE_NOT_PREPARED = 7
    """
    The fork's base could not be brought onto the upstream, so there is nothing current
    to assemble against.

    Aligned with the maintenance pass's own status for a base that would not fast-
    forward, which is what a rebuild inherits it from.
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

    PROBES_STILL_RUNNING = 15
    """
    A localisation's probes have not all answered, so the round cannot be read yet.

    Its own status rather than a failure, for the same reason a candidate's is: the
    caller asks again, and one that read this as an answer would act on a round nothing
    had judged.
    """

    NO_LIBRARY_CHECK_FAILED = 16
    """
    Nothing the candidate failed on names a library, so re-running one localises
    nothing.

    Said plainly rather than probed anyway: a tooling check is already localised
    by the local search, faster and before a build is pushed, and a check that is a
    property of one tree is not about a combination at all.
    """

    CANDIDATE_UNCHECKED = 17
    """
    No check was ever reported against a candidate a whole cycle old, so none is coming.

    Told apart from a matrix that is merely slow because what a reader has to look at is
    different: whatever should have started a run - the trigger, or the credential the
    candidate was opened with - rather than the checks themselves. A candidate reads as
    unchecked for as long as :class:`~integration_verdict.CandidateCheckTiming` records
    whatever happens, so this is only ever said of one a later run inherited.
    """

    NO_CANDIDATE_OPEN = 18
    """
    Nothing is being judged, so there is a build to assemble rather than one to settle.

    Its own status rather than an empty document, so a caller decides on the exit status
    it decides everything else on.
    """

    NO_RECORDED_PASS = 19
    """
    Nothing has been seen to pass over this build's tree, so it has to be judged.

    The ordinary answer rather than a fault: a build carrying a branch that moved is a
    tree nobody has checked, which is the whole reason a rebuild runs.
    """

    PIPELINE_WOULD_BE_REMOVED = 20
    """
    The build is one nothing could rebuild from, so it was not published.

    Publishing moves the fork's default branch, and a schedule registers from the
    default branch - so a build carrying no rebuild of its own would take the schedule
    with it and leave nothing able to publish a later build. Told apart from a failed
    candidate because the build is not what is wrong: its checks passed, and what is
    missing is the branches the pipeline lives on.
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
