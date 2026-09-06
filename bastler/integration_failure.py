"""
The failure a merge cannot see, and what is said about it.

Two branches can each pass their own checks, merge with no conflict, and not
work together. Per-branch CI cannot reach that: the failure exists only in a
tree neither branch is.
"""

from __future__ import annotations

import sys
import dataclasses
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from bastler.stack import (
    Branch,
    Configuration,
    LabelWrite,
    Stack,
)

from bastler.maintenance_board import (
    PullRequestField,
    get_session_link_in,
)
from bastler.maintenance_git_commands import MaintenanceGitCommandRunner
from bastler.maintenance_github import ForkPullRequests
from bastler.maintenance_restack_procedure import (
    DetachedCheckout,
    RestackWorktree,
)

from bastler.integration_assembly import IntegrationBuild
from bastler.integration_block_record import BlockRecords, MeasuredHead
from bastler.integration_constants import RERERE_SETTINGS, ReportKey
from bastler.integration_exit_codes import IntegrationExitCode
from bastler.integration_reproduction import REPRODUCTION_MARKER
from bastler.integration_selection import tips_of
from bastler.integration_suite import run_tests
from bastler.integration_tips import ResolutionProvenance

# %% the failure, and what its owner is told


FAILURE_COMMENT_PREFIX = "🔴 INTEGRATION - BREAKS ANOTHER BRANCH:"
"""Opens the comment an integration test failure is reported in.

Its own prefix rather than the restack's, because the two ask for different things: a
restack conflict is resolved by merging a moved parent, and this cannot be resolved on
this branch alone at all.
"""


@dataclass(frozen=True)
class IntegrationTestFailure:
    """Two tips that each pass their own suite, merge cleanly, and fail together.

    Nothing about the merge can find this: there was no conflict, so there is no pair to
    attribute and no preimage to key a recorded resolution on. It is found by adding tips
    one at a time until the suite turns, and narrowed by asking which earlier tip the
    culprit fails against on its own.
    """

    culprit: str
    """The tip whose arrival turned the suite red."""

    culprit_pull_request_number: int
    """The fork pull request that publishes it."""

    already_included: tuple[str, ...]
    """What was in the build when it turned, in merge order."""

    breaks_against: str | None
    """The single earlier tip the culprit fails against alone, or ``None`` when only the
    combination fails - which is a materially different thing to tell somebody."""

    measured_over: tuple[MeasuredHead, ...]
    """The heads the break was found between: the culprit's, then the partner's, or
    every tip that was in the build when no single partner reproduces it.

    This is the tree the block is about. A later build reads these against the fork to
    tell whether that tree still exists, which is what decides whether the block still
    holds.
    """

    @classmethod
    def measured(
        cls,
        git: MaintenanceGitCommandRunner,
        configuration: Configuration,
        culprit: Branch,
        already_included: tuple[str, ...],
        breaks_against: str | None,
        by_name: Mapping[str, Branch],
    ) -> IntegrationTestFailure:
        """Describe a localised failure together with the heads it was measured over.

        :param git: The runner the fork's heads are read through.
        :param configuration: The resolved configuration, naming the fork remote.
        :param culprit: The tip whose arrival turned the suite.
        :param already_included: What was in the build when it turned, in merge order.
        :param breaks_against: The single earlier tip it fails against alone, if any.
        :param by_name: Every tip, keyed by branch name.
        :return: The failure.
        """
        partners = (breaks_against,) if breaks_against is not None else already_included
        return cls(
            culprit=culprit.name,
            culprit_pull_request_number=culprit.pull_request_number,
            already_included=already_included,
            breaks_against=breaks_against,
            measured_over=tuple(
                MeasuredHead.of(git, configuration, by_name[name])
                for name in (culprit.name, *partners)
            ),
        )

    @classmethod
    def from_json(cls, document: dict[str, Any]) -> IntegrationTestFailure:
        """Read a localised failure back out of a report's document.

        :param document: The failure's own object, as
            :meth:`FailureLocationReport.as_json` wrote it.
        :return: The failure it describes.
        """
        return cls(
            culprit=document[ReportKey.CULPRIT],
            culprit_pull_request_number=document[ReportKey.CULPRIT_PULL_REQUEST_NUMBER],
            already_included=tuple(document[ReportKey.ALREADY_INCLUDED]),
            breaks_against=document.get(ReportKey.BREAKS_AGAINST),
            measured_over=tuple(
                MeasuredHead.from_json(head)
                for head in document[ReportKey.MEASURED_OVER]
            ),
        )

    def comment(self, session: str | None) -> str:
        """Write the comment telling a branch's owner that their branch breaks another.

        Names the branch it breaks, which is the half its owner cannot see: both pull
        requests pass their own checks, and the failure exists only in a tree neither of
        them is.

        :param session: The session named in the pull request's description, if any.
        :return: The comment body.
        """
        partner = (
            f"`{self.breaks_against}`"
            if self.breaks_against
            else "the combination of branches merged before it, no single one of which "
            "reproduces it alone"
        )
        addressed = (
            f"\n\n{session}"
            if session
            else "\n\nThis pull request's description names no session to address."
        )
        return (
            f"{FAILURE_COMMENT_PREFIX} `{self.culprit}` merges cleanly with "
            f"{partner} and the suite fails on the result.\n\n"
            f"Neither pull request is wrong on its own, and neither one's checks can "
            f"see this - the failure exists only in a tree neither branch is. Nothing "
            f"can be recorded for it either: a replay is keyed on a merge conflict's "
            f"preimage, and there is no conflict here, so every later build carries the "
            f"failure until one of the two branches changes.\n\n"
            f"This branch is labelled `integration-conflict` so later passes withhold "
            f"it rather than promoting it. The heads the break was measured over are "
            f"recorded with the block; once this branch or one it was measured against "
            f"has moved on from them, the next build carries this branch again, and its "
            f"suite passing is what lifts the label. A test marked "
            f"`@pytest.mark.{REPRODUCTION_MARKER}('{self.culprit}')` pushed to this "
            f"branch lifts it sooner, the moment it passes.{addressed}"
        )

    def block_the_branch_that_causes_it(
        self,
        configuration: Configuration,
        fork: ForkPullRequests,
        records: BlockRecords,
    ) -> BlockedBranchReport:
        """Label the branch that breaks another, and tell its owner why.

        The tree the break was measured in is recorded first: a label without it is a
        block nothing can ever tell has gone stale, and a record without the label is
        inert.

        :param configuration: The resolved configuration, naming the label to apply.
        :param fork: The fork to label and comment on.
        :param records: What the fork has recorded about its blocks, which this joins.
        :return: What was written where.
        """
        records.record(self)
        number = self.culprit_pull_request_number
        pull_request = fork.pull_request(number)
        body = PullRequestField.BODY.read(pull_request, number)
        fork.replace_labels(
            number,
            LabelWrite.replacing(
                PullRequestField.LABELS.read(pull_request, number),
                added=[configuration.integration_conflict_label],
            ).labels,
        )
        comment = self.comment(get_session_link_in(body))
        fork.add_comment(number, comment)
        return BlockedBranchReport(
            blocked=self.culprit,
            pull_request_number=number,
            breaks_against=self.breaks_against,
            label=configuration.integration_conflict_label,
            comment=comment,
        )


