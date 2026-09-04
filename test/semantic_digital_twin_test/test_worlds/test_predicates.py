from copy import deepcopy
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from semantic_digital_twin.exceptions import RelationStatedAboutNothing
from semantic_digital_twin.datastructures.field_of_view import FieldOfView
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.reasoning.predicates import (
    Turned,
    contact,
    visible,
    Above,
    Below,
    LeftOf,
    RightOf,
    Behind,
    Between,
    Colored,
    InFrontOf,
    Near,
    PlacementRelation,
    is_body_in_region,
    occluding_bodies,
    is_supported_by,
    reachable,
    is_place_occupied,
    InsideOf,
    InsideRegion,
    InContactWith,
    PlaceIsOccupied,
    Reachable,
    Stable,
    space_between,
    SupportedBy,
    Supports,
    ViewDependentSpatialRelation,
    VisibleTo,
)
from krrood.entity_query_language.backends import StatedRelation
from krrood.entity_query_language.factories import an, variable
from krrood.entity_query_language.predicate import Predicate, Relation, Triple
from krrood.entity_query_language.testing.result_verification import (
    placeholder_operands,
)
from krrood.entity_query_language.verbalization.pipeline import (
    verbalize_expression,
)
from semantic_digital_twin.reasoning.robot_predicates import (
    robot_in_collision,
    robot_holds_body,
    blocking,
    is_body_in_gripper,
    bodies_in_gripper,
    is_pose_free_for_robot,
    is_gripper_holding_something,
)
from semantic_digital_twin.robots.robot_parts import Camera, EndEffector
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.spatial_types import Point3, Vector3
from semantic_digital_twin.spatial_types.spatial_types import Pose, Quaternion
from semantic_digital_twin.testing import *
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.geometry import (
    Box,
    Scale,
    Color,
    VolumetricBoundingBox,
)
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    Region,
    KinematicStructureEntity,
)


@pytest.fixture(scope="function")
def two_block_world():
    def make_body(name: str) -> Body:
        result = Body(name=PrefixedName(name))
        collision = Box(
            scale=Scale(1.0, 1.0, 1.0),
            origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=result),
        )
        result.collision = ShapeCollection([collision], reference_frame=result)
        return result

    world = World()

    body_1 = make_body("body_1")
    body_2 = make_body("body_2")

    with world.modify_world():
        connection = FixedConnection(
            parent=body_1,
            child=body_2,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                z=3, reference_frame=body_1
            ),
        )
        world.add_connection(connection)
    return body_1, body_2


def test_in_contact():
    w = World()

    b1 = Body(name=PrefixedName("b1"))
    collision1 = Box(
        scale=Scale(1.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
            0,
            0,
            0.0,
            0,
            0,
            0,
            reference_frame=b1,
        ),
        color=Color(1.0, 0.0, 0.0),
    )
    b1.collision = ShapeCollection([collision1])

    b2 = Body(name=PrefixedName("b2"))
    collision2 = Box(
        scale=Scale(1.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
            0.9, 0, 0.0, 0, 0, 0, reference_frame=b2
        ),
        color=Color(0.0, 1.0, 0.0),
    )
    b2.collision = ShapeCollection([collision2])

    b3 = Body(name=PrefixedName("b3"))
    collision3 = Box(
        scale=Scale(1.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
            1.8, 0, 0.0, 0, 0, 0, reference_frame=b3
        ),
        color=Color(0.0, 0.0, 1.0),
    )
    b3.collision = ShapeCollection([collision3])

    with w.modify_world():
        w.add_kinematic_structure_entity(b1)
        w.add_kinematic_structure_entity(b2)
        w.add_kinematic_structure_entity(b3)
        w.add_connection(Connection6DoF.create_with_dofs(parent=b1, child=b2, world=w))
        w.add_connection(Connection6DoF.create_with_dofs(parent=b2, child=b3, world=w))
    assert contact(b1, b2)
    assert not contact(b1, b3)
    assert contact(b2, b3)


def test_robot_in_contact(pr2_world_copy: World):
    pr2 = pr2_world_copy.get_semantic_annotations_by_type(PR2)[0]
    body = Body(name=PrefixedName("test_body"))
    collision1 = Box(
        scale=Scale(1.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
            z=0.5,
            reference_frame=body,
        ),
        color=Color(1.0, 0.0, 0.0),
    )
    body.collision = ShapeCollection([collision1])

    with pr2_world_copy.modify_world():
        pr2_world_copy.add_connection(
            Connection6DoF.create_with_dofs(
                parent=pr2_world_copy.root,
                child=body,
                world=pr2_world_copy,
            )
        )

    # Ensure the call runs without raising
    assert robot_in_collision(pr2)

    body.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        4, 0, 0.5, 0, 0, 0, pr2_world_copy.root
    )
    assert not robot_in_collision(pr2)


def test_get_visible_objects(pr2_world_copy: World):
    body = Body(name=PrefixedName("test_body"))
    collision1 = Box(
        scale=Scale(1.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
            x=2.0,
            z=1.0,
            reference_frame=body,
        ),
        color=Color(1.0, 0.0, 0.0),
    )
    body.collision = ShapeCollection([collision1])

    with pr2_world_copy.modify_world():
        pr2_world_copy.add_connection(
            Connection6DoF.create_with_dofs(
                parent=pr2_world_copy.root,
                child=body,
                world=pr2_world_copy,
            )
        )

    camera = pr2_world_copy.get_semantic_annotations_by_type(Camera)[0]

    assert visible(camera, body)


