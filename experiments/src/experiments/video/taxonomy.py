"""
The framework in one picture: an example query, the kinds of backend that can answer it
laid out as a tree, and the choice among them.

The slide builds up in three steps as the narration reaches them: the query with what
is kept apart in it (its representation, its grounded meaning, its computation), then
the tree of backends, then the choice that picks one for the query.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Sequence, Tuple

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
Seconds a step of the slide takes to appear.
"""


# %% what is shown


@dataclass(frozen=True)
class ExampleQuery:
    """
    The query the slide is explained on: what it is written as, and what it means.
    """

    lines: Tuple[str, ...] = (
        "a(DetectedMontessoriShape)(category=CUBE)",
        "    .where(Colored(shape, CYAN), SupportedBy(shape, lid))",
    )
    """
    The query as written, line by line.
    """

    meaning: str = "the cyan cube resting on the board's lid"
    """
    What it denotes, in words.
    """


@dataclass(frozen=True)
class Aspect:
    """
    One of the things the framework keeps apart in a query.
    """

    name: str
    """
    What it is called.
    """

    reading: str
    """
    What it is for the example query.
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

ASPECTS = (
    Aspect("representation", "the query as written"),
    Aspect("grounded meaning", ExampleQuery().meaning),
    Aspect("computation", "whichever backend is chosen"),
)
"""
What the framework keeps apart in a query, and what each is for the example.
"""

CHOICE_NAME = "BackendChoice"
CHOICE_NOTE = "capability-based meta-queries over the task, in an order of preference among the capable ones"


# %% the slide


@dataclass
class TaxonomySlide(Scene):
    """
    The example query, the tree of backends under it, and the choice between them,
    appearing step by step.
    """

    steps_at: Tuple[float, float, float] = (0.0, 4.0, 8.0)
    """
    Seconds into the slide the query, the tree and the choice appear.
    """

    held_for: float = 12.0
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
    def card(self) -> Area:
        """
        Where the query is written.
        """
        return Area(self.resolution.width / 2 - 400, 26, 800, 30 * len(self.query.lines) + 30)

    @property
    def aspects(self) -> Area:
        """
        Where what is kept apart in the query is written, under the card.
        """
        return Area(self.resolution.width / 2 - 560, self.card.bottom + 8, 1120, 60)

    @property
    def choice(self) -> Area:
        """
        Where the choice is named, between the query and the tree.
        """
        return Area(self.resolution.width / 2 - 470, 216, 940, 62)

    @property
    def root(self) -> Area:
        return Area(self.resolution.width / 2 - 70, 318, 140, 42)

    def kind(self, index: int) -> Area:
        """
        Where one kind of backend is named.

        :param index: Which kind, left to right.
        """
        step = self.resolution.width / (len(self.tree.children) + 1)
        return Area(step * (index + 1) - 160, 400, 320, 66)

    def leaf(self, kind_index: int, index: int) -> Area:
        """
        Where one backend of a kind is named, in the column under its kind.

        :param kind_index: Which kind, left to right.
        :param index: Which backend of it, top to bottom.
        """
        kind = self.kind(kind_index)
        return Area(kind.x + 24, kind.bottom + 14 + index * 48, 300, 40)

    # %% drawing

    def step_weight(self, step: int, seconds: float) -> float:
        """
        How far one step has appeared at a moment, from zero to one.
        """
        return eased((seconds - self.steps_at[step]) / STEP_FADE)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        frame = self._faded_in(frame, self._query_drawn, self.step_weight(0, seconds))
        frame = self._faded_in(frame, self._tree_drawn, self.step_weight(1, seconds))
        return self._faded_in(frame, self._choice_drawn, self.step_weight(2, seconds))

    @staticmethod
    def _faded_in(frame: Frame, drawing, weight: float) -> Frame:
        """
        A drawing blended onto the frame by how far it has appeared.
        """
        if weight <= 0.0:
            return frame
        return blended(frame, drawing(frame), weight)

    def _query_drawn(self, frame: Frame) -> Frame:
        card = self.card
        frame = filled(frame, card, Ink.BUBBLE.rgb)
        frame = framed(frame, card, Ink.HAIRLINE.rgb, thickness=2)
        code = CodeTypesetting(size=22)
        for number, line in enumerate(self.query.lines):
            frame = code.written(frame, line, (card.x + 24, card.y + 28 + number * 30))
        name = Typesetting(size=20, face=Face.BOLD, color=Ink.TEXT.rgb)
        reading = Typesetting(size=19, color=Ink.MUTED.rgb)
        strip = self.aspects
        column = strip.width / len(ASPECTS)
        for number, aspect in enumerate(ASPECTS):
            middle = strip.x + column * (number + 0.5)
            frame = name.written(frame, aspect.name, (middle, strip.y + 18), Anchor.CENTRE_MIDDLE)
            frame = reading.written(frame, aspect.reading, (middle, strip.y + 44), Anchor.CENTRE_MIDDLE)
        return frame

    def _tree_drawn(self, frame: Frame) -> Frame:
        root = self.root
        frame = self._node(frame, root, self.tree, size=24)
        for kind_index, kind in enumerate(self.tree.children):
            box = self.kind(kind_index)
            frame = lined(frame, (root.centre[0], root.bottom), (box.centre[0], box.y), Ink.MUTED.rgb)
            frame = self._node(frame, box, kind, size=22)
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
        frame = arrowed(frame, (pill.centre[0], self.aspects.bottom + 4), (pill.centre[0], pill.y - 2), Ink.TEXT.rgb)
        frame = arrowed(frame, (pill.centre[0], pill.bottom), (pill.centre[0], self.root.y - 2), Ink.TEXT.rgb)
        frame = filled(frame, pill, Ink.PAPER.rgb)
        frame = framed(frame, pill, Ink.ASKED.rgb, thickness=3)
        frame = Typesetting(size=22, face=Face.BOLD, color=Ink.ASKED.rgb).written(
            frame, CHOICE_NAME, (pill.centre[0], pill.y + 20), Anchor.CENTRE_MIDDLE
        )
        return Typesetting(size=19, color=Ink.TEXT.rgb).written(
            frame, CHOICE_NOTE, (pill.centre[0], pill.y + 45), Anchor.CENTRE_MIDDLE
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
        frame = name.written(frame, node.name, (box.centre[0], box.y + 22), Anchor.CENTRE_MIDDLE)
        return Typesetting(size=18, color=Ink.MUTED.rgb).written(
            frame, node.note, (box.centre[0], box.y + 48), Anchor.CENTRE_MIDDLE
        )

    @staticmethod
    def _leaf(frame: Frame, box: Area, node: TreeNode) -> Frame:
        frame = Typesetting(size=20, face=Face.BOLD, color=node.color).written(
            frame, node.name, (box.x + 12, box.y + 12), Anchor.LEFT_MIDDLE
        )
        return Typesetting(size=17, color=Ink.MUTED.rgb).written(
            frame, node.note, (box.x + 12, box.y + 33), Anchor.LEFT_MIDDLE
        )
