"""
The Montessori sorting scenes, and the scripted runs over them, as instances of the
scenario domain model.

A scene is a :class:`PieceLayout` — which pieces stand on the table, where, and turned
how far — and a run is what is then done to it. The two compose: every run here takes a
layout, so a random scene and a near-ambiguous one are the same four scripts over
different scenes rather than eight scenarios.
"""

from __future__ import annotations

import math
import random
from abc import ABC
from dataclasses import dataclass, field

from typing_extensions import (
    ClassVar,
    Generic,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TYPE_CHECKING,
)

from krrood.entity_query_language.verbalization.vocabulary.english import (
    Prepositions,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    clause,
    Copula,
    Noun,
)

from experiments.montessori.pieces import (
    KNOWN_PIECE_BY_CATEGORY,
    KNOWN_PIECES,
    KnownPiece,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.world import (
    BOARD_POSITION,
    BOARD_SCALE,
    TABLE_POSITION,
    TABLE_SCALE,
    MontessoriWorld,
)
from experiments.scenarios.scenario import (
    Goal,
    Perturbation,
    RobotType,
    Scenario,
    ScenarioStep,
    StepName,
    WorldType,
)
from semantic_digital_twin.adapters.multi_sim import MujocoLight
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.world_entity import Body

if TYPE_CHECKING:
    from krrood.entity_query_language.predicate import RenderedFields
    from krrood.entity_query_language.verbalization.fragments.base import (
        VerbalizationFragment,
    )

# %% the steps a sorting run is divided into


TABLE_TOP_Z = float(TABLE_POSITION.z) + TABLE_SCALE.z / 2
"""
The height of the Montessori table's top surface, in the world root frame.

Every height in this module is measured against it rather than against the table, so a
placement's own height and a viewpoint's are in one frame and can be subtracted.
"""

SCENE_LIGHT_NAME = "scene light"
"""
The name a changed scene light is written into a MuJoCo scene under.
"""

WIDEST_PIECE_REACH = max(piece.radius for piece in KNOWN_PIECES)
"""
How far the widest piece of this set reaches from its own centre, in metres.

What an area has to be inset by for a piece standing anywhere in it to stand wholly
inside it, whichever piece it is.
"""


class SortingStep(StepName):
    """
    The steps every scripted run in this module is divided into.
    """

    SETTLE = "settle"
    PICK_UP = "pick up"
    PUT_DOWN = "put down"
    PUSH = "push"
    ANSWER = "answer"


PLACEMENT_ATTEMPTS = 200
"""
How many positions a layout tries for one piece before giving up on the area it was
given.

A layout places its pieces by drawing positions and keeping the ones that clear every
piece already standing, so an area too small for the pieces asked of it would otherwise
draw forever.
"""


class NoRoomForThePieceError(RuntimeError):
    """
    Raised when a layout cannot stand a piece anywhere in the area it was given without
    it touching one already standing.
    """

    def __init__(self, piece: KnownPiece, area: LayoutArea) -> None:
        super().__init__(
            f"No room left for the {piece.category} in {area} after "
            f"{PLACEMENT_ATTEMPTS} attempts."
        )
        self.piece = piece
        """
        The piece that found no room.
        """

        self.area = area
        """
        The area it found no room in.
        """


# %% where the pieces stand


@dataclass
class LayoutArea:
    """
    The rectangle of table top a layout stands its pieces on.
    """

    minimum_x: float
    """
    The near edge of the rectangle, in metres in the world root frame.
    """

    maximum_x: float
    """
    The far edge of the rectangle.
    """

    minimum_y: float
    """
    The right edge of the rectangle.
    """

    maximum_y: float
    """
    The left edge of the rectangle.
    """

    @classmethod
    def on_the_table_beside_the_board(cls) -> LayoutArea:
        """
        The strip of the Montessori table that lies clear of the board, inset by the
        reach of the widest piece so that a piece standing anywhere in it stands wholly
        on the table and never over the board.
        """
        table_far_x = float(TABLE_POSITION.x) + TABLE_SCALE.x / 2
        board_near_x = float(BOARD_POSITION.x) + BOARD_SCALE.x / 2
        table_right_y = float(TABLE_POSITION.y) - TABLE_SCALE.y / 2
        table_left_y = float(TABLE_POSITION.y) + TABLE_SCALE.y / 2
        return cls(
            minimum_x=board_near_x + WIDEST_PIECE_REACH,
            maximum_x=table_far_x - WIDEST_PIECE_REACH,
            minimum_y=table_right_y + WIDEST_PIECE_REACH,
            maximum_y=table_left_y - WIDEST_PIECE_REACH,
        )

    def contains(self, placement: PiecePlacement) -> bool:
        """
        Whether a placement stands inside this rectangle.

        :param placement: The placement to check.
        """
        return (
            self.minimum_x <= placement.x <= self.maximum_x
            and self.minimum_y <= placement.y <= self.maximum_y
        )

    def drawn_from(self, draw: random.Random) -> Tuple[float, float]:
        """
        One position drawn uniformly from this rectangle.

        :param draw: The source of randomness, so a layout is reproducible from a seed.
        """
        return (
            draw.uniform(self.minimum_x, self.maximum_x),
            draw.uniform(self.minimum_y, self.maximum_y),
        )


@dataclass
class PiecePlacement:
    """
    Where one loose piece stands on the table, and how far it is turned.
    """

    piece: KnownPiece
    """
    The kind of piece standing here.
    """

    x: float
    """
    Where it stands along the table's near-far axis, in metres in the world root frame.
    """

    y: float
    """
    Where it stands along the table's left-right axis.
    """

    yaw: float
    """
    How far it is turned about its own standing axis, in radians.
    """

    def distance_to(self, other: PiecePlacement) -> float:
        """
        How far this placement stands from another, measured on the table.

        :param other: The placement to measure to.
        """
        return math.hypot(self.x - other.x, self.y - other.y)

    def depth_from(self, viewpoint: Point3) -> float:
        """
        How far this placement's piece stands from somewhere looked from, measured to
        the middle of the piece's own height.

        :param viewpoint: Where the scene is looked at from, in the world root frame.
        """
        return math.dist(
            (self.x, self.y, self.standing_height),
            (float(viewpoint.x), float(viewpoint.y), float(viewpoint.z)),
        )

    @property
    def standing_height(self) -> float:
        """
        The height of the middle of the piece, in the world root frame.
        """
        return TABLE_TOP_Z + self.piece.height / 2


@dataclass
class PieceLayout:
    """
    Which pieces a scene holds and where each of them stands.
    """

    placements: List[PiecePlacement]
    """
    One placement per piece the scene holds, in the order the layout drew them.
    """

    @classmethod
    def randomized(cls, seed: int, area: LayoutArea) -> PieceLayout:
        """
        A layout standing every piece of this set somewhere in the given area, drawn
        from a seed so the same seed always builds the same scene.

        :param seed: What the positions and turns are drawn from.
        :param area: Where the pieces may stand.
        """
        return cls.partial(
            seed=seed,
            area=area,
            categories=tuple(piece.category for piece in KNOWN_PIECES),
        )

    @classmethod
    def partial(
        cls,
        seed: int,
        area: LayoutArea,
        categories: Sequence[MontessoriShapeCategory],
    ) -> PieceLayout:
        """
        A layout standing only the named pieces, so a scene can hold two or three of
        them rather than the whole set.

        :param seed: What the positions and turns are drawn from.
        :param area: Where the pieces may stand.
        :param categories: Which pieces the scene holds, in the order they are placed.
        """
        draw = random.Random(seed)
        placements: List[PiecePlacement] = []
        for category in categories:
            placements.append(
                cls._drawn_clear_of(
                    KNOWN_PIECE_BY_CATEGORY[category], area, draw, placements
                )
            )
        return cls(placements=placements)

    @classmethod
    def nearly_ambiguous(
        cls, seed: int, area: LayoutArea, viewpoint: Point3
    ) -> PieceLayout:
        """
        A layout standing the cube and the cylinder at one distance from the given
        viewpoint, with the rest of the set drawn as usual.

        The two wear the same measured hue, so at one depth neither colour nor depth
        separates them and only their outlines do — which is the hardest scene this set
        can present.

        :param seed: What the positions and turns are drawn from.
        :param area: Where the pieces may stand.
        :param viewpoint: Where the scene is looked at from, in the world root frame.
        """
        draw = random.Random(seed)
        cube = cls._drawn_clear_of(
            KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE], area, draw, []
        )
        cylinder = cls._drawn_at_the_depth_of(cube, area, draw, viewpoint)
        placements = [cube, cylinder]
        for piece in KNOWN_PIECES:
            if piece.category in (
                MontessoriShapeCategory.CUBE,
                MontessoriShapeCategory.CYLINDER,
            ):
                continue
            placements.append(cls._drawn_clear_of(piece, area, draw, placements))
        return cls(placements=placements)

    def placement_of(self, category: MontessoriShapeCategory) -> PiecePlacement:
        """
        Where the piece of the given shape stands in this layout.

        :param category: The shape to look up.
        :raises KeyError: If this layout holds no piece of that shape.
        """
        for placement in self.placements:
            if placement.piece.category is category:
                return placement
        raise KeyError(category)

    @property
    def categories(self) -> Set[MontessoriShapeCategory]:
        """
        The shapes this layout stands.
        """
        return {placement.piece.category for placement in self.placements}

    @classmethod
    def _drawn_clear_of(
        cls,
        piece: KnownPiece,
        area: LayoutArea,
        draw: random.Random,
        standing: Sequence[PiecePlacement],
    ) -> PiecePlacement:
        """
        One placement for a piece, drawn until it clears every piece already standing.

        :param piece: The piece to place.
        :param area: Where it may stand.
        :param draw: The source of randomness.
        :param standing: The pieces already placed.
        :raises NoRoomForThePieceError: If no drawn position clears them.
        """
        for _ in range(PLACEMENT_ATTEMPTS):
            x, y = area.drawn_from(draw)
            candidate = PiecePlacement(
                piece=piece, x=x, y=y, yaw=draw.uniform(-math.pi, math.pi)
            )
            if cls._clears_every_one(candidate, standing):
                return candidate
        raise NoRoomForThePieceError(piece, area)

    @classmethod
    def _drawn_at_the_depth_of(
        cls,
        already_standing: PiecePlacement,
        area: LayoutArea,
        draw: random.Random,
        viewpoint: Point3,
    ) -> PiecePlacement:
        """
        A placement for the cylinder at exactly the depth another piece already stands
        at, and as close to it as the area allows.

        The nearest of the drawn candidates rather than the first, so the two stand as
        confusably as this area lets them — which is what makes the scene ambiguous
        beyond the shared depth, without a separation nobody chose being written down.

        :param already_standing: The piece whose depth is to be matched.
        :param area: Where the cylinder may stand.
        :param draw: The source of randomness.
        :param viewpoint: Where the depth is measured from.
        :raises NoRoomForThePieceError: If no drawn position meets all three.
        """
        cylinder = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CYLINDER]
        depth = already_standing.depth_from(viewpoint)
        height = TABLE_TOP_Z + cylinder.height / 2
        candidates: List[PiecePlacement] = []
        for _ in range(PLACEMENT_ATTEMPTS):
            y = draw.uniform(area.minimum_y, area.maximum_y)
            offset_squared = (
                depth**2
                - (y - float(viewpoint.y)) ** 2
                - (height - float(viewpoint.z)) ** 2
            )
            if offset_squared < 0:
                continue
            for direction in (-1.0, 1.0):
                x = float(viewpoint.x) + direction * math.sqrt(offset_squared)
                candidate = PiecePlacement(
                    piece=cylinder, x=x, y=y, yaw=draw.uniform(-math.pi, math.pi)
                )
                if area.contains(candidate) and cls._clears_every_one(
                    candidate, [already_standing]
                ):
                    candidates.append(candidate)
        if not candidates:
            raise NoRoomForThePieceError(cylinder, area)
        return min(candidates, key=already_standing.distance_to)

    @staticmethod
    def _clears_every_one(
        candidate: PiecePlacement, standing: Sequence[PiecePlacement]
    ) -> bool:
        """
        Whether a candidate placement touches none of the pieces already standing.

        :param candidate: The placement being considered.
        :param standing: The pieces already placed.
        """
        return all(
            candidate.distance_to(placement)
            >= candidate.piece.radius + placement.piece.radius
            for placement in standing
        )


