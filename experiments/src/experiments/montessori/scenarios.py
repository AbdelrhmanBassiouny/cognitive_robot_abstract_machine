"""
The Montessori sorting scenes, and the scripted runs over them, as instances of the
scenario domain model.

A scene is a :class:`PieceLayout` — which pieces stand on the table, where, and turned
how far — and a run is what is then done to it. The two compose: every run here takes a
layout, so a random scene and a near-ambiguous one are the same four scripts over
different scenes rather than eight scenarios. What the layout stands its pieces in is a
:class:`MontessoriWorldBuilder` the scenario is given, so the same scripts run on the
board this package builds and on the one a demo brings with it.

Every run is carried in MuJoCo (:class:`SimulatedScene`), and what a step does it does
through the simulation: a scene comes to rest because gravity settles it, a piece is
shoved because a body runs into it, and a piece goes through a hole because it falls
through it. What the robot does it does through coraplex's own actions, which giskard
executes as motions. What a goal then reads it reads with the twin's own predicates
rather than by measuring the scene itself.
"""

from __future__ import annotations

import math
import os
import random
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy
from typing_extensions import (
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
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

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import (
    ApproachDirection,
    Arms,
    VerticalAlignment,
)
from coraplex.datastructures.grasp import GraspDescription
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction

from krrood.exceptions import DataclassException

from experiments.montessori.exceptions import (
    HoleHasNoLandingRegionError,
    NoSuchPieceError,
)
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.simulated_camera import SimulatedCamera
from experiments.montessori.perception.simulated_setup import perception_pipeline
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
from semantic_digital_twin.adapters.multi_sim import (
    MujocoCamera,
    MujocoLight,
    MujocoSim,
    MujocoSynchronizer,
    MultiSimSynchronizer,
)
from semantic_digital_twin.adapters.mujoco_video_recording import (
    MujocoVideoRecorder,
    RecordedVideo,
    VideoResolution,
)
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.callbacks.callback import ModelChangeCallback
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.reasoning.robot_predicates import robot_holds_body
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.spatial_types.derivatives import DerivativeMap
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import PrismaticConnection
from semantic_digital_twin.world_description.degree_of_freedom import (
    DegreeOfFreedom,
    DegreeOfFreedomLimits,
)
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    Region,
    SemanticAnnotation,
)

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

THE_ARM_THAT_SORTS = Arms.LEFT
"""
The arm a scripted run sorts with.

Every robot these scenarios run on has one arm, and an arm is named by which side it is
on rather than by how many there are, so a side has to be picked; which one is picked
does not matter while there is only one.
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
    LOOK = "look"
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
        :raises NoSuchPieceError: If the scene holds no piece of that shape.
        """
        for shape in self.world.get_semantic_annotations_by_type(MontessoriShape):
            if shape.shape_category is category:
                return shape
        raise NoSuchPieceError(category, frozenset(self.categories))

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

    def landing_region_for(self, category: MontessoriShapeCategory) -> Region:
        """
        The stretch of space below the hole this shape drops through: a piece that fell
        through the hole is inside it, and a piece resting on the board is not.

        Taken from the hole itself, which carries the space measured under it when the
        world was built.

        :param category: The shape to look up.
        :raises HoleHasNoLandingRegionError: If nothing was measured under that hole.
        """
        hole = self.hole_for(category)
        if hole.landing_region is None:
            raise HoleHasNoLandingRegionError(hole)
        return hole.landing_region

    def pick_the_piece_up(self, category: MontessoriShapeCategory) -> None:
        """
        Have the robot take hold of the loose piece of the given shape.

        :param category: The shape to pick up.
        """
        self._perform(
            PickUpAction(
                self.shape_of(category), THE_ARM_THAT_SORTS, self._grasp_description
            )
        )

    def put_the_piece_down_at(
        self, category: MontessoriShapeCategory, destination: Point3
    ) -> None:
        """
        Have the robot carry the piece it is holding to a place and let go of it there.

        :param category: The shape of the piece being carried.
        :param destination: Where to let go of it, in the world root frame.
        """
        self._perform(
            PlaceAction(
                self.body_of(category),
                Pose.from_xyz_rpy(
                    float(destination.x),
                    float(destination.y),
                    float(destination.z),
                    reference_frame=self.world.root,
                ),
                THE_ARM_THAT_SORTS,
                grasp_description=self._grasp_description,
            )
        )

    def _perform(self, action: ActionDescription) -> None:
        """
        Run one robot action against this scene's world.

        :param action: The action to run.
        """
        context = Context(self.world, self.robot)
        # The conditions a coraplex action states are about a robot that perceives and
        # navigates; a scripted scene states its own preconditions as its layout.
        context.evaluate_conditions = False
        with simulated_robot:
            sequential([action], context=context).plan.perform()

    @property
    def _grasp_description(self) -> GraspDescription:
        """
        How the robot takes hold of a piece: from above, since every piece here stands
        on a table and is posted down through a hole.
        """
        [end_effector] = self.robot.get_end_effectors()
        return GraspDescription(
            ApproachDirection.FRONT, VerticalAlignment.TOP, end_effector
        )

    def stand_the_piece_at(
        self, category: MontessoriShapeCategory, position: Point3
    ) -> None:
        """
        Put the loose piece of the given shape at a place, keeping how it is turned.

        :param category: The shape to move.
        :param position: Where to put it, in the world root frame.
        """
        body = self.body_of(category)
        body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=float(position.x),
            y=float(position.y),
            z=float(position.z),
            reference_frame=self.world.root,
        )

    def is_held(self, category: MontessoriShapeCategory) -> bool:
        """
        Whether the robot holds the loose piece of the given shape.

        Asked of the robot rather than of the connection the piece hangs from, so a
        piece counts as held when the robot's fingers are actually around it.

        :param category: The shape to look up.
        """
        return robot_holds_body(self.robot, self.body_of(category))

    def is_in_its_hole(self, category: MontessoriShapeCategory) -> bool:
        """
        Whether the loose piece of the given shape has gone through the board's hole for
        its own shape.

        Read as containment in that hole's landing region, which is how a containment
        detector reads an insertion.

        :param category: The shape to look up.
        """
        containment = InsideOf(
            self.body_of(category), self.landing_region_for(category)
        ).compute_containment_ratio()
        return containment >= CONTAINED_IN_ITS_LANDING_REGION

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


