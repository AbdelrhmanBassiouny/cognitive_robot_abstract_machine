"""
The Montessori sorting scenes and the scripted runs over them: that a layout places the
pieces it names where it says, that a scene built from one really has the property it is
built for, and that each scripted run leaves the world in the state its goal asks about.

Every test here builds its world headless, on the test dataset's own grasping robot
rather than on Tracy, whose description is a ROS package a checkout need not have.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy
import pytest
from typing_extensions import Dict, List, Type

from coraplex.datastructures.enums import ExecutionType

from experiments.montessori.pieces import FULL_SIZE_PIECES, KNOWN_PIECES
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from experiments.montessori.scenarios import (
    BoardOnItsOwnTable,
    CENTIMETRES_PER_METRE,
    CONTAINED_IN_ITS_LANDING_REGION,
    DEFAULT_VIDEO_DIRECTORY_NAME,
    DetectionRelabelled,
    HOW_FAR_A_MOVED_HOLE_GOES,
    LayoutArea,
    LayoutAsFound,
    LightingChanged,
    LookAtTheScene,
    MontessoriEnvironmentVariable,
    MountedRobot,
    PUSHER_NAME,
    PUSHER_RAIL_NAME,
    PUSHER_SCALE,
    PerceivedPoseOffset,
    PerceivingWorldBuilder,
    PerturbationOfTheNextLook,
    PieceHeldWhileTheQuestionIsAsked,
    PieceLayout,
    PiecePlacement,
    PiecePushedWhileTheRobotIsIdle,
    PieceShoved,
    RealScene,
    RobotSortsAPiece,
    SceneRecording,
    SimulatedScene,
    SortingScene,
    SortingStep,
    TargetHoleMoved,
    TheSceneIsUndisturbed,
    ThePieceIsHeld,
    ThePieceIsInItsHole,
    ThePieceMovedAndTheRobotDidNot,
    TABLE_TOP_Z,
    TheSceneStandsStill,
    TracyHoldsAPiece,
    TracyIsIdleWhileAPieceIsPushed,
    TracySortsAPiece,
    TracyWatchesTheSceneStandStill,
)
from experiments.montessori.perception.simulated_setup import (
    camera_over_the_table,
)
from experiments.montessori.exceptions import (
    HoleHasNoLandingRegionError,
    NoSuchPieceError,
    RealRunCannotBeFilmed,
    RealRunNeedsAPerceivedScene,
    ScenarioRunsOnlyInSimulation,
    SceneNotBuiltYet,
)
from experiments.montessori.world import MontessoriWorld
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.world import BOARD_POSITION, BOARD_SCALE
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.scenarios.runner import ScenarioRunner
from experiments.scenarios.scenario import AbsentPerson
from segmind.datastructures.events import TranslationEvent
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.adapters.multi_sim import MujocoLight
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.adapters.multi_sim import MultiSimSynchronizer
from semantic_digital_twin.world_description.connections import (
    FixedConnection,
    PrismaticConnection,
)
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import Point3
from semantic_digital_twin.spatial_types.spatial_types import Vector3
from semantic_digital_twin.world import World

from .dataset import montessori_scene_fixtures
from .dataset.synthetic_grasping_robot import SyntheticGraspingRobot

pytest_plugins = [montessori_scene_fixtures.__name__]

# %% what every scene here is built on

SEED = 20260908
"""
The seed every layout in this module is drawn from, so a failure is reproducible.
"""

A_TENTH_OF_A_MILLIMETRE = 0.0001
"""
How far a place is allowed to move and still count as the same place, in metres.

A grasp closes on a piece and moves it a little as it takes hold; this is what
distinguishes that from the piece having been carried somewhere.
"""

WHERE_THE_ARM_IS_BOLTED = Point3(0.25, 0.0, 0.5)
"""
Where the fixed-arm robot stands, in the world root frame.

The same place :mod:`test_montessori_world` bolts it: on the near side of the Montessori
table, at the table's own working height.
"""

HOW_FAR_ASIDE_THE_ARM_IS_BOLTED_INSTEAD = 0.1
"""
How far from where every scene here bolts the arm the one scene that bolts it elsewhere
puts it, in metres.

Any distance the arm could not have drifted serves; a tenth of a metre is one it could
not.
"""

HOW_MUCH_HIGHER_ANOTHER_SCENES_TABLE_STANDS = 0.1
"""
How far above this package's own table the scene a test brings of its own stands its
pieces, in metres.

Any height a piece would visibly stand off this table serves; a tenth of a metre is far
enough that a piece stood at the wrong one could not be read as rounding.
"""

WHERE_THE_CAMERA_LOOKS_FROM = Point3(0.6, 0.0, 1.2)
"""
The viewpoint the near-ambiguous layout is ambiguous from.

