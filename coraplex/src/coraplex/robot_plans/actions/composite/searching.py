from __future__ import annotations

from dataclasses import dataclass, field

import krrood.symbolic_math.symbolic_math as sm
from coraplex.datastructures.enums import DetectionTechnique
from coraplex.locations.locations import VisibilityLocation
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.misc import DetectAction
from coraplex.robot_plans.actions.core.navigation import LookAtAction, NavigateAction
from cramph.composites import Parallel, Sequence, TryInOrder
from cramph.context import StatechartContext
from cramph.node import NodeArtifacts, StatechartNode, SucceedsOnObservingTrue
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from krrood.entity_query_language.factories import a, variable
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_part_mixins import HasMobileBase
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Vector3
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    PrismaticConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import (
    DegreeOfFreedomLimits,
)
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.world_entity import (
    Body,
    SemanticAnnotation,
)

# %% the region a search sweeps across its target


@dataclass
class SweepRegion:
    """
    A frame the robot looks at while it slides across a target, at right angles to where
    the robot faces.
    """

    placement: Connection6DoF
    """
    Puts the region at the target, turned like the robot's base.
    """

    sweep: PrismaticConnection
    """
    Slides the region along its y-axis, which is the left of the robot's base.
    """

    @classmethod
    def for_robot(
        cls, robot: HasMobileBase, half_width: float, speed: float
    ) -> SweepRegion:
        """
        :param robot: The robot that looks at the region.
        :param half_width: How far the region has to slide to either side of the target.
        :param speed: How fast the region has to be able to slide, in meters per second.
        :return: The sweep region of `robot`, added to its world unless it has one
            already, able to slide at least `half_width` at `speed`.
        """
        sweep_region = cls.in_world_of(robot)
        if sweep_region is None:
            return cls._added_for(robot, half_width, speed)
        sweep_region._allow(half_width, speed)
        return sweep_region

    @classmethod
    def in_world_of(cls, robot: HasMobileBase) -> SweepRegion | None:
        """
        :param robot: The robot that looks at the region.
        :return: The sweep region of `robot` in its world, or None if it has none.
        """
        regions = robot._world.get_bodies_by_name(cls._name_for(robot))
        if not regions:
            return None
        [region] = regions
        sweep = region.parent_connection
        return cls(placement=sweep.parent.parent_connection, sweep=sweep)

    @classmethod
    def _added_for(
        cls, robot: HasMobileBase, half_width: float, speed: float
    ) -> SweepRegion:
        """
        :param robot: The robot that looks at the region.
        :param half_width: How far the region slides to either side of the target.
        :param speed: How fast the region slides, in meters per second.
        :return: A new sweep region of `robot` in its world, at the world's origin until
            it is placed.
        """
        world = robot._world
        name = cls._name_for(robot)
        origin = Body(name=PrefixedName(f"{name.name}_origin", name.prefix))
        region = Body(name=name)
        with world.modify_world():
            world.add_kinematic_structure_entity(origin)
            world.add_kinematic_structure_entity(region)
            placement = Connection6DoF.create_with_dofs(
                world=world, parent=world.root, child=origin
            )
            sweep = PrismaticConnection.create_with_dofs(
                world=world,
                parent=origin,
                child=region,
                axis=Vector3.Y(),
                dof_limits=DegreeOfFreedomLimits.from_position_range_and_speed(
                    lower_position=-half_width,
                    upper_position=half_width,
                    maximum_speed=speed,
                ),
            )
            world.add_connection(placement)
            world.add_connection(sweep)
        return cls(placement=placement, sweep=sweep)

    @staticmethod
    def _name_for(robot: HasMobileBase) -> PrefixedName:
        """
        :param robot: The robot that looks at the region.
        :return: The name of the body of the sweep region of `robot`.
        """
        return PrefixedName("sweep_region", str(robot.name))

    def _allow(self, half_width: float, speed: float) -> None:
        """
        Widens the limits of :attr:`sweep` so that it slides at least `half_width` to
        either side at `speed`, keeping whatever wider limits it has already.

        :param half_width: How far the region has to slide to either side.
        :param speed: How fast the region has to be able to slide.
        """
        limits = self.sweep.dof.limits
        half_width = max(half_width, limits.upper.position)
        speed = max(speed, limits.upper.velocity)
        self.sweep.dof.limits = DegreeOfFreedomLimits.from_position_range_and_speed(
            lower_position=-half_width, upper_position=half_width, maximum_speed=speed
        )

    def remove(self) -> None:
        """
        Removes the region from its world.
        """
        world = self.placement._world
        world.remove_branch_from_world(self.placement.child)

    def place(self, target: Pose, robot: HasMobileBase) -> None:
        """
        Puts the region at `target`, turned like the front of the robot's base now.

        :param target: Where the region slides across.
        :param robot: The robot whose base decides which way is sideways.
        """
        world = self.placement._world
        world_R_base = robot.mobile_base.root.global_transform.rotation_matrix
        self.placement.origin = (
            HomogeneousTransformationMatrix.from_point_rotation_matrix(
                point=world.transform(target, world.root).position,
                rotation_matrix=world_R_base @ robot.mobile_base.base_R_front,
                reference_frame=world.root,
            )
        )


