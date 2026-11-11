"""Draws the cartoon scenes of the notebook of Worksheet 3: the chef, the robot and the guests of the pizzeria, with
speech bubbles and thought clouds.

A scene is an SVG picture; :meth:`Scene.to_markdown` embeds it in a Markdown cell as an image, so the notebook shows it
without running a cell.
"""

from __future__ import annotations

import base64
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from html import escape

from typing_extensions import Iterable

# %% characters


class Mood(Enum):
    """The face a character makes."""

    HAPPY = "happy"
    WORRIED = "worried"
    SHOCKED = "shocked"
    THINKING = "thinking"
    SICK = "sick"


class Look(Enum):
    """The people of the pizzeria, each with the colours of their hair and clothes: hair, shirt, skin."""

    ADA = ("#8a4b2a", "#d9574a", "#f3cfa8")
    BEN = ("#3b2f2a", "#4f9a6b", "#e9b98f")
    CHIDI = ("#1f1a17", "#4a7fb5", "#9b6a45")
    DANA = ("#c9973a", "#8b5fb0", "#f6d6b8")


@dataclass
class Character:
    """One figure of a scene."""

    name: str
    """The name written below the figure."""

    mood: Mood = Mood.HAPPY
    """The face the figure makes."""

    def draw(self, x: float, floor: float) -> Iterable[str]:
        """
        :return: The SVG elements of the figure, standing on the floor with its centre at x.
        """
        raise NotImplementedError

    @property
    def head_top(self) -> float:
        """
        :return: How far above the floor the top of the figure is.
        """
        raise NotImplementedError

    def label(self, x: float, floor: float) -> str:
        """
        :return: The name of the figure, below its feet.
        """
        return (
            f'<text x="{x}" y="{floor + 18}" text-anchor="middle" font-size="13" font-weight="600" '
            f'fill="#3c4654">{escape(self.name)}</text>'
        )


def face(x: float, y: float, mood: Mood, scale: float = 1.0) -> Iterable[str]:
    """
    :return: Eyes, brows and mouth of a face centred at (x, y).
    """
    eye_dx, eye_y = 9 * scale, y - 3 * scale
    if mood is Mood.SICK:
        for side in (-1, 1):
            cx = x + side * eye_dx
            yield (
                f'<path d="M{cx - 3} {eye_y - 3} l6 6 M{cx + 3} {eye_y - 3} l-6 6" stroke="#2b2b2b" '
                f'stroke-width="2" stroke-linecap="round"/>'
            )
    else:
        radius = 4.2 * scale if mood is Mood.SHOCKED else 3.2 * scale
        for side in (-1, 1):
            yield f'<circle cx="{x + side * eye_dx}" cy="{eye_y}" r="{radius}" fill="#2b2b2b"/>'
            yield f'<circle cx="{x + side * eye_dx + 1}" cy="{eye_y - 1}" r="{radius / 3}" fill="#fff"/>'
    if mood in (Mood.WORRIED, Mood.SHOCKED):
        for side in (-1, 1):
            inner, outer = x + side * 5 * scale, x + side * 14 * scale
            yield (
                f'<path d="M{inner} {eye_y - 8 * scale} L{outer} {eye_y - 11 * scale}" stroke="#2b2b2b" '
                f'stroke-width="2" stroke-linecap="round"/>'
            )
    if mood is Mood.THINKING:
        yield (
            f'<path d="M{x + 4 * scale} {eye_y - 10 * scale} q6 -4 11 0" stroke="#2b2b2b" stroke-width="2" '
            f'fill="none" stroke-linecap="round"/>'
        )
    mouth_y = y + 9 * scale
    mouths = {
        Mood.HAPPY: f'<path d="M{x - 8 * scale} {mouth_y - 2} Q{x} {mouth_y + 8 * scale} {x + 8 * scale} '
        f'{mouth_y - 2}" stroke="#2b2b2b" stroke-width="2.2" fill="#b8473f" stroke-linecap="round"/>',
        Mood.WORRIED: f'<path d="M{x - 8 * scale} {mouth_y + 2} q4 -4 8 0 q4 4 8 0" stroke="#2b2b2b" '
        f'stroke-width="2.2" fill="none" stroke-linecap="round"/>',
        Mood.SHOCKED: f'<ellipse cx="{x}" cy="{mouth_y + 1}" rx="{5 * scale}" ry="{7 * scale}" fill="#5a2a26"/>',
        Mood.THINKING: f'<path d="M{x - 6 * scale} {mouth_y} L{x + 6 * scale} {mouth_y - 2}" stroke="#2b2b2b" '
        f'stroke-width="2.2" stroke-linecap="round"/>',
        Mood.SICK: f'<path d="M{x - 8 * scale} {mouth_y + 4} Q{x} {mouth_y - 5} {x + 8 * scale} {mouth_y + 4}" '
        f'stroke="#2b2b2b" stroke-width="2.2" fill="none" stroke-linecap="round"/>',
    }
    yield mouths[mood]
    if mood is Mood.HAPPY:
        for side in (-1, 1):
            yield (
                f'<ellipse cx="{x + side * 15 * scale}" cy="{y + 5 * scale}" rx="{4 * scale}" ry="{2.5 * scale}" '
                f'fill="#f08a7a" opacity="0.55"/>'
            )


