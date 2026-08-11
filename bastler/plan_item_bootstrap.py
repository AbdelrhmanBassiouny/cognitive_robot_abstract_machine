#!/usr/bin/env python3
"""
Keep a plan item's recorded state current, from before its implementation onward.

Everything a session knows the moment an implementation plan is approved - the branch,
the draft pull request, the item's manifest fields, its roadmap section - is derivable
without a line of the implementation, yet all of it conventionally happens at the end.
For that whole window ``plan.yaml`` says the item is ``not_started`` with no branch while
a branch exists and is being worked, which every dashboard, kickoff and resolve run
downstream reads as truth.

The same holds for every later transition - a blocker appearing, a status changing, a
conclusion that changes what the item means - so writing the entry is not a bootstrap
step but a standing obligation. ``manifest-staleness.md``, beside the plan-dashboard
skill, is the rule these operations serve.

Seven operations, so each caller depends only on the surface it uses:

``record``
    Write or update the item's ``plan.yaml`` entry and append its ``roadmap.md``
    section, set its status, and push both through ``save-plan.sh``.

``open``
    Create the branch, publish it, open the draft pull request, then write ``branch``,
    ``session`` and ``pull_request_number`` back onto the item and flip it to
    ``in_progress``. A caller that has already created the pull request passes
    ``--pull-request-number`` and only the recording happens.

``update``
    Set any of the item's recorded fields without appending a roadmap section, which
    ``record`` cannot do - it reads the section unconditionally. Most transitions change
    a field without warranting a section, and ``notes`` and ``blockers`` had no writer
    at all before this. ``--append-notes`` extends the recorded note rather than
    replacing it, since the two forms a note reaches this script in separate their
    paragraphs differently - see :func:`extend_note`.

``check``
    Report which recorded fields local git contradicts, exiting non-zero when any do.
    Deliberately local-only: the dashboard already compares the manifest against GitHub
    after the fact, so what nothing covered was the window before a push.

``resolve``
    Name the plan and the items a branch belongs to, for a caller that holds a branch
    rather than an item id - an automated pass over many branches at once.

``block`` / ``unblock``
    Record or withdraw one caller's own blocker on every item a branch carries, deriving
    the status from what is left blocking it. The owner is written into the blocker, so
    a pass replaces and clears its own entries and never a person's.

``repair``
    Rejoin the words an earlier wrap broke across a plan's recorded notes. Fixing the
    writer stops it breaking new words; it does not repair what it already wrote, and
    nothing else looks at those values. Only a break whose rejoined word appears
    elsewhere is closed up - a suspended hyphen has the same shape and is reported
    instead, since editing somebody's prose on a guess is the worse error.

``open`` runs before ``record`` when both are wanted: the pull request number does not
exist until the pull request does.

Usage:
    python3 plan_item_bootstrap.py record --plan <plan-id> --item <item-id> \\
        --status <status> --roadmap-section <file> [--title <title>] [--track <track>]
    python3 plan_item_bootstrap.py open --plan <plan-id> --item <item-id> \\
        --branch <branch> --base <branch> --session <url> \\
        (--pull-request-number <number> | --pull-request-title <title> \\
         --pull-request-body <file>)
    python3 plan_item_bootstrap.py update --plan <plan-id> --item <item-id> \\
        [--status <status>] [--branch <branch>] [--pull-request-number <number>] \\
        [--session <url>] [--notes <file> | --append-notes <file>] \\
        [--blockers <file> ...]
    python3 plan_item_bootstrap.py check --plan <plan-id> --item <item-id> \\
        [--remote <remote>]
    python3 plan_item_bootstrap.py resolve --branch <branch>
    python3 plan_item_bootstrap.py block --branch <branch> --owner <name> \\
        --reason <file>
    python3 plan_item_bootstrap.py unblock --branch <branch> --owner <name>
    python3 plan_item_bootstrap.py repair --plan <plan-id>

Prints a one-line JSON report led by ``status`` and ``exit_code``, so a caller acting on
the document never has to decode an integer back into a meaning.

.. note::
   Republishing the dashboard is deliberately not done here. Only a live session can
   call the ``Artifact`` tool, so every operation hands back the ``/plan-dashboard``
   command to run instead, exactly as ``save-plan.sh`` already does.

.. note::
   The manifest is edited by patching only the lines that change. A full YAML
   load-mutate-dump round trip is rejected for the reason ``sync_manifest_status.py``
   records: even a format-preserving library re-flows wrapped strings, turning a
   one-field edit into an unreadable diff across the whole file. Every key, filename and
   status this module writes is named once in :class:`ManifestKey`, :class:`PlanDocument`
   and :class:`ItemStatus`, and every line is rendered by the key that owns it, so no
   caller - tests included - writes a second copy of a manifest line by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum
from pathlib import Path
from typing import Any, ClassVar, Protocol

import yaml

from bastler.plan_model import ItemStatus

GITHUB_API_ROOT = "https://api.github.com"
"""
Where pull requests are created, overridable for a GitHub Enterprise host.
"""

HOOKS_DIRECTORY = ".claude/hooks"
"""
Where this repository keeps the scripts that read and write personal-notes data.
"""

PLANS_DIRECTORY = ".claude/personal/plans"
"""
Where plans live on the personal-notes branch.

Mirrors ``PLANS_DIR`` in ``resolve-personal-notes-config.sh``, which is the shell half of
the same tooling; a test holds the two equal so the mirror cannot drift.
"""

ITEM_FIELD_INDENT = "    "
"""
The indentation ``plan.yaml`` item fields carry, one level inside the list marker.
"""

ITEM_MARKER = "  - "
"""
What opens an item block, the list marker its first field sits behind.
"""

BLOCK_BODY_INDENT = "      "
"""
The indentation a block-styled value's body carries, one level inside its own key.
"""

SEQUENCE_ENTRY_INDENT = "      "
"""
The indentation a sequence entry's dash carries, one level inside its own key.
"""

MANIFEST_LINE_WIDTH = 100
"""
The column a wrapped body line is kept under.