# %% reading the scene back out of the world a trial runs in


@dataclass
class SortingScene:
    """
    The Montessori scene of one trial, read back out of the world it is running in.

    Every step and every goal here asks its questions through this rather than holding
    the built scene aside, so what they read is the twin's current state — which is
    what a perturbation, a push or a grasp actually changes.
    """

    world: World
    """
    The world the trial is running in.
    """

    @property
    def board(self) -> ShapeSortingBoard:
        """
        The shape-sorting board standing in the scene.
        """
        [board] = self.world.get_semantic_annotations_by_type(ShapeSortingBoard)
        return board

    @property
    def robot(self) -> AbstractRobot:
        """
        The robot mounted in the scene.
        """
        [robot] = self.world.get_semantic_annotations_by_type(AbstractRobot)
        return robot

    @property
    def gripper(self) -> Body:
        """
        The frame the robot grasps with, which a held piece hangs from.
        """
        [end_effector] = self.robot.get_end_effectors()
        return end_effector.tool_frame

    @property
    def categories(self) -> Set[MontessoriShapeCategory]:
        """
        The shapes the scene holds loose pieces of.
        """
        return {
            shape.shape_category
            for shape in self.world.get_semantic_annotations_by_type(MontessoriShape)
        }

    def shape_of(self, category: MontessoriShapeCategory) -> MontessoriShape:
        """
        The loose piece of the given shape.

        :param category: The shape to look up.
        :raises KeyError: If the scene holds no piece of that shape.
        """
        for shape in self.world.get_semantic_annotations_by_type(MontessoriShape):
            if shape.shape_category is category:
                return shape
        raise KeyError(category)

    def body_of(self, category: MontessoriShapeCategory) -> Body:
        """
        The body of the loose piece of the given shape.

        :param category: The shape to look up.
        """
        return self.shape_of(category).root

    def position_of(self, category: MontessoriShapeCategory) -> Point3:
        """
        Where the loose piece of the given shape currently stands, in the world root
        frame.

        :param category: The shape to look up.
        """
        return self.body_of(category).global_transform.to_position()

    def hole_for(self, category: MontessoriShapeCategory) -> ShapeSortingHole:
        """
        The board's hole the loose piece of the given shape drops through.

        :param category: The shape to look up.
        """
        return self.board.hole_for(self.shape_of(category))

    def is_held(self, category: MontessoriShapeCategory) -> bool:
        """
        Whether the loose piece of the given shape hangs from the gripper.

        :param category: The shape to look up.
        """
        return self.body_of(category).parent_connection.parent is self.gripper

    def stands_at(
        self, category: MontessoriShapeCategory, placement: PiecePlacement
    ) -> bool:
        """
        Whether the loose piece of the given shape still stands where a placement put
        it, to within a tenth of its own reach.

        :param category: The shape to look up.
        :param placement: Where it was put.
        """
        position = self.position_of(category)
        return (
            math.hypot(float(position.x) - placement.x, float(position.y) - placement.y)
            <= placement.piece.radius * UNDISTURBED_FRACTION_OF_A_PIECE
        )


