"""
The video's chapters: each contribution of the paper is stated as a claim when its
chapter starts, large over the first shot, and then kept in a pill in the top left
corner of every frame of the chapter, with a marker of how far along the video is.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from typing_extensions import Sequence, Tuple

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    CLAIM_SIZE,
    DIM,
    LABEL_SIZE,
    MARGIN,
    Anchor,
    Area,
    Ink,
    Rgb,
    Typesetting,
    dimmed,
    filled,
)
from experiments.video.script import Chapter
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased

PILL_HEIGHT = 36
"""
Pixels the pill is tall.
"""

PILL_PADDING = 14
"""
Pixels between the pill's edge and its text.
"""

DOT_PITCH = 16
"""
Pixels from one progress dot to the next.
"""

CLAIM_WIDTH = 1040
"""
Pixels a claim may run across when shown large, before it wraps.
"""

FOOTAGE_BRIGHTNESS = 235
"""
The mean brightness under which a frame is footage, which the claim is read over
shaded rather than faded towards white.
"""

@dataclass(frozen=True)
class ChapterMark:
    """
    The pill and the claim of one chapter, drawn over any frame.
    """

    chapter: Chapter
    """
    The chapter.
    """

    of: int
    """
    How many chapters there are: as many dots as the marker has.
    """

    def pill_drawn(self, frame: Frame) -> Frame:
        """
        The pill in the top left corner: the progress dots and the claim, in white on
        the video's dark.
        """
        lettering = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb)
        dots = self.of * DOT_PITCH
        width = PILL_PADDING * 2 + dots + 10 + lettering.width_of(self.chapter.claim)
        pill = Area(MARGIN, MARGIN, width, PILL_HEIGHT)
        frame = filled(frame, pill, Ink.TEXT.rgb)
        frame = self._dots_drawn(frame, (pill.x + PILL_PADDING, pill.centre[1]))
        return lettering.written(frame, self.chapter.claim, (pill.x + PILL_PADDING + dots + 10, pill.centre[1]), Anchor.LEFT_MIDDLE)

    def claim_drawn(self, frame: Frame, weight: float) -> Frame:
        """
        The claim large over the middle of the frame, the frame under it faded or
        shaded so the claim is what is read.

        :param frame: The frame.
        :param weight: How far the claim has come up, from zero to one.
        """
        if weight <= 0.0:
            return frame
        resolution = Resolution.of(frame)
        on_footage = float(frame.mean()) < FOOTAGE_BRIGHTNESS
        backdrop = self._shaded(frame, DIM) if on_footage else dimmed(frame, DIM)
        lettering = Typesetting(size=CLAIM_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb if on_footage else Ink.TEXT.rgb)
        text = lettering.wrapped(self.chapter.claim, CLAIM_WIDTH)
        written = lettering.written(backdrop, text, (resolution.width / 2, resolution.stage_height / 2), Anchor.CENTRE_MIDDLE)
        return blended(frame, written, weight)

    def _dots_drawn(self, frame: Frame, at: Tuple[float, float]) -> Frame:
        """
        One dot per chapter, the current one filled, the others rings.
        """
        result = frame.copy()
        for number in range(1, self.of + 1):
            centre = (int(at[0] + (number - 0.5) * DOT_PITCH), int(at[1]))
            if number == self.chapter.number:
                cv2.circle(result, centre, 5, Ink.PAPER.rgb, -1, lineType=cv2.LINE_AA)
            else:
                cv2.circle(result, centre, 5, Ink.PAPER.rgb, 1, lineType=cv2.LINE_AA)
        return result

    @staticmethod
    def _shaded(frame: Frame, by: float) -> Frame:
        shaded = frame.astype(np.float32) * (1.0 - by)
        return np.clip(shaded + 0.5, 0, 255).astype(np.uint8)

@dataclass
class InChapter(Scene):
    """
    A scene of a chapter: the chapter's pill stands in its corner throughout, and where
    the scene opens the chapter, the claim is first shown large and then shrinks into
    the pill.
    """

    scene: Scene
    """
    The scene.
    """

    mark: ChapterMark
    """
    The chapter it belongs to.
    """

    opens: bool = False
    """
    Whether this scene opens the chapter, so the claim is shown large first.
    """

    claim_for: float = 2.0
    """
    Seconds the claim is shown large where the scene opens the chapter.
    """

    claim_from: float = 0.0
    """
    Seconds into the scene the claim comes up; before it, nothing of the chapter is
    drawn.
    """

    fade: float = 0.25
    """
    Seconds the claim takes to come up, and to give way to the pill.
    """

    @property
    def duration(self) -> float:
        return self.scene.duration

    @property
    def dissolves_in(self) -> bool:
        return self.scene.dissolves_in

    @property
    def held_for(self) -> float:
        """
        How long the scene is held, where it is one that is held: the storyboard grows
        it to hold its lines through this.

        :raises AttributeError: Where the scene plays for its own time.
        """
        return self.scene.held_for

    @held_for.setter
    def held_for(self, value: float) -> None:
        self.scene.held_for = value

    def claim_at(self, seconds: float) -> float:
        """
        How far the large claim is up at a moment, from zero to one.
        """
        if not self.opens:
            return 0.0
        since = seconds - self.claim_from
        if since < self.claim_for:
            return eased(since / self.fade)
        return 1.0 - eased((since - self.claim_for) / self.fade)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.scene.picture_at(seconds)
        if self.opens and seconds < self.claim_from:
            return frame
        claim = self.claim_at(seconds)
        if claim > 0.0:
            return self.mark.claim_drawn(frame, claim)
        return self.mark.pill_drawn(frame)

def chaptered(scenes: Sequence[Scene], mark: ChapterMark) -> Tuple[InChapter, ...]:
    """
    Scenes wrapped as one chapter, the first opening it.

    :param scenes: The chapter's scenes, in order.
    :param mark: The chapter.
    """
    return tuple(InChapter(scene, mark, opens=number == 0) for number, scene in enumerate(scenes))
