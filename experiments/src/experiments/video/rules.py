"""
The ripple-down rules concluding which hole the cube belongs in, watched being run.

The rule tree is drawn as it stands; the piece the look found arrives as the case; each
rule is coloured by what happened to it in that very classification -- fired, evaluated
but not holding, never reached -- read off the tree's own trace; and the hole the rules
concluded is pointed out on the robot's picture of the board.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import Dict, List, Optional, Tuple

from experiments.montessori.perception.overlay import project_to_pixels
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.open_slots.holes import HoleShapeRules, PieceToSort
from experiments.paper.lettering import Face
from experiments.video.canvas import (
    Anchor,
    Area,
    Ink,
    Rgb,
    Typesetting,
    filled,
    fitted,
    framed,
)
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, eased
from krrood.entity_query_language.rdr.rule_tree_view import (
    RuleStatus,
    RuleView,
    format_condition,
    format_conclusion,
    resolve_status,
    walk_rules,
)

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size the scene draws itself at.
"""

STATEMENT = "a(ShapeSortingHole)(shape_category=...).from_(board.apertures)"
"""
The open slot, as the plan writes it.
"""

STATUS_INK: Dict[RuleStatus, Tuple[Rgb, Rgb]] = {
    RuleStatus.FIRED: (Ink.FIRED.rgb, (0xDC, 0xFC, 0xE7)),
    RuleStatus.EVALUATED_NOT_FIRED: (Ink.FAILED.rgb, (0xFE, 0xE2, 0xE2)),
    RuleStatus.NOT_EVALUATED: (Ink.HAIRLINE.rgb, (0xF6, 0xF7, 0xF9)),
}
"""
The stroke and fill a rule is drawn in, by what happened to it.
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
                cv2.circle(overlay, tuple(pixel.round().astype(int)), pixels + 4, Ink.RULES.rgb, 4, cv2.LINE_AA)
                cv2.putText(
                    overlay, category.value, (int(pixel[0]) - 26, int(pixel[1]) - pixels - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, Ink.RULES.rgb, 2, cv2.LINE_AA,
                )
        cv2.addWeighted(overlay, weight, picture, 1 - weight, 0, picture)
        left, top, width, height = self.crop().rounded()
        left, top = max(left, 0), max(top, 0)
        return picture[top : top + height, left : left + width]


# %% the scene


@dataclass
class RuleTreeEvaluation(Scene):
    """
    The rule tree drawn, the case arriving, each rule coloured as the trace says, and
    the concluded hole ringed on the board.
    """

    trace: HoleRuleTrace
    """
    The rules, run.
    """

    board: HoleOnThePicture
    """
    The holes on the robot's picture.
    """

    tree_for: float = 2.5
    """
    Seconds the tree stands uncoloured with the statement before the case arrives.
    """

    rule_every: float = 1.2
    """
    Seconds between one rule being evaluated and the next.
    """

    answer_for: float = 5.0
    """
    Seconds the conclusion is shown at the end.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the scene draws itself at.
    """

    @property
    def duration(self) -> float:
        return self.tree_for + self.rule_every * len(self.trace.evaluation_order) + self.answer_for

    def evaluated_by(self, seconds: float) -> int:
        """
        How many rules have been evaluated by a moment.
        """
        if seconds < self.tree_for:
            return 0
        return min(int((seconds - self.tree_for) / self.rule_every) + 1, len(self.trace.evaluation_order))

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        frame = Typesetting(size=26, face=Face.BOLD, color=Ink.RULES.rgb).written(
            frame, STATEMENT, (40, 40), Anchor.LEFT_MIDDLE
        )
        evaluated = self.evaluated_by(seconds)
        done = evaluated == len(self.trace.evaluation_order)
        frame = self._tree(frame, evaluated)
        concluded = self.trace.concluded if done else None
        weight = eased((seconds - self.tree_for - self.rule_every * len(self.trace.evaluation_order) + self.rule_every) / 0.8) if done else 0.0
        frame = fitted(frame, self.board.drawn(concluded, weight), Area(900, 100, 660, 600))
        frame = Typesetting(size=22, color=Ink.MUTED.rgb).written(
            frame, "the board's holes on the robot's own picture", (1230, 730), Anchor.CENTRE_MIDDLE
        )
        caption = "the rule tree, one rule per shape the board sorts"
        if evaluated:
            caption = f"the case: {self.trace.piece.shape_category.value} piece · rules read top down until one fires"
        if done:
            caption = f"concluded: hole.shape_category = {self.trace.concluded.value.upper()}"
        colour = Ink.FIRED.rgb if done else Ink.TEXT.rgb
        return Typesetting(size=28, face=Face.BOLD if done else Face.REGULAR, color=colour).written(
            frame, caption, (self.resolution.width / 2, self.resolution.height - 40), Anchor.CENTRE_MIDDLE
        )

    def _tree(self, frame: Frame, evaluated: int) -> Frame:
        left, top, width = 60, 110, 780
        node_height, gap = 74, 18
        code = Typesetting(size=22, face=Face.BOLD)
        small = Typesetting(size=18, color=Ink.MUTED.rgb)
        reached = set(self.trace.evaluation_order[:evaluated])
        for index, rule in enumerate(self.trace.traced):
            status = rule.status if index in reached else RuleStatus.NOT_EVALUATED
            stroke, fill = STATUS_INK[status]
            node = Area(left + 40, top + index * (node_height + gap), width - 40, node_height)
            frame = filled(frame, node, fill)
            frame = framed(frame, node, stroke, thickness=3)
            text_colour = Ink.TEXT.rgb if index in reached else Ink.MUTED.rgb
            frame = Typesetting(size=22, face=Face.BOLD, color=text_colour).written(
                frame, f"if {rule.condition}", (node.x + 16, node.y + 26), Anchor.LEFT_MIDDLE
            )
            frame = Typesetting(size=20, color=text_colour).written(
                frame, f"→ {rule.conclusion}", (node.x + 16, node.y + 52), Anchor.LEFT_MIDDLE
            )
            if index > 0:
                frame = small.written(frame, rule.kind, (left, node.y + node_height / 2), Anchor.LEFT_MIDDLE)
            if index in reached:
                word = {RuleStatus.FIRED: "fired", RuleStatus.EVALUATED_NOT_FIRED: "did not hold"}.get(status, "")
                frame = Typesetting(size=20, face=Face.BOLD, color=stroke).written(
                    frame, word, (node.right - 16, node.y + node_height / 2), Anchor.RIGHT_MIDDLE
                )
        return frame
