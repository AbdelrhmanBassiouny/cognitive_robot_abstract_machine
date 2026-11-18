"""
Colours, stored as hue, saturation and value with an independent opacity.
"""

from __future__ import annotations

import re
from colorsys import hsv_to_rgb, rgb_to_hsv
from dataclasses import dataclass

import numpy as np
from typing_extensions import Self, Sequence

from krrood.patterns.classproperty import classproperty
from krrood_image.exceptions import InvalidColorChannelCount, MalformedHexColor

# %% colours


@dataclass(unsafe_hash=True, kw_only=True)
class Color:
    """
    A color stored in HSV with RGB channel access and independent opacity.

    Channel values are normalized from zero to one. The default color is opaque white.
    Equality and hashing compare the stored hue, saturation, value, and opacity.
    """

    hue: float = 0.0
    """
    Position around the hue wheel, from zero inclusive to one exclusive.
    """

    saturation: float = 0.0
    """
    Color saturation from zero to one inclusive.
    """

    value: float = 1.0
    """
    Color value from zero to one inclusive.
    """

    opacity: float = 1.0
    """
    Opacity from zero to one inclusive.
    """

    def set_rgb(self, *, red: float, green: float, blue: float) -> None:
        """
        Replace the color's RGB channels while preserving opacity.
        """
        self.hue, self.saturation, self.value = rgb_to_hsv(
            float(red), float(green), float(blue)
        )

    @property
    def R(self) -> float:
        """
        Red intensity in the RGB representation.
        """
        return self.to_rgb()[0]

    @property
    def G(self) -> float:
        """
        Green intensity in the RGB representation.
        """
        return self.to_rgb()[1]

    @property
    def B(self) -> float:
        """
        Blue intensity in the RGB representation.
        """
        return self.to_rgb()[2]

    @property
    def A(self) -> float:
        """
        Opacity of the color.
        """
        return self.opacity

    def to_rgba(self) -> tuple[float, float, float, float]:
        """
        Return RGB channels followed by opacity.
        """
        return (*self.to_rgb(), self.opacity)

    def to_rgb(self) -> tuple[float, float, float]:
        """
        Return RGB channels converted from the stored HSV coordinates.
        """
        return hsv_to_rgb(self.hue, self.saturation, self.value)

    @classproperty
    def opencv_maximum_channel_value(cls) -> int:
        """
        Largest channel value in an 8-bit OpenCV HSV_FULL image.
        """
        return np.iinfo(np.uint8).max

    @classproperty
    def opencv_hue_channel_count(cls) -> int:
        """
        Number of hue steps in one turn of an 8-bit OpenCV HSV_FULL image.
        """
        return cls.opencv_maximum_channel_value + 1

    @classmethod
    def from_opencv_hue_saturation_value_full(
        cls, *, hue: int, saturation: int, value: int
    ) -> Self:
        """
        Create a color from OpenCV's 8-bit HSV_FULL channels.
        """
        return cls(
            hue=hue / cls.opencv_hue_channel_count,
            saturation=saturation / cls.opencv_maximum_channel_value,
            value=value / cls.opencv_maximum_channel_value,
        )

    def to_opencv_hue_saturation_value_full(self) -> tuple[int, int, int]:
        """
        Return OpenCV's 8-bit HSV_FULL channels, excluding opacity.
        """
        return (
            int(self.hue * self.opencv_hue_channel_count),
            round(self.saturation * self.opencv_maximum_channel_value),
            round(self.value * self.opencv_maximum_channel_value),
        )

    def to_hex(self, *, prefix: str = "#") -> str:
        """
        Return two hexadecimal digits per RGB channel, excluding opacity.
        """
        return prefix + "".join(
            f"{round(channel * 255):02X}" for channel in self.to_rgb()
        )

    def to_rgb_bytes(self) -> bytes:
        """
        :return: The red, green and blue channels as one byte each, the way an 8-bit
            image stores a pixel; the opacity is not part of it.
        """
        return bytes(round(channel * 255) for channel in self.to_rgb())

    @classmethod
    def from_list(cls, *, color: Sequence[float]) -> Self:
        """
        Create a color from three RGB or four RGBA channels.
        """
        if len(color) not in (3, 4):
            raise InvalidColorChannelCount(channel_count=len(color))
        red, green, blue, *opacity = color
        if not opacity:
            return cls.from_rgba(red=red, green=green, blue=blue)
        return cls.from_rgba(red=red, green=green, blue=blue, opacity=opacity[0])

    @classmethod
    def from_rgba(
        cls,
        *,
        red: float = 1.0,
        green: float = 1.0,
        blue: float = 1.0,
        opacity: float = 1.0,
    ) -> Self:
        """
        Create a color from normalized RGB channels and independent opacity.
        """
        color = cls(opacity=float(opacity))
        color.set_rgb(red=red, green=green, blue=blue)
        return color

    @classmethod
    def from_hex(
        cls,
        *,
        hex_color: str,
        prefix: str = "#",
        pattern: str = "(?:[0-9a-fA-F]{2}){3,4}",
    ) -> Self:
        """
        Read RGB or RGBA hexadecimal pairs, with an optional prefix.

        :raises MalformedHexColor: If the supplied text is not hexadecimal color data.
        """
        digits = hex_color.removeprefix(prefix)
        if re.fullmatch(pattern, digits) is None:
            raise MalformedHexColor(hex_color=hex_color)
        return cls.from_list(
            color=[
                int(digits[index : index + 2], 16) / 255
                for index in range(0, len(digits), 2)
            ]
        )

    @classmethod
    def PINK(cls) -> Self:
        """
        Create an opaque pink color.
        """
        return cls.from_rgba(red=1, green=0, blue=1, opacity=1)

    @classmethod
    def BLACK(cls) -> Self:
        """
        Create an opaque black color.
        """
        return cls.from_rgba(red=0, green=0, blue=0, opacity=1)

    @classmethod
    def WHITE(cls) -> Self:
        """
        Create an opaque white color.
        """
        return cls.from_rgba(red=1, green=1, blue=1, opacity=1)

    @classmethod
    def RED(cls) -> Self:
        """
        Create an opaque red color.
        """
        return cls.from_rgba(red=1, green=0, blue=0, opacity=1)

    @classmethod
    def GREEN(cls) -> Self:
        """
        Create an opaque green color.
        """
        return cls.from_rgba(red=0, green=1, blue=0, opacity=1)

    @classmethod
    def BLUE(cls) -> Self:
        """
        Create an opaque blue color.
        """
        return cls.from_rgba(red=0, green=0, blue=1, opacity=1)

    @classmethod
    def YELLOW(cls) -> Self:
        """
        Create an opaque yellow color.
        """
        return cls.from_rgba(red=1, green=1, blue=0, opacity=1)

    @classmethod
    def CYAN(cls) -> Self:
        """
        Create an opaque cyan color.
        """
        return cls.from_rgba(red=0, green=1, blue=1, opacity=1)

    @classmethod
    def MAGENTA(cls) -> Self:
        """
        Create an opaque magenta color.
        """
        return cls.from_rgba(red=1, green=0, blue=1, opacity=1)

    @classmethod
    def GREY(cls) -> Self:
        """
        Create an opaque middle gray color.
        """
        return cls.from_rgba(red=0.5, green=0.5, blue=0.5, opacity=1)

    @classmethod
    def GRAY(cls) -> Self:
        """
        Create an opaque gray color.
        """
        return cls.from_rgba(red=0.498, green=0.498, blue=0.498, opacity=1)

    @classmethod
    def BEIGE(cls) -> Self:
        """
        Create an opaque beige color.
        """
        return cls.from_rgba(red=1, green=0.827, blue=0.6078, opacity=1)

    @classmethod
    def ORANGE(cls) -> Self:
        """
        Create an opaque orange color.
        """
        return cls.from_rgba(red=1, green=0.647, blue=0, opacity=1)
