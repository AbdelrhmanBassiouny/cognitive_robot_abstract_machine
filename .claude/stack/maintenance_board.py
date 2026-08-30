"""
Reading fetched pull requests into the board the stack is derived from.

A fetch that drops a field is not partially correct, so every field the board is derived
from is declared with how to read it and whether it may be absent, and a record omitting
a required one is rejected rather than defaulted.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from integration_constants import CANDIDATE_TITLE_PREFIX, POINTER_BRANCH
from maintenance_constants import SESSION_LINK_PATTERN
from stack import BOARD_PATH, PullRequest

PullRequestRecord = Mapping[str, Any]
"""
One pull request as the REST API answers it, before any field is read.
"""

# %% the fields a board is read from


class PullRequestFieldShape(StrEnum):
    """
    How one pull-request field's value has to be read.

    The API answers some fields with a nested object where a plain value would do, so
    reading is per-field rather than uniform.
    """

    VALUE = "value"
    """
    Taken as it comes.
    """

    BRANCH_REFERENCE = "branch-reference"
    """
    A branch, given either plainly or as an object carrying a ``ref``.
    """

    LABEL_NAMES = "label-names"
    """
    A list of labels, each given either plainly or as an object carrying a ``name``.
    """

    COMMIT = "commit"
    """
    The commit a branch reference points at, which the same object carries as ``sha``.
    """


class BranchReferenceKey(StrEnum):
    """
    What the object a pull request gives for its head or base carries.
    """

    BRANCH = "ref"
    """
    The branch's name.
    """

    COMMIT = "sha"
    """
    The commit it points at, which is what checks are reported against.
    """


@dataclass(frozen=True)
class PullRequestFieldSpecification:
    """
    What one pull-request field is called, how to read it, and whether it may be absent.
    """

    key: str
    """
    The key the API answers under.
    """

    shape: PullRequestFieldShape = PullRequestFieldShape.VALUE
    """
    How its value has to be read.
    """

    required: bool = False
    """
    Whether a record omitting it is rejected rather than read.
    """


class PullRequestField(PullRequestFieldSpecification, Enum):
    """
    Every pull-request field this executor reads, and how to read it.

    Each member *is* a specification, so nothing outside this enum knows that ``head``
    arrives nested while ``draft`` does not, or which fields a board cannot be derived
    without.

    A member is written as the specification it carries, and :meth:`__init__` unpacks it
    onto the member itself - so ``PullRequestField.HEAD.key`` reads directly and the
    member is a :class:`PullRequestFieldSpecification` in its own right.
    """

    def __init__(self, specification: PullRequestFieldSpecification) -> None:
        """
        Carry the specification's values on the member itself.

        Without this the mixin would receive the whole specification as its first
        argument - silently, landing the instance in :attr:`key` - since an enum passes
        a member's value straight to the type it mixes in.

        :param specification: What this field is called and how to read it.
        """
        for field in dataclasses.fields(PullRequestFieldSpecification):
            object.__setattr__(self, field.name, getattr(specification, field.name))

    NUMBER = PullRequestFieldSpecification(key="number", required=True)
    """
    The pull request's number.
    """
    HEAD = PullRequestFieldSpecification(
        key="head", shape=PullRequestFieldShape.BRANCH_REFERENCE, required=True
    )
    """The branch the pull request would merge - the stack node it names."""
    BASE = PullRequestFieldSpecification(
        key="base", shape=PullRequestFieldShape.BRANCH_REFERENCE, required=True
    )
    """The branch it would merge into - its parent in the stack."""
    DRAFT = PullRequestFieldSpecification(key="draft", required=True)
    """
    Whether its author has yet reviewed it themselves.
    """
    LABELS = PullRequestFieldSpecification(
        key="labels", shape=PullRequestFieldShape.LABEL_NAMES, required=True
    )
    """
    The labels it carries, which the workflow reads as state.
    """
    HEAD_COMMIT = PullRequestFieldSpecification(
        key="head", shape=PullRequestFieldShape.COMMIT, required=True
    )
    """The commit that branch points at, which is what checks are reported against."""
    BODY = PullRequestFieldSpecification(key="body")
    """
    Its description, read for the session link and the promotion prefill.
    """
    TITLE = PullRequestFieldSpecification(key="title")
    """
    Its title, which prefills the upstream pull request.
    """
    MERGEABLE_STATE = PullRequestFieldSpecification(key="mergeable_state")
    """
    GitHub's own verdict on whether it currently conflicts with its base.
    """

    def read(self, record: PullRequestRecord, number: int | None = None) -> Any:
        """
        Read this field out of a fetched pull request.

        :param record: The fetched pull request.
        :param number: The pull request being read, named in any rejection.
        :return: The field's value, read according to its shape.
        :raises MissingPullRequestFieldError: If a required field is absent, or its
            value carries no name where its shape says one belongs.
        """
        value = record.get(self.key)
        if value is None:
            if self.required:
                raise MissingPullRequestFieldError(self, number)
            return None
        match self.shape:
            case PullRequestFieldShape.BRANCH_REFERENCE:
                return self._nested(value, BranchReferenceKey.BRANCH, number)
            case PullRequestFieldShape.COMMIT:
                return self._nested(value, BranchReferenceKey.COMMIT, number)
            case PullRequestFieldShape.LABEL_NAMES:
                return [
                    label if isinstance(label, str) else str(label["name"])
                    for label in value
                ]
            case _:
                return value

    def _nested(
        self, value: Any, wanted: BranchReferenceKey, number: int | None
    ) -> str:
        """
        Read one half of the object a pull request gives for a branch, taking a plain
        string as the branch it names.

        :param value: The field's value, plain or nested.
        :param wanted: Which half to read.
        :param number: The pull request being read, named in any rejection.
        :return: What it names.
        :raises MissingPullRequestFieldError: If it names none.
        """
        if isinstance(value, str) and wanted is BranchReferenceKey.BRANCH:
            return value
        if isinstance(value, Mapping) and value.get(wanted):
            return str(value[wanted])
        raise MissingPullRequestFieldError(self, number)


@dataclass
class MissingPullRequestFieldError(ValueError):
    """
    Raised when a fetched pull request omits a field the board is derived from.

    A fetch that drops a field is not partially correct: absent and legitimately empty
    are different facts, and defaulting one to the other is what makes bad board data
    indistinguishable from good.
    """

    field_name: PullRequestField
    """
    The field that was absent.
    """

    pull_request_number: int | None
    """
    The pull request it was absent from, or ``None`` when the number itself is.
    """

    def __str__(self) -> str:
        """:return: Which field is missing, and from where."""
        subject = (
            f"pull request {self.pull_request_number}"
            if self.pull_request_number is not None
            else "a fetched pull request"
        )
        return (
            f"{subject} has no '{self.field_name}'; the board cannot be derived from a "
            f"fetch that omits it"
        )


def get_session_link_in(body: str | None) -> str | None:
    """
    Read the session link out of a pull request description.

    :param body: The description to search, which may be absent.
    :return: The first session link, or ``None`` if the description names none.
    """
    if not body:
        return None
    found = SESSION_LINK_PATTERN.search(body)
    return found.group(0) if found else None


# %% the export itself


@dataclass(frozen=True)
class BoardExport:
    """
    The fork's open pull requests, in the shape the derived stack is read from.
    """

    pull_requests: tuple[PullRequest, ...]
    """
    The exported pull requests.
    """

    @classmethod
    def from_api_records(cls, records: Iterable[PullRequestRecord]) -> BoardExport:
        """
        Build the export from what the REST API returned, leaving out any candidate.

        A candidate is a build being judged rather than work in flight, and it is
        indistinguishable from an ordinary reviewed branch to everything reading the
        board: a build would merge it, putting the previous build inside the next, and a
        maintenance pass would restack it onto the branch it exists to replace. Left out
        here rather than at each reader, so no pass has to remember to.

        :param records: The fetched pull requests.
        :return: The export.
        :raises MissingPullRequestFieldError: If any record omits a required field.
        """
        return cls(
            tuple(
                cls._pull_request(record)
                for record in records
                if not cls.is_a_candidate(
                    record, int(PullRequestField.NUMBER.read(record))
                )
            )
        )

    @staticmethod
    def is_a_candidate(record: PullRequestRecord, number: int) -> bool:
        """
        Whether one open pull request is a build opened to collect the checks that judge
        it.

        Two facts say so, and both are needed. A candidate for a whole build is opened
        against the branch a build publishes to, which nothing else is; one for a build
        of some plans only is opened against the upstream base, like every ordinary
        branch, and what tells it apart there is the title it is given. Read together, so
        neither kind is left on the board for a pass to restack.

        :param record: One open pull request, as the API answers it.
        :param number: Its number, named in any rejection.
        :return: Whether it is a candidate.
        """
        title = PullRequestField.TITLE.read(record, number) or ""
        return PullRequestField.BASE.read(
            record, number
        ) == POINTER_BRANCH or title.startswith(CANDIDATE_TITLE_PREFIX)

    @staticmethod
    def _pull_request(record: PullRequestRecord) -> PullRequest:
        """
        Read one fetched pull request into a board entry.

        :param record: The fetched pull request.
        :return: The board entry.
        :raises MissingPullRequestFieldError: If a required field is absent.
        """
        number = int(PullRequestField.NUMBER.read(record))
        return PullRequest(
            number=number,
            head=PullRequestField.HEAD.read(record, number),
            base=PullRequestField.BASE.read(record, number),
            draft=bool(PullRequestField.DRAFT.read(record, number)),
            labels=PullRequestField.LABELS.read(record, number),
            ci=record.get("ci"),
            session=get_session_link_in(PullRequestField.BODY.read(record, number)),
        )

    def as_json(self) -> str:
        """:return: The export, in the document :func:`stack.load_board` parses."""
        return json.dumps(
            {"pull_requests": [asdict(entry) for entry in self.pull_requests]},
            indent=2,
        )

    def write(self, path: Path = BOARD_PATH) -> Path:
        """
        Write the export where the derived stack is read from.

        :param path: Where to write it.
        :return: The path written to.
        """
        path.write_text(self.as_json() + "\n")
        return path
