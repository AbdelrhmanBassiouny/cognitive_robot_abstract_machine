"""
The ways Montessori perception can fail.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Tuple

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

    missing_inputs: List[str]
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


@dataclass
class WorkspaceOutOfView(DataclassException):
    """
    Raised when the stretch of table perception looks at falls outside the camera image
    altogether, so there is nothing of it to show.
    """

    image_shape: Tuple[int, ...]
    """
    Height and width of the image the workspace was looked for in.
    """

    def error_message(self) -> str:
        return (
            f"The workspace falls outside the {self.image_shape} image, so the camera "
            "is not looking at it."
        )

    def suggest_correction(self) -> str:
        return (
            "Check where the camera is mounted and which frame its pose is given in, "
            "and that the configured workspace names the table it is pointed at."
        )


@dataclass
class SurfaceHasNothingToMeasure(DataclassException):
    """
    Raised when the world describes a surface with no shape at all, so neither how far
    it reaches nor how high it lies can be read from it.
    """

    surface_name: str
    """
    What the world calls the thing that carries no shape.
    """

    def error_message(self) -> str:
        return (
            f"{self.surface_name} has no shape, so its extent and height cannot be read "
            "from the world."
        )

    def suggest_correction(self) -> str:
        return (
            "Give it collision geometry in the world description, or annotate it with "
            "the supporting surface region it offers."
        )


@dataclass
class BoardMissingFromWorld(DataclassException):
    """
    Raised when the world perception was built against describes no shape-sorting board,
    so the height of the lid its holes lie in is not there to be read.
    """

    def error_message(self) -> str:
        return "The world describes no shape-sorting board."

    def suggest_correction(self) -> str:
        return (
            "Spawn the board into the world the robot publishes, so the height of its "
            "lid is read from the scene rather than assumed."
        )


@dataclass
class CaptureIncomplete(DataclassException):
    """
    Raised when a saved look at the scene is missing one of the files it is written as,
    so it cannot be read back into a frame.
    """

    capture_name: str
    """
    Name of the capture that was asked for.
    """

    directory: str
    """
    Where its files were looked for.
    """

    missing_parts: List[str]
    """
    Suffixes of the files that are not there.
    """

    def error_message(self) -> str:
        return (
            f"The capture {self.capture_name} in {self.directory} is missing "
            f"{', '.join(self.missing_parts)}."
        )

    def suggest_correction(self) -> str:
        return (
            "Write the capture again from the rosbag it was taken out of, with "
            "experiments.montessori.perception.capture_from_bag."
        )


@dataclass
class NothingRecordedOnTopic(DataclassException):
    """
    Raised when a rosbag carries none of a message a capture needs.
    """

    bag_name: str
    """
    The bag that was read.
    """

    topic: str
    """
    The topic that held nothing.
    """

    def error_message(self) -> str:
        return f"{self.bag_name} carries no message on {self.topic}."

    def suggest_correction(self) -> str:
        return (
            "Record the bag again with every camera topic the perception node reads, "
            "or capture from a bag that already has them."
        )


@dataclass
class NothingIsHiddenFromBelow(DataclassException):
    """
    Raised when what a thing hides from a camera is asked for, but the camera does not
    stand above the thing, so there is no surface below it that it stands in front of.
    """

    camera_height: float
    """
    Height the camera stands at, in metres.
    """

    top_height: float
    """
    Height of the top of the thing whose hidden ground was asked for, in metres.
    """

    def error_message(self) -> str:
        return (
            f"A camera at {self.camera_height:.3f}m does not look down on something "
            f"reaching {self.top_height:.3f}m, so it hides nothing below it."
        )

    def suggest_correction(self) -> str:
        return (
            "Check the camera's pose and the frame it is given in: a camera mounted "
            "above the scene reads higher than everything standing in it."
        )


@dataclass
class RegionsDoNotMeet(DataclassException):
    """
    Raised when the stretch two patches of a plane have in common is asked for, and they
    have none.
    """

    bounds: Tuple[float, float, float, float]
    """
    The first patch's bounds, as ``(minimum_x, maximum_x, minimum_y, maximum_y)`` in
    metres.
    """

    other_bounds: Tuple[float, float, float, float]
    """
    The second patch's bounds, in the same order.
    """

    def error_message(self) -> str:
        return (
            f"A patch spanning x {self.bounds[0]:.3f}..{self.bounds[1]:.3f}, "
            f"y {self.bounds[2]:.3f}..{self.bounds[3]:.3f} shares no ground with one "
            f"spanning x {self.other_bounds[0]:.3f}..{self.other_bounds[1]:.3f}, "
            f"y {self.other_bounds[2]:.3f}..{self.other_bounds[3]:.3f}."
        )

    def suggest_correction(self) -> str:
        return (
            "Ask whether the two meet before asking what they have in common: a look "
            "narrowed past the surface it searches has nothing left to rectify."
        )


@dataclass
class LookHasNoReferenceFrame(DataclassException):
    """
    Raised when a statement says where the thing sought lies, but the look reports its
    detections in no frame, so what the relation allows cannot be read in metres.
    """

    relation_name: str
    """
    The relation the statement stated, by the name of the class that means it.
    """

    def error_message(self) -> str:
        return (
            f"A look reporting detections in no frame cannot say where "
            f"{self.relation_name} allows a thing to be."
        )

    def suggest_correction(self) -> str:
        return (
            "Give the source the frame its detections are placed in, which for a "
            "pipeline read out of a world is that world's own root."
        )
