from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List

from coraplex.datastructures.enums import DetectionTechnique
from coraplex.locations.locations import VisibilityLocation
from coraplex.robot_plans.actions.base import SequentialAction
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
class SearchAction(SequentialAction):
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

    detection_margin: float = 0.5
    """
    How far beyond the points looked at an object may lie and still be detected.
    """

    def create_steps(self) -> List[StatechartNode]:
        detection_box = self._detection_box()
        return [
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
                            LookAtAction(
                                target=self.target_location,
                                sideways_offset=sideways_offset,
                            ),
                            DetectAction(
                                technique=DetectionTechnique.TYPES,
                                object_sem_annotation=self.object_semantic_annotation,
                                detection_box=detection_box,
                            ),
                        ]
                    )
                    for sideways_offset in self.sideways_look_offsets
                ]
            ),
        ]

    def _detection_box(self) -> VolumetricBoundingBox:
        """
        :return: The cube around :attr:`target_location` that holds every point looked
            at, widened by :attr:`detection_margin`.
        """
        half_extent = (
            max(abs(offset) for offset in self.sideways_look_offsets)
            + self.detection_margin
        )
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
