# used for delayed evaluation of typing until python 3.11 becomes mainstream
from __future__ import annotations

import atexit
import logging
import threading
import time
from abc import ABC
from dataclasses import dataclass, field
from typing_extensions import (
    Optional,
    Callable,
    Any,
    List,
    Union,
    Type,
)

from giskardpy.motion_statechart.goals.templates import Sequence, Parallel
from giskardpy.motion_statechart.graph_node import Goal, MotionStatechartNode
from coraplex.language_giskard_templates import TryAll, TryInOrder
from coraplex.plans.executables import (
    GiskardExecutable,
    Executable,
)
from coraplex.datastructures.enums import TaskStatus, MonitorBehavior
from coraplex.plans.failures import PlanFailure, AllChildrenFailed
from coraplex.fluent import Fluent
from coraplex.plans.plan_node import PlanNode

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class LanguageNode(PlanNode, ABC):
    """
    Base class for language nodes in a plan.

    Language nodes are nodes that are not directly executable, but manage the execution
    of their children in a certain way.
    """

    motion_state_chart_template: Type[Goal] = field(kw_only=True, default=Sequence)
    """
    Giskard template which this language expression translates to.
    """

    def simplify(self):
        for child in self.children:
            if type(child) != type(self):
                continue

            self.merge(child)

    def notify(self):
        for child in self.children:
            child.notify()

    def parse(self) -> Executable:
        return self.parse_children(self.children)

    def create_goal(self) -> Goal:
        """
        :return: An empty goal of this node's template, describing how its children are
            executed inside a motion state chart.
        """
        return self.motion_state_chart_template(name=type(self).__name__)

    def add_to_motion_state_chart(
        self, parent_goal: Goal, executable: GiskardExecutable
    ) -> Goal:
        """
        Add this node as its own goal below `parent_goal` and add every child that
        contributes motions into it, one at a time.
        """
        goal = self.create_goal()
        parent_goal.add_node(goal)
        self.add_children_to_motion_state_chart(goal, self.children, executable)
        return goal


@dataclass
class ExecutesSequentially(LanguageNode):
    """
    Base class for nodes that execute their children sequentially.
    """


@dataclass
class ExecutesInParallel(LanguageNode, ABC):
    """
    Base class for nodes that execute their children in parallel.
    """

    @classmethod
    def _perform_parallel(cls, nodes: List[PlanNode]):
        """
        Open threads for all nodes and wait for them to finish.

        :param nodes: A list of nodes which should be performed in parallel
        """
        threads = []
        for child in nodes:
            thread = threading.Thread(
                target=child.perform,
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()


@dataclass
class SequentialNode(ExecutesSequentially):
    """
    Executes all children sequentially.

    Any failure is immediately raised.
    """

    motion_state_chart_template: Type[Goal] = field(kw_only=True, default=Sequence)


@dataclass
class ParallelNode(ExecutesInParallel):
    """
    Executes all children in parallel by creating a thread per children and executing
    them in the respective thread.

    All exceptions are raised after all children have finished.
    """

    motion_state_chart_template: Type[Goal] = field(kw_only=True, default=Parallel)

    def notify(self):
        self._perform_parallel(self.children)
        for child in self.children:
            if child.status == TaskStatus.FAILED:
                raise child.reason


@dataclass(eq=False)
class RepeatNode(ExecutesSequentially):
    """
    Executes all children a given number of times in sequential order.
    """

    repetitions: int = 1
    """
    The number of repetitions of the children.
    """

    def notify(self):
        for _ in range(self.repetitions):
            super().notify()


@dataclass(eq=False)
class TryInOrderNode(ExecutesSequentially):
    """
    Tries all children in order sequentially and fails if all children fail.
    """

    motion_state_chart_template: Type[Goal] = field(kw_only=True, default=TryInOrder)

    def notify(self):
        for child in self.children:
            try:
                child.perform()
            except PlanFailure:
                continue
        failed = all([child.status == TaskStatus.FAILED for child in self.children])
        if failed:
            raise AllChildrenFailed(self)


@dataclass(eq=False)
class TryAllNode(ExecutesInParallel):
    """
    Executes all children in parallel.

    Only raise a failure if all children fail.
    """

    motion_state_chart_template: Type[Goal] = field(kw_only=True, default=TryAll)

    def notify(self):
        self._perform_parallel(self.children)
        failed = all([child.status == TaskStatus.FAILED for child in self.children])
        if failed:
            raise AllChildrenFailed(self)


@dataclass(eq=False)
class MonitorNode(LanguageNode):

    monitor: MotionStatechartNode = field(default=None, kw_only=True)

    def notify(self):
        self.child.notify()

    def parse(self) -> Executable:
        pass


@dataclass(eq=False)
class CancelMonitor(MonitorNode):
    pass


@dataclass(eq=False)
class PauseMonitor(MonitorNode):
    pass


@dataclass
class CodeNode(LanguageNode):
    """
    Executable function in a plan.

    This class' primary purpose is for debugging and testing.
    """

    code: Callable = field(default_factory=lambda: lambda: None, kw_only=True)

    def notify(self) -> Any:
        return self.code()
