"""
Drawing on a frame: where things go, what they are written in, and the few colours
every scene shares, so the scenes of a video look like one piece.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from enum import Enum

import cv2
import numpy as np
from PIL import Image, ImageDraw
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.video.lettering import Face, Typeface
from experiments.video.timeline import Frame, Resolution

Rgb = Tuple[int, int, int]
"""
A colour as red, green and blue bytes.
"""

VIDEO_RESOLUTION = Resolution(width=1280, height=720)
"""
The size a video is drawn at unless a scene is told otherwise: 720 rows, sharp enough to
read the smallest letters and small enough to encode minutes of video in a few
megabytes.
"""

CLAIM_SIZE = 40
"""
The letters of a title or a claim, in pixels of the video's own size: the largest of
the video's three sizes.
"""

BODY_SIZE = 28
"""
The letters of captions, body text and table cells.
"""

LABEL_SIZE = 20
"""
The letters of labels: the smallest size the video writes in.
"""

MARGIN = 32
"""
The margin every frame keeps all round, in pixels.
"""

DIM = 0.7
"""
How far what is not being looked at is faded towards white: everything else is dimmed
rather than anything outlined.
"""

# %% the colours


@dataclass(frozen=True)
class SyntaxInks:
    """
    What the kinds of piece of a line of code are written in, as an editor colours
    them; names and punctuation take the theme's text and muted colours.
    """

    call: Rgb
    """
    A name being called.
    """

    class_name: Rgb
    """
    A capitalised name: a class.
    """

    string: Rgb
    """
    A quoted string.
    """

    number: Rgb
    """
    A number.
    """


@dataclass(frozen=True)
class VideoTheme:
    """
    The colours and fonts every scene of a video draws in, so its scenes look like one
    piece; the hues a video gives its own subjects are its own to choose, as
    :data:`Rgb` values.
    """

    page: Rgb
    """
    What a slide is drawn on.
    """

    text: Rgb
    """
    What text is written in on the page.
    """

    muted: Rgb
    """
    What secondary text is written in.
    """

    hairline: Rgb
    """
    What rules and frames are drawn in.
    """

    panel: Rgb
    """
    What a panel standing off the page is filled with.
    """

    marker: Rgb
    """
    What a highlighter leaves behind a stretch of code that a reader is pointed to.
    """

    accent: Rgb
    """
    The one colour that marks what to look at, and how far the video has played.
    """

    syntax: SyntaxInks
    """
    What code is coloured in.
    """

    typeface: Typeface = Typeface()
    """
    The fonts text is set in.
    """

    def page_of(self, resolution: Resolution) -> Frame:
        """
        :param resolution: The size of the frame.
        :return: An empty page of that size.
        """
        return np.full(resolution.shape, self.page, dtype=np.uint8)

    def typesetting(self, size: int, face: Face = Face.REGULAR) -> Typesetting:
        """
        :param size: The height of the letters, in pixels.
        :param face: The face they are set in.
        :return: Text of that size and face, set in this theme's text colour and fonts.
        """
        return Typesetting(
            size=size, face=face, color=self.text, typeface=self.typeface
        )

    @property
    def code_inks(self) -> dict[Token, Rgb]:
        """
        What each kind of piece of a line of code is written in.
        """
        return {
            Token.CALL: self.syntax.call,
            Token.CLASS: self.syntax.class_name,
            Token.STRING: self.syntax.string,
            Token.NUMBER: self.syntax.number,
            Token.NAME: self.text,
            Token.PUNCTUATION: self.muted,
        }


NEUTRAL_THEME = VideoTheme(
    page=(0xFF, 0xFF, 0xFF),
    text=(0x1F, 0x23, 0x28),
    muted=(0x6B, 0x72, 0x80),
    hairline=(0xCF, 0xD4, 0xDC),
    panel=(0xF6, 0xF7, 0xF9),
    marker=(0xFF, 0xEE, 0x8C),
    accent=(0xC8, 0x5A, 0x19),
    syntax=SyntaxInks(
        call=(0x1D, 0x4E, 0xD8),
        class_name=(0x6D, 0x28, 0xD9),
        string=(0x15, 0x80, 0x3D),
        number=(0xB4, 0x53, 0x09),
    ),
)
"""
Dark text on a white page, in greys, with an orange accent: the default.
"""

DARK_THEME = VideoTheme(
    page=(0x0D, 0x11, 0x17),
    text=(0xE6, 0xED, 0xF3),
    muted=(0x8B, 0x94, 0x9E),
    hairline=(0x6E, 0x76, 0x81),
    panel=(0x16, 0x1B, 0x22),
    marker=(0x4D, 0x3F, 0x12),
    accent=(0xF0, 0x88, 0x3E),
    syntax=SyntaxInks(
        call=(0x5B, 0x8D, 0xEF),
        class_name=(0xBC, 0x8C, 0xFF),
        string=(0x3F, 0xB9, 0x7A),
        number=(0xE3, 0xB3, 0x41),
    ),
)
"""
Light text on a near-black page with an orange accent, the look of an explainer video.
"""

FOOTAGE_TEXT: Rgb = (0xFF, 0xFF, 0xFF)
"""
What text is written in over footage, whatever the theme: white, on footage darkened
under it.
"""

FOOTAGE_BADGE: Rgb = (0x1F, 0x23, 0x28)
"""
What a badge over footage is filled with, whatever the theme.
"""


# %% where things go


@dataclass(frozen=True)
class Area:
    """
    A stretch of a frame, in pixels from its top left corner.
    """

    x: float
    """
    Its left edge.
    """

    y: float
    """
    Its top edge.
    """

    width: float
    """
    How wide it is.
    """

    height: float
    """
    How tall it is.
    """

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def centre(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def aspect(self) -> float:
        """
        Width over height.
        """
        return self.width / self.height

    def towards(self, other: Area, progress: float) -> Area:
        """
        The rectangle part of the way from this one to another.

        :param other: Where it ends up.
        :param progress: How far along, from zero to one.
        """
        return Area(
            x=self.x + (other.x - self.x) * progress,
            y=self.y + (other.y - self.y) * progress,
            width=self.width + (other.width - self.width) * progress,
            height=self.height + (other.height - self.height) * progress,
        )

    def inset(self, by: float) -> Area:
        """
        :param by: How far in from every edge, in pixels.
        :return: The rectangle shrunk by that much all round.
        """
        return Area(self.x + by, self.y + by, self.width - 2 * by, self.height - 2 * by)

    def fitting(self, aspect: float) -> Area:
        """
        The largest rectangle of the given aspect centred in this one.

        :param aspect: Width over height.
        """
        if self.aspect > aspect:
            height = self.height
            width = height * aspect
        else:
            width = self.width
            height = width / aspect
        return Area(
            self.x + (self.width - width) / 2,
            self.y + (self.height - height) / 2,
            width,
            height,
        )

    def rounded(self) -> Tuple[int, int, int, int]:
        """
        Left, top, width and height as whole pixels.
        """
        left, top = int(round(self.x)), int(round(self.y))
        return left, top, int(round(self.right)) - left, int(round(self.bottom)) - top

    @classmethod
    def whole(cls, resolution: Resolution) -> Area:
        """
        :return: The rectangle covering a frame of the given size.
        """
        return cls(0, 0, resolution.width, resolution.height)


# %% pasting


def pasted(frame: Frame, picture: Frame, into: Area) -> Frame:
    """
    A copy of the frame with a picture resized into a rectangle of it, cropped to the
    frame where the rectangle leaves it.

    :param frame: The frame drawn on.
    :param picture: What to paste.
    :param into: Where, and how big.
    """
    result = frame.copy()
    left, top, width, height = into.rounded()
    if width <= 0 or height <= 0:
        return result
    resized = cv2.resize(picture, (width, height), interpolation=cv2.INTER_AREA)
    frame_height, frame_width = frame.shape[:2]
    x0, y0 = max(left, 0), max(top, 0)
    x1, y1 = min(left + width, frame_width), min(top + height, frame_height)
    if x1 <= x0 or y1 <= y0:
        return result
    result[y0:y1, x0:x1] = resized[y0 - top : y1 - top, x0 - left : x1 - left]
    return result


def fitted(frame: Frame, picture: Frame, into: Area) -> Frame:
    """
    A copy of the frame with a picture pasted as large as it goes into a rectangle
    without distorting it, centred there.

    :param frame: The frame drawn on.
    :param picture: What to paste.
    :param into: The room it may take.
    """
    return pasted(frame, picture, into.fitting(picture.shape[1] / picture.shape[0]))


def dimmed(frame: Frame, by: float) -> Frame:
    """
    A copy of the frame faded towards white.

    :param frame: The frame.
    :param by: How far towards white, from zero to one.
    """
    faded = frame.astype(np.float32) * (1.0 - by) + 255.0 * by
    return np.clip(faded + 0.5, 0, 255).astype(np.uint8)


def darkened(frame: Frame, over: Area, by: float) -> Frame:
    """
    A copy of the frame with a rectangle of it shaded towards black, fading in from its
    top edge to its full darkness a third of the way down: a band a caption is read on
    over footage.

    :param frame: The frame.
    :param over: The band.
    :param by: How dark the band is at the bottom, from zero to one.
    """
    result = frame.copy()
    left, top, width, height = over.rounded()
    frame_height, frame_width = frame.shape[:2]
    top, bottom = max(top, 0), min(top + height, frame_height)
    left, right = max(left, 0), min(left + width, frame_width)
    if bottom <= top or right <= left:
        return result
    rows = np.arange(bottom - top, dtype=np.float32)
    weight = np.clip(rows / max((bottom - top) / 3.0, 1.0), 0.0, 1.0) * by
    band = result[top:bottom, left:right].astype(np.float32)
    band *= 1.0 - weight[:, None, None]
    result[top:bottom, left:right] = np.clip(band + 0.5, 0, 255).astype(np.uint8)
    return result


def shaded(frame: Frame, over: Area, by: float, corner_radius: int) -> Frame:
    """
    A copy of the frame with a rectangle of it, its corners rounded, shaded evenly
    towards black: a box a caption is read on over any picture.

    :param frame: The frame.
    :param over: The box.
    :param by: How dark it is, from zero to one.
    :param corner_radius: Pixels its corners are rounded by.
    """
    mask = Image.new("L", (frame.shape[1], frame.shape[0]), 0)
    left, top, width, height = over.rounded()
    ImageDraw.Draw(mask).rounded_rectangle(
        (left, top, left + width - 1, top + height - 1), radius=corner_radius, fill=255
    )
    weight = np.asarray(mask, dtype=np.float32)[..., None] / 255.0 * by
    darkened_frame = frame.astype(np.float32) * (1.0 - weight)
    return np.clip(darkened_frame + 0.5, 0, 255).astype(np.uint8)


def framed(frame: Frame, around: Area, color: Rgb, thickness: int = 3) -> Frame:
    """
    A copy of the frame with a rectangle outlined on it.
    """
    result = frame.copy()
    left, top, width, height = around.rounded()
    cv2.rectangle(result, (left, top), (left + width, top + height), color, thickness)
    return result


def filled(frame: Frame, around: Area, color: Rgb) -> Frame:
    """
    A copy of the frame with a rectangle painted over it.
    """
    result = frame.copy()
    left, top, width, height = around.rounded()
    cv2.rectangle(result, (left, top), (left + width, top + height), color, -1)
    return result


def lined(
    frame: Frame,
    start: Tuple[float, float],
    end: Tuple[float, float],
    color: Rgb,
    thickness: int = 2,
) -> Frame:
    """
    A copy of the frame with a straight line drawn on it.
    """
    result = frame.copy()
    cv2.line(result, _point(start), _point(end), color, thickness, cv2.LINE_AA)
    return result


def arrowed(
    frame: Frame,
    start: Tuple[float, float],
    end: Tuple[float, float],
    color: Rgb,
    thickness: int = 2,
) -> Frame:
    """
    A copy of the frame with an arrow drawn on it, its head at the end.
    """
    result = frame.copy()
    length = max(((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5, 1.0)
    cv2.arrowedLine(
        result,
        _point(start),
        _point(end),
        color,
        thickness,
        cv2.LINE_AA,
        tipLength=min(12.0 / length, 0.5),
    )
    return result


def _point(at: Tuple[float, float]) -> Tuple[int, int]:
    return int(round(at[0])), int(round(at[1]))


# %% writing


class Anchor(Enum):
    """
    Which point of a line of text is put where it is written, as the drawing library
    names anchors.
    """

    LEFT_MIDDLE = "lm"
    CENTRE_MIDDLE = "mm"
    RIGHT_MIDDLE = "rm"
    LEFT_TOP = "lt"
    CENTRE_TOP = "mt"
    RIGHT_TOP = "rt"


@dataclass(frozen=True)
class Typesetting:
    """
    How a line of text is written on a frame.
    """

    size: int = 24
    """
    The height of the letters, in pixels.
    """

    face: Face = Face.REGULAR
    """
    The face they are set in.
    """

    color: Rgb = NEUTRAL_THEME.text
    """
    What they are written in.
    """

    typeface: Typeface = NEUTRAL_THEME.typeface
    """
    The fonts the faces are set in.
    """

    def written(
        self,
        frame: Frame,
        text: str,
        at: Tuple[float, float],
        anchor: Anchor = Anchor.LEFT_MIDDLE,
    ) -> Frame:
        """
        A copy of the frame with the text written on it.

        :param frame: The frame written on.
        :param text: What to write; new lines break it.
        :param at: Where the anchor goes, in pixels.
        :param anchor: Which point of the text goes there.
        """
        picture = Image.fromarray(frame)
        drawing = ImageDraw.Draw(picture)
        typeface = self.typeface.font(self.face, self.size)
        spacing = self.size * 0.35
        if "\n" in text:
            # several rows hang from their top; a middle anchor is met by raising them by
            # half their height
            anchor_value = anchor.value[0] + "a"
            if anchor.value[1] == "m":
                _, top, _, bottom = drawing.multiline_textbbox(
                    at, text, font=typeface, anchor=anchor_value, spacing=spacing
                )
                at = (at[0], at[1] - (bottom - top) / 2)
        else:
            anchor_value = anchor.value
        drawing.multiline_text(
            at,
            text,
            fill=self.color,
            font=typeface,
            anchor=anchor_value,
            align="center" if anchor.value[0] == "m" else "left",
            spacing=spacing,
        )
        return np.array(picture)

    def width_of(self, text: str) -> float:
        """
        :param text: One line.
        :return: How many pixels wide it is set.
        """
        return self.typeface.font(self.face, self.size).getlength(text)

    def wrapped(self, text: str, width: float) -> str:
        """
        The text broken into lines no wider than given, at spaces.

        :param text: What to break.
        :param width: The widest a line may be, in pixels.
        """
        lines: list[str] = []
        line = ""
        for word in text.split():
            candidate = word if not line else f"{line} {word}"
            if self.width_of(candidate) <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return "\n".join(lines)


# %% writing code


class Token(Enum):
    """
    The kinds of piece a line of Python is coloured by.
    """

    CALL = "call"
    CLASS = "class"
    STRING = "string"
    NUMBER = "number"
    NAME = "name"
    PUNCTUATION = "punctuation"


CODE_PIECE = re.compile(r"\"[^\"]*\"|'[^']*'|\d+(?:\.\d+)?|[A-Za-z_]\w*|\s+|.")
"""
How a line of code comes apart: a string, a number, a name, a run of spaces, or one
other character at a time.
"""


def tokenised(line: str) -> List[Tuple[str, Token]]:
    """
    A line of Python cut into pieces, each with the kind it is coloured by: a name is a
    class when it is capitalised, a call when a parenthesis follows it.

    :param line: The line.
    """
    pieces = CODE_PIECE.findall(line)
    kinds: List[Tuple[str, Token]] = []
    for index, piece in enumerate(pieces):
        following = next(
            (later for later in pieces[index + 1 :] if not later.isspace()), ""
        )
        if piece[0] in "\"'":
            kind = Token.STRING
        elif piece[0].isdigit():
            kind = Token.NUMBER
        elif piece[0].isalpha() or piece[0] == "_":
            kind = (
                Token.CLASS
                if piece[0].isupper()
                else Token.CALL if following == "(" else Token.NAME
            )
        else:
            kind = Token.PUNCTUATION
        kinds.append((piece, kind))
    return kinds


Span = Tuple[int, int]
"""
A stretch of a line: the index of its first character and of the one after its last.
"""


def changed_spans(before: str, after: str) -> List[Span]:
    """
    The stretches of a line of code that differ from an earlier line, as spans of the
    later one: what a reader comparing the two would find changed, piece by piece.

    :param before: The earlier line.
    :param after: The later line.
    """
    earlier = [piece for piece, _ in tokenised(before)]
    later = [piece for piece, _ in tokenised(after)]
    starts = [0]
    for piece in later:
        starts.append(starts[-1] + len(piece))
    return [
        (starts[first], starts[after_last])
        for tag, _, _, first, after_last in SequenceMatcher(
            a=earlier, b=later, autojunk=False
        ).get_opcodes()
        if tag != "equal" and after_last > first
    ]


@dataclass(frozen=True)
class CodeTypesetting:
    """
    How a line of Python is written on a frame: in the mono face, coloured piece by
    piece as an editor would, with any stretch a reader is pointed to marked behind it.
    """

    size: int = 22
    """
    The height of the letters, in pixels.
    """

    theme: VideoTheme = NEUTRAL_THEME
    """
    What the pieces are coloured in, what a marked stretch is filled behind with, and
    the mono font.
    """

    @property
    def face(self) -> Typesetting:
        """
        The mono face at this size, in the theme's text colour.
        """
        return self.theme.typesetting(self.size, Face.MONO)

    def written(
        self,
        frame: Frame,
        line: str,
        at: Tuple[float, float],
        marked: Sequence[Span] = (),
    ) -> Frame:
        """
        A copy of the frame with the line written on it, from its left middle.

        :param frame: The frame written on.
        :param line: One line of code.
        :param at: Where its left middle goes, in pixels.
        :param marked: The stretches of the line marked behind, if any.
        """
        x, y = at
        for first, after_last in marked:
            left, right = x + self.width_of(line[:first]), x + self.width_of(
                line[:after_last]
            )
            frame = filled(
                frame,
                Area(
                    left - 3, y - self.size * 0.62, right - left + 6, self.size * 1.24
                ),
                self.theme.marker,
            )
        for piece, kind in tokenised(line):
            if not piece.isspace():
                frame = replace(self.face, color=self.theme.code_inks[kind]).written(
                    frame, piece, (x, y), Anchor.LEFT_MIDDLE
                )
            x += self.face.width_of(piece)
        return frame

    def width_of(self, line: str) -> float:
        return self.face.width_of(line)