def test_camera_view_frame_x_axis_is_the_forward_axis(pr2_world_copy: World):
    """
    The frame the ray tracer casts along must be the camera's own frame, turned so that
    its x axis is the direction the camera looks.
    """
    camera = pr2_world_copy.get_semantic_annotations_by_type(Camera)[0]
    root_T_camera = camera.root.global_transform

    root_T_view = camera.root_T_forward_view.to_np()
    root_V_forward = (
        root_T_camera.to_rotation_matrix() @ camera.forward_facing_axis
    ).to_np()

    assert np.allclose(root_T_view[:3, 0], root_V_forward.flatten()[:3], atol=1e-9)
    assert np.allclose(root_T_view[:3, 3], root_T_camera.to_np()[:3, 3], atol=1e-9)


def test_visibility_follows_camera_orientation(pr2_world_copy: World):
    """
    A body off to the side is visible exactly when the head is turned towards it.
    """
    body = Body(name=PrefixedName("test_body"))
    body.collision = ShapeCollection(
        [
            Box(
                scale=Scale(1.0, 1.0, 1.0),
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    y=2.0, z=1.0, reference_frame=body
                ),
            )
        ]
    )

    with pr2_world_copy.modify_world():
        pr2_world_copy.add_connection(
            Connection6DoF.create_with_dofs(
                parent=pr2_world_copy.root,
                child=body,
                world=pr2_world_copy,
            )
        )

    camera = pr2_world_copy.get_semantic_annotations_by_type(Camera)[0]
    head_pan = pr2_world_copy.get_degree_of_freedom_by_name("head_pan_joint")

    assert not visible(camera, body)

    pr2_world_copy.state[head_pan.id].position = np.pi / 2
    pr2_world_copy.notify_state_change()

    assert visible(camera, body)


def test_occluding_bodies(pr2_world_state_reset: World):
    world = deepcopy(pr2_world_state_reset)
    world.get_body_by_name("base_footprint").parent_connection.origin = (
        HomogeneousTransformationMatrix.from_xyz_rpy(0, 0, 0)
    )

    def make_body(name: str) -> Body:
        result = Body(name=PrefixedName(name))
        collision = Box(
            scale=Scale(1.0, 1.0, 1.0),
            origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=result),
        )
        result.collision = ShapeCollection([collision])
        return result

    obstacle = make_body("obstacle")
    occluded_body = make_body("occluded_body")

    with world.modify_world():
        root = world.root
        c1 = FixedConnection(
            parent=root,
            child=obstacle,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                reference_frame=root, x=3, z=0.8
            ),
        )
        c2 = FixedConnection(
            parent=root,
            child=occluded_body,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                reference_frame=root, x=10, z=0.5
            ),
        )
        world.add_connection(c1)
        world.add_connection(c2)

    camera = world.get_semantic_annotations_by_type(Camera)[0]

    bodies = occluding_bodies(camera, occluded_body)
    assert obstacle in bodies
    assert camera not in bodies
    assert occluded_body not in bodies


def test_occluding_bodies_follows_camera_orientation(pr2_world_state_reset: World):
    """
    Occlusion is judged along the direction the camera looks, not along a fixed world
    axis, so a pair off to the side is only resolved once the head is turned towards it.
    """
    world = deepcopy(pr2_world_state_reset)
    world.get_body_by_name("base_footprint").parent_connection.origin = (
        HomogeneousTransformationMatrix.from_xyz_rpy(0, 0, 0)
    )

    def make_body(name: str) -> Body:
        result = Body(name=PrefixedName(name))
        collision = Box(
            scale=Scale(1.0, 1.0, 1.0),
            origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=result),
        )
        result.collision = ShapeCollection([collision])
        return result

    obstacle = make_body("obstacle")
    occluded_body = make_body("occluded_body")

    with world.modify_world():
        root = world.root
        world.add_connection(
            FixedConnection(
                parent=root,
                child=obstacle,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=root, y=3, z=0.8
                ),
            )
        )
        world.add_connection(
            FixedConnection(
                parent=root,
                child=occluded_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=root, y=10, z=0.5
                ),
            )
        )

    camera = world.get_semantic_annotations_by_type(Camera)[0]
    head_pan = world.get_degree_of_freedom_by_name("head_pan_joint")
    world.state[head_pan.id].position = np.pi / 2
    world.notify_state_change()

    assert obstacle in occluding_bodies(camera, occluded_body)


def test_above_and_below(two_block_world):
    center, top = two_block_world

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(x=-3)
    assert Above(top.center_of_mass, center.center_of_mass, pov)()
    assert Below(center.center_of_mass, top.center_of_mass, pov)()

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(x=3, yaw=np.pi)
    assert Above(top.center_of_mass, center.center_of_mass, pov)()
    assert Below(center.center_of_mass, top.center_of_mass, pov)()

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(x=3, roll=np.pi)
    assert Above(center.center_of_mass, top.center_of_mass, pov)()
    assert Below(top.center_of_mass, center.center_of_mass, pov)()