Measured from the manifests this writes rather than chosen: their hand-wrapped body
lines cluster at 96-99 columns, so a script-written note is indistinguishable from one
a person wrapped.
"""


def paragraphs_of(text: str) -> list[str]:
    """
    The paragraphs a value about to be written breaks into.

    A blank line separates paragraphs; a single newline is a hard-wrapped line within
    one, which is how a person writes the file a value comes from. Shared with
    :func:`fold` so that what gets counted and what gets written can never disagree.

    A hyphen immediately before one of those wrapped line breaks closes up rather than
    becoming a space, because that is where its author wrapped a word they wrote whole -
    ``blank-\\nline`` is *blank-line*, not *blank- line*. A suspended hyphen keeps its
    space, since a person types *network- and* on one line rather than breaking after
    the hyphen. The one shape this reads wrongly is a suspended hyphen a wrap happens to
    land on, which is why the space is only removed where the author put the break.

    :param text: The value as its author wrote it.
    :return: Its paragraphs, stripped.
    """
    return [
        re.sub(r"-\n", "-", paragraph.strip())
        for paragraph in re.split(r"\n\s*\n", text.strip())
    ]


def fold(text: str, indent: str) -> str:
    """
    Wrap *text* as the body of a folded scalar, newline-terminated.

    Only ever breaks between words. A folded scalar reads a line break back as a space,
    so a break placed inside a word - at a hyphen, or anywhere at all in a word too long
    for one line - returns a different string than it was given, still valid and no
    longer what anybody wrote. A word wider than the column overflows it instead, which
    is the one thing wrapping is allowed to get wrong here.

    :param text: The value to wrap, whose own paragraph breaks are preserved.
    :param indent: The indentation every body line carries.
    :return: The body's lines.
    """
    paragraphs = [
        textwrap.fill(
            paragraph,
            width=MANIFEST_LINE_WIDTH,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        for paragraph in paragraphs_of(text)
    ]
    return "\n\n".join(paragraphs) + "\n"


def render_sequence_entry(entry: str) -> str:
    """
    One entry of a sequence-styled value, newline-terminated.

    An entry that fits on its own line is written as a quoted scalar and a longer one as
    a folded block, which is how the manifests this writes already read.

    The folded form strips its trailing newline (``>-``), unlike a block-styled *value*,
    which keeps it: an entry is one item of a list and has to parse back as exactly the
    string it was given, where a note is a paragraph and every note already in these
    manifests ends in a newline.

    :param entry: The entry's text.
    :return: The entry's lines.
    """
    quoted = f'{SEQUENCE_ENTRY_INDENT}- "{entry}"'
    if "\n" not in entry and len(quoted) <= MANIFEST_LINE_WIDTH and '"' not in entry:
        return f"{quoted}\n"
    body = fold(entry, SEQUENCE_ENTRY_INDENT + ITEM_FIELD_INDENT)
    return f"{SEQUENCE_ENTRY_INDENT}- >-\n{body}"


# %% the vocabulary a plan manifest is written in


class HookScript(StrEnum):
    """
    The hook scripts this module drives, named once so a caller - a test installing them
    into a scratch layout, or this module invoking one - never spells a filename itself.
    """

    CONFIGURATION = "resolve-personal-notes-config.sh"
    """
    Resolves the personal-notes remote and branch, and fetches it.
    """

    SAVE_PLAN = "save-plan.sh"
    """
    Pushes an edited manifest and roadmap to the personal-notes branch.
    """

    PLAN_ITEM_BOOTSTRAP = "plan_item_bootstrap.py"
    """
    This module, which a caller invokes by path.
    """

    @property
    def path(self) -> str:
        """
        The script's path from the project root.
        """
        return f"{HOOKS_DIRECTORY}/{self.value}"


class PlanDocument(StrEnum):
    """
    The two files a plan is kept in, beside each other on the personal-notes branch.
    """

    MANIFEST = "plan.yaml"
    """
    The structured manifest, whose schema ``plan-schema.md`` documents.
    """

    ROADMAP = "roadmap.md"
    """
    The narrative companion, a fixed sibling filename rather than a configurable one.
    """

    def path_within_notes_branch(self, plan_identifier: str) -> str:
        """
        Where this document lives for one plan.

        :param plan_identifier: The plan's id.
        :return: The path, relative to the personal-notes branch's root.
        """
        return f"{PLANS_DIRECTORY}/{plan_identifier}/{self.value}"


class ValueStyle(StrEnum):
    """
    How a key's value is written, in YAML's own vocabulary.

    Mutually exclusive by construction, which the two booleans this replaced could not
    say: a value is written one of these ways, never two.
    """

    PLAIN = "plain"
    """
    A bare scalar on the key's own line.
    """

    DOUBLE_QUOTED = "double_quoted"
    """
    A quoted scalar, for prose that would otherwise need escaping.
    """

    BLOCK = "block"
    """
    A folded scalar, written across the lines beneath the key.

    Anything inserted after such a key would be swallowed by its value, so a new key
    goes before the first block-styled one in an item rather than at the end.
    """

    SEQUENCE = "sequence"
    """
    A list, one entry per dash beneath the key.

    Spans the lines beneath the key exactly as :attr:`BLOCK` does; they differ only in
    what those lines say, which is why writing one is not writing the other. A list with
    no entries is written inline as ``[]``, since a key with nothing beneath it parses
    as null rather than as an empty list.
    """

    @property
    def spans_lines_beneath(self) -> bool:
        """
        Whether this style's value continues below the key's own line.

        The property the insertion point and the replaced span both key on, so neither
        has to list the styles it means.
        """
        return self in {ValueStyle.BLOCK, ValueStyle.SEQUENCE}


@dataclass(frozen=True)
class KeySpecification:
    """
    How one ``plan.yaml`` key is written, so no caller has to decide per key.
    """

    key: str
    """
    The key as it appears in the manifest.

    Named ``key`` rather than ``name`` for two reasons: it is YAML's own term for the
    left-hand side of a mapping, and :class:`ManifestKey` mixes this class into an
    ``Enum``, whose ``name`` is reserved for the member's own name.
    """

    style: ValueStyle = ValueStyle.PLAIN
    """
    How this key's value is written.
    """


class ManifestKey(KeySpecification, Enum):
    """
    The ``plan.yaml`` keys this module reads or writes, each carrying how it is written.

    A member *is* a :class:`KeySpecification`, so ``isinstance`` and ``issubclass`` hold
    and a key's own style is reached directly: ``ManifestKey.TITLE.style``. That is what
    lets :meth:`render` produce a correct line from the key alone - a caller never
    chooses quoting, and every assertion about a manifest line derives from the same
    place the line is written. The full schema is documented in ``plan-schema.md``; this
    enum carries the subset bootstrapping an item touches.

    .. note::
       A member's value is the argument tuple its specification is built from, not a
       built :class:`KeySpecification`. Passing an instance is accepted silently by the
       enum machinery and lands the whole instance in :attr:`KeySpecification.key`, so a
       test asserts every key is a string.
    """

    IDENTIFIER = ("id",)
    """
    The item's own id, and the line that opens its block.
    """

    TITLE = ("title", ValueStyle.DOUBLE_QUOTED)
    """
    What the item does, quoted because it is prose.
    """

    BRANCH = ("branch",)
    """
    The git branch the work happens on, once one exists.
    """

    REPOSITORY = ("repository",)
    """
    The item's own repository, overriding the plan's default.
    """

    DEFAULT_REPOSITORY = ("default_repository",)
    """
    The repository every item uses unless it sets its own.
    """

    PULL_REQUEST_NUMBER = ("pull_request_number",)
    """
    The real pull request number, once one exists.
    """

    TRACK = ("track",)
    """
    The parallel line of work the item belongs to.
    """

    DEPENDS_ON = ("depends_on",)
    """
    The items this one stacks on, by id.
    """

    STATUS = ("status",)
    """
    The session's own planning assessment - see :class:`ItemStatus`.
    """

    SESSION = ("session",)
    """
    The session doing the work.
    """

    NOTES = ("notes", ValueStyle.BLOCK)
    """
    Freeform detail, routinely folded over many lines.
    """

    BLOCKERS = ("blockers", ValueStyle.SEQUENCE)
    """
    Why the item is stuck, written as a sequence.
    """

    ITEMS = ("items",)
    """
    The manifest's top-level list of items.
    """

    def render(self, value: str | Sequence[str], opening_the_item: bool = False) -> str:
        """
        The manifest text setting this key to *value*, newline-terminated.

        How the value is written comes from the key's own style rather than from the
        caller, so a style that spans the lines beneath the key returns those lines too
        rather than a single one.

        :param value: The value to write - a sequence only for a sequence-styled key.
        :param opening_the_item: Whether this is the item block's first line, which
            carries the list marker instead of the key indent.
        :return: The rendered text.
        """
        prefix = ITEM_MARKER if opening_the_item else ITEM_FIELD_INDENT
        if self.style is ValueStyle.SEQUENCE:
            if not value:
                return f"{prefix}{self.key}: []\n"
            entries = "".join(render_sequence_entry(entry) for entry in value)
            return f"{prefix}{self.key}:\n{entries}"
        if self.style is ValueStyle.BLOCK:
            return f"{prefix}{self.key}: >\n{fold(str(value), BLOCK_BODY_INDENT)}"
        written = f'"{value}"' if self.style is ValueStyle.DOUBLE_QUOTED else value
        return f"{prefix}{self.key}: {written}\n"

    @property
    def pattern(self) -> re.Pattern[str]:
        """
        Matches this key wherever it already appears in an item block.
        """
        return re.compile(rf"^\s*{re.escape(self.key)}:\s*.*$")


BLOCK_STYLED_KEYS = frozenset(
    manifest_key
    for manifest_key in ManifestKey
    if manifest_key.style.spans_lines_beneath
)
"""
The keys whose values run over the lines beneath them, derived from the keys themselves
rather than listed a second time.
"""


ITEM_START_PATTERN = re.compile(rf"^\s*- {re.escape(ManifestKey.IDENTIFIER.key)}:")
"""
Matches the first line of an item block, which is always its ``id``.

Same anchor ``sync_manifest_status.py`` uses to find item boundaries in raw text.
"""

TOP_LEVEL_KEY_PATTERN = re.compile(r"^\S")
"""
Matches a top-level ``plan.yaml`` key, which is where the last item block ends.
"""

BLOCK_VALUE_PATTERN = re.compile(
    rf"^\s*({'|'.join(sorted(manifest_key.key for manifest_key in BLOCK_STYLED_KEYS))}):"
)
"""
Matches a key whose value may run over the following lines, derived from
:data:`BLOCK_STYLED_KEYS` rather than listing those keys a second time.
"""


class ExitCode(IntEnum):
    """
    The process statuses this tool exits with.

    A distinct status per refusal lets a caller act on *which* failure happened without
    parsing stderr. ``argparse`` supplies 2 for a usage error.
    """

    SUCCESS = 0
    """
    The operation ran and printed its report.
    """

    UNKNOWN_PLAN = 3
    """
    No plan of that id is on the personal-notes branch.
    """

    UNKNOWN_ITEM = 4
    """
    The plan exists but tracks no item of that id, and too little was given to add one.
    """

    INCOMPLETE_NEW_ITEM = 5
    """
    Adding the item was asked for without every key a new entry must carry.
    """

    BRANCH_ALREADY_PUBLISHED = 6
    """
    The branch is already on the remote, so opening the work would adopt someone's.
    """

    PULL_REQUEST_DETAILS_MISSING = 7
    """
    Neither an existing pull request number nor the title and body to create one.
    """

    PULL_REQUEST_REFUSED = 8
    """
    GitHub rejected the creation; its own message says why.
    """

    MANIFEST_IS_STALE = 9
    """
    The check found recorded fields that local git contradicts.
    """

    BRANCH_TRACKS_NO_ITEM = 10
    """
    No plan claims the branch, so there was nothing to resolve or to write.

    A finding rather than a failure - every pull request is supposed to belong to a
    plan, so a caller acting on the status alone reports it instead of guessing.
    """

    TEXT_NEEDS_REPAIR = 11
    """
    Words a wrap once broke are still broken, and repairing them needs a person.

    A finding rather than a failure, like :attr:`BRANCH_TRACKS_NO_ITEM`: the repair the
    tool could make safely is already made, and what is left is what it declines to
    guess at.
    """

    @property
    def name_for_a_caller(self) -> str:
        """
        The status's own name, for a report a person or a script has to act on.

        Derived from the member rather than a table beside it, so a status can never
        carry a name belonging to a different one.
        """
        return self.name.lower()


# %% the vocabulary a report is written in


class ReportKey(StrEnum):
    """
    The keys of the JSON documents these operations print.

    Named here so the reader consuming a report and the code building it cannot drift
    apart, and so no caller spells one out as a bare string.

    Only the keys this module invents. A key naming a manifest field - ``branch``,
    ``blockers``, ``pull_request_number``, an item's own ``status`` - is read from
    :class:`ManifestKey` instead, since that is where a field's name already lives.
    """

    STATUS = "status"
    """
    What the run means, as :attr:`ExitCode.name_for_a_caller` puts it.

    Distinct from an item's own ``status``, which names a point in its lifecycle and
    comes from :attr:`ManifestKey.STATUS`; the two share a spelling and nothing else.
    """

    EXIT_CODE = "exit_code"
    """
    The status the process exits with, for a caller reading the document rather than
    waiting on the process.
    """

    PLAN = "plan"
    """
    The plan the operation acted on.
    """

    ITEM = "item"
    """
    The item the operation acted on.
    """

    ITEMS = "items"
    """
    Every item a branch carries, for an operation keyed on a branch.
    """

    CREATED_ITEM = "created_item"
    """
    Whether the item's manifest entry was written for the first time.
    """

    DASHBOARD_COMMAND = "dashboard_command"
    """
    The republish a live session still has to run, since only it can call ``Artifact``.
    """

    FINDINGS = "findings"
    """
    Every recorded field local git contradicts.
    """

    FIELD = "field"
    """
    The manifest field one finding is about.
    """

    RECORDED = "recorded"
    """
    What the manifest says for that field.
    """

    OBSERVED = "observed"
    """
    What git shows for it instead.
    """

    PREVIOUS_STATUS = "previous_status"
    """
    The status an item carried before a write, so a reader sees what changed.
    """

    PULL_REQUEST_URL = "pull_request_url"
    """
    Where an opened pull request lives.
    """

    NOTE_PARAGRAPHS = "note_paragraphs"
    """
    How many paragraphs the item's note ends up with.

    Reported because a file's paragraphs are whatever its blank lines say they are, and
    a caller who meant several and wrote none has no other way to see it.
    """

    REPAIRS = "repairs"
    """
    Every word a wrap once broke, and whether it was rejoined.
    """

    BROKEN = "broken"
    """
    The word as the manifest currently carries it, split across the break.
    """

    REJOINED = "rejoined"
    """
    What the word reads as once rejoined.
    """

    REPAIRED = "repaired"
    """
    Whether this one was rejoined, as against left for a person to judge.
    """


# %% failures


@dataclass
class BootstrapError(Exception, ABC):
    """
    Base for every refusal this tool reports, each carrying its own exit status.

    Subclasses hold the context that explains the refusal as typed fields and compose it
    into the message at construction, so no call site formats one. Mirrors ``krrood``'s
    ``DataclassException`` idiom rather than importing it, which is the boundary decision
    12 records for this tooling.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.SUCCESS
    """
    The process status this refusal exits with.
    """

    def __post_init__(self) -> None:
        """
        Compose the message from the subclass's own description and advice.
        """
        correction = self.suggest_correction()
        message = self.error_message()
        super().__init__(f"{message}\n{correction}" if correction else message)

    def __str__(self) -> str:
        """
        The composed message, rather than a repr of the dataclass fields.
        """
        return Exception.__str__(self)

    @abstractmethod
    def error_message(self) -> str:
        """
        :return: What went wrong.
        """

    @abstractmethod
    def suggest_correction(self) -> str:
        """
        :return: What to do about it, or an empty string when there is nothing to add.
        """


