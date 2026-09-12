"""
What an experiment is made of: the scenario a trial runs, the goal that decides whether
it succeeded, the conditions and perturbations one run varies it with, and the person
who brings a perturbation about when the trial runs on the robot.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import (
    ClassVar,
    Generic,
    List,
    Protocol,
    Sequence,
    TextIO,
    Type,
    TypeVar,
)

from coraplex.datastructures.enums import ExecutionType
from krrood.entity_query_language.predicate import Predicate
from krrood.exceptions import DataclassException
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.utils import get_generic_type_parameters
from segmind.datastructures.events import ReproducibleEvent
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World

WorldType = TypeVar("WorldType", bound=World)
"""
The world a scenario builds, and that its steps, goal, conditions and perturbations act
on.
"""

RobotType = TypeVar("RobotType", bound=AbstractRobot)
"""
The robot a scenario runs on.
"""

# %% where and how a scenario runs


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


@dataclass(eq=False)
class Goal(Predicate, Generic[WorldType], SubClassSafeGeneric, ABC):
    """
    What counts as success for a trial: a predicate that holds of the world the trial
    finished in.

    Being a predicate is what lets a goal be asked in the same query language the rest
    of the architecture is asked in, and it is why the world a goal is about is one of
    its operands rather than an argument handed to it at evaluation time. Every goal
    states its own verbalization, which :class:`Predicate` requires of it.
    """

    world: WorldType
    """
    The world this goal is asked about.
    """

    @abstractmethod
    def __call__(self) -> bool:
        """
        Whether this goal is reached in the world it was given.
        """


@dataclass
class ScenarioCondition(Generic[WorldType], SubClassSafeGeneric, ABC):
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


# %% the person at the scene


class Person(Protocol):
    """
    The other agent a trial has beside the robot: the person at the scene, who brings
    about on the robot what a simulated trial brings about itself.
    """

    def carry_out(self, instruction: str) -> None:
        """
        Do what the instruction says, returning once it is done.

        :param instruction: What the person is asked to do.
        """


@dataclass
class PersonAtTheConsole:
    """
    A person who reads each instruction off the console and confirms with a line of
    input once they have carried it out.
    """

    output: TextIO = field(default_factory=lambda: sys.stdout)
    """
    Where the instruction is written.
    """

    keyboard: TextIO = field(default_factory=lambda: sys.stdin)
    """
    Where the confirmation is read from.
    """

    def carry_out(self, instruction: str) -> None:
        self.output.write("%s\nPress enter once that is done. " % instruction)
        self.output.flush()
        self.keyboard.readline()


@dataclass
class AbsentPerson:
    """
    Stands in for the person at a trial that has none: keeps every instruction and does
    nothing about it.
    """

    asked: List[str] = field(default_factory=list)
    """
    The instructions given so far, in order.
    """

    def carry_out(self, instruction: str) -> None:
        self.asked.append(instruction)


# %% the change a run applies


@dataclass
class Perturbation(Generic[WorldType], SubClassSafeGeneric, ABC):
    """
    A change made to the scene of a running trial at one of its steps, by someone other
    than the robot.

    In simulation the run makes the change itself, by writing it into the world. On the
    robot the person at the scene makes it, and what the run then knows of it is each
    perturbation's own to say.
    """

    step: StepName
    """
    The step this perturbation is applied before.
    """

    @abstractmethod
    def apply(self, world: WorldType) -> None:
        """
        Make this perturbation's change in the world of a simulated trial, in the
        person's stead.

        :param world: The world the trial is running in.
        """

    @abstractmethod
    def instruction_for_a_person(self) -> str:
        """
        What to tell the person at the scene to bring this change about themselves.

        One perturbation describes one change, however the trial is run: the same
        instance that changes a simulated world says what a person does instead.
        """

    def carried_out_by(
        self, person: Person, scenario: Scenario[WorldType, RobotType], world: WorldType
    ) -> None:
        """
        Have the person at the scene bring this perturbation about, which is how a
        trial on the robot applies it: they are asked, and the run waits until they say
        it is done.

        Nothing is written into the world, so what the run knows of the change
        afterwards is what this says -- here nothing, as befits a change the run is not
        meant to know of.

        :param person: The person at the scene.
        :param scenario: The scenario the trial runs.
        :param world: The world the trial is running in.
        """
        person.carry_out(self.instruction_for_a_person())


@dataclass
class EventBroughtAbout(Perturbation[WorldType], ABC):
    """
    A perturbation that is one event of the scene made to happen: something moved,
    something slid, as the process that caused it would have.

    In simulation the run reproduces the event in the world. On the robot the person
    brings it about, and the robot then looks at the scene again, so the world learns
    of the event the way it learns of anything that happens on the robot: by
    perceiving it, never by being told.
    """

    @abstractmethod
    def event_in(self, world: WorldType) -> ReproducibleEvent:
        """
        The event this perturbation brings about, stated over the scene as it stands.

        :param world: The world the trial is running in.
        """

    def apply(self, world: WorldType) -> None:
        self.event_in(world).reproduce(world)

    def carried_out_by(
        self, person: Person, scenario: Scenario[WorldType, RobotType], world: WorldType
    ) -> None:
        """
        Have the person bring the event about, then look at the scene to learn what they
        did.

        :param person: The person at the scene.
        :param scenario: The scenario the trial runs, which looks at its scene.
        :param world: The world the trial is running in.
        """
        super().carried_out_by(person, scenario, world)
        scenario.perceive(world)


@dataclass
class ScenarioCannotPerceive(DataclassException):
    """
    Raised when a scenario is asked to look at its scene and has nothing to look with.
    """

    scenario_name: str
    """
    The name of the scenario that was asked.
    """

    def error_message(self) -> str:
        return "'%s' has no way of looking at its scene." % self.scenario_name

    def suggest_correction(self) -> str:
        return (
            "Run it in simulation, where the world is the scene, or give it a scene "
            "that is perceived."
        )


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

    execution_type: ExecutionType = field(default=ExecutionType.SIMULATED, kw_only=True)
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

    def perceive(self, world: WorldType) -> None:
        """
        Bring the world up to date with the scene by looking at it, which is how a trial
        on the robot learns of a change the person at the scene made.

        A scenario whose world is the scene -- a simulated one -- has nothing to look
        with, and this says so.

        :param world: The world the trial is running in.
        :raises ScenarioCannotPerceive: If this scenario has no way of looking.
        """
        raise ScenarioCannotPerceive(scenario_name=self.name)

    @abstractmethod
    def steps(self, world: WorldType) -> Sequence[ScenarioStep[WorldType]]:
        """
        What this scenario does to the given world, in the order it is done.

        :param world: The world the trial is about to run in.
        """

    @abstractmethod
    def goal(self, world: WorldType) -> Goal[WorldType]:
        """
        What a trial of this scenario in the given world has to reach to have succeeded.

        :param world: The world the trial is running in.
        """
