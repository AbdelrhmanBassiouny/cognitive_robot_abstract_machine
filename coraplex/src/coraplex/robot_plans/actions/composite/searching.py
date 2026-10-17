from __future__ import annotations

from dataclasses import dataclass

from coraplex.datastructures.enums import DetectionTechnique
from coraplex.locations.locations import VisibilityLocation
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.misc import DetectAction
from coraplex.robot_plans.actions.core.navigation import LookAtAction, NavigateAction
from cramph.composites import Sequence, TryInOrder
from cramph.node import StatechartNode
from krrood.entity_query_language.factories import a, variable
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.world_entity import SemanticAnnotation

# %% searching for an object


@dataclass(eq=False, repr=False, kw_only=True)
class SearchAction(Action):
    """
    Searches for an object around a location.

    The robot drives to a pose the location is visible from and looks at the location,
    then at the ends of a cross around it along the x- and y-axes of the location's
    reference frame, until the object is detected. The action fails if the object is
    seen from none of them.
    """

    target_location: Pose
    """
    Location around which to look for the object.
    """

    object_semantic_annotation: type[SemanticAnnotation]
    """
    Type of the object which is searched for.
    """

    cross_arm_length: float = 0.5
    """
    How far from :attr:`target_location` the ends of the cross lie.
    """

    detection_margin: float = 0.5
    """
    How far beyond the points looked at an object may lie and still be detected.
    """

    def create_action_body(self) -> StatechartNode:
        detection_box = self._detection_box()
        return Sequence(
            nodes=[
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
                TryInOrder(
                    nodes=[
                        Sequence(
                            nodes=[
                                LookAtAction(target=look_target),
                                DetectAction(
                                    technique=DetectionTechnique.TYPES,
                                    object_sem_annotation=self.object_semantic_annotation,
                                    detection_box=detection_box,
                                ),
                            ]
                        )
                        for look_target in self.look_targets()
                    ]
                ),
            ]
        )

    def look_targets(self) -> list[Pose]:
        """
        :return: :attr:`target_location`, then the ends of the cross around it, in the
            order the robot looks at them.
        """
        x, y, z = self.target_location.position.to_np().flatten()[:3]
        arm = self.cross_arm_length
        return [
            Pose.from_xyz_rpy(
                x + x_offset,
                y + y_offset,
                z,
                reference_frame=self.target_location.reference_frame,
            )
            for x_offset, y_offset in [(0, 0), (arm, 0), (-arm, 0), (0, arm), (0, -arm)]
        ]

    def _detection_box(self) -> VolumetricBoundingBox:
        """
        :return: The cube around :attr:`target_location` that holds every point looked
            at, widened by :attr:`detection_margin`.
        """
        half_extent = self.cross_arm_length + self.detection_margin
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
