from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

import trimesh.sample
from typing_extensions import Self

from krrood.entity_query_language.factories import (
    entity,
    variable,
    contains,
    an,
    the,
)
from krrood.entity_query_language.predicate import (
    Predicate,
    SymbolicFunction,
    functional_form,
)
from krrood.entity_query_language.verbalization.fragments.base import WordFragment
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    clause,
    Copula,
    Noun,
    Preposition,
    Verb,
)
from semantic_digital_twin.collision_checking.collision_detector import (
    ClosestPoints,
)
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionBetweenGroups,
    AvoidExternalCollisions,
    AllowSelfCollisions,
)
from semantic_digital_twin.reasoning.predicates import is_place_occupied
from semantic_digital_twin.robots.robot_part_mixins import HasTwoFingers
from semantic_digital_twin.robots.robot_parts import (
    AbstractRobot,
    EndEffector,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import Floor
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.geometry import BoundingBox
from semantic_digital_twin.world_description.world_entity import Body


@dataclass(eq=False)
class RobotCollisions(SymbolicFunction):
    """The collision contacts between a robot and the world at the robot's current pose."""

    robot: AbstractRobot
    """The robot checked for collisions."""

    ignore_collision_with: Optional[List[Body]] = None
    """Bodies to ignore collisions with."""

    threshold: float = 0.001
    """The buffer-zone distance for contact detection."""

    def __call__(self) -> List[ClosestPoints]:
        ignore_collision_with = self.ignore_collision_with or []

        world = self.robot._world

        with world.modify_world():
            world.collision_manager.clear_temporary_rules()
            world.collision_manager.add_temporary_rule(
                AvoidExternalCollisions(
                    buffer_zone_distance=self.threshold,
                    robot=self.robot,
                )
            )
            world.collision_manager.add_temporary_rule(
                AllowSelfCollisions(robot=self.robot)
            )
            world.collision_manager.add_temporary_rule(
                AllowCollisionBetweenGroups(
                    body_group_a=self.robot.bodies,
                    body_group_b=ignore_collision_with,
                )
            )
        world.collision_manager.update_collision_matrix()

        collisions = world.collision_manager.compute_collisions()

        return collisions.contacts


robot_in_collision = functional_form(RobotCollisions)


@dataclass(eq=False)
class RobotHoldsBody(Predicate):
    """Whether a robot is holding a body in one of its grippers."""

    robot: AbstractRobot
    """The robot."""

    body: Body
    """The body checked for being held."""

    def __call__(self) -> bool:
        g = variable(EndEffector, self.robot._world.semantic_annotations)
        grippers = an(
            entity(g).where(
                g._robot == self.robot,
            )
        )

        return any(
            [
                is_body_in_gripper(self.body, gripper) > 0.0
                for gripper in grippers.evaluate()
            ]
        )

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "<robot> holds <body>" -- the name starts with the subject noun, so the name-based default
        # would read it as a verb ("a robot robots holds body").
        return clause(Noun(operands.robot), Verb("hold"), Noun(operands.body))


robot_holds_body = functional_form(RobotHoldsBody)


@dataclass(eq=False)
class BlockingBodies(SymbolicFunction):
    """The bodies blocking a robot from reaching a pose.

    These are the bodies the robot is in collision with when its kinematic chain is moved to reach
    the pose by inverse kinematics.
    """

    pose: HomogeneousTransformationMatrix
    """The pose to reach."""

    root: Body
    """The root of the kinematic chain."""

    tip: Body
    """The tip (end effector) of the kinematic chain."""

    def __call__(self) -> List[ClosestPoints]:
        result = self.root._world.compute_inverse_kinematics(
            root=self.root, tip=self.tip, target=self.pose, max_iterations=1000
        )
        with self.root._world.modify_world():
            for dof, state in result.items():
                self.root._world.state[dof.id].position = state

        r = variable(AbstractRobot, self.root._world.semantic_annotations)
        robot = the(
            entity(r).where(
                contains(r.bodies, self.tip),
            )
        )
        return robot_in_collision(robot.first(), [])


blocking = functional_form(BlockingBodies)


@dataclass(eq=False)
class BodiesInGripper(SymbolicFunction):
    """The bodies between the two fingers of a gripper, found by ray casting between the fingers."""

    gripper: HasTwoFingers
    """The gripper to check between."""

    sample_size: int = 100
    """The number of rays to sample."""

    def __call__(self) -> List[Body]:
        gripper = self.gripper
        # Retrieve meshes in local frames
        thumb_mesh = gripper.thumb.tip.collision.combined_mesh.copy()
        finger_mesh = gripper.finger.tip.collision.combined_mesh.copy()

        # Transform copies of the meshes into the world frame
        # body_mesh.apply_transform(body.global_transform.to_np())
        thumb_mesh.apply_transform(gripper.thumb.tip.global_transform.to_np())
        finger_mesh.apply_transform(gripper.finger.tip.global_transform.to_np())

        # get random points from thumb mesh
        finger_points = trimesh.sample.sample_surface(finger_mesh, self.sample_size)[0]
        thumb_points = trimesh.sample.sample_surface(thumb_mesh, self.sample_size)[0]

        rt = gripper._world.ray_tracer
        rt.update_scene()

        points, index_ray, bodies = rt.ray_test(finger_points, thumb_points)
        return list(
            set(bodies) - set(gripper.finger.bodies) - set(gripper.thumb.bodies)
        )


bodies_in_gripper = functional_form(BodiesInGripper)


@dataclass(eq=False)
class BodyInGripperFraction(SymbolicFunction):
    """The fraction of sampled rays between a gripper's fingers that hit a given body.

    Random rays are sampled between the finger and thumb; the returned value is the marginal
    probability that a ray hits the body.
    """

    body: Body
    """The body checked for being in the gripper."""

    gripper: EndEffector
    """The gripper to check."""

    sample_size: int = 100
    """The number of rays to sample."""

    def __call__(self) -> float:
        bodies = bodies_in_gripper(self.gripper, self.sample_size)
        return len([b for b in bodies if b == self.body]) / self.sample_size


is_body_in_gripper = functional_form(BodyInGripperFraction)


@dataclass(eq=False)
class IsGripperHoldingSomething(Predicate):
    """Whether a gripper is holding something -- a body mounted beneath it in the kinematic chain."""

    gripper: EndEffector
    """The gripper to check."""

    def __call__(self) -> bool:
        bodies_under_tcp = self.gripper._world.get_kinematic_structure_entities_of_branch(
            self.gripper.tool_frame
        )
        # the branch always contains the tool frame itself, so only additional
        # entities below it count as something being held
        return len(bodies_under_tcp) > 1

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "<gripper> holds something" -- the name does not read as a clause on its own. "something"
        # is a bare word (no article).
        return clause(
            Noun(operands.gripper), Verb("hold"), WordFragment(text="something")
        )


is_gripper_holding_something = functional_form(IsGripperHoldingSomething)


@dataclass(eq=False)
class IsPoseFreeForRobot(Predicate):
    """Whether a pose is free for a robot -- its mobile base would not collide there (ignoring the
    robot's own bodies and the floor)."""

    robot: AbstractRobot
    """The robot whose mobile base is checked."""

    pose: Pose
    """The pose checked for being free."""

    def __call__(self) -> bool:
        return not is_place_occupied(
            self.robot.mobile_base.bounding_box,
            self.pose,
            self.robot._world,
            self.robot.bodies_with_collision
            + [
                kse
                for annotation in self.robot._world.get_semantic_annotations_by_type(
                    Floor
                )
                for kse in annotation.kinematic_structure_entities
            ],
        )

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "the <pose> is free for <robot>" -- an adjective relation with a preposition.
        return clause(
            Noun(operands.pose),
            Copula(),
            Adjective("free"),
            Preposition.FOR,
            Noun(operands.robot),
        )


is_pose_free_for_robot = functional_form(IsPoseFreeForRobot)
