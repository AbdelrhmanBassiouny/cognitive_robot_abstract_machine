"""
One search for the tip whose arrival turned a library's tests, and what it does next.

Two rounds: which prefix of the merge order turned them, then which earlier tip the tip
that did fails against on its own. The second exists because a report naming nothing is
a positive claim - that no single earlier tip reproduces the failure alone - and an
un-narrowed report would state it unchecked.

Repeatable rather than waited on: what has been established lives in a document, so a
later call picks up a search sharing nothing with the one that started it.
"""

from __future__ import annotations

import dataclasses
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


from bastler.matrix_libraries import LibraryUnderTest  # noqa: E402
from bastler.integration_probes import DispatchedProbe, verdict_of  # noqa: E402


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

    def to_json(self) -> dict[str, Any]:
        """:return: The suspect, keyed the way the state document holds it."""
        return {
            SuspectKey.BRANCH: self.branch,
            SuspectKey.PULL_REQUEST_NUMBER: self.pull_request_number,
            SuspectKey.ALREADY_INCLUDED: list(self.already_included),
        }

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> TipUnderSuspicion:
        """:param document: The suspect, as :meth:`to_json` wrote it.
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
    probes: tuple[DispatchedProbe, ...]
    """
    The round's probes, in merge order.
    """
    suspect: TipUnderSuspicion | None = None
    """
    The tip the prefix round localised, once it has.
    """

    def to_json(self) -> dict[str, Any]:
        """:return: This search, keyed the way the document holds it."""
        return {
            LocalisationKey.LIBRARY: str(self.library),
            LocalisationKey.STAGE: str(self.stage),
            LocalisationKey.PROBES: [probe.to_json() for probe in self.probes],
            LocalisationKey.SUSPECT: (
                None if self.suspect is None else self.suspect.to_json()
            ),
        }

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> Localisation:
        """
        Read a search back out of the document a previous call wrote.

        :param document: The search, as :meth:`to_json` wrote it.
        :return: The search it describes.
        """
        suspect = document[LocalisationKey.SUSPECT]
        return cls(
            library=LibraryUnderTest(document[LocalisationKey.LIBRARY]),
            stage=LocalisationStage(document[LocalisationKey.STAGE]),
            probes=tuple(
                DispatchedProbe.from_json(probe)
                for probe in document[LocalisationKey.PROBES]
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
