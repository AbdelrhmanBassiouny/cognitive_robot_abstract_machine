from __future__ import annotations

import re
from dataclasses import dataclass

from typing_extensions import Self

from krrimage.exceptions import MalformedHexColor, WrongNumberOfColorChannels

# %% a colour


@dataclass
class Color:
    """
    Dataclass for storing rgba_color as an RGBA value.

    The values are stored as floats between 0 and 1. The default rgba_color is white.
    """

    R: float = 1.0
    """
    Red value of the color.
    """

    G: float = 1.0
    """
    Green value of the color.
    """

    B: float = 1.0
    """
    Blue value of the color.
    """

    A: float = 1.0
    """
    Opacity of the color.
    """

    def __post_init__(self) -> None:
        """
        Make sure the color values are floats, because ros2 sucks.
        """
        self.R = float(self.R)
        self.G = float(self.G)
        self.B = float(self.B)
        self.A = float(self.A)

    def __hash__(self) -> int:
        return hash((self.R, self.G, self.B, self.A))

    def to_rgba(self) -> tuple[float, float, float, float]:
        """
        :return: The red, green, blue and opacity channels.
        """
        return (self.R, self.G, self.B, self.A)

    def to_rgb(self) -> tuple[float, float, float]:
        """
        :return: The red, green and blue channels.
        """
        return (self.R, self.G, self.B)

    def to_hex(self, prefix: str = "#") -> str:
        """
        :param prefix: The characters the digits are written behind.
        :return: The color written as ``#RRGGBB``, two hex digits per channel.

        ..note:: The opacity is not part of it, the same way it is not part of
            :meth:`to_rgb`.
        """
        return prefix + self.to_rgb_bytes().hex().upper()

    def to_rgb_bytes(self) -> bytes:
        """
        :return: The red, green and blue channels as one byte each, the way an 8-bit
            image stores a pixel.

        ..note:: The opacity is not part of it, the same way it is not part of
            :meth:`to_rgb`.
        """
        return bytes(round(channel * 255) for channel in self.to_rgb())

    @classmethod
    def from_list(cls, color: list[float]) -> Self:
        """
        :param color: The red, green and blue channels, optionally followed by the
            opacity.
        :raises WrongNumberOfColorChannels: If it has neither three nor four channels.
        :return: The color of those channels.
        """
        if len(color) == 3:
            return cls.from_rgb(color)
        if len(color) == 4:
            return cls.from_rgba(color)
        raise WrongNumberOfColorChannels(color)

    @classmethod
    def from_rgb(cls, rgb: list[float]) -> Self:
        """
        :param rgb: The red, green and blue channels.
        :return: The fully opaque color of those channels.
        """
        return cls(*rgb, 1)

    @classmethod
    def from_rgba(cls, rgba: list[float]) -> Self:
        """
        :param rgba: The red, green, blue and opacity channels.
        :return: The color of those channels.
        """
        return cls(*rgba)

    @classmethod
    def from_hex(
        cls,
        hex_color: str,
        prefix: str = "#",
        pattern: str = "(?:[0-9a-fA-F]{2}){3,4}",
    ) -> Self:
        """
        Read a color written as two hex digits per channel, red first.

        A fourth pair of digits sets the opacity; without it the color is fully opaque.

        :param hex_color: The color, optionally preceded by a ``#`` and written in
            either case.
        :param prefix: The characters the digits may be written behind.
        :param pattern: What the digits have to look like, by default three or four
            channels of two hex digits each.
        :raises MalformedHexColor: If the string is not written that way.
        :return: The color it names.
        """
        digits = hex_color.removeprefix(prefix)
        if re.fullmatch(pattern, digits) is None:
            raise MalformedHexColor(hex_color)
        return cls.from_list(
            [
                int(digits[index : index + 2], 16) / 255
                for index in range(0, len(digits), 2)
            ]
        )

    @classmethod
    def PINK(cls) -> Self:
        return cls(1, 0, 1, 1)

    @classmethod
    def BLACK(cls) -> Self:
        return cls(0, 0, 0, 1)

    @classmethod
    def WHITE(cls) -> Self:
        return cls(1, 1, 1, 1)

    @classmethod
    def RED(cls) -> Self:
        return cls(1, 0, 0, 1)

    @classmethod
    def GREEN(cls) -> Self:
        return cls(0, 1, 0, 1)

    @classmethod
    def BLUE(cls) -> Self:
        return cls(0, 0, 1, 1)

    @classmethod
    def YELLOW(cls) -> Self:
        return cls(1, 1, 0, 1)

    @classmethod
    def CYAN(cls) -> Self:
        return cls(0, 1, 1, 1)

    @classmethod
    def MAGENTA(cls) -> Self:
        return cls(1, 0, 1, 1)

    @classmethod
    def GREY(cls) -> Self:
        return cls(0.5, 0.5, 0.5, 1)

    @classmethod
    def GRAY(cls) -> Self:
        return cls(0.498, 0.498, 0.498, 1)

    @classmethod
    def BEIGE(cls) -> Self:
        return cls(1, 0.827, 0.6078, 1)

    @classmethod
    def ORANGE(cls) -> Self:
        return cls(1, 0.647, 0, 1)
