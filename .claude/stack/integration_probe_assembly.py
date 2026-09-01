"""
Assembling the trees a localisation asks CI about.

Sibling of the local search, which assembles the same prefixes and runs the suite over
each itself: a matrix job is the only thing that runs a library's own tests, and it runs
nowhere but CI, so each tree is published for a dispatched run instead.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from git_commands import DETACHED_HEAD, BranchPublication, ProposedPush
from stack import Branch, Stack

from maintenance_git_commands import MaintenanceGitCommandRunner
from maintenance_restack_procedure import DetachedCheckout, RestackWorktree

from integration_assembly import IntegrationBuild
from integration_constants import (
    BUILD_NAME_FORMAT,
    PROBE_BRANCH_PREFIX,
    RERERE_SETTINGS,
)
from integration_localisation import LocalisationStage
from integration_probes import DispatchedProbe
from integration_selection import tips_of
from integration_tips import ResolutionProvenance


@dataclass(frozen=True)
class ProbeAssembly:
    """
    The trees a localisation asks CI about, assembled and published one per question.

    Sibling of :class:`FailureLocation`: both add tips in the build's own order to find
    which one turns the tests, and they differ only in what runs them. That one runs the
    configured suite here and reads the answer immediately; this publishes each tree for
    a dispatched run to judge, because a matrix job is the only thing that runs a
    library's own tests and it runs nowhere but CI.

    Each tree is pushed straight from a detached head, so no local branch is left behind
    for a question that has been answered.
    """

    stack: Stack
    """
    The derived stack, whose tips these are prefixes of.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner naming the checkout to add the worktree to.
    """

    provenance: ResolutionProvenance
    """
    Who wrote each recorded resolution, for a merge that replays one.
    """

    named_at: datetime
    """
    The moment the round's branches are named after.
    """

    def branch_name(self, stage: LocalisationStage, ordinal: int) -> str:
        """
        Name one probe's tree.

        The round is in the name as well as the moment, because the two rounds of one
        search are opened by calls that can land in the same second - and a second round
        reusing a first round's name would be answered by the run that judged a different
        tree.

        :param stage: Which round the probe belongs to.
        :param ordinal: Which probe of the round it is.
        :return: The branch its tree is published under.
        """
        return (
            f"{PROBE_BRANCH_PREFIX}{self.named_at.strftime(BUILD_NAME_FORMAT)}"
            f"-{stage}-{ordinal}"
        )

    def prefixes(self) -> tuple[DispatchedProbe, ...]:
        """
        Publish every prefix of the merge order, one tip at a time.

        :return: One probe per tip that reached a build, in merge order.
        """
        tips = tips_of(self.stack)
        with self._assembling() as build:
            build.start_unnamed()
            probes: list[DispatchedProbe] = []
            included: list[str] = []
            for tip in tips:
                if not build.merge(tip, included).is_integrated:
                    continue
                included.append(tip.name)
                probes.append(
                    self._publish(build, tip, LocalisationStage.PREFIXES, len(probes))
                )
            return tuple(probes)

    def pairings(
        self, suspect: str, earlier: Sequence[str]
    ) -> tuple[DispatchedProbe, ...]:
        """
        Publish the suspect paired with each earlier tip on its own.

        Which earlier tip the suspect fails against alone is a different question from
        which prefix turned the tests, and only a tree holding just those two answers
        it.

        :param suspect: The tip whose arrival turned the library's tests.
        :param earlier: The tips that were in the build when it did, in merge order.
        :return: One probe per pairing that assembled.
        """
        by_name = {tip.name: tip for tip in tips_of(self.stack)}
        with self._assembling() as build:
            probes = []
            for name in earlier:
                build.start_unnamed()
                if not build.merge(by_name[name], []).is_integrated:
                    continue
                if not build.merge(by_name[suspect], [name]).is_integrated:
                    continue
                probes.append(
                    self._publish(
                        build, by_name[name], LocalisationStage.NARROWING, len(probes)
                    )
                )
            return tuple(probes)

    def take_down(self, probes: Sequence[DispatchedProbe]) -> None:
        """
        Delete the trees a concluded round published.

        A localisation runs whenever a candidate goes red, so trees left behind accumulate
        - and a run outlives the branch it ran on, so there is nothing in one to read once
        the search has answered.

        :param probes: The round's probes.
        """
        for probe in probes:
            self.git.delete_branch(self.stack.configuration.fork_remote, probe.branch)

    @contextmanager
    def _assembling(self) -> Iterator[IntegrationBuild]:
        """:return: A build in a worktree of its own, so the invoking checkout keeps its
        own files while trees are assembled."""
        with (
            DetachedCheckout.of(self.git),
            RestackWorktree.added_to(self.git) as assembling,
        ):
            yield IntegrationBuild(
                git=dataclasses.replace(
                    assembling, configuration_overrides=RERERE_SETTINGS
                ),
                configuration=self.stack.configuration,
                provenance=self.provenance,
            )

    def _publish(
        self,
        build: IntegrationBuild,
        tip: Branch,
        stage: LocalisationStage,
        ordinal: int,
    ) -> DispatchedProbe:
        """:param build: The assembly whose current head is the tree to publish.
        :param tip: The tip this probe is about.
        :param stage: Which round the probe belongs to.
        :param ordinal: Which probe of the round it is.
        :return: The probe, once its tree is on the fork."""
        branch = self.branch_name(stage, ordinal)
        build.git.push(
            ProposedPush(
                remote=self.stack.configuration.fork_remote,
                publication=BranchPublication(source=DETACHED_HEAD, branch=branch),
                with_lease=True,
            )
        ).raise_if_failed()
        return DispatchedProbe(
            branch=branch, tip=tip.name, pull_request_number=tip.pull_request_number
        )
