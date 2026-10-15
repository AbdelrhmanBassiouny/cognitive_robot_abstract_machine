"""
The sections of ``CLAUDE.local.md`` a session edits, each between a pair of markers.
"""

from __future__ import annotations

import re
from enum import StrEnum


class NotesMarker(StrEnum):
    """
    The name of one marked section: ``<!-- BEGIN-<name> -->`` opens it, optionally
    labelled as ``<!-- BEGIN-<name>: <label> -->``, and ``<!-- END-<name> -->`` closes
    it.
    """

    PERSONAL_NOTES = "PERSONAL-NOTES"
    """
    The contributor's own notes.
    """

    PR_PROGRESS = "PR-PROGRESS"
    """
    The current branch's pull request progress notes.
    """

    PLAN_MANIFEST = "PLAN-MANIFEST"
    """
    A plan's manifest, labelled with its plan.
    """

    PLAN_ROADMAP = "PLAN-ROADMAP"
    """
    A plan's roadmap, labelled with its plan.
    """

    def section_in(self, text: str) -> str | None:
        """
        :param text: A ``CLAUDE.local.md``.
        :return: The lines of the first section with this name, each ending in a newline,
            or ``None`` when *text* has no such section.
        """
        begin = re.compile(rf"<!-- BEGIN-{re.escape(self)}(: .*)? -->")
        end = f"<!-- END-{self} -->"
        lines = text.splitlines()
        start = next(
            (number for number, line in enumerate(lines) if begin.fullmatch(line)), None
        )
        if start is None:
            return None
        section = []
        for line in lines[start + 1 :]:
            if line == end:
                break
            section.append(f"{line}\n")
        return "".join(section)
