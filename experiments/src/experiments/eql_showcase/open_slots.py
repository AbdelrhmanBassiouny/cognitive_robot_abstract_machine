"""
Who answers each part a sorting plan leaves open, before the robot moves.

A plan says what it wants and leaves open what it does not know: the piece to pick up,
whether it still rests on the table, which side the hand takes it from, which arm does
it and which hole the piece goes into. Each of those is a statement in the entity query
language, and each is answered by a different faculty of the robot -- what the camera
saw, what the twin holds, what the rules about the board say, and what a probabilistic
model of grasping prefers. Every backend declares what it can answer, and
:class:`OpenSlotAnswerer` hands a statement to the first that declares it can, keeping
what each answered and the reasoning that led to it.
"""

from __future__ import annotations

import base64
import enum
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np
from typing_extensions import Any, Callable, Dict, Iterable, List, Type

from coraplex.querying.predicates import GripperIsFree
from cramera.knowledge.entity import NamedEntity
from experiments.eql_showcase.exceptions import NoBackendAnswers
from experiments.eql_showcase.perceived_twin import PerceivedTwin, SeenHole, SeenPiece
from experiments.montessori.perception.overlay import RectifiedView
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import BOARD_SCALE, _HOLE_FOOTPRINTS
from krrood.entity_query_language.backends import (
    ProbabilisticBackend,
    QueryBackend,
    SelectiveBackend,
)
from krrood.entity_query_language.factories import (
    a,
    add,
    alternative,
    an,
    deduced_variable,
    entity,
    inference,
    variable,
)
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query_observation import QueryObservation
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.ormatic.utils import classproperty
from krrood.parametrization.model_registries import ModelRegistry
from krrood.parametrization.parameterizer import ModelQueryParameters
from probabilistic_model.distributions.distributions import SymbolicDistribution
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
    ProductUnit,
    leaf,
)
from probabilistic_model.utils import MissingDict
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.reasoning.predicates import SupportedBy
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types import RotationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body, WorldEntity

# %% what answered


class Faculty(StrEnum):
    """
    The kind of knowledge a backend answers from.
    """

    PERCEPTION = "perception"
    """
    What the camera saw.
    """

    WORKING_MEMORY = "working memory"
    """
    What the twin holds now, relations read off its geometry.
    """

    RULES = "rules"
    """
    Ripple-down rules stated about the board.
    """

    PROBABILISTIC = "probabilistic"
    """
    A probabilistic model, sampled most likely first.
    """


class SlotMarker(StrEnum):
    """
    The brackets a line of a stated plan marks an open part with, around the part's id.
    """

    OPEN = "⟦"
    CLOSE = "⟧"

    @classmethod
    def around(cls, slot_id: str) -> str:
        """
        :param slot_id: The id of an open part.
        :return: The marker standing for the part in a line.
        """
        return f"{cls.OPEN}{slot_id}{cls.CLOSE}"


class ResolvedName(StrEnum):
    """
    The names a resolved statement's own answer goes by in its lines.
    """

    ANSWER = "answer"
    """
    What answers the statement as a whole.
    """


