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

EVALUATING_INK: Tuple[Rgb, Rgb] = ((0xD9, 0x77, 0x06), (0xFE, 0xF3, 0xC7))
"""
The stroke and fill of a rule while its condition is being checked.
"""

STATUS_WORD: Dict[RuleStatus, str] = {
    RuleStatus.FIRED: "holds → fired",
    RuleStatus.EVALUATED_NOT_FIRED: "does not hold",
    RuleStatus.NOT_EVALUATED: "not reached",
}
"""
What is written beside a rule once the case has reached it.
"""

ELSE_BRANCH = "else"
"""
What the branch to the next rule is called: taken when the condition does not hold.
"""

EXCEPT_BRANCH = "except"
"""
What the branch hanging off a rule that fired is called: where a rule correcting it
would be added, and empty while none has been.
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
    The rule tree drawn as ripple-down rules, the case arriving, each rule coloured as
    the trace says, and the concluded hole ringed on the board.

    Every rule is one node with its condition over its conclusion. Two branches leave
    it: ``else`` downward, to the rule tried when the condition does not hold, and
    ``except`` to the side, where a rule correcting this one would hang once an expert
    adds it. The case walks the ``else`` branches until a condition holds, and that
    rule's conclusion is the answer.
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

    checking_share: float = 0.4
    """
    The share of :attr:`rule_every` a rule is shown being checked before its outcome
    shows.
    """

    answer_for: float = 5.0
    """
    Seconds the conclusion is shown at the end.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the scene draws itself at.
    """

    tree_area: Area = field(default_factory=lambda: Area(120, 150, 660, 660))
    """
    Where the nodes stand, from the first node's top edge to the last node's bottom.
    """

    @property
    def duration(self) -> float:
        return self.tree_for + self.rule_every * len(self.trace.evaluation_order) + self.answer_for

    @property
    def evaluation_ends(self) -> float:
        """
        Seconds into the scene the last rule has been evaluated.
        """
        return self.tree_for + self.rule_every * len(self.trace.evaluation_order)

    def evaluated_by(self, seconds: float) -> int:
        """
        How many rules have been evaluated by a moment.
        """
        if seconds < self.tree_for:
            return 0
        return min(int((seconds - self.tree_for) / self.rule_every) + 1, len(self.trace.evaluation_order))

    def checking_at(self, seconds: float) -> bool:
        """
        Whether, at a moment, the rule last reached is still being checked rather than
        settled.
        """
        if seconds < self.tree_for or seconds >= self.evaluation_ends:
            return False
        return (seconds - self.tree_for) % self.rule_every < self.rule_every * self.checking_share

    def node_area(self, index: int) -> Area:
        """
        Where one rule's node stands.

        :param index: The rule's place in the tree's walk.
        """
        count = len(self.trace.traced)
        pitch = self.tree_area.height / count
        height = pitch * 0.72
        return Area(self.tree_area.x, self.tree_area.y + index * pitch, self.tree_area.width, height)

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        frame = Typesetting(size=26, face=Face.BOLD, color=Ink.RULES.rgb).written(
            frame, STATEMENT, (40, 40), Anchor.LEFT_MIDDLE
        )
        evaluated = self.evaluated_by(seconds)
        done = seconds >= self.evaluation_ends
        frame = self._tree(frame, evaluated, self.checking_at(seconds), done)
        concluded = self.trace.concluded if done else None
        weight = eased((seconds - self.evaluation_ends) / 0.8) if done else 0.0
        frame = fitted(frame, self.board.drawn(concluded, weight), Area(900, 100, 660, 600))
        frame = Typesetting(size=22, color=Ink.MUTED.rgb).written(
            frame, "the board's holes on the robot's own picture", (1230, 730), Anchor.CENTRE_MIDDLE
        )
        caption = "the rule tree: one rule per shape the board sorts, read top down"
        if evaluated:
            caption = "the case walks the else branches until a condition holds"
        if done:
            caption = f"concluded: hole.shape_category = {self.trace.concluded.value.upper()}"
        colour = Ink.FIRED.rgb if done else Ink.TEXT.rgb
        return Typesetting(size=28, face=Face.BOLD if done else Face.REGULAR, color=colour).written(
            frame, caption, (self.resolution.width / 2, self.resolution.height - 40), Anchor.CENTRE_MIDDLE
        )

    def _tree(self, frame: Frame, evaluated: int, checking: bool, done: bool) -> Frame:
        """
        The nodes and their branches, coloured by how far the case has got.

        :param frame: What to draw on.
        :param evaluated: How many rules the case has reached.
        :param checking: Whether the last rule reached is still being checked.
        :param done: Whether the evaluation has ended.
        """
        reached = self.trace.evaluation_order[:evaluated]
        frame = self._branches(frame, reached, done)
        for index, rule in enumerate(self.trace.traced):
            status = rule.status if index in reached else RuleStatus.NOT_EVALUATED
            being_checked = checking and reached and index == reached[-1]
            frame = self._node(frame, index, rule, status, being_checked)
        if evaluated:
            frame = self._case(frame)
        return frame

    def _branches(self, frame: Frame, reached: List[int], done: bool) -> Frame:
        """
        The else branch from each rule to the next and the except branch off its side,
        with the branches the case walked drawn strong.
        """
        small = Typesetting(size=18, color=Ink.MUTED.rgb)
        for index in range(len(self.trace.traced)):
            node = self.node_area(index)
            # the except branch: a stub off the side, ending where a correction would hang
            stub_y = int(node.y + node.height * 0.28)
            cv2.line(frame, (int(node.right), stub_y), (int(node.right) + 60, stub_y), Ink.HAIRLINE.rgb, 2, cv2.LINE_AA)
            cv2.circle(frame, (int(node.right) + 68, stub_y), 7, Ink.HAIRLINE.rgb, 2, cv2.LINE_AA)
            if index == 0:
                frame = small.written(frame, EXCEPT_BRANCH, (node.right + 84, stub_y), Anchor.LEFT_MIDDLE)
            if index + 1 == len(self.trace.traced):
                continue
            # the else branch: down the left to the next rule
            below = self.node_area(index + 1)
            x = int(node.x + 40)
            walked = index in reached and (index + 1) in reached
            colour = Ink.FIRED.rgb if walked else Ink.HAIRLINE.rgb
            cv2.arrowedLine(frame, (x, int(node.bottom)), (x, int(below.y)), colour, 3 if walked else 2, cv2.LINE_AA, tipLength=0.3)
            frame = small.written(frame, ELSE_BRANCH, (x - 14, (node.bottom + below.y) / 2), Anchor.RIGHT_MIDDLE)
        return frame

    def _node(self, frame: Frame, index: int, rule: TracedRule, status: RuleStatus, being_checked: bool) -> Frame:
        """
        One rule: its condition over its conclusion, coloured by its status.
        """
        node = self.node_area(index)
        stroke, fill = EVALUATING_INK if being_checked else STATUS_INK[status]
        reached = status is not RuleStatus.NOT_EVALUATED or being_checked
        text_colour = Ink.TEXT.rgb if reached else Ink.MUTED.rgb
        divider = node.y + node.height * 0.55
        frame = filled(frame, node, fill if status is RuleStatus.FIRED else Ink.PAPER.rgb)
        frame = filled(frame, Area(node.x, node.y, node.width, divider - node.y), fill)
        cv2.line(frame, (int(node.x), int(divider)), (int(node.right), int(divider)), stroke, 1, cv2.LINE_AA)
        frame = framed(frame, node, stroke, thickness=3)
        frame = Typesetting(size=21, face=Face.BOLD, color=text_colour).written(
            frame, f"if {rule.condition}", (node.x + 16, (node.y + divider) / 2), Anchor.LEFT_MIDDLE
        )
        frame = Typesetting(size=19, face=Face.BOLD if status is RuleStatus.FIRED else Face.REGULAR, color=text_colour).written(
            frame, f"then {rule.conclusion}", (node.x + 16, (divider + node.bottom) / 2), Anchor.LEFT_MIDDLE
        )
        word = "checking…" if being_checked else STATUS_WORD.get(status, "")
        if reached and word:
            frame = Typesetting(size=18, face=Face.BOLD, color=stroke).written(
                frame, word, (node.right - 14, (node.y + divider) / 2), Anchor.RIGHT_MIDDLE
            )
        return frame

    def _case(self, frame: Frame) -> Frame:
        """
        The case the rules are run on, written above the first rule with a pointer into
        it.
        """
        first = self.node_area(0)
        chip = Area(first.x, first.y - 62, first.width, 40)
        frame = filled(frame, chip, Ink.PERCEPTION_FILL.rgb)
        frame = framed(frame, chip, Ink.PERCEPTION.rgb, thickness=2)
        piece = self.trace.piece
        frame = Typesetting(size=20, face=Face.BOLD, color=Ink.TEXT.rgb).written(
            frame,
            f"case: {piece.name.name}  ·  shape_category = {piece.shape_category.name}",
            (chip.x + 16, chip.centre[1]),
            Anchor.LEFT_MIDDLE,
        )
        cv2.arrowedLine(frame, (int(first.x + 40), int(chip.bottom)), (int(first.x + 40), int(first.y)), Ink.FIRED.rgb, 3, cv2.LINE_AA, tipLength=0.4)
        return frame
