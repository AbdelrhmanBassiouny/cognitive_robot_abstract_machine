#!/usr/bin/env python3
"""Build a personal integration branch: the upstream base plus every in-flight stack tip.

Pull requests are produced faster than the upstream merges them, so a feature that is
finished but unreviewed is unusable in daily work, and two in-flight features that
conflict discover it only at the far end of the review queue. This assembles a branch
that carries all of them at once::

    python .claude/stack/integration.py build            # build, then run the suite on it
    python .claude/stack/integration.py build --restack  # bring stale tips forward first
    python .claude/stack/integration.py build --json     # the build as one document

The branch exists to be built *from*, not to be history. It is regenerated from scratch
on every run, nothing is ever merged out of it, and a conflict found on it is fixed in
the feature branch it belongs to - never here.

It gates nothing. Promotion asks whether one branch is ready for review against the
upstream; integration asks whether the branches coexist. Gating promotion on a clean
build would hold one branch back because another conflicts with it, with no principled
reason that one is the one to wait.

This module detects, attributes and skips; it makes no judgement about what a collision
means. That is ``/integration-conflict-triage``'s, which reads the document this emits.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shlex
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any, ClassVar

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from exceptions import GitCommandFailed  # noqa: E402
from stack import (  # noqa: E402
    AmbiguousForkRemoteError,
    Branch,
    Configuration,
    ForkRemoteNotFoundError,
    Stack,
    build_stack,
    load_configuration,
    order,
    resolve_ref,
)

from maintenance_board import (  # noqa: E402
    BoardExport,
    MissingPullRequestFieldError,
)
from maintenance_git_commands import (  # noqa: E402
    BranchAncestry,
    MaintenanceGitCommandRunner,
)
from maintenance_github import (  # noqa: E402
    GitHubCredentialUnavailableError,
    GitHubRepository,
    GitHubRequestFailed,
)
from maintenance_restack_procedure import (  # noqa: E402
    DetachedCheckout,
    RestackWorktree,
    restack,
)

POINTER_BRANCH = "integration"
"""The branch a developer checks out, moved to each build that finishes.

Builds are named ``integration-<timestamp>`` with a hyphen rather than a slash: git
stores refs as files, so ``refs/heads/integration/<timestamp>`` cannot exist while
``refs/heads/integration`` does. The obvious naming is the one git refuses.
"""

BUILD_NAME_FORMAT = "%Y%m%d-%H%M%S"
"""How a build's moment is spelled in its branch name."""

RERERE_SETTINGS = (
    ("rerere.enabled", "true"),
    ("rerere.autoupdate", "true"),
)
"""Replay of previously recorded conflict resolutions, turned on for the build alone.

Passed per command rather than written into the repository's configuration, which
belongs to whoever invoked the build rather than to the build.
"""

RESOLUTION_REPLAY_MARKER = "using previous resolution"
"""What git says when it resolves a conflict from its recorded cache.

Worth stating why this is read at all rather than inferred from the merge's shape: a
replayed merge *fails*, exactly like a merge that never began, and leaves no unmerged
paths behind because the replay has already staged them. The two are indistinguishable
without this.
"""

PROVENANCE_FILENAME = "resolution-authors.json"
"""Where the authorship of recorded resolutions is kept, beside the cache it describes."""


# %% what became of one tip


class TipStatus(StrEnum):
    """What a build did with one stack tip."""

    MERGED = "merged"
    """It merged cleanly and is in the build."""

    REPLAYED = "replayed"
    """It is in the build, but only because a recorded resolution was replayed - so the
    collision it hides is still there for whoever lands second."""

    SKIPPED = "skipped"
    """It conflicted and was left out, so the rest of the build could go on."""

    INTEGRATION_FAILED = "integration-failed"
    """The merge refused before it began - unrelated histories, a reference that does
    not resolve, something in the way. The build's own environment, not the tip's."""


class ResolutionAuthor(StrEnum):
    """Who wrote a conflict resolution that a later build replays."""

    HUMAN = "human"
    """A developer resolved it, which is the risk rerere was always understood to carry."""

    SKILL = "skill"
    """A skill resolved it, so it is replayed unreviewed on every later build and is
    worth being able to find again."""