A layout is only ambiguous with respect to somewhere to look from, so the scene that
needs one states it rather than assuming a camera the world does not yet carry.
"""


def mounted_arm() -> MountedRobot:
    """
    The grasping robot of the test dataset, bolted where every scene here bolts it.
    """
    return MountedRobot(position=WHERE_THE_ARM_IS_BOLTED)


def board_and_the_arm() -> BoardOnItsOwnTable:
    """
    The scene every run here is set in: the board on the table this package builds, with
    the grasping robot bolted in front of it.
    """
    return BoardOnItsOwnTable(robot=mounted_arm())


@dataclass
class WorldBuilderThatKeepsWhatItBuilt(BoardOnItsOwnTable):
    """
    A scene builder that hands back every scene it built, so a test can say whether a
    scenario ran in one of them or in a scene of its own.
    """

    built: List[World] = field(default_factory=list)
    """
    Every scene this has been asked for, in the order it was asked for them.
    """

    def build(self, robot_type: Type[AbstractRobot]) -> World:
        built = super().build(robot_type)
        self.built.append(built)
        return built


@dataclass
class WorldBuilderWhoseLookFindsTheCubeShoved(
    BoardOnItsOwnTable, PerceivingWorldBuilder
):
    """
    A scene builder standing in for one whose scene is perceived: every look it takes
    after the first finds the cube shoved by a stated displacement, as a camera would
    once the person at the table had shoved it, and the world holds the cube there.

    A displacement of nothing stands in for a person who did nothing.
    """

    shoved_by: Vector3 = field(kw_only=True)
    """
    How far each look finds the cube from where the look before found it.
    """

    built: List[World] = field(default_factory=list)
    """
    Every scene this has been asked for, in the order it was asked for them.
    """

    looks_taken: int = 0
    """
    How often the scene has been looked at again since it was built.
    """

    def build(self, robot_type: Type[AbstractRobot]) -> World:
        built = super().build(robot_type)
        self.built.append(built)
        return built

    def perceive(self) -> None:
        self.looks_taken += 1
        scene = SortingScene(self.built[-1])
        found_at = scene.position_of(MontessoriShapeCategory.CUBE)
        scene.stand_the_piece_at(
            MontessoriShapeCategory.CUBE,
            Point3(
                float(found_at.x) + float(self.shoved_by.x),
                float(found_at.y) + float(self.shoved_by.y),
                float(found_at.z) + float(self.shoved_by.z),
            ),
        )


@dataclass
class WorldBuilderWhoseTableStandsHigher(BoardOnItsOwnTable):
    """
    A scene builder that stands its pieces higher than this package's own table does,
    which is the difference a scene brought from elsewhere makes.

    The table it builds is unchanged; what differs is the height it says its pieces
    stand at, since that is what a scenario has to read rather than assume.
    """

    @property
    def table_top_z(self) -> float:
        return TABLE_TOP_Z + HOW_MUCH_HIGHER_ANOTHER_SCENES_TABLE_STANDS


class SyntheticGrasperSortsAPiece(RobotSortsAPiece[World, SyntheticGraspingRobot]):
    """
    The pick-and-place run, on the robot this test suite can actually build.
    """


class SyntheticGrasperWatchesTheSceneStandStill(
    TheSceneStandsStill[World, SyntheticGraspingRobot]
):
    """
    The static run, on the robot this test suite can actually build.
    """


class SyntheticGrasperIsIdleWhileAPieceIsPushed(
    PiecePushedWhileTheRobotIsIdle[World, SyntheticGraspingRobot]
):
    """
    The external-push run, on the robot this test suite can actually build.
    """


class SyntheticGrasperHoldsAPiece(
    PieceHeldWhileTheQuestionIsAsked[World, SyntheticGraspingRobot]
):
    """
    The piece-in-the-gripper run, on the robot this test suite can actually build.
    """


@pytest.fixture
def area() -> LayoutArea:
    """
    The patch of table a layout puts its pieces on.
    """
    return LayoutArea.on_the_table_beside_the_board()


# %% where the pieces stand


def test_a_random_layout_places_every_known_piece_once(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)

    assert [placement.piece for placement in layout.placements] == list(KNOWN_PIECES)


def test_a_random_layout_stands_every_piece_inside_the_area_it_was_given(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)

    assert all(area.contains(placement) for placement in layout.placements)


def test_a_random_layout_is_the_same_layout_every_time_its_seed_is(area):
    first = PieceLayout.randomized(seed=SEED, area=area)
    again = PieceLayout.randomized(seed=SEED, area=area)

    assert first.placements == again.placements


def test_a_random_layout_differs_when_its_seed_does(area):
    assert (
        PieceLayout.randomized(seed=SEED, area=area).placements
        != PieceLayout.randomized(seed=SEED + 1, area=area).placements
    )


def test_a_random_layout_leaves_room_between_every_pair_of_pieces(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)

    for one, other in _every_pair(layout.placements):
        assert one.distance_to(other) >= one.piece.radius + other.piece.radius


def test_a_partial_layout_places_only_the_pieces_it_names(area):
    named = (MontessoriShapeCategory.CUBE, MontessoriShapeCategory.CYLINDER)

    layout = PieceLayout.partial(seed=SEED, area=area, categories=named)

    assert tuple(placement.piece.category for placement in layout.placements) == named


def test_a_nearly_ambiguous_layout_stands_the_cube_and_the_cylinder_at_one_depth(area):
    layout = PieceLayout.nearly_ambiguous(
        seed=SEED, area=area, viewpoint=WHERE_THE_CAMERA_LOOKS_FROM
    )

    cube = layout.placement_of(MontessoriShapeCategory.CUBE)
    cylinder = layout.placement_of(MontessoriShapeCategory.CYLINDER)
    assert cube.depth_from(WHERE_THE_CAMERA_LOOKS_FROM) == pytest.approx(
        cylinder.depth_from(WHERE_THE_CAMERA_LOOKS_FROM)
    )


def test_a_nearly_ambiguous_layout_stands_the_two_pieces_clear_of_each_other(area):
    layout = PieceLayout.nearly_ambiguous(
        seed=SEED, area=area, viewpoint=WHERE_THE_CAMERA_LOOKS_FROM
    )

    cube = layout.placement_of(MontessoriShapeCategory.CUBE)
    cylinder = layout.placement_of(MontessoriShapeCategory.CYLINDER)
    assert cube.distance_to(cylinder) >= cube.piece.radius + cylinder.piece.radius


def test_a_nearly_ambiguous_layout_stands_the_two_pieces_nearer_than_chance_would(area):
    """
    The "near" in near-ambiguous: sharing a depth is what the scene is built for, but a
    scene where the two also stand far apart is not confusable, so the layout takes the
    closest placement its area allows rather than the first one it draws.
    """
    ambiguous = PieceLayout.nearly_ambiguous(
        seed=SEED, area=area, viewpoint=WHERE_THE_CAMERA_LOOKS_FROM
    )
    drawn_freely = PieceLayout.randomized(seed=SEED, area=area)

    assert _how_far_the_cube_stands_from_the_cylinder(
        ambiguous
    ) < _how_far_the_cube_stands_from_the_cylinder(drawn_freely)


# %% the scene a layout builds


def test_a_built_scene_stands_every_piece_where_its_layout_says(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    )

    world = scenario.build_world()

    scene = SortingScene(world)
    for placement in layout.placements:
        position = scene.position_of(placement.piece.category)
        assert float(position.x) == pytest.approx(placement.x)
        assert float(position.y) == pytest.approx(placement.y)


def test_a_built_scene_rests_every_piece_on_the_table_rather_than_in_it(area):
    """
    What ties a placement's stated height to the world it builds: a placement says where
    a piece stands on the table, and the scene has to put its lowest point exactly on
    the table's surface rather than at some height in the table's own frame.
    """
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    )

    world = scenario.build_world()

    scene = SortingScene(world)
    for placement in layout.placements:
        body = scene.body_of(placement.piece.category)
        lowest_point = body.collision.as_bounding_box_collection_in_frame(
            world.root
        ).bounding_box()
        assert float(lowest_point.min_z) == pytest.approx(TABLE_TOP_Z)


def test_a_built_scene_holds_only_the_pieces_a_partial_layout_names(area):
    layout = PieceLayout.partial(
        seed=SEED,
        area=area,
        categories=(MontessoriShapeCategory.CUBE, MontessoriShapeCategory.CYLINDER),
    )
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    )

    world = scenario.build_world()

    assert SortingScene(world).categories == {
        MontessoriShapeCategory.CUBE,
        MontessoriShapeCategory.CYLINDER,
    }


def test_a_built_scene_mounts_the_robot_its_type_names(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    world = scenario.build_world()

    assert isinstance(SortingScene(world).robot, SyntheticGraspingRobot)


# %% the layout a scene is found in


def test_a_stated_layout_is_the_layout_the_trial_starts_in(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    )

    scenario.build_world()

    assert scenario.starting_layout is layout


def test_a_scenario_asked_where_its_pieces_stood_before_it_built_a_scene_says_so(
    area,
):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    with pytest.raises(SceneNotBuiltYet) as asked:
        scenario.starting_layout

    assert asked.value.scenario_name == scenario.name


def test_a_layout_as_found_leaves_every_piece_where_the_scene_built_it():
    """
    The pieces stand where the scene's own builder put them, which is where a scene
    built without any layout stands them.
    """
    builder = board_and_the_arm()
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=LayoutAsFound(), world_builder=builder
    )
    as_built = SortingScene(builder.build(SyntheticGraspingRobot))

    scene = SortingScene(scenario.build_world())

    assert scene.categories == as_built.categories
    for category in as_built.categories:
        assert scene.position_of(category).to_np() == pytest.approx(
            as_built.position_of(category).to_np()
        )


def test_a_layout_as_found_reads_where_every_piece_of_the_set_stands_off_the_scene():
    """
    The scene this package builds also stands a disk and a sphere, which belong to no
    set of pieces and so to no layout.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=LayoutAsFound(), world_builder=board_and_the_arm()
    )

    world = scenario.build_world()

    found = scenario.starting_layout
    assert type(found) is PieceLayout
    of_the_set = [
        shape
        for shape in world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category in FULL_SIZE_PIECES.by_category
    ]
    assert len(found.placements) == len(of_the_set)
    for placement, shape in zip(found.placements, of_the_set):
        assert placement.piece is FULL_SIZE_PIECES.by_category[shape.shape_category]
        stands_at = shape.root.global_transform.to_position()
        assert placement.x == pytest.approx(float(stands_at.x))
        assert placement.y == pytest.approx(float(stands_at.y))


