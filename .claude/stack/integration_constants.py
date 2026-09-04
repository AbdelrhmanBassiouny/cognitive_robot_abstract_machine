"""
What a build is named, what it records, and the keys its documents carry.

Every document this tooling emits is keyed through :class:`ReportKey`, so a reader
parses one vocabulary rather than one per report.
"""

from __future__ import annotations

from enum import StrEnum

from git_commands import GitSetting

# %% what a build is named and where it lands


POINTER_BRANCH = "integration"
"""
The branch a developer checks out, moved to each build that finishes.

Builds are named ``integration-<timestamp>`` with a hyphen rather than a slash: git
stores refs as files, so ``refs/heads/integration/<timestamp>`` cannot exist while
``refs/heads/integration`` does. The obvious naming is the one git refuses.
"""

BUILD_NAME_FORMAT = "%Y%m%d-%H%M%S"
"""
How a build's moment is spelled in its branch name.
"""

RERERE_SETTINGS = (
    GitSetting("rerere.enabled", "true"),
    GitSetting("rerere.autoupdate", "true"),
)
"""
Replay of previously recorded conflict resolutions, turned on for the build alone.

Passed per command rather than written into the repository's configuration, which
belongs to whoever invoked the build rather than to the build.
"""

RESOLUTION_REPLAY_MARKER = "using previous resolution"
"""
What git says when it resolves a conflict from its recorded cache.

Worth stating why this is read at all rather than inferred from the merge's shape: a
replayed merge *fails*, exactly like a merge that never began, and leaves no unmerged
paths behind because the replay has already staged them. The two are indistinguishable
without this.
"""

PROVENANCE_FILENAME = "resolution-authors.json"
"""
Where the authorship of recorded resolutions is kept, beside the cache it describes.
"""

# %% the keys every document carries


class ReportKey(StrEnum):
    """
    The field names a report's machine-readable document is read by.

    Most mirror a field of the report dataclasses, which are written out with
    ``asdict``; the rest name what a single command emits beside them.
    """

    STATUS = "status"
    """
    What the run concluded, in the words its exit status carries.
    """

    EXIT_CODE = "exit_code"
    """
    The same conclusion as the number the process exits with.
    """

    BUILD_BRANCH = "build_branch"
    """
    The branch a run assembled onto.
    """

    BASE = "base"
    """
    The upstream base it started from.
    """

    TIPS = "tips"
    """
    What became of each tip the build tried to integrate.
    """

    TESTS_PASSED = "tests_passed"
    """
    Whether the suite passed, absent when it was not run.
    """

    LEFT_OUT = "left_out"
    """
    The branches a build never tried to merge, each saying which rule left it out.
    """

    CANDIDATE = "candidate"
    """
    The pull request opened so a build's checks run.
    """

    HEAD = "head"
    """
    The commit a candidate's checks are reported against.
    """

    VERDICT = "verdict"
    """
    What a candidate's checks amount to.
    """

    FAILED_CHECKS = "failed_checks"
    """
    Every finished check of a candidate that failed, by name.
    """

    PUBLISHED = "published"
    """
    Whether the base branch was moved to the build being judged.
    """

    TIPS_TESTED = "tips_tested"
    """
    The tips a search ran the suite over, in order.
    """

    INTEGRATION_TEST_FAILURE = "integration_test_failure"
    """
    The pair a localised failure was narrowed to, absent when nothing was localised.
    """

    BRANCH = "branch"
    """
    Which branch an entry is about.
    """

    PULL_REQUEST_NUMBER = "pull_request_number"
    """
    The fork pull request that publishes the branch an entry is about.
    """

    ATTRIBUTED_TO = "attributed_to"
    """
    The other branch an outcome is about, absent when there is none.
    """

    CONFLICTING_PATHS = "conflicting_paths"
    """
    The paths a conflict was on.
    """

    RESOLVED_BY = "resolved_by"
    """
    Who wrote the resolution a replay reused.
    """

    EXPLANATION = "explanation"
    """
    What git said about a refusal that is the build's own to fix.
    """

    CULPRIT = "culprit"
    """
    The tip whose arrival turned the suite.
    """

    CULPRIT_PULL_REQUEST_NUMBER = "culprit_pull_request_number"
    """
    The fork pull request that publishes the culprit.
    """

    ALREADY_INCLUDED = "already_included"
    """
    What was in the build when the suite turned, in merge order.
    """

    BREAKS_AGAINST = "breaks_against"
    """
    The earlier tip the culprit fails against alone.
    """

    BLOCKED = "blocked"
    """
    The branch a block-branch run labelled.
    """

    LABEL = "label"
    """
    The label applied to hold it out of promotion.
    """

    COMMENT = "comment"
    """
    What was said on its pull request.
    """

    WORKTREE = "worktree"
    """
    Where a staged collision is live, for a resolution to be written into.
    """

    CLEARED = "cleared"
    """
    The branches whose block a clearing run lifted.
    """