@dataclass
class UnknownPlanError(BootstrapError):
    """
    Raised when the named plan has no manifest on the personal-notes branch.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.UNKNOWN_PLAN

    plan_identifier: str
    """
    The plan that could not be found.
    """

    manifest_path: str
    """
    Where its manifest was looked for.
    """

    def error_message(self) -> str:
        return (
            f"no plan {self.plan_identifier!r} on the personal-notes branch "
            f"({self.manifest_path} is not there)"
        )

    def suggest_correction(self) -> str:
        return "Run /plan-create to bootstrap it, or check the plan id for a typo."


@dataclass
class UnknownItemError(BootstrapError):
    """
    Raised when the named item is absent from an otherwise resolvable plan.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.UNKNOWN_ITEM

    plan_identifier: str
    """
    The plan that was searched.
    """

    item_identifier: str
    """
    The item that is not in it.
    """

    def error_message(self) -> str:
        return f"no item {self.item_identifier!r} in plan {self.plan_identifier!r}"

    def suggest_correction(self) -> str:
        return (
            "Record the item first - /add-plan-item decides where new work belongs, and "
            "this tool's record operation writes the entry."
        )


@dataclass
class IncompleteNewItemError(BootstrapError):
    """
    Raised when an item that does not exist yet is recorded without the fields needed to
    write its entry.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.INCOMPLETE_NEW_ITEM

    item_identifier: str
    """
    The item that would have been created.
    """

    missing_keys: tuple[ManifestKey, ...]
    """
    The keys a new entry cannot omit that were not supplied.
    """

    def error_message(self) -> str:
        missing = ", ".join(manifest_key.key for manifest_key in self.missing_keys)
        return (
            f"item {self.item_identifier!r} is not in the plan yet, so recording it "
            f"needs {missing}"
        )

    def suggest_correction(self) -> str:
        return "Pass " + " and ".join(
            f"--{manifest_key.key.replace('_', '-')}"
            for manifest_key in self.missing_keys
        )


@dataclass
class BranchAlreadyPublishedError(BootstrapError):
    """
    Raised when the branch to open already exists on the remote, which means work is
    underway and overwriting it would discard someone's commits.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.BRANCH_ALREADY_PUBLISHED

    branch: str
    """
    The branch that is already published.
    """

    remote: str
    """
    The remote carrying it.
    """

    def error_message(self) -> str:
        return (
            f"branch {self.branch!r} already exists on {self.remote!r} - it is already "
            "being worked, and republishing it would discard those commits"
        )

    def suggest_correction(self) -> str:
        return (
            "Pass --pull-request-number if its pull request already exists, or choose a "
            "branch name that is not taken."
        )


@dataclass
class PullRequestDetailsMissingError(BootstrapError):
    """
    Raised when opening the work must create a pull request but was given nothing to
    create it from.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.PULL_REQUEST_DETAILS_MISSING

    item_identifier: str
    """
    The item whose work was being opened.
    """

    def error_message(self) -> str:
        return (
            f"opening {self.item_identifier!r} has to create a pull request, but was "
            "given neither a title nor a body to create one from"
        )

    def suggest_correction(self) -> str:
        return (
            "Pass --pull-request-number for one you already created - which keeps your "
            "identity on it - or --pull-request-title and --pull-request-body."
        )


@dataclass
class PullRequestRefusedError(BootstrapError):
    """
    Raised when the remote declines to create the pull request.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.PULL_REQUEST_REFUSED

    detail: str
    """
    What the remote said.
    """

    def error_message(self) -> str:
        return f"the remote refused to create the pull request: {self.detail}"

    def suggest_correction(self) -> str:
        return (
            "The branch is published, so create the pull request yourself and re-run "
            "with --pull-request-number."
        )


@dataclass
class NotesBranchUnavailableError(BootstrapError):
    """
    Raised when the personal-notes branch cannot be fetched, so there is no plan data to
    read or write.
    """

    exit_code: ClassVar[ExitCode] = ExitCode.UNKNOWN_PLAN

    detail: str
    """
    Why the fetch failed.
    """

    def error_message(self) -> str:
        return f"could not fetch the personal-notes branch: {self.detail}"

    def suggest_correction(self) -> str:
        return f"Run {HOOKS_DIRECTORY}/create-personal-notes-branch.sh first."


# %% the plan on the personal-notes branch


def run_git(*arguments: str, project_root: Path) -> str:
    """
    Run git in *project_root* and return its standard output.

    :param arguments: The arguments to pass to git.
    :param project_root: The repository to run within.
    :raises subprocess.CalledProcessError: If git reports an error.
    :return: Standard output, stripped of its trailing newline.
    """
    result = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def branch_is_published(branch: str, remote: str, project_root: Path) -> bool:
    """
    Whether *branch* already exists on *remote*.

    :param branch: The branch to look for.
    :param remote: The remote to ask.
    :param project_root: The repository to run within.
    :return: True when the remote already carries it.
    """
    listing = run_git("ls-remote", "--heads", remote, branch, project_root=project_root)
    return bool(listing.strip())


def fetch_notes_branch(project_root: Path) -> None:
    """
    Fetch the personal-notes branch, leaving ``FETCH_HEAD`` pointing at it.

    Sources the shell configuration and calls its own fetch function rather than
    re-deriving the remote and branch precedence, so this and the hook scripts can never
    disagree about which branch a plan is on. Where a plan sits *within* that branch is
    :meth:`PlanDocument.path_within_notes_branch`'s to say.

    :param project_root: The repository to fetch within.
    :raises NotesBranchUnavailableError: If the notes branch cannot be fetched.
    """
    probe = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HookScript.CONFIGURATION.path}" && fetch_personal_notes_branch',
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise NotesBranchUnavailableError(
            detail=probe.stderr.strip() or "no personal-notes branch found"
        )