def test_a_layout_read_off_a_scene_keeps_how_far_each_piece_is_turned(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    )
    world = scenario.build_world()

    read = PieceLayout.read_from(world, FULL_SIZE_PIECES)

    assert read.categories == layout.categories
    for placement in layout.placements:
        read_back = read.placement_of(placement.piece.category)
        assert read_back.piece is placement.piece
        assert read_back.x == pytest.approx(placement.x)
        assert read_back.y == pytest.approx(placement.y)
        assert read_back.yaw == pytest.approx(placement.yaw)


# %% standing a piece somewhere


def test_a_shoved_piece_keeps_how_far_it_was_turned(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    world = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    ).build_world()
    scene = SortingScene(world)
    turned_by = layout.placement_of(MontessoriShapeCategory.CUBE).yaw

    PieceShoved(
        step=SortingStep.SETTLE,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).apply(world)

    _, _, yaw = (
        scene.body_of(MontessoriShapeCategory.CUBE)
        .global_transform.to_rotation_matrix()
        .to_rpy()
    )
    assert float(yaw) == pytest.approx(turned_by)


def test_a_piece_fixed_where_it_stands_is_moved_by_restating_where_it_is_fixed():
    """
    A piece a look stood is welded to the world, so it has no degree of freedom to move
    it by; standing it elsewhere restates the weld.
    """
    world = MontessoriWorld(shapes_are_movable=False).world
    scene = SortingScene(world)
    cube = scene.body_of(MontessoriShapeCategory.CUBE)
    assert type(cube.parent_connection) is FixedConnection
    stood_at = scene.position_of(MontessoriShapeCategory.CUBE).to_np()
    moved_to = Point3(
        float(stood_at[0]) + float(HOW_FAR_A_PERTURBATION_MOVES_SOMETHING.x),
        float(stood_at[1]),
        float(stood_at[2]),
    )

    scene.stand_the_piece_at(MontessoriShapeCategory.CUBE, moved_to)

    assert type(cube.parent_connection) is FixedConnection
    assert scene.position_of(MontessoriShapeCategory.CUBE).to_np()[
        :3
    ].flatten() == pytest.approx(moved_to.to_np()[:3].flatten())


# %% a run on the robot


def a_run_on_the_robot(
    area, shoved_by: Vector3 = Vector3(0.0, 0.0, 0.0)
) -> tuple[TheSceneStandsStill, WorldBuilderWhoseLookFindsTheCubeShoved]:
    """
    The static run on the robot, in a scene whose every later look finds the cube shoved
    by the given displacement.

    :param area: The patch of table the pieces stand on.
    :param shoved_by: How far the person at the table is found to have shoved the cube.
    """
    builder = WorldBuilderWhoseLookFindsTheCubeShoved(
        robot=mounted_arm(), shoved_by=shoved_by
    )
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=builder,
        execution_type=ExecutionType.REAL,
    )
    return scenario, builder


def test_a_run_on_the_robot_is_carried_by_the_real_world(area):
    """
    Nothing simulates a scene on the robot: the trial runs with no simulation built and
    no synchronizer left on the world.
    """
    scenario, _ = a_run_on_the_robot(area)
    runner = ScenarioRunner(person=AbsentPerson())

    trial = runner.run_trial(scenario)

    assert type(scenario.physics) is RealScene
    assert trial.outcome is TrialOutcome.SUCCEEDED
    assert trial.execution_type is ExecutionType.REAL
    assert (
        MultiSimSynchronizer.all_callbacks_of_this_type_from_world(
            scenario.physics.world
        )
        == []
    )


def test_a_run_on_the_robot_needs_a_scene_it_can_look_at(area):
    """
    What the person at the table changes reaches the world only through a look, so a
    scene that is built rather than perceived cannot be run on the robot.
    """
    with pytest.raises(RealRunNeedsAPerceivedScene) as refused:
        SyntheticGrasperWatchesTheSceneStandStill(
            layout=PieceLayout.randomized(seed=SEED, area=area),
            world_builder=board_and_the_arm(),
            execution_type=ExecutionType.REAL,
        )

    assert refused.value.scenario_name == TheSceneStandsStill.name