@dataclass(frozen=True)
class ResolutionProvenance:
    """Which resolutions were written by a machine rather than by a developer.

    rerere matches on a conflict's preimage and replays it automatically, so a
    resolution that is textually applicable but semantically wrong is reapplied
    unreviewed for as long as it stays in the cache. That was accepted when only a
    developer could record one; it is a different proposition once a skill can, so the
    build says which it replayed rather than leaving them indistinguishable.
    """

    authors: dict[str, ResolutionAuthor]
    """The author recorded against each tip whose collision was resolved."""

    def author_for(self, branch: str) -> ResolutionAuthor:
        """Say who wrote the resolution replayed for a tip.

        An unrecorded resolution is a developer's: a skill records every one it writes,
        so reading silence as machine-authored would flag the one case that was never
        the problem.

        :param branch: The tip whose resolution was replayed.
        :return: Its author.
        """
        return self.authors.get(branch, ResolutionAuthor.HUMAN)

    @classmethod
    def read(cls, path: Path) -> ResolutionProvenance:
        """:param path: The manifest to read.
        :return: What it records, or no claims at all when it does not exist yet."""
        if not path.exists():
            return cls({})
        return cls(
            {
                branch: ResolutionAuthor(author)
                for branch, author in json.loads(path.read_text()).items()
            }
        )

    def write(self, path: Path) -> Path:
        """:param path: Where to record what is known.
        :return: The path written."""
        path.write_text(json.dumps(dict(self.authors), indent=2) + "\n")
        return path

    def claiming(self, branch: str, author: ResolutionAuthor) -> ResolutionProvenance:
        """:param branch: The tip whose resolution was just recorded.
        :param author: Who wrote it.
        :return: These claims with that one added, the existing ones left alone."""
        return ResolutionProvenance({**self.authors, branch: author})


@dataclass
class TestCommandNotConfiguredError(ValueError):
    """Raised when a build is asked to run a suite this checkout does not name one for.

    Refused rather than skipped: a build reporting that it ran nothing is honest, and a
    build reporting success because there was nothing to fail is the silence the suite
    exists to break.
    """

    setting: str
    """The configuration key that would name the suite."""

    def __str__(self) -> str:
        """:return: Which setting is missing, and the way out."""
        return (
            f"no suite to run: set '{self.setting}' in stack.toml, "
            f"or build with --no-test"
        )


@dataclass(frozen=True)
class TipOutcome:
    """One tip's fate in one build."""

    branch: str
    """The tip's branch."""

    pull_request_number: int
    """The fork pull request that publishes it."""

    status: TipStatus
    """What became of it."""

    collided_with: str | None = None
    """The branch already in the build that it conflicts with, or the base when it is
    simply stale. Named because the pair is what is actionable - which of the two should
    change is a judgement neither branch's own state answers."""

    conflicting_paths: tuple[str, ...] = ()
    """The paths the conflict was on."""

    resolved_by: ResolutionAuthor | None = None
    """Who wrote the resolution that was replayed, when one was."""

    explanation: str = ""
    """What git said, for a refusal that is the build's own to fix."""

    @property
    def reached_the_build(self) -> bool:
        """:return: Whether the tip's commits are in the finished branch."""
        return self.status in {TipStatus.MERGED, TipStatus.REPLAYED}


# %% selecting what to build from


def tips_of(stack: Stack) -> list[Branch]:
    """The branches to merge, in the order they are merged.

    Only a stack's tip is taken: a tip already contains its own stack, so merging its
    parent as well would merge the same commits twice and say nothing new. Anything
    already in the upstream base is left out for the same reason.

    Order is load-bearing rather than incidental. Once a conflict can skip a tip, the
    order decides *which* tip is skipped, so it is stated: ascending pull request
    number, which is stable across runs and independent of how the board arrived.

    :param stack: The derived stack.
    :return: The tips, in merge order.
    """
    claimed_as_parent = {branch.parent for branch in stack.branches}
    return sorted(
        (
            branch
            for branch in order(stack)
            if branch.name not in claimed_as_parent
            and not stack.has_landed_upstream(branch.name)
        ),
        key=lambda branch: branch.pull_request_number,
    )


def build_branch_name(moment: datetime) -> str:
    """:param moment: When the build started.
    :return: The branch to assemble it on."""
    return f"{POINTER_BRANCH}-{moment.strftime(BUILD_NAME_FORMAT)}"


# %% assembling the branch


