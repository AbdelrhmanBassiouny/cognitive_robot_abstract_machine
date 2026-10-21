from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException

# %% colours


@dataclass
class MalformedHexColor(DataclassException):
    """
    Raised when a string meant to name a color is not written as hex digits.
    """

    hex_color: str
    """
    The string that was read as a color.
    """

    def error_message(self) -> str:
        return f"'{self.hex_color}' does not name a color."

    def suggest_correction(self) -> str:
        return (
            "write the color as two hex digits per channel, red first, optionally "
            "preceded by a '#' and followed by a fourth pair for the opacity, for "
            "example '#4080C0' or '#4080C020'."
        )


@dataclass
class WrongNumberOfColorChannels(DataclassException):
    """
    Raised when a list meant to give a color has neither three nor four channels.
    """

    channels: list[float]
    """
    The values that were read as a color.
    """

    def error_message(self) -> str:
        return f"{self.channels} has {len(self.channels)} channels, not 3 or 4."

    def suggest_correction(self) -> str:
        return "give red, green and blue, optionally followed by the opacity."