@dataclass
class Reasoning(ABC):
    """
    What a backend read and weighed to answer a statement, as it is shown to a person.
    """

    @abstractmethod
    def lines(self) -> List[str]:
        """
        :return: The reasoning, one line each.
        """

    @abstractmethod
    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The reasoning as JSON for the viewer to draw.
        """

    @abstractmethod
    def bodies(self) -> List[Body]:
        """
        :return: The bodies of the twin the reasoning is about, to be lit up in the
            scene.
        """

    def framed(self) -> List[Body]:
        """
        :return: The bodies the scene is framed on while the reasoning is shown.
        """
        return self.bodies()


@dataclass(eq=False)
class SlotAnswer(NamedEntity):
    """
    One statement a plan left open, the backend that answered it and its reasoning.

    Named after what the statement asks for and the plan it was left open in.
    """

    step: str = field(repr=False)
    """
    The plan the statement was left open in, e.g. ``"put the cylinder into its
    hole"``.
    """

    slot: str = field(repr=False)
    """
    What the statement asks for, e.g. ``"which side to take it from"``.
    """

    slot_id: str = field(repr=False)
    """
    The id the open part goes by in the lines of its stated plan.
    """

    statement: str = field(repr=False)
    """
    The statement, as English.
    """

    faculty: Faculty
    """
    The kind of knowledge that answered it.
    """

    backend: str = field(repr=False)
    """
    The name of the backend that answered it.
    """

    answers: List[str]
    """
    What it answered, most preferred first.
    """

    evidence: List[str]
    """
    The backend's reasoning, one line each.
    """

    reasoning: Reasoning = field(repr=False)
    """
    The backend's reasoning, as drawn for a person.
    """

    seconds: float = field(repr=False)
    """
    How long answering took.
    """

    answered_at: float = field(repr=False)
    """
    When it was answered, as seconds since the epoch.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The answer as JSON for the viewer.
        """
        return {
            "step": self.step,
            "slot": self.slot,
            "slotId": self.slot_id,
            "statement": self.statement,
            "faculty": self.faculty.value,
            "backend": self.backend,
            "answers": self.answers,
            "evidence": self.evidence,
            "reasoning": self.reasoning.to_payload(),
            "highlight": [str(body.name) for body in self.reasoning.bodies()],
            "frame": [str(body.name) for body in self.reasoning.framed()],
            "milliseconds": round(self.seconds * 1000, 1),
            "answeredAt": self.answered_at,
        }


# %% a statement or plan, as stated and as resolved


@dataclass
class CodeLine:
    """
    One line of a stated plan, whose open parts are marked with :class:`SlotMarker`.
    """

    text: str
    """
    The line, with each open part it holds marked by its id.
    """

    slot_id: str | None = None
    """
    The id of the open part the whole line states, or None.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The line as JSON for the viewer.
        """
        return {"text": self.text, "slot": self.slot_id}


@dataclass(eq=False)
class PlanResolution(NamedEntity):
    """
    A plan or statement with parts left open, resolved by the backends before anything
    is carried out.
    """

    underspecified: List[CodeLine] = field(repr=False)
    """
    The plan as stated, its open parts marked.
    """

    resolved: List[CodeLine] = field(repr=False)
    """
    The plan as it is carried out, each open part marked where its answer goes.
    """

    executable: bool = field(repr=False, default=False)
    """
    Whether the resolved plan is something the robot can be told to do.
    """

    parts: List[SlotAnswer] = field(default_factory=list)
    """
    Every open part answered, in the order it was answered.
    """

    plan: Any = field(default=None, repr=False)
    """
    The resolved plan the robot can be told to carry out, or None.
    """

    done: bool = field(default=False, repr=False)
    """
    Whether every part that can be answered has been.
    """

    def to_payload(self, index: int) -> Dict[str, Any]:
        """
        :param index: The resolution's place among all resolutions so far.
        :return: The resolution as JSON for the viewer.
        """
        return {
            "id": index,
            "title": self.name,
            "executable": self.executable,
            "done": self.done,
            "underspecified": [line.to_payload() for line in self.underspecified],
            "resolved": [line.to_payload() for line in self.resolved],
            "parts": [part.to_payload() for part in self.parts],
        }


# %% the backends


@dataclass
class BackendAnswer:
    """
    What a backend answered to a statement and how it reasoned.
    """

    answers: List[Any]
    """
    What it answered, most preferred first.
    """

    reasoning: Reasoning
    """
    How it reasoned.
    """


@dataclass
class SlotBackend(QueryBackend, ABC):
    """
    A backend that declares which statements it can answer and shows how it reasoned
    to answer one.
    """

    @classproperty
    @abstractmethod
    def faculty(cls) -> Faculty:
        """
        The kind of knowledge this backend answers from.
        """

    @abstractmethod
    def can_answer(self, statement: Match) -> bool:
        """
        :param statement: The statement to answer.
        :return: Whether this backend can answer it.
        """

    @abstractmethod
    def reasoning_for(self, statement: Match, answers: List[Any]) -> Reasoning:
        """
        :param statement: The statement answered.
        :param answers: What this backend answered.
        :return: How it reasoned to answer it.
        """

    def resolve(self, statement: Match) -> BackendAnswer:
        """
        :param statement: The statement to answer.
        :return: What this backend answers to it, and how it reasoned.
        """
        answers = self.distinct(statement.evaluate(backend=self))
        # the reasoning is drawn for a person; the robot asks nothing to draw it
        with QueryObservation().unobserved():
            return BackendAnswer(answers, self.reasoning_for(statement, answers))

    @staticmethod
    def distinct(answers: Iterable[Any]) -> List[Any]:
        """
        :param answers: Answers, the same one possibly given more than once.
        :return: Each answer once, in the order first given.
        """
        given: Dict[int, Any] = {}
        for answer in answers:
            given.setdefault(id(answer), answer)
        return list(given.values())


# %% perception


@dataclass
class SightingReading:
    """
    One piece the camera saw, as perception weighs it against a statement.
    """

    piece: SeenPiece
    """
    The piece.
    """

    outline_agreement: float
    """
    How well the piece's outline fits what the camera saw, one being a perfect fit.
    """

    selected: bool
    """
    Whether it answers the statement.
    """


@dataclass
class PerceptionReasoning(Reasoning):
    """
    The pieces the camera saw, those that answer drawn onto the camera's top-down view
    of the table.
    """

    readings: List[SightingReading]
    """
    Every piece the camera saw, and whether it answers.
    """

    table_view: str
    """
    The camera's top-down view of the table, as a data URL, or empty without one.
    """

    found_view: str
    """
    The same view with the pieces outlined, as a data URL, or empty without one.
    """

    def lines(self) -> List[str]:
        return [
            f"{'✓' if reading.selected else '✗'} {reading.piece.name.name} · "
            f"outline fits {reading.outline_agreement:.0%}"
            for reading in self.readings
        ] or ["nothing was seen"]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "kind": Faculty.PERCEPTION.value,
            "tableView": self.table_view,
            "foundView": self.found_view,
            "pieces": [
                {
                    "name": reading.piece.name.name,
                    "kind": PerceivedTwin.kind_of(reading.piece.kind),
                    "fit": round(reading.outline_agreement, 3),
                    "selected": reading.selected,
                }
                for reading in self.readings
            ],
        }

    def bodies(self) -> List[Body]:
        return [reading.piece.root for reading in self.readings if reading.selected]


class OutlineColor(enum.Enum):
    """
    The colours pieces are outlined in on the camera's view, as blue, green and red.
    """

    SELECTED = (200, 213, 57)
    """
    A piece that answers.
    """

    OTHER = (150, 150, 150)
    """
    A piece that does not.
    """


@dataclass
class TableViewDrawing:
    """
    Draws pieces the camera saw onto its top-down view of the table.
    """

    view: RectifiedView
    """
    The camera's top-down view of the table.
    """

    width: int = 420
    """
    How wide a drawn view is, in pixels.
    """

    jpeg_quality: int = 82
    """
    The quality a drawn view is compressed at, out of a hundred.
    """

    def plain(self) -> str:
        """
        :return: The view as it is, as a data URL.
        """
        return self.data_url(self.view.to_image())

    def outlined(self, readings: List[SightingReading], twin: PerceivedTwin) -> str:
        """
        :param readings: The pieces to outline.
        :param twin: The twin keeping what each piece was seen as.
        :return: The view with the pieces outlined, as a data URL.
        """
        image = self.view.to_image()
        for reading in readings:
            sighting = twin.sightings[reading.piece]
            outline = self.view.to_pixels(sighting.outline, sighting.top_height)
            color = OutlineColor.SELECTED if reading.selected else OutlineColor.OTHER
            cv2.polylines(
                image,
                [outline.astype(np.int32).reshape(-1, 1, 2)],
                isClosed=True,
                color=color.value,
                thickness=5 if reading.selected else 2,
                lineType=cv2.LINE_AA,
            )
        return self.data_url(image)

    def data_url(self, image: np.ndarray) -> str:
        """
        :param image: An image, as blue, green and red.
        :return: The part of the image the camera saw, scaled to :attr:`width`, as a
            JPEG data URL.
        """
        rows, columns = np.nonzero(image.any(axis=2))
        image = image[rows.min() : rows.max() + 1, columns.min() : columns.max() + 1]
        scale = self.width / image.shape[1]
        scaled = cv2.resize(
            image, (self.width, round(image.shape[0] * scale)), cv2.INTER_AREA
        )
        _, encoded = cv2.imencode(
            ".jpg", scaled, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")


@dataclass(eq=False)
class PerceptionBackend(SelectiveBackend, SlotBackend):
    """
    Answers which pieces of a kind there are from what the last look at the scene saw.
    """

    twin: PerceivedTwin = field(repr=False)
    """
    The twin the look was committed into, which keeps what each piece was seen as.
    """

    view: RectifiedView | None = field(default=None, repr=False)
    """
    The camera's top-down view of the table in the last look, or None.
    """

    @classproperty
    def faculty(cls) -> Faculty:
        return Faculty.PERCEPTION

    def can_answer(self, statement: Match) -> bool:
        """
        A statement about a seen piece that states no relation: what was seen is all
        a look reports.
        """
        return statement._type_ is SeenPiece and not statement._where_conditions_

    def _evaluate(self, expression: Match) -> Iterable[SeenPiece]:
        yield from expression.from_(list(self.twin.sightings))._evaluate_natively_()

    def reasoning_for(self, statement: Match, answers: List[Any]) -> Reasoning:
        readings = [
            SightingReading(piece, sighting.outline_agreement, piece in answers)
            for piece, sighting in self.twin.sightings.items()
        ]
        if self.view is None:
            return PerceptionReasoning(readings, "", "")
        drawing = TableViewDrawing(self.view)
        return PerceptionReasoning(
            readings, drawing.plain(), drawing.outlined(readings, self.twin)
        )


# %% working memory


@dataclass
class ContactReading:
    """
    One thing of the twin a statement ranged over, and what its geometry says.
    """

    thing: Any
    """
    The thing.
    """

    selected: bool
    """
    Whether it answers the statement.
    """

    relation: str
    """
    What the twin says about it, e.g. ``"box on table · 0.0 mm"``.
    """

    support: Body | None = None
    """
    What its collision box rests on, if it is a piece.
    """

    gap: float | None = None
    """
    How far its collision box is from its support's, in metres.
    """

    size: List[float] | None = None
    """
    The size of its collision box, in metres, if it is a piece.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The reading as JSON for the viewer.
        """
        return {
            "name": OpenSlotAnswerer.name_of(self.thing),
            "selected": self.selected,
            "relation": self.relation,
            "support": None if self.support is None else self.support.name.name,
            "gapMillimetres": None if self.gap is None else round(self.gap * 1000, 1),
            "size": self.size,
        }


@dataclass
class ContactReasoning(Reasoning):
    """
    The things of the twin a statement ranged over, each with what the twin's geometry
    says about it.
    """

    readings: List[ContactReading]
    """
    Every thing ranged over.
    """

    condition: str
    """
    The relation the statement asks for, as English, or empty for none.
    """

    def lines(self) -> List[str]:
        return [
            f"{'✓' if reading.selected else '✗'} "
            f"{OpenSlotAnswerer.name_of(reading.thing)} · {reading.relation}"
            for reading in self.readings
        ]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "kind": Faculty.WORKING_MEMORY.value,
            "condition": self.condition,
            "readings": [reading.to_payload() for reading in self.readings],
        }

    def bodies(self) -> List[Body]:
        bodies = []
        for reading in self.readings:
            if not reading.selected or not isinstance(reading.thing, SeenPiece):
                continue
            bodies.append(reading.thing.root)
            if reading.support is not None:
                bodies.append(reading.support)
        return bodies

    def framed(self) -> List[Body]:
        """
        The pieces alone, not what they rest on.
        """
        return [
            reading.thing.root
            for reading in self.readings
            if reading.selected and isinstance(reading.thing, SeenPiece)
        ]


@dataclass(eq=False)
class WorkingMemoryBackend(SelectiveBackend, SlotBackend):
    """
    Answers a statement about the things the twin holds by selecting among them, a
    relation between two of them read off their collision boxes in the twin.
    """

    world: World = field(repr=False)
    """
    The twin whose things answer.
    """

    contact_tolerance: float = 0.005
    """
    How far apart two collision boxes may be and still touch, in metres.
    """

    @classproperty
    def faculty(cls) -> Faculty:
        return Faculty.WORKING_MEMORY

    def can_answer(self, statement: Match) -> bool:
        """
        A statement about a kind of thing the twin holds.
        """
        return bool(self.things_of_the_kind_of(statement))

    def _evaluate(self, expression: Match) -> Iterable[Any]:
        if expression._domain_ is None:
            expression.from_(self.things_of_the_kind_of(expression))
        yield from expression._evaluate_natively_()

    def things_of_the_kind_of(self, statement: Match) -> List[WorldEntity]:
        """
        :param statement: The statement to read.
        :return: Everything the twin holds of the kind the statement is about.
        """
        if statement._type_ is None:
            return []
        thing = variable(
            statement._type_,
            [
                *self.world.kinematic_structure_entities,
                *self.world.semantic_annotations,
            ],
        )
        return an(entity(thing)).tolist()

    def reasoning_for(self, statement: Match, answers: List[Any]) -> Reasoning:
        considered = statement._domain_ or self.things_of_the_kind_of(statement)
        return ContactReasoning(
            [self.reading_of(thing, thing in answers) for thing in considered],
            "; ".join(
                verbalize_expression(condition)
                for condition in statement._where_conditions_
            ),
        )

    def reading_of(self, thing: Any, selected: bool) -> ContactReading:
        """
        :param thing: A thing the statement ranged over.
        :param selected: Whether it was selected.
        :return: What the twin's geometry says about it.
        """
        if isinstance(thing, Arm):
            free = GripperIsFree(thing.end_effector)()
            return ContactReading(
                thing, selected, "gripper free" if free else "gripper holds something"
            )
        if not isinstance(thing, SeenPiece):
            return ContactReading(thing, selected, "held in the twin")
        root = thing.root
        [box] = root.collision.shapes
        size = [
            round(float(value), 4) for value in (box.scale.x, box.scale.y, box.scale.z)
        ]
        body = variable(Body, self.world.bodies_with_collision)
        support = next(
            an(
                entity(body).where(
                    SupportedBy(root, body, contact_tolerance=self.contact_tolerance)
                )
            ).evaluate(),
            None,
        )
        if support is None:
            return ContactReading(
                thing, selected, "its box rests on nothing", size=size
            )
        contact = self.world.collision_manager.collision_detector.check_collision_between_bodies(
            root, support, distance=self.contact_tolerance
        )
        gap = max(contact.distance, 0.0)
        return ContactReading(
            thing,
            selected,
            f"box on {support.name.name} · {gap * 1000:.1f} mm",
            support=support,
            gap=gap,
            size=size,
        )


# %% the rules about the board


@dataclass
class Insertion:
    """
    A piece and the hole it goes into.
    """

    piece: SeenPiece
    """
    The piece put into the hole.
    """

    hole: SeenHole
    """
    The hole it goes into.
    """


@dataclass
class HoleShape:
    """
    The kind of piece a hole is cut for, as the rules conclude it.
    """

    kind: Type[MontessoriShape]
    """
    The kind of piece the hole is cut for.
    """


@dataclass
class RuleReading:
    """
    One rule of the cascade, and how far evaluating the case got.
    """

    kind: Type[MontessoriShape]
    """
    The kind of piece the rule is stated for, and of hole it concludes.
    """

    tried: bool
    """
    Whether the case reached the rule.
    """

    fired: bool
    """
    Whether the rule's condition held for the case.
    """


@dataclass
class RuleReasoning(Reasoning):
    """
    The ripple-down rules evaluated on a piece, the one that fired, and the holes of
    the board its conclusion selects.
    """

    piece: SeenPiece
    """
    The case the rules were evaluated on.
    """

    rules: List[RuleReading]
    """
    The rules in the order they are stated.
    """

    holes: List[SeenHole]
    """
    The holes the conclusion selects.
    """

    board: Body | None
    """
    The board the holes are cut into, or None.
    """

    def lines(self) -> List[str]:
        return [
            f"{'▶' if rule.fired else '·'} {'if' if index == 0 else 'else if'} "
            f"{PerceivedTwin.kind_of(rule.kind)} ⇒ "
            f"{PerceivedTwin.kind_of(rule.kind)} hole"
            for index, rule in enumerate(self.rules)
        ]

    def to_payload(self) -> Dict[str, Any]:
        concluded = {hole.kind for hole in self.holes}
        return {
            "kind": Faculty.RULES.value,
            "case": self.piece.name.name,
            "caseKind": self.piece.kind.__name__,
            "rules": [
                {
                    "condition": f"case.kind == {rule.kind.__name__}",
                    "conclusion": f"hole.kind = {rule.kind.__name__}",
                    "tried": rule.tried,
                    "fired": rule.fired,
                }
                for rule in self.rules
            ],
            "board": {
                "width": float(BOARD_SCALE.x),
                "length": float(BOARD_SCALE.y),
                "holes": [
                    {
                        "kind": PerceivedTwin.kind_of(footprint.category),
                        "center": [
                            round(float(value), 4)
                            for value in footprint.center.to_np()[:2]
                        ],
                        "points": [
                            [round(float(x), 4), round(float(y), 4)]
                            for x, y in np.asarray(footprint.boundary.vertices)[:, :2]
                            + footprint.center.to_np()[:2]
                        ],
                        "chosen": footprint.category in concluded,
                    }
                    for footprint in _HOLE_FOOTPRINTS
                ],
            },
            "holes": [hole.region.name.name for hole in self.holes],
        }

    def bodies(self) -> List[Body]:
        return ([] if self.board is None else [self.board]) + [self.piece.root]


@dataclass(eq=False)
class HoleRulesBackend(SlotBackend):
    """
    Answers which hole a piece goes into: ripple-down rules stated over the piece
    conclude the kind of hole, and the board's holes of that kind are selected.
    """

    twin: PerceivedTwin = field(repr=False)
    """
    The twin whose board holds the holes.
    """

    rule_order: List[Type[MontessoriShape]] = field(default_factory=list)
    """
    The kinds of piece the rules are stated for, in the order they are stated.
    """

    @classproperty
    def faculty(cls) -> Faculty:
        return Faculty.RULES

    def can_answer(self, statement: Match) -> bool:
        """
        A statement about an insertion whose hole it leaves open.
        """
        return statement._type_ is Insertion and statement._kwargs_.get("hole") is ...

    def evaluate(self, expression: Match) -> Iterable[Insertion]:
        piece = expression._kwargs_["piece"]
        kind = self.concluded_kind(piece)
        hole = variable(SeenHole, self.twin.holes)
        for found in an(entity(hole).where(hole.kind == kind)).evaluate():
            yield Insertion(piece=piece, hole=found)

    def concluded_kind(self, piece: SeenPiece) -> Type[MontessoriShape] | None:
        """
        :param piece: The piece being sorted.
        :return: The kind of hole the rules conclude it goes into, or None where no
            rule reaches it.
        """
        case = variable(SeenPiece, domain=[piece])
        concluded = deduced_variable(HoleShape)
        [first, *rest] = self.rule_order
        rules = an(entity(concluded).where(case.kind == first))
        with rules:
            add(concluded, inference(HoleShape)(kind=first))
            for kind in rest:
                with alternative(case.kind == kind):
                    add(concluded, inference(HoleShape)(kind=kind))
        shape = next(iter(rules.evaluate()), None)
        return None if shape is None else shape.kind

    def reasoning_for(self, statement: Match, answers: List[Any]) -> Reasoning:
        piece = statement._kwargs_["piece"]
        kind = self.concluded_kind(piece)
        fired_at = (
            self.rule_order.index(kind)
            if kind in self.rule_order
            else len(self.rule_order)
        )
        return RuleReasoning(
            piece,
            [
                RuleReading(rule_kind, index <= fired_at, index == fired_at)
                for index, rule_kind in enumerate(self.rule_order)
            ],
            [insertion.hole for insertion in answers],
            self.twin.board,
        )


# %% how the hand takes hold of a piece


class GraspSide(enum.IntEnum):
    """
    The side of a piece the hand, coming down from above, closes its fingers from, as
    the turn about the piece's upright axis in degrees.
    """

    FRONT = 0
    LEFT = 90
    BACK = 180
    RIGHT = 270


@dataclass
class SideGrasp:
    """
    The side of a piece the hand takes it from.
    """

    side: GraspSide
    """
    The side the hand closes from.
    """

    piece: SeenPiece | None = None
    """
    The piece taken hold of, or None for a side not yet given a piece.
    """

    height_above_center: float = 0.008
    """
    How far above the piece's centre the fingers close, in metres, so that their tips
    stay clear of what the piece rests on.
    """

    def candidate_on(self, piece: SeenPiece) -> GraspCandidate:
        """
        :param piece: The piece to take hold of.
        :return: The grasp coming down onto the piece from above, turned to this side.
        """
        return GraspCandidate(
            piece,
            Pose(
                position=Point3(
                    0.0, 0.0, self.height_above_center, reference_frame=piece.root
                ),
                orientation=RotationMatrix.from_rpy(
                    pitch=np.pi / 2, yaw=np.radians(self.side.value)
                ).quaternion,
                reference_frame=piece.root,
            ),
        )


@dataclass
class GraspSideModel(ModelRegistry):
    """
    A distribution over the sides a piece is taken from, weighting each side by how
    narrow the piece is between the fingers there.
    """

    piece: SeenPiece
    """
    The piece to be taken hold of.
    """

    def weights(self) -> Dict[GraspSide, float]:
        """
        :return: The probability of each side.
        """
        [box] = self.piece.root.collision.shapes
        span = {
            side: box.scale.y if side.value % 180 == 0 else box.scale.x
            for side in GraspSide
        }
        total = sum(1 / width for width in span.values())
        return {side: (1 / width) / total for side, width in span.items()}

    def get_model(self, parameters: ModelQueryParameters) -> ProbabilisticCircuit:
        [side_variable] = parameters.variables.values()
        weights = self.weights()
        circuit = ProbabilisticCircuit()
        root = ProductUnit(probabilistic_circuit=circuit)
        root.add_subcircuit(
            leaf(
                SymbolicDistribution(
                    variable=side_variable,
                    probabilities=MissingDict(
                        float,
                        {
                            hash(element): weights[GraspSide(element.element)]
                            for element in side_variable.domain.simple_sets
                        },
                    ),
                ),
                circuit,
            )
        )
        return circuit


@dataclass
class SamplingReasoning(Reasoning):
    """
    The distribution over the sides a piece is taken from, and the sides drawn from it.
    """

    piece: SeenPiece
    """
    The piece to be taken hold of.
    """

    probabilities: Dict[GraspSide, float]
    """
    The probability of each side.
    """

    samples: List[GraspSide]
    """
    The sides drawn, in the order they were drawn.
    """

    def lines(self) -> List[str]:
        return [
            f"P({side.name.lower()}) = {probability:.2f}"
            for side, probability in sorted(
                self.probabilities.items(), key=lambda item: -item[1]
            )
        ]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "kind": Faculty.PROBABILISTIC.value,
            "piece": self.piece.name.name,
            "prior": [
                {"side": side.name, "probability": round(probability, 3)}
                for side, probability in self.probabilities.items()
            ],
            "samples": [side.name for side in self.samples],
        }

    def bodies(self) -> List[Body]:
        return [self.piece.root]


@dataclass(eq=False)
class GraspSamplingBackend(SlotBackend):
    """
    Answers which side to take a piece from by sampling a probabilistic model of
    grasping, most likely side first.
    """

    number_of_samples: int = 24
    """
    How many sides are sampled before the distinct ones are ranked.
    """

    @classproperty
    def faculty(cls) -> Faculty:
        return Faculty.PROBABILISTIC

    def can_answer(self, statement: Match) -> bool:
        """
        A statement about the side a piece is taken from.
        """
        return statement._type_ is SideGrasp

    def model_for(self, statement: Match) -> GraspSideModel:
        """
        :param statement: The statement to answer.
        :return: The model of the piece the statement is about.
        """
        return GraspSideModel(piece=statement._kwargs_["piece"])

    def sample(self, model: GraspSideModel) -> List[GraspSide]:
        """
        :param model: The model to sample.
        :return: The sides drawn, in the order they were drawn.
        """
        return [
            grasp.side
            for grasp in an(SideGrasp)(side=...).evaluate(
                backend=ProbabilisticBackend(
                    model_registry=model, number_of_samples=self.number_of_samples
                )
            )
        ]

    @staticmethod
    def ranked(model: GraspSideModel, samples: List[GraspSide]) -> List[SideGrasp]:
        """
        :param model: The model sampled.
        :param samples: The sides drawn.
        :return: Each side drawn once, most likely first.
        """
        weights = model.weights()
        return [
            SideGrasp(side=side, piece=model.piece)
            for side in sorted(set(samples), key=lambda side: -weights[side])
        ]

    def evaluate(self, expression: Match) -> Iterable[SideGrasp]:
        model = self.model_for(expression)
        yield from self.ranked(model, self.sample(model))

    def resolve(self, statement: Match) -> BackendAnswer:
        """
        Keeps the sides drawn as the reasoning.
        """
        model = self.model_for(statement)
        samples = self.sample(model)
        return BackendAnswer(
            self.ranked(model, samples),
            SamplingReasoning(model.piece, model.weights(), samples),
        )

    def reasoning_for(self, statement: Match, answers: List[Any]) -> Reasoning:
        model = self.model_for(statement)
        return SamplingReasoning(
            model.piece, model.weights(), [answer.side for answer in answers]
        )


# %% choosing who answers


@dataclass
class OpenSlotAnswerer:
    """
    Hands each statement a plan left open to the first backend that declares it can
    answer it, and keeps every resolution and answer.
    """

    backends: List[SlotBackend]
    """
    The backends to choose from, in the order they are preferred.
    """

    answered: List[SlotAnswer] = field(default_factory=list)
    """
    Every statement answered, in the order it was answered.
    """

    resolutions: List[PlanResolution] = field(default_factory=list)
    """
    Every plan or statement resolved, in the order it was resolved.
    """

    on_answer: Callable[[OpenSlotAnswerer], None] | None = None
    """
    Called after every statement answered.
    """

    def begin(
        self,
        title: str,
        underspecified: List[CodeLine],
        resolved: List[CodeLine],
        executable: bool = False,
    ) -> PlanResolution:
        """
        Start resolving a plan or statement.

        :param title: What the plan is, as said to a person.
        :param underspecified: The plan as stated, its open parts marked.
        :param resolved: The plan as carried out, each open part marked.
        :param executable: Whether the robot can be told to carry the plan out.
        :return: The resolution, whose parts are answered through :meth:`answer`.
        """
        resolution = PlanResolution(
            name=title,
            underspecified=underspecified,
            resolved=resolved,
            executable=executable,
        )
        self.resolutions.append(resolution)
        return resolution

    def answer(
        self, resolution: PlanResolution, slot_id: str, slot: str, statement: Match
    ) -> List[Any]:
        """
        Answer one open part of a plan being resolved and keep the answer.

        :param resolution: The resolution the part belongs to.
        :param slot_id: The id the part goes by in the plan's lines.
        :param slot: What the part asks for.
        :param statement: The statement the part is.
        :return: What the chosen backend answered, most preferred first.
        :raises NoBackendAnswers: If no backend declares it can answer it.
        """
        backend = self.backend_for(statement)
        started = time.perf_counter()
        answer = backend.resolve(statement)
        seconds = time.perf_counter() - started
        part = SlotAnswer(
            name=f"{slot} · {resolution.name}",
            step=resolution.name,
            slot=slot,
            slot_id=slot_id,
            statement=verbalize_expression(statement, backend=backend),
            faculty=backend.faculty,
            backend=type(backend).__name__,
            answers=[self.name_of(value) for value in answer.answers],
            evidence=answer.reasoning.lines(),
            reasoning=answer.reasoning,
            seconds=seconds,
            answered_at=time.time(),
        )
        resolution.parts.append(part)
        self.answered.append(part)
        if self.on_answer is not None:
            self.on_answer(self)
        return answer.answers

    def finish(self, resolution: PlanResolution) -> None:
        """
        Mark a resolution as complete and tell whoever listens.

        :param resolution: The resolution, every part it can answer answered.
        """
        resolution.done = True
        if self.on_answer is not None:
            self.on_answer(self)

    def answer_with_conditions(
        self, resolution: PlanResolution, slot_id: str, slot: str, statement: Match
    ) -> List[Any]:
        """
        Answer a statement that states relations in two parts: what there is of its
        kind, then which of those hold the relations.

        :param resolution: The resolution the parts belong to.
        :param slot_id: The id the part goes by; its relations go by it followed by
            ``-where``.
        :param slot: What the part asks for.
        :param statement: The statement, with its relations.
        :return: What answers the whole statement, most preferred first.
        """
        # a statement nested in another is answered as one of its own
        there_are = self.answer(
            resolution, slot_id, slot, a(statement._type_)(**statement._kwargs_)
        )
        if not statement._where_conditions_:
            return there_are
        statement.from_(there_are)
        return self.answer(
            resolution,
            f"{slot_id}-where",
            "which of them hold the relations",
            statement,
        )

    def resolve(self, statement: Match) -> List[Any]:
        """
        Resolve any statement with parts left open, each statement nested in it first,
        and show how in the viewer.

        :param statement: The statement.
        :return: What answers it, most preferred first.
        """
        nested = {
            name: value
            for name, value in statement._kwargs_.items()
            if isinstance(value, Match)
        }
        underspecified = [
            CodeLine(f"{name} = {self.code_of(value)}", slot_id=name)
            for name, value in nested.items()
        ]
        underspecified.append(
            CodeLine(
                self.code_of_call(
                    statement, {**statement._kwargs_, **{name: name for name in nested}}
                ),
                slot_id=ResolvedName.ANSWER,
            )
        )
        resolved = [
            CodeLine(f"{name} = {SlotMarker.around(name)}") for name in nested
        ] + [
            CodeLine(
                f"{ResolvedName.ANSWER} = {SlotMarker.around(ResolvedName.ANSWER)}"
            )
        ]
        resolution = self.begin(
            verbalize_expression(statement), underspecified, resolved
        )
        answers = self._answer_nested(resolution, statement, nested)
        self.finish(resolution)
        return answers

    def _answer_nested(
        self, resolution: PlanResolution, statement: Match, nested: Dict[str, Match]
    ) -> List[Any]:
        """
        :param resolution: The resolution the parts are answered in.
        :param statement: The statement.
        :param nested: The statements nested in it, by the argument each is.
        :return: What answers the statement once each nested statement is answered by
            its most preferred answer, or nothing as soon as one has no answer.
        """
        concrete = dict(statement._kwargs_)
        for name, value in nested.items():
            answers = self.answer_with_conditions(
                resolution, name, f"which {name}", value
            )
            if not answers:
                return []
            concrete[name] = answers[0]
        answered = a(statement._type_)(**concrete)
        for condition in statement._where_conditions_:
            answered.where(condition)
        return self.answer_with_conditions(
            resolution, ResolvedName.ANSWER, "the answer", answered
        )

    def code_of(self, statement: Match) -> str:
        """
        :param statement: A statement.
        :return: The statement, written the way it is stated in a query.
        """
        return self.code_of_call(statement, statement._kwargs_)

    def code_of_call(self, statement: Match, arguments: Dict[str, Any]) -> str:
        """
        :param statement: A statement.
        :param arguments: Its arguments, each a value or the name it is written as.
        :return: The statement with those arguments, written the way it is stated in a
            query.
        """
        type_name = statement._type_.__name__
        article = "an" if type_name[0].lower() in "aeiou" else "a"
        written = ", ".join(
            f"{name}={self.code_of_value(value)}" for name, value in arguments.items()
        )
        conditions = "".join(
            f".where({verbalize_expression(condition)})"
            for condition in statement._where_conditions_
        )
        return f"{article}({type_name})({written}){conditions}"

    def code_of_value(self, value: Any) -> str:
        """
        :param value: An argument of a statement.
        :return: The argument, written the way it is stated in a query.
        """
        if value is ...:
            return "..."
        if isinstance(value, str):
            return value
        if isinstance(value, Match):
            return self.code_of(value)
        if isinstance(value, type):
            return value.__name__
        return self.name_of(value)

    def backend_for(self, statement: Match) -> SlotBackend:
        """
        :param statement: The statement to answer.
        :return: The first backend that declares it can answer it.
        :raises NoBackendAnswers: If none does.
        """
        for backend in self.backends:
            if backend.can_answer(statement):
                return backend
        raise NoBackendAnswers(statement=statement)

    @staticmethod
    def name_of(answer: Any) -> str:
        """
        :param answer: One answer.
        :return: How it is named to a person.
        """
        if isinstance(answer, Insertion):
            return answer.hole.region.name.name
        if isinstance(answer, SeenHole):
            return answer.region.name.name
        if isinstance(answer, HoleShape):
            return f"{answer.kind.__name__} hole"
        if isinstance(answer, SideGrasp):
            return answer.side.name
        if isinstance(answer, enum.Enum):
            return answer.name
        return answer.name.name if hasattr(answer, "name") else str(answer)

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: Every resolution so far, and the backends there are, as JSON for the
            viewer.
        """
        return {
            "backends": [
                {"faculty": backend.faculty.value, "name": type(backend).__name__}
                for backend in self.backends
            ],
            "resolutions": [
                resolution.to_payload(index)
                for index, resolution in enumerate(self.resolutions)
            ],
        }