@dataclass
class Chef(Character):
    """The chef: a white coat, a tall hat and a moustache."""

    name: str = "Chef"
    """The name written below the figure."""

    @property
    def head_top(self) -> float:
        return 190

    def draw(self, x: float, floor: float) -> Iterable[str]:
        head_y = floor - 112
        yield f'<rect x="{x - 34}" y="{floor - 82}" width="68" height="82" rx="22" fill="#fbfbfb" stroke="#9aa3ad" stroke-width="2"/>'
        for row in (floor - 64, floor - 44, floor - 24):
            yield f'<circle cx="{x}" cy="{row}" r="3" fill="#9aa3ad"/>'
        yield f'<path d="M{x - 18} {floor - 82} L{x} {floor - 66} L{x + 18} {floor - 82}" fill="#d9574a"/>'
        yield f'<circle cx="{x}" cy="{head_y}" r="30" fill="#f3cfa8" stroke="#c99a74" stroke-width="1.5"/>'
        yield f'<rect x="{x - 26}" y="{head_y - 52}" width="52" height="26" rx="4" fill="#fff" stroke="#9aa3ad" stroke-width="2"/>'
        for dx, dy, radius in ((-20, -60, 16), (0, -70, 19), (20, -60, 16)):
            yield (
                f'<circle cx="{x + dx}" cy="{head_y + dy}" r="{radius}" fill="#fff" stroke="#9aa3ad" '
                f'stroke-width="2"/>'
            )
        yield f'<rect x="{x - 24}" y="{head_y - 50}" width="48" height="20" fill="#fff"/>'
        yield from face(x, head_y, self.mood)
        yield (
            f'<path d="M{x} {head_y + 6} q-10 -6 -20 2 q8 0 20 -1 q12 1 20 1 q-10 -8 -20 -2" fill="#5b3a29"/>'
        )