@dataclass(eq=False, repr=False)
class SweepRegionPlacement(SucceedsOnObservingTrue, StatechartNode):
    """
    Places a :class:`SweepRegion` at its target when it starts, turned like the robot's
    base as it stands then, and succeeds once it did.
    """

    sweep_region: SweepRegion = field(kw_only=True)
    """
    The region to place.
    """

    target: Pose = field(kw_only=True)
    """
    Where the region slides across.
    """

    robot: HasMobileBase = field(kw_only=True)
    """
    The robot whose base decides which way is sideways.
    """

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        return NodeArtifacts(observation=sm.Scalar.const_true())

    def on_start(self, context: StatechartContext) -> None:
        self.sweep_region.place(self.target, self.robot)


# %% searching for an object


@dataclass(eq=False, repr=False)
class SearchAction(Action):
    """
    Searches for an object around a location.

    The robot drives to a pose the location is visible from and looks at the location,
    then to either side of it, until the object is detected. The action fails if the
    object is seen from none of them.
    """

    target_location: Pose
    """
    Location around which to look for the object.
    """

    object_semantic_annotation: type[SemanticAnnotation]
    """
    Type of the object which is searched for.
    """

    sideways_look_offsets: tuple[float, ...] = (0.0, -0.5, 0.5)
    """
    How far to the left of :attr:`target_location` the robot looks, as seen from where
    it stands, in the order the looks are tried; negative offsets look to the right.
    """

    sweep_speed: float = 0.5
    """
    How fast the point looked at moves from one look to the next, in meters per second.
    """

    detection_margin: float = 0.5
    """
    How far beyond the points looked at an object may lie and still be detected.
    """

    def create_action_body(self) -> StatechartNode:
        sweep_region = SweepRegion.for_robot(
            self.robot, half_width=self._half_sweep_width(), speed=self.sweep_speed
        )
        detection_box = self._detection_box()
        return Sequence(
            [
                a(NavigateAction)(
                    target_location=variable(
                        Pose,
                        domain=VisibilityLocation(
                            target_pose=self.target_location,
                            context=self.context,
                            seed=self.sampling_seed,
                        ),
                    )
                ),
                SweepRegionPlacement(
                    sweep_region=sweep_region,
                    target=self.target_location,
                    robot=self.robot,
                ),
                TryInOrder(
                    [
                        Sequence(
                            [
                                Parallel(
                                    [
                                        LookAtAction(
                                            Pose(
                                                reference_frame=sweep_region.sweep.child
                                            )
                                        ),
                                        JointPositionList(
                                            goal_state=JointState.from_mapping(
                                                {sweep_region.sweep: sideways_offset}
                                            ),
                                            max_velocity=self.sweep_speed,
                                        ),
                                    ]
                                ),
                                DetectAction(
                                    DetectionTechnique.TYPES,
                                    object_sem_annotation=self.object_semantic_annotation,
                                    detection_box=detection_box,
                                ),
                            ]
                        )
                        for sideways_offset in self.sideways_look_offsets
                    ]
                ),
            ]
        )

    def cleanup(self, context: StatechartContext) -> None:
        """
        Removes the sweep region of the robot from the world once the plan ended, unless
        another search of the robot already did.
        """
        sweep_region = SweepRegion.in_world_of(self.robot)
        if sweep_region is None:
            return
        sweep_region.remove()

    def _half_sweep_width(self) -> float:
        """
        :return: How far the farthest look lies to the side of :attr:`target_location`.
        """
        return max(abs(offset) for offset in self.sideways_look_offsets)

    def _detection_box(self) -> VolumetricBoundingBox:
        """
        :return: The cube around :attr:`target_location` that holds every point looked
            at, widened by :attr:`detection_margin`.
        """
        half_extent = self._half_sweep_width() + self.detection_margin
        x, y, z = self.target_location.position.to_np().flatten()[:3]
        return VolumetricBoundingBox(
            origin=HomogeneousTransformationMatrix(
                reference_frame=self.target_location.reference_frame
            ),
            min_x=x - half_extent,
            min_y=y - half_extent,
            min_z=z - half_extent,
            max_x=x + half_extent,
            max_y=y + half_extent,
            max_z=z + half_extent,
        )