def test_a_shove_on_the_robot_is_the_persons_and_is_learned_of_by_looking(area):
    scenario, builder = a_run_on_the_robot(
        area, shoved_by=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING
    )
    person = AbsentPerson()
    shove = PieceShoved(
        step=SortingStep.SETTLE,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    )

    trial = ScenarioRunner(person=person).run_trial(scenario, perturbations=[shove])

    assert person.asked == [shove.instruction_for_a_person()]
    assert builder.looks_taken == 1
    assert trial.outcome is TrialOutcome.FAILED


def test_a_shove_the_look_does_not_find_leaves_the_world_as_it_was(area):
    """
    The run never writes the shove into the world itself: where the look finds the cube
    where it stood, the scene counts as undisturbed however the person was asked.
    """
    scenario, builder = a_run_on_the_robot(area)
    shove = PieceShoved(
        step=SortingStep.SETTLE,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    )

    trial = ScenarioRunner(person=AbsentPerson()).run_trial(
        scenario, perturbations=[shove]
    )

    assert builder.looks_taken == 1
    assert trial.outcome is TrialOutcome.SUCCEEDED
    stood_at = scenario.starting_layout.placement_of(MontessoriShapeCategory.CUBE)
    assert SortingScene(builder.built[-1]).stands_at(
        MontessoriShapeCategory.CUBE, stood_at
    )


def test_a_run_on_the_robot_cannot_be_filmed(area):
    with pytest.raises(RealRunCannotBeFilmed) as refused:
        SyntheticGrasperWatchesTheSceneStandStill(
            layout=PieceLayout.randomized(seed=SEED, area=area),
            world_builder=board_and_the_arm(),
            execution_type=ExecutionType.REAL,
            filmed=True,
        )

    assert refused.value.scenario_name == TheSceneStandsStill.name


@pytest.mark.parametrize(
    "scenario_class, acted_on",
    [
        (SyntheticGrasperSortsAPiece, "sorted_category"),
        (SyntheticGrasperIsIdleWhileAPieceIsPushed, "pushed_category"),
        (SyntheticGrasperHoldsAPiece, "held_category"),
    ],
)
def test_a_script_the_simulation_drives_cannot_run_on_the_robot(
    scenario_class, acted_on, area
):
    with pytest.raises(ScenarioRunsOnlyInSimulation) as refused:
        scenario_class(
            layout=PieceLayout.randomized(seed=SEED, area=area),
            world_builder=board_and_the_arm(),
            execution_type=ExecutionType.REAL,
            **{acted_on: MontessoriShapeCategory.CUBE},
        )

    assert refused.value.scenario_name == scenario_class.name


# %% the scene a scenario is given


def test_a_scenario_runs_in_the_scene_the_builder_it_was_given_built(area):
    builder = WorldBuilderThatKeepsWhatItBuilt(robot=mounted_arm())
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), world_builder=builder
    )

    world = scenario.build_world()

    assert builder.built == [world]


def test_a_scenario_stands_its_pieces_on_the_table_the_scene_it_was_given_says(area):
    builder = WorldBuilderWhoseTableStandsHigher(robot=mounted_arm())
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=builder
    )

    world = scenario.build_world()

    scene = SortingScene(world)
    for placement in layout.placements:
        standing_on = (
            scene.body_of(placement.piece.category)
            .collision.as_bounding_box_collection_in_frame(world.root)
            .bounding_box()
        )
        assert float(standing_on.min_z) == pytest.approx(builder.table_top_z)


def test_a_scenario_bolts_its_robot_where_the_scene_it_was_given_says(area):
    bolted_elsewhere = MountedRobot(
        position=Point3(
            float(WHERE_THE_ARM_IS_BOLTED.x) + HOW_FAR_ASIDE_THE_ARM_IS_BOLTED_INSTEAD,
            float(WHERE_THE_ARM_IS_BOLTED.y) + HOW_FAR_ASIDE_THE_ARM_IS_BOLTED_INSTEAD,
            float(WHERE_THE_ARM_IS_BOLTED.z),
        )
    )
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=BoardOnItsOwnTable(robot=bolted_elsewhere),
    )

    world = scenario.build_world()

    stands_at = SortingScene(world).robot.root.global_transform.to_position()
    assert float(stands_at.x) == pytest.approx(float(bolted_elsewhere.position.x))
    assert float(stands_at.y) == pytest.approx(float(bolted_elsewhere.position.y))
    assert float(stands_at.z) == pytest.approx(float(bolted_elsewhere.position.z))


# %% the scripted runs


def test_the_static_run_leaves_every_piece_where_the_layout_put_it(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, world_builder=board_and_the_arm()
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_static_run_performs_no_step_that_moves_anything(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    steps = scenario.steps(scenario.build_world())

    assert [step.name for step in steps] == [SortingStep.SETTLE, SortingStep.ANSWER]


def test_the_pick_and_place_run_puts_the_piece_through_its_own_hole(area):
    scenario = SyntheticGrasperSortsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        sorted_category=MontessoriShapeCategory.CUBE,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_pushed_piece_run_moves_the_piece_and_not_the_robot(area):
    scenario = SyntheticGrasperIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        pushed_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_held_piece_run_still_holds_the_piece_when_the_question_is_asked(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_held_piece_run_ends_with_the_robot_holding_the_piece(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )
    world = scenario.build_world()

    for step in scenario.steps(world):
        step.perform(world)

    assert SortingScene(world).is_held(MontessoriShapeCategory.CYLINDER)


# %% the physics the scene runs under


def test_a_piece_left_above_the_table_falls_onto_it_when_the_scene_settles(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    world = scenario.build_world()
    scene = SortingScene(world)
    stood_at = scene.position_of(MontessoriShapeCategory.CUBE)
    scene.stand_the_piece_at(
        MontessoriShapeCategory.CUBE,
        Point3(stood_at.x, stood_at.y, float(stood_at.z) + 0.1),
    )

    scenario.physics.settle()

    rested_at = scene.position_of(MontessoriShapeCategory.CUBE)
    assert float(rested_at.z) == pytest.approx(float(stood_at.z), abs=1e-3)


def test_the_pushed_scene_stands_a_pusher_on_a_rail_beside_the_piece(area):
    scenario = SyntheticGrasperIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        pushed_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
    )

    world = scenario.build_world()

    pusher = world.get_body_by_name(PUSHER_NAME)
    assert isinstance(
        world.get_connection_by_name(PUSHER_RAIL_NAME), PrismaticConnection
    )
    piece = SortingScene(world).position_of(MontessoriShapeCategory.TRIANGULAR_PRISM)
    stands_at = pusher.global_transform.to_position()
    assert float(stands_at.y) < float(piece.y)


def test_the_push_moves_the_piece_along_the_rail_the_pusher_slides_on(area):
    scenario = SyntheticGrasperIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        pushed_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
    )
    world = scenario.build_world()
    scene = SortingScene(world)
    steps = {step.name: step for step in scenario.steps(world)}
    steps[SortingStep.SETTLE].perform(world)
    stood_at = scene.position_of(MontessoriShapeCategory.TRIANGULAR_PRISM)

    steps[SortingStep.PUSH].perform(world)

    shoved_to = scene.position_of(MontessoriShapeCategory.TRIANGULAR_PRISM)
    assert float(shoved_to.y) > float(stood_at.y)
    assert float(shoved_to.z) == pytest.approx(float(stood_at.z), abs=1e-3)


def test_the_pusher_ends_the_push_up_against_the_piece_it_shoved(area):
    scenario = SyntheticGrasperIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        pushed_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
    )
    world = scenario.build_world()
    steps = {step.name: step for step in scenario.steps(world)}
    steps[SortingStep.SETTLE].perform(world)
    steps[SortingStep.PUSH].perform(world)

    piece = SortingScene(world).position_of(MontessoriShapeCategory.TRIANGULAR_PRISM)
    pusher = world.get_body_by_name(PUSHER_NAME).global_transform.to_position()

    reach = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM].radius
    assert float(piece.y) - float(pusher.y) <= reach + PUSHER_SCALE.y