@dataclass(frozen=True)
class IntegrationBuild:
    """One branch under assembly, and the tips merged into it so far."""

    git: MaintenanceGitCommandRunner
    """The runner for the worktree the branch is assembled in, with replay turned on."""

    configuration: Configuration
    """The resolved configuration naming both remotes and the base."""

    provenance: ResolutionProvenance
    """Who wrote each recorded resolution, for reporting a replay by its author."""

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
        """Begin an assembly nobody is meant to keep, at the upstream base.

        A probe exists to answer one question and be thrown away, so it is built on a
        detached head rather than a branch: a named one would outlive the answer and
        accumulate, one ref per question ever asked.
        """
        self.git.run("checkout", "--quiet", "--detach", self.base_reference)

    def merge(self, tip: Branch, already_included: list[str]) -> TipOutcome:
        """Merge one tip, or say why it was left out.

        :param tip: The tip to merge.
        :param already_included: The tips merged so far, oldest first.
        :return: What became of it.
        """
        result = self.git.merge(self.reference_to(tip.name))
        if result.succeeded:
            return TipOutcome(
                branch=tip.name,
                pull_request_number=tip.pull_request_number,
                status=TipStatus.MERGED,
            )
        if self._replayed_a_resolution(result.output, result.error_output):
            return self._conclude_replay(tip, already_included)
        conflicting_paths = self.git.unmerged_paths()
        self.git.abandon(tip.strategy)
        if not conflicting_paths:
            return TipOutcome(
                branch=tip.name,
                pull_request_number=tip.pull_request_number,
                status=TipStatus.INTEGRATION_FAILED,
                explanation=result.error_output,
            )
        return TipOutcome(
            branch=tip.name,
            pull_request_number=tip.pull_request_number,
            status=TipStatus.SKIPPED,
            collided_with=self._collided_with(tip, already_included),
            conflicting_paths=conflicting_paths,
        )

    @staticmethod
    def _replayed_a_resolution(*streams: str) -> bool:
        """:param streams: What git said about the merge.
        :return: Whether it applied a resolution out of its cache."""
        return any(RESOLUTION_REPLAY_MARKER in stream for stream in streams)

    def _conclude_replay(self, tip: Branch, already_included: list[str]) -> TipOutcome:
        """Commit a merge whose conflicts the replay already resolved.

        :param tip: The tip being merged.
        :param already_included: The tips merged so far, oldest first.
        :return: The tip's outcome, reported as replayed rather than as clean.
        """
        self.git.conclude_merge().raise_if_failed()
        return TipOutcome(
            branch=tip.name,
            pull_request_number=tip.pull_request_number,
            status=TipStatus.REPLAYED,
            collided_with=self._collided_with(tip, already_included),
            resolved_by=self.provenance.author_for(tip.name),
        )

    def _collided_with(self, tip: Branch, already_included: list[str]) -> str:
        """Attribute a collision to the pair it is between.

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
) -> IntegrationReport:
    """Assemble one integration branch and report what went into it.

    The assembly happens in a worktree of its own, which the invoking checkout lends its
    branch to through a :class:`maintenance.DetachedCheckout` and gets back with its own
    files still in place - a build is something a developer runs *while* working.

    :param stack: The derived stack, whose tips this merges.
    :param git: The runner naming the checkout to add the worktree to.
    :param build_branch: The branch to assemble onto.
    :param provenance: Who wrote each recorded resolution.
    :param test_command: The suite to run on the finished branch, or ``None`` to skip.
    :return: What the build contains and what it left out.
    """
    tips = tips_of(stack)
    with DetachedCheckout.of(git), RestackWorktree.added_to(git) as assembling:
        build = IntegrationBuild(
            git=dataclasses.replace(
                assembling, configuration_overrides=RERERE_SETTINGS
            ),
            configuration=stack.configuration,
            provenance=provenance,
        )
        build.start(build_branch)
        outcomes: list[TipOutcome] = []
        included: list[str] = []
        for tip in tips:
            outcome = build.merge(tip, included)
            outcomes.append(outcome)
            if outcome.reached_the_build:
                included.append(tip.name)
        git.run("branch", "--force", POINTER_BRANCH, build_branch)
        tests_passed = _run_tests(test_command, build.git.working_directory)
    return IntegrationReport(
        build_branch=build_branch,
        base=stack.configuration.upstream_base,
        tips=tuple(outcomes),
        tests_passed=tests_passed,
    )


# %% localising a break the merge could not see


@dataclass(frozen=True)
class SemanticBreak:
    """Two tips that each work, merge cleanly, and do not work together.

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


