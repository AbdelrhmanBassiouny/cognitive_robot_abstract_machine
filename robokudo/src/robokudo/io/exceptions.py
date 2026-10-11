"""
Errors raised by RoboKudo camera interfaces.
"""

from __future__ import annotations

# %% Imports
from dataclasses import dataclass
from robokudo.exceptions import RoboKudoError
from robokudo.types.image import ImageRotation


# %% Image rotation
@dataclass
class UnsupportedImageRotation(RoboKudoError, ValueError):
    """
    A requested image rotation is outside the supported orientations.
    """

    rotation: str | None
    """
    Unsupported rotation supplied to the camera interface.
    """

    def error_message(self) -> str:
        """
        Identify the unsupported rotation.
        """
        return f"Unsupported image rotation: {self.rotation!r}."

    def suggest_correction(self) -> str:
        """
        List the supported rotation choices.
        """
        choices = ", ".join(rotation.value for rotation in ImageRotation)
        return f"Use one of the supported image rotations: {choices}."