@dataclass(frozen=True)
class PlanDocuments:
    """
    One plan's manifest and roadmap as they stand on the personal-notes branch.
    """

    plan_identifier: str
    """
    The plan's id.
    """

    manifest_text: str
    """
    The manifest's raw text, patched by line rather than re-serialized.
    """

    roadmap_text: str
    """
    The roadmap's raw markdown.
    """

    @classmethod
    def load(cls, plan_identifier: str, project_root: Path) -> PlanDocuments:
        """
        Read a plan's manifest and roadmap off the freshly fetched notes branch.

        The fetch happens here, immediately before the caller's edit, so an edit is
        never applied to a copy loaded earlier in the session.

        :param plan_identifier: The plan's id.
        :param project_root: The repository to read within.
        :raises UnknownPlanError: If the plan has no manifest on the branch.
        :return: The loaded documents.
        """
        fetch_notes_branch(project_root)
        contents = {}
        for document in PlanDocument:
            path = document.path_within_notes_branch(plan_identifier)
            try:
                contents[document] = (
                    run_git("show", f"FETCH_HEAD:{path}", project_root=project_root)
                    + "\n"
                )
            except subprocess.CalledProcessError as error:
                raise UnknownPlanError(
                    plan_identifier=plan_identifier, manifest_path=path
                ) from error
        return cls(
            plan_identifier=plan_identifier,
            manifest_text=contents[PlanDocument.MANIFEST],
            roadmap_text=contents[PlanDocument.ROADMAP],
        )

    @property
    def manifest(self) -> dict[str, Any]:
        """
        The parsed manifest, for reading fields rather than editing them.
        """
        return yaml.safe_load(self.manifest_text)

    def repository_for(self, item_identifier: str) -> str:
        """
        The ``owner/repo`` an item's pull request belongs to.

        :param item_identifier: The item's id.
        :raises UnknownItemError: If no item carries that id.
        :return: The item's own repository, or the plan's default one.
        """
        item = self.item(item_identifier)
        return (
            item.get(ManifestKey.REPOSITORY.key)
            or self.manifest[ManifestKey.DEFAULT_REPOSITORY.key]
        )

    def item(self, item_identifier: str) -> dict[str, Any]:
        """
        One item's parsed mapping.

        :param item_identifier: The item's id, or its branch when it has no id.
        :raises UnknownItemError: If no item matches.
        :return: The item's mapping.
        """
        for candidate in self.manifest.get(ManifestKey.ITEMS.key, []):
            identifier = candidate.get(ManifestKey.IDENTIFIER.key) or candidate.get(
                ManifestKey.BRANCH
            )
            if identifier == item_identifier:
                return candidate
        raise UnknownItemError(
            plan_identifier=self.plan_identifier, item_identifier=item_identifier
        )

    def has_item(self, item_identifier: str) -> bool:
        """
        Whether the plan already tracks an item under *item_identifier*.

        :param item_identifier: The item's id.
        :return: True when an entry exists.
        """
        try:
            self.item(item_identifier)
        except UnknownItemError:
            return False
        return True

    def save(self, manifest_text: str, roadmap_text: str, project_root: Path) -> None:
        """
        Push an edited manifest and roadmap through ``save-plan.sh``.

        :param manifest_text: The full manifest to write.
        :param roadmap_text: The full roadmap to write.
        :param project_root: The repository to run the script from.
        :raises subprocess.CalledProcessError: If the script reports an error.
        """
        with tempfile.TemporaryDirectory() as scratch_directory:
            scratch = Path(scratch_directory)
            written = {
                PlanDocument.MANIFEST: manifest_text,
                PlanDocument.ROADMAP: roadmap_text,
            }
            for document, content in written.items():
                (scratch / document.value).write_text(content)
            subprocess.run(
                [
                    "bash",
                    HookScript.SAVE_PLAN.path,
                    self.plan_identifier,
                    "--manifest",
                    str(scratch / PlanDocument.MANIFEST.value),
                    "--roadmap",
                    str(scratch / PlanDocument.ROADMAP.value),
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            )


# %% patching one item's fields in the manifest text


def item_block_bounds(manifest_lines: list[str]) -> list[tuple[int, int]]:
    """
    The half-open line range of every item block in the manifest.

    :param manifest_lines: The manifest, split into lines.
    :return: One ``(start, end)`` pair per item, in manifest order.
    """
    starts = [
        index
        for index, line in enumerate(manifest_lines)
        if ITEM_START_PATTERN.match(line)
    ]
    if not starts:
        return []
    end_of_items = next(
        (
            index
            for index in range(starts[-1] + 1, len(manifest_lines))
            if TOP_LEVEL_KEY_PATTERN.match(manifest_lines[index])
        ),
        len(manifest_lines),
    )
    return list(zip(starts, starts[1:] + [end_of_items]))


def locate_item_block(
    manifest_lines: list[str], plan_identifier: str, item_identifier: str
) -> tuple[int, int]:
    """
    Find one item's block within the manifest text.

    :param manifest_lines: The manifest, split into lines.
    :param plan_identifier: The plan being edited, for the error message.
    :param item_identifier: The item's id.
    :raises UnknownItemError: If no block starts with that id.
    :return: The block's half-open line range.
    """
    opener = f"- {ManifestKey.IDENTIFIER.key}:"
    for start, end in item_block_bounds(manifest_lines):
        if (
            manifest_lines[start].strip().removeprefix(opener).strip()
            == item_identifier
        ):
            return start, end
    raise UnknownItemError(
        plan_identifier=plan_identifier, item_identifier=item_identifier
    )


def apply_item_fields(
    manifest_text: str,
    plan_identifier: str,
    item_identifier: str,
    values_by_key: dict[ManifestKey, str],
) -> str:
    """
    Set each of *values_by_key* on one item, patching an existing line or inserting a new
    one.

    Every other line is left byte-for-byte untouched, so comments, key order, string
    wrapping and quoting all survive.

    :param manifest_text: The manifest's raw text.
    :param plan_identifier: The plan being edited.
    :param item_identifier: The item to patch.
    :param values_by_key: The value to write to each key, applied in insertion order. A
        mapping rather than pairs, since one key cannot be set twice.
    :raises UnknownItemError: If the item has no block in the text.
    :return: The patched manifest text.
    """
    lines = manifest_text.split("\n")
    start, end = locate_item_block(lines, plan_identifier, item_identifier)
    for manifest_key, value in values_by_key.items():
        rendered = manifest_key.render(value).rstrip("\n").split("\n")
        existing = next(
            (
                index
                for index in range(start, end)
                if manifest_key.pattern.match(lines[index])
            ),
            None,
        )
        if existing is not None:
            replaced = value_span(lines, existing, end, manifest_key)
            lines[existing:replaced] = rendered
            end += len(rendered) - (replaced - existing)
            continue
        insertion = next(
            (
                index
                for index in range(start, end)
                if BLOCK_VALUE_PATTERN.match(lines[index])
            ),
            last_populated_line(lines, start, end) + 1,
        )
        lines[insertion:insertion] = rendered
        end += len(rendered)
    return "\n".join(lines)


def value_span(
    manifest_lines: list[str], key_line: int, end: int, manifest_key: ManifestKey
) -> int:
    """
    One past the last line a key's value occupies.

    A value written across the lines beneath its key owns every following line indented
    past the key itself; replacing only the key's own line would leave that body behind,
    where YAML reads it as a continuation of whatever replaced it.

    :param manifest_lines: The manifest, split into lines.
    :param key_line: The line the key sits on.
    :param end: One past the item block's last line.
    :param manifest_key: The key whose value is being measured.
    :return: One past the value's last line.
    """
    if not manifest_key.style.spans_lines_beneath:
        return key_line + 1
    key_indent = indentation_of(manifest_lines[key_line])
    last_value_line = key_line
    for index in range(key_line + 1, end):
        line = manifest_lines[index]
        if not line.strip():
            continue
        if indentation_of(line) <= key_indent:
            break
        last_value_line = index
    return last_value_line + 1


def indentation_of(line: str) -> int:
    """
    How many columns a line is indented by.

    :param line: The line to measure.
    :return: The width of its leading whitespace.
    """
    return len(line) - len(line.lstrip())


def last_populated_line(manifest_lines: list[str], start: int, end: int) -> int:
    """
    The last non-blank line of a block, so an appended field lands inside it.

    :param manifest_lines: The manifest, split into lines.
    :param start: The block's first line.
    :param end: One past the block's last line.
    :return: The index of the block's last non-blank line.
    """
    return max(
        (index for index in range(start, end) if manifest_lines[index].strip()),
        default=start,
    )


def render_new_item(request: ItemRecordRequest) -> str:
    """
    Render a brand-new item block, in the field order ``plan-schema.md`` documents.

    :param request: The item to record.
    :raises IncompleteNewItemError: If a field a new entry cannot omit is missing.
    :return: The block's text, newline-terminated.
    """
    required = {ManifestKey.TITLE: request.title, ManifestKey.TRACK: request.track}
    missing = tuple(
        manifest_key for manifest_key, value in required.items() if not value
    )
    if missing:
        raise IncompleteNewItemError(
            item_identifier=request.item_identifier, missing_keys=missing
        )
    body = {
        ManifestKey.TITLE: request.title,
        ManifestKey.BRANCH: "null",
        ManifestKey.TRACK: request.track,
        ManifestKey.DEPENDS_ON: "[]",
        ManifestKey.STATUS: request.status.value,
    }
    return ManifestKey.IDENTIFIER.render(
        request.item_identifier, opening_the_item=True
    ) + "".join(manifest_key.render(value) for manifest_key, value in body.items())


def append_item(manifest_text: str, block: str) -> str:
    """
    Add a rendered item block after the manifest's last item.

    :param manifest_text: The manifest's raw text.
    :param block: The block to append, as :func:`render_new_item` renders it.
    :return: The extended manifest text.
    """
    lines = manifest_text.split("\n")
    bounds = item_block_bounds(lines)
    insertion = bounds[-1][1] if bounds else len(lines)
    tail = "\n".join(lines[insertion:])
    head = "\n".join(lines[:insertion]).rstrip("\n")
    return f"{head}\n\n{block}{tail}"


# %% recording an item


@dataclass(frozen=True)
class ItemRecordRequest:
    """
    What recording one item needs: where it goes, what it is, and what to say about it.
    """

    plan_identifier: str
    """
    The plan the item belongs to.
    """

    item_identifier: str
    """
    The item's id, created if the plan does not track it yet.
    """

    status: ItemStatus
    """
    The status to set on the item.
    """

    roadmap_section_path: Path
    """
    A file whose markdown is appended to the plan's roadmap.
    """

    title: str | None = None
    """
    The item's title, required only when the entry does not exist yet.
    """

    track: str | None = None
    """
    The track the item belongs to, required only when the entry does not exist yet.
    """


@dataclass(frozen=True)
class BootstrapReport:
    """
    What an operation did, in the shape a caller acts on.
    """

    exit_code: ExitCode
    """
    The status the process exits with.
    """

    plan_identifier: str
    """
    The plan that was written.
    """

    item_identifier: str
    """
    The item that was recorded or opened.
    """

    created_item: bool = False
    """
    Whether the item's manifest entry was written for the first time.
    """

    branch: str | None = None
    """
    The branch opened, when one was.
    """

    pull_request_number: int | None = None
    """
    The pull request opened, when one was.
    """

    pull_request_url: str | None = None
    """
    Where the opened pull request lives.
    """

    note_paragraphs: int | None = None
    """
    How many paragraphs the written note reads as, when one was written.
    """

    @property
    def dashboard_command(self) -> str:
        """
        The republish a live session still has to run, since only it can call
        ``Artifact``.
        """
        return f"/plan-dashboard {self.plan_identifier}"

    def to_json(self) -> dict[str, Any]:
        """
        Render the report as the JSON a caller reads, led by what it means.
        """
        document: dict[str, Any] = {
            ReportKey.STATUS: self.exit_code.name_for_a_caller,
            ReportKey.EXIT_CODE: int(self.exit_code),
            ReportKey.PLAN: self.plan_identifier,
            ReportKey.ITEM: self.item_identifier,
            ReportKey.CREATED_ITEM: self.created_item,
            ReportKey.DASHBOARD_COMMAND: self.dashboard_command,
        }
        if self.branch is not None:
            document[ManifestKey.BRANCH.key] = self.branch
        if self.pull_request_number is not None:
            document[ManifestKey.PULL_REQUEST_NUMBER.key] = self.pull_request_number
            document[ReportKey.PULL_REQUEST_URL] = self.pull_request_url
        if self.note_paragraphs is not None:
            document[ReportKey.NOTE_PARAGRAPHS] = self.note_paragraphs
        return document


def record_item(request: ItemRecordRequest, project_root: Path) -> BootstrapReport:
    """
    Write or update one item's manifest entry and roadmap section, then push both.

    :param request: The item to record.
    :param project_root: The repository to run within.
    :raises UnknownPlanError: If the plan has no manifest on the notes branch.
    :raises IncompleteNewItemError: If a new entry is missing a field it cannot omit.
    :return: What was recorded.
    """
    documents = PlanDocuments.load(request.plan_identifier, project_root)
    created_item = not documents.has_item(request.item_identifier)

    if created_item:
        manifest_text = append_item(documents.manifest_text, render_new_item(request))
    else:
        manifest_text = apply_item_fields(
            documents.manifest_text,
            request.plan_identifier,
            request.item_identifier,
            {ManifestKey.STATUS: request.status.value},
        )

    roadmap_text = append_roadmap_section(
        documents.roadmap_text, request.roadmap_section_path.read_text()
    )
    documents.save(manifest_text, roadmap_text, project_root)
    return BootstrapReport(
        exit_code=ExitCode.SUCCESS,
        plan_identifier=request.plan_identifier,
        item_identifier=request.item_identifier,
        created_item=created_item,
    )


@dataclass(frozen=True)
class ItemUpdateRequest:
    """
    What updating one item needs: which item, and which fields to set on it.

    Separate from :class:`ItemRecordRequest` because most transitions change a field
    without warranting a roadmap section, and ``record`` cannot express that - it reads
    the section unconditionally.
    """

    plan_identifier: str
    """
    The plan the item belongs to.
    """

    item_identifier: str
    """
    The item being updated, which must already be tracked.
    """

    values_by_key: dict[ManifestKey, Any]
    """
    The value to write to each key, in the order they should be applied.
    """

    notes_to_append: str | None = None
    """
    A further paragraph for the item's existing note, rather than a replacement for it.
    """


def extend_note(recorded: str | None, addition: str) -> str:
    """
    A recorded note with *addition* as a further paragraph.

    The two sources separate their paragraphs differently, which is why extending a note
    cannot simply concatenate them. A folded scalar reads its own line breaks back as
    spaces and a blank line back as one newline, so a note read out of the manifest
    separates paragraphs with a single newline - which :func:`fold` would take for a
    hard-wrapped line and run together into one paragraph. A file a caller writes uses a
    blank line, which :func:`fold` already reads correctly.

    :param recorded: The note the manifest carries, or ``None`` where it carries none.
    :param addition: The text to add, as its author wrote it.
    :return: The whole note, separated the way a written note is.
    """
    paragraphs = [
        paragraph
        for paragraph in re.split(r"\n+", (recorded or "").strip())
        if paragraph
    ]
    paragraphs.append(addition.strip())
    return "\n\n".join(paragraphs)


def note_paragraph_count(note: str) -> int:
    """
    How many paragraphs a note will read as once written.

    Counted the way :func:`fold` splits it rather than by counting newlines, since a
    hard-wrapped line is not a paragraph and counting it as one would report a number
    the manifest never shows.

    :param note: The note as its author wrote it, before folding.
    :return: The paragraph count.
    """
    return len(paragraphs_of(note))


def update_item(request: ItemUpdateRequest, project_root: Path) -> BootstrapReport:
    """
    Set one item's recorded fields and push the manifest, leaving the roadmap alone.

    :param request: The item and the fields to set on it.
    :param project_root: The repository to run within.
    :raises UnknownPlanError: If the plan has no manifest on the notes branch.
    :raises UnknownItemError: If the plan tracks no item of that id.
    :return: What was written.
    """
    documents = PlanDocuments.load(request.plan_identifier, project_root)
    values_by_key = dict(request.values_by_key)
    if request.notes_to_append is not None:
        values_by_key[ManifestKey.NOTES] = extend_note(
            documents.item(request.item_identifier).get(ManifestKey.NOTES.key),
            request.notes_to_append,
        )
    manifest_text = apply_item_fields(
        documents.manifest_text,
        request.plan_identifier,
        request.item_identifier,
        {key: written_value(value) for key, value in values_by_key.items()},
    )
    documents.save(manifest_text, documents.roadmap_text, project_root)
    written_note = values_by_key.get(ManifestKey.NOTES)
    return BootstrapReport(
        exit_code=ExitCode.SUCCESS,
        plan_identifier=request.plan_identifier,
        item_identifier=request.item_identifier,
        note_paragraphs=(
            note_paragraph_count(written_note) if written_note is not None else None
        ),
    )


def written_value(value: Any) -> str | Sequence[str]:
    """
    A caller's value in the form a key renders, so callers can pass what they hold.

    :param value: The value to write - a status, a number, prose, or a sequence.
    :return: The value a :class:`ManifestKey` renders.
    """
    if isinstance(value, str) or not isinstance(value, Sequence):
        return str(value)
    return [str(entry) for entry in value]


# %% repairing words an earlier wrap broke


BROKEN_WORD_PATTERN = re.compile(r"([A-Za-z0-9_.]+)- ([A-Za-z0-9_.]+)")
"""
A hyphenated word with a space after the hyphen, which a wrap that broke on hyphens
leaves behind once a folded scalar reads the break back as a space.

Matching is not deciding: a suspended hyphen (*network- and credential-free*) has the
same shape and is correct English. :func:`repairable_words` is what tells them apart.
"""


@dataclass(frozen=True)
class BrokenWord:
    """
    One word an earlier wrap may have broken, and what rejoining it would give.
    """

    broken: str
    """
    The word as the manifest carries it now, hyphen and space included.
    """

    rejoined: str
    """
    What it reads as with the break closed up.
    """

    repaired: bool
    """
    Whether this one was rejoined, as against left for a person.
    """

    def to_json(self) -> dict[str, Any]:
        """
        Render the word as the JSON a caller reads.
        """
        return {
            ReportKey.BROKEN: self.broken,
            ReportKey.REJOINED: self.rejoined,
            ReportKey.REPAIRED: self.repaired,
        }


def repairable_words(text: str, corpus: str) -> list[BrokenWord]:
    """
    Every apparently broken word in *text*, and whether rejoining it is safe.

    A break is only rejoined when the rejoined word occurs somewhere in *corpus*
    unbroken - inside a longer compound counts, since *plan-item-kickoff* is evidence
    that *plan-item* is a word somebody wrote. That is the bug's own signature rather
    than a guess about English: a wrap breaks a word its author wrote whole, and such a
    word is written elsewhere. A suspended hyphen fails the test, since *network-and*
    appears nowhere.

    The cost of the rule is that a genuinely broken word occurring exactly once is left
    alone. That is the safe direction - it is reported rather than rewritten, where the
    opposite error silently edits somebody's prose.

    :param text: The value to examine.
    :param corpus: The whole plan's text, as the evidence for what a word looks like.
    :return: Every candidate, in the order they appear.
    """
    candidates = []
    for match in BROKEN_WORD_PATTERN.finditer(text):
        rejoined = f"{match.group(1)}-{match.group(2)}"
        candidates.append(
            BrokenWord(
                broken=match.group(0),
                rejoined=rejoined,
                repaired=rejoined in corpus,
            )
        )
    return candidates


def repair_text(text: str, corpus: str) -> tuple[str, list[BrokenWord]]:
    """
    Close up every break in *text* that :func:`repairable_words` judges safe.

    :param text: The value to repair.
    :param corpus: The whole plan's text, as the evidence for what a word looks like.
    :return: The repaired value, and every candidate found.
    """
    candidates = repairable_words(text, corpus)
    repaired = text
    for candidate in candidates:
        if candidate.repaired:
            repaired = repaired.replace(candidate.broken, candidate.rejoined)
    return repaired, candidates


@dataclass(frozen=True)
class RepairReport:
    """
    Every broken word a plan's notes carry, and which of them were rejoined.
    """

    plan_identifier: str
    """
    The plan that was repaired.
    """

    words_by_item: dict[str, list[BrokenWord]]
    """
    Every candidate found, by the item whose note carries it.
    """

    @property
    def left_for_a_person(self) -> list[BrokenWord]:
        """
        Every candidate the rule declined to rejoin.
        """
        return [
            word
            for words in self.words_by_item.values()
            for word in words
            if not word.repaired
        ]

    @property
    def exit_code(self) -> ExitCode:
        """
        The status the process exits with, so a caller acting on the status alone sees
        that something is still broken rather than reading a partial repair as a clean
        one.
        """
        return (
            ExitCode.TEXT_NEEDS_REPAIR if self.left_for_a_person else ExitCode.SUCCESS
        )

    def to_json(self) -> dict[str, Any]:
        """
        Render the report as the JSON a caller reads, led by what it means.
        """
        return {
            ReportKey.STATUS: self.exit_code.name_for_a_caller,
            ReportKey.EXIT_CODE: int(self.exit_code),
            ReportKey.PLAN: self.plan_identifier,
            ReportKey.REPAIRS: {
                item_identifier: [word.to_json() for word in words]
                for item_identifier, words in self.words_by_item.items()
            },
            ReportKey.DASHBOARD_COMMAND: f"/plan-dashboard {self.plan_identifier}",
        }


def repair_plan(plan_identifier: str, project_root: Path) -> RepairReport:
    """
    Rejoin the words an earlier wrap broke across a plan's recorded notes.

    A fix to the writer stops it breaking new words; it does not repair what it already
    wrote, and nothing else is looking at those values.

    :param plan_identifier: The plan to repair.
    :param project_root: The repository to run within.
    :raises UnknownPlanError: If the plan has no manifest on the notes branch.
    :return: What was found and what was rejoined.
    """
    documents = PlanDocuments.load(plan_identifier, project_root)
    corpus = documents.manifest_text + documents.roadmap_text
    manifest_text = documents.manifest_text
    words_by_item: dict[str, list[BrokenWord]] = {}

    for item in documents.manifest[ManifestKey.ITEMS.key]:
        note = item.get(ManifestKey.NOTES.key)
        if not note:
            continue
        repaired, candidates = repair_text(note, corpus)
        if not candidates:
            continue
        words_by_item[item[ManifestKey.IDENTIFIER.key]] = candidates
        if repaired != note:
            manifest_text = apply_item_fields(
                manifest_text,
                plan_identifier,
                item[ManifestKey.IDENTIFIER.key],
                {ManifestKey.NOTES: repaired},
            )

    if manifest_text != documents.manifest_text:
        documents.save(manifest_text, documents.roadmap_text, project_root)
    return RepairReport(plan_identifier=plan_identifier, words_by_item=words_by_item)


# %% checking what the manifest claims against local git


@dataclass(frozen=True)
class StalenessFinding:
    """
    One recorded field that local git contradicts.
    """

    manifest_key: ManifestKey
    """
    The field whose recorded value is stale.
    """

    recorded: str | None
    """
    What the manifest says, or ``None`` where it says nothing.
    """

    observed: str
    """
    What git shows instead, in the terms a reader acts on.
    """

    def to_json(self) -> dict[str, Any]:
        """
        Render the finding as the JSON a caller reads.
        """
        return {
            ReportKey.FIELD: self.manifest_key.key,
            ReportKey.RECORDED: self.recorded,
            ReportKey.OBSERVED: self.observed,
        }


@dataclass(frozen=True)
class StalenessReport:
    """
    Which of an item's recorded fields local git contradicts, if any.
    """

    plan_identifier: str
    """
    The plan the item belongs to.
    """

    item_identifier: str
    """
    The item that was checked.
    """

    findings: list[StalenessFinding]
    """
    Every stale field, in the order the fields are checked.
    """

    @property
    def exit_code(self) -> ExitCode:
        """
        The status the process exits with, so a caller acting on the status alone reads
        a stale manifest as something to fix rather than as a clean run.
        """
        return ExitCode.MANIFEST_IS_STALE if self.findings else ExitCode.SUCCESS

    def to_json(self) -> dict[str, Any]:
        """
        Render the report as the JSON a caller reads, led by what it means.
        """
        return {
            ReportKey.STATUS: self.exit_code.name_for_a_caller,
            ReportKey.EXIT_CODE: int(self.exit_code),
            ReportKey.PLAN: self.plan_identifier,
            ReportKey.ITEM: self.item_identifier,
            ReportKey.FINDINGS: [finding.to_json() for finding in self.findings],
            ReportKey.DASHBOARD_COMMAND: f"/plan-dashboard {self.plan_identifier}",
        }


def check_item(
    plan_identifier: str,
    item_identifier: str,
    project_root: Path,
    remote: str = "origin",
) -> StalenessReport:
    """
    Compare one item's recorded fields against what local git actually shows.

    Deliberately local-only. The dashboard already compares the manifest against GitHub
    after the fact; what nothing covers is the window before a push, where a session
    knows the branch exists and every other reader still sees ``not_started``. Answering
    it from git alone also keeps this importable by a hook, which cannot reach
    ``sync_manifest_status.py`` - that module imports ``build_dashboard``, and so needs
    jinja2 and markdown.

    :param plan_identifier: The plan the item belongs to.
    :param item_identifier: The item to check.
    :param project_root: The repository to run within.
    :param remote: The remote a branch would be published to.
    :raises UnknownPlanError: If the plan has no manifest on the notes branch.
    :raises UnknownItemError: If the plan tracks no item of that id.
    :return: What is stale, if anything.
    """
    documents = PlanDocuments.load(plan_identifier, project_root)
    item = documents.item(item_identifier)
    recorded_branch = item.get(ManifestKey.BRANCH.key)
    findings: list[StalenessFinding] = []

    if recorded_branch and not branch_is_published(
        recorded_branch, remote=remote, project_root=project_root
    ):
        findings.append(
            StalenessFinding(
                manifest_key=ManifestKey.BRANCH,
                recorded=recorded_branch,
                observed=f"no branch of that name on {remote}",
            )
        )
        return StalenessReport(plan_identifier, item_identifier, findings)

    if not recorded_branch:
        return StalenessReport(plan_identifier, item_identifier, findings)

    findings.extend(fields_a_published_branch_requires(item, recorded_branch))
    return StalenessReport(plan_identifier, item_identifier, findings)


def fields_a_published_branch_requires(
    item: dict[str, Any], branch: str
) -> list[StalenessFinding]:
    """
    The fields an item whose branch is published should already carry.

    :param item: The item's parsed manifest mapping.
    :param branch: The published branch it records.
    :return: One finding per field the item still leaves unset or contradicts.
    """
    observed = f"{branch} is published"
    findings = [
        StalenessFinding(
            manifest_key=manifest_key,
            recorded=None,
            observed=observed,
        )
        for manifest_key in (ManifestKey.SESSION, ManifestKey.PULL_REQUEST_NUMBER)
        if item.get(manifest_key.key) is None
    ]
    recorded_status = item.get(ManifestKey.STATUS.key)
    if recorded_status == ItemStatus.NOT_STARTED.value:
        findings.insert(
            0,
            StalenessFinding(
                manifest_key=ManifestKey.STATUS,
                recorded=recorded_status,
                observed=observed,
            ),
        )
    return findings


# %% resolving a branch to the items it carries


BLOCKER_OWNER_SEPARATOR = ": "
"""
What separates the owner of a written blocker from its reason.

An automated caller writes ``<owner>: <reason>`` so that the pass which wrote a blocker
is the only one that replaces or clears it, and a blocker a person wrote carries no
owner and is therefore never touched.
"""


def plan_tracking(branch: str, project_root: Path) -> str | None:
    """
    The plan that tracks *branch*, per the generated branch index.

    Calls the shell configuration's own lookup rather than reading the index here, so
    this and every other reader agree on where the index lives and how it is written.

    :param branch: The branch to look up.
    :param project_root: The repository to run within.
    :raises NotesBranchUnavailableError: If the notes branch cannot be fetched.
    :return: The plan's id, or None when no plan claims the branch.
    """
    fetch_notes_branch(project_root)
    lookup = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HookScript.CONFIGURATION.path}" && plan_id_for_branch "$1"',
            HookScript.CONFIGURATION.value,
            branch,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    return lookup.stdout.strip() or None