RELEASE_HEIGHT_ABOVE_THE_HOLE = 0.02
"""
How far above a hole a carried piece is let go of, in metres.

Far enough that the piece is clear of the board when the fingers open, so what puts it
through the hole is its own fall rather than the release.
"""

PUSHER_NAME = "pusher"
"""
The name the body that shoves a piece stands in the scene under.
"""

PUSHER_RAIL_NAME = "pusher_rail"
"""
The name of the connection the pusher slides along.
"""

PUSHER_SCALE = Scale(0.02, 0.02, 0.04)
"""
How big the pusher is, in metres.

Taller than the pieces so it meets them square on, and narrow enough to sit beside one
without touching its neighbours.
"""

PUSHER_CLEARANCE = 0.01
"""
The gap left between the pusher and the piece it is going to push, in metres.

The pusher starts out of contact so that the push is something it does, rather than
something that has already happened when the scene is built.
"""

PUSHING_STEPS = 20
"""
How many stretches of simulation one push is driven over.

The pusher is advanced a fraction of its travel at a time and the scene is simulated in
between, so it meets the piece at a speed rather than appearing on the far side of it.
"""

PUSHING_STEP_DURATION = 0.02
"""
How long the scene is simulated for after each of those stretches, in seconds.
"""

CONTAINED_IN_ITS_LANDING_REGION = 0.9
"""
How much of a piece's own mesh must lie inside a hole's landing region for the piece to
count as having gone through that hole.

The same fraction :class:`segmind`'s containment detector requires of a containment; the
region is sized so that a piece that fell through is wholly inside it and a piece
anywhere else is wholly outside, so nothing here rests on where between the two the
line is drawn.
"""

UNDISTURBED_FRACTION_OF_A_PIECE = 0.1
"""
How far, as a fraction of a piece's own reach, it may drift and still count as standing
where it was put.

Expressed against the piece rather than in metres, so the same tolerance means the same
thing for the widest piece of the set and the narrowest.
"""


# %% the video a run is filmed as


FRAMES_PER_SECOND = 15
"""
How many frames one second of a filmed run plays back as.
"""

STATE_CHANGES_PER_FRAME_OF_A_MOTION = 3
"""
How many changes to the world a robot's motion is filmed every frame of.

A stretch of physics is filmed against the simulated clock, so it needs no such number;
a motion is written into the world by giskard's controller at a rate of its own, and
filming every change of it would both slow the run down and play back far slower than
it happened.
"""

VIDEO_RESOLUTION = VideoResolution(width=640, height=480)
"""
How large a filmed run's frames are, in pixels.
"""

TABLE_BOUNDS = (
    (
        float(TABLE_POSITION.x) - TABLE_SCALE.x / 2,
        float(TABLE_POSITION.y) - TABLE_SCALE.y / 2,
        float(TABLE_POSITION.z) - TABLE_SCALE.z / 2,
    ),
    (
        float(TABLE_POSITION.x) + TABLE_SCALE.x / 2,
        float(TABLE_POSITION.y) + TABLE_SCALE.y / 2,
        float(TABLE_POSITION.z) + TABLE_SCALE.z / 2,
    ),
)
"""
The lowest and highest corner of the Montessori table, in the world root frame.
"""

SCENE_CAMERA_NAME = "the camera a run is filmed by"
"""
The name of the camera a filmed run is watched through.
"""

DEFAULT_VIDEO_DIRECTORY_NAME = "montessori_scenario_videos"
"""
The directory filmed runs are written into when nothing says where they should go.
"""


