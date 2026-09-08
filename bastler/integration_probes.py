"""
The probes a localisation dispatches, and what each one's run says.

A probe is one assembled tree published under a name of its own, and a dispatched run
judging it. Every probe of one round is dispatched on the same reference - the one
carrying the pipeline - so the reference cannot tell two of them apart and the name has
to.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


from bastler.maintenance_github import (  # noqa: E402
    DispatchedWorkflowRuns,
    WorkflowRunRecord,
)
from bastler.integration_verdict import (  # noqa: E402
    ChecksVerdict,
    CheckRunField,
    ReportedChecks,
)
from bastler.matrix_libraries import LibraryUnderTest  # noqa: E402
from bastler.workflow_document import WorkflowFile  # noqa: E402

PROBE_RUN_NAME_PREFIX = "Integration probe over "
"""
Opens the name a probe's run carries, so a reader can tell one probe's run from
another's.

Every probe of one localisation is dispatched on the same reference - the one carrying
the pipeline - so the reference cannot tell them apart and the name has to.
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


def probe_run_name(build_branch: str) -> str:
    """
    Name a probe's run after the tree it tests.

    :param build_branch: The assembled prefix under test.
    :return: The name its run carries, which is how it is found again.
    """
    return f"{PROBE_RUN_NAME_PREFIX}{build_branch}"


# %% what one probe is, and what its run says


@dataclass(frozen=True)
class DispatchedProbe:
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

    def to_json(self) -> dict[str, Any]:
        """:return: This probe, keyed the way the state document holds it."""
        return {
            ProbeKey.BRANCH: self.branch,
            ProbeKey.TIP: self.tip,
            ProbeKey.PULL_REQUEST_NUMBER: self.pull_request_number,
            ProbeKey.VERDICT: str(self.verdict),
        }

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> DispatchedProbe:
        """:param document: One probe, as :meth:`to_json` wrote it.
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


# %% what a probe's run says


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


# %% dispatching a round


def dispatch(
    fork: DispatchedWorkflowRuns,
    reference: str,
    library: LibraryUnderTest,
    probes: Sequence[DispatchedProbe],
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
            workflow=str(WorkflowFile.INTEGRATION_PROBE),
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