@dataclass(frozen=True)
class TrackedItem:
    """
    One item a branch carries, in the shape a caller deciding what to write reads it.
    """

    item_identifier: str
    """
    The item's id.
    """

    status: ItemStatus
    """
    The status the manifest records for it right now.
    """

    blockers: list[str]
    """
    What the manifest records as blocking it right now.
    """

    def blockers_not_owned_by(self, owner: str) -> list[str]:
        """
        Every blocker except the ones *owner* wrote, in their recorded order.

        :param owner: The automated caller whose blockers are its own to replace.
        :return: The blockers it must leave alone.
        """
        prefix = f"{owner}{BLOCKER_OWNER_SEPARATOR}"
        return [blocker for blocker in self.blockers if not blocker.startswith(prefix)]

    def to_json(self) -> dict[str, Any]:
        """
        Render the item as the JSON a caller reads.
        """
        return {
            ReportKey.ITEM: self.item_identifier,
            ManifestKey.STATUS.key: self.status.value,
            ManifestKey.BLOCKERS.key: self.blockers,
        }


@dataclass(frozen=True)
class ItemWrite(TrackedItem):
    """
    One item's recorded state after a write, and the status it carried before it.

    A written item is still a tracked item - the same id, status and blockers a reader
    acts on - so a caller reading either operation's report reads one shape.
    """

    previous_status: ItemStatus
    """
    The status the manifest recorded before the write.
    """

    def to_json(self) -> dict[str, Any]:
        """
        Render the write as the JSON a caller reads, naming what changed as well as what
        the item now says.
        """
        return {
            **super().to_json(),
            ReportKey.PREVIOUS_STATUS: self.previous_status.value,
        }


