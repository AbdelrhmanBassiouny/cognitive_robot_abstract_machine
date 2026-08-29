"""
Localising a candidate's red to the tip whose arrival turned it.

A candidate that fails on a matrix job names a failing check and nothing else. The local
search cannot reproduce it: that re-runs the configured tooling suite, and a matrix job
runs one library's own tests, so the two see different failures by construction. This
re-runs the failing library over each prefix of the merge order instead, as a dispatched
run per prefix, and reports the same finding the local search reports.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from maintenance_github import (  # noqa: E402
    DispatchedWorkflowRuns,
    WorkflowRunRecord,
)
from integration_verdict import (  # noqa: E402
    ChecksVerdict,
    CheckRunField,
    ReportedChecks,
)

PROBE_WORKFLOW_FILE = "integration-probe.yml"
"""
The workflow one probe is a run of.

A file name rather than a numeric identifier, which is what the dispatch endpoint takes
and what keeps this readable in a repository that has never dispatched it.
"""

PROBE_RUN_NAME_PREFIX = "Integration probe over "
"""
Opens the name a probe's run carries, so a reader can tell one probe's run from
another's.

Every probe of one localisation is dispatched on the same reference - the one carrying
the pipeline - so the reference cannot tell them apart and the name has to.
"""

MATRIX_CHECK_PATTERN = re.compile(r"\(([^)]+)\)")
"""
Finds the library a matrix job's check name is for.

The matrix names each job ``test_each_lib (<lib>)``, optionally suffixed with the
reusable job's own name; the library is what the parentheses hold.
"""


class ProbeWorkflowInput(StrEnum):
    """
    What a probe has to be told, because its run starts on neither.
    """

    BUILD = "build"
    """
    The assembled prefix to check out and test.
    """

    LIBRARY = "library"
    """
    Which library's tests to run over it.
    """


class LibraryUnderTest(StrEnum):
    """
    The libraries the matrix runs a job for, which are the failures this can localise.

    A failing check naming one of these is re-runnable over a prefix; a failing check
    naming none of them is not this search's to answer, and saying so is better than
    probing something that cannot reproduce it.
    """

    GISKARDPY = "giskardpy"
    """
    The motion-planning library.
    """

    KRROOD = "krrood"
    """
    The knowledge-representation library.
    """

    SEMANTIC_DIGITAL_TWIN = "semantic_digital_twin"
    """
    The world-model library.
    """

    CORAPLEX = "coraplex"
    """
    The task-representation library.
    """

    RANDOM_EVENTS = "random_events"
    """
    The event-algebra library.
    """

    PROBABILISTIC_MODEL = "probabilistic_model"
    """
    The probabilistic-model library.
    """

    PHYSICS_SIMULATORS = "physics_simulators"
    """
    The simulator adapters.
    """

    ROBOKUDO = "robokudo"
    """
    The perception library.
    """

    SEGMIND = "segmind"
    """
    The segmentation library.
    """

    EXPERIMENTS = "experiments"
    """
    The experiment harnesses.
    """

    VERSION = "version"
    """
    The version-consistency checks.
    """

    COGNITIVE_ROBOT_ABSTRACT_MACHINE = "cognitive_robot_abstract_machine"
    """
    The umbrella package.
    """

    @classmethod
    def named_by(cls, check: str) -> LibraryUnderTest | None:
        """
        Read which library a failing check is about.

        :param check: The check's name, as the API reports it.
        :return: The library it runs, or ``None`` when it names none - which is the
            answer for every check that is not one of the matrix's jobs.
        """
        found = MATRIX_CHECK_PATTERN.search(check)
        if found is None:
            return None
        named = found.group(1)
        if named not in set(cls):
            return None
        return cls(named)


def probe_run_name(build_branch: str) -> str:
    """
    Name a probe's run after the tree it tests.

    :param build_branch: The assembled prefix under test.
    :return: The name its run carries, which is how it is found again.
    """
    return f"{PROBE_RUN_NAME_PREFIX}{build_branch}"


# %% what one probe is, and what its run says


@dataclass(frozen=True)
class Probe:
    """
    One assembled tree, and what the run judging it says so far.
    """

    branch: str
    """
    The tree, published under a name of its own so its run can be found again.
    """

    tip: str
    """The tip this probe is about - the one whose arrival it adds in a prefix round, or
    the earlier one it pairs the suspect with while narrowing."""

    pull_request_number: int
    """
    The fork pull request publishing that tip.
    """

    verdict: ChecksVerdict = ChecksVerdict.ABSENT
    """
    What its run amounts to, starting from before one has appeared.
    """

    @property
    def has_answered(self) -> bool:
        """
        A probe whose run has not appeared yet is waited for rather than acted on: a
        dispatch is accepted before its run object exists, so absence is the ordinary
        first answer. What catches one that never appears is the caller's own timeout.

        :return: Whether its run has finished.
        """
        return self.verdict in {ChecksVerdict.PASSED, ChecksVerdict.FAILED}

    @property
    def failed(self) -> bool:
        """:return: Whether the library's tests failed over this tree."""
        return self.verdict is ChecksVerdict.FAILED

    def as_json(self) -> dict[str, Any]:
        """:return: This probe, keyed the way the state document holds it."""
        return {
            ProbeKey.BRANCH: self.branch,
            ProbeKey.TIP: self.tip,
            ProbeKey.PULL_REQUEST_NUMBER: self.pull_request_number,
            ProbeKey.VERDICT: str(self.verdict),
        }

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> Probe:
        """:param document: One probe, as :meth:`as_json` wrote it.
        :return: The probe it describes."""
        return cls(
            branch=document[ProbeKey.BRANCH],
            tip=document[ProbeKey.TIP],
            pull_request_number=document[ProbeKey.PULL_REQUEST_NUMBER],
            verdict=ChecksVerdict(document[ProbeKey.VERDICT]),
        )