UNDISTURBED_FRACTION_OF_A_PIECE = 0.1
"""
How far, as a fraction of a piece's own reach, it may drift and still count as standing
where it was put.

Expressed against the piece rather than in metres, so the same tolerance means the same
thing for the widest piece of the set and the narrowest.
"""


# %% what is done to the scene


@dataclass
class LetTheSceneSettle(ScenarioStep[World]):
    """
    The moment the scene is standing and nothing has acted on it yet.

    It changes nothing: what it is for is to be a moment a perturbation can name, since
    a perturbation strikes before a step rather than at a time of its own.
    """

    def perform(self, world: World) -> None:
        pass


@dataclass
class AskTheQuestion(ScenarioStep[World]):
    """
    The moment the scene is asked about, which is the state every goal here is about.

    Like :class:`LetTheSceneSettle` it changes nothing; a scenario ends with it so that
    what a run is questioned on is a named moment rather than "whatever was last done".
    """

    def perform(self, world: World) -> None:
        pass


@dataclass
class PickThePieceUp(ScenarioStep[World]):
    """
    Take a loose piece into the gripper, so it moves with the robot from here on.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece to pick up.
    """

    def perform(self, world: World) -> None:
        scene = SortingScene(world)
        hang(world, scene.body_of(self.category), scene.gripper)


