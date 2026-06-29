from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from typing_extensions import Any, List, Mapping

from krrood.entity_query_language.factories import entity, inference, variable
from krrood.entity_query_language.predicate import Triple
from krrood.entity_query_language.query.query import Entity
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    clause,
    Copula,
    Noun,
    Preposition,
)
from krrood.symbol_graph.symbol_graph import Symbol


class ShapeKind(Enum):
    """The geometric kinds of object a Montessori board sorts."""

    CYLINDER = "cylinder"
    CUBE = "cube"
    TRIANGLE = "triangle"


class HoleKind(Enum):
    """The geometric kinds of hole on a Montessori board."""

    SQUARE = "square"
    ROUND = "round"
    TRIANGULAR = "triangular"


@dataclass(eq=False)
class Shape(Symbol):
    """The shape of a placeable object."""

    kind: ShapeKind
    """The geometric kind of the shape."""

    def __hash__(self) -> int:
        return id(self)


@dataclass(eq=False)
class Hole(Symbol):
    """A hole on the Montessori board that an object can be placed into."""

    kind: HoleKind
    """The geometric kind of the hole."""

    name: str
    """A human-readable identifier for the hole."""

    def __hash__(self) -> int:
        return id(self)


@dataclass(eq=False)
class MontessoriObject(Symbol):
    """An object placed on the Montessori board."""

    shape: Shape
    """The shape of this object."""

    name: str
    """A human-readable identifier for the object."""

    on_board: bool = True
    """Whether the object is currently on the board. Always true in this scene; the over-general
    rule keys on this board membership and never on the object's shape."""

    def __hash__(self) -> int:
        return id(self)


@dataclass(eq=False)
class In(Triple):
    """Relation asserting that an object is placed in a hole (*"<object> is in <hole>"*)."""

    object_: Any
    """The placed object; the subject of the relation."""

    hole: Any
    """The hole the object is placed in; the object of the relation."""

    @property
    def subject(self) -> Any:
        return self.object_

    @property
    def object(self) -> Any:
        return self.hole

    def __call__(self) -> bool:
        return True

    @classmethod
    def _verbalization_fragment_(
        cls, fields: Mapping[str, VerbalizationFragment]
    ) -> VerbalizationFragment:
        return clause(
            Noun(fields["object_"]),
            Copula(),
            Preposition.IN,
            Noun(fields["hole"]),
        )


@dataclass
class MontessoriScene:
    """A shape-sorting board with an over-general placement rule, for exercising ``why``.

    The board has three objects and three holes; the only rule learned so far over-generalises the
    first demonstration (a cube placed in the square hole) to *every* object, because it keys on
    board membership rather than shape.
    """

    objects: List[MontessoriObject]
    """The objects on the board (cylinder, cube, triangle)."""

    square_hole: Hole
    """The square hole the over-general rule sends every object into."""

    round_hole: Hole
    """The round hole that matches the cylinder's shape."""

    triangular_hole: Hole
    """The triangular hole that matches the triangle's shape."""

    def object_named(self, name: str) -> MontessoriObject:
        """:return: The board object with the given name."""
        for placed_object in self.objects:
            if placed_object.name == name:
                return placed_object
        raise ValueError(f"No board object named {name!r}.")

    def over_general_placement_query(self) -> Entity:
        """Infer that every board object belongs in the square hole, regardless of its shape.

        The ``where`` condition keys only on board membership, so the rule over-generalises every
        object into the square hole — the knowledge gap the teaching loop later corrects.
        """
        placed_object = variable(MontessoriObject, domain=self.objects)
        return entity(
            inference(In)(object_=placed_object, hole=self.square_hole)
        ).where(placed_object.on_board == True)


def build_montessori_scene() -> MontessoriScene:
    """Construct a fresh Montessori scene.

    ..note:: Call this inside a test, after the autouse fixture has reset the ``SymbolGraph``, so the
        constructed symbols register in the test's own graph.
    """
    cylinder = MontessoriObject(shape=Shape(kind=ShapeKind.CYLINDER), name="cylinder")
    cube = MontessoriObject(shape=Shape(kind=ShapeKind.CUBE), name="cube")
    triangle = MontessoriObject(shape=Shape(kind=ShapeKind.TRIANGLE), name="triangle")
    return MontessoriScene(
        objects=[cylinder, cube, triangle],
        square_hole=Hole(kind=HoleKind.SQUARE, name="square hole"),
        round_hole=Hole(kind=HoleKind.ROUND, name="round hole"),
        triangular_hole=Hole(kind=HoleKind.TRIANGULAR, name="triangular hole"),
    )
