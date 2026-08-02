#!/usr/bin/env python3
"""
Machine-readable model of the prompt documents the cloud Routine runs on.

``ROUTINE.md`` is the prompt the Routine executes and ``POINTER.md`` is the short prompt
registered at claude.ai/code/routines that resolves it. Both are prose, so nothing in
them can be imported and asserted against directly. This module declares the landmarks
and rules they are required to contain and owns the extraction their contract tests
need, so renaming a section is one edit here rather than one per assertion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import ClassVar, Protocol

# %% documents

ROUTINE_DOCUMENT = Path(__file__).with_name("ROUTINE.md")
"""
The prompt the Routine reads from git and executes each run.
"""

POINTER_DOCUMENT = Path(__file__).with_name("POINTER.md")
"""
The pointer prompt registered with the cloud Routine, which resolves the routine
document.
"""

# %% vocabulary the documents are required to use


class GitHubMcpTool(StrEnum):
    """
    GitHub MCP server tools the documents prescribe or forbid by name.
    """

    UPDATE_PULL_REQUEST = "update_pull_request"
    CREATE_PULL_REQUEST = "create_pull_request"
    SUBSCRIBE_PULL_REQUEST_ACTIVITY = "subscribe_pr_activity"


class PromptDirective(StrEnum):
    """
    Words an executable prompt uses to mark an instruction as non-negotiable.
    """

    HARD_RULES = "HARD RULES"
    NEVER = "NEVER"


class PointerPlaceholder(StrEnum):
    """
    Tokens in the pointer prompt a fork owner substitutes before registering it.
    """

    FORK_REPOSITORY = "<FORK_REPOSITORY>"
    TOOLING_BRANCH = "<TOOLING_BRANCH>"


@dataclass(frozen=True, eq=False)
class LandmarkSpecification:
    """
    One piece of literal text a prompt document is required to contain.
    """

    text: str
    """
    The literal text, exactly as it appears in the document.
    """

    purpose: str
    """
    What the document's contract depends on this landmark for.
    """


@dataclass(frozen=True, eq=False)
class RuleSpecification(LandmarkSpecification):
    """
    A rule the prompt documents state, together with the refusal that motivates it.

    A rule that exists only to steer a session away from a failing client is not fully
    specified by its heading: the status code and the client that earns it are what a
    session actually meets, and the document has to name both for the rule to be
    recognisable when it happens.
    """

    refused_client: str
    """
    The client whose attempt at this operation is rejected.
    """

    refusal_status_code: str
    """
    The status the refused client receives, as it appears in the document.
    """


class PromptLandmark(LandmarkSpecification, Enum):
    """
    The structural landmarks the prompt documents are located by.

    Section extraction slices between these, so each text must occur exactly where the
    section it opens begins, and must not occur earlier in the document.
    """

    EXECUTABLE_PROMPT_FENCE = (
        "```text",
        "Opens the block the Routine executes; surrounding prose is commentary.",
    )
    CLOSING_FENCE = (
        "\n```",
        "Closes the executable block.",
    )
    HARD_RULES = (
        f"{PromptDirective.HARD_RULES} so you never drift into review work:",
        "Heads the rules that must bind before any file is read.",
    )
    PRE_FLIGHT = (
        "PRE-FLIGHT",
        "Heads the checks that precede every push, and so ends the hard rules.",
    )
    SETUP = (
        "\nSETUP\n",
        "Heads the steps that make the run's preconditions true.",
    )
    FORK_MAIN_UPDATE = (
        "1. UPDATE FORK MAIN FIRST",
        "First numbered setup step, and so ends step 0.",
    )
    PHASE_ONE = (
        "PHASE 1 - LANDED PARENTS",
        "Heads the phase owning every reparent instruction.",
    )
    PHASE_TWO = (
        "PHASE 2 - RESTACK",
        "Heads the restack phase, and so ends Phase 1.",
    )
    ORPHANED_CHILD_SWEEP = (
        "REPARENT EVERY ORPHANED CHILD",
        "Opens the first of the two reparent sites.",
    )
    NATIVE_STACK_MEMBERS = (
        "NATIVE-STACK MEMBERS.",
        "Opens the sequence for children the plain retarget cannot move.",
    )
    MERGED_PARENT_LIST = (
        "For each OPEN fork PR (head branch B)",
        "Opens the second of the two reparent sites.",
    )


class PromptRule(RuleSpecification, Enum):
    """
    The rules the prompt documents are required to state, and what refusal each avoids.
    """

    BASE_CHANGE = (
        "BASE CHANGES GO THROUGH THE GITHUB MCP SERVER.",
        "Opens the rule naming the one client able to retarget a base.",
        "curl",
        "403",
    )


class DocumentLandmark(Protocol):
    """
    Anything a prompt document can be located by, named so a failure can report it.

    Declared structurally so a new kind of landmark needs no edit here.
    """

    name: str
    """
    The identifier the declaring enum gives it.
    """

    text: str
    """
    The literal text to find in the document.
    """

    purpose: str
    """
    What the document's contract depends on it for.
    """


@dataclass
class LandmarkNotFoundError(LookupError):
    """
    Raised when a prompt document no longer contains a landmark it is required to
    contain.
    """

    landmark: DocumentLandmark
    """
    The landmark that could not be located.
    """

    document: Path
    """
    The document that was searched.
    """

    def __str__(self) -> str:
        """
        :return: The missing landmark and what the contract needed it for.
        """
        return (
            f"{self.document.name} no longer contains {self.landmark.name}: "
            f"{self.landmark.text!r} ({self.landmark.purpose})"
        )


# %% the documents themselves


@dataclass(frozen=True)
class PromptDocument:
    """
    A markdown document carrying an executable prompt, and the parts of it callers
    assert on.
    """

    PARAGRAPH_BREAK: ClassVar[str] = "\n\n"
    """
    Separator ending the paragraph :meth:`paragraph` returns.
    """

    text: str
    """
    The document's full text.
    """

    path: Path
    """
    Where the text was read from.
    """

    @classmethod
    def load(cls, path: Path = ROUTINE_DOCUMENT) -> PromptDocument:
        """
        Read a prompt document from disk.

        :param path: The document to read.
        :return: The loaded document.
        """
        return cls(path.read_text(), path)

    def position(self, landmark: DocumentLandmark, start: int = 0) -> int:
        """
        Locate a landmark.

        :param landmark: The landmark to find.
        :param start: Index to search from.
        :return: Index at which the landmark's text begins.
        :raises LandmarkNotFoundError: If the document does not contain it.
        """
        index = self.text.find(landmark.text, start)
        if index < 0:
            raise LandmarkNotFoundError(landmark, self.path)
        return index

    def occurrences(self, landmark: DocumentLandmark) -> int:
        """
        Count how often a landmark appears.

        :param landmark: The landmark to count.
        :return: Number of occurrences.
        """
        return self.text.count(landmark.text)

    def section(
        self, start: DocumentLandmark, end: DocumentLandmark | None = None
    ) -> str:
        """
        Extract the text between two landmarks.

        :param start: Landmark opening the section.
        :param end: Landmark opening the next section; omit to run to the document's
            end.
        :return: The section's text, including *start*'s own text.
        :raises LandmarkNotFoundError: If either landmark is missing.
        """
        begin = self.position(start)
        if end is None:
            return self.text[begin:]
        return self.text[begin : self.position(end, begin)]

    def paragraph(self, landmark: DocumentLandmark) -> str:
        """
        Extract the single paragraph a landmark opens.

        :param landmark: Landmark opening the paragraph.
        :return: The text from the landmark up to the next blank line.
        :raises LandmarkNotFoundError: If the landmark is missing.
        """
        begin = self.position(landmark)
        return self.text[begin : self.text.index(self.PARAGRAPH_BREAK, begin)]

    def executable_prompt(self) -> str:
        """
        Extract the fenced block, the way the Routine's own prompt does.

        :return: The text between the opening and closing fences.
        :raises LandmarkNotFoundError: If either fence is missing.
        """
        fence = PromptLandmark.EXECUTABLE_PROMPT_FENCE
        begin = self.position(fence) + len(fence.text)
        return self.text[begin : self.position(PromptLandmark.CLOSING_FENCE, begin)]

    def hard_rules(self) -> str:
        """
        Extract the hard-rules block: its heading and every bullet beneath it.

        Parsing to the end of the bullets rather than to a following landmark lets the
        block be compared across documents that continue differently after it.

        :return: The heading line and its bullets.
        :raises LandmarkNotFoundError: If the block is missing.
        """
        lines = self.section(PromptLandmark.HARD_RULES).splitlines()
        block = [lines[0]]
        for line in lines[1:]:
            if not line.startswith(("- ", "  ")):
                break
            block.append(line)
        return "\n".join(block)
