"""
What is expected of a thing something acted on, and what a look reports when it finds
otherwise.

An action says what it will do before it does it, and Segmind says what was seen to
happen. Both speak the world's own vocabulary: released over a hole, a thing is expected
to lie in that hole's region, within a release's spread of it; each event then says
which relations hold of the thing from then on, which stop holding, and which it is a
reason to check; and a thing nothing has acted on keeps exactly what was last believed
of it. That last rule is what makes a history worth keeping, since it is what lets a
belief hold across every frame in which nothing happened.

Looking becomes checking once a belief exists. The relations expected of a thing are the
relations a look is asked for, and what the look finds is asked the same relations, so
*which* of them it contradicts -- in the hole or beside it, on the lid or on the table,
turned this way or that -- is what a recovery can act on. That is the difference between
a failure and an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from typing_extensions import Any, Dict, List, Optional, Tuple, Type, TypeVar

from krrood.entity_query_language.backends import LookRequest, StatedRelation
from krrood.entity_query_language.predicate import Relation
from krrood.patterns.belief_source import BeliefSource
from segmind.datastructures.events import DetectionEvent, Effect, EventWithEffect
from semantic_digital_twin.reasoning.predicates import Colored, InsideRegion, Near
from semantic_digital_twin.semantic_annotations.mixins import (
    HasRootKinematicStructureEntity,
)
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
    Region,
)

Sought = TypeVar("Sought")
"""
The kind of thing a look reports.
"""

# %% what is expected of one thing


@dataclass
class Expectation:
    """
    The relations one thing is expected to stand in, and what put that belief there.

    Nothing here names a kind of relation: whatever the world's vocabulary can state
    about a thing can be expected of it, and a look checks each the way it can.
    """

    subject: Body
    """
    The thing this is expected of, as the world holds it.
    """

    holds: Tuple[StatedRelation, ...]
    """
    What is believed to hold of the subject, each relation stated with nothing standing
    in the subject's place.
    """

    source: BeliefSource
    """
    What put this belief there: the action that declared the effect, or whoever asked
    for the look.
    """

    @property
    def color(self) -> Optional[Color]:
        """
        The colour the subject is drawn in, or ``None`` where its geometry is drawn in
        none or in more than one.

        A colour is what tells a look which things are worth fitting where the subject
        is expected, so a look is asked for it alongside the relations.
        """
        colors: List[Color] = []
        for shape in (*self.subject.visual, *self.subject.collision):
            if shape.color not in colors:
                colors.append(shape.color)
        return colors[0] if len(colors) == 1 else None

    def after(self, effect: Effect) -> Expectation:
        """
        The same expectation once an event has happened to the subject.

        :param effect: What the event says holds of the subject from then on.
        """
        return replace(self, holds=effect.applied_to(self.holds, self.subject))

    def look_request(self, type_: Type[Sought]) -> LookRequest[Sought]:
        """
        This expectation as what a look is asked for: the relations expected of the
        subject, together with the colour it is drawn in where it is drawn in one.

        :param type_: The kind of thing the look reports.
        """
        stated = list(self.holds)
        if self.color is not None:
            stated.append(StatedRelation.of(Colored, self.color))
        return LookRequest(type_=type_, stated_relations=stated)

    def check(self, seen: Any) -> ExpectationReport:
        """
        What a look aimed at this expectation found, against what was expected.

        Each expected relation is asked of what was found, and the ones that fail are
        the report.

        :param seen: What the look reported where the subject was expected, as an entity
            of a world every relation can be asked of, or ``None`` where it reported
            nothing there.
        """
        if seen is None:
            return ExpectationReport(expectation=self, seen=None)
        return ExpectationReport(
            expectation=self, seen=seen, violated=self.contradicted_by(seen)
        )

    def contradicted_by(self, seen: KinematicStructureEntity) -> Tuple[Relation, ...]:
        """
        Every expected relation an entity does not stand in, each asserted about that
        entity so it can be read as the claim that failed.

        :param seen: The entity a look reported where the subject was expected.
        """
        return tuple(
            stated.about(seen) for stated in self.holds if not stated.about(seen)()
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

    seen: Any
    """
    What the look found where the subject was expected, or ``None`` where it found
    nothing.
    """

    violated: Tuple[Relation, ...] = ()
    """
    The expected relations the sighting does not stand in, each asserted about what the
    look found.

    Empty where the sighting stands in all of them, and empty where there was no
    sighting at all -- an absence contradicts no particular relation, which is why
    :attr:`nothing_was_found` reads it instead.
    """

    @property
    def holds(self) -> bool:
        """
        Whether the subject was found standing in every relation expected of it.
        """
        return self.seen is not None and not self.violated

    @property
    def nothing_was_found(self) -> bool:
        """
        Whether the look reported nothing at all where the subject was expected.
        """
        return self.seen is None


# %% what the robot expects, and what moves it


@dataclass
class Expectations(BeliefSource):
    """
    What is expected of everything the robot has acted on.

    An action's declared effect is what puts a belief here, and Segmind's events move it
    afterwards by what each says holds from then on. A belief nothing has acted on is
    left exactly as it was, which is what lets one release still direct a look many
    frames later.
    """

    release_spread: float = field(kw_only=True)
    """
    How far from where it was let go a released thing may come to rest, in metres.

    There is no honest default: how far a released thing scatters depends on the height
    it was let go from and on what it fell onto, so whoever declares the effect states
    it. This is the same call :class:`~semantic_digital_twin.reasoning.predicates.Near`
    makes about its own radius.
    """

    expected: Dict[Body, Expectation] = field(default_factory=dict)
    """
    One expectation per thing something has acted on, by the body an event names it by.
    """

    def expect(
        self, subject: Body, holds: Tuple[StatedRelation, ...], source: BeliefSource
    ) -> Expectation:
        """
        Believe something of a thing, in place of whatever was believed of it before.

        :param subject: The thing, as the world holds it.
        :param holds: The relations expected of it.
        :param source: What put the belief there.
        :return: The expectation now held.
        """
        expectation = Expectation(subject=subject, holds=holds, source=source)
        self.expected[subject] = expectation
        return expectation

    def released_over(
        self, subject: Body, hole: Region, source: BeliefSource
    ) -> Expectation:
        """
        Expect a thing let go above a hole to lie in that hole, within the release's
        spread of it.

        This is an insertion's own declared effect, and it is armed before any event
        confirms it -- which is the whole reason an expectation reaches a look at all on
        the frame the release happened. What the thing comes to rest on is deliberately
        not part of it: a thing that went in rests on whatever lies under the hole, not
        on the surface the hole is cut through, so expecting that surface would
        contradict the insertion's own success.

        :param subject: The thing that was released.
        :param hole: The region of the hole it was released over.
        :param source: What declared the effect.
        """
        return self.expect(
            subject,
            (
                StatedRelation.of(InsideRegion, hole),
                StatedRelation.of(Near, hole, radius=self.release_spread),
            ),
            source,
        )

    def record(self, event: DetectionEvent) -> None:
        """
        Move the belief about whatever the event says was acted on.

        An event moves a belief rather than creating one: only a declared effect says
        what to expect of a thing the robot has not acted on, so an event about a thing
        nothing is expected of is read and changes nothing. An event that states no
        effect leaves every belief alone.

        :param event: What Segmind saw happen.
        """
        if not isinstance(event, EventWithEffect):
            return
        expectation = self.of(event.tracked_object)
        if expectation is None:
            return
        self.expected[event.tracked_object] = expectation.after(event.effect())

    def of(self, subject: KinematicStructureEntity) -> Optional[Expectation]:
        """
        What is expected of one thing, or ``None`` where nothing has acted on it.

        :param subject: The thing, as the world holds it.
        """
        return self.expected.get(subject)

    def of_annotation(
        self, annotation: HasRootKinematicStructureEntity
    ) -> Optional[Expectation]:
        """
        What is expected of the thing an annotation is about, or ``None`` where nothing
        has acted on it.

        :param annotation: What the world says about the thing.
        """
        return self.of(annotation.root)

    def look_requests(self, type_: Type[Sought]) -> List[LookRequest[Sought]]:
        """
        What a look is armed with: one request per thing something has acted on.

        :param type_: The kind of thing the look reports.
        """
        return [
            expectation.look_request(type_) for expectation in self.expected.values()
        ]
