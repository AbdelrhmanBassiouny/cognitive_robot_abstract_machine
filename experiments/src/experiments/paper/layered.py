"""
A card's levels drawn one above another as a single picture.

Figures floating separately on a page are read in whatever order the layout puts them;
the point of this card is that its levels are read *straight down* -- the event over the
item of the plan that was running when it happened, over what the camera saw, over where
the object went. That only holds if they are one picture.

The levels are already pictures by the time they get here, so this composes what the
panels wrote rather than drawing anything itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from typing_extensions import List, Optional, Sequence

from experiments.paper.lettering import Face, Lettering, drawn
from semantic_digital_twin.world_description.geometry import Color

# %% how a stacked figure is laid out

FIGURE_WIDTH = 1600
"""
How wide the whole figure is drawn, in pixels.

Every level is scaled to this, since levels drawn at whatever width they happened to be
rendered at would not line up under one another.
"""

MAXIMUM_LEVEL_HEIGHT = 720
"""
How tall one level may be drawn, in pixels.

A rendered scene is far taller for its width than a chart of a few rows, and stretched
to the figure's width it would push every other level off the page. A level that would
exceed this is fitted to it and centred instead.
"""

TITLE_HEIGHT = 56
"""
How tall the band the figure's title is written in, in pixels.
"""

LABEL_HEIGHT = 30
"""
How tall the band a level's name is written in, in pixels.
"""

MISSING_HEIGHT = 60
"""
How tall a level the run left nothing to draw is, in pixels.

