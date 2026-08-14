"""
A PR2 opens the fridge of the small kitchen, takes a milk out of it, closes the fridge
again and puts the milk down on the kitchen island.

The plan is assembled from the core action designators rather than delegating to
:class:`~coraplex.robot_plans.actions.composite.transporting.TransportAction`, which
recognizes drawers only and would leave the fridge door shut.

The world is built from specifications: the kitchen comes from a URDF, the robot from a
:class:`~semantic_digital_twin.api.RobotSpecification`, and the shelf and the milk from
body and annotation specifications placed relative to the fridge.

..note:: This demonstration is written for a simulated run. Running it with
    :attr:`~coraplex.datastructures.enums.ExecutionType.REAL` fetches the world from a
    controller, and the world fetcher does not run
    :class:`~semantic_digital_twin.reasoning.world_reasoner.WorldReasoner` over what it
    receives, so the fridge annotation the scene is placed against would be missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import numpy as np
from typing_extensions import ClassVar

from coraplex.robot_plans.actions.composite.transporting import TransportAction
from krrood.entity_query_language.factories import (
    a,
    an,
    contains,
    entity,
    the,
    variable,
)
from krrood.entity_query_language.query.match import Match
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import (
    ApproachDirection,
    Arms,
    ExecutionType,
    VerticalAlignment,
)
from coraplex.datastructures.grasp import GraspDescription
from coraplex.demonstrations import RobotDemonstration
from coraplex.locations.base import DeferredLocation
from coraplex.locations.factories import giskard_reachability_location
from coraplex.plans.factories import sequential, execute_single
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.core.container import CloseAction, OpenAction
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from coraplex.view_manager import ViewManager
from semantic_digital_twin.api import RobotSpecification, WorldSpecification
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.reasoning.world_reasoner import WorldReasoner
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Door,
    Fridge,
    Milk,
    ShelfLayer,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color, Scale
from semantic_digital_twin.world_description.world_entity import Body

# %% where everything stands in the kitchen

KITCHEN_URDF = Path(files("coraplex")).parent.parent / "resources" / "worlds" / "kitchen-small.urdf"
"""
The kitchen the demo plays in.

Its fridge door is the only door in it that opens.
"""

ROBOT_START_POSE = Pose.from_xyz_rpy(0.0, 0.0, 0.0)
"""
Where the robot starts, on the free floor between the fridge and the kitchen island.

The PR2's root is its ``base_footprint``, so a height of zero puts it on the floor.
"""

MILK_NAME = "milk"
"""
Name of the transported body.
"""

SHELF_LAYER_NAME = "fridge_shelf"
"""
Name of the shelf layer the milk stands on.
"""

ISLAND_SURFACE_NAME = "kitchen_island_surface"
"""
Name of the kitchen island body the milk is put down on.
"""

MILK_SCALE = Scale(0.065, 0.065, 0.2)
"""
The extents of the milk carton.
"""

SHELF_LAYER_SCALE = Scale(0.45, 0.5, 0.02)
"""
The extents of the shelf layer the milk stands on.

Fits into the fridge cavity, which is about 0.03 meters narrower than the shell on every
side.
"""

SHELF_LAYER_COLOR = Color(0.9, 0.93, 0.95)
"""
The colour of the shelf layer, an off-white against the fridge's own shell.
"""

FRIDGE_T_SHELF_LAYER = HomogeneousTransformationMatrix.from_xyz_rpy(
    0.0, 0.02, 0.0, yaw=np.pi
)
"""
The shelf layer in the fridge frame, centered in the cavity.

The kitchen places its fridge turned by half a turn against the room, so the layer turns
back: everything spawned below it is then aligned with the room, and grasped from the
front like any other object standing in it.
"""

SHELF_LAYER_T_MILK = HomogeneousTransformationMatrix.from_xyz_rpy(-0.16, 0.0, 0.11)
"""
The milk on the shelf layer, standing near its front edge.

Layer x runs towards the fridge opening, and the layer is 0.4 meters deep, so this
leaves the 0.065 meter carton just clear of the edge. The further forward it stands, the
further back the robot can stand to take it, and the less it has to lean into the swing
of the open door.
"""

ISLAND_APPROACH_YAW = np.pi
"""
The heading the robot faces at the kitchen island, which it reaches from positive x.
"""

PLACE_POSITION_ON_ISLAND = (-0.8, 1.2)
"""
Where on the kitchen island the milk ends up, in x and y.