@dataclass
class Robot(Character):
    """The service robot: a box with a screen for a face, an antenna and wheels."""

    name: str = "Robot"
    """The name written below the figure."""

    @property
    def head_top(self) -> float:
        return 175

    def draw(self, x: float, floor: float) -> Iterable[str]:
        head_y = floor - 118
        for side in (-1, 1):
            yield f'<circle cx="{x + side * 20}" cy="{floor - 9}" r="9" fill="#3c4654"/>'
        yield f'<rect x="{x - 32}" y="{floor - 78}" width="64" height="62" rx="10" fill="#9fb4c8" stroke="#5f7486" stroke-width="2"/>'
        yield f'<circle cx="{x}" cy="{floor - 48}" r="9" fill="#f2c14e" stroke="#5f7486" stroke-width="2"/>'
        for side in (-1, 1):
            yield (
                f'<path d="M{x + side * 32} {floor - 66} q{side * 18} 10 {side * 14} 34" stroke="#5f7486" '
                f'stroke-width="6" fill="none" stroke-linecap="round"/>'
            )
        yield f'<rect x="{x - 6}" y="{floor - 88}" width="12" height="12" fill="#5f7486"/>'
        yield f'<rect x="{x - 36}" y="{head_y - 30}" width="72" height="60" rx="14" fill="#c4d4e2" stroke="#5f7486" stroke-width="2"/>'
        yield f'<rect x="{x - 28}" y="{head_y - 22}" width="56" height="44" rx="9" fill="#24394d"/>'
        yield f'<line x1="{x}" y1="{head_y - 30}" x2="{x}" y2="{head_y - 48}" stroke="#5f7486" stroke-width="3"/>'
        yield f'<circle cx="{x}" cy="{head_y - 52}" r="6" fill="#d9574a"/>'
        eyes = {
            Mood.SHOCKED: '<circle cx="{cx}" cy="{cy}" r="6" fill="none" stroke="#7fe0c4" stroke-width="2.5"/>',
            Mood.SICK: '<path d="M{left} {top} l8 8 M{right} {top} l-8 8" stroke="#ff8a7a" stroke-width="2.5"/>',
        }
        for side in (-1, 1):
            cx, cy = x + side * 12, head_y - 4
            template = eyes.get(
                self.mood,
                '<rect x="{left}" y="{top}" width="8" height="8" rx="2" fill="#7fe0c4"/>',
            )
            yield template.format(cx=cx, cy=cy, left=cx - 4, right=cx + 4, top=cy - 4)
        mouth_y = head_y + 11
        mouths = {
            Mood.HAPPY: f'<path d="M{x - 10} {mouth_y - 2} q10 8 20 0" stroke="#7fe0c4" stroke-width="2.5" fill="none"/>',
            Mood.WORRIED: f'<path d="M{x - 10} {mouth_y + 2} l5 -3 l5 3 l5 -3 l5 3" stroke="#f2c14e" stroke-width="2.5" fill="none"/>',
            Mood.SHOCKED: f'<rect x="{x - 5}" y="{mouth_y - 4}" width="10" height="8" fill="#7fe0c4"/>',
            Mood.THINKING: f'<line x1="{x - 9}" y1="{mouth_y}" x2="{x + 9}" y2="{mouth_y}" stroke="#7fe0c4" stroke-width="2.5"/>',
            Mood.SICK: f'<path d="M{x - 10} {mouth_y + 3} q10 -8 20 0" stroke="#ff8a7a" stroke-width="2.5" fill="none"/>',
        }
        yield mouths[self.mood]


@dataclass
class Guest(Character):
    """A guest of the pizzeria, drawn in the colours of their :class:`Look`."""

    look: Look = Look.ADA
    """The hair, shirt and skin colours of the guest."""

    @property
    def head_top(self) -> float:
        return 150

    def draw(self, x: float, floor: float) -> Iterable[str]:
        hair, shirt, skin = self.look.value
        head_y = floor - 108
        yield f'<path d="M{x - 30} {floor} q0 -66 30 -70 q30 4 30 70 z" fill="{shirt}"/>'
        if self.look is Look.ADA:
            yield f'<path d="M{x - 32} {head_y + 34} q-6 -54 32 -62 q38 8 32 62 z" fill="{hair}"/>'
        if self.look is Look.DANA:
            yield f'<circle cx="{x}" cy="{head_y - 34}" r="12" fill="{hair}"/>'
        yield f'<circle cx="{x}" cy="{head_y}" r="28" fill="{skin}"/>'
        hairs = {
            Look.ADA: f'<path d="M{x - 28} {head_y - 4} q8 -30 30 -26 q24 2 26 26 q-20 -14 -56 0" fill="{hair}"/>',
            Look.BEN: f'<path d="M{x - 28} {head_y - 6} q4 -26 28 -24 q26 -2 28 24 q-8 -10 -28 -10 q-18 0 -28 10" fill="{hair}"/>',
            Look.CHIDI: "".join(
                f'<circle cx="{x + dx}" cy="{head_y + dy}" r="9" fill="{hair}"/>'
                for dx, dy in ((-20, -14), (-10, -24), (2, -27), (14, -23), (22, -13))
            ),
            Look.DANA: f'<path d="M{x - 28} {head_y - 2} q2 -28 28 -28 q26 0 28 28 q-14 -16 -28 -16 q-14 0 -28 16" fill="{hair}"/>',
        }
        yield hairs[self.look]
        if self.look is Look.BEN:
            for side in (-1, 1):
                yield (
                    f'<circle cx="{x + side * 9}" cy="{head_y - 3}" r="7.5" fill="none" stroke="#2b2b2b" '
                    f'stroke-width="1.8"/>'
                )
            yield f'<line x1="{x - 1.5}" y1="{head_y - 3}" x2="{x + 1.5}" y2="{head_y - 3}" stroke="#2b2b2b" stroke-width="1.8"/>'
        yield from face(x, head_y, self.mood)
        if self.mood is Mood.SICK:
            yield f'<ellipse cx="{x}" cy="{head_y + 2}" rx="26" ry="20" fill="#9bd38a" opacity="0.35"/>'


