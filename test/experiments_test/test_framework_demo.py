"""
Tests for :mod:`experiments.tracy_experiments.framework_demo`: the plan the framework
figure shows, resolved against a look at the simulated lab and then carried out there --
the piece the look found is picked up off the board's lid, put through the hole the
rules concluded, and both cameras keep a film of it.
"""

from __future__ import annotations

import pytest

from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.semantics import ShapeSortingHole
from experiments.open_slots.holes import HoleRulesBackend
from experiments.open_slots.plan import FROM_ABOVE, SORTED_PIECE
from experiments.tracy_experiments.framework_demo import (
    VIDEO_RESOLUTION,
    DemoFilm,
    FrameworkDemo,
)
from experiments.tracy_experiments.pick_and_place_action import (
    InsertionActionMujoco,
    PickUpActionMujoco,
)
from experiments.tracy_experiments.pickup.pickup_demo_mujoco import SORTED_INTO_ITS_HOLE
from coraplex.datastructures.grasp import GraspDescription
from krrood.entity_query_language.backends import ProbabilisticBackend


@pytest.fixture(scope="module")
def performed(tmp_path_factory: pytest.TempPathFactory) -> FrameworkDemo:
    """
    The whole run, performed once headless and as fast as the machine allows.
    """
    demo = FrameworkDemo(films_directory=tmp_path_factory.mktemp("framework_demo"))
    demo.perform()
    return demo


# %% what the plan came to


def test_each_slot_is_answered_by_the_backend_that_can(
    performed: FrameworkDemo,
) -> None:
    assert [
        (type(answered.backend), answered.statement._type_)
        for answered in performed.grounded.answered_by.answered
    ] == [
        (MontessoriPerceptionBackend, DetectedMontessoriShape),
        (ProbabilisticBackend, GraspDescription),
        (HoleRulesBackend, ShapeSortingHole),
    ]


def test_it_reaches_for_the_piece_the_look_found_where_the_robot_plans(
    performed: FrameworkDemo,
) -> None:
    """
    The arm is driven at a body the world the robot plans in holds, which is what a look
    keeping its findings in that world is for.
    """
    [picking_up, putting_through] = performed.grounded.actions

    assert isinstance(picking_up, PickUpAction)
    assert isinstance(putting_through, InsertionAction)
    assert picking_up.object_designator.category is SORTED_PIECE
    assert picking_up.object_designator.root in performed.lab.belief.bodies
    assert putting_through.target.shape_category is SORTED_PIECE


def test_the_hand_it_takes_hold_with_comes_down_on_the_piece(
    performed: FrameworkDemo,
) -> None:
    [picking_up, _] = performed.grounded.actions

    assert picking_up.grasp_description.vertical_alignment is FROM_ABOVE


# %% what it did with it


def test_the_plan_is_carried_out_by_the_actions_that_drive_the_actuators(
    performed: FrameworkDemo,
) -> None:
    assert [type(action) for action in performed.carried_out] == [
        PickUpActionMujoco,
        InsertionActionMujoco,
    ]


def test_the_piece_ends_up_through_its_own_hole(performed: FrameworkDemo) -> None:
    assert performed.sorted_piece_is_through_its_hole > SORTED_INTO_ITS_HOLE


# %% what it leaves behind


def test_it_films_the_run_from_in_front_of_the_table_and_through_the_robots_camera(
    performed: FrameworkDemo,
) -> None:
    assert [film.film.path.name for film in performed.films] == [
        DemoFilm.FROM_THE_FRONT,
        DemoFilm.ROBOT_CAMERA,
    ]
    for film in performed.films:
        assert film.taken.frame(0).shape == (
            VIDEO_RESOLUTION.height,
            VIDEO_RESOLUTION.width,
            3,
        )


def test_each_film_says_how_far_into_the_run_its_frames_were_taken(
    performed: FrameworkDemo,
) -> None:
    """
    A film's frames are stamped by the simulation's own clock, so what is watched can be
    lined up with how long the run took.
    """
    for film in performed.films:
        moments = film.taken.moments

        assert moments == sorted(moments)
        assert moments[0] < moments[-1]