class ProbeKey(StrEnum):
    """
    The field names one probe is held under in the state document.
    """

    BRANCH = "branch"
    """
    The tree it published.
    """

    TIP = "tip"
    """
    The tip it is about.
    """

    PULL_REQUEST_NUMBER = "pull_request_number"
    """
    The fork pull request publishing that tip.
    """

    VERDICT = "verdict"
    """
    What its run says.
    """


@dataclass(frozen=True)
class TipUnderSuspicion:
    """
    The tip a prefix round localised, and what was in the build when it arrived.

    Carries exactly what an :class:`~integration.IntegrationTestFailure` is built from,
    so a localisation done this way and one done locally produce the same finding and
    are acted on through the same path.
    """

    branch: str
    """
    The tip whose arrival turned the library's tests.
    """

    pull_request_number: int
    """
    The fork pull request publishing it.
    """

    already_included: tuple[str, ...]
    """
    What was in the build when it turned, in merge order.
    """

    def as_json(self) -> dict[str, Any]:
        """:return: The suspect, keyed the way the state document holds it."""
        return {
            SuspectKey.BRANCH: self.branch,
            SuspectKey.PULL_REQUEST_NUMBER: self.pull_request_number,
            SuspectKey.ALREADY_INCLUDED: list(self.already_included),
        }

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> TipUnderSuspicion:
        """:param document: The suspect, as :meth:`as_json` wrote it.
        :return: The suspect it describes."""
        return cls(
            branch=document[SuspectKey.BRANCH],
            pull_request_number=document[SuspectKey.PULL_REQUEST_NUMBER],
            already_included=tuple(document[SuspectKey.ALREADY_INCLUDED]),
        )


class SuspectKey(StrEnum):
    """
    The field names the localised tip is held under in the state document.
    """

    BRANCH = "branch"
    """
    The tip itself.
    """

    PULL_REQUEST_NUMBER = "pull_request_number"
    """
    The fork pull request publishing it.
    """

    ALREADY_INCLUDED = "already_included"
    """
    What was in the build when it arrived.
    """


# %% the search, and what it does next


class LocalisationStage(StrEnum):
    """
    Which of the two rounds a search is in.
    """

    PREFIXES = "prefixes"
    """
    Adding the tips one at a time, to find whose arrival turns the library's tests.
    """

    NARROWING = "narrowing"
    """
    Pairing the tip that turned them with each earlier one, to find which it fails
    against alone.
    """