@dataclass(frozen=True)
class BranchReport:
    """
    What an operation keyed on a branch found, for every item that branch carries.
    """

    branch: str
    """
    The branch that was looked up.
    """

    plan_identifier: str | None
    """
    The plan tracking it, or None when no plan claims the branch.
    """

    items: list[TrackedItem]
    """
    Every item recording that branch, in manifest order.
    """

    @property
    def exit_code(self) -> ExitCode:
        """
        The status the process exits with, so a caller acting on the status alone
        reports an unclaimed branch rather than writing against a plan it guessed.
        """
        return ExitCode.SUCCESS if self.items else ExitCode.BRANCH_TRACKS_NO_ITEM

    def to_json(self) -> dict[str, Any]:
        """
        Render the report as the JSON a caller reads, led by what it means.
        """
        document: dict[str, Any] = {
            ReportKey.STATUS: self.exit_code.name_for_a_caller,
            ReportKey.EXIT_CODE: int(self.exit_code),
            ManifestKey.BRANCH.key: self.branch,
            ReportKey.PLAN: self.plan_identifier,
            ReportKey.ITEMS: [item.to_json() for item in self.items],
        }
        if self.plan_identifier is not None:
            document[ReportKey.DASHBOARD_COMMAND] = (
                f"/plan-dashboard {self.plan_identifier}"
            )
        return document


def resolve_branch(branch: str, project_root: Path) -> BranchReport:
    """
    Find the plan and the items a branch belongs to.

    A branch can carry more than one item - a plan may split what one branch does into
    several - so every item recording it is answered with, not the first.

    :param branch: The branch to resolve.
    :param project_root: The repository to run within.
    :raises UnknownPlanError: If the index names a plan with no manifest on the branch.
    :return: What the branch belongs to.
    """
    plan_identifier = plan_tracking(branch, project_root)
    if plan_identifier is None:
        return BranchReport(branch=branch, plan_identifier=None, items=[])

    documents = PlanDocuments.load(plan_identifier, project_root)
    items = [
        TrackedItem(
            item_identifier=item[ManifestKey.IDENTIFIER.key],
            status=ItemStatus(item[ManifestKey.STATUS.key]),
            blockers=list(item.get(ManifestKey.BLOCKERS.key) or []),
        )
        for item in documents.manifest[ManifestKey.ITEMS.key]
        if item.get(ManifestKey.BRANCH.key) == branch
    ]
    return BranchReport(branch=branch, plan_identifier=plan_identifier, items=items)


# %% owning a blocker on every item a branch carries


def block_branch(
    branch: str, owner: str, reason: str, project_root: Path
) -> BranchReport:
    """
    Record *owner*'s blocker on every item a branch carries, and mark them blocked.

    Running it again replaces that owner's own blocker rather than adding a second, so a
    pass that keeps finding the same conflict keeps writing the same entry.

    :param branch: The branch whose items are blocked.
    :param owner: The automated caller the blocker belongs to.
    :param reason: Why the branch is blocked, in a reader's terms.
    :param project_root: The repository to run within.
    :return: What was written.
    """
    return write_owned_blocker(
        branch=branch,
        owner=owner,
        reason=reason,
        project_root=project_root,
    )


def unblock_branch(branch: str, owner: str, project_root: Path) -> BranchReport:
    """
    Clear *owner*'s blocker from every item a branch carries.

    An item left carrying somebody else's blocker stays blocked; one left carrying none
    returns to :attr:`ItemStatus.IN_PROGRESS`, since the branch it names exists.

    :param branch: The branch whose items are cleared.
    :param owner: The automated caller whose blocker is being withdrawn.
    :param project_root: The repository to run within.
    :return: What was written.
    """
    return write_owned_blocker(
        branch=branch,
        owner=owner,
        reason=None,
        project_root=project_root,
    )


