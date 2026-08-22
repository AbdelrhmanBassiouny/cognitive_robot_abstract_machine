"""
Tracy stacks a tower of cubes onto a base cube, held only by real MuJoCo contact
friction, in MuJoCo.

Every joint of both arms is driven directly via :class:`~real_time_simulation.
RealTimeSimulation`'s own actuator commands rather than through Giskard or
``world.state``, so every joint is always under real actuator/contact dynamics, never
kinematically teleported -- a cube held only by the gripper's squeeze is not left
behind the instant a kinematic snap would otherwise yank the arm out from under it,
since friction can only react to continuous motion, not an instantaneous position jump.

Cartesian reaches are planned by :func:`trajectory_planning.plan_cartesian_trajectory`
against an isolated, physics-free clone of the world, then the resulting joint-space
trajectory is played back here via :func:`trajectory_planning.follow_joint_trajectory`,
which drives the real actuators directly -- Giskard itself never touches this live,
physically simulated world, sidestepping a race between Giskard's own closed-loop
control and MuJoCo's physics-thread state sync (see :mod:`tracy_equipment`'s own module
docstring for the class of race this avoids). Park and gripper open/close are planned
the same way, via :func:`trajectory_planning.park_arms`/
:func:`trajectory_planning.set_gripper`, rather than commanded straight to the target
with no velocity profile: see :func:`trajectory_planning.plan_joint_trajectory`'s own
docstring for why that would otherwise let a joint move far faster than its real
hardware ever could.

Every cube (the stationary base and each one picked up and stacked on top of it) is
additionally, independently physically simulated, as a free body with real collision
geometry (see :func:`tracy_equipment.add_cube`); nothing ever kinematically attaches a
cube to the gripper (no ``AttachNode``/``PickUpAction``/``PlaceAction``).

Run with (the ``iai_tracy_description`` ROS package must be built and sourced)::

    python coraplex/demos/coraplex_tracy_demo/stacking_demo.py
"""

from __future__ import annotations

import logging
import math
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")

import numpy

from coraplex.datastructures.enums import Arms
from real_time_simulation import RealTimeSimulation
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
from semantic_digital_twin.world_description.geometry import Color

# coraplex/demos is not part of the coraplex package (only coraplex/src is on
# sys.path); this "demos" tree is a collection of standalone scripts run directly
# (python coraplex/demos/coraplex_tracy_demo/stacking_demo.py), matching every sibling
# demo here, so these sibling modules are only reachable as bare imports.
from tracy_equipment import (
    add_cube,
    apply_gravity_compensation,
    equip_arms_with_servos,
    equip_grippers_with_servos,
    exclude_self_collision,
    joint_state_of_type,
)
from trajectory_planning import (
    follow_joint_trajectory,
    park_arms,
    plan_cartesian_trajectory,
    set_gripper,
)

logger = logging.getLogger(__name__)

CUBE_SIZE = 0.05
"""
Edge length of both cubes, in metres -- well inside the Robotiq 2F-85's roughly 85mm
opening, unlike ``coraplex_real_tracy/demo.py``'s own 10cm boxes, which that demo never
actually has to close its fingers around since it holds them with an ``AttachNode``
instead of real friction.
"""

_PICK_XY_LIST = [(0.8, 0.25), (0.8, 0.10), (0.8, 0.40)]
"""
Tracy's left arm's own pick coordinates, one per cube stacked onto the base.

The first is reused as-is from ``coraplex_real_tracy/demo.py``'s own proven-reachable
coordinates (its own ``box2``, picked by ``Arms.LEFT``) -- not re-derived here, since
that demo already established it works. The other two sit 0.15m either side of it
along Y: with them only 0.1m apart, Giskard's own external collision avoidance
(enabled for each cube's first, empty-gripper reach -- see this module's own
docstring) visibly distorted the approach to the middle cube to keep clear of its
neighbours, missing the grasp -- confirmed directly, deterministically reproduced
across repeated runs. 0.15m leaves a full cube's own edge length of clearance instead
of half of one.
"""

_STACK_XY = (0.8, 0.0)
"""
Tracy's left arm's own stack-base coordinate.

Reused as-is from ``coraplex_real_tracy/demo.py``'s own proven-reachable stack base,
for the same reason as :data:`_PICK_XY_LIST`.
"""