@dataclass(frozen=True)
class BisectReport:
    """What one bisect localised."""

    build_branch: str
    """The branch the bisect assembled onto."""

    base: str
    """The upstream base it started from."""

    tips_tested: tuple[str, ...] = ()
    """The tips that reached the build and had the suite run over them, in order."""

    semantic_break: SemanticBreak | None = None
    """The break, or ``None`` when every prefix of the build passed."""

    def as_json(self) -> str:
        """:return: The bisect as one machine-readable document, led by its status."""
        status = exit_code_for_bisect(self)
        return json.dumps(
            {
                "status": status.name_for_a_caller,
                "exit_code": int(status),
                **asdict(self),
            },
            indent=2,
        )


def exit_code_for_bisect(report: BisectReport) -> IntegrationExitCode:
    """:param report: What the bisect localised.
    :return: The process exit code, which reports a located break the same way the build
        that failed reported it."""
    if report.semantic_break is None:
        return IntegrationExitCode.SUCCESS
    return IntegrationExitCode.TESTS_FAILED


def bisect_integration(
    stack: Stack,
    git: MaintenanceGitCommandRunner,
    build_branch: str,
    provenance: ResolutionProvenance,
    test_command: str,
) -> BisectReport:
    """Find the tip whose arrival breaks a build that merged cleanly.

    Assembles the same tips in the same order as :func:`build_integration` and runs the
    suite after each one that reaches the build, so what it localises describes the build
    that failed rather than some other ordering of it. Stops at the first tip that turns
    the suite, then narrows to the earlier tip that alone reproduces it.

    Slow by construction - one suite run per tip, plus one per candidate while narrowing.
    It is a diagnosis, not part of a build.

    :param stack: The derived stack, whose tips this merges.
    :param git: The runner naming the checkout to add the worktree to.
    :param build_branch: The branch to assemble onto.
    :param provenance: Who wrote each recorded resolution.
    :param test_command: The suite that decides whether a build works.
    :return: What it localised.
    """
    tips = tips_of(stack)
    by_name = {tip.name: tip for tip in tips}
    with DetachedCheckout.of(git), RestackWorktree.added_to(git) as assembling:
        build = IntegrationBuild(
            git=dataclasses.replace(
                assembling, configuration_overrides=RERERE_SETTINGS
            ),
            configuration=stack.configuration,
            provenance=provenance,
        )
        build.start(build_branch)
        included: list[str] = []
        for tip in tips:
            if not build.merge(tip, included).reached_the_build:
                continue
            if _run_tests(test_command, build.git.working_directory):
                included.append(tip.name)
                continue
            return BisectReport(
                build_branch=build_branch,
                base=stack.configuration.upstream_base,
                tips_tested=tuple(included) + (tip.name,),
                semantic_break=SemanticBreak(
                    culprit=tip.name,
                    culprit_pull_request_number=tip.pull_request_number,
                    already_included=tuple(included),
                    breaks_against=_breaks_against(
                        build, tip, included, by_name, test_command
                    ),
                ),
            )
        return BisectReport(
            build_branch=build_branch,
            base=stack.configuration.upstream_base,
            tips_tested=tuple(included),
        )


def _breaks_against(
    build: IntegrationBuild,
    culprit: Branch,
    already_included: list[str],
    by_name: dict[str, Branch],
    test_command: str,
) -> str | None:
    """Narrow a break to the one earlier tip that reproduces it on its own.

    Naming everything that was in the build is not actionable when only one of them is
    involved. Asked most-recent-first, the same way a merge conflict's partner is.

    :param build: The build under assembly, whose worktree the probes run in.
    :param culprit: The tip whose arrival turned the suite.
    :param already_included: The tips in the build when it turned, in merge order.
    :param by_name: Every tip, keyed by branch name.
    :param test_command: The suite that decides whether a build works.
    :return: The tip it fails against alone, or ``None`` when only the combination does.
    """
    for candidate in reversed(already_included):
        build.start_unnamed()
        if not build.merge(by_name[candidate], []).reached_the_build:
            continue
        if not build.merge(culprit, [candidate]).reached_the_build:
            continue
        if not _run_tests(test_command, build.git.working_directory):
            return candidate
    return None


def _run_tests(command: str | None, working_directory: Path) -> bool | None:
    """Run the configured suite against the finished branch.

    :param command: The suite to run, or ``None`` when it was asked to be skipped.
    :param working_directory: The assembled branch's checkout.
    :return: Whether it passed, or ``None`` when it was not run.
    """
    if command is None:
        return None
    return (
        subprocess.run(
            shlex.split(command), cwd=working_directory, capture_output=True, text=True
        ).returncode
        == 0
    )