@dataclass
class PutThePieceInItsHole(ScenarioStep[World]):
    """
    Drop a held piece through the board's hole for its own shape.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece to put down.
    """

    def perform(self, world: World) -> None:
        scene = SortingScene(world)
        hole = scene.hole_for(self.category)
        above_the_hole = hole.root.global_transform.to_position()
        hang(
            world,
            scene.body_of(self.category),
            world.root,
            Point3(
                float(above_the_hole.x),
                float(above_the_hole.y),
                float(above_the_hole.z) - KNOWN_PIECE_BY_CATEGORY[self.category].height,
            ),
        )


@dataclass
class PushThePiece(ScenarioStep[World]):
    """
    Shove a loose piece sideways, as a body other than the robot would.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece to push.
    """

    def perform(self, world: World) -> None:
        scene = SortingScene(world)
        body = scene.body_of(self.category)
        was_at = body.global_transform.to_position()
        piece = KNOWN_PIECE_BY_CATEGORY[self.category]
        hang(
            world,
            body,
            world.root,
            Point3(
                float(was_at.x),
                float(was_at.y) + 2 * piece.radius,
                float(was_at.z),
            ),
        )


def hang(
    world: World,
    body: Body,
    parent: Body,
    position: Optional[Point3] = None,
) -> None:
    """
    Move a body onto a new parent, optionally at a stated place in that parent's frame.

    This is what taking a piece into the gripper and what setting one down again both
    are: the piece stops hanging from wherever it hung and starts hanging from
    somewhere else.

    :param world: The world both bodies live in.
    :param body: The body to re-hang.
    :param parent: What it hangs from afterwards.
    :param position: Where it hangs, in the parent's frame; the parent's own origin if
        left unsaid.
    """
    origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=0.0 if position is None else float(position.x),
        y=0.0 if position is None else float(position.y),
        z=0.0 if position is None else float(position.z),
    )
    with world.modify_world():
        world.remove_connection(body.parent_connection)
        world.add_connection(
            FixedConnection(
                parent=parent, child=body, parent_T_connection_expression=origin
            )
        )


