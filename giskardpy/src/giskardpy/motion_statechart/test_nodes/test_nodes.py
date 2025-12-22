from dataclasses import dataclass, field
from typing import Optional

import krrood.symbolic_math.symbolic_math as sm
from giskardpy.motion_statechart.context import ExecutionContext, BuildContext
from giskardpy.motion_statechart.graph_node import (
    MotionStatechartNode,
    Goal,
    NodeArtifacts,
)


@dataclass(eq=False, repr=False)
class ConstTrueNode(MotionStatechartNode):
    def build(self, context: BuildContext) -> NodeArtifacts:
        return NodeArtifacts(observation=sm.Scalar.const_true())


@dataclass(eq=False, repr=False)
class ConstFalseNode(MotionStatechartNode):
    def build(self, context: BuildContext) -> NodeArtifacts:
        return NodeArtifacts(observation=sm.Scalar.const_false())


@dataclass(repr=False, eq=False)
class ChangeStateOnEvents(MotionStatechartNode):
    state: Optional[str] = None

    def on_start(self, context: ExecutionContext):
        self.state = "on_start"

    def on_pause(self, context: ExecutionContext):
        self.state = "on_pause"

    def on_unpause(self, context: ExecutionContext):
        self.state = "on_unpause"

    def on_end(self, context: ExecutionContext):
        self.state = "on_end"

    def on_reset(self, context: ExecutionContext):
        self.state = "on_reset"


@dataclass(repr=False, eq=False)
class TestGoal(Goal):
    sub_node1: ConstTrueNode = field(init=False)
    sub_node2: ConstTrueNode = field(init=False)

    def expand(self, context: BuildContext) -> None:
        self.sub_node1 = ConstTrueNode(name="sub muh1")
        self.add_node(self.sub_node1)
        self.sub_node2 = ConstTrueNode(name="sub muh2")
        self.add_node(self.sub_node2)
        self.sub_node1.end_condition = self.sub_node1.observation_variable
        self.sub_node2.start_condition = self.sub_node1.observation_variable

    def build(self, context: BuildContext) -> NodeArtifacts:
        return NodeArtifacts(observation=self.sub_node2.observation_variable)


@dataclass(repr=False, eq=False)
class TestNestedGoal(Goal):
    sub_node1: TestGoal = field(init=False)
    sub_node2: TestGoal = field(init=False)
    inner: TestGoal = field(init=False)

    def expand(self, context: BuildContext) -> None:
        self.inner = TestGoal(name="inner")
        self.add_node(self.inner)

    def build(self, context: BuildContext) -> NodeArtifacts:
        return NodeArtifacts(observation=sm.Scalar(self.inner.observation_variable))
