"""
The Montessori sorting scenes and the scripted runs over them: that a layout places the
pieces it names where it says, that a scene built from one really has the property it is
built for, and that each scripted run leaves the world in the state its goal asks about.

Every test here builds its world headless, on the test dataset's own fixed-arm robot
rather than on Tracy, whose description is a ROS package a checkout need not have.
"""

from __future__ import annotations

import pytest
from typing_extensions import List

from experiments.montessori.pieces import KNOWN_PIECES
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from experiments.montessori.scenarios import (
    LayoutArea,
    LightingChanged,
    MountedRobot,
    PieceHeldWhileTheQuestionIsAsked,
    PieceLayout,
    PiecePlacement,
    PiecePushedWhileTheRobotIsIdle,
    RobotSortsAPiece,
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
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.scenarios.runner import ScenarioRunner
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.adapters.multi_sim import MujocoLight
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import Point3
from semantic_digital_twin.world import World

from .dataset.synthetic_fixed_arm_robot import SyntheticFixedArmRobot

# %% what every scene here is built on

SEED = 20260908
"""
The seed every layout in this module is drawn from, so a failure is reproducible.
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
    The fixed-arm robot of the test dataset, bolted where every scene here bolts it.
    """
    return MountedRobot(position=WHERE_THE_ARM_IS_BOLTED)


class SyntheticArmSortsAPiece(RobotSortsAPiece[World, SyntheticFixedArmRobot]):
    """
    The pick-and-place run, on the robot this test suite can actually build.
    """


class SyntheticArmWatchesTheSceneStandStill(
    TheSceneStandsStill[World, SyntheticFixedArmRobot]
):
    """
    The static run, on the robot this test suite can actually build.
    """


class SyntheticArmIsIdleWhileAPieceIsPushed(
    PiecePushedWhileTheRobotIsIdle[World, SyntheticFixedArmRobot]
):
    """
    The external-push run, on the robot this test suite can actually build.
    """


class SyntheticArmHoldsAPiece(
    PieceHeldWhileTheQuestionIsAsked[World, SyntheticFixedArmRobot]
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
    scenario = SyntheticArmWatchesTheSceneStandStill(layout=layout, robot=mounted_arm())

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
    scenario = SyntheticArmWatchesTheSceneStandStill(layout=layout, robot=mounted_arm())

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
    scenario = SyntheticArmWatchesTheSceneStandStill(layout=layout, robot=mounted_arm())

    world = scenario.build_world()

    assert SortingScene(world).categories == {
        MontessoriShapeCategory.CUBE,
        MontessoriShapeCategory.CYLINDER,
    }


def test_a_built_scene_mounts_the_robot_its_type_names(area):
    scenario = SyntheticArmWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )

    world = scenario.build_world()

    assert isinstance(SortingScene(world).robot, SyntheticFixedArmRobot)


# %% the scripted runs


def test_the_static_run_leaves_every_piece_where_the_layout_put_it(area):
    layout = PieceLayout.randomized(seed=SEED, area=area)
    scenario = SyntheticArmWatchesTheSceneStandStill(layout=layout, robot=mounted_arm())

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_static_run_performs_no_step_that_moves_anything(area):
    scenario = SyntheticArmWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area), robot=mounted_arm()
    )

    steps = scenario.steps(scenario.build_world())

    assert [step.name for step in steps] == [SortingStep.SETTLE, SortingStep.ANSWER]


def test_the_pick_and_place_run_puts_the_piece_through_its_own_hole(area):
    scenario = SyntheticArmSortsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        sorted_category=MontessoriShapeCategory.CUBE,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_pushed_piece_run_moves_the_piece_and_not_the_robot(area):
    scenario = SyntheticArmIsIdleWhileAPieceIsPushed(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        pushed_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_held_piece_run_still_holds_the_piece_when_the_question_is_asked(area):
    scenario = SyntheticArmHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )

    trial = ScenarioRunner().run_trial(scenario)

    assert trial.outcome is TrialOutcome.SUCCEEDED


def test_the_held_piece_run_ends_with_the_piece_hanging_from_the_gripper(area):
    scenario = SyntheticArmHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        robot=mounted_arm(),
        held_category=MontessoriShapeCategory.CYLINDER,
    )
    world = scenario.build_world()

    for step in scenario.steps(world):
        step.perform(world)

    assert SortingScene(world).is_held(MontessoriShapeCategory.CYLINDER)


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
    scenario = SyntheticArmWatchesTheSceneStandStill(
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
    scenario = SyntheticArmWatchesTheSceneStandStill(
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


# %% helpers


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
