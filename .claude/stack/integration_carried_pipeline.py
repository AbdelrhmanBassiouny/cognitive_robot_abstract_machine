"""
Whether a build carries the rebuild that would produce the next one.

Publishing a build moves this fork's default branch onto it, and a schedule registers
from the default branch - so a build that does not itself carry the rebuild takes the
schedule down with it and leaves nothing able to publish a later build. The pipeline is
answerable for its own continued existence in a way nothing else here is: a red build is
somebody's afternoon, and a published build with no rebuild in it is the end of the
automation with nothing left to restore it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tool_runner import ToolingScript
from workflow_document import (
    REPOSITORY_ROOT,
    TriggerEvent,
    WorkflowDocument,
    WorkflowFile,
)

if TYPE_CHECKING:
    from git_commands import GitCommandRunner

REFRESH_WORKFLOW_PATH = str(
    WorkflowFile.INTEGRATION_REFRESH.path.relative_to(REPOSITORY_ROOT)
)
"""
Where the workflow a schedule starts the rebuild from is filed, as a tree names it.
"""

PIPELINE_PATHS = (
    REFRESH_WORKFLOW_PATH,
    *(str(script.path.relative_to(REPOSITORY_ROOT)) for script in ToolingScript),
)
"""
What a tree has to carry for a rebuild to happen from it again: the workflow a schedule
starts, and the entry points that workflow drives.

Derived from the enums naming them rather than listed a second time, so a script or a
workflow that moves is not still looked for where it used to be - which would refuse
every build over a file nothing is missing.
"""


@dataclass(frozen=True)
class CarriedPipeline:
    """
    What of the rebuild a tree carries, and what it is missing.
    """

    missing: tuple[str, ...]
    """
    The pipeline's own files this tree does not hold.
    """

    starts_on_a_schedule: bool
    """
    Whether the rebuild it holds is one that starts unasked.

    A dispatch somebody remembers to press is not what publishing must not cost, so a
    refresh workflow left with nothing but one counts as no rebuild at all.
    """

    @property
    def can_rebuild(self) -> bool:
        """:return: Whether a rebuild would still happen once this tree is published."""
        return not self.missing and self.starts_on_a_schedule


def pipeline_carried_by(git: GitCommandRunner, reference: str) -> CarriedPipeline:
    """
    Ask a tree what of the rebuild it holds.

    :param git: The runner to read the tree through.
    :param reference: The commit or branch to read.
    :return: What it carries.
    """
    carried = {path: _content(git, reference, path) for path in PIPELINE_PATHS}
    workflow = carried[REFRESH_WORKFLOW_PATH]
    return CarriedPipeline(
        missing=tuple(path for path, content in carried.items() if content is None),
        starts_on_a_schedule=workflow is not None
        and WorkflowDocument.from_text(workflow).answers_to(TriggerEvent.SCHEDULE),
    )


def _content(git: GitCommandRunner, reference: str, path: str) -> str | None:
    """
    :param git: The runner to read through.
    :param reference: The commit or branch to read.
    :param path: The file wanted.
    :return: What that tree holds at that path, or ``None`` when it holds nothing there.
    """
    found = git.attempt("show", f"{reference}:{path}")
    return found.output if found.succeeded else None
