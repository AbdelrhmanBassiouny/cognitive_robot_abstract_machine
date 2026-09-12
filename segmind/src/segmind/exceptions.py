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


# %% events


@dataclass
class EventNamesNoObject(DataclassException):
    """
    Raised when an event whose effect is stated about the object it names, names none.
    """

    event: str
    """
    The event, as it prints.
    """

    def error_message(self) -> str:
        return (
            f"{self.event} is an event whose effect is stated about the object it "
            f"names, but it names none."
        )

    def suggest_correction(self) -> str:
        return "Build the event with the entity its object was seen involved with."


# %% expectations


@dataclass
class NothingSaysWhereItStands(DataclassException):
    """
    Raised when an expectation is asked where its subject is believed to stand and
    nothing expected of it says.
    """

    subject: str
    """
    The thing the expectation is about, as the world names it.
    """

    def error_message(self) -> str:
        return (
            f"Nothing believed of {self.subject} says where it stands, so there is no "
            f"believed place to read."
        )

    def suggest_correction(self) -> str:
        return (
            "Expect a placement of it -- that it lies in a region, or stands near a "
            "place -- or ask what is believed of it instead of where."
        )
