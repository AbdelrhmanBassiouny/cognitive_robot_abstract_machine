"""
The size every plan document and every pull request's progress notes are held to.

Everything a session reads about a plan or a pull request costs context on every session
that loads it, so each document may hold only what a future session needs to act: the
next step, what blocks it, and the standing rules of the plan. History lives in git and on
the pull requests themselves. The save hooks run these checks and refuse a save that
breaks one, so the limits hold without anyone having to remember them.

Usage:
    python3 -m basstler.plan_size_limits stage <manifest-file> <roadmap-file> \\
        --manifest-destination <path> --roadmap-destination <path>
    python3 -m basstler.plan_size_limits check-progress <progress-file>
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path

from basstler.plan_model import PlanManifest
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% the limits


@dataclass(frozen=True)
class SizeLimit:
    """
    The most of one quantity a document may hold.
    """

    description: str
    """
    What is counted, as a phrase following the count.
    """

    maximum: int
    """
    The most a document may hold.
    """


class Measure(SizeLimit, Enum):
    """
    One quantity a document is measured by, with the most of it a document may hold.
    """

    ITEM_COUNT = ("items in the plan", 15)
    """
    A plan larger than this is two plans.
    """

    DESCRIPTION_LENGTH = ("characters in the plan's description", 600)
    """
    What the plan is for, in a paragraph.
    """

    NOTE_LENGTH = ("characters in an item's notes", 600)
    """
    What the item's next session needs: its scope and the decisions that bind it.
    """

    BLOCKER_COUNT = ("blockers on an item", 2)
    """
    The things an item currently waits on.
    """

    BLOCKER_LENGTH = ("characters in one blocker", 300)
    """
    One sentence naming what is awaited and from whom.
    """

    ROADMAP_ENTRY_COUNT = ("entries in the roadmap", 12)
    """
    The plan's standing rules, one entry each.
    """

    ROADMAP_ENTRY_LENGTH = ("characters in one roadmap entry", 400)
    """
    One standing rule and the reason it exists.
    """

    PROGRESS_LENGTH = ("characters in the progress notes", 2000)
    """
    A pull request's plan, what is done and what is next.
    """

    def violations(
        self, location: DocumentLocation, measured: int
    ) -> list[SizeViolation]:
        """
        :param location: Where the quantity was counted.
        :param measured: How much was counted.
        :return: The violation, when *measured* is over the limit; otherwise nothing.
        """
        if measured <= self.maximum:
            return []
        return [SizeViolation(measure=self, location=location, measured=measured)]


# %% violations


class DocumentPart(StrEnum):
    """
    A part of a document a quantity is counted in.
    """

    PLAN = "plan"
    """
    The plan as a whole.
    """

    PLAN_DESCRIPTION = "plan description"
    """
    The plan's description.
    """

    ITEM = "item"
    """
    One of the plan's items.
    """

    ROADMAP = "roadmap"
    """
    The roadmap as a whole.
    """

    ROADMAP_ENTRY = "roadmap entry"
    """
    One of the roadmap's entries.
    """

    PROGRESS_NOTES = "progress notes"
    """
    A pull request's progress notes.
    """


@dataclass(frozen=True)
class DocumentLocation:
    """
    Where in a document a quantity was counted.
    """

    part: DocumentPart
    """
    The part of the document.
    """

    subject: str | int | None = None
    """
    Which one of several such parts: an item's id or an entry's number.
    """

    def __str__(self) -> str:
        """
        :return: The part, followed by the subject when there is one.
        """
        if self.subject is None:
            return self.part
        return f"{self.part} {self.subject!r}"


@dataclass(frozen=True)
class Violation(ABC):
    """
    Anything that makes a document refused.
    """

    @abstractmethod
    def __str__(self) -> str:
        """
        :return: What is wrong and where, as one line.
        """


@dataclass(frozen=True)
class SizeViolation(Violation):
    """
    One measure a document holds more of than its limit allows.
    """

    measure: Measure
    """
    What was counted.
    """

    location: DocumentLocation
    """
    Where in the document it was counted.
    """

    measured: int
    """
    How much the document holds.
    """

    def __str__(self) -> str:
        return (
            f"{self.location}: {self.measured} {self.measure.description}, "
            f"over the limit of {self.measure.maximum}"
        )


@dataclass(frozen=True)
class RoadmapFormatViolation(Violation):
    """
    A roadmap line that is neither the title, an entry, nor an entry's continuation.
    """

    line_number: int
    """
    The line's number, counted from one.
    """

    line: str
    """
    The line as written.
    """

    def __str__(self) -> str:
        return (
            f"roadmap line {self.line_number} is not a '- ' entry or its indented "
            f"continuation: {self.line[:80]!r}"
        )


@dataclass(frozen=True)
class DocumentSummary:
    """
    How a refusal names a document, and what it tells the author to keep.
    """

    description: str
    """
    The document, as a phrase.
    """

    content_to_keep: str
    """
    What the document is for, which is all it should hold.
    """


class LimitedDocument(DocumentSummary, Enum):
    """
    A document the limits are enforced on, with what to keep when it is refused.
    """

    PLAN = ("the plan", "the next step, what blocks it and the plan's standing rules")
    """
    A plan's manifest and roadmap.
    """

    PROGRESS_NOTES = ("the progress notes", "the plan, what is done and what is next")
    """
    A pull request's progress notes.
    """


@dataclass
class DocumentOverLimitError(Exception):
    """
    Raised when a document breaks one of its limits.
    """

    document: LimitedDocument
    """
    The document that was refused.
    """

    violations: list[Violation]
    """
    Every limit the document breaks.
    """

    def __str__(self) -> str:
        """
        :return: One line per violation, then what the document should hold instead.
        """
        return "\n".join(
            [f"Refusing to save {self.document.description}:"]
            + [f"  {violation}" for violation in self.violations]
            + [
                f"Keep only {self.document.content_to_keep}; history belongs in git "
                "and on the pull requests."
            ]
        )


# %% the documents


class MeasuredDocument(ABC):
    """
    A document held to the limits.
    """

    @property
    @abstractmethod
    def limited_document(self) -> LimitedDocument:
        """
        :return: Which document this is, as a refusal names it.
        """

    @abstractmethod
    def violations(self) -> list[Violation]:
        """
        :return: Every limit the document breaks.
        """

    def check(self) -> None:
        """
        :raises DocumentOverLimitError: If the document breaks a limit.
        """
        violations = self.violations()
        if violations:
            raise DocumentOverLimitError(self.limited_document, violations)


class RoadmapLine(StrEnum):
    """
    The shapes a roadmap line may take, as the pattern each one matches.
    """

    TITLE = r"^# \S"
    """
    The roadmap's one heading, its first line.
    """

    ENTRY = r"^- \S"
    """
    The first line of an entry.
    """

    CONTINUATION = r"^  \S"
    """
    A further line of the entry above it.
    """


@dataclass(frozen=True)
class Roadmap:
    """
    A plan's ``roadmap.md``: a title, then the plan's standing rules as a list of
    entries.
    """

    entries: list[str]
    """
    Each entry with its line wrapping undone.
    """

    format_violations: list[RoadmapFormatViolation]
    """
    The lines that fit none of the roadmap's shapes.
    """

    @classmethod
    def from_text(cls, text: str) -> Roadmap:
        """
        :param text: The roadmap as written.
        :return: Its entries, and every line that is not part of one.
        """
        entries: list[str] = []
        format_violations: list[RoadmapFormatViolation] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            if line_number == 1 and re.match(RoadmapLine.TITLE, line):
                continue
            if re.match(RoadmapLine.ENTRY, line):
                entries.append(line[2:].strip())
            elif re.match(RoadmapLine.CONTINUATION, line) and entries:
                entries[-1] = f"{entries[-1]} {line.strip()}"
            else:
                format_violations.append(RoadmapFormatViolation(line_number, line))
        return cls(entries=entries, format_violations=format_violations)

    def violations(self) -> list[Violation]:
        """
        :return: Every limit the roadmap breaks.
        """
        violations: list[Violation] = list(self.format_violations)
        violations += Measure.ROADMAP_ENTRY_COUNT.violations(
            DocumentLocation(DocumentPart.ROADMAP), len(self.entries)
        )
        for number, entry in enumerate(self.entries, start=1):
            violations += Measure.ROADMAP_ENTRY_LENGTH.violations(
                DocumentLocation(DocumentPart.ROADMAP_ENTRY, number), len(entry)
            )
        return violations


@dataclass(frozen=True)
class Plan(MeasuredDocument):
    """
    A plan's manifest and roadmap, measured together.
    """

    manifest: PlanManifest
    """
    The plan's items and their state.
    """

    roadmap: Roadmap
    """
    The plan's standing rules.
    """

    @property
    def limited_document(self) -> LimitedDocument:
        return LimitedDocument.PLAN

    def manifest_violations(self) -> list[Violation]:
        """
        :return: Every limit the manifest breaks.
        """
        manifest = self.manifest
        violations: list[Violation] = []
        violations += Measure.ITEM_COUNT.violations(
            DocumentLocation(DocumentPart.PLAN), len(manifest.items)
        )
        violations += Measure.DESCRIPTION_LENGTH.violations(
            DocumentLocation(DocumentPart.PLAN_DESCRIPTION), len(manifest.description)
        )
        for item in manifest.items:
            location = DocumentLocation(DocumentPart.ITEM, item.identifier)
            violations += Measure.NOTE_LENGTH.violations(location, len(item.notes))
            violations += Measure.BLOCKER_COUNT.violations(location, len(item.blockers))
            for blocker in item.blockers:
                violations += Measure.BLOCKER_LENGTH.violations(location, len(blocker))
        return violations

    def violations(self) -> list[Violation]:
        return self.manifest_violations() + self.roadmap.violations()


@dataclass(frozen=True)
class ProgressNotes(MeasuredDocument):
    """
    A pull request's progress notes.
    """

    text: str
    """
    The notes as written.
    """

    @classmethod
    def from_file(cls, path: Path) -> ProgressNotes:
        """
        :param path: A file holding a pull request's progress notes.
        :return: The notes it holds.
        """
        return cls(path.read_text())

    @property
    def limited_document(self) -> LimitedDocument:
        return LimitedDocument.PROGRESS_NOTES

    def violations(self) -> list[Violation]:
        return Measure.PROGRESS_LENGTH.violations(
            DocumentLocation(DocumentPart.PROGRESS_NOTES), len(self.text.strip())
        )


# %% staging a plan


class StagedPlan(StrEnum):
    """
    What staging a plan's files left at their destination.
    """

    SAVED = "saved"
    """
    The pruned manifest and the roadmap were written.
    """

    REMOVED = "removed"
    """
    Every item had landed, so the plan's directory was deleted.
    """


@dataclass(frozen=True)
class PlanFiles:
    """
    A plan's manifest and roadmap.
    """

    manifest: Path
    """
    The plan's ``plan.yaml``.
    """

    roadmap: Path
    """
    The plan's ``roadmap.md``.
    """

    def stage(self, destination: PlanFiles) -> StagedPlan:
        """
        Write the plan, without its landed items, to *destination*; a plan with no
        items left is finished, and its directory is deleted instead. A manifest with
        nothing landed is copied unchanged.

        :param destination: Where the plan is saved; both files share one directory.
        :raises DocumentOverLimitError: If the pruned plan breaks a limit.
        :return: Which of the two happened.
        """
        original = PlanManifest.from_file(self.manifest)
        manifest = original.without_landed_items()
        if not manifest.items:
            shutil.rmtree(destination.manifest.parent, ignore_errors=True)
            return StagedPlan.REMOVED
        Plan(manifest, Roadmap.from_text(self.roadmap.read_text())).check()
        destination.manifest.parent.mkdir(parents=True, exist_ok=True)
        if original.landed_identifiers:
            manifest.write(destination.manifest)
        else:
            shutil.copyfile(self.manifest, destination.manifest)
        shutil.copyfile(self.roadmap, destination.roadmap)
        return StagedPlan.SAVED


# %% command line


class SizeLimitCommand(StrEnum):
    """
    The subcommands this module's command line runs.
    """

    STAGE = "stage"
    """
    Write a plan without its landed items, or delete it once all have landed.
    """

    CHECK_PROGRESS = "check-progress"
    """
    Refuse progress notes over their limit.
    """


class SizeLimitOption(StrEnum):
    """
    The options this module's command line takes.
    """

    MANIFEST_DESTINATION = "--manifest-destination"
    """
    Where :attr:`SizeLimitCommand.STAGE` writes the manifest.
    """

    ROADMAP_DESTINATION = "--roadmap-destination"
    """
    Where :attr:`SizeLimitCommand.STAGE` writes the roadmap.
    """


def build_parser() -> argparse.ArgumentParser:
    """
    :return: The parser for the two subcommands.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subcommands = parser.add_subparsers(dest="subcommand", required=True)
    stage = subcommands.add_parser(
        SizeLimitCommand.STAGE,
        help="Write a plan without its landed items, or delete it once all have landed",
    )
    stage.add_argument("manifest_path", type=Path)
    stage.add_argument("roadmap_path", type=Path)
    stage.add_argument(SizeLimitOption.MANIFEST_DESTINATION, required=True, type=Path)
    stage.add_argument(SizeLimitOption.ROADMAP_DESTINATION, required=True, type=Path)
    check_progress = subcommands.add_parser(
        SizeLimitCommand.CHECK_PROGRESS, help="Refuse progress notes over their limit"
    )
    check_progress.add_argument("progress_path", type=Path)
    return parser


def main() -> int:
    """
    Run the requested subcommand. ``stage`` prints what it left at the destination; a
    document over its limits exits with status 1 and names every violation on standard
    error.
    """
    arguments = build_parser().parse_args()
    try:
        if arguments.subcommand == SizeLimitCommand.STAGE:
            source = PlanFiles(arguments.manifest_path, arguments.roadmap_path)
            destination = PlanFiles(
                arguments.manifest_destination, arguments.roadmap_destination
            )
            logger.info(source.stage(destination))
        else:
            ProgressNotes.from_file(arguments.progress_path).check()
    except DocumentOverLimitError as error:
        logger.error(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
