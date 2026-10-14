from dataclasses import dataclass

from typing_extensions import Callable, List

from coraplex.querying.grasp_closeness import GraspCloseness
from krrood.entity_query_language.predicate import Predicate, RenderedFields
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Noun,
    predicate_clause,
)
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body


@dataclass
class GripperOccupancy:
    """
    Base class for predicates that check the gripper occupancy.
    """

    end_effector: EndEffector
    """
    Semantic annotation for the gripper that should be evaluated.
    """

    def check_manipulator_occupancy(
        self, condition: Callable[List[Body], bool]
    ) -> bool:
        """
        Checks the occupancy of the gripper against a condition.

        The condition gets the list of bodies below the tool frame in the kinematic
        structure and returns a boolean.

        :param condition: The condition that should be evaluated.
        :return: True if the condition is satisfied, False otherwise.
        """
        bodies_below_tool_frame = (
            self.end_effector._world.get_kinematic_structure_entities_of_branch(
                self.end_effector.tool_frame
            )
        )
        if self.end_effector.tool_frame in bodies_below_tool_frame:
            bodies_below_tool_frame.remove(self.end_effector.tool_frame)
        return condition(bodies_below_tool_frame)


@dataclass
class GripperHolds(GripperOccupancy, Predicate):
    """
    Checks if the gripper holds a particular body.

    This is checked by looking at the kinematic structure below the tool frame, so a
    gripper holding something else does not count.
    """

    body: Body
    """
    The body the gripper is asked to hold.
    """

    def __call__(self) -> bool:
        return self.check_manipulator_occupancy(lambda bodies: self.body in bodies)

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        :param fields: The rendered fragment for each field.
        :return: The clause *"<end effector> holds <body>"*.
        """
        return predicate_clause(cls, Noun(fields["end_effector"]), Noun(fields["body"]))


@dataclass(eq=False)
class IsAmongTheClosestGraspsTo(Predicate):
    """
    Whether a grasp is among the grasps closest to where the robot stands.

    Grasps are ranked by their
    :class:`~coraplex.querying.grasp_closeness.GraspCloseness` to the standing pose,
    then by their order in :attr:`grasps`. Left open, :attr:`standing_position` is
    grounded to the standing poses that suit a fixed grasp.
    """

    grasp: GraspCandidate
    """
    The grasp that is asked about.
    """

    standing_position: Pose
    """
    Where the robot stands while taking the grasp.
    """

    grasps: List[GraspCandidate]
    """
    The grasps on the same object that :attr:`grasp` is ranked among.

    A grasp not among them ranks after those as close as it.
    """

    number_of_grasps: int = 3
    """
    How many of :attr:`grasps` count as the closest.
    """

    def __call__(self) -> bool:
        world = self.grasp.graspable.root._world

        # Transform to np for speed, as this is called a lot
        world_P_standing = world.transform(self.standing_position, world.root).to_np()[
            :, 3
        ]
        world_T_object = self.grasp.graspable.root.global_transform.to_np()

        position = next(
            (index for index, grasp in enumerate(self.grasps) if grasp is self.grasp),
            len(self.grasps),
        )
        ranked = [*self.grasps[:position], self.grasp, *self.grasps[position + 1 :]]
        closeness = GraspCloseness.of(self.grasp, world_T_object, world_P_standing)
        # Grasps exactly as close as this one rank by the order they are listed in, so
        # no more of them count as the closest than were asked for.
        ranked_ahead = sum(
            1
            for index, other_closeness in enumerate(
                GraspCloseness.of(grasp, world_T_object, world_P_standing)
                for grasp in ranked
            )
            if other_closeness < closeness
            or (other_closeness == closeness and index < position)
        )
        return ranked_ahead < self.number_of_grasps

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        :param fields: The rendered fragment for each field.
        :return: The clause *"<grasp> is among the closest grasps to <standing
            position>"*.
        """
        return predicate_clause(
            cls, Noun(fields["grasp"]), Noun(fields["standing_position"])
        )
