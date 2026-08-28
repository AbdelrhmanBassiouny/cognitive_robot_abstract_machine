"""
The ways Montessori perception can fail.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Sequence, Tuple

from krrood.exceptions import DataclassException


@dataclass
class UnsupportedImageEncoding(DataclassException):
    """
    Raised when an image arrives in an encoding this package cannot read.
    """

    encoding: str
    """
    The encoding the image declared.
    """

    supported_encodings: List[str]
    """
    The encodings that would have been read.
    """

    def error_message(self) -> str:
        return f"Cannot read an image encoded as {self.encoding}."

    def suggest_correction(self) -> str:
        return (
            "Republish the image in one of "
            f"{', '.join(self.supported_encodings)}, or extend ImageEncoding."
        )


@dataclass
class UndecodableCompressedImage(DataclassException):
    """
    Raised when a transport-compressed image's payload cannot be read back into pixels.
    """

    image_format: str
    """
    The ``format`` the message declared its payload in.
    """

    payload_size: int
    """
    Number of payload bytes that failed to decode.
    """

    def error_message(self) -> str:
        return (
            f"Could not decode the {self.payload_size} byte payload of an image "
            f"declared as {self.image_format}."
        )

    def suggest_correction(self) -> str:
        return (
            "Check that the topic carries the transport its name promises, since a "
            "payload compressed one way cannot be read as another."
        )


@dataclass
class DepthAndColourNotRegistered(DataclassException):
    """
    Raised when a frame's depth and colour images differ in size, which means they were
    not registered onto one another and a pixel does not name the same ray in both.
    """

    color_shape: Tuple[int, ...]
    """
    Height and width of the colour image.
    """

    depth_shape: Tuple[int, ...]
    """
    Height and width of the depth image.
    """

    def error_message(self) -> str:
        return (
            f"Colour is {self.color_shape} but depth is {self.depth_shape}, so the two "
            "are not registered onto one another."
        )

    def suggest_correction(self) -> str:
        return (
            "Subscribe to the depth stream the driver has aligned to colour, so both "
            "share a resolution and a set of intrinsics."
        )


@dataclass
class NoSceneAvailable(DataclassException):
    """
    Raised when a scene is asked for before any camera data has arrived.
    """

    waited_seconds: float
    """
    How long the caller waited for a frame.
    """

    missing_inputs: Sequence[str]
    """
    The inputs that never arrived.
    """

    def error_message(self) -> str:
        return (
            f"No scene after waiting {self.waited_seconds:.1f}s; still missing "
            f"{', '.join(self.missing_inputs)}."
        )

    def suggest_correction(self) -> str:
        return (
            "Check that the camera and the robot's transform tree are running, and "
            "that the configured topic names match the ones being published."
        )