def write_owned_blocker(
    branch: str, owner: str, reason: str | None, project_root: Path
) -> BranchReport:
    """
    Rewrite every item on a branch with *owner*'s blocker set or withdrawn.

    Both directions are the same write - replace the owner's entries, leave everyone
    else's, then derive the status from what is left - so they cannot disagree about
    which blockers belong to whom.

    Only fields that actually change are written. A pass withdraws its blocker from every
    branch it finds clean, and most of those it never blocked; recording an empty list on
    each would spread noise across the manifest one run at a time.

    :param branch: The branch whose items are written.
    :param owner: The automated caller the blocker belongs to.
    :param reason: Why the branch is blocked, or None to withdraw the blocker.
    :param project_root: The repository to run within.
    :return: What was written.
    """
    resolution = resolve_branch(branch, project_root)
    if not resolution.items:
        return resolution

    writes: list[TrackedItem] = []
    for item in resolution.items:
        blockers = item.blockers_not_owned_by(owner)
        if reason is not None:
            blockers.append(f"{owner}{BLOCKER_OWNER_SEPARATOR}{reason}")
        status = status_beside(blockers, previous=item.status)
        changed = {
            manifest_key: value
            for manifest_key, value, recorded in (
                (ManifestKey.STATUS, status.value, item.status.value),
                (ManifestKey.BLOCKERS, blockers, item.blockers),
            )
            if value != recorded
        }
        if changed:
            update_item(
                ItemUpdateRequest(
                    plan_identifier=resolution.plan_identifier,
                    item_identifier=item.item_identifier,
                    values_by_key=changed,
                ),
                project_root=project_root,
            )
        writes.append(
            ItemWrite(
                item_identifier=item.item_identifier,
                status=status,
                blockers=blockers,
                previous_status=item.status,
            )
        )
    return BranchReport(
        branch=branch, plan_identifier=resolution.plan_identifier, items=writes
    )


def status_beside(blockers: list[str], previous: ItemStatus) -> ItemStatus:
    """
    The status an item carries given what is now blocking it.

    Only the blocked/unblocked axis is decided here: an item nothing blocks keeps
    whatever it already said unless that was :attr:`ItemStatus.BLOCKED`, which the
    blockers it no longer has were the reason for.

    :param blockers: What blocks the item now.
    :param previous: The status it recorded before.
    :return: The status to record.
    """
    if blockers:
        return ItemStatus.BLOCKED
    if previous is ItemStatus.BLOCKED:
        return ItemStatus.IN_PROGRESS
    return previous


def append_roadmap_section(roadmap_text: str, section: str) -> str:
    """
    Add one section to the end of a roadmap, separated by a blank line.

    :param roadmap_text: The roadmap as it stands.
    :param section: The markdown to append.
    :return: The extended roadmap.
    """
    return f"{roadmap_text.rstrip(chr(10))}\n\n{section.lstrip(chr(10))}"


# %% opening the work


@dataclass(frozen=True)
class PullRequestRequest:
    """
    One pull request to create.
    """

    repository: str
    """
    The ``owner/repo`` to create it in.
    """

    title: str
    """
    The pull request's title.
    """

    body: str
    """
    The pull request's description.
    """

    head: str
    """
    The branch carrying the changes.
    """

    base: str
    """
    The branch to merge into.
    """

    draft: bool = True
    """
    Always a draft: this repository's convention is that a pull request stays a draft
    until its author has reviewed it themselves, and at creation time nobody has.
    """


@dataclass(frozen=True)
class CreatedPullRequest:
    """
    The pull request a remote actually created.
    """

    number: int
    """
    Its number.
    """

    html_url: str | None
    """
    Where to read it, unset when the caller supplied the number and already has it.
    """


class PullRequestOpener(Protocol):
    """
    The one call opening the work makes against a forge, kept behind a seam so the
    surrounding git work is testable without network access.
    """

    def open_pull_request(self, request: PullRequestRequest) -> CreatedPullRequest:
        """
        Create *request* and report what came back.

        :param request: The pull request to create.
        :raises PullRequestRefusedError: If the remote declines it.
        :return: The created pull request.
        """


@dataclass(frozen=True)
class GitHubPullRequestOpener:
    """
    Opens pull requests through GitHub's REST API.

    Sends a bearer token when the environment supplies one and nothing otherwise. Inside
    a Claude Code session the credential is inert - the agent proxy substitutes its own
    identity - but the same code run from a terminal or a scheduled Action has no proxy,
    and there the token is the credential. This is deliberately not a third copy of the
    prefer-``gh``-else-token rule ``github-api.sh`` and ``pr_state`` carry between them;
    it is the minimum that works from ``main`` today, for whichever item unifies them to
    absorb.
    """

    api_root: str = GITHUB_API_ROOT
    """
    The API host, overridable for a GitHub Enterprise deployment.
    """

    def open_pull_request(self, request: PullRequestRequest) -> CreatedPullRequest:
        """
        Create *request* through ``POST /repos/{owner}/{repo}/pulls``.

        :param request: The pull request to create.
        :raises PullRequestRefusedError: If GitHub declines the creation.
        :return: The created pull request.
        """
        payload = json.dumps(
            {
                "title": request.title,
                "body": request.body,
                "head": request.head,
                "base": request.base,
                "draft": request.draft,
            }
        ).encode()
        http_request = urllib.request.Request(
            f"{self.api_root}/repos/{request.repository}/pulls",
            data=payload,
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                **self.authorization_headers(),
            },
        )
        try:
            with urllib.request.urlopen(http_request) as response:
                created = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise PullRequestRefusedError(
                detail=f"{error.code} "
                f"{error.read().decode(errors='replace').strip()}"
            ) from error
        return CreatedPullRequest(
            number=created["number"], html_url=created["html_url"]
        )

    @staticmethod
    def authorization_headers() -> dict[str, str]:
        """
        The ``Authorization`` header, when the environment carries a token to send.

        :return: The header, or an empty mapping when there is no token.
        """
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        return {"Authorization": f"Bearer {token}"} if token else {}


@dataclass(frozen=True)
class WorkOpenRequest:
    """
    What opening an item's work needs: the branch to create and the pull request to open
    on it.
    """

    plan_identifier: str
    """
    The plan the item belongs to.
    """

    item_identifier: str
    """
    The item being opened, which must already be tracked.
    """

    branch: str
    """
    The branch to create and publish.
    """

    base_branch: str
    """
    The branch to create it from and target the pull request at.
    """

    session_url: str
    """
    The session doing the work, recorded on the item.

    Required rather than derived: a session's environment cannot be asked which session
    it is, and a script that guessed would record something wrong in silence.
    """

    pull_request_title: str | None = None
    """
    The pull request's title, needed only when this module creates it.
    """

    pull_request_body: str | None = None
    """
    The pull request's description, needed only when this module creates it.
    """

    pull_request_number: int | None = None
    """
    A pull request the caller has already created, recorded instead of creating one.

    A pull request this module creates is attributed to the app the request is proxied
    through rather than to the person whose work it is, so a caller that can create one
    under its own identity should, and hand the number here. Left unset, the module
    creates it - which is what an unattended run with no session has to do.
    """


@dataclass
class WorkOpener:
    """
    The git half of opening an item's work: branch from the base, mark the start, and
    publish.
    """

    project_root: Path
    """
    The repository the branch is created in.
    """

    remote: str = "origin"
    """
    The remote the branch is published to.
    """

    def branch_is_published(self, branch: str) -> bool:
        """
        Whether *branch* already exists on the remote.

        :param branch: The branch to look for.
        :return: True when the remote already carries it.
        """
        return branch_is_published(
            branch, remote=self.remote, project_root=self.project_root
        )

    def publish(self, request: WorkOpenRequest) -> None:
        """
        Create the branch from its base and push it, so a pull request has a head.

        The opening commit is empty by construction: the whole point of this tool is
        that the branch exists before any implementation does, and a pull request needs
        a commit its base does not have.

        :param request: The work being opened.
        """
        run_git(
            "checkout",
            "-b",
            request.branch,
            request.base_branch,
            project_root=self.project_root,
        )
        run_git(
            "commit",
            "--allow-empty",
            "--quiet",
            "-m",
            f"Bootstrap {request.item_identifier}",
            project_root=self.project_root,
        )
        run_git(
            "push", "-u", self.remote, request.branch, project_root=self.project_root
        )


def open_work(
    request: WorkOpenRequest,
    project_root: Path,
    pull_request_opener: PullRequestOpener | None = None,
    remote: str = "origin",
) -> BootstrapReport:
    """
    Create the item's branch and draft pull request, then record both on the item.

    Both refusals this can raise before publishing - an untracked item, an already
    published branch - are checked first, so neither leaves anything behind. A pull
    request the remote declines is the one case that does: the branch is already
    published by then and stays, since a session cannot delete a remote branch. The
    manifest is left untouched rather than pointing at a pull request that does not
    exist, and re-running once the refusal is understood is refused by the
    already-published guard rather than silently overwriting those commits.

    :param request: The work to open.
    :param project_root: The repository to run within.
    :param pull_request_opener: What creates the pull request, defaulting to GitHub.
    :param remote: The remote to publish the branch to.
    :raises UnknownItemError: If the plan does not track the item yet.
    :raises PullRequestDetailsMissingError: If it must create a pull request but was
        given nothing to create one from.
    :raises BranchAlreadyPublishedError: If the branch already exists on the remote.
    :raises PullRequestRefusedError: If the pull request could not be created.
    :return: What was opened.
    """
    opener = pull_request_opener or GitHubPullRequestOpener()
    if request.pull_request_number is None and not (
        request.pull_request_title and request.pull_request_body
    ):
        raise PullRequestDetailsMissingError(item_identifier=request.item_identifier)
    documents = PlanDocuments.load(request.plan_identifier, project_root)
    repository = documents.repository_for(request.item_identifier)

    work = WorkOpener(project_root=project_root, remote=remote)
    if not work.branch_is_published(request.branch):
        work.publish(request)
    elif request.pull_request_number is None:
        raise BranchAlreadyPublishedError(branch=request.branch, remote=remote)

    created = (
        CreatedPullRequest(number=request.pull_request_number, html_url=None)
        if request.pull_request_number is not None
        else opener.open_pull_request(
            PullRequestRequest(
                repository=repository,
                title=request.pull_request_title,
                body=request.pull_request_body,
                head=request.branch,
                base=request.base_branch,
            )
        )
    )

    manifest_text = apply_item_fields(
        documents.manifest_text,
        request.plan_identifier,
        request.item_identifier,
        {
            ManifestKey.BRANCH: request.branch,
            ManifestKey.PULL_REQUEST_NUMBER: str(created.number),
            ManifestKey.SESSION: request.session_url,
            ManifestKey.STATUS: ItemStatus.IN_PROGRESS.value,
        },
    )
    documents.save(manifest_text, documents.roadmap_text, project_root)
    return BootstrapReport(
        exit_code=ExitCode.SUCCESS,
        plan_identifier=request.plan_identifier,
        item_identifier=request.item_identifier,
        branch=request.branch,
        pull_request_number=created.number,
        pull_request_url=created.html_url,
    )


# %% command line


