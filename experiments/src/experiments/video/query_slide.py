"""
The introduction in one slide, in three beats: a query of the plan's own with its open
field marked and what it says in words; then the query shrunk to the top and the
backends that can answer one laid out by kind, with the choice among them; then the
hero frame, the query above a divider and the paper's principle under it in large
type, that backends differ in their source of information and their mechanism and
never in the description.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Tuple

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    BODY_SIZE,
    CLAIM_SIZE,
    LABEL_SIZE,
    MARGIN,
    VIDEO_RESOLUTION,
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Rgb,
    Typesetting,
    filled,
    framed,
    lined,
)
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased

STEP_FADE = 0.25
"""
Seconds a part of the slide takes to appear or to give way.
"""

MOVE = 0.3
"""
Seconds the query takes to shrink to the top.
"""

CODE_SIZE = BODY_SIZE
"""
The letters of the query while it is the one thing on the slide.
"""

SMALL_CODE_SIZE = LABEL_SIZE
"""
The letters of the query once it has shrunk to the top.
"""

HEADER_CLEAR = 96
"""
Pixels from the top kept clear for the chapter's pill.
"""

# %% what is shown


@dataclass(frozen=True)
class ExampleQuery:
    """
    The query the slide is explained on: one of the plan's own, and what it says in
    words.
    """

    lines: Tuple[str, ...] = (
        "a(GraspDescription)(",
        "  approach_direction=...,",
        "  vertical_alignment=TOP,",
        "  end_effector=LEFT_HAND)",
    )
    """
    The query as written, line by line.
    """

    open_field: str = "..."
    """
    How a field left for the answering backend to fill is written.
    """

    gloss: str = (
        "a grasp with the left hand, from the top, approach direction still to be chosen"
    )
    """
    What it says, in words, under it.
    """

    @property
    def open_field_line(self) -> int:
        """
        Which line leaves a field open.
        """
        return next(number for number, line in enumerate(self.lines) if self.open_field in line)

    @property
    def open_field_span(self) -> Tuple[int, int]:
        """
        Where on its line the open field is written: the index of its first character
        and of the one after its last.
        """
        first = self.lines[self.open_field_line].index(self.open_field)
        return first, first + len(self.open_field)


@dataclass(frozen=True)
class IntroductionMoments:
    """
    Seconds into the slide each beat comes up, as the narration reaches it.
    """

    example: float = 0.0
    """
    The query, on its card in the middle.
    """

    open_field: float = 3.0
    """
    Its open field marked.
    """

    gloss: float = 4.0
    """
    What it says, in words.
    """

    backends: float = 7.0
    """
    The query shrinks to the top, and the backends come up by kind with the choice.
    """

    hero: float = 14.0
    """
    The backends give way to the divider, the two labels and the principle.
    """


@dataclass(frozen=True)
class BackendKind:
    """
    One kind of backend and the backends of that kind, in their colours.
    """

    name: str
    backends: Tuple[Tuple[str, Rgb], ...]


BACKEND_KINDS = (
    BackendKind(
        "Selective",
        (("WorkingMemory", Ink.SIMULATION.rgb), ("LongTermMemory", Ink.MEMORY.rgb)),
    ),
    BackendKind(
        "Generative",
        (
            ("PerceptionBackend", Ink.PERCEPTION.rgb),
            ("RippleDownRulesBackend", Ink.RULES.rgb),
            ("ProbabilisticBackend", Ink.PROBABILISTIC.rgb),
        ),
    ),
)
"""
The kinds of backend and the backends of each kind, as the paper's table lists them.
"""

CHOICE_NAME = "BackendChoice"
"""
What the choice among the backends is called in the code.
"""


# %% the slide


@dataclass
class IntroductionSlide(Scene):
    """
    The three beats of the introduction on one slide, each coming up as the narration
    reaches it.
    """

    choice_note: str
    """
    What a backend choice does, under its name.
    """

    principle: str
    """
    The paper's principle, in large type on the hero frame.
    """

    statement_label: str
    """
    What is named above the divider.
    """

    backends_label: str
    """
    What is named below the divider.
    """

    moments: IntroductionMoments = IntroductionMoments()
    """
    When each beat comes up.
    """

    held_for: float = 20.0
    """
    How long the slide is shown, in seconds.
    """

    query: ExampleQuery = field(default_factory=ExampleQuery)
    """
    The query the slide is explained on.
    """

    kinds: Tuple[BackendKind, ...] = BACKEND_KINDS
    """
    The backends, by kind.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    # %% where things lie

    def card_for(self, size: int) -> Tuple[float, float]:
        """
        How wide and tall the query's card is at a letter size.
        """
        code = CodeTypesetting(size=size)
        width = max(code.width_of(line) for line in self.query.lines) + 2 * size
        return width, len(self.query.lines) * size * 1.4 + size

    @property
    def middle_card(self) -> Area:
        """
        The card in the middle of the slide, in the first beat.
        """
        width, height = self.card_for(CODE_SIZE)
        return Area(self.resolution.width / 2 - width / 2, HEADER_CLEAR + 60, width, height)

    @property
    def top_card(self) -> Area:
        """
        The card at the top, from the second beat on.
        """
        width, height = self.card_for(SMALL_CODE_SIZE)
        return Area(self.resolution.width / 2 - width / 2, HEADER_CLEAR, width, height)

    @property
    def choice(self) -> Area:
        return Area(MARGIN + 60, self.top_card.bottom + 28, self.resolution.width - 2 * MARGIN - 120, 68)

    def kind(self, index: int) -> Area:
        step = self.resolution.width / (len(self.kinds) + 1)
        return Area(step * (index + 1) - 170, self.choice.bottom + 30, 340, 40)

    def backend(self, kind_index: int, index: int) -> Tuple[float, float]:
        """
        Where one backend's name is written, its left middle.
        """
        kind = self.kind(kind_index)
        return kind.x + 36, kind.bottom + 26 + index * 38

    @property
    def divider_y(self) -> float:
        return self.top_card.bottom + 68

    # %% drawing

    def picture_at(self, seconds: float) -> Frame:
        moments = self.moments
        frame = self.resolution.blank(255)
        moved = eased((seconds - moments.backends) / MOVE)
        card = self.middle_card.towards(self.top_card, moved)
        size = CODE_SIZE + (SMALL_CODE_SIZE - CODE_SIZE) * moved
        frame = self._faded(frame, lambda f: self._card_drawn(f, card, size, seconds >= moments.open_field), eased((seconds - moments.example) / STEP_FADE))
        gloss = min(eased((seconds - moments.gloss) / STEP_FADE), 1.0 - moved)
        frame = self._faded(frame, self._gloss_drawn, gloss)
        backends = min(eased((seconds - moments.backends - MOVE) / STEP_FADE), 1.0 - eased((seconds - moments.hero) / STEP_FADE))
        frame = self._faded(frame, self._backends_drawn, backends)
        return self._faded(frame, self._hero_drawn, eased((seconds - moments.hero) / STEP_FADE))

    @staticmethod
    def _faded(frame: Frame, drawing, weight: float) -> Frame:
        if weight <= 0.0:
            return frame
        return blended(frame, drawing(frame), min(weight, 1.0))

    def _card_drawn(self, frame: Frame, card: Area, size: float, marked: bool) -> Frame:
        """
        The query on its card, wherever the card lies and however large its letters,
        its open field marked once it has been named.
        """
        code = CodeTypesetting(size=int(round(size)))
        frame = filled(frame, card, Ink.BUBBLE.rgb)
        frame = framed(frame, card, Ink.HAIRLINE.rgb, thickness=2)
        for number, line in enumerate(self.query.lines):
            at = (card.x + size, card.y + size / 2 + size * 1.4 * (number + 0.5))
            spans = (self.query.open_field_span,) if marked and number == self.query.open_field_line else ()
            frame = code.written(frame, line, at, marked=spans)
        return frame

    def _gloss_drawn(self, frame: Frame) -> Frame:
        card = self.middle_card
        words = Typesetting(size=BODY_SIZE, color=Ink.MUTED.rgb)
        return words.written(frame, words.wrapped(self.query.gloss, 900), (self.resolution.width / 2, card.bottom + 44), Anchor.CENTRE_TOP)

    def _backends_drawn(self, frame: Frame) -> Frame:
        """
        The choice under the query, and the backends by kind under it.
        """
        choice = self.choice
        frame = framed(frame, choice, Ink.TEXT.rgb, thickness=2)
        frame = Typesetting(size=BODY_SIZE, face=Face.BOLD).written(frame, CHOICE_NAME, (choice.centre[0], choice.y + 22), Anchor.CENTRE_MIDDLE)
        frame = Typesetting(size=LABEL_SIZE, color=Ink.TEXT.rgb).written(frame, self.choice_note, (choice.centre[0], choice.y + 49), Anchor.CENTRE_MIDDLE)
        for kind_index, kind in enumerate(self.kinds):
            box = self.kind(kind_index)
            frame = lined(frame, (choice.centre[0], choice.bottom), (choice.centre[0], choice.bottom + 12), Ink.MUTED.rgb)
            frame = lined(frame, (self.kind(0).centre[0], choice.bottom + 12), (self.kind(len(self.kinds) - 1).centre[0], choice.bottom + 12), Ink.MUTED.rgb)
            frame = lined(frame, (box.centre[0], choice.bottom + 12), (box.centre[0], box.y), Ink.MUTED.rgb)
            frame = Typesetting(size=BODY_SIZE, face=Face.BOLD).written(frame, kind.name, box.centre, Anchor.CENTRE_MIDDLE)
            spine = box.x + 14
            last = self.backend(kind_index, len(kind.backends) - 1)
            frame = lined(frame, (spine, box.bottom), (spine, last[1]), Ink.HAIRLINE.rgb)
            for index, (name, color) in enumerate(kind.backends):
                at = self.backend(kind_index, index)
                frame = lined(frame, (spine, at[1]), (at[0] - 10, at[1]), Ink.HAIRLINE.rgb)
                frame = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=color).written(frame, name, at, Anchor.LEFT_MIDDLE)
        return frame

    def _hero_drawn(self, frame: Frame) -> Frame:
        """
        The divider under the query, the statement named above it and the backends
        below, and the principle large under them.
        """
        y = self.divider_y
        label = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.MUTED.rgb)
        frame = lined(frame, (MARGIN, y), (self.resolution.width - MARGIN, y), Ink.TEXT.rgb, thickness=2)
        frame = label.written(frame, self.statement_label, (MARGIN, y - 18), Anchor.LEFT_MIDDLE)
        frame = label.written(frame, self.backends_label, (MARGIN, y + 20), Anchor.LEFT_MIDDLE)
        hero = Typesetting(size=CLAIM_SIZE, face=Face.BOLD)
        middle = (y + 40 + self.resolution.stage_height) / 2
        return hero.written(frame, hero.wrapped(self.principle, 1040), (self.resolution.width / 2, middle), Anchor.CENTRE_MIDDLE)
