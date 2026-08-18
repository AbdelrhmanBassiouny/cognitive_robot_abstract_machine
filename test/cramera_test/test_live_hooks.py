"""
Unit tests for the live hooks' wrapper methods.

Exercised against mimics of the CRAM interfaces and of the bridge itself, so no
giskardpy import is needed and no real world binding happens. What is covered is each
wrapper's own contract: when it forwards to the bridge, when it falls through to the
original call, and how it behaves when the bridge itself misbehaves.

The one exception is the plan hook, which is also driven through a real coraplex plan
node: which method it sits on is the whole point of it, and no mimic can pin that down.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from typing_extensions import Any, List, Optional, Tuple

from coraplex.language import SequentialNode
from coraplex.plans.executables import GiskardExecutable
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import PlanNode

import cramera.live.hooks
from cramera.live.bridge import Bridge, TaskStatusName
from cramera.live.hooks import LiveHooks, install_plan_hooks


# %% mimics of the interfaces the hooks read
@dataclass
class FakeBridge:
    """
    Records what a hook forwards to it, standing in for a real :class:`Bridge`.
    """

    world: Optional[Any] = None
    attached: List[Any] = field(default_factory=list)
    observed_charts: List[Any] = field(default_factory=list)
    followed_plans: List[Any] = field(default_factory=list)
    bound_motion_groups: List[Any] = field(default_factory=list)
    frozen_motion_groups: List[Tuple[Any, Any]] = field(default_factory=list)
    remembered_mesh_files: List[str] = field(default_factory=list)
    remembered_urdf_sources: List[str] = field(default_factory=list)
    raise_on_observe_tick: bool = False

    def attach(self, world: Any) -> None:
        self.attached.append(world)
        self.world = world

    def observe_tick(self, chart: Any) -> None:
        if self.raise_on_observe_tick:
            raise RuntimeError("bridge misbehaved")
        self.observed_charts.append(chart)

    def follow_plan(self, plan: Any) -> None:
        self.followed_plans.append(plan)

    def bind_motion_group(self, executable: Any) -> None:
        self.bound_motion_groups.append(executable)

    def freeze_motion_group(self, executable: Any, status: Any) -> None:
        self.frozen_motion_groups.append((executable, status))

    def remember_mesh_file(self, file_path: str) -> None:
        self.remembered_mesh_files.append(file_path)

    def remember_urdf_source(self, file_path: str) -> None:
        self.remembered_urdf_sources.append(file_path)


@dataclass
class FakeExecutorContext:
    """
    The part of ``Executor.context`` the tick hook reads.
    """

    world: Any


@dataclass
class FakeExecutor:
    """
    A giskardpy executor, of which the tick hook reads only its context and chart.
    """

    context: FakeExecutorContext
    motion_statechart: Any = None


@dataclass
class FakePlanNode:
    """
    A plan node, of which the plan hook reads only the plan it belongs to.
    """

    plan: Any


@dataclass
class FakeMeshParser:
    """
    A mesh parser, of which the mesh hook reads only its file path.
    """

    file_path: str


# %% tick hook
class TestObserveTick:
    def test_the_first_tick_attaches_the_world(self):
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)
        executor = FakeExecutor(
            context=FakeExecutorContext(world="the-world"), motion_statechart="chart"
        )

        result = hooks._observe_tick(lambda executor: "ticked", executor)

        assert result == "ticked"
        assert bridge.attached == ["the-world"]
        assert bridge.observed_charts == ["chart"]

    def test_the_world_already_bound_is_not_reattached(self):
        bridge = FakeBridge(world="the-world")
        hooks = LiveHooks(bridge=bridge)
        executor = FakeExecutor(
            context=FakeExecutorContext(world="the-world"), motion_statechart="chart"
        )

        hooks._observe_tick(lambda executor: None, executor)

        assert bridge.attached == []

    def test_a_rebuilt_world_replaces_the_one_bound_before_it(self):
        """
        A demo restarted from the viewer executes in a world it has just built.

        Staying bound to the abandoned one publishes its last poses forever, which reads
        as a viewer that attaches but never shows anything happening.
        """
        bridge = FakeBridge(world="the-abandoned-world")
        hooks = LiveHooks(bridge=bridge)
        executor = FakeExecutor(
            context=FakeExecutorContext(world="the-rebuilt-world"),
            motion_statechart="chart",
        )

        hooks._observe_tick(lambda executor: None, executor)

        assert bridge.attached == ["the-rebuilt-world"]

    def test_a_bridge_failure_does_not_stop_the_tick(self):
        """
        A visualization bug must never take the robot demo down.
        """
        bridge = FakeBridge(world="already-bound", raise_on_observe_tick=True)
        hooks = LiveHooks(bridge=bridge)
        executor = FakeExecutor(
            context=FakeExecutorContext(world="the-world"), motion_statechart="chart"
        )

        result = hooks._observe_tick(lambda executor: "ticked", executor)

        assert result == "ticked"


# %% plan hook
@pytest.fixture
def installed_on_a_bridge(monkeypatch):
    """
    The plan hooks installed the way the runner installs them, on a bridge of this
    test's own, and taken off both classes again afterwards.
    """
    bridge = Bridge()
    monkeypatch.setattr(cramera.live.hooks, "BRIDGE", bridge)
    monkeypatch.setattr(cramera.live.hooks, "_LIVE_HOOKS", LiveHooks(bridge=bridge))
    # re-setting each method to what it already is registers it for restoration, so the
    # patches the install leaves behind come off with the fixture
    monkeypatch.setattr(PlanNode, "perform", PlanNode.perform)
    monkeypatch.setattr(GiskardExecutable, "execute", GiskardExecutable.execute)
    install_plan_hooks()
    return bridge


class TestFollowPlan:
    def test_the_performing_node_s_plan_is_captured_before_it_performs(self):
        """
        A demo performs a plan *node*, so the plan is read off the node.

        ``Plan.perform`` is one way in but not the only one: coraplex's own
        ``execute_single`` hands back the root node and the caller performs that, which
        never enters ``Plan.perform`` at all.
        """
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)
        node = FakePlanNode(plan="the-plan")
        order = []

        def original(node: Any) -> str:
            order.append(node)
            return "performed"

        result = hooks._follow_plan(original, node)

        assert bridge.followed_plans == ["the-plan"]
        assert order == [node]
        assert result == "performed"

    def test_a_node_performed_on_its_own_publishes_its_plan(
        self, installed_on_a_bridge
    ):
        """
        The hooks have to sit on the method a demo actually calls.

        coraplex's ``execute_single`` hands back the root node and the caller performs
        that, so hooks watching ``Plan.perform`` see nothing of such a run and the
        viewer is left with no plan to draw.
        """
        plan = Plan()
        node = SequentialNode()
        plan.add_node(node)

        node.perform()

        assert [
            entry["kind"] for entry in installed_on_a_bridge.get_plan()["nodes"]
        ] == ["SequentialNode"]


# %% motion-group hook
class TestTrackMotionGroup:
    def test_a_successful_execution_freezes_succeeded(self):
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)

        result = hooks._track_motion_group(lambda executable: "ok", "the-executable")

        assert bridge.bound_motion_groups == ["the-executable"]
        assert bridge.frozen_motion_groups == [
            ("the-executable", TaskStatusName.SUCCEEDED)
        ]
        assert result == "ok"

    def test_a_failed_execution_freezes_failed_and_reraises(self):
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)

        def original(executable: Any) -> None:
            raise RuntimeError("motion group failed")

        with pytest.raises(RuntimeError):
            hooks._track_motion_group(original, "the-executable")

        assert bridge.frozen_motion_groups == [
            ("the-executable", TaskStatusName.FAILED)
        ]


# %% mesh hook
class TestRememberMeshFile:
    def test_the_mesh_source_is_remembered_before_parsing(self):
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)

        result = hooks._remember_mesh_file(
            lambda parser: "a-world", FakeMeshParser(file_path="cup.stl")
        )

        assert bridge.remembered_mesh_files == ["cup.stl"]
        assert result == "a-world"

    def test_an_empty_file_path_is_not_remembered(self):
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)

        hooks._remember_mesh_file(
            lambda parser: "a-world", FakeMeshParser(file_path="")
        )

        assert bridge.remembered_mesh_files == []


# %% urdf source hook
class TestRememberUrdfSource:
    def test_the_urdf_source_is_remembered_before_parsing(self):
        bridge = FakeBridge()
        hooks = LiveHooks(bridge=bridge)

        result = hooks._remember_urdf_source(
            lambda cls, file_path, **kwargs: "a-parser", "the-cls", "robot.urdf"
        )

        assert bridge.remembered_urdf_sources == ["robot.urdf"]
        assert result == "a-parser"
