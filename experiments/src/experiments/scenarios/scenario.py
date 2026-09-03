"""
What an experiment is made of: the scenario a trial runs, the goal that decides whether
it succeeded, and the conditions and perturbations one run varies it with.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import ClassVar, Generic, Sequence, Type, TypeVar

from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.utils import get_generic_type_parameters

WorldType = TypeVar("WorldType")
"""
The world a scenario builds, and that its steps, goal, conditions and perturbations act
on.
"""

RobotType = TypeVar("RobotType")
"""
The robot a scenario runs on.
"""

# %% where and how a scenario runs


class ExecutionKind(StrEnum):
    """
    Whether a scenario runs in a simulator or on the robot.
    """

    SIMULATED = "simulated"
    REAL = "real"


class StepName(StrEnum):
    """
    Base for the enum a family of scenarios names its steps with.

    A perturbation names the step it strikes at, so the steps of a scenario are a fixed
    set of names rather than free text.
    """


# %% the pieces a scenario is described with


@dataclass
class ScenarioStep(Generic[WorldType], SubClassSafeGeneric, ABC):
    """
    One named part of what a scenario does to its world.
    """

    name: StepName
    """
    Which step of its scenario this is.
    """

    @abstractmethod
    def perform(self, world: WorldType) -> None:
        """
        Do this step in the given world.

        :param world: The world the trial is running in.
        """


@dataclass
class Goal(Generic[WorldType], SubClassSafeGeneric, ABC):
    """
    What counts as success for a trial.
    """

    @abstractmethod
    def is_reached(self, world: WorldType) -> bool:
        """
        Whether the world a trial finished in meets this goal.

        :param world: The world the trial ran in.
        """


@dataclass
class Condition(Generic[WorldType], SubClassSafeGeneric, ABC):
    """
    One knowledge source switched on or off for a trial.

    A condition is what takes knowledge away from a run, so an ablation is never a
    branch inside the action that reads it.
    """

    @abstractmethod
    def apply(self, world: WorldType) -> None:
        """
        Switch this condition's knowledge source in the world a trial is about to run
        in.

        :param world: The world the trial will run in.
        """


@dataclass
class Perturbation(Generic[WorldType], SubClassSafeGeneric, ABC):
    """
    A change applied to the world of a running trial at one of its steps.
    """

    step: StepName
    """
    The step this perturbation is applied before.
    """

    @abstractmethod
    def apply(self, world: WorldType) -> None:
        """
        Make this perturbation's change to the world.

        :param world: The world the trial is running in.
        """


# %% the scenario itself


@dataclass
class Scenario(Generic[WorldType, RobotType], SubClassSafeGeneric, ABC):
    """
    One experiment scene: the world it is run in, the robot it is run on, what is done
    in it, and what counts as success.
    """

    name: ClassVar[str]
    """
    The name this scenario is reported under.
    """

    goal: Goal[WorldType] = field(kw_only=True)
    """
    What a trial of this scenario has to reach to have succeeded.
    """

    execution_kind: ExecutionKind = field(default=ExecutionKind.SIMULATED, kw_only=True)
    """
    Whether this instance runs in a simulator or on the robot.
    """

    @property
    def robot_type(self) -> Type[RobotType]:
        """
        The robot this scenario runs on, read from its bound generic parameter.
        """
        world_type, robot_type = get_generic_type_parameters(self, Scenario)
        return robot_type

    @abstractmethod
    def build_world(self) -> WorldType:
        """
        Build the world one trial of this scenario runs in.
        """

    def release_world(self, world: WorldType) -> None:
        """
        Give up whatever the world holds, once a trial has finished in it.

        :param world: The world the finished trial ran in.
        """

    @abstractmethod
    def steps(self, world: WorldType) -> Sequence[ScenarioStep[WorldType]]:
        """
        What this scenario does to the given world, in the order it is done.

        :param world: The world the trial is about to run in.
        """
