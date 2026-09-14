"""
The actions that carry a resolved plan out on the physical Tracy: which of them carries
out which action of a plan, which lab each drives, and what each reads off the action it
carries out.

No robot and no ROS: the plan is grounded against a look at a rendered scene, and what
the actions would drive is a stand-in that records what it was asked to do.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from coraplex.robot_plans.actions.core.insertion import (
    DEFAULT_HOVER_HEIGHT,
    InsertionAction,
)
from coraplex.robot_plans.actions.core.pick_up import PickUpAction, ReachAction
from coraplex.datastructures.dataclasses import Context
from coraplex.robot_plans.actions.core.placing import PlaceAction
from experiments.montessori.perception.detections import MontessoriScene
from experiments.open_slots.plan import SORTED_PIECE
from experiments.tracy_experiments.montessori.grasp_widths import GraspCloseTable
from experiments.tracy_experiments.pick_and_place_action import (
    ActuatorDrivenAction,
    InsertionActionMujoco,
    NoActionCarriesItOut,
    PickUpActionMujoco,
    PlaceActionMujoco,
    SimulatedActuators,
)
from experiments.tracy_experiments.pick_and_place_action_real import (
    GRASP_HEIGHT_OFFSET,
    InsertionActionReal,
    PickUpActionReal,
    TracyActuators,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose

from .dataset import figure_plan_fixtures, montessori_scene_fixtures
from .dataset.actuators_that_record import (
    ActuatorsThatRecord,
    EndEffectorFacingAWay,
    FingersThatRecord,
)
from .dataset.figure_plan_fixtures import PICK_ARM

pytest_plugins = [
    montessori_scene_fixtures.__name__,
    figure_plan_fixtures.__name__,
]
"""
The rendered scene and the pipeline that reads it, and the figure's plan grounded
against it.
"""


@pytest.fixture
def tracy(scene_with_a_piece_on_the_lid: MontessoriScene) -> TracyActuators:
    """
    Tracy's actuators, recording rather than driving, over the world the look stood its
    findings in -- which is the world the piece these actions act on stands in.
    """
    return ActuatorsThatRecord(
        context=Context(
            world=scene_with_a_piece_on_the_lid.imagined.world,
            robot=None,
            evaluate_conditions=False,
        ),
        gripper=FingersThatRecord(),
        gripper_listener=None,
        tool_frame=None,
    )


@pytest.fixture
def simulation() -> SimulatedActuators:
    """
    A simulated lab's actuators, which drive nothing here either.
    """
    return SimulatedActuators(simulation=None, actuators={})


# %% which action carries out which, and where


def test_each_action_says_what_it_carries_out_and_which_lab_it_drives() -> None:
    """
    Both halves are read off the type parameters the member binds, so neither can
    disagree with the signature.
    """
    assert [
        (member.action_it_carries_out(), member.lab_it_drives())
        for member in ActuatorDrivenAction.__subclasses__()
    ] == [
        (PickUpAction, SimulatedActuators),
        (PlaceAction, SimulatedActuators),
        (InsertionAction, SimulatedActuators),
        (PickUpAction, TracyActuators),
        (InsertionAction, TracyActuators),
    ]


def test_the_robot_carries_the_plan_out_with_its_own_actions(
    grounded: list, tracy: TracyActuators
) -> None:
    """
    The same resolved plan is run by whichever members drive the lab it is handed, so
    nothing in the plan has to name them.
    """
    carried_out = ActuatorDrivenAction.performing(grounded, tracy)

    assert [type(action) for action in carried_out] == [
        PickUpActionReal,
        InsertionActionReal,
    ]


def test_the_simulated_lab_carries_the_same_plan_out_with_its_own(
    grounded: list, simulation: SimulatedActuators
) -> None:
    carried_out = ActuatorDrivenAction.performing(grounded, simulation)

    assert [type(action) for action in carried_out] == [
        PickUpActionMujoco,
        InsertionActionMujoco,
    ]


def test_an_action_nothing_drives_this_lab_with_is_refused(
    grounded: list, tracy: TracyActuators
) -> None:
    """
    A plan stating an action this lab cannot run says so, rather than running the rest
    of it and leaving that one out.
    """
    [picking_up, _] = grounded
    reaching = ReachAction(
        target_pose=Pose(),
        arm=PICK_ARM,
        grasp_description=picking_up.grasp_description,
    )

    with pytest.raises(NoActionCarriesItOut) as refusal:
        ActuatorDrivenAction.performing([reaching], tracy)

    assert refusal.value.action is reaching
    assert refusal.value.lab is tracy


def test_a_place_is_carried_out_in_simulation_but_not_on_the_robot(
    simulation: SimulatedActuators, tracy: TracyActuators
) -> None:
    """
    The two labs answer for themselves: a place the simulated lab runs is one the robot
    has no member for, and saying so is the point of binding the lab.
    """
    placing = PlaceAction(object_designator=None, target_location=Pose(), arm=PICK_ARM)

    assert ActuatorDrivenAction._carrier_of(placing, simulation) is PlaceActionMujoco
    with pytest.raises(NoActionCarriesItOut):
        ActuatorDrivenAction._carrier_of(placing, tracy)


# %% what each reads off the action it carries out


def test_it_takes_hold_of_the_piece_the_plan_names(
    grounded: list, tracy: TracyActuators
) -> None:
    [picking_up, _] = grounded

    taking_hold = PickUpActionReal.carrying_out(picking_up, tracy)

    assert taking_hold.object_designator is picking_up.object_designator
    assert taking_hold.arm is picking_up.arm
    assert taking_hold.grasp_description is picking_up.grasp_description
    assert taking_hold.shape_category is SORTED_PIECE
    assert taking_hold.manipulated_bodies == [picking_up.object_designator.root]


def test_the_reach_is_handed_the_piece_the_plan_names_not_its_body(
    grounded: list, tracy: ActuatorsThatRecord
) -> None:
    """
    A reach expands its plan from the piece's annotation, reading the body off it, so it
    is handed the annotation the plan grounded rather than the body under it.
    """
    [picking_up, _] = grounded
    taking_hold = PickUpActionReal.carrying_out(picking_up, tracy)
    taking_hold.grasp_description = replace(
        taking_hold.grasp_description,
        end_effector=EndEffectorFacingAWay(tracy.context.world),
    )

    taking_hold._run()

    [reaching] = [node.designator for node in tracy.driven[0].actions]
    assert type(reaching) is ReachAction
    assert reaching.object_designator is picking_up.object_designator


def test_the_fingers_close_to_the_width_that_piece_asks_for(
    grounded: list, tracy: TracyActuators
) -> None:
    """
    A cube is held at the width the close table records for a cube, rather than at
    whatever a fully closed hand would reach.
    """
    [picking_up, _] = grounded

    taking_hold = PickUpActionReal.carrying_out(picking_up, tracy)

    assert taking_hold.close_setpoint == GraspCloseTable().setpoint_for(SORTED_PIECE)


def test_it_puts_through_the_opening_the_plan_names(
    grounded: list, tracy: TracyActuators
) -> None:
    [_, putting_through] = grounded

    insertion = InsertionActionReal.carrying_out(putting_through, tracy)

    assert insertion.target is putting_through.target
    assert insertion.object_designator is putting_through.object_designator.root
    assert insertion.arm is putting_through.arm
    assert insertion.grasp_description is putting_through.grasp_description
    assert insertion.hover_height == putting_through.hover_height


def test_it_lets_the_piece_go_above_the_opening_rather_than_in_it(
    grounded: list, tracy: TracyActuators
) -> None:
    """
    The piece is released clear of the lid so what carries it through is its own fall,
    which is the height the insertion it carries out states.
    """
    [_, putting_through] = grounded

    insertion = InsertionActionReal.carrying_out(putting_through, tracy)

    assert insertion.hover_height == DEFAULT_HOVER_HEIGHT


def test_the_reach_is_aimed_above_the_piece_it_stands_on_the_surface(
    grounded: list, tracy: TracyActuators
) -> None:
    """
    A piece a look stood rests on the surface it was seen on, so the reach is lifted
    back off that surface by the offset the demo reaches with.
    """
    [picking_up, _] = grounded
    body = picking_up.object_designator.root
    stands_at = body.global_transform.to_position()

    aimed_at = tracy.grasp_target_above(body).to_position()

    assert float(aimed_at.x) == pytest.approx(float(stands_at.x))
    assert float(aimed_at.y) == pytest.approx(float(stands_at.y))
    assert float(aimed_at.z) == pytest.approx(float(stands_at.z) + GRASP_HEIGHT_OFFSET)
