"""Unit tests for the live bridge's plan/statechart serializers.

The Bridge runs against stub plan nodes and stub statecharts — no coraplex or
giskardpy needed — because the serializers only touch duck-typed attributes
(children, status.name, designator, life_cycle_state, rx_graph, …). What IS
covered is the interesting logic: bottom-up status aggregation in the plan
tree, freeze semantics when a motion group finishes, and structure signatures
that let the frontend distinguish "re-colour only" from "rebuild".
"""

import types

import pytest

from cram_viz.live.bridge import Bridge


class _Status:
    def __init__(self, name):
        self.name = name


def make_node(kind, status="CREATED", designator=None, children=()):
    cls = type(kind, (object,), {})
    node = cls()
    node.status = _Status(status)
    node.designator = designator
    node.children = list(children)
    return node


class _Designator:
    def __init__(self, target=None, arm=None):
        if target:
            self.obj = types.SimpleNamespace(name="world/" + target)
        if arm:
            self.arm = arm


class _Task:
    def __init__(self, life_cycle):
        self.life_cycle_state = life_cycle


@pytest.fixture()
def plan_bridge():
    """A bridge bound to a small plan: root -> action -> [condition, motion]."""
    bridge = Bridge()
    motion = make_node("MotionNode", designator=_Designator(target="milk.stl"))
    condition = make_node("ConditionNode")
    action = make_node("ActionNode", designator=_Designator(arm="LEFT"),
                       children=[condition, motion])
    root = make_node("SequentialNode", status="SUCCEEDED", children=[action])
    bridge._bodies = {"milk.stl": object(), "__base__": object()}
    bridge._plan = types.SimpleNamespace(root=root)
    return bridge, root, action, condition, motion


def by_kind(bridge):
    return {n["kind"]: n for n in bridge.get_plan()["nodes"]}


class TestPlanSnapshot:
    def test_running_task_bubbles_up(self, plan_bridge):
        bridge, root, action, condition, motion = plan_bridge
        bridge._motion_tasks[id(motion)] = _Task(1)          # RUNNING
        bridge.snapshot_plan()
        nodes = by_kind(bridge)
        assert nodes["MotionNode"]["status"] == "RUNNING"
        assert nodes["MotionNode"]["derived"] is True
        assert nodes["ActionNode"]["status"] == "RUNNING"

    def test_designator_metadata_is_serialized(self, plan_bridge):
        bridge, *_ = plan_bridge
        bridge.snapshot_plan()
        nodes = by_kind(bridge)
        assert nodes["MotionNode"]["target"] == "milk.stl"
        assert nodes["ActionNode"]["arm"] == "LEFT"

    def test_real_status_wins_over_derivation(self, plan_bridge):
        bridge, *_ = plan_bridge
        bridge.snapshot_plan()
        assert by_kind(bridge)["SequentialNode"]["status"] == "SUCCEEDED"
        assert by_kind(bridge)["SequentialNode"]["derived"] is False

    def test_partially_done_parent_is_running_not_succeeded(self, plan_bridge):
        bridge, root, action, condition, motion = plan_bridge
        bridge._frozen[id(motion)] = "SUCCEEDED"             # condition still CREATED
        bridge.snapshot_plan()
        assert by_kind(bridge)["ActionNode"]["status"] == "RUNNING"

    def test_fully_done_parent_is_succeeded(self, plan_bridge):
        bridge, root, action, condition, motion = plan_bridge
        bridge._frozen[id(motion)] = "SUCCEEDED"
        bridge._frozen[id(condition)] = "SUCCEEDED"
        bridge.snapshot_plan()
        assert by_kind(bridge)["ActionNode"]["status"] == "SUCCEEDED"

    def test_failure_outranks_done_sibling(self, plan_bridge):
        bridge, root, action, condition, motion = plan_bridge
        bridge._frozen[id(motion)] = "SUCCEEDED"
        bridge._frozen[id(condition)] = "FAILED"
        bridge.snapshot_plan()
        assert by_kind(bridge)["ActionNode"]["status"] == "FAILED"

    def test_signature_is_stable_across_status_changes(self, plan_bridge):
        bridge, root, action, condition, motion = plan_bridge
        bridge._motion_tasks[id(motion)] = _Task(1)
        bridge.snapshot_plan()
        sig1 = bridge.get_plan()["sig"]
        bridge._motion_tasks.clear()
        bridge._frozen[id(motion)] = "SUCCEEDED"
        bridge.snapshot_plan()
        assert bridge.get_plan()["sig"] == sig1


