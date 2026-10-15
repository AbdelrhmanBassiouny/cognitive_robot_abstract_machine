"""
Who answers each part a sorting plan leaves open.

A plan says what it wants and leaves open what it does not know: the piece to pick up,
whether it still rests on the table, which side the hand takes it from, which hole it
goes into and which arm does it. Each of those is a statement in the entity query
language, and each is answered by a different faculty of the robot -- what the camera
saw, what the twin holds, what the rules about the board say, and what a probabilistic
model of grasping prefers. Every backend declares what it can answer, and
:class:`OpenSlotAnswerer` hands a statement to the first that declares it can, keeping
what each answered and what it read to answer it.
"""

from __future__ import annotations

import contextvars
import enum
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
from typing_extensions import Any, Callable, Dict, Iterable, Iterator, List, Type

from experiments.eql_showcase.exceptions import NoBackendAnswers
from experiments.eql_showcase.perceived_twin import PerceivedTwin, SeenHole, SeenPiece
from experiments.montessori.perception.detections import MontessoriShapeDetection
from experiments.montessori.semantics import MontessoriShape
from krrood.entity_query_language.backends import (
    ProbabilisticBackend,
    QueryBackend,
    SelectiveBackend,
)
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.factories import (
    add,
    alternative,
    an,
    deduced_variable,
    entity,
    inference,
    variable,
)
from krrood.entity_query_language.query.match import Match
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
from semantic_digital_twin.spatial_types import RotationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
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


@dataclass
class SlotAnswer:
    """
    One statement a plan left open, the backend that answered it and what it read.
    """

    step: str
    """
    The plan step the statement was left open in, e.g. ``"pick up the cylinder"``.
    """

    slot: str
    """
    What the statement asks for, e.g. ``"which side to take it from"``.
    """

    statement: str
    """
    The statement, as English.
    """

    faculty: Faculty
    """
    The kind of knowledge that answered it.
    """

    backend: str
    """
    The name of the backend that answered it.
    """

    answers: List[str]
    """
    What it answered, most preferred first.
    """

    evidence: List[str]
    """
    What the backend read to answer it, one line each.
    """

    seconds: float
    """
    How long answering took.
    """

    answered_at: float
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
            "statement": self.statement,
            "faculty": self.faculty.value,
            "backend": self.backend,
            "answers": self.answers,
            "evidence": self.evidence,
            "milliseconds": round(self.seconds * 1000, 1),
            "answeredAt": self.answered_at,
        }


# %% the backends