class LocalisationStep(StrEnum):
    """
    What a search wants done next, which is the whole of what a caller decides on.
    """

    WAIT = "wait"
    """
    A probe has not answered yet, so nothing can be read from the round.
    """

    NARROW = "narrow"
    """
    A prefix round localised a tip with earlier ones to try it against.
    """

    CONCLUDE = "conclude"
    """
    There is nothing left to dispatch, so what the search found is what it found.
    """


@dataclass(frozen=True)
class Localisation:
    """
    One search in flight, as the document a repeatable call reads and rewrites.

    The state is the document rather than the process, so the waiting stays with the
    caller and every invocation is one decision that can be read on its own - the same
    shape settling a candidate has.
    """

    library: LibraryUnderTest
    """
    Whose tests the probes run.
    """
    stage: LocalisationStage
    """
    Which round the probes belong to.
    """
    probes: tuple[Probe, ...]
    """
    The round's probes, in merge order.
    """
    suspect: TipUnderSuspicion | None = None
    """
    The tip the prefix round localised, once it has.
    """

    def as_json(self) -> dict[str, Any]:
        """:return: This search, keyed the way the document holds it."""
        return {
            LocalisationKey.LIBRARY: str(self.library),
            LocalisationKey.STAGE: str(self.stage),
            LocalisationKey.PROBES: [probe.as_json() for probe in self.probes],
            LocalisationKey.SUSPECT: (
                None if self.suspect is None else self.suspect.as_json()
            ),
        }

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> Localisation:
        """
        Read a search back out of the document a previous call wrote.

        :param document: The search, as :meth:`as_json` wrote it.
        :return: The search it describes.
        """
        suspect = document[LocalisationKey.SUSPECT]
        return cls(
            library=LibraryUnderTest(document[LocalisationKey.LIBRARY]),
            stage=LocalisationStage(document[LocalisationKey.STAGE]),
            probes=tuple(
                Probe.from_json(probe) for probe in document[LocalisationKey.PROBES]
            ),
            suspect=None if suspect is None else TipUnderSuspicion.from_json(suspect),
        )

    def answered_by(self, runs: Sequence[WorkflowRunRecord]) -> Localisation:
        """
        Read every probe's run, so the round is judged on one reading rather than on one
        per probe taken at different moments.

        :param runs: The probe workflow's runs, as the API answers them.
        :return: The same search with each probe's verdict as those runs report it.
        """
        return dataclasses.replace(
            self,
            probes=tuple(
                dataclasses.replace(probe, verdict=verdict_of(runs, probe.branch))
                for probe in self.probes
            ),
        )

    @property
    def next_step(self) -> LocalisationStep:
        """:return: What the search wants done next."""
        if not all(probe.has_answered for probe in self.probes):
            return LocalisationStep.WAIT
        if self.stage is LocalisationStage.NARROWING:
            return LocalisationStep.CONCLUDE
        localised = self.localised_suspect
        if localised is None or not localised.already_included:
            return LocalisationStep.CONCLUDE
        return LocalisationStep.NARROW

    @property
    def localised_suspect(self) -> TipUnderSuspicion | None:
        """
        The tip a prefix round blames, read off the first prefix that failed.

        The tips before it were in a build that passed, so the one that turned the
        library's tests is the one that arrived - the same rule the local search follows
        by stopping at the first prefix that fails.

        :return: The suspect, or ``None`` when every prefix passed.
        """
        if self.stage is LocalisationStage.NARROWING:
            return self.suspect
        for position, probe in enumerate(self.probes):
            if probe.failed:
                return TipUnderSuspicion(
                    branch=probe.tip,
                    pull_request_number=probe.pull_request_number,
                    already_included=tuple(
                        earlier.tip for earlier in self.probes[:position]
                    ),
                )
        return None

    @property
    def breaks_against(self) -> str | None:
        """
        The one earlier tip the suspect fails against on its own.

        Asked most-recent-first, the same way a merge conflict's partner is: that is the
        tip whose commits the failing one just met. ``None`` is a positive claim - that
        no single earlier tip reproduces the failure alone - so it is only ever answered
        from a narrowing round that looked, or from a suspect that had nothing before it.

        :return: The tip it fails against alone, or ``None`` when only the combination
            does.
        """
        if self.stage is not LocalisationStage.NARROWING:
            return None
        for probe in reversed(self.probes):
            if probe.failed:
                return probe.tip
        return None