# %% what a run counts as success


@dataclass(eq=False)
class TheSceneIsUndisturbed(Goal[World]):
    """
    Success is every piece still standing where the layout put it.
    """

    layout: PieceLayout
    """
    Where the pieces were put.
    """

    def __call__(self) -> bool:
        scene = SortingScene(self.world)
        return all(
            scene.stands_at(placement.piece.category, placement)
            for placement in self.layout.placements
        )

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        return clause(Noun(fields["world"]), Copula(), Adjective("undisturbed"))


@dataclass(eq=False)
class ThePieceIsInItsHole(Goal[World]):
    """
    Success is one piece having gone through the board's hole for its own shape.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece that had to be sorted.
    """

    def __call__(self) -> bool:
        scene = SortingScene(self.world)
        piece = scene.position_of(self.category)
        hole = scene.hole_for(self.category).root.global_transform.to_position()
        reach = KNOWN_PIECE_BY_CATEGORY[self.category].radius
        return math.hypot(
            float(piece.x) - float(hole.x), float(piece.y) - float(hole.y)
        ) <= reach and float(piece.z) < float(hole.z)

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        return clause(
            Noun(fields["category"]),
            Copula(),
            Prepositions.IN,
            Noun.bare("its own hole"),
        )


@dataclass(eq=False)
class ThePieceMovedAndTheRobotDidNot(Goal[World]):
    """
    Success is one piece no longer standing where the layout put it, while every other
    piece still does — what an external body pushing one piece leaves behind.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece that was pushed.
    """

    layout: PieceLayout
    """
    Where the pieces were put.
    """

    def __call__(self) -> bool:
        scene = SortingScene(self.world)
        pushed = self.layout.placement_of(self.category)
        if scene.stands_at(self.category, pushed):
            return False
        return all(
            scene.stands_at(placement.piece.category, placement)
            for placement in self.layout.placements
            if placement.piece.category is not self.category
        )

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        return clause(
            Noun(fields["category"]),
            Copula(),
            Adjective("displaced"),
            Prepositions.FROM,
            Noun(fields["layout"]),
        )


@dataclass(eq=False)
class ThePieceIsHeld(Goal[World]):
    """
    Success is one piece hanging from the gripper at the moment the scene is asked
    about.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece that had to be held.
    """

    def __call__(self) -> bool:
        return SortingScene(self.world).is_held(self.category)

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        return clause(Noun(fields["category"]), Copula(), Adjective("held"))