@dataclass
class SlotBackend(QueryBackend, ABC):
    """
    A backend that declares which statements it can answer and says what it read to
    answer one.
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
    def evidence_for(self, statement: Match, answers: List[Any]) -> List[str]:
        """
        :param statement: The statement answered.
        :param answers: What this backend answered.
        :return: What it read to answer it, one line each.
        """


@dataclass(eq=False)
class PerceptionBackend(SelectiveBackend, SlotBackend):
    """
    Answers which pieces of a kind there are from what the last look at the scene saw.
    """

    twin: PerceivedTwin = field(repr=False)
    """
    The twin the look was committed into, which keeps what each piece was seen as.
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

    def evidence_for(self, statement: Match, answers: List[Any]) -> List[str]:
        return [
            f"{piece.name.name} · outline fits {sighting.outline_agreement:.0%}"
            for piece, sighting in self.twin.sightings.items()
            if piece in answers
        ] or ["nothing of that kind was seen"]


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
        everything: List[WorldEntity] = [
            *self.world.kinematic_structure_entities,
            *self.world.semantic_annotations,
        ]
        return [thing for thing in everything if isinstance(thing, statement._type_)]

    def evidence_for(self, statement: Match, answers: List[Any]) -> List[str]:
        considered = statement._domain_ or self.things_of_the_kind_of(statement)
        return [self.reading_of(thing, thing in answers) for thing in considered]

    def reading_of(self, thing: Any, selected: bool) -> str:
        """
        :param thing: A thing the statement ranged over.
        :param selected: Whether it was selected.
        :return: The thing, whether it was selected, and what its collision box rests
            on.
        """
        mark = "✓" if selected else "✗"
        if not isinstance(thing, SeenPiece):
            return f"{mark} {thing.name.name}"
        root = thing.root
        support = next(
            (
                body
                for body in self.world.bodies_with_collision
                if SupportedBy(root, body, contact_tolerance=self.contact_tolerance)()
            ),
            None,
        )
        if support is None:
            return f"{mark} {thing.name.name} · its box rests on nothing"
        contact = self.world.collision_manager.collision_detector.check_collision_between_bodies(
            root, support, distance=self.contact_tolerance
        )
        return (
            f"{mark} {thing.name.name} · box on {support.name.name} · "
            f"{max(contact.distance, 0.0) * 1000:.1f} mm"
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
        for hole in self.twin.holes:
            if hole.kind is kind:
                yield Insertion(piece=piece, hole=hole)

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
        # the rules are asked while the plan's own query is being answered, whose
        # evaluation state they must not conclude into
        shape = contextvars.Context().run(lambda: next(iter(rules.evaluate()), None))
        return None if shape is None else shape.kind

    def evidence_for(self, statement: Match, answers: List[Any]) -> List[str]:
        kind = self.concluded_kind(statement._kwargs_["piece"])
        return [
            f"{'▶' if rule_kind is kind else '·'} {'if' if index == 1 else 'else if'} "
            f"{self.twin.kind_of(rule_kind)} ⇒ {self.twin.kind_of(rule_kind)} hole"
            for index, rule_kind in enumerate(self.rule_order, start=1)
        ]


# %% how the hand takes hold of a piece


class GraspSide(enum.IntEnum):
    """
    The side of a piece the hand takes it from, as the turn about the piece's upright
    axis in degrees.
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
    The side the hand comes from.
    """

    piece: SeenPiece | None = None
    """
    The piece taken hold of, or None for a side not yet given a piece.
    """

    def candidate_on(self, piece: SeenPiece) -> GraspCandidate:
        """
        :param piece: The piece to take hold of.
        :return: The grasp taking the piece from this side.
        """
        return GraspCandidate(
            piece,
            Pose(
                orientation=RotationMatrix.from_rpy(
                    yaw=np.radians(self.side.value)
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

    def evaluate(self, expression: Match) -> Iterable[SideGrasp]:
        model = self.model_for(expression)
        sampled = ProbabilisticBackend(
            model_registry=model, number_of_samples=self.number_of_samples
        ).evaluate(an(SideGrasp)(side=...))
        weights = model.weights()
        sides = {grasp.side for grasp in sampled}
        for side in sorted(sides, key=lambda side: -weights[side]):
            yield SideGrasp(side=side, piece=model.piece)

    def evidence_for(self, statement: Match, answers: List[Any]) -> List[str]:
        weights = self.model_for(statement).weights()
        return [
            f"P({side.name.lower()}) = {probability:.2f}"
            for side, probability in sorted(weights.items(), key=lambda item: -item[1])
        ]


# %% choosing who answers


@dataclass
class OpenSlotAnswerer:
    """
    Hands each statement a plan left open to the first backend that declares it can
    answer it, and keeps what each answered.
    """

    backends: List[SlotBackend]
    """
    The backends to choose from, in the order they are preferred.
    """

    answered: List[SlotAnswer] = field(default_factory=list)
    """
    Every statement answered, in the order it was answered.
    """

    on_answer: Callable[[OpenSlotAnswerer], None] | None = None
    """
    Called after every statement answered.
    """

    def answer(self, step: str, slot: str, statement: Match) -> List[Any]:
        """
        Answer a statement and keep the answer.

        :param step: The plan step it was left open in.
        :param slot: What it asks for.
        :param statement: The statement.
        :return: What the chosen backend answered, most preferred first.
        :raises NoBackendAnswers: If no backend declares it can answer it.
        """
        backend = self.backend_for(statement)
        started = time.perf_counter()
        answers = list(backend.evaluate(statement))
        seconds = time.perf_counter() - started
        self.answered.append(
            SlotAnswer(
                step=step,
                slot=slot,
                statement=verbalize_expression(statement, backend=backend),
                faculty=backend.faculty,
                backend=type(backend).__name__,
                answers=[self.name_of(answer) for answer in answers],
                evidence=backend.evidence_for(statement, answers),
                seconds=seconds,
                answered_at=time.time(),
            )
        )
        if self.on_answer is not None:
            self.on_answer(self)
        return answers

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
        if isinstance(answer, SideGrasp):
            return f"from the {answer.side.name.lower()}"
        return answer.name.name if hasattr(answer, "name") else str(answer)

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: Every answer so far, and the backends there are, as JSON for the
            viewer.
        """
        return {
            "backends": [
                {"faculty": backend.faculty.value, "name": type(backend).__name__}
                for backend in self.backends
            ],
            "answers": [answer.to_payload() for answer in self.answered],
        }


# %% the domains the plan's open parts range over


@dataclass
class AnsweredWhenAsked:
    """
    The values an open part of a plan ranges over, answered by the backends only when
    the step it is left open in comes to be resolved.
    """

    answers: Callable[[], Iterator[Any]]
    """
    Produces the values, asking the backends as it goes.
    """

    def __iter__(self) -> Iterator[Any]:
        yield from self.answers()
