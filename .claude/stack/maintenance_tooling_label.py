"""
Saying which fork pull requests change the tooling, from the files they change.

The label a build reads to decide a collision was applied by hand, so a branch took its
priority from somebody having remembered rather than from what it does. The changed
files answer that question already, and :class:`~changed_paths.ChangedPaths` reads them.

Both directions are written: a pull request that stops being a tooling change loses the
label, so the label says what the files say rather than what they said when it was last
looked at.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from changed_paths import ChangedPaths
from maintenance_board import PullRequestField, PullRequestRecord
from maintenance_github import ForkPullRequests, PullRequestFiles
from stack import Configuration, LabelWrite


@dataclass(frozen=True)
class ToolingLabelling:
    """
    What one pull request's changed files made it, and whether its labels had to move.
    """

    pull_request_number: int
    """
    The pull request read.
    """

    is_a_tooling_change: bool
    """
    What its changed files make it.
    """

    label_was_written: bool
    """
    Whether its labels had to change to say so.

    Reported rather than derived from the verdict, because most passes find the label
    already right and a pass that says it wrote every time says nothing.
    """


def label_tooling_changes(
    fork: ForkPullRequests,
    files: PullRequestFiles,
    configuration: Configuration,
    pull_request_numbers: Collection[int] | None = None,
) -> list[ToolingLabelling]:
    """
    Bring every pull request's tooling label into line with the files it changes.

    :param fork: The fork to read the open pull requests from and write the labels back
        to.
    :param files: The same fork, asked what each pull request changes - a call of its
        own, which is why it is not read off the record already fetched.
    :param configuration: The configuration naming the label and where the tooling lives.
    :param pull_request_numbers: The pull requests to label, or ``None`` for every open
        one.
    :return: One entry per pull request read, in the order the fork answered them.
    """
    labelled: list[ToolingLabelling] = []
    for record in _records(fork, pull_request_numbers):
        number = int(PullRequestField.NUMBER.read(record))
        carried = PullRequestField.LABELS.read(record, number)
        changed = ChangedPaths.of(files.changed_paths(number), configuration)
        write = _label_write(changed.is_a_tooling_change, carried, configuration)
        if write.labels != tuple(carried):
            fork.replace_labels(number, write.labels)
        labelled.append(
            ToolingLabelling(
                pull_request_number=number,
                is_a_tooling_change=changed.is_a_tooling_change,
                label_was_written=write.labels != tuple(carried),
            )
        )
    return labelled


def _records(
    fork: ForkPullRequests, pull_request_numbers: Collection[int] | None
) -> list[PullRequestRecord]:
    """
    Read the pull requests to label, asking for named ones one at a time.

    Named ones are read individually rather than filtered out of the open ones, so a
    hook labelling the pull request that just moved costs a call about that pull request
    rather than a listing of every open one.

    :param fork: The fork to read from.
    :param pull_request_numbers: The pull requests to read, or ``None`` for every open
        one.
    :return: Their records.
    """
    if pull_request_numbers is None:
        return fork.open_pull_requests()
    return [fork.pull_request(number) for number in pull_request_numbers]


def _label_write(
    is_a_tooling_change: bool, carried: Collection[str], configuration: Configuration
) -> LabelWrite:
    """
    :param is_a_tooling_change: What the changed files made the pull request.
    :param carried: The labels it carries now.
    :param configuration: The configuration naming the label.
    :return: The complete label set it must end up with.
    """
    label = [configuration.tooling_label]
    if is_a_tooling_change:
        return LabelWrite.replacing(carried, added=label)
    return LabelWrite.replacing(carried, removed=label)
