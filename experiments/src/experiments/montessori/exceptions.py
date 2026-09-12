"""
The ways the Montessori scene's semantics can fail.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import FrozenSet, Optional, TYPE_CHECKING, Type

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from semantic_digital_twin.robots.robot_parts import AbstractRobot
    from semantic_digital_twin.world import World

    from experiments.montessori.semantics import (
        MontessoriShape,
        MontessoriShapeCategory,
        ShapeSortingBoard,
        ShapeSortingHole,
    )


@dataclass
class NoMatchingHoleError(DataclassException):
    """
    Raised when a :class:`~experiments.montessori.semantics.ShapeSortingBoard` has no
    :class:`~experiments.montessori.semantics.ShapeSortingHole` whose category matches a
    given :class:`~experiments.montessori.semantics.MontessoriShape`.
    """

    montessori_shape: MontessoriShape
    """
    The shape that has no matching hole.
    """

    board: ShapeSortingBoard
    """
    The board that has no hole matching :attr:`montessori_shape`.
    """

    def error_message(self) -> str:
        return (
            f"{self.board.name} has no hole matching {self.montessori_shape.name}'s "
            f"category {self.montessori_shape.shape_category}."
        )

    def suggest_correction(self) -> str:
        return ""


@dataclass
class NoSuchPieceError(DataclassException):
    """
    Raised when a scene is asked about a loose piece of a shape it does not hold.
    """

    shape_category: MontessoriShapeCategory
    """
    The shape that was asked about.
    """

    standing_in_the_scene: FrozenSet[MontessoriShapeCategory]
    """
    The shapes the scene does hold a piece of.
    """

    def error_message(self) -> str:
        holds = ", ".join(sorted(str(each) for each in self.standing_in_the_scene))
        return f"No piece of shape {self.shape_category} stands in this scene; it holds {holds}."

    def suggest_correction(self) -> str:
        return (
            "Name a shape the scene's layout places, or build the scene from a layout "
            "that places this one."
        )


@dataclass
class HoleHasNoLandingRegionError(DataclassException):
    """
    Raised when the space under a hole is asked for and that hole was never measured.
    """

    hole: ShapeSortingHole
    """
    The hole with no space measured under it.
    """

    def error_message(self) -> str:
        return f"{self.hole.name} has no landing region, so nothing can be inside it."

    def suggest_correction(self) -> str:
        return (
            "Take the hole from a world that measured the space under it, which "
            "MontessoriWorld does when it builds its board."
        )


@dataclass
class BoardDescriptionIncomplete(DataclassException):
    """
    Raised when a statement of the shape-sorting board leaves open something a look
    needs to lay the board's holes over a picture.
    """

    missing_attribute: str
    """
    The attribute the statement leaves open, by the name the annotation gives it.
    """

    hole_index: Optional[int] = None
    """
    Which of the stated holes leaves it open, in the order they were stated, or None
    where the board itself does.
    """

    def error_message(self) -> str:
        described = (
            "The board" if self.hole_index is None else f"Hole {self.hole_index}"
        )
        return f"{described} is stated without its {self.missing_attribute}."

    def suggest_correction(self) -> str:
        return (
            "State the lid's size and height, and every hole's shape, size and place "
            "on the lid, so the whole layout can be fitted at once."
        )


@dataclass
class WorldHoldsNoSuchRobot(DataclassException):
    """
    Raised when a scene is to be built around the robot a world already holds, and the
    world holds no robot of the kind the scenario runs on.
    """

    robot_type: Type[AbstractRobot]
    """
    The kind of robot the scenario runs on.
    """

    world: World
    """
    The world that was to hold it.
    """

    def error_message(self) -> str:
        return (
            f"The world does not hold exactly one {self.robot_type.__name__}, so no "
            f"scene can be built around one."
        )

    def suggest_correction(self) -> str:
        return (
            "Run the scenario bound to the robot the world holds, or fetch the world "
            "from that robot."
        )


@dataclass
class SceneNotBuiltYet(DataclassException):
    """
    Raised when a scenario is asked about the scene of its most recent trial before it
    has built one.
    """

    scenario_name: str
    """
    The name of the scenario that was asked.
    """

    def error_message(self) -> str:
        return f"'{self.scenario_name}' has not built a scene yet."

    def suggest_correction(self) -> str:
        return "Build the scenario's world first; a runner does so at the start of a trial."


@dataclass
class ScenarioRunsOnlyInSimulation(DataclassException):
    """
    Raised when a scenario whose script needs the simulation is asked to run on the
    robot.
    """

    scenario_name: str
    """
    The name of the scenario that was asked to run on the robot.
    """

    def error_message(self) -> str:
        return f"'{self.scenario_name}' cannot run on the robot."

    def suggest_correction(self) -> str:
        return (
            "Its script drives the scene through the simulation; on the robot, run a "
            "scenario whose steps the real scene can perform, and bring what the "
            "script would have done about as a perturbation a person carries out."
        )


@dataclass
class RealRunCannotBeFilmed(DataclassException):
    """
    Raised when a scenario running on the robot is asked to film its trials, which only
    a simulation can do.
    """

    scenario_name: str
    """
    The name of the scenario that was asked to film.
    """

    def error_message(self) -> str:
        return f"'{self.scenario_name}' runs on the robot, where no trial is filmed."

    def suggest_correction(self) -> str:
        return (
            "A trial is filmed from the simulation carrying it; on the robot, record a "
            "bag of the camera instead."
        )


@dataclass
class RealRunNeedsAPerceivedScene(DataclassException):
    """
    Raised when a scenario running on the robot is given a scene that is built rather
    than perceived: what the person at the table changes reaches the world only through
    a look, and a built scene has nothing to look with.
    """

    scenario_name: str
    """
    The name of the scenario that was given the scene.
    """

    def error_message(self) -> str:
        return (
            f"'{self.scenario_name}' runs on the robot, so its scene has to be one the "
            f"robot's camera finds."
        )

    def suggest_correction(self) -> str:
        return (
            "Give the scenario a scene builder that perceives the scene, or run it in "
            "simulation."
        )
