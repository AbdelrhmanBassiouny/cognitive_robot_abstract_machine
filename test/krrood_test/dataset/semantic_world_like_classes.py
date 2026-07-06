from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import ClassVar, List, Mapping, Optional, Type, Iterable

from krrood.entity_query_language.factories import (
    an,
    entity,
    variable,
)
from krrood.entity_query_language.predicate import Symbol, Predicate
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.rdr.recognition.candidate_generator import (
    CandidateGenerator,
)
from krrood.entity_query_language.rdr.recognition.has_candidates import HasCandidates
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.english import Prepositions
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    clause,
    Noun,
    Verb,
)


@dataclass(unsafe_hash=True)
class WorldEntity(Symbol):
    world: Optional[World] = field(default=None, kw_only=True, repr=False, hash=False)


@dataclass(unsafe_hash=True)
class Body(WorldEntity):
    name: str
    size: int = field(default=1)


@dataclass(unsafe_hash=True)
class Handle(Body): ...


@dataclass(unsafe_hash=True)
class Container(Body): ...


@dataclass(unsafe_hash=True)
class Connection(WorldEntity):
    parent: Body
    child: Body


@dataclass(unsafe_hash=True)
class FixedConnection(Connection): ...


@dataclass(unsafe_hash=True)
class PrismaticConnection(Connection): ...


@dataclass(unsafe_hash=True)
class RevoluteConnection(Connection): ...


@dataclass
class World(Symbol):
    id: int = field(default=0)
    bodies: List[Body] = field(default_factory=list)
    connections: List[Connection] = field(default_factory=list)
    views: List[View] = field(default_factory=list, repr=False)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, World):
            return False
        return self.id == other.id

    def add_view(self, view: View) -> None:
        """Record a recognized view so dependent view types can query it.

        The double's analogue of a world model absorbing an inferred annotation.
        """
        self.views.append(view)


@dataclass(unsafe_hash=True)
class View(WorldEntity): ...


@dataclass
class Drawer(View, HasCandidates):
    container: Container
    handle: Optional[Handle] = None
    correct: Optional[bool] = None

    def __hash__(self):
        return hash((self.__class__.__name__, self.handle, self.container))

    def __eq__(self, other):
        if not isinstance(other, Drawer):
            return False
        return (
            self.handle == other.handle
            and self.container == other.container
            and self.world == other.world
        )

    @classmethod
    def candidates(cls, world: World) -> Match:
        """Over-generating structural proposal of drawer candidates, as an underspecified view.

        The recall-oriented half of recognition (:cite:t:`erman1980hearsay`); a
        :class:`~krrood.entity_query_language.rdr.recognition.definition.Definition`
        judges which constructed candidates are genuine drawers.
        """
        return DrawerCandidateGenerator().generate(world)


@dataclass
class DrawerCandidateGenerator(CandidateGenerator["Drawer"]):
    """Proposes drawer candidates from a weak structural signal.

    A candidate is any container mounted on a prismatic joint (drawers slide). The
    handle is deliberately not required, so handle-less drawers are still proposed;
    precision — including whether a handle is present — is left to the drawer
    definition (:cite:t:`clancey1985heuristic`).
    """

    def generate(self, world: World) -> Match:
        return an(Drawer)(
            container=variable(Container, domain=self._prismatic_child_containers(world))
        )

    @staticmethod
    def _prismatic_child_containers(world: World) -> List[Container]:
        """The containers mounted as the child of a prismatic connection (the recall signal)."""
        container = variable(Container, domain=world.bodies)
        prismatic_connection = variable(PrismaticConnection, domain=world.connections)
        return list(
            an(entity(container).where(container == prismatic_connection.child)).evaluate()
        )


