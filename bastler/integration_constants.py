"""
What a build is named, what it records, and the keys its documents carry.

Every document this tooling emits is keyed through :class:`ReportKey`, so a reader
parses one vocabulary rather than one per report.
"""

from __future__ import annotations

from enum import StrEnum

from bastler.git_commands import GitSetting

# %% who a rebuild runs as, and what it keeps between calls


ACTOR_VARIABLE = "GITHUB_ACTOR"
"""
Who a runner is acting as, which is who a rebuild's own merge commits are authored as.
"""

ACTOR_EMAIL_SUFFIX = "@users.noreply.github.com"
"""
The address GitHub gives an actor that has published none of its own.
"""

LOCALISATION_STATE_FILE = "integration-localisation.json"
"""
What a rebuild calls the document its localisation keeps between calls.
"""


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

CANDIDATE_TITLE_PREFIX = "Integration candidate:"
"""
Opens the title of the pull request a build is judged as.

Beside the branch names rather than beside the judging, because it is also how a reader
of the fork's pull requests tells a build being judged from somebody's work - and one
kind of candidate is opened against the same base as every ordinary branch.
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

    MISSING_PIPELINE = "missing_pipeline"
    """
    The pipeline's own files a build does not carry, which is why it was not published.
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

    MEASURED_OVER = "measured_over"
    """
    The heads a break was found between, which is the tree its block is about.
    """

    COMMIT = "commit"
    """
    What the fork had a branch pointing at when a break was measured over it.
    """

    READMITTED = "readmitted"
    """
    The branches a build carried although a label withholds them, because the tree
    their block was measured in is gone.
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

    RECORDED_BREAKS = "recorded_breaks"
    """
    Every branch a reproduction run had a break recorded against, and whether each break
    still reproduces.
    """

    TAKEN_DOWN = "taken_down"
    """
    The build branches a run deleted because nothing was judging them any more.
    """


BUILD_BRANCH_PATTERN = f"{POINTER_BRANCH}-[0-9]*"
"""
Matches every branch a build was assembled onto, and nothing a build did not.

The digit is what tells a build from a probe: both open with the pointer's own name and
a hyphen, and only a build follows it with the moment it was named at.
"""

BUILD_BRANCH_FILTER = f"{POINTER_BRANCH}-*"
"""
Matches a build's branch where a workflow says which branches an event is about.

Spelled apart from :data:`BUILD_BRANCH_PATTERN` because the two are read by different
things: git's own listing takes the character class that tells a build from a probe, and
a workflow's filter does not, so the pattern that narrows one silently matches nothing in
the other. Nothing is lost by the wider form here - a probe's tree is judged by the probe
workflow rather than by the one this filter is about.
"""

PROBE_BRANCH_PREFIX = f"{POINTER_BRANCH}-probe-"
"""
Opens the name of every tree a localisation publishes for CI to judge.

Its own prefix rather than a build's, so a probe is never mistaken for one: a build is
what the pointer moves to, and a probe exists to answer one question and be deleted.
"""