def test_left_and_right(two_block_world):
    center, top = two_block_world

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(x=3, roll=np.pi / 2)
    assert LeftOf(top.center_of_mass, center.center_of_mass, pov)()
    assert RightOf(center.center_of_mass, top.center_of_mass, pov)()

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(x=3, roll=-np.pi / 2)
    assert RightOf(top.center_of_mass, center.center_of_mass, pov)()
    assert LeftOf(center.center_of_mass, top.center_of_mass, pov)()


def test_behind_and_in_front_of(two_block_world):
    center, top = two_block_world

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(z=-5, pitch=np.pi / 2)
    assert Behind(top.center_of_mass, center.center_of_mass, pov)()
    assert InFrontOf(center.center_of_mass, top.center_of_mass, pov)()

    pov = HomogeneousTransformationMatrix.from_xyz_rpy(z=5, pitch=-np.pi / 2)
    assert InFrontOf(top.center_of_mass, center.center_of_mass, pov)()
    assert Behind(center.center_of_mass, top.center_of_mass, pov)()


def test_body_in_region(two_block_world):
    center, top = two_block_world
    region = Region(name=PrefixedName("test_region"))
    region_box = Box(
        scale=Scale(1.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=region),
    )
    region.area = ShapeCollection([region_box])

    with center._world.modify_world():
        connection = FixedConnection(
            parent=center,
            child=region,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                z=0.5, reference_frame=center
            ),
        )
        center._world.add_connection(connection)
    assert InsideRegion(center, region).compute_contained_fraction() == 0.5
    assert InsideRegion(top, region).compute_contained_fraction() == 0.0
    assert is_body_in_region(center, region)
    assert not is_body_in_region(top, region)


def test_supporting(two_block_world):
    center, top = two_block_world

    with center._world.modify_world():
        top.parent_connection.parent_T_connection_expression = (
            HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=center, z=1.0)
        )
    assert is_supported_by(top, center)
    assert not is_supported_by(center, top)


def test_is_body_in_gripper(pr2_world_copy):
    pr2 = pr2_world_copy.get_semantic_annotations_by_type(PR2)[0]

    gripper = pr2_world_copy.get_semantic_annotations_by_type(EndEffector)

    left_gripper = (
        gripper[0]
        if LeftOf(
            gripper[0].root.center_of_mass,
            gripper[1].root.center_of_mass,
            pr2.root.global_transform,
        )()
        else gripper[1]
    )

    # Create krrood_test box between fingers
    test_box = Body(name=PrefixedName("test_box"))
    box_collision = Box(
        scale=Scale(0.05, 0.01, 0.05),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=test_box),
        color=Color(1.0, 0.0, 0.0),
    )
    test_box.collision = ShapeCollection([box_collision])

    # Calculate position between fingers
    finger1_pos = (
        left_gripper.finger.tip.collision.center_of_mass_in_world().to_vector3()
    )
    finger2_pos = (
        left_gripper.thumb.tip.collision.center_of_mass_in_world().to_vector3()
    )
    between_fingers = (finger1_pos + finger2_pos) / 2.0

    # Add box to world
    with pr2_world_copy.modify_world():
        root = pr2_world_copy.root
        connection = Connection6DoF.create_with_dofs(
            parent=root,
            child=test_box,
            world=pr2_world_copy,
        )
        pr2_world_copy.add_connection(connection)
        connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=between_fingers[0],
            y=between_fingers[1],
            z=between_fingers[2],
            reference_frame=root,
        )

    assert is_body_in_gripper(test_box, left_gripper) > 0
    assert robot_holds_body(pr2, test_box)
    connection.origin = HomogeneousTransformationMatrix(reference_frame=root)
    assert is_body_in_gripper(test_box, left_gripper) == 0


def test_reachable(pr2_world_state_reset, rclpy_node):
    pr2 = pr2_world_state_reset.get_semantic_annotations_by_type(PR2)[0]

    tool_frame_T_reachable_goal = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=-0.2,
        y=0.3,
        reference_frame=pr2.left_arm.end_effector.tool_frame,
    )

    assert reachable(
        tool_frame_T_reachable_goal,
        pr2.left_arm.root,
        pr2.left_arm.end_effector.tool_frame,
    )
    assert not blocking(
        tool_frame_T_reachable_goal,
        pr2.left_arm.root,
        pr2.left_arm.end_effector.tool_frame,
    )
    tool_frame_T_unreachable_goal = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=10, y=10, reference_frame=pr2.left_arm.end_effector.tool_frame
    )
    assert not reachable(
        tool_frame_T_unreachable_goal,
        pr2.left_arm.root,
        pr2.left_arm.end_effector.tool_frame,
    )

    tool_frame_T_rotated_reachable_goal = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=-0.2,
        y=0.3,
        yaw=np.pi / 2,
        reference_frame=pr2.left_arm.end_effector.tool_frame,
    )
    assert reachable(
        tool_frame_T_rotated_reachable_goal,
        pr2.left_arm.root,
        pr2.left_arm.end_effector.tool_frame,
    )

    tool_frame_T_rotated_unreachable_goal = (
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=-0.2,
            y=0.3,
            yaw=-np.pi / 2,
            reference_frame=pr2.left_arm.end_effector.tool_frame,
        )
    )
    assert not reachable(
        tool_frame_T_rotated_unreachable_goal,
        pr2.left_arm.root,
        pr2.left_arm.end_effector.tool_frame,
    )