def test_picking_a_piece_up_lifts_it_from_where_it_stood_rather_than_fetching_it(area):
    """
    The robot goes to the piece: it comes away straight up from where it stood, rather
    than arriving at wherever the gripper happened to be.
    """
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )
    world = scenario.build_world()
    scene = SortingScene(world)
    steps = {step.name: step for step in scenario.steps(world)}
    steps[SortingStep.SETTLE].perform(world)
    stood_at = scene.position_of(MontessoriShapeCategory.CYLINDER)

    steps[SortingStep.PICK_UP].perform(world)

    assert scene.is_held(MontessoriShapeCategory.CYLINDER)
    held_at = scene.position_of(MontessoriShapeCategory.CYLINDER)
    assert (float(held_at.x), float(held_at.y)) == pytest.approx(
        (float(stood_at.x), float(stood_at.y)), abs=A_TENTH_OF_A_MILLIMETRE
    )
    assert float(held_at.z) > float(stood_at.z)


def test_a_released_piece_is_outside_its_landing_region_until_it_has_fallen(area):
    scenario = SyntheticGrasperSortsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        sorted_category=MontessoriShapeCategory.CUBE,
    )
    world = scenario.build_world()
    scene = SortingScene(world)
    steps = {step.name: step for step in scenario.steps(world)}
    steps[SortingStep.SETTLE].perform(world)
    steps[SortingStep.PICK_UP].perform(world)
    carried = InsideOf(
        scene.body_of(MontessoriShapeCategory.CUBE),
        scene.landing_region_for(MontessoriShapeCategory.CUBE),
    ).compute_containment_ratio()

    steps[SortingStep.PUT_DOWN].perform(world)

    assert carried < CONTAINED_IN_ITS_LANDING_REGION
    assert scene.is_in_its_hole(MontessoriShapeCategory.CUBE)


def test_a_piece_standing_on_the_table_is_not_in_its_hole(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    world = scenario.build_world()

    assert not SortingScene(world).is_in_its_hole(MontessoriShapeCategory.CUBE)


def test_the_robot_holds_nothing_before_it_has_picked_anything_up(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )

    world = scenario.build_world()

    assert not SortingScene(world).is_held(MontessoriShapeCategory.CYLINDER)


def test_a_picked_up_piece_hangs_from_the_frame_the_robot_grasps_with(area):
    """
    A robot action takes hold of the piece, which is what re-parents it onto the
    gripper; nothing here moves it there.
    """
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )
    world = scenario.build_world()
    scene = SortingScene(world)
    steps = {step.name: step for step in scenario.steps(world)}
    steps[SortingStep.SETTLE].perform(world)

    steps[SortingStep.PICK_UP].perform(world)

    piece = scene.body_of(MontessoriShapeCategory.CYLINDER)
    assert piece.parent_connection.parent is scene.gripper


# %% the space a hole drops a piece into


def test_a_landing_region_is_no_wider_than_the_hole_it_lies_under(area):
    """
    It is the space the hole leaves open, so it is the hole's own opening carried down
    rather than a stretch of table chosen around it.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    scene = SortingScene(scenario.build_world())

    for category in scene.categories:
        hole = scene.hole_for(category)
        opening = _size_of(hole.root.area)
        landing = _size_of(scene.landing_region_for(category).area)
        assert (landing[0], landing[1]) == pytest.approx((opening[0], opening[1]))


def test_a_landing_region_reaches_from_the_table_to_the_top_of_the_board(area):
    """
    The whole shaft, so a piece is inside it wherever in the shaft it came to rest, and
    no higher, so a piece standing on the board is outside it.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    scene = SortingScene(scenario.build_world())
    region = scene.landing_region_for(MontessoriShapeCategory.CUBE)

    top = float(region.global_transform.to_position().z) + _size_of(region.area)[2] / 2

    assert top == pytest.approx(float(BOARD_POSITION.z) + BOARD_SCALE.z / 2)


