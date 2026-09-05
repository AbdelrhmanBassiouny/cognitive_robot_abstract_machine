"""
One pull request as GitHub's listing endpoint reports it, for the fakes that stand in
for that endpoint.

The readers under test parse GitHub's own JSON, so a test cannot hand them a class of
ours - it has to produce that shape. Declaring the shape once here keeps the field names
and the nesting of the labels out of every fake response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from build_dashboard import PullRequestLabel, PullRequestState
from github_api import LabelField, PullRequestField


@dataclass(frozen=True)
class PullRequestDetail:
    """
    One pull request's live state, in the terms the dashboards classify it by.
    """

    number: int
    """
    The number the pull request is addressed and keyed by.
    """

    state: PullRequestState = PullRequestState.OPEN
    """
    Whether it is still open.
    """

    draft: bool = False
    """
    Whether it is still a draft.
    """

    merged_at: str | None = None
    """
    When it merged, or ``None`` when it did not.
    """

    labels: tuple[PullRequestLabel, ...] = ()
    """
    The labels it carries.
    """

    def to_json(self) -> dict[str, Any]:
        """
        :return: The same state in the shape GitHub's listing endpoint reports it in.
        """
        return {
            PullRequestField.NUMBER.value: self.number,
            PullRequestField.STATE.value: self.state.value,
            PullRequestField.DRAFT.value: self.draft,
            PullRequestField.MERGED_AT.value: self.merged_at,
            PullRequestField.LABELS.value: [
                {LabelField.NAME.value: label.value} for label in self.labels
            ],
        }
