"""
The framework in one picture: what a query is, explained on one of the plan's own, and
the backends that can answer it laid out as a tree, with the choice among them.

The slide builds up as the narration reaches each part: the form every query takes,
with its parts named in turn; the example typed in a piece at a time as each piece is
said, and its open field marked; what the example means, what grounds it and what
computes it; then the tree of backends, and the choice that picks one for the query.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Callable, Tuple

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    VIDEO_RESOLUTION,
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Rgb,
    Typesetting,
    arrowed,
    filled,
    framed,
    lined,
)
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased

STEP_FADE = 0.6
"""
Seconds a part of the slide takes to appear.
"""

Drawing = Callable[[Frame], Frame]
"""
One part of the slide, drawn onto a frame.
"""


# %% what is shown


@dataclass(frozen=True)
class QueryPart:
    """
    One part of the form every query takes, as the template names it and as it is
    called under it.
    """

    placeholder: str
    """
    What stands for the part in the template.
    """

    label: str
    """
    What the part is called, under the template.
    """

    named_by: str
    """
    The words of the line defining a query that name the part, at which it is labelled.
    """


QUERY_TEMPLATE = "an(EntityType)(known_field=value, open_field=...).where(further_conditions)"
"""
The form every query takes.
"""

QUERY_PARTS = (
    QueryPart("open_field=...", "left open", "under-specified"),
    QueryPart("EntityType", "its type", "its type"),
    QueryPart("known_field=value", "the fields already known", "the fields already known"),
    QueryPart("further_conditions", "further conditions", "further conditions"),
)
"""
The template's parts, in the order they are named.
"""


@dataclass(frozen=True)
class ExampleQuery:
    """
    The query the slide is explained on: one of the plan's own, what it means, and what
    grounds it.
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

    meaning: str = (
        "a grasp with the left hand, from the top, from an approach direction still "
        "to be chosen"
    )
    """
    What it means, in words.
    """

    grounding: str = (
        "GraspDescription is a class of the robot's own program; the answer is an "
        "instance of it"
    )
    """
    What the classes it names are, and so what its answer is.
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
class SlideMoments:
    """
    Seconds into the slide each part of it comes up, in the order the narration names
    them.
    """

    template: float = 0.0
    """
    The form every query takes.
    """

    parts: Tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)
    """
    Each part of the template named under it, in the order they are named.
    """

    lines: Tuple[float, ...] = (4.0, 6.0, 5.0, 4.5)
    """
    Each line of the example typed in, in the example's order; the first brings the
    name of what the example is.
    """

    open_field: float = 7.0
    """
    The example's open field marked.
    """

    meaning: float = 8.0
    """
    What the example means.
    """

    grounding: float = 9.0
    """
    What grounds it.
    """

    computation: float = 10.0
    """
    What computes it: the arrow down to the backends.
    """

    tree: float = 11.0
    """
    The tree of backends.
    """

    choice: float = 12.0
    """
    The choice among them.
    """


@dataclass(frozen=True)
class TreeNode:
    """
    One backend, or one kind of backend, of the tree.
    """

    name: str
    """
    The class name, or the kind's name.
    """

    note: str = ""
    """
    A few words under the name, or none.
    """

    color: Rgb = Ink.TEXT.rgb
    """
    What the node is drawn in.
    """

    children: Tuple[TreeNode, ...] = ()
    """
    The nodes under it.
    """


BACKEND_TAXONOMY = TreeNode(
    "Backend",
    children=(
        TreeNode(
            "Selective",
            "retrieves what is already known",
            children=(
                TreeNode("WorkingMemory", "short-term memory: the world as it stands", Ink.SIMULATION.rgb),
                TreeNode("LongTermMemory", "every recorded episode", Ink.MEMORY.rgb),
            ),
        ),
        TreeNode(
            "Generative",
            "computes an answer",
            children=(
                TreeNode("PerceptionBackend", "looks through the robot's camera", Ink.PERCEPTION.rgb),
                TreeNode("RippleDownRulesBackend", "rule-based reasoning", Ink.RULES.rgb),
                TreeNode("ProbabilisticBackend", "samples from a model", Ink.PROBABILISTIC.rgb),
            ),
        ),
    ),
)
"""
The kinds of backend and the backends of each kind, as the video meets them.
"""

REPRESENTATION_LABEL = "representation"
MEANING_LABEL = "intended meaning"
GROUNDING_LABEL = "grounding"
COMPUTATION_LABEL = "computation"
COMPUTATION_NOTE = "any backend whose capability holds"
CHOICE_NAME = "BackendChoice"
CHOICE_NOTE = "capability-based meta-queries over the task, in an order of preference among the capable ones"

LABEL_TYPESETTING = Typesetting(size=19, face=Face.BOLD, color=Ink.TEXT.rgb)
"""
How the name of a part of the query is written.
"""

NOTE_TYPESETTING = Typesetting(size=18, color=Ink.MUTED.rgb)
"""
How the words under a name are written.
"""

CODE_LINE_HEIGHT = 26
"""
Pixels from one line of the example to the next.
"""


# %% the slide


@dataclass
class QuerySlide(Scene):
    """
    What a query is, on one of the plan's own, then the tree of backends under it and
    the choice between them, each part appearing as the narration reaches it.
    """

    moments: SlideMoments = SlideMoments()
    """
    When each part comes up.
    """

    held_for: float = 14.0
    """
    How long the slide is shown, in seconds.
    """

    query: ExampleQuery = field(default_factory=ExampleQuery)
    """
    The query the slide is explained on.
    """

    tree: TreeNode = BACKEND_TAXONOMY
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

    @property
    def template_at(self) -> Tuple[float, float]:
        """
        Where the template's left middle is written.
        """
        code = CodeTypesetting(size=22)
        return self.resolution.width / 2 - code.width_of(QUERY_TEMPLATE) / 2, 32

    def part_span(self, part: QueryPart) -> Tuple[float, float]:
        """
        From where to where a part of the template runs across the slide.
        """
        code = CodeTypesetting(size=22)
        left = self.template_at[0] + code.width_of(QUERY_TEMPLATE[: QUERY_TEMPLATE.index(part.placeholder)])
        return left, left + code.width_of(part.placeholder)

    @property
    def card(self) -> Area:
        """
        Where the example is written.
        """
        return Area(self.resolution.width / 2 - 260, 98, 520, CODE_LINE_HEIGHT * len(self.query.lines) + 24)

    @property
    def meaning_block(self) -> Area:
        """
        Where what the example means is written, left of the card.
        """
        return Area(40, self.card.y, self.card.x - 80, self.card.height)

    @property
    def grounding_block(self) -> Area:
        """
        Where what grounds the example is written, right of the card.
        """
        return Area(self.card.right + 40, self.card.y, self.resolution.width - self.card.right - 80, self.card.height)

    @property
    def choice(self) -> Area:
        """
        Where the choice is named, between the query and the tree.
        """
        return Area(self.resolution.width / 2 - 470, 266, 940, 56)

    @property
    def root(self) -> Area:
        return Area(self.resolution.width / 2 - 70, 350, 140, 36)

    def kind(self, index: int) -> Area:
        """
        Where one kind of backend is named.

        :param index: Which kind, left to right.
        """
        step = self.resolution.width / (len(self.tree.children) + 1)
        return Area(step * (index + 1) - 160, 416, 320, 58)

    def leaf(self, kind_index: int, index: int) -> Area:
        """
        Where one backend of a kind is named, in the column under its kind.

        :param kind_index: Which kind, left to right.
        :param index: Which backend of it, top to bottom.
        """
        kind = self.kind(kind_index)
        return Area(kind.x + 24, kind.bottom + 14 + index * 42, 300, 38)

    # %% drawing

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        for drawing, moment in self.drawings():
            frame = self._faded_in(frame, drawing, eased((seconds - moment) / STEP_FADE))
        return frame

    def drawings(self) -> Tuple[Tuple[Drawing, float], ...]:
        """
        Every part of the slide with the moment it comes up, in drawing order.
        """
        moments = self.moments
        parts = tuple((self._part_labelled(part), at) for part, at in zip(QUERY_PARTS, moments.parts))
        lines = tuple((self._line_typed(number), at) for number, at in enumerate(moments.lines))
        return (
            (self._template_drawn, moments.template),
            *parts,
            (self._card_drawn, moments.lines[0]),
            *lines,
            (self._open_field_marked, moments.open_field),
            (self._meaning_drawn, moments.meaning),
            (self._grounding_drawn, moments.grounding),
            (self._computation_drawn, moments.computation),
            (self._tree_drawn, moments.tree),
            (self._choice_drawn, moments.choice),
        )

    @staticmethod
    def _faded_in(frame: Frame, drawing: Drawing, weight: float) -> Frame:
        """
        A drawing blended onto the frame by how far it has appeared.
        """
        if weight <= 0.0:
            return frame
        return blended(frame, drawing(frame), weight)

    def _template_drawn(self, frame: Frame) -> Frame:
        return CodeTypesetting(size=22).written(frame, QUERY_TEMPLATE, self.template_at)

    def _part_labelled(self, part: QueryPart) -> Drawing:
        """
        A part of the template bracketed and named under it.
        """

        def drawing(frame: Frame) -> Frame:
            left, right = self.part_span(part)
            y = self.template_at[1] + 16
            frame = lined(frame, (left, y), (right, y), Ink.MUTED.rgb)
            return NOTE_TYPESETTING.written(frame, part.label, ((left + right) / 2, y + 14), Anchor.CENTRE_MIDDLE)

        return drawing

    def _card_drawn(self, frame: Frame) -> Frame:
        """
        The card the example is typed onto, with what it is named above it.
        """
        card = self.card
        frame = filled(frame, card, Ink.BUBBLE.rgb)
        frame = framed(frame, card, Ink.HAIRLINE.rgb, thickness=2)
        return LABEL_TYPESETTING.written(frame, REPRESENTATION_LABEL, (card.x, card.y - 14), Anchor.LEFT_MIDDLE)

    def line_at(self, number: int) -> Tuple[float, float]:
        """
        Where the left middle of one line of the example is written.
        """
        return self.card.x + 24, self.card.y + 12 + CODE_LINE_HEIGHT * (number + 0.5)

    def _line_typed(self, number: int) -> Drawing:
        """
        One line of the example written in its place.
        """

        def drawing(frame: Frame) -> Frame:
            return CodeTypesetting(size=22).written(frame, self.query.lines[number], self.line_at(number))

        return drawing

    def _open_field_marked(self, frame: Frame) -> Frame:
        number = self.query.open_field_line
        return CodeTypesetting(size=22).written(
            frame, self.query.lines[number], self.line_at(number), marked=(self.query.open_field_span,)
        )

    def _meaning_drawn(self, frame: Frame) -> Frame:
        block = self.meaning_block
        frame = arrowed(frame, (self.card.x - 6, self.card.centre[1]), (block.right + 6, self.card.centre[1]), Ink.MUTED.rgb)
        return self._block_written(frame, block, MEANING_LABEL, self.query.meaning)

    def _grounding_drawn(self, frame: Frame) -> Frame:
        block = self.grounding_block
        frame = arrowed(frame, (self.card.right + 6, self.card.centre[1]), (block.x - 6, self.card.centre[1]), Ink.MUTED.rgb)
        return self._block_written(frame, block, GROUNDING_LABEL, self.query.grounding)

    @staticmethod
    def _block_written(frame: Frame, block: Area, label: str, words: str) -> Frame:
        """
        A name over some words, wrapped to the block.
        """
        frame = LABEL_TYPESETTING.written(frame, label, (block.x, block.y + 10), Anchor.LEFT_MIDDLE)
        wrapped = NOTE_TYPESETTING.wrapped(words, block.width)
        return NOTE_TYPESETTING.written(frame, wrapped, (block.x, block.y + 24), Anchor.LEFT_TOP)

    def _computation_drawn(self, frame: Frame) -> Frame:
        """
        The arrow from the query down to whatever computes it, named beside it.
        """
        x = self.card.centre[0]
        frame = arrowed(frame, (x, self.card.bottom), (x, self.choice.y - 2), Ink.TEXT.rgb)
        y = (self.card.bottom + self.choice.y) / 2
        frame = LABEL_TYPESETTING.written(frame, COMPUTATION_LABEL, (x + 14, y), Anchor.LEFT_MIDDLE)
        return NOTE_TYPESETTING.written(
            frame, COMPUTATION_NOTE, (x + 14 + LABEL_TYPESETTING.width_of(COMPUTATION_LABEL) + 10, y), Anchor.LEFT_MIDDLE
        )

    def _tree_drawn(self, frame: Frame) -> Frame:
        root = self.root
        frame = arrowed(frame, (root.centre[0], self.choice.bottom), (root.centre[0], root.y - 2), Ink.TEXT.rgb)
        frame = self._node(frame, root, self.tree, size=22)
        for kind_index, kind in enumerate(self.tree.children):
            box = self.kind(kind_index)
            frame = lined(frame, (root.centre[0], root.bottom), (box.centre[0], box.y), Ink.MUTED.rgb)
            frame = self._node(frame, box, kind, size=21)
            spine_x = box.x + 10
            last = self.leaf(kind_index, len(kind.children) - 1)
            frame = lined(frame, (spine_x, box.bottom), (spine_x, last.centre[1]), Ink.HAIRLINE.rgb)
            for index, leaf in enumerate(kind.children):
                where = self.leaf(kind_index, index)
                frame = lined(frame, (spine_x, where.centre[1]), (where.x, where.centre[1]), Ink.HAIRLINE.rgb)
                frame = self._leaf(frame, where, leaf)
        return frame

    def _choice_drawn(self, frame: Frame) -> Frame:
        pill = self.choice
        frame = filled(frame, pill, Ink.PAPER.rgb)
        frame = framed(frame, pill, Ink.ASKED.rgb, thickness=3)
        frame = Typesetting(size=21, face=Face.BOLD, color=Ink.ASKED.rgb).written(
            frame, CHOICE_NAME, (pill.centre[0], pill.y + 18), Anchor.CENTRE_MIDDLE
        )
        return Typesetting(size=18, color=Ink.TEXT.rgb).written(
            frame, CHOICE_NOTE, (pill.centre[0], pill.y + 40), Anchor.CENTRE_MIDDLE
        )

    @staticmethod
    def _node(frame: Frame, box: Area, node: TreeNode, size: int) -> Frame:
        """
        A node in its box: its name alone in the middle, or its name over its note.
        """
        frame = filled(frame, box, Ink.PAPER.rgb)
        frame = framed(frame, box, node.color, thickness=2)
        name = Typesetting(size=size, face=Face.BOLD, color=node.color)
        if not node.note:
            return name.written(frame, node.name, box.centre, Anchor.CENTRE_MIDDLE)
        frame = name.written(frame, node.name, (box.centre[0], box.y + 20), Anchor.CENTRE_MIDDLE)
        return Typesetting(size=17, color=Ink.MUTED.rgb).written(
            frame, node.note, (box.centre[0], box.y + 42), Anchor.CENTRE_MIDDLE
        )

    @staticmethod
    def _leaf(frame: Frame, box: Area, node: TreeNode) -> Frame:
        frame = Typesetting(size=19, face=Face.BOLD, color=node.color).written(
            frame, node.name, (box.x + 12, box.y + 11), Anchor.LEFT_MIDDLE
        )
        return Typesetting(size=16, color=Ink.MUTED.rgb).written(
            frame, node.note, (box.x + 12, box.y + 30), Anchor.LEFT_MIDDLE
        )