# %% the change a run applies to its world


@dataclass
class LightingChanged(Perturbation[World]):
    """
    Light the scene differently, by giving the world a directional light of its own.

    A change to how the scene is lit rather than to what stands in it, so it is a
    perturbation of a run rather than a scene in its own right.
    """

    def apply(self, world: World) -> None:
        world.root.simulator_additional_properties.append(
            MujocoLight(name=SCENE_LIGHT_NAME, body=world.root, directional=True)
        )


# %% the scenarios themselves


@dataclass
class MountedRobot:
    """
    Where a fixed-base robot is bolted into a scene.

    Stated rather than derived: a bolted arm has no base to move afterwards, so where it
    stands is part of describing the scene, and there is no one right answer to read off
    the table.
    """

    position: Point3
    """
    Where the robot's root is bolted, in the world root frame.
    """

    yaw: float = 0.0
    """
    Which way it is turned to face, in radians.
    """


@dataclass
class MontessoriSortingScenario(
    Scenario[WorldType, RobotType], Generic[WorldType, RobotType], ABC
):
    """
    A scene of the Montessori sorting task: the board on its table, the pieces its
    layout stands, and a robot bolted in front of them.

    What each concrete scenario adds is the script — which steps are performed on the
    scene and what its goal then asks about it.
    """

    layout: PieceLayout = field(kw_only=True)
    """
    Which pieces stand in the scene and where.
    """

    robot: MountedRobot = field(kw_only=True)
    """
    Where the robot this scenario runs on is bolted.
    """

    def build_world(self) -> World:
        montessori = MontessoriWorld(shapes_are_movable=True)
        self._keep_only_the_layouts_pieces(montessori)
        self._stand_the_pieces_where_the_layout_says(montessori)
        montessori.mount_stationary_robot(
            self.robot_type,
            URDFParser.from_file(self.robot_type.get_ros_file_path()).parse(),
            self.robot.position,
            self.robot.yaw,
        )
        montessori.world.update_forward_kinematics()
        return montessori.world

    def _keep_only_the_layouts_pieces(self, montessori: MontessoriWorld) -> None:
        """
        Take out every loose piece the layout does not stand, so a partial scene really
        holds two or three pieces rather than the whole set with some of them tidied
        away.

        :param montessori: The freshly built scene.
        """
        wanted = self.layout.categories
        for shape in list(
            montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        ):
            if shape.shape_category in wanted:
                continue
            with montessori.world.modify_world():
                montessori.world.remove_semantic_annotation(shape)
                montessori.world.remove_kinematic_structure_entity(shape.root)

    def _stand_the_pieces_where_the_layout_says(
        self, montessori: MontessoriWorld
    ) -> None:
        """
        Move each remaining piece to its placement, resting on the table.

        :param montessori: The freshly built scene.
        """
        scene = SortingScene(montessori.world)
        for placement in self.layout.placements:
            body = scene.body_of(placement.piece.category)
            body.parent_connection.origin = (
                HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=placement.x,
                    y=placement.y,
                    z=resting_height_of(body),
                    yaw=placement.yaw,
                    reference_frame=montessori.world.root,
                )
            )


def resting_height_of(body: Body) -> float:
    """
    The height, in the world root frame, at which a loose piece's own origin sits when
    the piece rests on the Montessori table.

    Read off the body's own geometry rather than stated, so a piece whose mesh is built
    around a different point still rests on the surface rather than in it or above it.

    :param body: The piece's body.
    """
    lowest_point_of_the_body = float(body.collision.combined_mesh.bounds[0][2])
    return TABLE_TOP_Z - lowest_point_of_the_body


@dataclass
class TheSceneStandsStill(
    MontessoriSortingScenario[WorldType, RobotType], Generic[WorldType, RobotType]
):
    """
    The static run: the pieces are stood where the layout says and nothing acts on them.
    """

    name: ClassVar[str] = "the scene stands still"

    def goal(self, world: World) -> Goal[World]:
        """
        Success is the scene being exactly the one the layout described.

        :param world: The world the trial is running in.
        """
        return TheSceneIsUndisturbed(world=world, layout=self.layout)

    def steps(self, world: World) -> Sequence[ScenarioStep[World]]:
        return [
            LetTheSceneSettle(name=SortingStep.SETTLE),
            AskTheQuestion(name=SortingStep.ANSWER),
        ]