def test_blocking(pr2_world_copy):
    pr2 = pr2_world_copy.get_semantic_annotations_by_type(PR2)[0]
    obstacle = Body(name=PrefixedName("obstacle"))
    collision = Box(
        scale=Scale(3.0, 1.0, 1.0),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1.0, z=0.5, reference_frame=obstacle
        ),
    )
    obstacle.collision = ShapeCollection([collision])
    obstacle.visual = ShapeCollection([collision])

    with pr2_world_copy.modify_world():
        pr2_world_copy.add_connection(
            Connection6DoF.create_with_dofs(
                parent=pr2_world_copy.root,
                child=obstacle,
                world=pr2_world_copy,
            )
        )

    assert obstacle not in pr2.bodies
    assert robot_in_collision(pr2)

    tool_frame_T_reachable_goal = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=-0.2,
        y=0.3,
        reference_frame=pr2.left_arm.end_effector.tool_frame,
    )
    assert blocking(
        tool_frame_T_reachable_goal,
        pr2.left_arm.root,
        pr2.left_arm.end_effector.tool_frame,
    )


def test_region_is_occupied(pr2_world_state_reset):
    view = pr2_world_state_reset.get_semantic_annotations_by_type(PR2)[0]

    target_box = VolumetricBoundingBox(
        0, 0, 0, 1, 1, 1, HomogeneousTransformationMatrix()
    )
    assert not is_place_occupied(
        target_box,
        Pose.from_xyz_rpy(2.5, 2, 0, reference_frame=pr2_world_state_reset.root),
        pr2_world_state_reset,
    )

    view.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        3.5, 2.5, 0
    )
    pr2_world_state_reset.notify_state_change()

    assert is_place_occupied(target_box, view.root.global_pose, pr2_world_state_reset)

    assert not is_place_occupied(
        target_box,
        Pose.from_xyz_rpy(3.5, 2.5, 1, 0, reference_frame=pr2_world_state_reset.root),
        pr2_world_state_reset,
        view.bodies_with_collision,
    )


def test_is_pose_free_for_robot(pr2_apartment_state_reset):
    view = pr2_apartment_state_reset.get_semantic_annotations_by_type(PR2)[0]
    assert is_pose_free_for_robot(
        view,
        Pose.from_xyz_rpy(2, -2, 0, reference_frame=pr2_apartment_state_reset.root),
    )

    assert not is_pose_free_for_robot(
        view,
        Pose.from_xyz_rpy(3, 2, 0, reference_frame=pr2_apartment_state_reset.root),
    )

    view.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        2, -2, 0
    )

    assert is_pose_free_for_robot(
        view,
        Pose.from_xyz_rpy(2, -2, 0, reference_frame=pr2_apartment_state_reset.root),
    )

    assert is_pose_free_for_robot(
        view,
        Pose.from_xyz_rpy(2.1, -2.1, 0, reference_frame=pr2_apartment_state_reset.root),
    )


def test_is_pose_free_for_robot_with_robot_pose(pr2_apartment_state_reset):
    view = pr2_apartment_state_reset.get_semantic_annotations_by_type(PR2)[0]
    assert is_pose_free_for_robot(
        view,
        Pose.from_xyz_rpy(2, -2, 0, reference_frame=pr2_apartment_state_reset.root),
    )

    assert is_pose_free_for_robot(
        view,
        view.root.global_pose,
    )


def test_bodies_in_gripper(pr2_apartment_world):
    world = deepcopy(pr2_apartment_world)
    tcp = world.get_body_by_name("l_gripper_tool_frame")
    pr2 = world.get_semantic_annotations_by_type(PR2)[0]

    with world.modify_world():
        body = Body(
            name=PrefixedName("mock_milk"),
            collision=ShapeCollection([Box(scale=Scale(0.05, 0.05, 0.3))]),
        )

        connection = FixedConnection(tcp, body)
        world.add_connection(connection)

    pr2.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        2, -2, 0
    )

    bodies = bodies_in_gripper(pr2.left_arm.end_effector)

    assert len(bodies) == 1
    assert bodies[0].name.name == "mock_milk"
    assert bodies[0] == body


def test_empty_gripper_is_not_holding_something():

    @dataclass(eq=False)
    class ReviewEndEffector(EndEffector):
        """
        Minimal concrete EndEffector for predicate tests.
        """

        def setup_hardware_interfaces(self):
            pass

        def setup_joint_states(self) -> List[JointState]:
            return []

        @classmethod
        def setup_default_configuration_in_world_below_robot_root(
            cls, robot_root: KinematicStructureEntity
        ):
            raise NotImplementedError

    world = World()
    root = Body(name=PrefixedName("root", prefix="review"))
    palm = Body(name=PrefixedName("palm", prefix="review"))
    collision = Box(
        scale=Scale(),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=palm),
    )
    palm.collision = ShapeCollection([collision], reference_frame=palm)
    tool_frame = Body(name=PrefixedName("tool_frame", prefix="review"))
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        world.add_kinematic_structure_entity(palm)
        world.add_kinematic_structure_entity(tool_frame)
        world.add_connection(FixedConnection(parent=root, child=palm))
        world.add_connection(FixedConnection(parent=palm, child=tool_frame))
        gripper = ReviewEndEffector(
            name=PrefixedName("gripper", prefix="review"),
            root=palm,
            tool_frame=tool_frame,
            front_facing_orientation=Quaternion(0, 0, 0, 1),
        )
        world.add_semantic_annotation(gripper)

    # nothing is attached below the tool frame -> the gripper holds nothing
    assert is_gripper_holding_something(gripper) is False