class TestFreezeSemantics:
    def test_freeze_pins_status_and_releases_tasks(self, plan_bridge):
        bridge, root, action, condition, motion = plan_bridge
        executable = types.SimpleNamespace(
            motion_mappings={motion: _Task(1)},
            pre_condition_node=condition, post_condition_node=None)
        bridge.bind_motion_group(executable)
        assert id(motion) in bridge._motion_tasks
        bridge.freeze_motion_group(executable, "SUCCEEDED")
        assert id(motion) not in bridge._motion_tasks
        bridge.snapshot_plan()
        nodes = by_kind(bridge)
        assert nodes["MotionNode"]["status"] == "SUCCEEDED"
        assert nodes["ConditionNode"]["status"] == "SUCCEEDED"


# ---- statechart -------------------------------------------------------------
class _SNode:
    def __init__(self, index, name, parent=None):
        self.index = index
        self.name = name
        self.parent_node_index = parent


class _Transition:
    def __init__(self, kind):
        self.kind = types.SimpleNamespace(name=kind)


class _RxGraph:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def edge_index_map(self):
        return {i: e for i, e in enumerate(self._edges)}

    def get_node_data(self, i):
        return self._nodes[i]


def make_chart(life=(1, 1, 0), obs=(0.5, 0.5, 0.0)):
    chart = types.SimpleNamespace()
    chart.nodes = [_SNode(0, "Goal"), _SNode(1, "MoveJoints", 0),
                   _SNode(2, "JointGoalReached")]
    chart.rx_graph = _RxGraph(chart.nodes, [(0, 1, _Transition("START")),
                                            (1, 2, _Transition("END"))])
    chart.life_cycle_state = types.SimpleNamespace(data=list(life))
    chart.observation_state = types.SimpleNamespace(data=list(obs))
    return chart


class TestChartSnapshot:
    def test_structure_and_states(self):
        bridge = Bridge()
        bridge._chart_title = "TransportAction"
        bridge.observe_chart(make_chart())
        chart = bridge.get_chart()
        assert chart["title"] == "TransportAction"
        assert [n["life"] for n in chart["nodes"]] == ["RUNNING", "RUNNING", "NOT_STARTED"]
        assert [n["obs"] for n in chart["nodes"]] == ["UNKNOWN", "UNKNOWN", "FALSE"]
        assert chart["nodes"][1]["parent"] == "s0"
        assert chart["edges"] == [{"from": "s0", "to": "s1", "kind": "START"},
                                  {"from": "s1", "to": "s2", "kind": "END"}]

    def test_lifecycle_update_keeps_signature(self):
        bridge = Bridge()
        chart = make_chart()
        bridge.observe_chart(chart)
        sig = bridge.get_chart()["sig"]
        chart.life_cycle_state.data = [3, 3, 3]
        bridge.observe_chart(chart)
        assert bridge.get_chart()["sig"] == sig
        assert [n["life"] for n in bridge.get_chart()["nodes"]] == ["DONE"] * 3

    def test_new_chart_replaces_structure(self):
        bridge = Bridge()
        bridge.observe_chart(make_chart())
        sig = bridge.get_chart()["sig"]
        other = types.SimpleNamespace(
            nodes=[_SNode(0, "OtherGoal")],
            rx_graph=_RxGraph([_SNode(0, "OtherGoal")], []),
            life_cycle_state=types.SimpleNamespace(data=[1]),
            observation_state=types.SimpleNamespace(data=[1.0]))
        bridge.observe_chart(other)
        chart = bridge.get_chart()
        assert chart["sig"] != sig
        assert len(chart["nodes"]) == 1
        assert chart["nodes"][0]["obs"] == "TRUE"

    def test_trinary_observation_thresholds(self):
        bridge = Bridge()
        bridge.observe_chart(make_chart(obs=(0.0, 0.5, 1.0)))
        assert [n["obs"] for n in bridge.get_chart()["nodes"]] == ["FALSE", "UNKNOWN", "TRUE"]