The southern half of the island, clear of the stove and of the drawer handles. The
height is measured from the island surface instead of being fixed here.
"""

DOOR_SPEED_LIMIT = 1.0
"""
How fast the fridge door may swing, in radians per second.

The kitchen's URDF describes the hinge with 10 rad/s, a speed a door does not turn at.
The controller keeps a braking margin from a joint's own position limit that grows with
that limit, and at 10 rad/s the margin is wide enough that the door can neither be swung
fully open nor shut.
"""

DOOR_OPENING_ANGLE = 1.45
"""
How far the fridge door is swung open, in radians.

Wide enough to reach past it into the fridge, short of the hinge's 1.5708 limit so the
swing does not have to be timed against the door frame.
"""

DOOR_CLOSING_ANGLE = 0.0
"""
How far the fridge door is asked to stand open after closing, in radians: shut.
"""

DOOR_IS_CLOSED_ANGLE = 0.02
"""
Up to which fridge door angle, in radians, the door counts as closed.

The closing motion parks the door within about a hundredth of a radian of the hinge's
limit, half a degree of swing, so this is how exactly the door shuts rather than how far
ajar it may stand.
"""

PLACEMENT_TOLERANCE = 0.02
"""
How far, in meters, the milk may end up from where it was placed.

Nothing here is subject to gravity or contact forces, so a placement that goes to plan
lands on the target rather than near it.
"""

# %% who reaches for what

MILK_ARM = Arms.RIGHT
"""
The arm carrying the milk.

Reaching into the fridge means standing to the left of the opening, out of the swing of
the open door, which leaves the milk on the robot's right.
"""

DOOR_ARM = Arms.LEFT
"""
The arm opening and closing the fridge door.

Whichever arm this is, it cannot be :data:`MILK_ARM`: the door is shut again while the
milk is still being carried, so that hand is not free.
"""

HANDLE_APPROACH_DIRECTION = ApproachDirection.BACK
"""
The side of the fridge door handle the gripper comes from.