@dataclass(eq=False)
class ReviewCamera(Camera):
    """
    Minimal concrete Camera for predicate tests.
    """

    def setup_hardware_interfaces(self):
        pass

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ):
        raise NotImplementedError


def test_nothing_occludes_a_body_in_clear_line_of_sight():

    world = World()
    root = Body(name=PrefixedName("root", prefix="review"))
    camera_body = Body(name=PrefixedName("camera_body", prefix="review"))
    target = Body(name=PrefixedName("target", prefix="review"))
    collision = Box(
        scale=Scale(),
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=target),
    )
    target.collision = ShapeCollection([collision], reference_frame=target)
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        world.add_kinematic_structure_entity(camera_body)
        world.add_kinematic_structure_entity(target)
        world.add_connection(
            FixedConnection(
                parent=root,
                child=camera_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=1.0, reference_frame=root
                ),
            )
        )
        world.add_connection(
            FixedConnection(
                parent=root,
                child=target,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=3.0, z=1.0, reference_frame=root
                ),
            )
        )
        camera = ReviewCamera(
            name=PrefixedName("camera", prefix="review"),
            root=camera_body,
            forward_facing_axis=Vector3.X(),
            field_of_view=FieldOfView(horizontal_angle=0.99, vertical_angle=0.75),
        )
        world.add_semantic_annotation(camera)

    assert occluding_bodies(camera, target) == []


# %% a spatial relation is something a query can state


def test_a_view_dependent_spatial_relation_is_a_predicate():
    """
    A relation a statement asserts has to be a predicate rather than a bare symbol, so a
    query can state it and a search can be devised from it rather than only evaluating
    it after the fact.
    """
    assert issubclass(ViewDependentSpatialRelation, Predicate)


@pytest.mark.parametrize(
    "relation",
    [
        Stable,
        InContactWith,
        VisibleTo,
        Reachable,
        SupportedBy,
        Supports,
        InsideOf,
        InsideRegion,
        PlaceIsOccupied,
        ViewDependentSpatialRelation,
    ],
)
def test_every_relation_is_a_predicate(relation):
    """
    A relation belongs in the vocabulary a statement can assert, so it is a predicate
    even where what it reads is a measurement.
    """
    assert issubclass(relation, Predicate)


def test_containment_answers_whether_it_holds_rather_than_by_how_much(two_block_world):
    center, top = two_block_world

    assert InsideOf(top, center)() in (True, False)


def test_containment_reports_the_fraction_it_measured(two_block_world):
    """
    The judgement is a threshold over a measurement, and the measurement stays readable
    on its own for the callers that compare it against a threshold of their own.
    """
    center, top = two_block_world
    relation = InsideOf(top, center)

    assert relation.compute_containment_ratio() == pytest.approx(
        InsideOf(top, center).compute_containment_ratio()
    )


def test_the_threshold_is_what_turns_the_measurement_into_a_verdict(two_block_world):
    """
    The same pair reads either way depending only on how much containment is asked for,
    which is what makes the threshold the statement of intent rather than a tuned
    constant hidden in the caller.
    """
    center, top = two_block_world
    measured = InsideOf(top, center).compute_containment_ratio()

    assert InsideOf(top, center, minimum_containment_ratio=measured)()
    assert not InsideOf(top, center, minimum_containment_ratio=measured + 0.01)()


def test_support_relates_the_supported_thing_to_what_holds_it_up():
    supported = Body(name=PrefixedName("supported"))
    supporting = Body(name=PrefixedName("supporting"))

    relation = SupportedBy(supported=supported, supporting=supporting)

    assert relation.subject is supported
    assert relation.object is supporting


def test_support_asserted_of_a_variable_is_carried_as_a_symbolic_expression():
    """
    A statement asserts support about the thing it is looking for, which has no value
    yet, so constructing the relation over it has to yield an expression a backend can
    read rather than an instance that would have to be evaluated at once.
    """
    supporting = Body(name=PrefixedName("supporting"))
    sought = variable(Body, [])

    relation = SupportedBy(supported=sought, supporting=supporting)

    stated = StatedRelation.read_from(relation, sought)
    assert stated.relation_type is SupportedBy
    assert stated.related_thing is supporting


def test_support_holds_exactly_where_the_geometric_reading_says_it_does(
    two_block_world,
):
    center, top = two_block_world

    assert SupportedBy(supported=top, supporting=center)() is is_supported_by(
        top, center
    )


# %% how a relation reads


def test_reachability_reads_the_pose_as_what_is_reachable():
    """
    Reachability is stated about the pose, by the tip that has to arrive at it, so the
    pose is the subject of the sentence rather than the chain that reaches for it.
    """
    operands = placeholder_operands(Reachable)
    operands.update(Reachable._example_operand_values_())

    assert (
        verbalize_expression(Reachable(**operands))
        == "a HomogeneousTransformationMatrix is reachable by a Body"
    )


@pytest.mark.parametrize(
    "relation, sentence",
    [
        (SupportedBy, "a Body is supported by another Body"),
        (VisibleTo, "a Body or a Region is visible to a Camera"),
        (InContactWith, "a Body is in contact with another Body"),
        (Supports, "a Body is supporting a body"),
    ],
)
def test_a_relation_named_for_its_object_still_reads_as_a_sentence(relation, sentence):
    """
    A relation whose name is not verb-first cannot have its verb read off that name, so
    it states its own clause rather than inheriting one that renders ungrammatically.
    """
    operands = placeholder_operands(relation)
    operands.update(relation._example_operand_values_())

    assert verbalize_expression(relation(**operands)) == sentence


