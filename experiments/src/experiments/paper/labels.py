"""
Naming things in a picture: each name written a little above the thing it names, in a
colour nothing in a scene is drawn in, moved up out of the way of every name written
below it, and joined to the thing by a line so it still reads as that thing's.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.paper.lettering import drawn
from semantic_digital_twin.world_description.geometry import Color

# %% how a name is written

LABEL_COLOR = Color(0.0, 0.25, 1.0, 1.0)
"""
What a name is written in: a blue nothing on the table is drawn in, so it is not taken
for a piece, the board or the robot.
"""

LABEL_HALO = Color(1.0, 1.0, 1.0, 1.0)
"""
What is drawn around the letters, so they read against the dark of the robot as well as
against the white of the table.
"""

LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
"""
The face a name is written in.
"""

LIFTED_ABOVE = 0.03
"""
How far above the top of a thing its name is anchored, in metres, so the name is not
written across the thing itself.
"""

LABELS_APART = 4
"""
The least gap left between two names, in pixels.
"""

Pixel = Tuple[float, float]
"""
A place in a picture, as ``(x, y)`` from its top left corner.
"""

# %% one name and where it goes


@dataclass(frozen=True)
class Label:
    """
    One name to write in a picture, and where the thing it names is.
    """

    text: str
    """
    The name.
    """

    anchor: Pixel
    """
    Where the name is meant to be written: the point a little above the thing.
    """

    thing: Pixel
    """
    Where the thing itself is, which the name is joined to by a line.
    """


@dataclass(frozen=True)
class PlacedLabel:
    """
    A name with the place it ended up written at, once moved clear of the others.
    """

    label: Label
    """
    The name and what it names.
    """

    left: int
    """
    Where the letters start, in pixels from the left of the picture.
    """

    baseline: int
    """
    The line the letters stand on, in pixels from the top of the picture.
    """

    width: int
    """
    How wide the letters are, in pixels.
    """

    height: int
    """
    How tall the letters are above the baseline, in pixels.
    """

    descent: int
    """
    How far the letters reach below the baseline, in pixels.
    """

    @property
    def top(self) -> int:
        """
        Where the letters reach up to, in pixels from the top of the picture.
        """
        return self.baseline - self.height

    @property
    def bottom(self) -> int:
        """
        Where the letters reach down to, in pixels from the top of the picture.
        """
        return self.baseline + self.descent

    @property
    def right(self) -> int:
        """
        Where the letters end, in pixels from the left of the picture.
        """
        return self.left + self.width

    @property
    def foot(self) -> Tuple[int, int]:
        """
        The middle of the letters' lower edge, where the line to the thing starts.
        """
        return (self.left + self.width // 2, self.bottom)

    def overlaps(self, other: PlacedLabel) -> bool:
        """
        Whether this name and another are written closer than :data:`LABELS_APART`.

        :param other: The other name.
        """
        return (
            self.left < other.right + LABELS_APART
            and other.left < self.right + LABELS_APART
            and self.top < other.bottom + LABELS_APART
            and other.top < self.bottom + LABELS_APART
        )


# %% writing the names


@dataclass(frozen=True)
class Labelling:
    """
    How names are written on a picture: their size, their colours, and the laying out
    that keeps them apart.
    """

    height: float = 0.6
    """
    Size a name is written at, as OpenCV's own multiple of its base font.
    """

    line_width: int = 2
    """
    Thickness of the letters, in pixels.
    """

    color: Color = LABEL_COLOR
    """
    What the letters are written in.
    """

    halo: Color = LABEL_HALO
    """
    What is drawn around the letters.
    """

    leader_width: int = 1
    """
    Thickness of the line from a name to its thing, in pixels.
    """

    def write_on(
        self, picture: np.ndarray, labels: Sequence[Label]
    ) -> List[PlacedLabel]:
        """
        Write the names on the picture, each clear of the others and joined to its thing
        by a line.

        :param picture: The picture to write on, changed in place.
        :param labels: The names and where their things are.
        :return: Where each name was written.
        """
        placed = self.lay_out(labels, width=picture.shape[1], height=picture.shape[0])
        for one in placed:
            cv2.line(
                picture,
                tuple(round(coordinate) for coordinate in one.label.thing),
                one.foot,
                drawn(self.color),
                self.leader_width,
                cv2.LINE_8,
            )
        for one in placed:
            picture[self._halo_of(one, picture.shape[:2])] = drawn(self.halo)
            self._write(picture, one, drawn(self.color))
        return placed

    def _halo_of(self, one: PlacedLabel, shape: Tuple[int, ...]) -> np.ndarray:
        """
        Which pixels the halo around a name covers: the letters, widened by their own
        thickness on every side.

        :param one: The name and where it is written.
        :param shape: The picture's height and width, in pixels.
        """
        letters = np.zeros(shape, dtype=np.uint8)
        self._write(letters, one, 255)
        widened_by = 2 * self.line_width + 1
        return (
            cv2.dilate(letters, np.ones((widened_by, widened_by), dtype=np.uint8)) > 0
        )

    def _write(self, picture: np.ndarray, one: PlacedLabel, color) -> None:
        """
        Write one name on the picture where it was placed.

        :param picture: The picture to write on, changed in place.
        :param one: The name and where it is written.
        :param color: The channel values to write it in.
        """
        cv2.putText(
            picture,
            one.label.text,
            (one.left, one.baseline),
            LABEL_FONT,
            self.height,
            color,
            self.line_width,
            cv2.LINE_AA,
        )

    def lay_out(
        self, labels: Sequence[Label], width: int, height: int
    ) -> List[PlacedLabel]:
        """
        Where each name goes: centred over its anchor and kept inside the picture, then
        moved up until it is clear of every name placed below it.

        Names are placed from the bottom of the picture up, so a name only ever moves
        away from the things below it and never onto one.

        :param labels: The names and where their things are.
        :param width: How wide the picture is, in pixels.
        :param height: How tall it is, in pixels.
        """
        placed: List[PlacedLabel] = []
        for label in sorted(labels, key=lambda one: -one.anchor[1]):
            one = self._over_the_anchor(label, width, height)
            blocking = self._blocking(one, placed)
            while blocking is not None:
                one = replace(one, baseline=blocking.top - LABELS_APART - one.descent)
                blocking = self._blocking(one, placed)
            placed.append(one)
        return placed

    def _over_the_anchor(self, label: Label, width: int, height: int) -> PlacedLabel:
        """
        The name centred over its anchor, moved just far enough to lie inside the
        picture.

        :param label: The name and where it goes.
        :param width: How wide the picture is, in pixels.
        :param height: How tall it is, in pixels.
        """
        (text_width, text_height), descent = cv2.getTextSize(
            label.text, LABEL_FONT, self.height, self.line_width
        )
        left = int(
            np.clip(round(label.anchor[0] - text_width / 2), 0, width - text_width)
        )
        baseline = int(np.clip(round(label.anchor[1]), text_height, height - descent))
        return PlacedLabel(
            label=label,
            left=left,
            baseline=baseline,
            width=text_width,
            height=text_height,
            descent=descent,
        )

    @staticmethod
    def _blocking(
        one: PlacedLabel, placed: Sequence[PlacedLabel]
    ) -> Optional[PlacedLabel]:
        """
        The lowest name already placed that the given one is written over, or None when
        it is clear of them all.

        :param one: The name being placed.
        :param placed: The names placed so far.
        """
        blocking = [other for other in placed if one.overlaps(other)]
        if not blocking:
            return None
        return max(blocking, key=lambda other: other.top)