# %% the report a caller renders or acts on


@dataclass(frozen=True)
class IntegrationReport:
    """One build: what reached the branch, what did not, and whether it works."""

    build_branch: str
    """The branch this build was assembled onto."""

    base: str
    """The upstream base it started from."""

    tips: tuple[TipOutcome, ...] = ()
    """What became of each tip, in the order they were merged."""

    tests_passed: bool | None = None
    """Whether the configured suite passed, or ``None`` when it was not run - which a
    caller has to be able to tell from a suite that ran and passed."""

    def as_json(self) -> str:
        """:return: The build as one machine-readable document, led by its status."""
        status = exit_code_for(self)
        return json.dumps(
            {
                "status": status.name_for_a_caller,
                "exit_code": int(status),
                **asdict(self),
            },
            indent=2,
        )

    @property
    def tips_left_out(self) -> tuple[TipOutcome, ...]:
        """:return: Every tip whose commits are not in the finished branch."""
        return tuple(outcome for outcome in self.tips if not outcome.reached_the_build)

    @property
    def replayed_by_a_skill(self) -> tuple[TipOutcome, ...]:
        """:return: Every tip whose merge replayed a machine-written resolution."""
        return tuple(
            outcome
            for outcome in self.tips
            if outcome.status is TipStatus.REPLAYED
            and outcome.resolved_by is ResolutionAuthor.SKILL
        )


class IntegrationExitCode(IntEnum):
    """What this builder's exit status tells a caller.

    The first six match :class:`maintenance.MaintenanceExitCode` value for value and
    meaning, so a caller acting on both tools' statuses never has to remember which
    produced one.
    """

    SUCCESS = 0
    """Every tip is in the branch, and the suite passed or was not asked for."""

    USAGE = 2
    """No such command, or the wrong arguments."""

    REMOTES_UNRESOLVED = 4
    """The fork could not be identified from this checkout's remotes."""

    GIT_COMMAND_FAILED = 6
    """A git command the build depended on failed; nothing further was attempted."""

    CREDENTIAL_UNAVAILABLE = 8
    """No GitHub token is set, so the fork's open pull requests cannot be read."""

    GITHUB_REQUEST_FAILED = 9
    """The API refused a call this build depends on; its status and reason are on
    stderr."""

    TIP_LEFT_OUT = 10
    """The branch was built, but at least one tip is missing from it - a collision, or a
    merge that refused before it began. The build is still usable; it is not whole."""

    TESTS_FAILED = 11
    """The branch was built and the suite failed on it. This is what catches the
    semantic conflict per-branch checks structurally cannot: two branches that each pass
    alone, merge cleanly, and break together."""

    SUSPECT_REPLAY = 12
    """The suite failed on a branch carrying a machine-written resolution, replayed
    without review. Distinct from an ordinary red suite because the answer differs:
    report and stop, since re-resolving into the same failure is how a build thrashes."""

    @property
    def name_for_a_caller(self) -> str:
        """What this status means, in words rather than as a number to be looked up.

        Derived from the member itself, so a status can never end up carrying a name
        belonging to a different one.

        :return: The status's name, in the form a caller reads or matches on.
        """
        return self.name.lower().replace("_", "-")


def exit_code_for(report: IntegrationReport) -> IntegrationExitCode:
    """Decide one build's exit status from what it actually left behind.

    Shared by every command that produces a report, so none of them can disagree about
    what a clean build is. A tip silently missing, or a red suite reported as success,
    is exactly the kind of silence this exists to prevent - and the exit status is the
    only half a caller with no model in it reads.

    :param report: What the build did.
    :return: The process exit code.
    """
    if report.tests_passed is False:
        if report.replayed_by_a_skill:
            return IntegrationExitCode.SUSPECT_REPLAY
        return IntegrationExitCode.TESTS_FAILED
    if report.tips_left_out:
        return IntegrationExitCode.TIP_LEFT_OUT
    return IntegrationExitCode.SUCCESS


# %% printing