def test_a_direction_says_where_it_was_read_from():
    """
    A direction holds from somewhere rather than of the world, so it says so and names
    the frame it was read from, instead of the matrix that frame's pose is stored as.
    """
    camera = Body(name=PrefixedName("camera", "tracy"))
    operands = placeholder_operands(LeftOf)
    operands["point_of_view"] = HomogeneousTransformationMatrix(child_frame=camera)

    assert verbalize_expression(LeftOf(**operands)).endswith(
        f"as seen from the {camera.name.name}"
    )


# %% where a relation allows a thing to be


@pytest.fixture(scope="function")
def three_places() -> Tuple[World, Body, Body, Body]:
    """
    A world holding three bodies a metre apart along the x axis, at y = 0.
    """
    world = World()
    root = Body(name=PrefixedName("root"))
    placed = [Body(name=PrefixedName(f"place_{step}")) for step in range(3)]
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        for step, body in enumerate(placed):
            world.add_connection(
                FixedConnection(
                    parent=root,
                    child=body,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=float(step), reference_frame=root
                    ),
                )
            )
    world.update_forward_kinematics()
    return (world, *placed)


def looking_along_x(world: World) -> HomogeneousTransformationMatrix:
    """
    A point of view facing along the world's own x axis, which is the one an axis-
    aligned box can hold exactly what a direction from it allows.

    :param world: The world it stands in.
    """
    return HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=world.root)


def test_a_direction_is_stated_about_things_rather_than_about_their_coordinates(
    three_places,
):
    """
    A statement relates the things the world holds, so a relation reads where each of
    them stands rather than being handed a point measured beforehand.
    """
    world, near, middle, far = three_places
    point_of_view = looking_along_x(world)

    assert InFrontOf(far, middle, point_of_view)()
    assert Behind(near, middle, point_of_view)()
    assert not InFrontOf(near, middle, point_of_view)()


def test_a_direction_leaves_everything_on_its_own_side_of_the_other_thing(three_places):
    world, near, middle, far = three_places

    allowed = InFrontOf(
        other=middle, point_of_view=looking_along_x(world)
    ).allowed_space

    assert allowed.x_interval.lower == pytest.approx(
        float(middle.global_pose.to_position().x)
    )
    assert allowed.x_interval.upper == np.inf
    assert (allowed.y_interval.lower, allowed.y_interval.upper) == (-np.inf, np.inf)
    assert allowed.contains(far.global_pose.to_position())
    assert not allowed.contains(near.global_pose.to_position())


def test_a_direction_running_across_the_worlds_axes_narrows_nothing_and_still_answers(
    three_places,
):
    """
    No axis-aligned box holds exactly what a direction across the world's own axes
    allows, so the narrowing gives up rather than reporting a stretch that leaves out
    somewhere the relation allows -- and the relation itself still answers exactly.
    """
    world, near, middle, far = three_places
    turned = HomogeneousTransformationMatrix.from_xyz_rpy(
        yaw=np.pi / 4, reference_frame=world.root
    )
    relation = InFrontOf(far, middle, turned)

    assert relation.allowed_space.x_interval.lower == -np.inf
    assert relation.allowed_space.x_interval.upper == np.inf
    assert relation()


def stretch_around_the_places(world: World) -> VolumetricBoundingBox:
    """
    A bounded stretch of the world holding all three places, which is the kind of thing
    a search is about to read.

    :param world: The world they stand in.
    """
    return space_between(
        np.array([-1.0, -1.0, -0.5]), np.array([3.0, 1.0, 0.5]), world.root
    )


def test_a_direction_across_the_worlds_axes_narrows_a_stretch_that_is_bounded(
    three_places,
):
    """
    Asked about the world a tilted direction can answer nothing, since no axis-aligned
    box holds a half space; asked about a stretch already bounded it answers the part of
    it on its own side, which is what lets a search read less picture for a direction
    stated from where a camera stands.
    """
    world, near, middle, far = three_places
    turned = HomogeneousTransformationMatrix.from_xyz_rpy(
        yaw=np.pi / 4, reference_frame=world.root
    )
    relation = InFrontOf(other=middle, point_of_view=turned)
    stretch = stretch_around_the_places(world)

    narrowed = relation.allowed_part_of(stretch)

    assert narrowed.x_interval.lower > stretch.x_interval.lower
    assert narrowed.x_interval.upper == pytest.approx(stretch.x_interval.upper)
    assert narrowed.contains(far.global_pose.to_position())


def test_a_stretch_wholly_against_a_direction_is_left_with_nothing_of_it(three_places):
    world, near, middle, far = three_places
    relation = Behind(other=middle, point_of_view=looking_along_x(world))

    assert (
        relation.allowed_part_of(
            space_between(
                np.array([1.5, -1.0, -0.5]), np.array([3.0, 1.0, 0.5]), world.root
            )
        )
        is None
    )