class WorkflowRunField(StrEnum):
    """
    The fields of a workflow run this module reads.
    """

    NAME = "display_title"
    """
    What the run is called, which is its ``run-name`` evaluated.
    """
    STATUS = "status"
    """
    Whether it has finished.
    """
    CONCLUSION = "conclusion"
    """
    How it finished, absent until it has.
    """


def verdict_of(runs: Sequence[WorkflowRunRecord], build_branch: str) -> ChecksVerdict:
    """
    Read what the run judging one tree says so far.

    Found by the name it carries rather than by the reference it ran on: every probe of
    one localisation is dispatched on the same reference - the one carrying the pipeline
    - so only the name tells two of them apart. What the runs amount to is asked of
    :class:`~integration_verdict.ReportedChecks`, so a probe and a candidate cannot
    disagree about what finished, failed, or declined to judge.

    :param runs: The workflow's runs, as the API answers them.
    :param build_branch: The tree to read the verdict for.
    :return: What its run says, or :attr:`~integration_verdict.ChecksVerdict.ABSENT` when
        none has appeared.
    """
    wanted = probe_run_name(build_branch)
    return ReportedChecks.of(
        [
            {
                CheckRunField.NAME: str(run[WorkflowRunField.NAME]),
                CheckRunField.STATUS: str(run[WorkflowRunField.STATUS]),
                CheckRunField.CONCLUSION: run.get(WorkflowRunField.CONCLUSION),
            }
            for run in runs
            if run.get(WorkflowRunField.NAME) == wanted
        ]
    ).verdict


class LocalisationKey(StrEnum):
    """
    The field names a search is held under in the document that carries it between
    calls.
    """

    LIBRARY = "library"
    """
    Whose tests the probes run.
    """
    STAGE = "stage"
    """
    Which round the probes belong to.
    """
    PROBES = "probes"
    """
    The round's probes, in merge order.
    """
    SUSPECT = "suspect"
    """
    The tip the prefix round localised, once it has.
    """


def dispatch(
    fork: DispatchedWorkflowRuns,
    reference: str,
    library: LibraryUnderTest,
    probes: Sequence[Probe],
) -> None:
    """
    Start a run for every probe of one round, at once.

    The probes are independent, so a round costs one run's wall clock rather than one per
    tip - which is what makes a linear scan the right shape here, where a bisection would
    spend a sequential round to save runs nobody is short of, and would have to assume a
    monotonicity this does not.

    :param fork: The fork to dispatch on.
    :param reference: The reference carrying the pipeline, which is what a dispatch runs
        the workflow file from.
    :param library: Whose tests to run over each tree.
    :param probes: The round's probes.
    """
    for probe in probes:
        fork.dispatch_workflow(
            workflow=PROBE_WORKFLOW_FILE,
            reference=reference,
            inputs={
                ProbeWorkflowInput.BUILD: probe.branch,
                ProbeWorkflowInput.LIBRARY: str(library),
            },
        )


def library_a_candidate_failed_on(
    checks: ReportedChecks,
) -> LibraryUnderTest | None:
    """
    Read which library a candidate's red is about, where it is about one at all.

    The first failing check that names one, in the order the API reported them: a
    candidate can fail several matrix jobs at once, and localising the first is what
    tells anybody which pair of branches to look at - the rest of the matrix reruns on the
    branch that gets blocked for it.

    :param checks: What the candidate's checks said.
    :return: The library to re-run, or ``None`` when nothing that failed names one.
    """
    for run in checks.failed:
        library = LibraryUnderTest.named_by(run.name)
        if library is not None:
            return library
    return None