@dataclass
class TrialNotFilmedError(DataclassException):
    """
    Raised when a scenario is asked for the video of a trial it did not film.
    """

    scenario_name: str
    """
    The scenario that was asked.
    """

    def error_message(self) -> str:
        return "No trial of %r was filmed." % self.scenario_name

    def suggest_correction(self) -> str:
        return (
            "Build the scenario with filmed=True, and ask for the video only once a "
            "trial has built its world."
        )


class MontessoriEnvironmentVariable(StrEnum):
    """
    What the environment can be asked about a run of these scenarios.
    """

    VIDEO_DIRECTORY = "MONTESSORI_SCENARIO_VIDEO_DIRECTORY"
    """
    Where a filmed run writes its video.
    """


@dataclass
class SceneRecording:
    """
    The video a run is filmed as.

    A simulation is compiled against one kinematic model and cannot follow a change to
    it, and a run changes that model whenever the robot takes hold of something. So a
    run is filmed in more than one take: each stretch between two changes is one take,
    and the takes are kept here and written out as one video.
    """

    world: World
    """
    The world being filmed.
    """

    frames_per_second: int = FRAMES_PER_SECOND
    """
    How many frames one second of the video plays back as.
    """

    camera: MujocoCamera = field(init=False, repr=False)
    """
    Where the run is watched from, attached to the world once so that a cut between two
    takes does not also move the camera.
    """

    frames: List[numpy.ndarray] = field(init=False, default_factory=list, repr=False)
    """
    Everything filmed so far, in playback order.
    """

    _take: Optional[MujocoVideoRecorder] = field(init=False, default=None, repr=False)
    """
    The take being filmed, while one is running.
    """

    def __post_init__(self):
        self.camera = self._camera_watching_the_scene()

    def film(self) -> MujocoVideoRecorder:
        """
        The take running now, started if there is none.

        Its simulation is the one carrying the scene, so what is filmed is the run
        itself rather than a second simulation of it.
        """
        if self._take is not None:
            return self._take
        take = MujocoVideoRecorder(
            world=self.world,
            frames_per_second=self.frames_per_second,
            capture_every_n_state_changes=STATE_CHANGES_PER_FRAME_OF_A_MOTION,
            resolution=VIDEO_RESOLUTION,
            camera=self.camera,
        )
        take.start()
        self._take = take
        return take

    def cut(self) -> None:
        """
        End the take that is running, keeping what it filmed.
        """
        if self._take is None:
            return
        self.frames.extend(self._take.stop().frames)
        self._take = None

    def video(self) -> RecordedVideo:
        """
        Every take filmed so far, as one video, ending the take that is running.
        """
        self.cut()
        return RecordedVideo(
            frames=self.frames, frames_per_second=self.frames_per_second
        )

    def write(self, output_path: Path) -> Path:
        """
        Encode every take filmed so far as one video.

        :param output_path: The file to write it to.
        :return: The file it was written to.
        """
        return self.video().write(output_path)

    @property
    def frame_count(self) -> int:
        """
        How many frames the video holds, the take running now included.
        """
        filmed_now = 0 if self._take is None else self._take.captured_frame_count
        return len(self.frames) + filmed_now

    @staticmethod
    def where_videos_are_written() -> Path:
        """
        The directory a filmed run writes its video into, named by
        :attr:`MontessoriEnvironmentVariable.VIDEO_DIRECTORY` or, when that says
        nothing, a directory of its own beside whatever else this machine keeps
        temporarily.
        """
        stated = os.environ.get(MontessoriEnvironmentVariable.VIDEO_DIRECTORY)
        if stated is not None:
            return Path(stated)
        return Path(tempfile.gettempdir()) / DEFAULT_VIDEO_DIRECTORY_NAME

    def _camera_watching_the_scene(self) -> MujocoCamera:
        """
        A camera framing the table everything a run does is done on, attached to the
        world's root.

        The table rather than the whole world, which also holds a floor reaching far
        past anything a run touches.
        """
        watches_from = MujocoCamera.overview_pose(numpy.asarray(TABLE_BOUNDS))
        quaternion = watches_from.to_quaternion().to_np().tolist()
        camera = MujocoCamera(
            name=SCENE_CAMERA_NAME,
            body=self.world.root,
            position=watches_from.to_position().to_np()[:3].tolist(),
            # MuJoCo writes the scalar of a quaternion first, and Quaternion.to_np last.
            quaternion=[quaternion[3]] + quaternion[:3],
            resolution=[float(VIDEO_RESOLUTION.width), float(VIDEO_RESOLUTION.height)],
        )
        self.world.root.simulator_additional_properties.append(camera)
        return camera


# %% the physics the scene runs under


SIMULATION_STEP_SIZE = 0.001
"""
How far one step advances the simulation carrying a scene, in seconds.
"""

STILLNESS = 0.0005
"""
How far a piece may travel over one settling window and still count as standing still,
in metres.
"""

SETTLING_WINDOW = 0.05
"""
The stretch of simulated time stillness is measured over, in seconds.
"""