def print_build(report: IntegrationReport) -> None:
    """:param report: The build to summarise, one tab-separated line per tip."""
    print(f"{report.build_branch}\tbuilt-on\t{report.base}")
    for outcome in report.tips:
        detail = (
            ",".join(outcome.conflicting_paths)
            or outcome.explanation
            or (outcome.resolved_by or "")
        )
        collided = f" (with {outcome.collided_with})" if outcome.collided_with else ""
        print(f"{outcome.branch}\t{outcome.status}{collided}\t{detail}")
    if report.tests_passed is not None:
        print(
            f"{report.build_branch}\ttests\t{'passed' if report.tests_passed else 'failed'}"
        )


def print_bisect(report: BisectReport) -> None:
    """:param report: The bisect to summarise."""
    localised = report.semantic_break
    if localised is None:
        print(
            f"{report.build_branch}\tno-break-localised\t{len(report.tips_tested)} tip(s)"
        )
        return
    against = localised.breaks_against or "the combination before it"
    print(f"{localised.culprit}\tbreaks-against\t{against}")
    print(
        f"{localised.culprit}\twas-added-to\t{','.join(localised.already_included)}",
        file=sys.stderr,
    )


# %% entry point


@dataclass(frozen=True)
class IntegrationRun:
    """What one run has resolved so far, built lazily as a command asks for it.

    The credential is resolved before anything is fetched, so a checkout without one is
    sent after a token rather than after whichever network call happened to come first -
    the fork's open pull requests are what a build is derived from, and no amount of
    fetching substitutes for them.
    """

    configuration: Configuration
    """The resolved configuration naming both repositories and the base."""

    git: MaintenanceGitCommandRunner
    """The runner every git command goes through."""

    def fork(self) -> GitHubRepository:
        """:return: The fork, as this run's credential can read it."""
        return GitHubRepository.from_environment(self.configuration.fork_repository)

    def stack(self, fork: GitHubRepository) -> Stack:
        """Derive the stack from the fork's open pull requests, read fresh.

        Read rather than loaded from ``board.json``: a build is only as good as its idea
        of what is in flight, and a snapshot left behind by an earlier pass is worse than
        no snapshot at all.

        :param fork: The fork to read the open pull requests from.
        :return: The derived stack.
        """
        export = BoardExport.from_api_records(fork.open_pull_requests())
        ancestry = BranchAncestry(self.configuration, self.git)
        upstream = (
            f"{self.configuration.upstream_remote}/{self.configuration.upstream_base}"
        )
        return build_stack(
            self.configuration,
            list(export.pull_requests),
            lambda name: ancestry.is_ancestor(name, upstream),
        )

    def refresh_remotes(self) -> None:
        """Fetch both remotes, so a build merges what is published rather than what
        this checkout last happened to see."""
        self.git.fetch(self.configuration.fork_remote)
        self.git.fetch(self.configuration.upstream_remote)

    def provenance_path(self) -> Path:
        """:return: Where this repository records who wrote each cached resolution -
        beside the cache itself, which is shared by every worktree."""
        return Path(self.git.run("rev-parse", "--git-common-dir")).resolve() / (
            PROVENANCE_FILENAME
        )

    def replaying(self, working_directory: Path) -> MaintenanceGitCommandRunner:
        """:param working_directory: The checkout to run in.
        :return: A runner with resolution replay turned on for its commands alone."""
        return MaintenanceGitCommandRunner(
            working_directory=working_directory,
            configuration_overrides=RERERE_SETTINGS,
        )

    def stage_conflict(self, already_included: str, tip: str) -> dict[str, Any]:
        """Reproduce one pair's collision in a worktree of its own.

        The merge is left conflicted rather than abandoned: recording a resolution means
        resolving *this* conflict, and rerere keys its cache on the conflict's own shape.

        :param already_included: The branch that reached the build first.
        :param tip: The branch that was skipped against it.
        :return: Where the collision is live, and which paths it is on.
        :raises GitCommandFailed: If the worktree cannot be added.
        """
        worktree = Path(tempfile.mkdtemp(prefix="stack-resolve-"))
        self.git.run(
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(worktree),
            resolve_ref(self.configuration, already_included),
        )
        resolving = self.replaying(worktree)
        resolving.merge(resolve_ref(self.configuration, tip))
        return {
            "worktree": str(worktree),
            "tip": tip,
            "against": already_included,
            "conflicting_paths": list(resolving.unmerged_paths()),
        }

    def record_resolution(
        self, worktree: Path, tip: str, author: ResolutionAuthor
    ) -> Path:
        """Commit a staged resolution, so a later build replays it, and say who wrote it.

        :param worktree: The worktree the resolution was made in.
        :param tip: The branch that was skipped.
        :param author: Who wrote the resolution.
        :return: The provenance manifest that now claims it.
        :raises GitCommandFailed: If the resolution cannot be committed.
        """
        resolving = self.replaying(worktree)
        resolving.run("add", "--all")
        resolving.conclude_merge().raise_if_failed()
        self.git.attempt("worktree", "remove", "--force", str(worktree))
        path = self.provenance_path()
        return ResolutionProvenance.read(path).claiming(tip, author).write(path)


