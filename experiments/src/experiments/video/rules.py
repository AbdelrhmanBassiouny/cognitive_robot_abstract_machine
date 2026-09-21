"""
The ripple-down rules concluding which hole the cube belongs in, watched being run.

The rule tree is drawn elided; the piece the look found arrives as the case; the rule
that fired in that very classification, read off the tree's own trace, is highlighted;
and the hole the rules concluded is pointed out on the robot's picture of the board.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import Dict, List, Optional

from experiments.montessori.perception.overlay import project_to_pixels
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.open_slots.holes import HoleShapeRules, PieceToSort
from experiments.paper.lettering import Face
from experiments.video.canvas import (
    BODY_SIZE,
    LABEL_SIZE,
    Anchor,
    Area,
    Ink,
    Typesetting,
    filled,
    fitted,
    framed,
)
from experiments.video.sources import RecordedRun
from experiments.video.stages import PANEL_VISUAL
from experiments.video.timeline import Frame, Resolution, Scene, eased
from krrood.entity_query_language.rdr.rule_tree_view import (
    RuleStatus,
    RuleView,
    format_condition,
    format_conclusion,
    resolve_status,
    walk_rules,
)

ELSE_BRANCH = "else"
"""
What the branch to the next rule is called: taken when the condition does not hold.
"""

RULE_SIZE = 24
"""
The letters of a rule's condition and conclusion: between the video's body and label
sizes, so that the longest condition fits its node.
"""

ELLIPSIS = "⋮"
"""
What stands for the rules not drawn between the rule that fired and the last.
"""

# %% the rules, run on the recorded piece


@dataclass(frozen=True)
class TracedRule:
    """
    One rule of the tree and what happened to it when the case was classified.
    """

    condition: str
    """
    The rule's condition, as text.
    """

    conclusion: str
    """
    What it concludes, as text.
    """

    kind: str
    """
    How it relates to the rule before it, as the tree names it.
    """

    status: RuleStatus
    """
    Fired, evaluated but not holding, or never reached.
    """


@dataclass
class HoleRuleTrace:
    """
    The hole rules run on the piece the look found, keeping what the tree recorded.
    """

    piece: MontessoriShape
    """
    The piece being sorted.
    """

    rules: HoleShapeRules = field(default_factory=HoleShapeRules)
    """
    The rule tree.
    """

    @cached_property
    def concluded(self) -> Optional[MontessoriShapeCategory]:
        """
        The shape of hole the rules concluded.
        """
        return self.rules.shape_for(self.piece)

    @cached_property
    def traced(self) -> List[TracedRule]:
        """
        Every rule of the tree, in the order the tree walks them, with its status in
        this classification.
        """
        trace = self.rules.rules._trace(PieceToSort(self.piece))
        return [
            TracedRule(
                condition=format_condition(rule.condition),
                conclusion=" ".join(format_conclusion(add) for add in rule.conclusions),
                kind=rule.kind.value,
                status=resolve_status(
                    rule, trace.satisfied_condition_ids, trace.evaluated_expression_ids
                ),
            )
            for rule in walk_rules(self.rules.rules.conditions_root)
        ]

    @property
    def evaluation_order(self) -> List[int]:
        """
        Which rules were evaluated, in order: every rule up to and including the one
        that fired.
        """
        order = []
        for index, rule in enumerate(self.traced):
            if rule.status is RuleStatus.NOT_EVALUATED:
                continue
            order.append(index)
        return order


# %% the concluded hole on the robot's picture


@dataclass
class HoleOnThePicture:
    """
    The board's holes on the robot's own picture, with the concluded one pointed out.
    """

    run: RecordedRun
    """
    The run, whose first camera frame is drawn on.
    """

    radius: float = 0.03
    """
    How far around a hole's centre the ring is drawn, in metres.
    """

    @cached_property
    def frame(self):
        return self.run.frame(0)

    @cached_property
    def holes(self) -> Dict[MontessoriShapeCategory, np.ndarray]:
        """
        Where each aperture of the board stands in the world the plan chose from, by
        the shape it takes; a shape the board has two holes of keeps the first.
        """
        world = self.run.world
        board = next(
            annotation
            for annotation in world.semantic_annotations
            if isinstance(annotation, ShapeSortingBoard)
        )
        holes: Dict[MontessoriShapeCategory, np.ndarray] = {}
        for hole in board.apertures:
            holes.setdefault(
                hole.shape_category,
                world.compute_forward_kinematics_np(world.root, hole.root)[:3, 3],
            )
        return holes

    @property
    def lid_height(self) -> float:
        """
        Height of the lid the holes are cut into, in metres: where the apertures stand.
        """
        return float(np.mean([hole[2] for hole in self.holes.values()]))

    def crop(self) -> Area:
        """
        The stretch of the picture holding every hole.
        """
        centres = project_to_pixels(
            self.frame, np.array([hole[:2] for hole in self.holes.values()]), self.lid_height
        )
        left, top = centres.min(axis=0)
        right, bottom = centres.max(axis=0)
        pad = (right - left) * 0.35
        return Area(left - pad, top - pad * 1.2, right - left + 2 * pad, bottom - top + 2.4 * pad)

    def drawn(self, concluded: Optional[MontessoriShapeCategory], weight: float) -> Frame:
        """
        The picture cropped to the board, the concluded hole ringed.

        :param concluded: The hole to ring, or None for none.
        :param weight: How strongly the ring shows, from zero to one.
        """
        picture = cv2.cvtColor(self.frame.color, cv2.COLOR_BGR2RGB).copy()
        overlay = picture.copy()
        for category, centre in self.holes.items():
            [pixel] = project_to_pixels(self.frame, centre[:2].reshape(1, 2), self.lid_height)
            [edge] = project_to_pixels(
                self.frame, (centre[:2] + np.array([self.radius, 0.0])).reshape(1, 2), self.lid_height
            )
            pixels = int(round(float(np.linalg.norm(edge - pixel))))
            strong = category is concluded
            if strong:
                cv2.circle(overlay, tuple(pixel.round().astype(int)), pixels + 4, Ink.ANSWER.rgb, 5, cv2.LINE_AA)
        cv2.addWeighted(overlay, weight, picture, 1 - weight, 0, picture)
        left, top, width, height = self.crop().rounded()
        left, top = max(left, 0), max(top, 0)
        return picture[top : top + height, left : left + width]


# %% the scene


@dataclass
class RuleTreeEvaluation(Scene):
    """
    The rule tree elided: the case arriving, the rule that fired at full size and
    highlighted once its condition has been checked, an ellipsis for the rules under
    it, and the last rule of the tree at full size; beside it, the concluded hole
    ringed on the robot's picture of the board.
    """

    trace: HoleRuleTrace
    """
    The rules, run.
    """

    board: HoleOnThePicture
    """
    The holes on the robot's picture.
    """

    tree_for: float = 2.0
    """
    Seconds the tree stands alone before the case arrives.
    """

    checking_for: float = 1.0
    """
    Seconds the fired rule's condition is checked before it is highlighted.
    """

    answer_for: float = 5.0
    """
    Seconds the conclusion is shown at the end.
    """

    resolution: Resolution = PANEL_VISUAL
    """
    The size the scene draws itself at.
    """

    tree_width: float = 600.0
    """
    Pixels the nodes are wide.
    """

    @property
    def duration(self) -> float:
        return self.tree_for + self.checking_for + self.answer_for

    @property
    def answers_at(self) -> float:
        """
        Seconds into the scene the rule that fired is highlighted and the hole ringed.
        """
        return self.tree_for + self.checking_for

    @property
    def fired(self) -> TracedRule:
        """
        The rule that fired: the last the case reached.
        """
        return self.trace.traced[self.trace.evaluation_order[-1]]

    @property
    def last(self) -> TracedRule:
        """
        The last rule of the tree.
        """
        return self.trace.traced[-1]

    @property
    def case_chip(self) -> Area:
        return Area(0, 8, self.tree_width, 40)

    @property
    def fired_node(self) -> Area:
        return Area(0, 72, self.tree_width, 92)

    @property
    def last_node(self) -> Area:
        return Area(0, 268, self.tree_width, 92)

    @property
    def board_area(self) -> Area:
        return Area(self.tree_width + 30, 8, self.resolution.width - self.tree_width - 30, self.resolution.height - 16)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        arrived = seconds >= self.tree_for
        done = seconds >= self.answers_at
        frame = self._tree(frame, arrived, done)
        concluded = self.trace.concluded if done else None
        weight = eased((seconds - self.answers_at) / 0.25) if done else 0.0
        return fitted(frame, self.board.drawn(concluded, weight), self.board_area)

    def _tree(self, frame: Frame, arrived: bool, done: bool) -> Frame:
        """
        The case, the rule that fired, the ellipsis and the last rule, the branches
        between them, and the rule that fired highlighted once it has.
        """
        fired, last = self.fired_node, self.last_node
        small = Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb)
        x = int(fired.x + 40)
        cv2.arrowedLine(frame, (x, int(fired.bottom)), (x, int(fired.bottom) + 36), Ink.HAIRLINE.rgb, 2, cv2.LINE_AA, tipLength=0.3)
        frame = small.written(frame, ELSE_BRANCH, (x + 14, fired.bottom + 18), Anchor.LEFT_MIDDLE)
        frame = Typesetting(size=BODY_SIZE, color=Ink.MUTED.rgb).written(frame, ELLIPSIS, (x, (fired.bottom + last.y) / 2 + 8), Anchor.CENTRE_MIDDLE)
        cv2.arrowedLine(frame, (x, int(last.y) - 36), (x, int(last.y)), Ink.HAIRLINE.rgb, 2, cv2.LINE_AA, tipLength=0.3)
        frame = self._node(frame, fired, self.fired, highlighted=done)
        frame = self._node(frame, last, self.last, highlighted=False)
        if arrived:
            frame = self._case(frame)
        return frame

    def _node(self, frame: Frame, node: Area, rule: TracedRule, highlighted: bool) -> Frame:
        """
        One rule: its condition over its conclusion; framed in the accent once it has
        fired.
        """
        stroke = Ink.ANSWER.rgb if highlighted else Ink.HAIRLINE.rgb
        divider = node.y + node.height * 0.5
        frame = filled(frame, node, Ink.BUBBLE.rgb)
        cv2.line(frame, (int(node.x), int(divider)), (int(node.right), int(divider)), stroke, 1, cv2.LINE_AA)
        frame = framed(frame, node, stroke, thickness=3)
        frame = Typesetting(size=RULE_SIZE, face=Face.BOLD, color=Ink.TEXT.rgb).written(
            frame, f"if {rule.condition}", (node.x + 16, (node.y + divider) / 2), Anchor.LEFT_MIDDLE
        )
        return Typesetting(size=RULE_SIZE, face=Face.BOLD if highlighted else Face.REGULAR, color=Ink.TEXT.rgb).written(
            frame, f"then {rule.conclusion}", (node.x + 16, (divider + node.bottom) / 2), Anchor.LEFT_MIDDLE
        )

    def _case(self, frame: Frame) -> Frame:
        """
        The case the rules are run on, written above the first rule with a pointer into
        it.
        """
        chip, first = self.case_chip, self.fired_node
        piece = self.trace.piece
        frame = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.TEXT.rgb).written(
            frame,
            f"case: {piece.name.name}  ·  shape_category = {piece.shape_category.name}",
            (chip.x + 16, chip.centre[1]),
            Anchor.LEFT_MIDDLE,
        )
        cv2.arrowedLine(frame, (int(first.x + 40), int(chip.bottom)), (int(first.x + 40), int(first.y)), Ink.TEXT.rgb, 2, cv2.LINE_AA, tipLength=0.4)
        return frame
