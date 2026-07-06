from dataclasses import dataclass

from typing_extensions import Optional, Tuple

from krrood.entity_query_language.predicate import (
    SymbolicFunction,
    functional_form,
)
from coraplex.datastructures.enums import Arms
from semantic_digital_twin.robots.robot_parts import (
    EndEffector,
    KinematicChain,
    AbstractRobot,
    Neck,
)


@dataclass(eq=False)
class EndEffectorView(SymbolicFunction):
    """The end effector of a robot's arm view, as a value operation."""

    arm: Arms
    """The arm to get the end effector for."""

    robot_view: AbstractRobot
    """The robot view to search in."""

    def __call__(self) -> Optional[EndEffector]:
        arm_view = ViewManager.get_arm_view(self.arm, self.robot_view)
        return arm_view.end_effector


@dataclass
class ViewManager:

    get_end_effector_view = staticmethod(functional_form(EndEffectorView))
    """Returns the end effector of an arm view -- the class-form :class:`EndEffectorView` behind a
    :func:`functional_form` wrapper, so a call returns the end effector for concrete arguments and a
    symbolic expression when any argument is symbolic."""

    @staticmethod
    def get_arm_view(arm: Arms, robot_view: AbstractRobot) -> Optional[KinematicChain]:
        """
        Get the arm view for a given arm and robot view.

        :param arm: The arm to get the view for.
        :param robot_view: The robot view to search in.
        :return: The Manipulator object representing the arm.
        """
        all_arms = ViewManager.get_all_arm_views(arm, robot_view)
        return all_arms[0]

    @staticmethod
    def get_all_arm_views(
        arm: Arms, robot_view: AbstractRobot
    ) -> Optional[Tuple[KinematicChain]]:
        """
        Get all possible arm views for a given arm and robot view.

        :param arm: The arm to get the view for.
        :param robot_view: The robot view to search in.
        :return: The Manipulator object representing the arm.
        """
        if len(robot_view.get_arms()) == 1:
            return (robot_view.get_arms()[0],)
        elif arm == Arms.LEFT:
            return (robot_view.get_left_arm_if_specified(),)
        elif arm == Arms.RIGHT:
            return (robot_view.get_right_arm_if_specified(),)
        elif arm == Arms.BOTH:
            return robot_view.get_arms()
        return None

    @staticmethod
    def get_neck_view(robot_view: AbstractRobot) -> Optional[Neck]:
        """
        Get the neck view for a given robot view.

        :param robot_view: The robot view to search in.
        :return: The Neck object representing the neck.
        """
        return next(
            (part for part in robot_view._robot_parts if isinstance(part, Neck)), None
        )