@dataclass
class Cabinet(View, HasCandidates):
    container: Container
    drawers: List[Drawer] = field(default_factory=list)
    correct: Optional[bool] = None

    def __hash__(self):
        return hash((self.__class__.__name__, self.container))

    def __eq__(self, other):
        if not isinstance(other, Cabinet):
            return False
        return (
            self.container == other.container
            and self.drawers == other.drawers
            and self.world == other.world
        )

    @classmethod
    def candidates(cls, world: World) -> Match:
        """Propose cabinet candidates from recognized drawers (a referenced conclusion).

        Reads recognized :class:`Drawer` views from the world, so the engine must recognize
        drawers first; the cabinet definition declares ``Drawer`` as a referenced conclusion.
        """
        return CabinetCandidateGenerator().generate(world)


@dataclass
class CabinetCandidateGenerator(CandidateGenerator["Cabinet"]):
    """Proposes a cabinet from the drawers already recognized in the world.

    A candidate is a container that is the prismatic parent of a recognized drawer's
    container, constructed holding those recognized drawers — a dependent view built from
    another view's conclusions (the "conclusions as case attributes" loop of GRDR).

    .. note::
        The proof double assumes a single cabinet body; per-body drawer grouping for the
        general multi-cabinet case is left to the real integration.
    """

    def generate(self, world: World) -> Match:
        return an(Cabinet)(
            container=variable(Container, domain=self._cabinet_bodies(world)),
            drawers=self._recognized_drawers(world),
        )

    @staticmethod
    def _recognized_drawers(world: World) -> List[Drawer]:
        """The drawers already recognized into the world."""
        return list(an(entity(variable(Drawer, domain=world.views))).evaluate())

    @staticmethod
    def _cabinet_bodies(world: World) -> List[Container]:
        """Containers that are the prismatic parent of a recognized drawer's container."""
        container = variable(Container, domain=world.bodies)
        prismatic_connection = variable(PrismaticConnection, domain=world.connections)
        drawer = variable(Drawer, domain=world.views)
        return list(
            an(
                entity(container).where(
                    container == prismatic_connection.parent,
                    prismatic_connection.child == drawer.container,
                )
            ).evaluate()
        )


@dataclass(unsafe_hash=True)
class Door(View):
    handle: Handle
    body: Body


@dataclass(unsafe_hash=True)
class Wardrobe(View):
    handle: Handle
    body: Body
    container: Container


@dataclass(unsafe_hash=True)
class Apple(Body): ...


@dataclass
class FruitBox(Symbol):
    name: str
    fruits: List[Body]


@dataclass
class ContainsType(Predicate):
    """
    Predicate that checks if any object in the iterable is of the given type.
    """

    iterable: Iterable
    """
    Iterable to check for objects of the given type.
    """

    obj_type: Type
    """
    Object type to check for.
    """

    def __call__(self) -> bool:
        return any(isinstance(obj, self.obj_type) for obj in self.iterable)

    @classmethod
    def _verbalization_fragment_(
        cls, fields: Mapping[str, VerbalizationFragment]
    ) -> VerbalizationFragment:
        return clause(
            Noun(fields["iterable"]),
            Verb("contain"),
            Noun("instance"),
            Prepositions.OF,
            Noun(fields["obj_type"]),
        )


@dataclass(unsafe_hash=True)
class GraspConfig(WorldEntity):
    """
    Simulates GraspDescription from coraplex with fields like rotate_gripper.
    Used to test set_of() with transitive attributes like MoveToReachDAO.grasp_description.rotate_gripper.
    """

    rotate_gripper: float = field(default=0.0)
    approach_direction: float = field(default=0.0)
    manipulation_offset: float = field(default=0.0)


@dataclass(unsafe_hash=True)
class MoveAction(WorldEntity):
    """
    Simulates MoveToReachDAO from coraplex with direct fields and a relationship.
    Used to test set_of() with both direct and transitive attributes.
    """

    robot_x: float = field(default=0.0)
    robot_y: float = field(default=0.0)
    hip_rotation: float = field(default=0.0)
    grasp_config: GraspConfig = field(default=None)
