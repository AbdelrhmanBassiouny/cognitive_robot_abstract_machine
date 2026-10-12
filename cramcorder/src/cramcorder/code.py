"""
Lines of Python written on a frame, coloured piece by piece as an editor would.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum

from semantic_digital_twin.spatial_types.spatial_types import Point2
from semantic_digital_twin.world_description.geometry import Color
from typing_extensions import ClassVar, List, Sequence

from cramcorder.frame import Frame
from cramcorder.lettering import Face
from cramcorder.theme import VideoTheme
from cramcorder.typesetting import Anchor, Typesetting


class Token(StrEnum):
    """
    The kinds of piece a line of Python is coloured by.
    """

    CALL = "call"
    """
    A name followed by a parenthesis.
    """

    CLASS = "class"
    """
    A capitalised name.
    """

    STRING = "string"
    """
    A quoted string.
    """

    NUMBER = "number"
    """
    A number.
    """

    NAME = "name"
    """
    Any other name.
    """

    PUNCTUATION = "punctuation"
    """
    Anything else.
    """


@dataclass(frozen=True)
class Span:
    """
    A stretch of a line.
    """

    first: int
    """
    The index of its first character.
    """

    after_last: int
    """
    The index of the character after its last.
    """


@dataclass(frozen=True)
class CodePiece:
    """
    One piece of a line of code with the kind it is coloured by.
    """

    text: str
    """
    The characters of the piece.
    """

    token: Token
    """
    The kind of piece it is.
    """


@dataclass(frozen=True)
class CodeLine:
    """
    One line of Python.
    """

    text: str
    """
    The line.
    """

    PIECE: ClassVar[re.Pattern] = re.compile(
        r"\"[^\"]*\"|'[^']*'|\d+(?:\.\d+)?|[A-Za-z_]\w*|\s+|."
    )
    """
    How a line comes apart: a string, a number, a name, a run of spaces, or one other
    character at a time.
    """

    @property
    def pieces(self) -> List[CodePiece]:
        """
        The line cut into pieces, each with the kind it is coloured by: a name is a class
        when it is capitalised, a call when a parenthesis follows it.
        """
        texts = self.PIECE.findall(self.text)
        pieces: List[CodePiece] = []
        for index, text in enumerate(texts):
            following = next(
                (later for later in texts[index + 1 :] if not later.isspace()), ""
            )
            pieces.append(CodePiece(text, self._token_of(text, following)))
        return pieces

    @staticmethod
    def _token_of(text: str, following: str) -> Token:
        """
        :param text: One piece of the line.
        :param following: The piece after it that is not a space, if any.
        :return: The kind of piece it is.
        """
        if text[0] in "\"'":
            return Token.STRING
        if text[0].isdigit():
            return Token.NUMBER
        if not (text[0].isalpha() or text[0] == "_"):
            return Token.PUNCTUATION
        if text[0].isupper():
            return Token.CLASS
        return Token.CALL if following == "(" else Token.NAME

    def changed_spans(self, earlier: CodeLine) -> List[Span]:
        """
        :param earlier: The line before this one.
        :return: The stretches of this line that differ from the earlier one: what a
            reader comparing the two would find changed, piece by piece.
        """
        before = [piece.text for piece in earlier.pieces]
        after = [piece.text for piece in self.pieces]
        starts = [0]
        for text in after:
            starts.append(starts[-1] + len(text))
        return [
            Span(starts[first], starts[after_last])
            for tag, _, _, first, after_last in SequenceMatcher(
                a=before, b=after, autojunk=False
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

    theme: VideoTheme = field(default_factory=VideoTheme.neutral)
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

    def color_of(self, token: Token) -> Color:
        """
        :param token: A kind of piece.
        :return: What pieces of that kind are written in.
        """
        return {
            Token.CALL: self.theme.syntax.call,
            Token.CLASS: self.theme.syntax.class_name,
            Token.STRING: self.theme.syntax.string,
            Token.NUMBER: self.theme.syntax.number,
            Token.NAME: self.theme.text,
            Token.PUNCTUATION: self.theme.muted,
        }[token]

    def written(
        self,
        frame: Frame,
        line: CodeLine,
        at: Point2,
        marked: Sequence[Span] = (),
    ) -> Frame:
        """
        :param frame: The frame written on.
        :param line: The line.
        :param at: Where its left middle goes, in pixels.
        :param marked: The stretches of the line marked behind, if any.
        :return: A copy of the frame with the line written on it.
        """
        x, y = float(at.x), float(at.y)
        for span in marked:
            left = x + self.width_of(line.text[: span.first])
            right = x + self.width_of(line.text[: span.after_last])
            frame = frame.filled(
                Frame.box(
                    left - 3, y - self.size * 0.62, right - left + 6, self.size * 1.24
                ),
                self.theme.marker,
            )
        for piece in line.pieces:
            if not piece.text.isspace():
                coloured = Typesetting(
                    size=self.size,
                    face=Face.MONO,
                    color=self.color_of(piece.token),
                    typeface=self.theme.typeface,
                )
                frame = coloured.written(
                    frame, piece.text, Point2(x, y), Anchor.LEFT_MIDDLE
                )
            x += self.face.width_of(piece.text)
        return frame

    def width_of(self, text: str) -> float:
        """
        :param text: A stretch of one line.
        :return: How many pixels wide it is set.
        """
        return self.face.width_of(text)
