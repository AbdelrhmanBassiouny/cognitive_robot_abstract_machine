"""
A mimic of a demo the viewer steps through, recording what the viewer asked of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List, Tuple

from cramera.live.query_steps import QueryStepControl


@dataclass
class RecordedStepControl(QueryStepControl):
    """
    Records every request the viewer makes of a demo it steps through.
    """

    advances: int = 0
    """
    How often the viewer let the demo carry on.
    """

    modes: List[Tuple[bool, bool]] = field(default_factory=list)
    """
    Every stepping mode the viewer chose, as whether it steps and whether into nested
    queries.
    """

    def advance(self) -> None:
        self.advances += 1

    def set_stepping(self, is_stepping: bool, holds_nested: bool) -> None:
        self.modes.append((is_stepping, holds_nested))