Enough to say what is missing and why, without taking the room a drawn level would.
"""

LAYER_GAP = 4
"""
How many pixels of background are left between one level and the next.
"""

FIGURE_BACKGROUND = Color(1.0, 1.0, 1.0, 1.0)
"""
What the figure is drawn on, behind and between the levels.
"""

TITLE_BACKGROUND = Color(0.13, 0.15, 0.19, 1.0)
"""
What the title band is, dark so the title reads as the head of the figure.
"""

SUBTITLE_HEIGHT = 34
"""
How tall the band under the title naming the run the figure is drawn from is, in pixels.
"""

LABEL_BACKGROUND = Color(0.93, 0.94, 0.96, 1.0)
"""
What a level's name band is, a shade off the background so each level reads as a section
of the figure.
"""

MISSING_TEXT_COLOR = Color(0.45, 0.45, 0.48, 1.0)
"""
What the line saying a level was not recorded is written in, which is fainter than a
name so that it reads as an absence rather than as content.
"""

# %% one level of the figure


@dataclass(frozen=True)
class Layer:
    """
    One level of a layered figure: what it shows, and the picture of it.
    """

    name: str
    """
    What this level shows, as it is written on the band above it.
    """

    picture: Optional[Path] = None
    """
    Where the picture of this level was left, or None where the run left nothing to draw
    it from.
    """

    note: str = ""
    """
    What is written in a level's place where it has no picture, saying why there is
    none.
    """

    @property
    def was_drawn(self) -> bool:
        """
        Whether this level has a picture to stack.
        """
        return self.picture is not None


# %% the figure they make


@dataclass
class LayeredFigure:
    """
    Draws a card's levels one above another as a single picture, each written over with
    what it shows, under a title saying what the whole figure is about.
    """

    width: int = FIGURE_WIDTH
    """
    How wide the whole figure is drawn, in pixels.
    """

    maximum_level_height: int = MAXIMUM_LEVEL_HEIGHT
    """
    How tall one level may be drawn, in pixels.
    """

    title_height: int = TITLE_HEIGHT
    """
    How tall the band the title is written in, in pixels.
    """

    label_height: int = LABEL_HEIGHT
    """
    How tall the band a level's name is written in, in pixels.
    """

    missing_height: int = MISSING_HEIGHT
    """
    How tall a level with nothing to draw is, in pixels.
    """

    gap: int = LAYER_GAP
    """
    How many pixels of background are left between one level and the next.
    """

    background: Color = FIGURE_BACKGROUND
    """
    What the figure is drawn on.
    """

    title: Lettering = field(
        default_factory=lambda: Lettering(
            size=24, face=Face.BOLD, color=Color(1.0, 1.0, 1.0, 1.0)
        )
    )
    """
    How the title is set.
    """

    subtitle_height: int = SUBTITLE_HEIGHT
    """
    How tall the band naming the run under the title is, in pixels.
    """

    subtitle: Lettering = field(
        default_factory=lambda: Lettering(size=16, color=Color(0.85, 0.87, 0.9, 1.0))
    )
    """
    How the line naming the run is set.
    """

    label: Lettering = field(default_factory=lambda: Lettering(size=16, face=Face.BOLD))
    """
    How a level's name is set.
    """

    missing: Lettering = field(
        default_factory=lambda: Lettering(size=16, color=MISSING_TEXT_COLOR)
    )
    """
    How the line saying a level was not recorded is set.
    """

    def of(
        self, layers: Sequence[Layer], title: str = "", subtitle: str = ""
    ) -> np.ndarray:
        """
        Draw the given levels one above another.

        :param layers: The levels, top first. A level with no picture keeps its place
            and says what is missing, so a reader is never left wondering whether a
            level was left out or never existed.
        :param title: What the whole figure is about, written across its head; nothing
            for a figure without a head.
        :param subtitle: Which run the figure is drawn from, written under the title;
            nothing for a figure without one.
        :return: The figure as red, green and blue in that order, shape ``(height,
            width, 3)`` of ``uint8``.
        """
        stacked: List[np.ndarray] = []
        if title:
            stacked.append(
                self.title.band(title, self.width, self.title_height, TITLE_BACKGROUND)
            )
        if subtitle:
            stacked.append(
                self.subtitle.band(
                    subtitle, self.width, self.subtitle_height, TITLE_BACKGROUND
                )
            )
        for layer in layers:
            if stacked:
                stacked.append(self._blank(self.gap))
            stacked.append(
                self.label.band(
                    layer.name, self.width, self.label_height, LABEL_BACKGROUND
                )
            )
            stacked.append(self._drawn(layer))
        return np.vstack(stacked)

    def write(
        self, layers: Sequence[Layer], path: Path, title: str = "", subtitle: str = ""
    ) -> Path:
        """
        Leave the layered figure at the given path.

        :param layers: The levels, top first.
        :param path: The file it is written to, its directory created if it is not
            there.
        :param title: What the whole figure is about, or nothing.
        :param subtitle: Which run the figure is drawn from, or nothing.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.of(layers, title, subtitle))
        return path

    # %% the pieces one level is made of

    def _drawn(self, layer: Layer) -> np.ndarray:
        """
        The picture of one level, scaled to the figure's width.

        :param layer: The level to draw.
        """
        if not layer.was_drawn:
            return self.missing.band(
                layer.note, self.width, self.missing_height, self.background
            )
        return self._scaled(imageio.imread(layer.picture))

    def _scaled(self, picture: np.ndarray) -> np.ndarray:
        """
        One level's picture as three channels, as large as it can be drawn without being
        taller than a level may be, centred on the figure's own width.

        :param picture: The picture as it was written, which may carry an opacity
            channel or none at all.
        """
        colored = self._three_channels(picture)
        shrunk_by = min(
            self.width / colored.shape[1],
            self.maximum_level_height / colored.shape[0],
        )
        width = max(round(colored.shape[1] * shrunk_by), 1)
        height = max(round(colored.shape[0] * shrunk_by), 1)
        fitted = cv2.resize(
            colored, (width, height), interpolation=cv2.INTER_AREA
        ).astype(np.uint8)
        return self._centred(fitted)

    def _centred(self, picture: np.ndarray) -> np.ndarray:
        """
        One level's picture with background either side of it, so that a level narrower
        than the figure sits in the middle rather than against an edge.

        :param picture: The picture, no wider than the figure.
        """
        if picture.shape[1] == self.width:
            return picture
        strip = self._blank(picture.shape[0])
        left = (self.width - picture.shape[1]) // 2
        strip[:, left : left + picture.shape[1]] = picture
        return strip

    @staticmethod
    def _three_channels(picture: np.ndarray) -> np.ndarray:
        """
        A written picture as red, green and blue, whatever it was written as.

        :param picture: The picture as it was read back.
        """
        if picture.ndim == 2:
            return np.dstack([picture] * 3)
        return picture[:, :, :3]

    def _blank(self, height: int) -> np.ndarray:
        """
        A strip of background nothing is written on.

        :param height: How tall the strip is, in pixels.
        """
        strip = np.zeros((height, self.width, 3), dtype=np.uint8)
        strip[:, :] = drawn(self.background)
        return strip