def test_a_landing_region_is_the_one_its_own_hole_carries(area):
    """
    Read off the hole rather than looked up beside it, so no two spellings of a name can
    drift apart.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    scene = SortingScene(scenario.build_world())

    for category in scene.categories:
        assert (
            scene.landing_region_for(category)
            is scene.hole_for(category).landing_region
        )


def test_a_hole_with_nothing_measured_under_it_says_so(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    scene = SortingScene(scenario.build_world())
    hole = scene.hole_for(MontessoriShapeCategory.CUBE)
    hole.landing_region = None

    with pytest.raises(HoleHasNoLandingRegionError):
        scene.landing_region_for(MontessoriShapeCategory.CUBE)


def test_a_scene_asked_about_a_piece_it_does_not_hold_says_so(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.partial(
            seed=SEED, area=area, categories=(MontessoriShapeCategory.CUBE,)
        ),
        world_builder=board_and_the_arm(),
    )
    scene = SortingScene(scenario.build_world())

    with pytest.raises(NoSuchPieceError):
        scene.shape_of(MontessoriShapeCategory.CYLINDER)


# %% what a run counts as success


@pytest.mark.parametrize(
    "goal, sentence",
    [
        (
            TheSceneIsUndisturbed(
                world=variable(World, []), layout=variable(PieceLayout, [])
            ),
            "a World is undisturbed",
        ),
        (
            ThePieceIsInItsHole(
                world=variable(World, []), category=MontessoriShapeCategory.CUBE
            ),
            "CUBE is in its own hole",
        ),
        (
            ThePieceMovedAndTheRobotDidNot(
                world=variable(World, []),
                category=MontessoriShapeCategory.CUBE,
                layout=variable(PieceLayout, []),
            ),
            "CUBE is displaced from a PieceLayout",
        ),
        (
            ThePieceIsHeld(
                world=variable(World, []), category=MontessoriShapeCategory.CYLINDER
            ),
            "CYLINDER is held",
        ),
    ],
)
def test_every_goal_verbalizes_as_the_clause_it_states(goal, sentence):
    assert verbalize_expression(goal) == sentence


# %% the change a run applies to its world


def test_the_lighting_change_gives_the_world_a_light_of_its_own(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    world = scenario.build_world()

    LightingChanged(step=SortingStep.SETTLE).apply(world)

    [light] = [
        additional_property
        for body in world.bodies
        for additional_property in body.simulator_additional_properties
        if isinstance(additional_property, MujocoLight)
    ]
    assert light.directional


HOW_FAR_A_PERTURBATION_MOVES_SOMETHING = Vector3(0.0, HOW_FAR_A_MOVED_HOLE_GOES, 0.0)
"""
The displacement every perturbation in this module is given.

