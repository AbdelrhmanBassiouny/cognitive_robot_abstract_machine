"""
What perception expects of a piece the robot has acted on, and what it reports when a
look finds something else.

An action says what it will do before it does it, and Segmind says what was seen to
happen. Both speak the world's own vocabulary: released over a hole, a piece is expected
to lie in that hole's region, within a release's spread of it, resting on the lid; each
event then says which relations hold of the piece from then on and which stop holding;
and a piece nothing has acted on keeps exactly what was last believed of it. That last
rule is what makes a history worth keeping, since it is what lets a belief hold across
every frame in which nothing happened.

Looking becomes checking once a belief exists. The relations expected of a piece are the
relations a look is asked for, so the search is narrowed and seeded by them; and what
the look finds is asked the same relations, so *which* of them it contradicts -- in the
hole or beside it, on the lid or on the table, turned this way or that -- is what a
recovery can act on. That is the difference between a failure and an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from typing_extensions import Dict, List, Optional, Tuple

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import MontessoriShape, ShapeSortingHole
from krrood.entity_query_language.backends import LookRequest, StatedRelation
from krrood.entity_query_language.predicate import Relation
from krrood.patterns.belief_source import BeliefSource
from segmind.datastructures.events import DetectionEvent, Effect, EventWithEffect
from semantic_digital_twin.reasoning.predicates import (
    Colored,
    InsideRegion,
    Near,
    SupportedBy,
)
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import Body

# %% what is expected of one piece


@dataclass(frozen=True)
class Expectation:
    """
    The relations one piece is expected to stand in, and what put that belief there.

    Nothing here names a kind of relation: whatever the world's vocabulary can state
    about a piece can be expected of it, and a look checks each the way it can.
    """

    piece: MontessoriShape
    """
    The piece this is expected of, as the world holds it.
    """

    holds: Tuple[StatedRelation, ...]
    """
    What is believed to hold of the piece, each relation stated with nothing standing in
    the piece's place.
    """

    source: BeliefSource
    """
    What put this belief there: the action that declared the effect, or whoever asked
    for the look.
    """

    @property
    def color(self) -> Color:
        """
        The colour this set gives the expected piece, which is what tells a look which
        pieces are worth fitting where the piece is expected.
        """
        return KNOWN_PIECE_BY_CATEGORY[self.piece.shape_category].color

    def after(self, effect: Effect) -> Expectation:
        """
        The same expectation once an event has happened to the piece.

        :param effect: What the event says holds of the piece from then on.
        """
        return replace(self, holds=effect.applied_to(self.holds))

    def look_request(self) -> LookRequest[DetectedMontessoriShape]:
        """
        This expectation as what a look is asked for: the relations expected of the
        piece, together with the colour it wears.
        """
        return LookRequest(
            type_=DetectedMontessoriShape,
            stated_relations=[*self.holds, StatedRelation.of(Colored, self.color)],
        )

    def scene_request(self) -> SceneRequest:
        """
        This expectation as something a look at the Montessori scene can act on, vouched
        for by whatever put the belief here so the look fits a piece where it is
        expected.
        """
        return replace(
            MontessoriPerceptionBackend.scene_request(self.look_request()),
            believed_by=self.source,
        )

    def check(self, seen: Optional[DetectedMontessoriShape]) -> ExpectationReport:
        """
        What a look aimed at this expectation found, against what was expected.

        :param seen: What the look reported where the piece was expected, or None where
            it reported nothing there.
        """
        if seen is None:
            return ExpectationReport(expectation=self, seen=None)
        return ExpectationReport(
            expectation=self,
            seen=seen,
            violated=MontessoriPerceptionBackend.contradicted_by(seen, self.holds),
        )


@dataclass(frozen=True)
class ExpectationReport:
    """
    What one look said about one expectation.

    A recovery reads this rather than the raw sighting: it says whether what was
    expected held, and where it did not, which relations the look contradicted.
    """

    expectation: Expectation
    """
    What was expected.
    """

    seen: Optional[DetectedMontessoriShape]
    """
    What the look found where the piece was expected, or None where it found nothing.
    """

    violated: Tuple[Relation, ...] = ()
    """
    The expected relations the sighting does not stand in, each asserted about the body
    the look stood in its world for the sighting.

    Empty where the sighting stands in all of them, and empty where there was no
    sighting at all -- an absence contradicts no particular relation, which is why
    :attr:`nothing_was_found` reads it instead.
    """

    @property
    def holds(self) -> bool:
        """
        Whether the piece was found standing in every relation expected of it.
        """
        return self.seen is not None and not self.violated

    @property
    def nothing_was_found(self) -> bool:
        """
        Whether the look reported nothing at all where the piece was expected.
        """
        return self.seen is None


# %% what the robot expects, and what moves it


@dataclass
class Expectations(BeliefSource):
    """
    What is expected of every piece the robot has acted on.

    An action's declared effect is what puts a belief here, and Segmind's events move it
    afterwards by what each says holds from then on. A belief nothing has acted on is
    left exactly as it was, which is what lets one release still direct a look many
    frames later.
    """

    lid: Body
    """
    The board's lid, which a piece released over one of its holes comes to rest on
    whether or not it went through, and so is looked for on.
    """

    release_spread: float = field(kw_only=True)
    """
    How far from a hole a released piece may come to rest, in metres.

    There is no honest default: how far a released piece scatters depends on the height
    it was let go from and on what it fell onto, so whoever declares the effect states
    it. This is the same call :class:`~semantic_digital_twin.reasoning.predicates.Near`
    makes about its own radius.
    """

    expected: Dict[Body, Expectation] = field(default_factory=dict)
    """
    One expectation per piece something has acted on, by the body an event names it by.
    """

    def released_over(
        self, piece: MontessoriShape, hole: ShapeSortingHole, source: BeliefSource
    ) -> None:
        """
        Expect a piece let go above a hole to lie in that hole, within the release's
        spread of it, resting on the lid.

        This is the action's own declared effect, and it is armed before any event
        confirms it -- which is the whole reason an expectation reaches a look at all on
        the frame the release happened.

        :param piece: The piece that was released.
        :param hole: The hole it was released over.
        :param source: What declared the effect.
        """
        self.expected[piece.root] = Expectation(
            piece=piece,
            holds=(
                StatedRelation.of(SupportedBy, self.lid),
                StatedRelation.of(InsideRegion, hole.root),
                StatedRelation.of(Near, hole.root, radius=self.release_spread),
            ),
            source=source,
        )

    def record(self, event: DetectionEvent) -> None:
        """
        Move the belief about whatever the event says was acted on.

        An event moves a belief rather than creating one: only a declared effect says
        what to expect of a piece the robot has not acted on, so an event about a piece
        nothing is expected of is read and changes nothing. An event that states no
        effect leaves every belief alone.

        :param event: What Segmind saw happen.
        """
        if not isinstance(event, EventWithEffect):
            return
        expectation = self.expected.get(event.tracked_object)
        if expectation is None:
            return
        self.expected[event.tracked_object] = expectation.after(event.effect())

    def of(self, piece: MontessoriShape) -> Optional[Expectation]:
        """
        What is expected of one piece, or None where nothing has acted on it.

        :param piece: The piece, as the world holds it.
        """
        return self.expected.get(piece.root)

    def scene_requests(self) -> List[SceneRequest]:
        """
        What a look is armed with: one request per piece something has acted on.
        """
        return [expectation.scene_request() for expectation in self.expected.values()]