SETTLING_LIMIT = 5.0
"""
How long a scene is given to come to rest before it is taken as settled anyway, in
seconds.

A scene that is still moving after this is one where something is rolling or bouncing
without end, which no scene here is built to be; the bound is what stops a run hanging
on one if it happens.
"""


@dataclass(eq=False)
class _LetGoOfTheSimulationCallback(ModelChangeCallback):
    """
    Sibling callback owned by a :class:`SimulatedScene`. Lets go of the simulation the
    moment the world's model changes, since a simulation is compiled against the model
    as it was.
    """

    scene: SimulatedScene = field(kw_only=True)
    """
    The scene whose simulation is let go of.
    """

    def on_model_change(self, **kwargs) -> None:
        self.scene.stop()


@dataclass
class SimulatedScene:
    """
    The MuJoCo simulation carrying the scene of one trial.

    Advanced by a stated stretch of simulated time rather than against the wall clock,
    so two runs of the same scenario see the same physics.
    """

    world: World
    """
    The world being simulated.
    """

    step_size: float = SIMULATION_STEP_SIZE
    """
    How far one step advances it, in seconds.
    """

    recording: Optional[SceneRecording] = None
    """
    The video the run is being filmed as, when it is being filmed.
    """

    headless: bool = True
    """
    Whether the simulation runs without opening a viewer window.
    """

    physics: Optional[MujocoSim] = field(init=False, default=None, repr=False)
    """
    The MuJoCo simulation the scene is carried in, once there is one.
    """

    _let_go_of_the_simulation: Optional[_LetGoOfTheSimulationCallback] = field(
        init=False, default=None, repr=False
    )
    """
    What tells this scene that the world's model has changed under it.
    """

    def __post_init__(self):
        self._let_go_of_the_simulation = _LetGoOfTheSimulationCallback(
            _world=self.world, scene=self
        )

    def advance(self, duration: float) -> None:
        """
        Run the simulation for the given stretch of simulated time.

        :param duration: How long to run it for, in seconds.
        """
        self._take_up_carrying_the_scene()
        if self.recording is not None:
            self.recording.film().advance_simulation(duration)
            return
        for _ in range(round(duration / self.step_size)):
            self.physics.simulator.step()

    def _take_up_carrying_the_scene(self) -> None:
        """
        Make sure something is carrying the scene: the take a filmed run is being
        filmed as, or a simulation mirroring the world.

        A filmed run has no simulation of its own — it is carried by the one it is
        filmed from, so what is watched is the run itself rather than a second
        simulation of it.
        """
        # Building either puts the world under a root the simulation gives it, which is
        # a change to the model of the build's own making rather than one to let go of.
        self._let_go_of_the_simulation.pause()
        if self.recording is None:
            self._mirror_of_the_world()
        else:
            self.recording.film()
        self._let_go_of_the_simulation.resume()

    def _mirror_of_the_world(self) -> MujocoSim:
        """
        The simulation mirroring the world as it stands, built if there is none.
        """
        if self.physics is not None:
            return self.physics
        self.physics = MujocoSim(
            world=self.world, headless=self.headless, step_size=self.step_size
        )
        self.physics.synchronizer.sync_rate_hz = (
            MujocoSynchronizer.UNTHROTTLED_SYNC_RATE_HZ
        )
        # Stepped from here rather than from a thread of the simulator's own, so a step
        # of a scenario ends when the physics it asked for has actually run.
        self.physics.simulator.start(simulate_in_thread=False)
        return self.physics

    def settle(self) -> None:
        """
        Run the simulation until nothing in the scene is moving any more, or until
        :data:`SETTLING_LIMIT` has passed.
        """
        elapsed = 0.0
        was_at = self._piece_positions()
        while elapsed < SETTLING_LIMIT:
            self.advance(SETTLING_WINDOW)
            elapsed += SETTLING_WINDOW
            now_at = self._piece_positions()
            if all(
                numpy.linalg.norm(now_at[category] - was_at[category]) < STILLNESS
                for category in now_at
            ):
                return
            was_at = now_at

    def stop(self) -> None:
        """
        Stop carrying the scene, so the world is free to change the model the
        simulation was built against.
        """
        for synchronizer in MultiSimSynchronizer.all_callbacks_of_this_type_from_world(
            self.world
        ):
            # A change is notified to every callback the world had when it began, so a
            # simulation being let go of has to be paused as well as stopped for the
            # change under way not to reach it.
            synchronizer.pause()
            synchronizer.stop()
        if self.recording is not None:
            self.recording.cut()
        if self.physics is None:
            return
        self.physics.stop_simulation()
        self.physics = None

    def _piece_positions(self) -> Dict[MontessoriShapeCategory, numpy.ndarray]:
        """
        Where every loose piece stands right now, keyed by its shape.
        """
        scene = SortingScene(self.world)
        return {
            category: scene.position_of(category).to_np().flatten()[:3]
            for category in scene.categories
        }


# %% what is done to the scene


