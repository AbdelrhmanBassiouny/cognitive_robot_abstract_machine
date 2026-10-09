"""
Animated scenes to start a video from.

Each is a :class:`~experiments.video.drawing.ScenePainting` holding only what it shows,
so a video writes its own words and keeps the look of the package. None of them draws a
progress bar or a caption; the production draws both over every scene.
"""

from __future__ import annotations

from dataclasses import dataclass

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    FadeIn,
    GrowFromCenter,
    Line as ManimLine,
    ReplacementTransform,
    VGroup,
)
from typing_extensions import List, Tuple

from experiments.video.animation import AnimationStep
from experiments.video.drawing import (
    AnimationPalette,
    Card,
    ChapterHeader,
    DriftingConstellation,
    Headline,
    LetterWeight,
    ScenePainter,
    ScenePainting,
)

# %% a title


@dataclass
class TitleCard(ScenePainting):
    """
    A title and a line under it, over a drifting background: the opening of a video.

    It plays one beat per line said over it, writing the title on the first and holding
    it for the rest.
    """

    heading: str
    """
    The title.
    """

    standfirst: str
    """
    The line under the title.
    """

    widest: float = 12.4
    """
    How wide the title may be before it is narrowed, in Manim's units.
    """

    heading_size: float = 46.0
    """
    The height of the title's letters.
    """

    standfirst_size: float = 34.0
    """
    The height of the letters under it.
    """

    def beats_of(
        self, painter: ScenePainter, palette: AnimationPalette
    ) -> List[Tuple[AnimationStep, ...]]:
        background = DriftingConstellation(colour=palette.accent).built()
        heading = Headline(
            self.heading,
            size=self.heading_size,
            weight=LetterWeight.BOLD,
            palette=palette,
        ).fitted_to(self.widest)
        standfirst = Headline(
            self.standfirst,
            size=self.standfirst_size,
            colour=palette.muted,
            palette=palette,
        ).fitted_to(self.widest)
        title = VGroup(heading, standfirst).arrange(DOWN, buff=0.28)
        rule = ManimLine(
            LEFT * 1.4,
            RIGHT * 1.4,
            stroke_color=palette.accent,
            stroke_width=4,
        ).next_to(title, DOWN, buff=0.38)
        painter.add(background)
        beats: List[Tuple[AnimationStep, ...]] = [
            (
                AnimationStep(weight=0.9, drawn=(FadeIn(heading, shift=UP * 0.2),)),
                AnimationStep(
                    weight=0.6,
                    drawn=(FadeIn(standfirst), GrowFromCenter(rule)),
                ),
            )
        ]
        beats.extend(
            (AnimationStep(weight=1.0),) for _ in range(painter.schedule_beats - 1)
        )
        return beats


# %% numbered cards, one per beat


@dataclass
class NumberedCards(ScenePainting):
    """
    Numbered cards revealed one per beat, under a chapter header: a list the narration
    walks through.
    """

    heading: str
    """
    What the chapter is about, shown in the corner.
    """

    cards: Tuple[Tuple[str, str], ...]
    """
    Each card's number and what it says, in the order they are revealed.
    """

    number: str = "01"
    """
    Which chapter it is, shown in the corner.
    """

    card_width: float = 3.4
    """
    How wide one card is, in Manim's units.
    """

    card_height: float = 1.6
    """
    How tall one card is, in Manim's units.
    """

    def beats_of(
        self, painter: ScenePainter, palette: AnimationPalette
    ) -> List[Tuple[AnimationStep, ...]]:
        header = ChapterHeader(
            number=self.number, title=self.heading, palette=palette
        ).built()
        painter.add(header)
        built = [
            Card(
                heading=number,
                body=(words,),
                colour=palette.accent,
                palette=palette,
                width=self.card_width,
                height=self.card_height,
            ).built()
            for number, words in self.cards
        ]
        VGroup(*built).arrange(RIGHT, buff=0.4)
        return [
            (AnimationStep(weight=1.0, drawn=(FadeIn(card, shift=UP * 0.3),)),)
            for card in built
        ]


# %% three cards at once


@dataclass
class OverviewCards(ScenePainting):
    """
    Three cards shown together, then held: what a video is about, in one frame.
    """

    heading: str
    """
    What the chapter is about, shown in the corner.
    """

    cards: Tuple[Tuple[str, Tuple[str, ...]], ...]
    """
    Each card's heading and the lines under it.
    """

    number: str = "00"
    """
    Which chapter it is, shown in the corner.
    """

    def beats_of(
        self, painter: ScenePainter, palette: AnimationPalette
    ) -> List[Tuple[AnimationStep, ...]]:
        painter.add(
            ChapterHeader(
                number=self.number, title=self.heading, palette=palette
            ).built()
        )
        built = [
            Card(
                heading=heading, body=body, colour=palette.accent, palette=palette
            ).built()
            for heading, body in self.cards
        ]
        VGroup(*built).arrange(RIGHT, buff=0.35)
        beats: List[Tuple[AnimationStep, ...]] = [
            (
                AnimationStep(
                    weight=1.0,
                    drawn=tuple(FadeIn(card, shift=UP * 0.25) for card in built),
                ),
            )
        ]
        beats.extend(
            (AnimationStep(weight=1.0),) for _ in range(painter.schedule_beats - 1)
        )
        return beats


# %% summary cards and a thank you


@dataclass
class ClosingCards(ScenePainting):
    """
    A card per point to take away, one per beat, replaced by a closing line on the last
    beat.
    """

    heading: str
    """
    What the chapter is about, shown in the corner.
    """

    points: Tuple[Tuple[str, Tuple[str, ...]], ...]
    """
    Each summary card's heading and the lines under it.
    """

    farewell: str
    """
    The closing line, shown on the last beat.
    """

    number: str = "99"
    """
    Which chapter it is, shown in the corner.
    """

    farewell_size: float = 44.0
    """
    The height of the closing line's letters.
    """

    def beats_of(
        self, painter: ScenePainter, palette: AnimationPalette
    ) -> List[Tuple[AnimationStep, ...]]:
        header = ChapterHeader(
            number=self.number, title=self.heading, palette=palette
        ).built()
        painter.add(header)
        built = [
            Card(
                heading=heading, body=body, colour=palette.accent, palette=palette
            ).built()
            for heading, body in self.points
        ]
        shown = VGroup(*built).arrange(RIGHT, buff=0.35)
        beats: List[Tuple[AnimationStep, ...]] = [
            (AnimationStep(weight=1.0, drawn=(FadeIn(card, shift=UP * 0.25),)),)
            for card in built
        ]
        farewell = Headline(
            self.farewell,
            size=self.farewell_size,
            weight=LetterWeight.BOLD,
            palette=palette,
        ).built()
        beats.append(
            (AnimationStep(weight=1.0, drawn=(ReplacementTransform(shown, farewell),)),)
        )
        return beats