HOVER_CLEARANCE = 0.15
"""
Height, in metres, above a cube's own top face the TCP moves to before descending onto
it -- clears the cube during the horizontal part of each approach, so the gripper never
drags across the table or another cube on its way in.
"""

GRASP_HEIGHT_MARGIN = 0.02
"""
Height, in metres, the grasp point sits above a cube's own vertical centre.

The fingertip pad's own collision mesh is taller (about 5.7cm) than the cube itself
(5cm), so closing the fingers around the cube's exact centre brings the pad's own
lower edge into contact with the table -- confirmed directly, a real contact between
``left_robotiq_85_left_finger_tip_link`` and the table at the cube's exact centre
height, gone at 1cm of margin; this keeps a wider margin above that (the Cartesian
reach itself carries a few millimetres of its own tracking error on top of the
fingertip geometry margin), while staying below the cube's own half-height (2.5cm)
so the fingers still close around the cube rather than above it.
"""

RELEASE_MARGIN = 0.02
"""
Height, in metres, a cube is released above its own intended resting centre, rather
than at it.

Even a small tracking error during the final descent can otherwise force the held
cube into the one below it instead of resting on top of it -- confirmed directly, the
observed failure mode was the held cube being pushed into the target cube, not falling
short of it. Releasing slightly high lets gravity settle the last few millimetres
instead of the arm's own descent forcing contact.
"""


def _bounding_box_center_world(robot: Tracy, body_name: str) -> numpy.ndarray:
    """
    A body's own collision bounding box centre, in the world root frame.

    :param robot: The robot the body belongs to.
    :param body_name: Name of the body to measure.
    """
    body = robot._world.get_body_by_name(body_name)
    bounding_box = body.collision[0].local_frame_bounding_box
    center_local = numpy.array(
        [
            (bounding_box.min_x + bounding_box.max_x) / 2,
            (bounding_box.min_y + bounding_box.max_y) / 2,
            (bounding_box.min_z + bounding_box.max_z) / 2,
        ]
    )
    root_transform_body = robot._world.compute_forward_kinematics_np(
        robot._world.root, body
    )
    return root_transform_body[:3, :3] @ center_local + root_transform_body[:3, 3]


def _finger_midpoint_offset(robot: Tracy) -> numpy.ndarray:
    """
    Fixed offset from the left arm's own tool frame to its gripper's own finger-tip
    midpoint, expressed in the tool frame's own local axes.

    :func:`~coraplex.robot_plans.motions.gripper.MoveToolCenterPointMotion` (and this
    module's own :func:`trajectory_planning.plan_cartesian_trajectory`) place the tool
    frame itself at a Cartesian goal, not where the fingers actually meet -- confirmed
    directly, targeting a cube's own centre this way put the tool frame there but left
    the fingers several centimetres above it, closing on open air.

    Each fingertip's own collision bounding box centre (not its link origin) stands in
    for where that finger actually is: the link origin sits at one edge of the
    fingertip mesh, not its geometric centre -- confirmed directly, the mesh's own
    local bounding box runs from -0.006m to +0.051m along one axis relative to the
    link origin, so using the origin left the corrected target still several
    centimetres off, close enough to let some other part of the gripper (the inner
    knuckle, not the fingertip pad) touch the target object instead of the pad itself.

    This offset is a fixed property of the gripper's own geometry (in the tool frame's
    own local axes, not world axes, so it does not depend on the arm's current
    orientation), used to correct a Cartesian target from "where the tool frame should
    end up" to "where the fingers should end up".

    :param robot: The robot whose left gripper this offset is measured on.
    """
    tool_frame = robot.left_arm.end_effector.tool_frame
    root_transform_tool = robot._world.compute_forward_kinematics_np(
        robot._world.root, tool_frame
    )
    left_center = _bounding_box_center_world(
        robot, "left_robotiq_85_left_finger_tip_link"
    )
    right_center = _bounding_box_center_world(
        robot, "left_robotiq_85_right_finger_tip_link"
    )
    finger_midpoint = (left_center + right_center) / 2
    offset_in_root_frame = finger_midpoint - root_transform_tool[:3, 3]
    return root_transform_tool[:3, :3].T @ offset_in_root_frame


