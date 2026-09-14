"""
Answering a statement about the things one world holds.

A look reports sightings and brings what it found into the world as bodies standing
where they were seen; from then on the thing is one the world holds, and what is asked
about it -- whether it rests on the lid, which way it is turned, what colour it is drawn
in -- is read off the world's own geometry rather than off the picture it was found in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Iterable, Iterator, List

from krrood.entity_query_language.backends import SelectiveBackend
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.factories import ConditionType
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.utils import T
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import WorldEntity


@dataclass(eq=False)
class WorldBackend(SelectiveBackend):
    """
    Answers a statement about the things one world holds by selecting among them.

    Selective, because the world already holds them: a statement here says which of them
    is meant, and every condition it states is decided against the thing itself -- a
    relation between two of them reads their geometry, which is the whole of why the
    answer is the world's to give rather than the look's.

    Which world is the point. A world entity is a
    :class:`~krrood.entity_query_language.predicate.Symbol`, so a statement over one that
    is handed no domain is answered out of the symbol graph -- and that is one graph per
    process, holding every entity ever made in it: the ones of a scene that has been torn
    down, and the copies an imagined world takes to try something out. Answering from
    there means answering with pieces standing in worlds nobody is planning in. This
    answers out of the world it is given.
    """

    world: World = field(repr=False)
    """
    The world whose things answer.

    Never shown when this backend is: a world prints as everything it holds, which is
    the whole scene wherever a backend is named in a message.
    """

    def capability(self, statement: Evaluable) -> ConditionType:
        """
        Beyond what every selective backend answers, the statement must be a pattern
        over a kind of thing this world holds: there is nothing to select out of a world
        holding none of them, so a statement about anything else is another backend's to
        answer.
        """
        return (
            super().capability(statement)
            and isinstance(statement, Match)
            and bool(self.things_of_the_kind_of(statement))
        )

    def _evaluate(self, expression: Match[T]) -> Iterable[T]:
        yield from expression.from_(
            self.things_of_the_kind_of(expression)
        )._evaluate_natively_()

    def things_of_the_kind_of(self, statement: Match[T]) -> List[T]:
        """
        :param statement: The statement to read.
        :return: Everything this world holds of the kind it is about, whatever kind that
            is -- a body, a connection, a degree of freedom, an annotation -- which is
            nothing where the world holds none of them.
        """
        if statement._type_ is None:
            return []
        return [
            thing
            for thing in self.everything_it_holds
            if isinstance(thing, statement._type_)
        ]

    @property
    def everything_it_holds(self) -> Iterator[WorldEntity]:
        """
        :return: Every entity of this world: what its kinematic structure is made of,
            what moves in it, what drives it, and what it is annotated with.
        """
        yield from self.world.kinematic_structure_entities
        yield from self.world.connections
        yield from self.world.degrees_of_freedom
        yield from self.world.actuators
        yield from self.world.semantic_annotations