The distance a moved hole is specified at, reused for the pieces and the reported places
so a test says what moved rather than how far.
"""


def a_scene_to_perturb(area) -> World:
    """
    The world a perturbation is applied to: the static run's, which nothing else has
    acted on, so what moved in it is the perturbation's doing.

    :param area: The patch of table the pieces stand on.
    """
    return SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    ).build_world()


def test_a_moved_target_hole_stands_the_displacement_away_from_where_it_was(area):
    world = a_scene_to_perturb(area)
    hole = SortingScene(world).hole_for(MontessoriShapeCategory.CUBE).root
    stood_at = hole.global_transform.to_position().to_np()

    TargetHoleMoved(
        step=SortingStep.PUT_DOWN,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).apply(world)

    moved_by = hole.global_transform.to_position().to_np() - stood_at
    assert numpy.linalg.norm(moved_by[:3]) == pytest.approx(HOW_FAR_A_MOVED_HOLE_GOES)


def test_a_moved_target_hole_carries_the_boards_other_holes_with_it(area):
    """
    A hole is cut into the board rather than standing beside it, so the board is what
    moves and every hole in it travels the same distance.

    Naming one hole says which displacement is being stated, not that the board bends
    around it.
    """
    world = a_scene_to_perturb(area)
    scene = SortingScene(world)
    alongside = MontessoriShapeCategory.CYLINDER
    stood_at = scene.hole_for(alongside).root.global_transform.to_position().to_np()

    TargetHoleMoved(
        step=SortingStep.PUT_DOWN,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).apply(world)

    moved_by = (
        scene.hole_for(alongside).root.global_transform.to_position().to_np() - stood_at
    )
    assert numpy.linalg.norm(moved_by[:3]) == pytest.approx(HOW_FAR_A_MOVED_HOLE_GOES)


def test_a_shove_is_the_translation_of_the_piece_by_its_displacement(area):
    world = a_scene_to_perturb(area)
    scene = SortingScene(world)
    cube = scene.body_of(MontessoriShapeCategory.CUBE)
    stood_at = cube.global_transform.to_np()

    event = PieceShoved(
        step=SortingStep.SETTLE,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).event_in(world)

    assert type(event) is TranslationEvent
    assert event.tracked_object is cube
    assert numpy.allclose(event.start_pose.to_homogeneous_matrix().to_np(), stood_at)
    ended_at = event.current_pose.to_homogeneous_matrix().to_np()
    assert numpy.allclose(ended_at[:3, :3], stood_at[:3, :3])
    assert (ended_at[:3, 3] - stood_at[:3, 3]) == pytest.approx(
        HOW_FAR_A_PERTURBATION_MOVES_SOMETHING.to_np()[:3].flatten()
    )


def test_a_moved_target_hole_is_the_translation_of_the_board(area):
    world = a_scene_to_perturb(area)
    board = SortingScene(world).board.root

    event = TargetHoleMoved(
        step=SortingStep.PUT_DOWN,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).event_in(world)

    assert type(event) is TranslationEvent
    assert event.tracked_object is board
    moved_by = (
        event.current_pose.to_homogeneous_matrix().to_np()[:3, 3]
        - board.global_transform.to_np()[:3, 3]
    )
    assert numpy.linalg.norm(moved_by) == pytest.approx(HOW_FAR_A_MOVED_HOLE_GOES)


def test_a_shoved_piece_stands_the_displacement_away_from_where_it_was(area):
    world = a_scene_to_perturb(area)
    scene = SortingScene(world)
    stood_at = scene.position_of(MontessoriShapeCategory.CUBE).to_np()

    PieceShoved(
        step=SortingStep.SETTLE,
        category=MontessoriShapeCategory.CUBE,
        displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).apply(world)

    moved_by = scene.position_of(MontessoriShapeCategory.CUBE).to_np() - stood_at
    assert moved_by[:3].flatten() == pytest.approx(
        HOW_FAR_A_PERTURBATION_MOVES_SOMETHING.to_np()[:3].flatten()
    )


# %% the change a run applies to what it is shown


def test_a_perturbation_of_what_is_seen_waits_on_the_world_for_the_next_look(area):
    """
    A perturbation is handed the world and the look is taken by a later step, so the
    world is what carries the one to the other.
    """
    world = a_scene_to_perturb(area)
    perturbation = PerceivedPoseOffset(
        step=SortingStep.LOOK,
        category=MontessoriShapeCategory.CUBE,
        offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    )

    perturbation.apply(world)

    [waiting] = world.get_semantic_annotations_by_type(PerturbationOfTheNextLook)
    assert waiting.perturbation is perturbation


def test_a_perturbation_of_what_is_seen_leaves_the_twin_alone(area):
    """
    What makes it a perturbation of perception rather than of the scene: the piece is
    still where it was, and only what the robot is told about it differs.
    """
    world = a_scene_to_perturb(area)
    scene = SortingScene(world)
    stood_at = scene.position_of(MontessoriShapeCategory.CUBE).to_np()

    PerceivedPoseOffset(
        step=SortingStep.LOOK,
        category=MontessoriShapeCategory.CUBE,
        offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).apply(world)

    assert scene.position_of(MontessoriShapeCategory.CUBE).to_np() == pytest.approx(
        stood_at
    )


def test_a_perceived_pose_offset_reports_the_piece_the_offset_away_from_where_it_is(
    scene,
):
    reported_at = {
        shape.category: shape.pose.to_position().to_np() for shape in scene.shapes
    }
    offset = MontessoriShapeCategory.CUBE

    PerceivedPoseOffset(
        step=SortingStep.LOOK,
        category=offset,
        offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).change_what_was_seen(scene)

    [moved] = [shape for shape in scene.shapes if shape.category is offset]
    moved_by = moved.pose.to_position().to_np() - reported_at[offset]
    assert moved_by[:3].flatten() == pytest.approx(
        HOW_FAR_A_PERTURBATION_MOVES_SOMETHING.to_np()[:3].flatten()
    )


def test_a_perceived_pose_offset_reports_every_other_piece_where_it_found_it(scene):
    reported_at = {
        shape.category: shape.pose.to_position().to_np() for shape in scene.shapes
    }

    PerceivedPoseOffset(
        step=SortingStep.LOOK,
        category=MontessoriShapeCategory.CUBE,
        offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).change_what_was_seen(scene)

    for shape in scene.shapes:
        if shape.category is MontessoriShapeCategory.CUBE:
            continue
        assert shape.pose.to_position().to_np() == pytest.approx(
            reported_at[shape.category]
        )


def test_a_look_takes_the_perturbations_it_applied_off_the_world(area):
    """
    A perturbation strikes at the one look its step named, so the step clears what it
    applied rather than leaving it to distort every later look as well.
    """
    world = a_scene_to_perturb(area)
    PerceivedPoseOffset(
        step=SortingStep.LOOK,
        category=MontessoriShapeCategory.CUBE,
        offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
    ).apply(world)
    looking = LookAtTheScene(
        name=SortingStep.LOOK,
        scene=SimulatedScene(world=world),
        camera=camera_over_the_table(world),
    )

    looking.perform(world)

    assert world.get_semantic_annotations_by_type(PerturbationOfTheNextLook) == []


def test_a_relabelled_detection_is_reported_as_the_shape_it_is_not(scene):
    actually_there = MontessoriShapeCategory.CUBE
    reported_as = MontessoriShapeCategory.DISK
    stood_at = [
        shape.pose.to_position().to_np()
        for shape in scene.shapes
        if shape.category is actually_there
    ]
    assert stood_at, "the rendered scene holds no piece of the shape being relabelled"

    DetectionRelabelled(
        step=SortingStep.LOOK,
        category=actually_there,
        reported_as=reported_as,
    ).change_what_was_seen(scene)

    assert not [shape for shape in scene.shapes if shape.category is actually_there]
    relabelled = [shape for shape in scene.shapes if shape.category is reported_as]
    assert numpy.array(
        [shape.pose.to_position().to_np() for shape in relabelled]
    ) == pytest.approx(numpy.array(stood_at))


# %% what a person at the table is asked to do instead


@pytest.mark.parametrize(
    "perturbation, names",
    [
        (
            TargetHoleMoved(
                step=SortingStep.PUT_DOWN,
                category=MontessoriShapeCategory.CUBE,
                displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
            ),
            (MontessoriShapeCategory.CUBE,),
        ),
        (
            PieceShoved(
                step=SortingStep.SETTLE,
                category=MontessoriShapeCategory.CYLINDER,
                displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
            ),
            (MontessoriShapeCategory.CYLINDER,),
        ),
        (
            PerceivedPoseOffset(
                step=SortingStep.LOOK,
                category=MontessoriShapeCategory.DISK,
                offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
            ),
            (MontessoriShapeCategory.DISK,),
        ),
        (
            DetectionRelabelled(
                step=SortingStep.LOOK,
                category=MontessoriShapeCategory.CUBE,
                reported_as=MontessoriShapeCategory.SPHERE,
            ),
            (MontessoriShapeCategory.CUBE, MontessoriShapeCategory.SPHERE),
        ),
    ],
)
def test_a_perturbation_tells_a_person_which_pieces_to_act_on(perturbation, names):
    """
    The same instance changes a simulated world and states what a person does at the
    real table, so the instruction has to say which pieces it is about.
    """
    instruction = perturbation.instruction_for_a_person()

    for named in names:
        assert named in instruction


@pytest.mark.parametrize(
    "perturbation",
    [
        TargetHoleMoved(
            step=SortingStep.PUT_DOWN,
            category=MontessoriShapeCategory.CUBE,
            displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
        ),
        PieceShoved(
            step=SortingStep.SETTLE,
            category=MontessoriShapeCategory.CYLINDER,
            displacement=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
        ),
        PerceivedPoseOffset(
            step=SortingStep.LOOK,
            category=MontessoriShapeCategory.DISK,
            offset=HOW_FAR_A_PERTURBATION_MOVES_SOMETHING,
        ),
    ],
)
def test_a_perturbation_that_moves_something_tells_a_person_how_far(perturbation):
    """
    A person cannot bring about a displacement they are not told the size of, and the
    table is measured in centimetres rather than in the metres every length is held in.
    """
    how_far = round(HOW_FAR_A_MOVED_HOLE_GOES * CENTIMETRES_PER_METRE)

    assert f"{how_far} cm" in perturbation.instruction_for_a_person()


def test_the_lighting_change_tells_a_person_to_light_the_table_differently():
    """
    The one perturbation that displaces nothing still says what a person does, since
    every perturbation has to hold on the real robot as well as in simulation.
    """
    assert (
        LightingChanged(step=SortingStep.SETTLE).instruction_for_a_person()
        == "Light the table differently."
    )


# %% running one scenario more than once


def test_every_trial_of_a_seeded_scenario_builds_the_same_scene(area):
    """
    What a seed is for: two trials of one scenario stand the pieces in the same places,
    so a difference between them is the run's and never the scene's.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    first = SortingScene(scenario.build_world())
    again = SortingScene(scenario.build_world())

    for placement in scenario.layout.placements:
        one = first.position_of(placement.piece.category)
        other = again.position_of(placement.piece.category)
        assert one.to_np() == pytest.approx(other.to_np())