The fridge, and with it its handle, is turned by half a turn against the room, so the
handle's own front points into the fridge and is reached from its back. The handle turns
with the door, so this holds whether the door is being opened or shut.
"""

# %% the demonstration


@dataclass
class KitchenFridgeDemonstration(RobotDemonstration):
    """
    A robot fetches a milk out of the kitchen fridge and puts it on the kitchen island.
    """

    ros_node_name: ClassVar[str] = "kitchen_fridge_demo_node"

    def build_simulated_world(self) -> World:
        """
        Load the kitchen from its URDF, put the robot in it and infer what its bodies
        mean, which is what turns the fridge's parts into a fridge with a door and a
        handle.
        """
        world = WorldSpecification.from_urdf(
            str(KITCHEN_URDF),
            robots=[
                RobotSpecification(
                    semantic_annotation_type=self.used_robot,
                    world_T_odom=ROBOT_START_POSE.to_homogeneous_matrix(),
                )
            ],
        ).to_domain_object()

        with world.modify_world():
            WorldReasoner(world).reason()

        hinge = self.fridge_door(world).root.parent_connection
        hinge.raw_dof.limits.upper.velocity = DOOR_SPEED_LIMIT
        hinge.raw_dof.limits.lower.velocity = -DOOR_SPEED_LIMIT

        return world

    def is_scene_populated(self, world: World) -> bool:
        milk = variable(Milk, domain=world.semantic_annotations)
        return next(an(entity(milk)).evaluate(), None) is not None

    def populate_scene(self, world: World) -> None:
        """
        Spawn the fridge's shelf layer and the milk standing on it.
        """
        fridge = variable(Fridge, domain=world.semantic_annotations)
        fridge_annotation = the(entity(fridge)).first()
        shelf_layer = ShelfLayer.get_annotation_specification(
            SHELF_LAYER_NAME,
            ShelfLayer.get_default_root_kinematic_structure_entity_specification(
                scale=SHELF_LAYER_SCALE
            ),
        ).spawn(
            world,
            parent=fridge_annotation.root,
            parent_T_self=FRIDGE_T_SHELF_LAYER,
        )
        with world.modify_world():
            fridge_annotation.add(shelf_layer)
            for shape in shelf_layer.root.visual.shapes:
                shape.color = SHELF_LAYER_COLOR

        Milk.get_annotation_specification(
            MILK_NAME,
            Milk.get_default_root_kinematic_structure_entity_specification(
                scale=MILK_SCALE
            ),
        ).spawn(world, parent=shelf_layer.root, parent_T_self=SHELF_LAYER_T_MILK)

    def fridge_door(self, world: World) -> Door:
        """
        :param world: The world holding the kitchen.
        :return: The fridge door, told apart from the kitchen's other doors by belonging
            to the fridge.
        """
        fridge = variable(Fridge, domain=world.semantic_annotations)
        door = variable(Door, domain=world.semantic_annotations)
        return the(entity(door).where(contains(fridge.doors, door))).first()

    def place_pose_on_island(self, world: World) -> Pose:
        """
        :param world: The world holding the kitchen.
        :return: The pose the milk is placed at, standing on the kitchen island surface.
        """
        island_surface = variable(Body, domain=world.bodies)
        surface_height = (
            the(
                entity(island_surface).where(
                    island_surface.name.name == ISLAND_SURFACE_NAME
                )
            )
            .first()
            .collision.as_bounding_box_collection_in_frame(world.root)
            .bounding_box()
            .max_z
        )
        x, y = PLACE_POSITION_ON_ISLAND
        return Pose.from_xyz_rpy(
            x,
            y,
            surface_height + MILK_SCALE.z / 2,
            yaw=ISLAND_APPROACH_YAW,
            reference_frame=world.root,
        )

    def build_context(self, world: World) -> Context:
        """
        Build the plan context around the robot in ``world``.
        """
        robot = variable(self.used_robot, domain=world.semantic_annotations)
        return Context(
            world=world,
            robot=the(entity(robot)).first(),
            ros_node=self.ros_node,
            evaluate_conditions=False,
            alternative_motion_mappings=self.alternative_motion_mappings,
        )

    @staticmethod
    def navigate_within_reach(
        target: Body | Pose,
        arm: Arms,
        grasp_description: GraspDescription,
        context: Context,
    ) -> Match[NavigateAction]:
        """
        Drive to a base pose the target can be reached from with ``arm``.

        Every action of a plan is expanded before its first motion runs, which is too
        early to choose a standing pose: earlier steps still move both the robot and the
        handle riding the swinging door. An underspecified action is grounded once
        execution reaches it, which is late enough.

        :param target: The body or pose the gripper has to reach.
        :param arm: The arm that has to reach it.
        :param grasp_description: How the gripper takes hold of the target.
        :param context: The context the standing pose is chosen in.
        """
        return a(NavigateAction)(
            target_location=variable(
                Pose,
                domain=DeferredLocation(
                    lambda: giskard_reachability_location(
                        target, context, arm, grasp_description
                    )
                ),
            ),
            keep_joint_states=True,
        )

    def build_plan(self, context: Context) -> PlanNode:
        """
        Open the fridge, carry the milk to the kitchen island and shut the fridge on the
        way.
        """
        world = context.world
        milk = variable(Milk, domain=world.semantic_annotations)
        milk_body = the(entity(milk)).first().root
        handle = self.fridge_door(world).handle.root
        place_pose = self.place_pose_on_island(world)

        door_end_effector = ViewManager.get_end_effector_view(DOOR_ARM, context.robot)
        handle_grasp = GraspDescription(
            HANDLE_APPROACH_DIRECTION,
            VerticalAlignment.NoAlignment,
            door_end_effector,
        )
        milk_grasp = GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.NoAlignment,
            ViewManager.get_end_effector_view(MILK_ARM, context.robot),
        )

        context.debug = True

        return sequential(
            [

                ParkArmsAction(Arms.BOTH),
            ],
            context,
        )


# %% running the demo


def main(execution_type: ExecutionType = ExecutionType.SIMULATED) -> World:
    """
    Run the demonstration and check that the milk ended up on the kitchen island with
    the fridge shut behind it.

    :param execution_type: Whether to drive the real robot or simulate it.
    :return: The world the demonstration acted on.
    """
    demonstration = KitchenFridgeDemonstration(
        used_robot=PR2, execution_type=execution_type
    )
    world = demonstration.run()

    milk = variable(Milk, domain=world.semantic_annotations)
    milk_position = the(entity(milk)).first().root.global_pose.to_position()
    expected_position = demonstration.place_pose_on_island(world).to_position()
    door_angle = demonstration.fridge_door(world).root.parent_connection.position
    print(f"milk placed at {np.round(milk_position, 3)}")
    print(f"Expected milk to be placed at {np.round(expected_position, 3)}")
    print(f"fridge door closed to {door_angle:.4f} rad")

    assert np.allclose(milk_position, expected_position, atol=PLACEMENT_TOLERANCE)
    assert door_angle < DOOR_IS_CLOSED_ANGLE
    return world


if __name__ == "__main__":
    main()