@dataclass(frozen=True)
class IntegrationCommand(ABC):
    """One command this builder answers.

    A command owns its own name, its own flags and what it does, so adding one is
    writing a subclass - :data:`COMMANDS` finds it, and nothing else has to be told it
    exists.
    """

    invoked_as: ClassVar[str]
    """The name it is invoked by on the command line."""

    description: ClassVar[str]
    """What it does, as ``--help`` puts it."""

    REQUIRED_OF_EVERY_COMMAND: ClassVar[tuple[str, ...]] = ("invoked_as", "description")
    """The class variables a subclass has to supply for the parser to describe it."""

    def __init_subclass__(cls, **keyword_arguments: Any) -> None:
        """Refuse a command that does not say what it is called or what it does.

        :param keyword_arguments: Passed to the base implementation untouched.
        :raises TypeError: If the subclass leaves either class variable unset.
        """
        super().__init_subclass__(**keyword_arguments)
        missing = [
            name
            for name in cls.REQUIRED_OF_EVERY_COMMAND
            if not isinstance(getattr(cls, name, None), str)
        ]
        if missing:
            raise TypeError(f"{cls.__name__} must define {' and '.join(missing)}")

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Declare this command's own flags.

        :param parser: The subparser to declare them on.
        """

    @abstractmethod
    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """Perform the command.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """


@dataclass(frozen=True)
class BuildCommand(IntegrationCommand):
    """Assembles the upstream base plus every in-flight stack tip."""

    invoked_as: ClassVar[str] = "build"
    description: ClassVar[str] = "assemble the upstream base plus every in-flight tip"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument(
            "--restack",
            action="store_true",
            help=(
                "bring every stale tip forward first; this pushes to branches that "
                "belong to other people, which is why it is not the default"
            ),
        )
        parser.add_argument(
            "--no-test",
            dest="run_tests",
            action="store_false",
            help="skip the suite that would otherwise be run on the finished branch",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """:param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code."""
        test_command = self._test_command(run.configuration, arguments.run_tests)
        fork = run.fork()
        run.refresh_remotes()
        stack = run.stack(fork)
        if arguments.restack:
            restack(stack, run.git, fork)
            run.refresh_remotes()
        report = build_integration(
            stack=stack,
            git=run.git,
            build_branch=build_branch_name(datetime.now(timezone.utc)),
            provenance=ResolutionProvenance.read(run.provenance_path()),
            test_command=test_command,
        )
        if arguments.json:
            print(report.as_json())
        else:
            print_build(report)
        return exit_code_for(report)

    @staticmethod
    def _test_command(configuration: Configuration, run_tests: bool) -> str | None:
        """Settle what the suite is before anything is built, so an unrunnable request
        fails before it has cost a build rather than after.

        :param configuration: The resolved configuration.
        :param run_tests: Whether a suite was asked for.
        :return: The command to run, or ``None`` when it was asked to be skipped.
        :raises TestCommandNotConfiguredError: If one was asked for and none is named.
        """
        if not run_tests:
            return None
        if not configuration.integration_test_command:
            raise TestCommandNotConfiguredError("integration_test_command")
        return configuration.integration_test_command


@dataclass(frozen=True)
class BisectCommand(IntegrationCommand):
    """Finds which tip's arrival breaks a build that merged cleanly."""

    invoked_as: ClassVar[str] = "bisect"
    description: ClassVar[str] = "find which tip's arrival breaks the suite"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare ``--json`` on."""
        parser.add_argument(
            "--json",
            action="store_true",
            help="emit the machine-readable document rather than a summary",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """:param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code."""
        test_command = BuildCommand._test_command(run.configuration, run_tests=True)
        fork = run.fork()
        run.refresh_remotes()
        report = bisect_integration(
            stack=run.stack(fork),
            git=run.git,
            build_branch=build_branch_name(datetime.now(timezone.utc)),
            provenance=ResolutionProvenance.read(run.provenance_path()),
            test_command=test_command,
        )
        if arguments.json:
            print(report.as_json())
        else:
            print_bisect(report)
        return exit_code_for_bisect(report)


@dataclass(frozen=True)
class StageConflictCommand(IntegrationCommand):
    """Reproduces one pair's collision in a worktree of its own, for a resolution to be
    written into."""

    invoked_as: ClassVar[str] = "stage-conflict"
    description: ClassVar[str] = "reproduce a pair's collision in a scratch worktree"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument("--tip", required=True, help="the branch that was skipped")
        parser.add_argument(
            "--against", required=True, help="the branch it was reported colliding with"
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """Leave the collision live in a scratch worktree, and say where.

        The worktree outlives this command on purpose: what goes into the conflicted
        files is the judgement this tool does not make, so it stops here and hands back
        somewhere to make it.

        :param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code.
        """
        run.refresh_remotes()
        staged = run.stage_conflict(arguments.against, arguments.tip)
        print(json.dumps(staged, indent=2))
        return IntegrationExitCode.SUCCESS


@dataclass(frozen=True)
class RecordResolutionCommand(IntegrationCommand):
    """Commits a staged resolution into the replay cache, under the author that wrote
    it."""

    invoked_as: ClassVar[str] = "record-resolution"
    description: ClassVar[str] = "record a staged resolution, with who wrote it"

    def declare_arguments(self, parser: argparse.ArgumentParser) -> None:
        """:param parser: The subparser to declare this command's flags on."""
        parser.add_argument("--tip", required=True, help="the branch that was skipped")
        parser.add_argument(
            "--worktree", required=True, help="the worktree the resolution was made in"
        )
        parser.add_argument(
            "--author",
            required=True,
            choices=[author.value for author in ResolutionAuthor],
            help="who wrote it, which decides how a later replay of it is reported",
        )

    def run(
        self, run: IntegrationRun, arguments: argparse.Namespace
    ) -> IntegrationExitCode:
        """:param run: What this run has resolved.
        :param arguments: The parsed command line.
        :return: The process exit code."""
        run.record_resolution(
            worktree=Path(arguments.worktree),
            tip=arguments.tip,
            author=ResolutionAuthor(arguments.author),
        )
        print(f"{arguments.tip}\trecorded-by\t{arguments.author}")
        return IntegrationExitCode.SUCCESS


