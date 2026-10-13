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
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path

import yaml

from basstler.plan_model import PlanManifest
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% the limits


class Measure(Enum):
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

    def __init__(self, description: str, maximum: int) -> None:
        self.description = description
        """
        What is counted, as a phrase following the count.
        """
        self.maximum = maximum
        """
        The most a document may hold.
        """


# %% violations


@dataclass(frozen=True)
class SizeViolation:
    """
    One measure a document holds more of than its limit allows.
    """

    measure: Measure
    """
    What was counted.
    """

    location: str
    """
    Where in the document it was counted.
    """

    measured: int
    """
    How much the document holds.
    """

    def __str__(self) -> str:
        """
        :return: Where, how much, and the limit.
        """
        return (
            f"{self.location}: {self.measured} {self.measure.description}, "
            f"over the limit of {self.measure.maximum}"
        )


@dataclass(frozen=True)
class RoadmapFormatViolation:
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
        """
        :return: The line and what a roadmap may hold instead.
        """
        return (
            f"roadmap line {self.line_number} is not a '- ' entry or its indented "
            f"continuation: {self.line[:80]!r}"
        )


Violation = SizeViolation | RoadmapFormatViolation
"""
Anything that makes a document refused.
"""


def measured_violation(
    measure: Measure, location: str, measured: int
) -> list[SizeViolation]:
    """
    :param measure: What was counted.
    :param location: Where it was counted.
    :param measured: How much was counted.
    :return: The violation, when *measured* is over the limit; otherwise nothing.
    """
    if measured <= measure.maximum:
        return []
    return [SizeViolation(measure=measure, location=location, measured=measured)]


class LimitedDocument(Enum):
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

    def __init__(self, description: str, content_to_keep: str) -> None:
        self.description = description
        """
        The document, as a phrase.
        """
        self.content_to_keep = content_to_keep
        """
        What the document is for, which is all it should hold.
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


def manifest_violations(manifest: PlanManifest) -> list[SizeViolation]:
    """
    :param manifest: The manifest to measure.
    :return: Every limit the manifest breaks.
    """
    violations = measured_violation(
        Measure.ITEM_COUNT, "plan", len(manifest.items)
    ) + measured_violation(
        Measure.DESCRIPTION_LENGTH, "plan description", len(manifest.description)
    )
    for item in manifest.items:
        location = f"item {item.identifier!r}"
        violations += measured_violation(Measure.NOTE_LENGTH, location, len(item.notes))
        violations += measured_violation(
            Measure.BLOCKER_COUNT, location, len(item.blockers)
        )
        for blocker in item.blockers:
            violations += measured_violation(
                Measure.BLOCKER_LENGTH, location, len(blocker)
            )
    return violations


ROADMAP_TITLE = re.compile(r"^# \S")
"""
The roadmap's one heading, its first line.
"""

ROADMAP_ENTRY = re.compile(r"^- \S")
"""
The first line of an entry.
"""

ROADMAP_CONTINUATION = re.compile(r"^  \S")
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
            if line_number == 1 and ROADMAP_TITLE.match(line):
                continue
            if ROADMAP_ENTRY.match(line):
                entries.append(line[2:].strip())
            elif ROADMAP_CONTINUATION.match(line) and entries:
                entries[-1] = f"{entries[-1]} {line.strip()}"
            else:
                format_violations.append(RoadmapFormatViolation(line_number, line))
        return cls(entries=entries, format_violations=format_violations)

    def violations(self) -> list[Violation]:
        """
        :return: Every limit the roadmap breaks.
        """
        violations: list[Violation] = list(self.format_violations)
        violations += measured_violation(
            Measure.ROADMAP_ENTRY_COUNT, "roadmap", len(self.entries)
        )
        for number, entry in enumerate(self.entries, start=1):
            violations += measured_violation(
                Measure.ROADMAP_ENTRY_LENGTH, f"roadmap entry {number}", len(entry)
            )
        return violations


def progress_violations(text: str) -> list[SizeViolation]:
    """
    :param text: A pull request's progress notes.
    :return: Every limit the notes break.
    """
    return measured_violation(
        Measure.PROGRESS_LENGTH, "progress notes", len(text.strip())
    )


# %% reading and writing files


def read_manifest(path: Path) -> PlanManifest:
    """
    :param path: A ``plan.yaml`` file.
    :return: The manifest it holds.
    """
    return PlanManifest(yaml.safe_load(path.read_text()) or {})


def write_manifest(manifest: PlanManifest, path: Path) -> None:
    """
    Write a manifest in block style, keeping its keys in their order.

    :param manifest: The manifest to write.
    :param path: Where to write it.
    """
    path.write_text(
        yaml.safe_dump(manifest.content, sort_keys=False, allow_unicode=True, width=88)
    )


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
        original = read_manifest(self.manifest)
        manifest = original.without_landed_items()
        if not manifest.items:
            shutil.rmtree(destination.manifest.parent, ignore_errors=True)
            return StagedPlan.REMOVED
        violations: list[Violation] = list(manifest_violations(manifest))
        violations += Roadmap.from_text(self.roadmap.read_text()).violations()
        if violations:
            raise DocumentOverLimitError(LimitedDocument.PLAN, violations)
        destination.manifest.parent.mkdir(parents=True, exist_ok=True)
        if original.landed_identifiers:
            write_manifest(manifest, destination.manifest)
        else:
            shutil.copyfile(self.manifest, destination.manifest)
        shutil.copyfile(self.roadmap, destination.roadmap)
        return StagedPlan.SAVED


def check_progress_file(path: Path) -> None:
    """
    :param path: A pull request's progress notes.
    :raises DocumentOverLimitError: If they break a limit.
    """
    violations = progress_violations(path.read_text())
    if violations:
        raise DocumentOverLimitError(LimitedDocument.PROGRESS_NOTES, list(violations))


# %% command line


def build_parser() -> argparse.ArgumentParser:
    """
    :return: The parser for the two subcommands.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subcommands = parser.add_subparsers(dest="subcommand", required=True)
    stage = subcommands.add_parser(
        "stage",
        help="Write a plan without its landed items, or delete it once all have landed",
    )
    stage.add_argument("manifest_path", type=Path)
    stage.add_argument("roadmap_path", type=Path)
    stage.add_argument("--manifest-destination", required=True, type=Path)
    stage.add_argument("--roadmap-destination", required=True, type=Path)
    check_progress = subcommands.add_parser(
        "check-progress", help="Refuse progress notes over their limit"
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
        if arguments.subcommand == "stage":
            source = PlanFiles(arguments.manifest_path, arguments.roadmap_path)
            destination = PlanFiles(
                arguments.manifest_destination, arguments.roadmap_destination
            )
            logger.info(source.stage(destination))
        else:
            check_progress_file(arguments.progress_path)
    except DocumentOverLimitError as error:
        logger.error(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