def test_a_relation_that_can_say_where_it_allows_narrows_by_meeting_the_stretch(
    three_places,
):
    """
    A relation whose own stretch is bounded needs no cutting: what it leaves of another
    is the ground the two share.
    """
    world, near, middle, far = three_places
    relation = Near(place=middle, radius=0.5)

    narrowed = relation.allowed_part_of(stretch_around_the_places(world))

    assert narrowed == relation.allowed_space.intersection_with(
        stretch_around_the_places(world)
    )


def test_a_relation_stated_about_nothing_says_what_it_allows_but_not_whether_it_holds(
    three_places,
):
    world, near, middle, far = three_places
    constraint = RightOf(other=middle, point_of_view=looking_along_x(world))

    assert constraint.allowed_space.y_interval.upper == pytest.approx(
        float(middle.global_pose.to_position().y)
    )
    with pytest.raises(RelationStatedAboutNothing):
        constraint()


def test_left_and_right_are_the_two_sides_of_the_point_of_views_own_y_axis(
    three_places,
):
    world, near, middle, far = three_places
    point_of_view = looking_along_x(world)
    beside = Point3(1.0, 0.5, 0.0, reference_frame=world.root)

    assert LeftOf(beside, middle, point_of_view)()
    assert not RightOf(beside, middle, point_of_view)()
    assert RightOf(middle, beside, point_of_view)()


def test_between_holds_along_the_line_joining_two_things(three_places):
    world, near, middle, far = three_places

    assert Between(middle, near, far)()
    assert not Between(near, middle, far)()


def test_between_refuses_a_place_further_to_the_side_than_the_fraction_allows(
    three_places,
):
    world, near, middle, far = three_places
    apart = float(
        np.linalg.norm(
            far.global_pose.to_position().to_np()[:3]
            - near.global_pose.to_position().to_np()[:3]
        )
    )
    relation = Between(one=near, other=far)
    just_inside = Point3(
        1.0, relation.maximum_sideways_fraction * apart, 0.0, reference_frame=world.root
    )
    just_outside = Point3(
        1.0,
        relation.maximum_sideways_fraction * apart + 0.01,
        0.0,
        reference_frame=world.root,
    )

    assert relation.allows(just_inside)
    assert not relation.allows(just_outside)


def test_between_leaves_a_stretch_holding_everything_it_allows(three_places):
    world, near, middle, far = three_places
    relation = Between(one=near, other=far)
    reach = relation.maximum_sideways_fraction * 2.0

    allowed = relation.allowed_space

    assert allowed.x_interval.lower == pytest.approx(-reach)
    assert allowed.x_interval.upper == pytest.approx(2.0 + reach)
    assert allowed.contains(middle.global_pose.to_position())


def test_near_holds_within_the_radius_it_was_stated_with(three_places):
    world, near, middle, far = three_places

    assert Near(near, middle, radius=1.5)()
    assert not Near(near, middle, radius=0.5)()


def test_near_leaves_the_box_its_radius_reaches_into(three_places):
    world, near, middle, far = three_places
    radius = 0.25

    allowed = Near(place=middle, radius=radius).allowed_space

    middle_x = float(middle.global_pose.to_position().x)
    assert allowed.x_interval.lower == pytest.approx(middle_x - radius)
    assert allowed.x_interval.upper == pytest.approx(middle_x + radius)


def test_near_reads_a_pose_as_the_place_it_is_measured_from(three_places):
    """
    A place worth searching around is as often a pose the robot is about to reach for as
    a thing already standing there, so either can be stated.
    """
    world, near, middle, far = three_places
    pose = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=1.1, reference_frame=world.root
    )

    assert Near(middle, pose, radius=0.2)()


def test_a_body_is_colored_the_color_its_own_shape_is_drawn_in():
    body = Body(name=PrefixedName("colored_body"))
    color = Color(0.0, 1.0, 1.0)
    body.collision = ShapeCollection(
        [
            Box(
                scale=Scale(0.1, 0.1, 0.1),
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=body
                ),
                color=color,
            )
        ],
        reference_frame=body,
    )

    assert Colored(body, color)()
    assert not Colored(body, Color(1.0, 0.0, 0.0))()


@pytest.mark.parametrize(
    "relation", [LeftOf, RightOf, Above, Below, Behind, InFrontOf, Between, Near]
)
def test_every_placement_relation_says_where_the_thing_it_is_about_may_be(relation):
    """
    Saying where a thing may be is what lets a search act on a relation before anything
    has been found, so it is the family every one of them belongs to.
    """
    assert issubclass(relation, PlacementRelation)


def test_a_relation_of_more_than_two_operands_is_still_asserted_about_one_thing():
    """
    Between relates the thing sought to two others at once, so it is not a triple -- but
    it still names the thing it is about, which is what a look reads it by.
    """
    assert issubclass(Between, Relation)
    assert not issubclass(Between, Triple)


def test_a_color_reads_as_something_the_thing_is_rather_than_something_it_does():
    operands = placeholder_operands(Colored)
    operands.update(Colored._example_operand_values_())

    assert verbalize_expression(Colored(**operands)) == "a Body is colored a Color"


@pytest.mark.parametrize(
    "assertion, sentence",
    [
        (
            lambda sought, one, other: Between(sought, one, other),
            "Generate an object where it is between a specific Body and a specific Body",
        ),
        (
            lambda sought, one, other: Near(sought, one, radius=0.05),
            "Generate an object where it is within 0.05 of a specific Body",
        ),
    ],
)
def test_a_relation_this_vocabulary_adds_reads_as_a_sentence(assertion, sentence):
    """
    A relation over places is stated about the thing a statement is looking for, so what
    it has to read as a sentence is the statement asserting it.
    """
    one = Body(name=PrefixedName("one"))
    other = Body(name=PrefixedName("other"))
    statement = an(object)()
    statement = statement.where(assertion(statement.variable, one, other))

    assert verbalize_expression(statement) == sentence