@dataclass
class RobotSortsAPiece(
    MontessoriSortingScenario[WorldType, RobotType], Generic[WorldType, RobotType]
):
    """
    The pick-and-place run: the robot takes one piece and drops it through its own hole.
    """

    name: ClassVar[str] = "the robot sorts a piece"

    sorted_category: MontessoriShapeCategory = field(kw_only=True)
    """
    The shape of the piece the robot sorts.
    """

    def goal(self, world: World) -> Goal[World]:
        """
        Success is that piece having gone through its own hole.

        :param world: The world the trial is running in.
        """
        return ThePieceIsInItsHole(world=world, category=self.sorted_category)

    def steps(self, world: World) -> Sequence[ScenarioStep[World]]:
        return [
            LetTheSceneSettle(name=SortingStep.SETTLE),
            PickThePieceUp(name=SortingStep.PICK_UP, category=self.sorted_category),
            PutThePieceInItsHole(
                name=SortingStep.PUT_DOWN, category=self.sorted_category
            ),
            AskTheQuestion(name=SortingStep.ANSWER),
        ]


@dataclass
class PiecePushedWhileTheRobotIsIdle(
    MontessoriSortingScenario[WorldType, RobotType], Generic[WorldType, RobotType]
):
    """
    The external-push run: something other than the robot moves a piece while the robot
    does nothing, so what changed in the scene is not the robot's own doing.
    """

    name: ClassVar[str] = "a piece is pushed while the robot is idle"

    pushed_category: MontessoriShapeCategory = field(kw_only=True)
    """
    The shape of the piece that is pushed.
    """

    def goal(self, world: World) -> Goal[World]:
        """
        Success is that piece having moved and every other one having stayed.

        :param world: The world the trial is running in.
        """
        return ThePieceMovedAndTheRobotDidNot(
            world=world, category=self.pushed_category, layout=self.layout
        )

    def steps(self, world: World) -> Sequence[ScenarioStep[World]]:
        return [
            LetTheSceneSettle(name=SortingStep.SETTLE),
            PushThePiece(name=SortingStep.PUSH, category=self.pushed_category),
            AskTheQuestion(name=SortingStep.ANSWER),
        ]


@dataclass
class PieceHeldWhileTheQuestionIsAsked(
    MontessoriSortingScenario[WorldType, RobotType], Generic[WorldType, RobotType]
):
    """
    The in-gripper run: the robot is still holding a piece at the moment the scene is
    asked about, so the piece is part of the robot rather than of the table.
    """

    name: ClassVar[str] = "a piece is held while the question is asked"

    held_category: MontessoriShapeCategory = field(kw_only=True)
    """
    The shape of the piece the robot holds.
    """

    def goal(self, world: World) -> Goal[World]:
        """
        Success is that piece hanging from the gripper when the question is asked.

        :param world: The world the trial is running in.
        """
        return ThePieceIsHeld(world=world, category=self.held_category)

    def steps(self, world: World) -> Sequence[ScenarioStep[World]]:
        return [
            LetTheSceneSettle(name=SortingStep.SETTLE),
            PickThePieceUp(name=SortingStep.PICK_UP, category=self.held_category),
            AskTheQuestion(name=SortingStep.ANSWER),
        ]


# %% the scenarios as the simulated demo runs them


@dataclass
class TracyWatchesTheSceneStandStill(TheSceneStandsStill[World, Tracy]):
    """
    The static run, on the robot the simulated Montessori demo is built around.
    """


@dataclass
class TracySortsAPiece(RobotSortsAPiece[World, Tracy]):
    """
    The pick-and-place run, on the robot the simulated Montessori demo is built around.
    """


@dataclass
class TracyIsIdleWhileAPieceIsPushed(PiecePushedWhileTheRobotIsIdle[World, Tracy]):
    """
    The external-push run, on the robot the simulated Montessori demo is built around.
    """


@dataclass
class TracyHoldsAPiece(PieceHeldWhileTheQuestionIsAsked[World, Tracy]):
    """
    The in-gripper run, on the robot the simulated Montessori demo is built around.
    """