@dataclass
class ScenePhysicsStep(ScenarioStep[World], ABC):
    """
    A step of a scripted run, performed on a scene that is running under physics.
    """

    scene: SimulatedScene = field(kw_only=True)
    """
    The simulation carrying the scene this step acts on.
    """


@dataclass
class LetTheSceneSettle(ScenePhysicsStep):
    """
    Run the scene until it has come to rest, which is the moment before anything has
    acted on it.

    It is also the moment a perturbation can name, since a perturbation strikes before a
    step rather than at a time of its own.
    """

    def perform(self, world: World) -> None:
        self.scene.settle()


@dataclass
class AskTheQuestion(ScenePhysicsStep):
    """
    The moment the scene is asked about, which is the state every goal here is about.

    A scenario ends with it so that what a run is questioned on is a named moment rather
    than "whatever was last done"; the simulation that carried the scene stops here.
    """

    def perform(self, world: World) -> None:
        self.scene.stop()


@dataclass
class PickThePieceUp(ScenePhysicsStep):
    """
    Have the robot take hold of a loose piece, so that from here on the piece travels
    with it.

    The scene goes on being carried while the robot reaches for it, so the reach is
    watched as it happens; the grasp re-parents what it takes hold of, and the scene is
    let go of there, since that is a change to the model the simulation was built
    against.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece to pick up.
    """

    def perform(self, world: World) -> None:
        SortingScene(world).pick_the_piece_up(self.category)


@dataclass
class PutThePieceInItsHole(ScenePhysicsStep):
    """
    Have the robot carry a held piece over the board's hole for its own shape and let go
    of it there.

    Nothing puts the piece through the hole: the gripper opens above it and gravity does
    the rest, so a piece that does not fit does not go in.

    Carrying the piece is the one stretch of a run that cannot be simulated: a held
    piece hangs off the gripper on the free connection it stood on the table with, and
    a body on a free connection has to be a top-level one for MuJoCo to compile the
    scene at all. The scene is taken up again once the piece has been let go of.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece to put down.
    """

    def perform(self, world: World) -> None:
        scene = SortingScene(world)
        hole = scene.hole_for(self.category).root.global_transform.to_position()
        scene.put_the_piece_down_at(
            self.category,
            Point3(
                float(hole.x),
                float(hole.y),
                float(hole.z) + RELEASE_HEIGHT_ABOVE_THE_HOLE,
            ),
        )
        self.scene.settle()


@dataclass
class PushThePiece(ScenePhysicsStep):
    """
    Drive the scene's pusher into a loose piece, so a body other than the robot moves it.

    The piece is never moved directly: the pusher slides along its rail until it meets
    the piece, and what happens to the piece is whatever the contact does.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece to push.
    """

    def perform(self, world: World) -> None:
        reach = KNOWN_PIECE_BY_CATEGORY[self.category].radius
        travel = PUSHER_CLEARANCE + 2 * reach
        rail = world.get_connection_by_name(PUSHER_RAIL_NAME)
        for step in range(1, PUSHING_STEPS + 1):
            rail.position = travel * step / PUSHING_STEPS
            self.scene.advance(PUSHING_STEP_DURATION)
        self.scene.settle()


@dataclass
class LookAtTheScene(ScenePhysicsStep):
    """
    Take a look at the scene through the camera over the table, and keep what
    perception made of it.

    The one step of a run that reaches the scene through a camera rather than through
    the twin's own state, so it is the only place a perturbation of a reported pose or
    of a detection's label has anything to act on. Such a perturbation leaves what it
    wants changed on the world, since it is handed the world and nothing else; this
    step applies each one to what it found and takes it off the world again, so a
    perturbation strikes at the one look its step named rather than at every later one.

    The scene is let go of while the look is taken: a camera draws its picture from a
    mirror of the world built for it, and two simulations of one world are one too
    many.
    """

    camera: SimulatedCamera = field(kw_only=True)
    """
    The camera the look is taken through.
    """

    seen: Optional[MontessoriScene] = field(init=False, default=None)
    """
    What the last look found, or None before one has been taken.
    """

    def perform(self, world: World) -> None:
        self.scene.stop()
        with self.camera as looking:
            self.seen = perception_pipeline(world).detect(looking.frame())
        for waiting in world.get_semantic_annotations_by_type(
            PerturbationOfTheNextLook
        ):
            waiting.perturbation.change_what_was_seen(self.seen)
            with world.modify_world():
                world.remove_semantic_annotation(waiting)


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
        return SortingScene(self.world).is_in_its_hole(self.category)

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
    Success is the robot holding one piece at the moment the scene is asked about.
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

CENTIMETRES_PER_METRE = 100
"""
How many centimetres a metre is, since every length here is held in metres and a person
at the table is told centimetres.
"""

HOW_FAR_A_MOVED_HOLE_GOES = 0.1
"""
How far a perturbation slides the hole a piece is being aimed at, in metres.

The distance this perturbation was specified at. It is stated here rather than
defaulted onto :class:`TargetHoleMoved`, which takes the whole displacement: how far
the hole goes is settled, and which way it goes is the scene's to say.
"""


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

    def instruction_for_a_person(self) -> str:
        return "Light the table differently."