# %% relations answered without symbolic geometry


def _refuse_to_build(*args, **kwargs):
    """
    Stand in for symbolic machinery a numeric check must never reach.
    """
    raise AssertionError("a symbolic value was built")


def test_supporting_builds_nothing_symbolic(two_block_world, monkeypatch):
    """
    Support is checked on every detector tick, from a thread that does not own the
    world, so the check must reach its answer without touching CasADi.
    """
    center, top = two_block_world
    with center._world.modify_world():
        top.parent_connection.parent_T_connection_expression = (
            HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=center, z=1.0)
        )
    expected = is_supported_by(top, center)
    monkeypatch.setattr(HomogeneousTransformationMatrix, "__init__", _refuse_to_build)
    monkeypatch.setattr(HomogeneousTransformationMatrix, "to_np", _refuse_to_build)
    monkeypatch.setattr(Point3, "__init__", _refuse_to_build)
    monkeypatch.setattr(Vector3, "__init__", _refuse_to_build)

    assert is_supported_by(top, center) == expected


def test_bodies_nowhere_near_each_other_support_nothing(two_block_world):
    """
    Most candidate pairs a detector tick asks about are far apart, and are ruled out
    without an exact intersection ever being computed.
    """
    center, top = two_block_world

    assert not is_supported_by(top, center)
    assert not is_supported_by(center, top)


# %% containment answered numerically
@pytest.fixture(scope="function")
def container_and_content():
    """
    A hollow-free box twice the size of the one placed inside it, movable relative to
    it.

    The inner box's corners sit well inside the outer box's faces, so a test moves it
    without landing any corner exactly on a boundary.
    """
    container = Body(name=PrefixedName("container"))
    container.collision = ShapeCollection(
        [
            Box(
                scale=Scale(2.0, 2.0, 2.0),
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=container
                ),
            )
        ],
        reference_frame=container,
    )

    content = Body(name=PrefixedName("content"))
    content.collision = ShapeCollection(
        [
            Box(
                scale=Scale(1.0, 1.0, 1.0),
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=content
                ),
            )
        ],
        reference_frame=content,
    )

    world = World()
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=container,
                child=content,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=container
                ),
            )
        )
    return container, content


def _place_content(container: Body, content: Body, z: float) -> None:
    """
    Move the inner box to a height above the outer box's own frame.
    """
    with container._world.modify_world():
        content.parent_connection.parent_T_connection_expression = (
            HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=container, z=z)
        )


def test_a_body_within_another_is_entirely_contained(container_and_content):
    container, content = container_and_content

    assert InsideOf(content, container).compute_containment_ratio() == 1.0


def test_a_body_beyond_another_is_not_contained_at_all(container_and_content):
    container, content = container_and_content
    _place_content(container, content, z=5.0)

    assert InsideOf(content, container).compute_containment_ratio() == 0.0


def test_a_body_crossing_another_is_contained_in_proportion(container_and_content):
    """
    Half the inner box's corners are still inside the outer box once it is lifted far
    enough that its top face clears the outer box's own.
    """
    container, content = container_and_content
    _place_content(container, content, z=1.0)

    assert InsideOf(content, container).compute_containment_ratio() == 0.5


def test_containment_builds_nothing_symbolic(container_and_content, monkeypatch):
    """
    Containment is checked against every collidable body on every detector tick, so it
    must reach its answer without touching CasADi.
    """
    container, content = container_and_content
    _place_content(container, content, z=1.0)
    expected = InsideOf(content, container).compute_containment_ratio()
    monkeypatch.setattr(HomogeneousTransformationMatrix, "__init__", _refuse_to_build)
    monkeypatch.setattr(HomogeneousTransformationMatrix, "to_np", _refuse_to_build)
    monkeypatch.setattr(Point3, "__init__", _refuse_to_build)

    assert InsideOf(content, container).compute_containment_ratio() == expected


# %% which way a thing is turned


def test_turned_holds_within_the_spread_it_was_stated_with(three_places):
    world, near, middle, far = three_places
    pose = HomogeneousTransformationMatrix.from_xyz_rpy(
        yaw=0.5, reference_frame=world.root
    )

    assert Turned(pose, yaw=0.4, spread=0.2)()
    assert not Turned(pose, yaw=0.0, spread=0.2)()


def test_turned_reads_a_turn_the_short_way_round():
    """
    A turn just past a half circle is a small turn the other way, not a large one.
    """
    assert Turned(yaw=np.pi - 0.05, spread=0.2).allows_turn(-np.pi + 0.05)


def test_turned_reads_the_turn_off_a_thing_the_world_places(three_places):
    world, near, middle, far = three_places

    assert Turned(middle, yaw=0.0, spread=0.01)()


def test_turned_stated_about_nothing_refuses_to_say_whether_it_holds():
    with pytest.raises(RelationStatedAboutNothing):
        Turned(yaw=0.0, spread=0.1)()


def test_turned_is_a_relation_a_statement_can_state():
    assert issubclass(Turned, Predicate)
