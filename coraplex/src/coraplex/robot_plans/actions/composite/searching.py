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
    Distances along the y-axis of :attr:`target_location` that are looked at, in order.
    """

    detection_half_extent: float = 0.5
    """
    Half the edge length of the cube around each looked-at point in which the object is
    detected.
    """

    def create_action_body(self) -> StatechartNode:
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
                TryInOrder(
                    [
                        self._look_and_detect(sideways_offset)
                        for sideways_offset in self.sideways_look_offsets
                    ]
                ),
            ]
        )

    def _look_and_detect(self, sideways_offset: float) -> StatechartNode:
        """
        :param sideways_offset: Distance along the y-axis of :attr:`target_location`.
        :return: A node looking at :attr:`target_location` moved sideways and detecting
            the object around the point looked at.
        """
        reference_T_target = self.target_location.homogeneous_matrix
        target_T_look = HomogeneousTransformationMatrix.from_xyz_rpy(y=sideways_offset)
        look_target = (reference_T_target @ target_T_look).pose
        x, y, z = look_target.position.to_np().flatten()[:3]
        return Sequence(
            [
                LookAtAction(look_target),
                DetectAction(
                    DetectionTechnique.TYPES,
                    object_sem_annotation=self.object_semantic_annotation,
                    detection_box=VolumetricBoundingBox(
                        origin=HomogeneousTransformationMatrix(
                            reference_frame=look_target.reference_frame
                        ),
                        min_x=x - self.detection_half_extent,
                        min_y=y - self.detection_half_extent,
                        min_z=z - self.detection_half_extent,
                        max_x=x + self.detection_half_extent,
                        max_y=y + self.detection_half_extent,
                        max_z=z + self.detection_half_extent,
                    ),
                ),
            ]
        )