OperationReport = BootstrapReport | BranchReport | StalenessReport | RepairReport
"""
What any of the operations answers with: a report carrying both the status the process
exits with and the JSON a caller reads.
"""


@dataclass(frozen=True)
class Subcommand(ABC):
    """
    One operation the command line offers, owning both its flags and the work it runs.

    :data:`SUBCOMMANDS` is built by instantiating every subclass, so a command that
    exists is reachable by construction rather than by also being listed somewhere.
    """

    @property
    @abstractmethod
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command on the command line.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        :return: What the command does, as ``--help`` puts it.
        """

    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the flags this command takes.

        :param parser: The subparser to declare them on.
        """

    @abstractmethod
    def run(self, arguments: argparse.Namespace, project_root: Path) -> OperationReport:
        """
        Do the work the parsed command line asks for.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What the operation found or wrote.
        """


@dataclass(frozen=True)
class RecordSubcommand(Subcommand):
    """
    Write an item's manifest entry and its roadmap section.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "record"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Write an item's manifest entry and roadmap section"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the item to record and the section to record it with.

        :param parser: The subparser to declare them on.
        """
        parser.add_argument("--plan", required=True)
        parser.add_argument("--item", required=True)
        parser.add_argument("--status", required=True, type=ItemStatus)
        parser.add_argument("--roadmap-section", required=True, type=Path)
        parser.add_argument("--title")
        parser.add_argument("--track")

    def run(self, arguments: argparse.Namespace, project_root: Path) -> BootstrapReport:
        """
        Record the item.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What was recorded.
        """
        return record_item(
            ItemRecordRequest(
                plan_identifier=arguments.plan,
                item_identifier=arguments.item,
                status=arguments.status,
                roadmap_section_path=arguments.roadmap_section,
                title=arguments.title,
                track=arguments.track,
            ),
            project_root=project_root,
        )


@dataclass(frozen=True)
class UpdateSubcommand(Subcommand):
    """
    Set an item's recorded fields, without demanding a roadmap section.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "update"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Set an item's recorded fields, without a roadmap section"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare every field this command can set.

        :param parser: The subparser to declare them on.
        """
        parser.add_argument("--plan", required=True)
        parser.add_argument("--item", required=True)
        parser.add_argument("--status", type=ItemStatus)
        parser.add_argument("--branch")
        parser.add_argument("--pull-request-number", type=int)
        parser.add_argument("--session")
        notes = parser.add_mutually_exclusive_group()
        notes.add_argument(
            "--notes", type=Path, help="A file whose text becomes the item's notes"
        )
        notes.add_argument(
            "--append-notes",
            type=Path,
            help="A file whose text is added to the item's notes as a new paragraph",
        )
        parser.add_argument(
            "--blockers",
            type=Path,
            action="append",
            help="A file whose text becomes one blocker; repeat for each",
        )

    def run(self, arguments: argparse.Namespace, project_root: Path) -> BootstrapReport:
        """
        Write whichever fields the command line named.

        Prose comes from files rather than the command line, the same way
        ``--pull-request-body`` already does: a note is routinely longer than a shell
        invocation should carry.

        ``--append-notes`` extends the recorded note instead of replacing it, so a
        caller adding to one never has to read it back and restore its paragraph breaks
        itself - see :func:`extend_note` for why those two forms differ.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What was written.
        """
        values_by_key: dict[ManifestKey, Any] = {
            manifest_key: value
            for manifest_key, value in (
                (ManifestKey.STATUS, arguments.status),
                (ManifestKey.BRANCH, arguments.branch),
                (ManifestKey.PULL_REQUEST_NUMBER, arguments.pull_request_number),
                (ManifestKey.SESSION, arguments.session),
            )
            if value is not None
        }
        if arguments.notes:
            values_by_key[ManifestKey.NOTES] = arguments.notes.read_text()
        if arguments.blockers:
            values_by_key[ManifestKey.BLOCKERS] = [
                blocker.read_text().strip() for blocker in arguments.blockers
            ]
        return update_item(
            ItemUpdateRequest(
                plan_identifier=arguments.plan,
                item_identifier=arguments.item,
                values_by_key=values_by_key,
                notes_to_append=(
                    arguments.append_notes.read_text()
                    if arguments.append_notes
                    else None
                ),
            ),
            project_root=project_root,
        )


@dataclass(frozen=True)
class ResolveSubcommand(Subcommand):
    """
    Name the plan and the items a branch belongs to.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "resolve"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Name the plan and items a branch belongs to"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the branch to look up.

        :param parser: The subparser to declare it on.
        """
        parser.add_argument("--branch", required=True)

    def run(self, arguments: argparse.Namespace, project_root: Path) -> BranchReport:
        """
        Look the branch up.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What the branch belongs to.
        """
        return resolve_branch(arguments.branch, project_root=project_root)


@dataclass(frozen=True)
class BlockSubcommand(Subcommand):
    """
    Record your own blocker on every item a branch carries.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "block"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Record your own blocker on every item a branch carries"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the branch, the blocker's owner, and the reason.

        :param parser: The subparser to declare them on.
        """
        parser.add_argument("--branch", required=True)
        parser.add_argument("--owner", required=True)
        parser.add_argument(
            "--reason",
            required=True,
            type=Path,
            help="A file whose text is the blocker",
        )

    def run(self, arguments: argparse.Namespace, project_root: Path) -> BranchReport:
        """
        Write the blocker.

        The reason comes from a file for the same reason a note does: it is routinely
        longer than a shell invocation should carry.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What was written.
        """
        return block_branch(
            arguments.branch,
            owner=arguments.owner,
            reason=arguments.reason.read_text().strip(),
            project_root=project_root,
        )


@dataclass(frozen=True)
class UnblockSubcommand(Subcommand):
    """
    Clear your own blocker from every item a branch carries.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "unblock"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Clear your own blocker from every item a branch carries"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the branch and whose blocker to withdraw.

        :param parser: The subparser to declare them on.
        """
        parser.add_argument("--branch", required=True)
        parser.add_argument("--owner", required=True)

    def run(self, arguments: argparse.Namespace, project_root: Path) -> BranchReport:
        """
        Withdraw the blocker.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What was written.
        """
        return unblock_branch(
            arguments.branch, owner=arguments.owner, project_root=project_root
        )


@dataclass(frozen=True)
class CheckSubcommand(Subcommand):
    """
    Report which of an item's recorded fields local git contradicts.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "check"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Report which recorded fields local git contradicts"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the item to check and the remote to measure it against.

        :param parser: The subparser to declare them on.
        """
        parser.add_argument("--plan", required=True)
        parser.add_argument("--item", required=True)
        parser.add_argument("--remote", default="origin")

    def run(self, arguments: argparse.Namespace, project_root: Path) -> StalenessReport:
        """
        Compare the item's recorded fields against local git.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What is stale, if anything.
        """
        return check_item(
            arguments.plan,
            arguments.item,
            project_root=project_root,
            remote=arguments.remote,
        )


@dataclass(frozen=True)
class OpenSubcommand(Subcommand):
    """
    Create the item's branch and draft pull request, and record them.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "open"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Create the item's branch and draft pull request"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the branch to open and how to reach its pull request.

        :param parser: The subparser to declare them on.
        """
        parser.add_argument("--plan", required=True)
        parser.add_argument("--item", required=True)
        parser.add_argument("--branch", required=True)
        parser.add_argument("--base", required=True)
        parser.add_argument("--session", required=True)
        parser.add_argument(
            "--pull-request-title",
            help="Required unless --pull-request-number is given",
        )
        parser.add_argument(
            "--pull-request-body",
            type=Path,
            help="Required unless --pull-request-number is given",
        )
        parser.add_argument(
            "--pull-request-number",
            type=int,
            help=(
                "Record a pull request the caller already created, instead of "
                "creating one"
            ),
        )
        parser.add_argument("--remote", default="origin")

    def run(self, arguments: argparse.Namespace, project_root: Path) -> BootstrapReport:
        """
        Open the branch and pull request.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What was opened.
        """
        return open_work(
            WorkOpenRequest(
                plan_identifier=arguments.plan,
                item_identifier=arguments.item,
                branch=arguments.branch,
                base_branch=arguments.base,
                session_url=arguments.session,
                pull_request_title=arguments.pull_request_title,
                pull_request_body=(
                    arguments.pull_request_body.read_text()
                    if arguments.pull_request_body
                    else None
                ),
                pull_request_number=arguments.pull_request_number,
            ),
            project_root=project_root,
            remote=arguments.remote,
        )


@dataclass(frozen=True)
class RepairSubcommand(Subcommand):
    """
    Rejoin the words an earlier wrap broke across a plan's recorded notes.
    """

    @property
    def invoked_as(self) -> str:
        """
        :return: The word that selects this command.
        """
        return "repair"

    @property
    def description(self) -> str:
        """
        :return: What the command does.
        """
        return "Rejoin words an earlier wrap broke across a plan's notes"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """
        Declare the plan to repair.

        :param parser: The subparser to declare it on.
        """
        parser.add_argument("--plan", required=True)

    def run(self, arguments: argparse.Namespace, project_root: Path) -> RepairReport:
        """
        Repair what can be repaired safely, and report the rest.

        :param arguments: The parsed command line.
        :param project_root: The repository to run within.
        :return: What was found and what was rejoined.
        """
        return repair_plan(arguments.plan, project_root=project_root)


SUBCOMMANDS: dict[str, Subcommand] = {
    subcommand.invoked_as: subcommand
    for subcommand in (subclass() for subclass in Subcommand.__subclasses__())
}
"""
Every operation the command line offers, by the word that selects it.

Found from the subclasses rather than listed, since the list carried nothing a reader
needs: it is the classes themselves that say what each command is and takes.
"""


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser from the commands themselves.

    :return: The parser.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for subcommand in SUBCOMMANDS.values():
        subcommand.add_arguments(
            subparsers.add_parser(subcommand.invoked_as, help=subcommand.description)
        )
    return parser


def main() -> int:
    """
    Parse arguments, run the requested operation, and print its report.

    See the module docstring for the command line contract.
    """
    arguments = build_parser().parse_args()
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))

    try:
        report = SUBCOMMANDS[arguments.subcommand].run(arguments, project_root)
    except BootstrapError as error:
        print(f"{error.exit_code.name_for_a_caller}: {error}", file=sys.stderr)
        return int(error.exit_code)

    print(json.dumps(report.to_json()))
    return int(report.exit_code)


if __name__ == "__main__":
    sys.exit(main())