@dataclass
class TargetHoleMoved(Perturbation[World]):
    """
    Slide the board, so the hole a piece is meant to drop through is no longer where
    the robot was going to let go of it.

    The board is what moves, because a hole is cut into its lid rather than standing
    beside it: the board and every hole in it hang off connections with no degree of
    freedom, so the one thing that can be moved is the board itself, and every hole
    travels with it. The named hole therefore ends up exactly this displacement from
    where it was, which is what a run aiming at it has to cope with.
    """

    category: MontessoriShapeCategory
    """
    The shape whose own hole the displacement is stated for, and which the instruction
    to a person names.
    """

    displacement: Vector3
    """
    How far the board is moved and which way, in the board's own frame.
    """

    def apply(self, world: World) -> None:
        board = SortingScene(world).board.root.parent_connection
        with world.modify_world():
            board.parent_T_connection_expression = (
                board.parent_T_connection_expression
                @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=float(self.displacement.x),
                    y=float(self.displacement.y),
                    z=float(self.displacement.z),
                )
            )

    def instruction_for_a_person(self) -> str:
        return (
            f"Slide the board so its {self.category} hole sits "
            f"{_in_centimetres(self.displacement)} from where it is now."
        )


@dataclass
class PieceShoved(Perturbation[World]):
    """
    Move a loose piece, as something other than the robot running into it would.

    Where the piece ends up is what this states; the shove itself, as a contact a body
    sliding along its rail makes, is :class:`PushThePiece`'s, which the one scenario
    that builds a pusher uses. Both leave the scene in the state a run has to cope
    with, which is what a perturbation is for.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece that is moved.
    """

    displacement: Vector3
    """
    How far the piece is moved and which way, in the world root frame.
    """

    def apply(self, world: World) -> None:
        scene = SortingScene(world)
        stands_at = scene.position_of(self.category)
        scene.stand_the_piece_at(
            self.category,
            Point3(
                float(stands_at.x) + float(self.displacement.x),
                float(stands_at.y) + float(self.displacement.y),
                float(stands_at.z) + float(self.displacement.z),
            ),
        )

    def instruction_for_a_person(self) -> str:
        return (
            f"Push the {self.category} {_in_centimetres(self.displacement)} "
            f"across the table."
        )


# %% the change a run applies to what it is shown


@dataclass
class PerturbationOfWhatIsSeen(Perturbation[World], ABC):
    """
    A perturbation of what a look reports rather than of what stands in the scene.

    A perturbation is handed the world and nothing else, and the look it is aimed at is
    taken by a later step, so it leaves itself on the world for :class:`LookAtTheScene`
    to find. What the twin holds is untouched, which is the point: the run goes wrong
    because what it was told differs from what is there.
    """

    def apply(self, world: World) -> None:
        with world.modify_world():
            world.add_semantic_annotation(PerturbationOfTheNextLook(perturbation=self))

    @abstractmethod
    def change_what_was_seen(self, seen: MontessoriScene) -> None:
        """
        Change what a look reported, in place.

        :param seen: What the look found.
        """


@dataclass(eq=False)
class PerturbationOfTheNextLook(SemanticAnnotation):
    """
    A perturbation of what is seen, left on the world until a look is taken.

    The world is the only thing a perturbation and the step taking the look both hold,
    so it is what carries one to the other.
    """

    perturbation: PerturbationOfWhatIsSeen = field(kw_only=True)
    """
    The perturbation waiting for that look.
    """


@dataclass
class PerceivedPoseOffset(PerturbationOfWhatIsSeen):
    """
    Report a piece as standing somewhere other than where the look found it.

    The piece itself does not move, so a run that reaches for where it was told the
    piece is misses it by exactly this much.
    """

    category: MontessoriShapeCategory
    """
    The shape whose reported place is moved.
    """

    offset: Vector3
    """
    How far the reported place is moved and which way, in the frame the look reports
    in.
    """

    def change_what_was_seen(self, seen: MontessoriScene) -> None:
        for shape in seen.shapes:
            if shape.category is not self.category:
                continue
            reported_at = shape.pose.to_position()
            shape.pose = Pose(
                position=Point3(
                    float(reported_at.x) + float(self.offset.x),
                    float(reported_at.y) + float(self.offset.y),
                    float(reported_at.z) + float(self.offset.z),
                ),
                orientation=shape.pose.to_quaternion(),
                reference_frame=shape.pose.reference_frame,
            )

    def instruction_for_a_person(self) -> str:
        return (
            f"Once the robot has looked at the table, move the {self.category} "
            f"{_in_centimetres(self.offset)} without telling it."
        )


