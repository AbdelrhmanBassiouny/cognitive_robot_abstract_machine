"""
Putting a held body through an opening: the robot carries it over the aperture, lines it
up with the aperture's own axis, lowers it and lets go.

What separates this from
:class:`~coraplex.robot_plans.actions.core.placing.PlaceAction` is what counts as having
worked. A place is done when the body stands at the pose it was carried to; an insertion
is done when the body is *behind* the opening -- which is a different reading of the
world, and one the body reaches by falling or being pushed the last stretch rather than
by being put there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, Dict, List, Optional

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.exceptions import ApertureHasNoLandingRegion
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.mixins import (
    HasGraspDetectionThreshold,
    HasTcpGoalThresholds,
    ManipulatesBodies,
    PlaceTuningParameters,
)
from coraplex.view_manager import ViewManager
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import ConditionType, variable_from
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.reasoning.robot_predicates import is_body_gripped
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.spatial_types.spatial_types import (
    Point3,
    Pose,
    Quaternion,
    RotationMatrix,
)
from semantic_digital_twin.world_description.world_entity import Body

DEFAULT_HOVER_HEIGHT = 0.02
"""
How far above an aperture's own origin a body is let go of by default, in metres.

Far enough that the body is clear of the surface the opening is cut into when the
fingers open, so what carries it through is its own fall rather than the release.
"""

DEFAULT_MINIMUM_CONTAINMENT_RATIO = 0.9
"""
How much of a body must stand in an aperture's landing region by default before it
counts as inserted.

Higher than :attr:`~semantic_digital_twin.reasoning.predicates.InsideOf.minimum_containment_ratio`'s
own half, which reads a body as in once it is more swallowed than not: a body wedged
across the opening is already half through it, and that is exactly the insertion that
did not work.
"""


@dataclass
class InsertAction(
    ActionDescription,
    PlaceTuningParameters,
    HasGraspDetectionThreshold,
    HasTcpGoalThresholds,
    ManipulatesBodies,
):
    """
    Puts a held body through an aperture.
    """

    object_designator: Body
    """
    The body to put through :attr:`target`.
    """

    target: Aperture
    """
    The opening the body goes through.
    """

    arm: Arms
    """
    The arm holding the body.
    """

    hover_height: float = field(default=DEFAULT_HOVER_HEIGHT, kw_only=True)
    """
    How far above :attr:`target`'s own origin, along its own axis, the body is let go
    of; see :data:`DEFAULT_HOVER_HEIGHT`.
    """

    grasp_description: Optional[GraspDescription] = field(default=None, kw_only=True)
    """
    How :attr:`object_designator` is held, which the poses this action moves through are
    computed from.

    Optional because an insertion that follows its own pick-up reads the grasp off the
    world; state it when the body was picked up in a plan of its own.
    """

    minimum_containment_ratio: float = field(
        default=DEFAULT_MINIMUM_CONTAINMENT_RATIO, kw_only=True
    )
    """
    How much of the body must stand in :attr:`target`'s landing region for this action
    to have worked; see :data:`DEFAULT_MINIMUM_CONTAINMENT_RATIO`.
    """

    target_R_body: RotationMatrix = field(default_factory=RotationMatrix, kw_only=True)
    """
    How the body is turned relative to :attr:`target`'s own axes when it is let go of.

    The default presents it the way the opening is turned, which is what lines a body up
    with an opening cut to its own cross-section; a body that only goes through turned
    some other way -- a coin, which has to go into a slot on its edge -- is inserted by
    stating that turn here.
    """

    @property
    def insertion_pose(self) -> Pose:
        """
        The pose, in :attr:`target`'s own frame, the body is released at:
        :attr:`hover_height` above the opening's origin along its own axis, turned as
        :attr:`target_R_body` states.
        """
        return Pose(
            Point3(0.0, 0.0, self.hover_height),
            Quaternion.from_rotation_matrix(self.target_R_body),
            reference_frame=self.target.root,
        )

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The body this action acts on.
        """
        return [self.object_designator]

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                PlaceAction(
                    self.object_designator,
                    self.world.transform(self.insertion_pose, self.world.root),
                    self.arm,
                    grasp_description=self.grasp_description,
                    grasp_detection_threshold=self.grasp_detection_threshold,
                    placing_linear_velocity=self.placing_linear_velocity,
                    transport_linear_velocity=self.transport_linear_velocity,
                    release_opening_velocity=self.release_opening_velocity,
                    retract_linear_velocity=self.retract_linear_velocity,
                    position_threshold=self.position_threshold,
                    orientation_threshold=self.orientation_threshold,
                )
            ],
            self.context,
        )

    @staticmethod
    def pre_condition(
        variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]
    ) -> ConditionType:
        """
        The arm's gripper needs to be holding the body.
        """
        end_effector = ViewManager.get_end_effector_view(
            variables["arm"], context.robot
        )
        return is_body_gripped(
            variable_from(kwargs["object_designator"]),
            end_effector,
            threshold=kwargs["grasp_detection_threshold"],
        )

    @staticmethod
    def post_condition(
        variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]
    ) -> ConditionType:
        """
        The body needs to stand in the space behind the opening.

        :raises ApertureHasNoLandingRegion: If the opening carries no such space.
        """
        target = kwargs["target"]
        if target.landing_region is None:
            raise ApertureHasNoLandingRegion(target)
        return InsideOf(
            variable_from(kwargs["object_designator"]),
            target.landing_region,
            minimum_containment_ratio=kwargs["minimum_containment_ratio"],
        )