def _table_top_z(robot: Tracy) -> float:
    """
    Height of Tracy's own table's top surface above the world root, in metres.

    :param robot: The robot whose table height is read.
    """
    table = robot.root
    tabletop = max(table.collision, key=lambda shape: shape.scale.x * shape.scale.y)
    root_transform_table = robot._world.compute_forward_kinematics_np(
        robot._world.root, table
    )
    return float(
        root_transform_table[2, 3]
        + tabletop.origin.to_np()[2, 3]
        + tabletop.scale.z / 2
    )


def main(headless: bool = False) -> None:
    """
    Build the scene, then pick up each cube in :data:`_PICK_XY_LIST` in turn and stack
    it on top of the growing tower.

    :param headless: Whether to run without opening MuJoCo's viewer window.
    """
    world = URDFParser.from_file(Tracy.get_ros_file_path()).parse()
    robot = Tracy.from_world(world)

    joint_state_of_type(robot.right_arm.end_effector, GripperState.CLOSE).apply_to(
        world
    )
    joint_state_of_type(robot.left_arm.end_effector, GripperState.OPEN).apply_to(world)
    world.notify_state_change()

    apply_gravity_compensation(world, robot)
    exclude_self_collision(world, robot)
    arm_actuators = equip_arms_with_servos(world, robot)
    gripper_actuators = equip_grippers_with_servos(world, robot)
    actuators = {**arm_actuators, **gripper_actuators}

    table_top_z = _table_top_z(robot)
    cube_center_z = table_top_z + CUBE_SIZE / 2

    stack_x, stack_y = _STACK_XY
    add_cube(
        world,
        "cube_base",
        Point3(stack_x, stack_y, cube_center_z),
        CUBE_SIZE,
        Color(0.3, 0.9, 0.3, 1.0),
    )

    cube_names = [f"cube_{index + 1}" for index in range(len(_PICK_XY_LIST))]
    cube_colors = [
        Color(0.9, 0.3, 0.3, 1.0),
        Color(0.3, 0.3, 0.9, 1.0),
        Color(0.9, 0.8, 0.2, 1.0),
    ]
    for name, (pick_x, pick_y), color in zip(
        cube_names, _PICK_XY_LIST, cube_colors
    ):
        add_cube(
            world, name, Point3(pick_x, pick_y, cube_center_z), CUBE_SIZE, color
        )

    # pitch=pi points the gripper straight down: yaw alone (the identity pitch/roll
    # this had before) is not a downward-facing orientation at all, and reaching for a
    # low target with it swings the wrist sideways into the table on the way down --
    # confirmed directly (a real MuJoCo contact between left_wrist_1_link and the
    # table, blocking the reach) before this was found and fixed.
    orientation = Pose.from_xyz_rpy(0, 0, 0, pitch=math.pi, reference_frame=world.root)
    tool_frame_rotation = orientation.to_rotation_matrix().evaluate()[:3, :3]
    finger_midpoint_offset = _finger_midpoint_offset(robot)

    def pose(x: float, y: float, z: float) -> Pose:
        # x, y, z are where the fingers -- not the tool frame -- should end up: see
        # _finger_midpoint_offset's own docstring for why a plain tool-frame target
        # misses by several centimetres.
        finger_target = numpy.array([x, y, z])
        tool_frame_target = finger_target - tool_frame_rotation @ finger_midpoint_offset
        return Pose.from_xyz_rpy(
            *tool_frame_target, pitch=math.pi, reference_frame=world.root
        )

    with RealTimeSimulation(world=world, headless=headless, step_size=1e-3) as sim:
        try:
            time.sleep(5)
            park_arms(sim, actuators, robot, [Arms.LEFT, Arms.RIGHT])

            def reach(
                goal_pose: Pose, translation_only: bool, avoid_collisions: bool = True
            ) -> None:
                trajectory = plan_cartesian_trajectory(
                    world,
                    Arms.LEFT,
                    goal_pose,
                    translation_only=translation_only,
                    avoid_collisions=avoid_collisions,
                )
                follow_joint_trajectory(sim, actuators, trajectory)

            stacked_cube_names = ["cube_base"]
            for name, (pick_x, pick_y) in zip(cube_names, _PICK_XY_LIST):
                # Read the stack's own current top height directly, rather than
                # assuming every previous cube in stacked_cube_names actually made it
                # onto the stack (a fixed height per loop index would): confirmed
                # directly, a single missed grasp otherwise left every later cube
                # released one whole cube height too high, silently falling onto
                # whatever was actually there instead of landing where intended.
                stacked_positions = sim.multi_sim.simulator.get_bodies_positions(
                    stacked_cube_names
                ).result
                # get_bodies_positions returns each cube's own centre, not its top
                # face, so the tallest centre needs half a cube added to reach the
                # stack's own actual top surface before the next cube's own centre
                # (another half cube up) can be placed there -- confirmed directly,
                # missing that first half-cube placed every cube's own centre where
                # its bottom face should have been, so it started out already
                # overlapping the cube below it and got ejected sideways on release.
                highest_center_z = max(
                    position[2] for position in stacked_positions.values()
                )
                stack_top_z = highest_center_z + CUBE_SIZE / 2
                place_center_z = stack_top_z + CUBE_SIZE / 2
                pick_hover = pose(pick_x, pick_y, cube_center_z + HOVER_CLEARANCE)
                pick_grasp = pose(pick_x, pick_y, cube_center_z + GRASP_HEIGHT_MARGIN)
                place_hover = pose(stack_x, stack_y, place_center_z + HOVER_CLEARANCE)
                place_release = pose(
                    stack_x, stack_y, place_center_z + RELEASE_MARGIN
                )

                # Collision avoidance stays on only for this first reach of each cube:
                # the gripper is empty and starts from a safe hover height (park, or
                # the previous cube's own escape hover), the one real risk of sweeping
                # into the table or an already-stacked cube on the way (see this
                # module's own docstring). Every reach after it is off: the moment the
                # gripper has touched anything -- approaching a cube to grasp it,
                # holding it, carrying it -- the arm's own starting configuration is
                # already "in collision" with that object by definition, and Giskard's
                # own collision check raises hard on a starting violation rather than
                # just steering around it.
                #
                # A prior version of this loop routed every lateral move through one
                # shared height well above the tallest possible tower, so the arm only
                # ever moved straight up/down within a single cube's own column,
                # trying to avoid grazing a cube sitting in between. That was reverted:
                # despite the goal being right, it reliably made the grasp itself
                # worse in a way not tied to which cube was being picked or how many
                # were in the scene -- still not root-caused. This loop's own real
                # collision risk (a lateral move at the wrong height clipping another
                # cube) is a known, open gap; fixing it needs to not regress the grasp
                # itself, which this attempt did.
                #
                # Every reach below constrains orientation too (translation_only=False)
                # rather than position alone: every pose this demo ever asks for shares
                # the exact same fixed orientation, so there is nothing to gain from
                # leaving it unconstrained, and doing so let Giskard's own IK
                # redundancy resolution drift the achieved orientation slightly on each
                # leg -- confirmed directly, constraining it dropped the grasp's own
                # position error from several millimetres to a fraction of one.
                reach(pick_hover, translation_only=False)
                reach(pick_grasp, translation_only=False, avoid_collisions=False)
                set_gripper(sim, actuators, robot, Arms.LEFT, GripperState.CLOSE)
                reach(pick_hover, translation_only=False, avoid_collisions=False)
                reach(place_hover, translation_only=False, avoid_collisions=False)
                reach(place_release, translation_only=False, avoid_collisions=False)
                set_gripper(sim, actuators, robot, Arms.LEFT, GripperState.OPEN)
                reach(place_hover, translation_only=False, avoid_collisions=False)
                stacked_cube_names.append(name)
            logger.info("Stacking plan finished.")
        except Exception as error:
            logger.warning("Stacking plan raised: %r", error)
        finally:
            all_cube_names = ["cube_base", *cube_names]
            final_positions = sim.multi_sim.simulator.get_bodies_positions(
                all_cube_names
            ).result
            for name in all_cube_names:
                logger.info("%s final position: %s", name, final_positions[name])

            if not headless:
                while sim.is_running:
                    time.sleep(0.1)


if __name__ == "__main__":
    main()