# %% bubbles


class BubbleKind(Enum):
    """Whether a bubble is said aloud or only thought."""

    SPEECH = "speech"
    THOUGHT = "thought"


@dataclass
class Bubble:
    """What one character of a scene says or thinks."""

    speaker: int
    """The position of the character in :attr:`Scene.characters`."""

    text: str
    """The words in the bubble; long text is wrapped."""

    kind: BubbleKind = BubbleKind.SPEECH
    """Whether the text is said or thought."""

    code: bool = False
    """Whether the text is set in a monospace font, as code or a formula."""

    def draw(
        self, tail_x: float, tail_y: float, centre_x: float, top: float, width: float
    ) -> Iterable[str]:
        """
        :return: The bubble with its text, centred at centre_x with its top at top, pointing at (tail_x, tail_y).
        """
        characters_per_line = max(10, int((width - 24) / (7.4 if self.code else 6.9)))
        lines = textwrap.wrap(self.text, characters_per_line)
        height = 22 + 17 * len(lines)
        left = centre_x - width / 2
        bottom = top + height
        base_x = min(max(tail_x, left + 26), left + width - 26)
        if self.kind is BubbleKind.SPEECH:
            yield (
                f'<path d="M{base_x - 11} {bottom - 1} L{tail_x} {tail_y} L{base_x + 11} {bottom - 1} z" '
                f'fill="#fff" stroke="#3c4654" stroke-width="2" stroke-linejoin="round"/>'
            )
            yield (
                f'<rect x="{left}" y="{top}" width="{width}" height="{height}" rx="16" fill="#fff" '
                f'stroke="#3c4654" stroke-width="2"/>'
            )
            yield f'<rect x="{base_x - 10}" y="{bottom - 4}" width="20" height="5" fill="#fff"/>'
        else:
            for step, radius in ((0.3, 7), (0.62, 5), (0.88, 3.5)):
                cx = base_x + (tail_x - base_x) * step
                cy = bottom + (tail_y - bottom) * step
                yield f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="#fff" stroke="#3c4654" stroke-width="2"/>'
            puffs = max(5, int(width / 24))
            for index in range(puffs):
                cx = left + 12 + index * (width - 24) / (puffs - 1)
                for cy in (top + 7, bottom - 7):
                    yield f'<circle cx="{cx}" cy="{cy}" r="17" fill="#fff" stroke="#3c4654" stroke-width="2"/>'
            for cx in (left + 6, left + width - 6):
                yield (
                    f'<circle cx="{cx}" cy="{(top + bottom) / 2}" r="{max(17.0, height / 2 - 4)}" fill="#fff" '
                    f'stroke="#3c4654" stroke-width="2"/>'
                )
            yield f'<rect x="{left + 1}" y="{top + 1}" width="{width - 2}" height="{height - 2}" rx="12" fill="#fff"/>'
        family = (
            "DejaVu Sans Mono, Menlo, monospace"
            if self.code
            else "Comic Sans MS, Comic Neue, Chalkboard, sans-serif"
        )
        style = (
            "italic" if self.kind is BubbleKind.THOUGHT and not self.code else "normal"
        )
        for index, line in enumerate(lines):
            yield (
                f'<text x="{centre_x}" y="{top + 24 + 17 * index}" text-anchor="middle" font-size="13.5" '
                f'font-family="{family}" font-style="{style}" fill="#24303d">{escape(line)}</text>'
            )


# %% scenes