@dataclass
class DetectionRelabelled(PerturbationOfWhatIsSeen):
    """
    Report a piece as being a piece of another shape.

    What the look found stays where it is and keeps its outline; only what it is called
    changes, which is what sends the run to the wrong hole.
    """

    category: MontessoriShapeCategory
    """
    The shape of the piece that is actually there.
    """

    reported_as: MontessoriShapeCategory
    """
    The shape it is reported as instead.
    """

    def change_what_was_seen(self, seen: MontessoriScene) -> None:
        for shape in seen.shapes:
            if shape.category is self.category:
                shape.category = self.reported_as

    def instruction_for_a_person(self) -> str:
        return (
            f"Put the {self.reported_as} where the {self.category} is, so the robot "
            f"finds the wrong shape there."
        )


def _in_centimetres(displacement: Vector3) -> str:
    """
    How far a displacement reaches, worded for the person asked to bring it about.

    :param displacement: The displacement to word.
    """
    reach = math.hypot(
        float(displacement.x), float(displacement.y), float(displacement.z)
    )
    return f"{round(reach * CENTIMETRES_PER_METRE)} cm"


# %% the scene a run is set in


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
class MontessoriWorldBuilder(ABC):
    """
    What builds the Montessori scene a trial is run in, and says how high the table it
    stands its pieces on is.

    A scenario is handed one rather than building a scene of its own, so the same
    scripts run on the scene this package builds and on the one a demo brings with it —
    a board standing on the robot's own table, whose height is known only once that
    robot is mounted.
    """

    @abstractmethod
    def build(self, robot_type: Type[AbstractRobot]) -> MontessoriWorld:
        """
        Build a fresh scene with a robot of the given type mounted in it.

        Asked once per trial rather than a built scene being handed round, so two trials
        of one scenario are two scenes. The loose pieces have to be movable
        (:attr:`~experiments.montessori.world.MontessoriWorld.shapes_are_movable`),
        since the runs pick them up.

        :param robot_type: The robot the scenario runs on, as its own binding names it.
        """

    @property
    @abstractmethod
    def table_top_z(self) -> float:
        """
        The height of the surface this scene's loose pieces stand on, in the world root
        frame.
        """

    def resting_height_of(self, body: Body) -> float:
        """
        The height at which a loose piece's own origin sits when it rests on this
        scene's table.

        Read off the body's own geometry rather than stated, so a piece whose mesh is
        built around a different point still rests on the surface rather than in it or
        above it.

        :param body: The piece's body.
        """
        lowest_point_of_the_body = float(body.collision.combined_mesh.bounds[0][2])
        return self.table_top_z - lowest_point_of_the_body


@dataclass
class BoardOnItsOwnTable(MontessoriWorldBuilder):
    """
    The scene this package builds itself: the board on the table
    :class:`~experiments.montessori.world.MontessoriWorld` stands it on, with the robot
    bolted in front of it.
    """

    robot: MountedRobot = field(kw_only=True)
    """
    Where the robot is bolted in the scene.
    """

    def build(self, robot_type: Type[AbstractRobot]) -> MontessoriWorld:
        montessori = MontessoriWorld(shapes_are_movable=True)
        montessori.mount_stationary_robot(
            robot_type,
            URDFParser.from_file(robot_type.get_ros_file_path()).parse(),
            self.robot.position,
            self.robot.yaw,
        )
        return montessori

    @property
    def table_top_z(self) -> float:
        return TABLE_TOP_Z


# %% the scenarios themselves