COMMANDS: tuple[IntegrationCommand, ...] = tuple(
    subclass() for subclass in IntegrationCommand.__subclasses__()
)
"""Every command this builder answers, found from the subclasses themselves so a command
cannot exist without being reachable, in the order they are defined."""


def _argument_parser() -> argparse.ArgumentParser:
    """:return: The parser, built from the commands rather than from a list of them."""
    parser = argparse.ArgumentParser(
        prog="integration.py",
        description=(
            "Build a personal integration branch: the upstream base plus every "
            "in-flight stack tip."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        command.declare_arguments(
            subparsers.add_parser(command.invoked_as, help=command.description)
        )
    return parser


def main() -> IntegrationExitCode:
    """Run the command line and say, in words, what its status means.

    :return: The process exit code.
    """
    status = _dispatch()
    if status is not IntegrationExitCode.SUCCESS:
        print(
            f"integration.py: {status.name_for_a_caller} ({int(status)})",
            file=sys.stderr,
        )
    return status


def _dispatch() -> IntegrationExitCode:
    """Run the requested command, mapping every refusal to its own status.

    :return: The process exit code.
    """
    arguments = _argument_parser().parse_args()
    requested = next(
        entry for entry in COMMANDS if entry.invoked_as == arguments.command
    )
    try:
        return requested.run(
            IntegrationRun(
                configuration=load_configuration(),
                git=MaintenanceGitCommandRunner(working_directory=Path.cwd()),
            ),
            arguments,
        )
    except (ForkRemoteNotFoundError, AmbiguousForkRemoteError) as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.REMOTES_UNRESOLVED
    except GitHubCredentialUnavailableError as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.CREDENTIAL_UNAVAILABLE
    except (MissingPullRequestFieldError, TestCommandNotConfiguredError) as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.USAGE
    except GitCommandFailed as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.GIT_COMMAND_FAILED
    except GitHubRequestFailed as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.GITHUB_REQUEST_FAILED


if __name__ == "__main__":
    sys.exit(main())