# %% the scenarios the simulated demo runs


@pytest.mark.parametrize(
    "scenario_class",
    [
        TracyWatchesTheSceneStandStill,
        TracySortsAPiece,
        TracyIsIdleWhileAPieceIsPushed,
        TracyHoldsAPiece,
    ],
)
def test_every_demo_scenario_runs_on_tracy(scenario_class, area):
    """
    Which robot a scenario runs on is its bound type parameter, so this reads the
    binding rather than building a world: Tracy's description is a ROS package a
    checkout need not have, but its type is always available.
    """
    scenario = _instantiated(scenario_class, area)

    assert scenario.robot_type is Tracy


def _instantiated(scenario_class, area: LayoutArea):
    """
    One instance of a scenario class, given whatever piece its script names.
    """
    arguments = {
        "layout": PieceLayout.randomized(seed=SEED, area=area),
        "world_builder": board_and_the_arm(),
    }
    for field_name in ("sorted_category", "pushed_category", "held_category"):
        if field_name in scenario_class.__dataclass_fields__:
            arguments[field_name] = MontessoriShapeCategory.CUBE
    return scenario_class(**arguments)


# %% the video a run is filmed as


SORTED_PIECE = MontessoriShapeCategory.CUBE
"""
The piece the runs filmed here sort.
"""


@dataclass
class AFilmedRun:
    """
    What one filmed run left behind.
    """

    recording: SceneRecording
    """
    The video it was filmed as.
    """

    frames_by_the_end_of: Dict[SortingStep, int]
    """
    How many frames had been filmed by the end of each of its steps.
    """

    left_the_piece_at: List[float]
    """
    Where the sorted piece stood when the run was over, in the world root frame.
    """


@pytest.fixture(scope="module")
def a_filmed_sorting_run() -> AFilmedRun:
    """
    One filmed pick-and-place run, performed once and read by every test that asks about
    a video, since filming a run renders a frame every few changes of it.
    """
    scenario = _sorting_run(filmed=True)
    world = scenario.build_world()
    frames_by_the_end_of = {}
    for step in scenario.steps(world):
        step.perform(world)
        frames_by_the_end_of[step.name] = scenario.physics.recording.frame_count
    return AFilmedRun(
        recording=scenario.physics.recording,
        frames_by_the_end_of=frames_by_the_end_of,
        left_the_piece_at=_where_the_sorted_piece_stands(world),
    )


def test_every_step_that_acts_on_a_scene_is_filmed(a_filmed_sorting_run):
    """
    The robot's own reach is watched as well as the physics, and the video is taken up
    again after the grasp, which no simulation the run began with could follow.
    """
    frames = a_filmed_sorting_run.frames_by_the_end_of

    assert (
        0
        < frames[SortingStep.SETTLE]
        < frames[SortingStep.PICK_UP]
        < frames[SortingStep.PUT_DOWN]
    )


def test_filming_a_run_leaves_it_doing_what_it_did_unfilmed(a_filmed_sorting_run):
    """
    A filmed run is carried by the very simulation it is filmed from, so the film is
    something the run is watched through rather than something done to it.
    """
    unfilmed = _sorting_run(filmed=False)
    world = unfilmed.build_world()

    for step in unfilmed.steps(world):
        step.perform(world)

    assert _where_the_sorted_piece_stands(world) == pytest.approx(
        a_filmed_sorting_run.left_the_piece_at
    )


def test_a_filmed_run_is_written_as_one_video_where_videos_are_kept(
    a_filmed_sorting_run,
):
    """
    Written where videos of runs are kept rather than into a directory of this test's
    own: a video nobody can find is not one worth filming.
    """
    output_path = a_filmed_sorting_run.recording.write(
        SceneRecording.where_videos_are_written() / f"{RobotSortsAPiece.name}.mp4"
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert (
        len(a_filmed_sorting_run.recording.frames)
        == a_filmed_sorting_run.frames_by_the_end_of[SortingStep.ANSWER]
    )


def test_videos_are_written_where_the_environment_says(monkeypatch, tmp_path):
    monkeypatch.setenv(MontessoriEnvironmentVariable.VIDEO_DIRECTORY, str(tmp_path))

    assert SceneRecording.where_videos_are_written() == tmp_path


def test_videos_of_a_machine_that_says_nothing_are_kept_beside_its_other_temporary_files(
    monkeypatch,
):
    monkeypatch.delenv(MontessoriEnvironmentVariable.VIDEO_DIRECTORY, raising=False)

    assert (
        SceneRecording.where_videos_are_written()
        == Path(tempfile.gettempdir()) / DEFAULT_VIDEO_DIRECTORY_NAME
    )


# %% helpers


def _sorting_run(filmed: bool) -> SyntheticGrasperSortsAPiece:
    """
    The pick-and-place run every test about a video is about.

    :param filmed: Whether to film it.
    """
    return SyntheticGrasperSortsAPiece(
        layout=PieceLayout.randomized(
            seed=SEED, area=LayoutArea.on_the_table_beside_the_board()
        ),
        world_builder=board_and_the_arm(),
        sorted_category=SORTED_PIECE,
        filmed=filmed,
    )


def _where_the_sorted_piece_stands(world: World) -> List[float]:
    """
    Where the piece a filmed run sorts stands, in the world root frame.

    :param world: The world the run was performed in.
    """
    stands_at = SortingScene(world).position_of(SORTED_PIECE)
    return [float(stands_at.x), float(stands_at.y), float(stands_at.z)]


def _size_of(area) -> List[float]:
    """
    How far a region's own shapes reach along each axis, in metres.

    :param area: The shapes to measure.
    """
    bounds = area.combined_mesh.bounds
    return [float(upper - lower) for lower, upper in zip(bounds[0], bounds[1])]


def _how_far_the_cube_stands_from_the_cylinder(layout: PieceLayout) -> float:
    """
    How far apart a layout stands the two pieces that wear the same colour.
    """
    return layout.placement_of(MontessoriShapeCategory.CUBE).distance_to(
        layout.placement_of(MontessoriShapeCategory.CYLINDER)
    )


def _every_pair(placements: List[PiecePlacement]):
    """
    Every unordered pair of the given placements.
    """
    for index, one in enumerate(placements):
        for other in placements[index + 1 :]:
            yield one, other