@dataclass
class Scene:
    """A row of characters on the floor of the pizzeria, with what they say and think above them."""

    characters: list[Character]
    """The figures, from left to right."""

    bubbles: list[Bubble] = field(default_factory=list)
    """What the figures say or think; a bubble sits above its speaker, a second bubble of the same scene higher."""

    caption: str = ""
    """A line below the scene, such as the time of the evening."""

    width: int = 760
    """The width of the picture in pixels."""

    def to_svg(self) -> str:
        """
        :return: The scene as an SVG document.
        """
        slot = self.width / len(self.characters)
        xs = [slot * (index + 0.5) for index in range(len(self.characters))]
        placed = self.place_bubbles(xs, slot)
        floor = max([230.0] + [-top + 12 for _, _, top, _, _ in placed])
        height = floor + (46 if self.caption else 30)
        parts = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{height}" '
                f'viewBox="0 0 {self.width} {height}" font-family="Helvetica, Arial, sans-serif">'
            ),
            f'<rect width="{self.width}" height="{height}" rx="14" fill="#fdf6ea"/>',
            f'<rect y="{floor}" width="{self.width}" height="{height - floor}" fill="#ead9bd"/>',
        ]
        parts += [
            f'<rect x="{x}" y="{floor + 6}" width="18" height="{height - floor - 6}" fill="#e2cda9"/>'
            for x in range(10, self.width, 40)
        ]
        for character, x in zip(self.characters, xs):
            parts += character.draw(x, floor)
            parts.append(character.label(x, floor))
        for bubble, centre, top, width, _ in sorted(placed, key=lambda item: item[2]):
            speaker = self.characters[bubble.speaker]
            parts += bubble.draw(
                xs[bubble.speaker],
                floor - speaker.head_top - 2,
                centre,
                floor + top,
                width,
            )
        if self.caption:
            parts.append(
                f'<text x="{self.width / 2}" y="{height - 12}" text-anchor="middle" font-size="13" '
                f'font-style="italic" fill="#6b5a40">{escape(self.caption)}</text>'
            )
        parts.append("</svg>")
        return "\n".join(parts)

    def place_bubbles(
        self, xs: list[float], slot: float
    ) -> list[tuple[Bubble, float, float, float, float]]:
        """Place every bubble just above its speaker's head, and higher where it would overlap a bubble placed before.

        :return: Per bubble: the bubble, its centre, its top relative to the floor, its width and its height.
        """
        placed = []
        for bubble in self.bubbles:
            width = min(
                330.0, self.width - 24.0, max(150.0, 44 + 7.0 * len(bubble.text))
            )
            characters_per_line = max(
                10, int((width - 24) / (7.4 if bubble.code else 6.9))
            )
            height = 22 + 17 * len(textwrap.wrap(bubble.text, characters_per_line))
            gap = 34 if bubble.kind is BubbleKind.THOUGHT else 22
            top = -self.characters[bubble.speaker].head_top - gap - height
            centre = self.free_centre(xs[bubble.speaker], top, width, height, placed)
            if centre is None:
                centre = min(
                    max(xs[bubble.speaker], width / 2 + 30), self.width - width / 2 - 30
                )
                for _, other_centre, other_top, other_width, other_height in sorted(
                    placed, key=lambda item: -item[2]
                ):
                    if self.overlaps(
                        centre,
                        top,
                        width,
                        height,
                        other_centre,
                        other_top,
                        other_width,
                        other_height,
                    ):
                        top = other_top - height - 18
            placed.append((bubble, centre, top, width, height))
        return placed

    def free_centre(
        self,
        speaker_x: float,
        top: float,
        width: float,
        height: float,
        placed: list[tuple],
    ) -> float | None:
        """
        :return: The centre nearest to the speaker at which the bubble overlaps no placed bubble and still lies
            above its speaker, or ``None`` if there is none.
        """
        lowest, highest = width / 2 + 30, self.width - width / 2 - 30
        for shift in sorted(
            range(-int(width / 2) + 24, int(width / 2) - 23, 8), key=abs
        ):
            centre = speaker_x + shift
            if not lowest <= centre <= highest:
                continue
            if not any(
                self.overlaps(centre, top, width, height, *other[1:])
                for other in placed
            ):
                return centre
        return None

    @staticmethod
    def overlaps(
        centre: float,
        top: float,
        width: float,
        height: float,
        other_centre: float,
        other_top: float,
        other_width: float,
        other_height: float,
    ) -> bool:
        """
        :return: Whether two bubbles, with a margin around each, cover a common area.
        """
        horizontally = abs(centre - other_centre) < (width + other_width) / 2 + 14
        vertically = (
            top < other_top + other_height + 16 and other_top < top + height + 16
        )
        return horizontally and vertically

    def to_markdown(self) -> str:
        """
        :return: The scene as a Markdown image that carries its SVG with it.
        """
        data = base64.b64encode(self.to_svg().encode()).decode()
        return f'<img src="data:image/svg+xml;base64,{data}" width="{self.width}" alt="{escape(self.alt_text)}">'

    @property
    def alt_text(self) -> str:
        """
        :return: The scene in words, for readers who cannot see the picture.
        """
        return " ".join(
            f"{self.characters[bubble.speaker].name} "
            f"{'says' if bubble.kind is BubbleKind.SPEECH else 'thinks'}: {bubble.text}"
            for bubble in self.bubbles
        )