@dataclass(frozen=True)
class BlockedBranchReport:
    """What blocking one branch wrote, and where."""

    blocked: str
    """The branch that was labelled."""

    pull_request_number: int
    """The fork pull request that publishes it."""

    breaks_against: str | None
    """The earlier tip it fails against alone, or ``None`` when only the combination
    fails."""

    label: str
    """The label applied to hold it out of promotion."""

    comment: str
    """What was said on its pull request."""

    def as_json(self) -> str:
        """:return: The block as one machine-readable document."""
        return json.dumps(
            {
                ReportKey.BLOCKED: self.blocked,
                ReportKey.PULL_REQUEST_NUMBER: self.pull_request_number,
                ReportKey.BREAKS_AGAINST: self.breaks_against,
                ReportKey.LABEL: self.label,
                ReportKey.COMMENT: self.comment,
            },
            indent=2,
        )

    def as_line(self) -> str:
        """:return: The block as the one tab-separated line a shell caller reads."""
        return f"{self.blocked}\tblocked\t{self.label}"


# %% finding which pair it is about


@dataclass(frozen=True)
class FailureLocationReport:
    """What one search for the tip that turned the suite found."""

    build_branch: str
    """The branch the search assembled onto."""

    base: str
    """The upstream base it started from."""

    tips_tested: tuple[str, ...] = ()
    """The tips that reached the build and had the suite run over them, in order."""

    integration_test_failure: IntegrationTestFailure | None = None
    """The failure, or ``None`` when every prefix of the build passed."""

    @property
    def exit_code(self) -> IntegrationExitCode:
        """:return: The process exit code, which reports a localised failure the same way
        the build that failed reported it."""
        if self.integration_test_failure is None:
            return IntegrationExitCode.SUCCESS
        return IntegrationExitCode.TESTS_FAILED

    def as_json(self) -> str:
        """:return: The search as one machine-readable document, led by its status."""
        return json.dumps(
            {
                ReportKey.STATUS: self.exit_code.name_for_a_caller,
                ReportKey.EXIT_CODE: int(self.exit_code),
                **asdict(self),
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> FailureLocationReport:
        """Read a search back out of the document it was written to.

        :param text: A document :meth:`as_json` wrote.
        :return: The search it describes.
        """
        document = json.loads(text)
        failure = document.get(ReportKey.INTEGRATION_TEST_FAILURE)
        return cls(
            build_branch=document[ReportKey.BUILD_BRANCH],
            base=document[ReportKey.BASE],
            tips_tested=tuple(document[ReportKey.TIPS_TESTED]),
            integration_test_failure=(
                None if failure is None else IntegrationTestFailure.from_json(failure)
            ),
        )


@dataclass(frozen=True)
class FailureLocation:
    """The search for the tip whose arrival breaks a build that merged cleanly.

    Assembles the same tips in the same order as :func:`build_integration` and runs the
    suite after each one that reaches the build, so what it localises describes the build
    that failed rather than some other ordering of it. Stops at the first tip that turns
    the suite, then narrows to the earlier tip that alone reproduces it.

    Slow by construction - one suite run per tip, plus one per candidate while narrowing.
    It is a diagnosis, not part of a build.
    """

    stack: Stack
    """The derived stack, whose tips this merges."""

    git: MaintenanceGitCommandRunner
    """The runner naming the checkout to add the worktree to."""

    build_branch: str
    """The branch to assemble onto."""

    provenance: ResolutionProvenance
    """Who wrote each recorded resolution."""

    test_command: str
    """The suite that decides whether a build works."""

    def find(self) -> FailureLocationReport:
        """:return: What the search localised."""
        tips = tips_of(self.stack)
        by_name = {tip.name: tip for tip in tips}
        with (
            DetachedCheckout.of(self.git),
            RestackWorktree.added_to(self.git) as assembling,
        ):
            build = IntegrationBuild(
                git=dataclasses.replace(
                    assembling, configuration_overrides=RERERE_SETTINGS
                ),
                configuration=self.stack.configuration,
                provenance=self.provenance,
            )
            build.start(self.build_branch)
            included: list[str] = []
            for tip in tips:
                if not build.merge(tip, included).is_integrated:
                    continue
                if self._suite_passes(build):
                    included.append(tip.name)
                    continue
                return self._report(
                    tips_tested=tuple(included) + (tip.name,),
                    failure=IntegrationTestFailure.measured(
                        git=self.git,
                        configuration=self.stack.configuration,
                        culprit=tip,
                        already_included=tuple(included),
                        breaks_against=self._narrow(build, tip, included, by_name),
                        by_name=by_name,
                    ),
                )
            return self._report(tips_tested=tuple(included))

    def _report(
        self,
        tips_tested: tuple[str, ...],
        failure: IntegrationTestFailure | None = None,
    ) -> FailureLocationReport:
        """:param tips_tested: The tips the suite was run over, in order.
        :param failure: What was localised, when anything was.
        :return: The search's report."""
        return FailureLocationReport(
            build_branch=self.build_branch,
            base=self.stack.configuration.upstream_base,
            tips_tested=tips_tested,
            integration_test_failure=failure,
        )

    def _narrow(
        self,
        build: IntegrationBuild,
        culprit: Branch,
        already_included: list[str],
        by_name: dict[str, Branch],
    ) -> str | None:
        """Narrow a failure to the one earlier tip that reproduces it on its own.

        Naming everything that was in the build is not actionable when only one of them
        is involved. Asked most-recent-first, the same way a merge conflict's partner is.

        :param build: The build under assembly, whose worktree the probes run in.
        :param culprit: The tip whose arrival turned the suite.
        :param already_included: The tips in the build when it turned, in merge order.
        :param by_name: Every tip, keyed by branch name.
        :return: The tip it fails against alone, or ``None`` when only the combination
            does.
        """
        for candidate in reversed(already_included):
            build.start_unnamed()
            if not build.merge(by_name[candidate], []).is_integrated:
                continue
            if not build.merge(culprit, [candidate]).is_integrated:
                continue
            if not self._suite_passes(build):
                return candidate
        return None

    def _suite_passes(self, build: IntegrationBuild) -> bool | None:
        """:param build: The assembly to run the suite against.
        :return: Whether it passed."""
        return run_tests(self.test_command, build.git.working_directory)


def print_failure_location(report: FailureLocationReport) -> None:
    """:param report: The localised failure to summarise."""
    localised = report.integration_test_failure
    if localised is None:
        print(
            f"{report.build_branch}\tno-failure-localised\t{len(report.tips_tested)} tip(s)"
        )
        return
    against = localised.breaks_against or "the combination before it"
    print(f"{localised.culprit}\tbreaks-against\t{against}")
    print(
        f"{localised.culprit}\twas-added-to\t{','.join(localised.already_included)}",
        file=sys.stderr,
    )