@dataclass
class MontessoriSortingScenario(
    Scenario[WorldType, RobotType], Generic[WorldType, RobotType], ABC
):
    """
    A run of the Montessori sorting task: the scene it is given, the pieces its layout
    stands in that scene, and the robot the scene bolts in it.

    What each concrete scenario adds is the script — which steps are performed on the
    scene and what its goal then asks about it.
    """

    layout: PieceLayout = field(kw_only=True)
    """
    Which pieces stand in the scene and where.
    """

    world_builder: MontessoriWorldBuilder = field(kw_only=True)
    """
    What builds the scene each trial of this scenario is run in.
    """

    filmed: bool = field(kw_only=True, default=False)
    """
    Whether a video of the run is made while it is performed.
    """

    headless: bool = field(kw_only=True, default=True)
    """
    Whether the run's simulation goes without a viewer window.
    """

    simulation: Optional[SimulatedScene] = field(init=False, default=None)
    """
    The physics carrying the world this scenario built most recently.

    A scenario owns it because the world it carries is the one the scenario built, and
    because a scene has to be standing before it can be simulated: the simulator
    compiles the scene once, so everything a run acts with has to be in it by then.
    """

    def build_world(self) -> World:
        if self.simulation is not None:
            self.simulation.stop()
        montessori = self.world_builder.build(self.robot_type)
        self._keep_only_the_layouts_pieces(montessori)
        self._stand_the_pieces_where_the_layout_says(montessori)
        self.add_what_the_script_acts_with(montessori)
        montessori.world.update_forward_kinematics()
        self.simulation = SimulatedScene(
            world=montessori.world,
            recording=(SceneRecording(world=montessori.world) if self.filmed else None),
            headless=self.headless,
        )
        return montessori.world

    @property
    def acted_on_category(self) -> Optional[MontessoriShapeCategory]:
        """
        The shape of the piece this scenario's script acts on, or None for a script
        that leaves every piece alone.
        """
        return None

    def video_of_the_trial(self) -> RecordedVideo:
        """
        The video of the trial that ran in the world built most recently.

        :raises TrialNotFilmedError: If that trial was not filmed.
        """
        if self.simulation is None or self.simulation.recording is None:
            raise TrialNotFilmedError(scenario_name=self.name)
        return self.simulation.recording.video()

    def add_what_the_script_acts_with(self, montessori: MontessoriWorld) -> None:
        """
        Put anything this scenario's script needs into the scene, beyond the board, the
        pieces and the robot every scenario here has.

        :param montessori: The scene being built.
        """

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
                    z=self.world_builder.resting_height_of(body),
                    yaw=placement.yaw,
                    reference_frame=montessori.world.root,
                )
            )


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
            LetTheSceneSettle(name=SortingStep.SETTLE, scene=self.simulation),
            AskTheQuestion(name=SortingStep.ANSWER, scene=self.simulation),
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

    @property
    def acted_on_category(self) -> Optional[MontessoriShapeCategory]:
        return self.sorted_category

    def goal(self, world: World) -> Goal[World]:
        """
        Success is that piece having gone through its own hole.

        :param world: The world the trial is running in.
        """
        return ThePieceIsInItsHole(world=world, category=self.sorted_category)

    def steps(self, world: World) -> Sequence[ScenarioStep[World]]:
        return [
            LetTheSceneSettle(name=SortingStep.SETTLE, scene=self.simulation),
            PickThePieceUp(
                name=SortingStep.PICK_UP,
                category=self.sorted_category,
                scene=self.simulation,
            ),
            PutThePieceInItsHole(
                name=SortingStep.PUT_DOWN,
                category=self.sorted_category,
                scene=self.simulation,
            ),
            AskTheQuestion(name=SortingStep.ANSWER, scene=self.simulation),
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

    @property
    def acted_on_category(self) -> Optional[MontessoriShapeCategory]:
        return self.pushed_category

    def add_what_the_script_acts_with(self, montessori: MontessoriWorld) -> None:
        """
        Stand the pusher on its rail beside the piece it is going to shove.

        :param montessori: The scene being built.
        """
        world = montessori.world
        scene = SortingScene(world)
        stands_at = scene.position_of(self.pushed_category)
        reach = KNOWN_PIECE_BY_CATEGORY[self.pushed_category].radius
        pusher = Body(
            name=PrefixedName(PUSHER_NAME),
            collision=ShapeCollection([Box(scale=PUSHER_SCALE)]),
        )
        travel = DegreeOfFreedom(
            name=PrefixedName(PUSHER_RAIL_NAME),
            # A degree of freedom named after anything but its own connection is read as
            # a joint mimicking another one, which this is not.
            limits=DegreeOfFreedomLimits(lower=DerivativeMap(), upper=DerivativeMap()),
        )
        travel.limits.lower.position = 0.0
        travel.limits.upper.position = PUSHER_CLEARANCE + 2 * reach
        with world.modify_world():
            world.add_kinematic_structure_entity(pusher)
            world.add_degree_of_freedom(travel)
            world.add_connection(
                PrismaticConnection(
                    name=PrefixedName(PUSHER_RAIL_NAME),
                    parent=world.root,
                    child=pusher,
                    raw_dof=travel,
                    axis=Vector3.Y(reference_frame=world.root),
                    parent_T_connection_expression=(
                        HomogeneousTransformationMatrix.from_xyz_rpy(
                            x=float(stands_at.x),
                            y=float(stands_at.y) - reach - PUSHER_CLEARANCE,
                            z=self.world_builder.table_top_z + PUSHER_SCALE.z / 2,
                        )
                    ),
                )
            )

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
            LetTheSceneSettle(name=SortingStep.SETTLE, scene=self.simulation),
            PushThePiece(
                name=SortingStep.PUSH,
                category=self.pushed_category,
                scene=self.simulation,
            ),
            AskTheQuestion(name=SortingStep.ANSWER, scene=self.simulation),
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

    @property
    def acted_on_category(self) -> Optional[MontessoriShapeCategory]:
        return self.held_category

    def goal(self, world: World) -> Goal[World]:
        """
        Success is the robot still holding that piece when the question is asked.

        :param world: The world the trial is running in.
        """
        return ThePieceIsHeld(world=world, category=self.held_category)

    def steps(self, world: World) -> Sequence[ScenarioStep[World]]:
        return [
            LetTheSceneSettle(name=SortingStep.SETTLE, scene=self.simulation),
            PickThePieceUp(
                name=SortingStep.PICK_UP,
                category=self.held_category,
                scene=self.simulation,
            ),
            AskTheQuestion(name=SortingStep.ANSWER, scene=self.simulation),
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
