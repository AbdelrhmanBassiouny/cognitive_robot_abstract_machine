from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type

from typing_extensions import TYPE_CHECKING

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from semantic_digital_twin.adapters.ros.messages import MetaData


@dataclass
class ROS2ConversionError(DataclassException):
    """
    Base class for errors that occur during ROS2 message conversion.
    """


@dataclass
class CannotConvertSemDTToRos2Error(ROS2ConversionError):
    """
    Raised when a semDT object cannot be converted to a ROS2 message.
    """

    data_type: Type = field(kw_only=True)
    """
    The type of the object that could not be converted.
    """

    def error_message(self) -> str:
        return f"Cannot convert {self.data_type.__name__} to ROS2 message."

    def suggest_correction(self) -> str:
        return ""


@dataclass
class CannotConvertRos2ToSemDTError(ROS2ConversionError):
    """
    Raised when a ROS2 message cannot be converted to a semDT object.
    """

    data_type: Type = field(kw_only=True)
    """
    The type of the message that could not be converted.
    """

    def error_message(self) -> str:
        return f"Cannot convert {self.data_type.__name__} to our semDT type."

    def suggest_correction(self) -> str:
        return ""


@dataclass
class LaserScanBeamCountMismatch(ROS2ConversionError):
    """
    Raised when a laser scan holds a different number of measurements than the beams its
    own angles describe.
    """

    beam_count: int = field(kw_only=True)
    """
    How many beams the scan's angles describe.
    """

    range_count: int = field(kw_only=True)
    """
    How many measurements the scan holds.
    """

    def error_message(self) -> str:
        return f"Laser scan describes {self.beam_count} beams but holds {self.range_count} measurements."

    def suggest_correction(self) -> str:
        return "check that the scan's angle_min, angle_max and angle_increment match its ranges."


@dataclass
class WorldUpdatesLostError(DataclassException):
    """
    Raised when a synchronizer is asked how far it caught up with a publisher whose
    updates it did not all receive.

    Only what changed is published, so the world may differ from the publisher's in what
    the lost updates carried for good.
    """

    publisher: MetaData
    """
    The synchronizer whose updates were lost.
    """

    last_received_sequence_number: int
    """
    The position of the update received before the lost ones.
    """

    received_sequence_number: int
    """
    The position of the update received after the lost ones.
    """

    def error_message(self) -> str:
        return (
            f"Updates #{self.last_received_sequence_number + 1} to "
            f"#{self.received_sequence_number - 1} of '{self.publisher.node_name}' were "
            f"lost, so this world may differ from the one of the publisher."
        )

    def suggest_correction(self) -> str:
        return (
            "Fetch the world again, and raise the message queue depth of the "
            "synchronizers if the receiver cannot keep up with the publisher."
        )
