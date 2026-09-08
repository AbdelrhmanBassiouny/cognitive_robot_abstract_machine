"""
The Montessori sorting scenes and the scripted runs over them: that a layout places the
pieces it names where it says, that a scene built from one really has the property it is
built for, and that each scripted run leaves the world in the state its goal asks about.

Every test here builds its world headless, on the test dataset's own grasping robot
rather than on Tracy, whose description is a ROS package a checkout need not have.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from typing_extensions import Dict, List

from experiments.montessori.pieces import KNOWN_PIECES
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from experiments.montessori.scenarios import (
    CONTAINED_IN_ITS_LANDING_REGION,
    DEFAULT_VIDEO_DIRECTORY_NAME,
    LayoutArea,
    LightingChanged,
    MontessoriEnvironmentVariable,
    MountedRobot,
    PUSHER_NAME,
    PUSHER_RAIL_NAME,
    PUSHER_SCALE,
    PieceHeldWhileTheQuestionIsAsked,
    PieceLayout,
    PiecePlacement,
    PiecePushedWhileTheRobotIsIdle,
    RobotSortsAPiece,
    SceneRecording,
    SortingScene,
    SortingStep,
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
from experiments.montessori.exceptions import (
    HoleHasNoLandingRegionError,
    NoSuchPieceError,
)
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.world import BOARD_POSITION, BOARD_SCALE
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.scenarios.runner import ScenarioRunner
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.adapters.multi_sim import MujocoLight
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.world_description.connections import PrismaticConnection
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import Point3
from semantic_digital_twin.world import World

from .dataset.synthetic_grasping_robot import SyntheticGraspingRobot

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
        layout=layout, robot=mounted_arm()
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
        layout=layout, robot=mounted_arm()
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
        layout=layout, robot=mounted_arm()
    )

    world = scenario.build_world()

    assert SortingScene(world).categories == {
        MontessoriShapeCategory.CUBE,
        MontessoriShapeCategory.CYLINDER,
    }


def test_a_built_scene_mounts_the_robot_its_type_names(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )

    world = scenario.build_world()

    assert isinstance(SortingScene(world).robot, SyntheticGraspingRobot)


# %% the scripted runs


def test_the_static_run_leaves_every_piece_where_the_layout_put_it(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=layout, robot=mounted_arm()
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_static_run_performs_no_step_that_moves_anything(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )

    steps = scenario.steps(scenario.build_world())

    assert [step.name for step in steps] == [SortingStep.SETTLE, SortingStep.ANSWER]


def test_the_pick_and_place_run_puts_the_piece_through_its_own_hole(area):
    scenario = SyntheticGrasperSortsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        sorted_category=MontessoriShapeCategory.CUBE,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_pushed_piece_run_moves_the_piece_and_not_the_robot(area):
    scenario = SyntheticGrasperIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        pushed_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_held_piece_run_still_holds_the_piece_when_the_question_is_asked(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_held_piece_run_ends_with_the_robot_holding_the_piece(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )
    world = scenario.build_world()

    for step in scenario.steps(world):
        step.perform(world)

    assert SortingScene(world).is_held(MontessoriShapeCategory.CYLINDER)


# %% the physics the scene runs under


def test_a_piece_left_above_the_table_falls_onto_it_when_the_scene_settles(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )
    world = scenario.build_world()
    scene = SortingScene(world)
    stood_at = scene.position_of(MontessoriShapeCategory.CUBE)
    scene.stand_the_piece_at(
        MontessoriShapeCategory.CUBE,
        Point3(stood_at.x, stood_at.y, float(stood_at.z) + 0.1),
    )

    scenario.simulation.settle()

    rested_at = scene.position_of(MontessoriShapeCategory.CUBE)
    assert float(rested_at.z) == pytest.approx(float(stood_at.z), abs=1e-3)


def test_the_pushed_scene_stands_a_pusher_on_a_rail_beside_the_piece(area):
    scenario = SyntheticGrasperIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
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
        robot=mounted_arm(),
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
        robot=mounted_arm(),
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
        robot=mounted_arm(),
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
        robot=mounted_arm(),
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
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )

    world = scenario.build_world()

    assert not SortingScene(world).is_in_its_hole(MontessoriShapeCategory.CUBE)


def test_the_robot_holds_nothing_before_it_has_picked_anything_up(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
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
        robot=mounted_arm(),
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
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
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
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
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
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )
    scene = SortingScene(scenario.build_world())

    for category in scene.categories:
        assert (
            scene.landing_region_for(category)
            is scene.hole_for(category).landing_region
        )


def test_a_hole_with_nothing_measured_under_it_says_so(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
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
        robot=mounted_arm(),
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
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
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


# %% running one scenario more than once


def test_every_trial_of_a_seeded_scenario_builds_the_same_scene(area):
    """
    What a seed is for: two trials of one scenario stand the pieces in the same places,
    so a difference between them is the run's and never the scene's.
    """
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
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
        "robot": mounted_arm(),
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
        frames_by_the_end_of[step.name] = scenario.simulation.recording.frame_count
    return AFilmedRun(
        recording=scenario.simulation.recording,
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
        robot=mounted_arm(),
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
