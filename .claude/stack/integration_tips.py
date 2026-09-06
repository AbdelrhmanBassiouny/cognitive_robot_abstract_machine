"""
What became of one tip, and who resolved the conflict that let it in.

Every branch a build considered is one :class:`PullRequestStackTipOutcome`,
whose :class:`TipStatus` answers for itself whether it reached the build.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from integration_constants import ReportKey

# %% what became of one tip


@dataclass(frozen=True)
class TipStatusSpecification:
    """What one status is called, and whether the tip it describes is in the build."""

    name: str
    """How the status is written in the report a caller reads."""

    integrated: bool
    """Whether the tip's commits reached the finished branch.

    Answered per status rather than by a set of the statuses that count, so a status
    added later has to say which it is.
    """


class TipStatus(StrEnum):
    """What a build did with one branch it considered.

    Each member's value is its specification, unpacked by ``__new__`` into the
    :class:`str` the report is written with: :class:`~enum.StrEnum` owns member
    creation, so a specification *base* would take that over and stop the member being
    a ``str`` - and a field called ``name`` cannot exist on an enum member at all.
    """

    def __new__(cls, specification: TipStatusSpecification) -> TipStatus:
        """:param specification: What this status is called and whether it is integrated.
        :return: The member, still a ``str`` of its own name."""
        member = str.__new__(cls, specification.name)
        member._value_ = specification.name
        member.specification = specification
        return member

    specification: TipStatusSpecification
    """What this status is called and whether its tip reached the finished branch."""

    MERGED = TipStatusSpecification("merged", integrated=True)
    """It merged cleanly and is in the build."""

    REPLAYED = TipStatusSpecification("replayed", integrated=True)
    """It is in the build, but only because a recorded resolution was replayed - so the
    collision it hides is still there for whoever lands second."""

    SKIPPED = TipStatusSpecification("skipped", integrated=False)
    """It conflicted and was left out, so the rest of the build could go on."""

    INTEGRATION_FAILED = TipStatusSpecification("integration-failed", integrated=False)
    """The merge refused before it began - unrelated histories, a reference that does
    not resolve, something in the way. The build's own environment, not the tip's."""

    UNREVIEWED = TipStatusSpecification("unreviewed", integrated=False)
    """Its author has not reviewed it, or has not reviewed something beneath it, so the
    build never tried to merge it. Left out by the rule working rather than by a build
    going wrong, which is why it is reported apart from the tips a build attempted."""

    BLOCKED = TipStatusSpecification("blocked", integrated=False)
    """It carries a label that withholds it, or stands on something that does, so the
    build never tried to merge it. Carrying it would put a known conflict or a known
    break into the branch this workflow exists to build from."""

    CHECKS_FAILED = TipStatusSpecification("checks-failed", integrated=False)
    """Its own checks failed, or something beneath it failed its own, so the build never
    tried to merge it. Reported apart from :attr:`BLOCKED` because nobody labelled it:
    what lets it back in is its checks going green, not a label coming off."""

    NOT_A_TOOLING_CHANGE = TipStatusSpecification(
        "not-a-tooling-change", integrated=False
    )
    """This build was asked for the tooling and the branch changes something else, or
    stands on one that does. Nothing is wrong with it; it is simply not what was asked
    for."""


# %% who resolved the conflict that let it in


class ResolutionAuthor(StrEnum):
    """Who wrote a conflict resolution that a later build replays."""

    HUMAN = "human"
    """A developer resolved it, which is the risk rerere was always understood to carry."""

    SKILL = "skill"
    """A skill resolved it, so it is replayed unreviewed on every later build and is
    worth being able to find again."""


@dataclass(frozen=True)
class ResolutionProvenance:
    """Which resolutions were written by a machine rather than by a developer.

    rerere matches on a conflict's preimage and replays it automatically, so a
    resolution that is textually applicable but semantically wrong is reapplied
    unreviewed for as long as it stays in the cache. That was accepted when only a
    developer could record one; it is a different proposition once a skill can, so the
    build says which it replayed rather than leaving them indistinguishable.
    """

    authors: dict[str, ResolutionAuthor]
    """The author recorded against each tip whose collision was resolved."""

    def author_for(self, branch: str) -> ResolutionAuthor:
        """Say who wrote the resolution replayed for a tip.

        An unrecorded resolution is a developer's: a skill records every one it writes,
        so reading silence as machine-authored would flag the one case that was never
        the problem.

        :param branch: The tip whose resolution was replayed.
        :return: Its author.
        """
        return self.authors.get(branch, ResolutionAuthor.HUMAN)

    @classmethod
    def read(cls, path: Path) -> ResolutionProvenance:
        """:param path: The manifest to read.
        :return: What it records, or no claims at all when it does not exist yet."""
        if not path.exists():
            return cls({})
        return cls(
            {
                branch: ResolutionAuthor(author)
                for branch, author in json.loads(path.read_text()).items()
            }
        )

    def write(self, path: Path) -> Path:
        """:param path: Where to record what is known.
        :return: The path written."""
        path.write_text(json.dumps(dict(self.authors), indent=2) + "\n")
        return path

    def claiming(self, branch: str, author: ResolutionAuthor) -> ResolutionProvenance:
        """:param branch: The tip whose resolution was just recorded.
        :param author: Who wrote it.
        :return: These claims with that one added, the existing ones left alone."""
        return ResolutionProvenance({**self.authors, branch: author})


# %% the outcome a report carries


@dataclass(frozen=True)
class PullRequestStackTipOutcome:
    """What one build did with one branch, and which other branch explains it.

    Every branch a build considered is one of these, whether it was merged, left out
    after a collision, or never attempted because nobody had reviewed it. One type
    because the question a reader asks is the same in all three cases - what happened,
    and which other branch is it about.
    """

    branch: str
    """The tip's branch."""

    pull_request_number: int
    """The fork pull request that publishes it."""

    status: TipStatus
    """What became of it."""

    attributed_to: str | None = None
    """The other branch this outcome is about, when there is one.

    The branch already in the build it conflicts with, the base when it is simply stale,
    or the draft beneath it when nobody has reviewed that. Named because the pair is
    what is actionable - "this one was left out" answers nothing on its own, and which
    of the two should change is a judgement neither branch's own state settles.
    """

    conflicting_paths: tuple[str, ...] = ()
    """The paths the conflict was on."""

    resolved_by: ResolutionAuthor | None = None
    """Who wrote the resolution that was replayed, when one was."""

    explanation: str = ""
    """What git said, for a refusal that is the build's own to fix."""

    @property
    def is_integrated(self) -> bool:
        """:return: Whether the tip's commits are in the finished branch."""
        return self.status.specification.integrated

    @classmethod
    def from_json(cls, document: dict[str, Any]) -> PullRequestStackTipOutcome:
        """Read one outcome back out of a report's document.

        :param document: The outcome's own object, as :meth:`IntegrationReport.as_json`
            wrote it.
        :return: The outcome it describes.
        """
        resolved_by = document.get(ReportKey.RESOLVED_BY)
        return cls(
            branch=document[ReportKey.BRANCH],
            pull_request_number=document[ReportKey.PULL_REQUEST_NUMBER],
            status=TipStatus(document[ReportKey.STATUS]),
            attributed_to=document.get(ReportKey.ATTRIBUTED_TO),
            conflicting_paths=tuple(document.get(ReportKey.CONFLICTING_PATHS, ())),
            resolved_by=None if resolved_by is None else ResolutionAuthor(resolved_by),
            explanation=document.get(ReportKey.EXPLANATION, ""),
        )
