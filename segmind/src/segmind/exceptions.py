"""
Exceptions raised by segmind.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from krrood.exceptions import DataclassException
from typing_extensions import List

# %% recordings


@dataclass
class RecordingHoldsNothingToReplay(DataclassException):
    """
    Raised when a recording carries none of the topics a player can move a world by.
    """

    recording: Path
    """
    The recording that was opened.
    """

    replayable_topics: List[str]
    """
    The topics a player would have read.
    """

    def error_message(self) -> str:
        return (
            f"The recording {self.recording} carries none of the topics that can be "
            f"replayed into a world: {', '.join(self.replayable_topics)}."
        )

    def suggest_correction(self) -> str:
        return (
            "Record the robot's transform tree and joint states alongside the camera."
        )


@dataclass
class ReferenceFrameNotRecorded(DataclassException):
    """
    Raised when the frame poses are to be expressed in appears nowhere in a recording's
    transform tree.
    """

    reference_frame: str
    """
    The frame that was asked for.
    """

    recording: Path
    """
    The recording whose transform tree was read.
    """

    def error_message(self) -> str:
        return (
            f"The recording {self.recording} never publishes a transform to or from "
            f"the frame {self.reference_frame!r}, so no pose can be expressed in it."
        )

    def suggest_correction(self) -> str:
        return "Name the frame the recording roots its transform tree in as the reference frame."
