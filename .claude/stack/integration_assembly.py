"""
Assembling the branch: the upstream base, then each tip in a stated order.

A collision skips its tip and the build continues, because a build that halted on the
first one would leave nothing to work from.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from stack import (
    Branch,
    Configuration,
    Stack,
    resolve_ref,
)

from maintenance_git_commands import MaintenanceGitCommandRunner
from maintenance_restack_procedure import (
    DetachedCheckout,
    RestackWorktree,
)

from integration_constants import (
    POINTER_BRANCH,
    RERERE_SETTINGS,
    RESOLUTION_REPLAY_MARKER,
)
from integration_plans import PlanFilter
from integration_report import IntegrationReport
from integration_selection import select_for_build, tips_of
from integration_suite import run_tests
from integration_tips import (
    PullRequestStackTipOutcome,
    ReadmittedBranch,
    ResolutionProvenance,
    TipStatus,
)


@dataclass(frozen=True)
class IntegrationBuild:
    """
    One branch under assembly, and the tips merged into it so far.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner for the worktree the branch is assembled in, with replay turned on.
    """

    configuration: Configuration
    """
    The resolved configuration naming both remotes and the base.
    """

    provenance: ResolutionProvenance
    """
    Who wrote each recorded resolution, for reporting a replay by its author.
    """

    @property
    def base_reference(self) -> str:
        """:return: The upstream base every build starts from."""
        return (
            f"{self.configuration.upstream_remote}/{self.configuration.upstream_base}"
        )

    def reference_to(self, branch: str) -> str:
        """:param branch: A fork branch.
        :return: The fork's own copy of it, which is what a build merges - so a branch
            somebody moved mid-build is taken as published rather than as this checkout
            last saw it."""
        return resolve_ref(self.configuration, branch)

    def start(self, build_branch: str) -> None:
        """:param build_branch: The branch to assemble onto, at the upstream base."""
        self.git.checkout(build_branch, self.base_reference)

    def start_unnamed(self) -> None:
        """
        Begin an assembly nobody is meant to keep, at the upstream base.

        A probe exists to answer one question and be thrown away, so it is built on a
        detached head rather than a branch: a named one would outlive the answer and
        accumulate, one ref per question ever asked.
        """
        self.git.run("checkout", "--quiet", "--detach", self.base_reference)

    def merge(
        self, tip: Branch, already_included: list[str]
    ) -> PullRequestStackTipOutcome:
        """
        Merge one tip, or say why it was left out.

        :param tip: The tip to merge.
        :param already_included: The tips merged so far, oldest first.
        :return: What became of it.
        """
        result = self.git.merge(self.reference_to(tip.name))
        if result.succeeded:
            return PullRequestStackTipOutcome(
                branch=tip.name,
                pull_request_number=tip.pull_request_number,
                status=TipStatus.MERGED,
            )
        conflicting_paths = self.git.unmerged_paths()
        if not conflicting_paths and self._replayed_a_resolution(
            result.output, result.error_output
        ):
            return self._conclude_replay(tip, already_included)
        self.git.abandon(tip.strategy)
        if not conflicting_paths:
            return PullRequestStackTipOutcome(
                branch=tip.name,
                pull_request_number=tip.pull_request_number,
                status=TipStatus.INTEGRATION_FAILED,
                explanation=result.error_output,
            )
        return PullRequestStackTipOutcome(
            branch=tip.name,
            pull_request_number=tip.pull_request_number,
            status=TipStatus.SKIPPED,
            attributed_to=self._attribution_for(tip, already_included),
            conflicting_paths=conflicting_paths,
        )

    @staticmethod
    def _replayed_a_resolution(*streams: str) -> bool:
        """:param streams: What git said about the merge.
        :return: Whether it applied a resolution out of its cache."""
        return any(RESOLUTION_REPLAY_MARKER in stream for stream in streams)

    def _conclude_replay(
        self, tip: Branch, already_included: list[str]
    ) -> PullRequestStackTipOutcome:
        """
        Commit a merge whose conflicts the replay already resolved.

        :param tip: The tip being merged.
        :param already_included: The tips merged so far, oldest first.
        :return: The tip's outcome, reported as replayed rather than as clean.
        """
        self.git.conclude_merge().raise_if_failed()
        return PullRequestStackTipOutcome(
            branch=tip.name,
            pull_request_number=tip.pull_request_number,
            status=TipStatus.REPLAYED,
            attributed_to=self._attribution_for(tip, already_included),
            resolved_by=self.provenance.author_for(tip.name),
        )

    def _attribution_for(self, tip: Branch, already_included: list[str]) -> str:
        """
        Attribute a collision to the pair it is between.

        Probed with ``merge-tree`` rather than by merging, so identifying the partner
        never disturbs the branch under assembly. The most recently merged tip is asked
        first, since that is the one whose commits the failed merge just met.

        :param tip: The tip that conflicted.
        :param already_included: The tips merged so far, oldest first.
        :return: The branch it conflicts with, or the base when no sibling does.
        """
        for candidate in reversed(already_included):
            if not self.git.merges_cleanly(
                self.reference_to(candidate), self.reference_to(tip.name)
            ):
                return candidate
        return self.configuration.upstream_base


def build_integration(
    stack: Stack,
    git: MaintenanceGitCommandRunner,
    build_branch: str,
    provenance: ResolutionProvenance,
    test_command: str | None,
    plans: PlanFilter | None = None,
) -> IntegrationReport:
    """
    Assemble one integration branch and report what went into it.

    The assembly happens in a worktree of its own, which the invoking checkout lends its
    branch to through a :class:`maintenance.DetachedCheckout` and gets back with its own
    files still in place - a build is something a developer runs *while* working.

    :param stack: The derived stack, whose tips this merges.
    :param git: The runner naming the checkout to add the worktree to.
    :param build_branch: The branch to assemble onto.
    :param provenance: Who wrote each recorded resolution.
    :param test_command: The suite to run on the finished branch, or ``None`` to skip.
    :param plans: The plans this build was asked to carry, or ``None`` for all of them.
    :return: What the build contains and what it left out.
    """
    selection = select_for_build(stack, plans)
    tips = tips_of(stack, plans)
    with DetachedCheckout.of(git), RestackWorktree.added_to(git) as assembling:
        build = IntegrationBuild(
            git=dataclasses.replace(
                assembling, configuration_overrides=RERERE_SETTINGS
            ),
            configuration=stack.configuration,
            provenance=provenance,
        )
        build.start(build_branch)
        outcomes: list[PullRequestStackTipOutcome] = []
        included: list[str] = []
        for tip in tips:
            outcome = build.merge(tip, included)
            outcomes.append(outcome)
            if outcome.is_integrated:
                included.append(tip.name)
        git.run("branch", "--force", POINTER_BRANCH, build_branch)
        tests_passed = run_tests(test_command, build.git.working_directory)
    reached = branches_carried_by(stack, included)
    return IntegrationReport(
        build_branch=build_branch,
        base=stack.configuration.upstream_base,
        tips=tuple(outcomes),
        tests_passed=tests_passed,
        left_out=selection.left_out,
        readmitted=tuple(
            ReadmittedBranch(branch.name, branch.pull_request_number)
            for branch in selection.readmitted
            if branch.name in reached
        ),
    )


def branches_carried_by(stack: Stack, tips: Sequence[str]) -> set[str]:
    """
    Every branch in a build: each merged tip and everything it stands on in the stack.

    A tip contains its stack, so a branch below a merged tip reached the build under the
    tip's name.

    :param stack: The derived stack, whose parents are walked.
    :param tips: The tips that reached the build.
    :return: The names of every branch the build carries.
    """
    by_name = {branch.name: branch for branch in stack.branches}
    carried: set[str] = set()
    for tip in tips:
        name = tip
        while name in by_name and name not in carried:
            carried.add(name)
            name = by_name[name].parent
    return carried
