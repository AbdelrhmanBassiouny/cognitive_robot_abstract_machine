"""
Errors raised while reading colours.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException

# %% colours


@dataclass(kw_only=True)
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


@dataclass(kw_only=True)
class InvalidColorChannelCount(DataclassException, ValueError):
    """
    A channel sequence cannot describe an RGB or RGBA color.
    """

    channel_count: int
    """
    Number of supplied color channels.
    """

    def error_message(self) -> str:
        return f"A color cannot be constructed from {self.channel_count} channels."

    def suggest_correction(self) -> str:
        return "Supply three RGB channels or four RGBA channels."
