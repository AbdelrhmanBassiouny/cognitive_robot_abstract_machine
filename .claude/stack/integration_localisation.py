"""
Localising a candidate's red to the tip whose arrival turned it.

A candidate that fails on a matrix job names a failing check and nothing else. The local
search cannot reproduce it: that re-runs the configured tooling suite, and a matrix job
runs one library's own tests, so the two see different failures by construction. This
re-runs the failing library over each prefix of the merge order instead, as a dispatched
run per prefix, and reports the same finding the local search reports.
"""

from __future__ import annotations

import re
from enum import StrEnum

PROBE_WORKFLOW_FILE = "integration-probe.yml"
"""
The workflow one probe is a run of.

A file name rather than a numeric identifier, which is what the dispatch endpoint takes
and what keeps this readable in a repository that has never dispatched it.
"""

PROBE_RUN_NAME_PREFIX = "Integration probe over "
"""
Opens the name a probe's run carries, so a reader can tell one probe's run from another's.

Every probe of one localisation is dispatched on the same reference - the one carrying
the pipeline - so the reference cannot tell them apart and the name has to.
"""

MATRIX_CHECK_PATTERN = re.compile(r"\(([^)]+)\)")
"""
Finds the library a matrix job's check name is for.

The matrix names each job ``test_each_lib (<lib>)``, optionally suffixed with the reusable
job's own name; the library is what the parentheses hold.
"""


class ProbeWorkflowInput(StrEnum):
    """
    What a probe has to be told, because its run starts on neither.
    """

    BUILD = "build"
    """The assembled prefix to check out and test."""

    LIBRARY = "library"
    """Which library's tests to run over it."""


class LibraryUnderTest(StrEnum):
    """
    The libraries the matrix runs a job for, which are the failures this can localise.

    A failing check naming one of these is re-runnable over a prefix; a failing check
    naming none of them is not this search's to answer, and saying so is better than
    probing something that cannot reproduce it.
    """

    GISKARDPY = "giskardpy"
    """The motion-planning library."""

    KRROOD = "krrood"
    """The knowledge-representation library."""

    SEMANTIC_DIGITAL_TWIN = "semantic_digital_twin"
    """The world-model library."""

    CORAPLEX = "coraplex"
    """The task-representation library."""

    RANDOM_EVENTS = "random_events"
    """The event-algebra library."""

    PROBABILISTIC_MODEL = "probabilistic_model"
    """The probabilistic-model library."""

    PHYSICS_SIMULATORS = "physics_simulators"
    """The simulator adapters."""

    ROBOKUDO = "robokudo"
    """The perception library."""

    SEGMIND = "segmind"
    """The segmentation library."""

    EXPERIMENTS = "experiments"
    """The experiment harnesses."""

    VERSION = "version"
    """The version-consistency checks."""

    COGNITIVE_ROBOT_ABSTRACT_MACHINE = "cognitive_robot_abstract_machine"
    """The umbrella package."""

    @classmethod
    def named_by(cls, check: str) -> LibraryUnderTest | None:
        """Read which library a failing check is about.

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
    """Name a probe's run after the tree it tests.

    :param build_branch: The assembled prefix under test.
    :return: The name its run carries, which is how it is found again.
    """
    return f"{PROBE_RUN_NAME_PREFIX}{build_branch}"
