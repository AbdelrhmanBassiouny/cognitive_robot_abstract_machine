"""
Tests for asking a running demo about its own state.

The questions are answered from what the bridge already publishes, so the plan side is
exercised through the same plan-node mimics the bridge tests use, and the holding side
against a real world whose kinematic tree an object is carried and released in.
"""

from __future__ import annotations

import pytest

krrood = pytest.importorskip("krrood", reason="EQL requires krrood")

from semantic_digital_twin.datastructures.prefixed_name import (  # noqa: E402
    PrefixedName,
)
from semantic_digital_twin.world import World  # noqa: E402
from semantic_digital_twin.world_description.connections import (  # noqa: E402
    FixedConnection,
)
from semantic_digital_twin.world_description.world_entity import Body  # noqa: E402
from typing_extensions import Any, Dict, List, Tuple  # noqa: E402

from cramera.knowledge.query_runner import EmptyQuery, EqlQueryRunner  # noqa: E402
from cramera.live.bridge import Bridge, TaskStatusName  # noqa: E402
from cramera.live.http import serve  # noqa: E402
from cramera.live.held_objects import HeldObject  # noqa: E402
from cramera.live.query import NoQuerySourceRegistered  # noqa: E402
from cramera.live.robot_state import (  # noqa: E402
    ROBOT_STATE_PRESETS,
    RobotAction,
    RobotStateQuerySource,
)
from cramera.robot_parts import ArmSide  # noqa: E402

from .test_live_bridge import (  # noqa: E402
    ActionDescription,
    make_plan_node,
    PlanWithRoot,
    PublishedBody,
)
from .test_robot_parts import (  # noqa: E402
    ArmPart,
    EndEffectorPart,
    OneArmedRobot,
    TwoArmedRobot,
)
from .test_live_http import post  # noqa: E402
from .test_server import get_json  # noqa: E402

CEREAL_KEY = "cereal.obj"
"""
Published key of the object the tests hand to the robot.
"""

# %% a world an object can be carried in


def body(name: str, prefix: str = "stretch") -> Body:
    """
    One world body, named the way a composed world prefixes its models.

    :param name: The body's local name.
    :param prefix: The model prefix the body's name carries.
    """
    return Body(name=PrefixedName(name, prefix=prefix))


def chain(*bodies: Body) -> World:
    """
    A world whose bodies hang off each other in the order given, the first at the root.

    :param bodies: The bodies to chain, parent before child.
    """
    world = World()
    with world.modify_world():
        world.add_body(bodies[0])
        for parent, child in zip(bodies, bodies[1:]):
            world.add_connection(FixedConnection(parent=parent, child=child))
    return world


def hang(world: World, parent: Body, child: Body) -> None:
    """
    Hang a body off another one, moving it there when it hangs somewhere already.

    :param world: The world both bodies live in.
    :param parent: The body to hang ``child`` off.
    :param child: The body to (re)parent.
    """
    with world.modify_world():
        if child.index is not None and child.parent_kinematic_structure_entity:
            world.remove_connection(child.parent_connection)
        world.add_connection(FixedConnection(parent=parent, child=child))


class TestHeldObjects:
    def test_an_object_standing_in_the_world_is_not_held(self):
        ground, base, gripper = body("map", prefix="world"), body("base"), body("grip")
        cereal = body(CEREAL_KEY)
        world = chain(ground, base, gripper)
        hang(world, ground, cereal)
        robot = OneArmedRobot(arm=ArmPart(bodies=[gripper]), root=base)

        assert HeldObject.of_bodies(robot, {CEREAL_KEY: cereal}) == []

    def test_an_object_below_the_gripper_is_held_by_its_arm(self):
        ground, base, gripper = body("map", prefix="world"), body("base"), body("grip")
        cereal = body(CEREAL_KEY)
        chain(ground, base, gripper, cereal)
        robot = OneArmedRobot(
            arm=ArmPart(
                bodies=[gripper], end_effector=EndEffectorPart(bodies=[gripper])
            ),
            root=base,
        )

        assert HeldObject.of_bodies(robot, {CEREAL_KEY: cereal}) == [
            HeldObject(name=CEREAL_KEY, attached_to="grip", arm="ArmPart", side=None)
        ]

    def test_an_object_stacked_on_a_held_one_is_held_by_the_same_body(self):
        ground, base, gripper = body("map", prefix="world"), body("base"), body("grip")
        tray, cereal = body("tray.obj"), body(CEREAL_KEY)
        chain(ground, base, gripper, tray, cereal)
        robot = OneArmedRobot(arm=ArmPart(bodies=[gripper]), root=base)

        held = HeldObject.of_bodies(robot, {CEREAL_KEY: cereal})

        assert [(entry.name, entry.attached_to) for entry in held] == [
            (CEREAL_KEY, "grip")
        ]

    def test_an_object_on_an_unannotated_robot_body_names_no_arm(self):
        ground, base = body("map", prefix="world"), body("base")
        cereal = body(CEREAL_KEY)
        chain(ground, base, cereal)
        robot = OneArmedRobot(arm=ArmPart(bodies=[body("grip")]), root=base)

        assert HeldObject.of_bodies(robot, {CEREAL_KEY: cereal}) == [
            HeldObject(name=CEREAL_KEY, attached_to="base", arm=None, side=None)
        ]

    def test_the_side_of_the_carrying_arm_is_reported(self):
        ground, base = body("map", prefix="world"), body("base")
        right_gripper, cereal = body("r_grip"), body(CEREAL_KEY)
        chain(ground, base, right_gripper, cereal)
        robot = TwoArmedRobot(
            left=ArmPart(bodies=[body("l_grip")]),
            right=ArmPart(bodies=[right_gripper]),
            root=base,
        )

        held = HeldObject.of_bodies(robot, {CEREAL_KEY: cereal})

        assert [(entry.arm, entry.side) for entry in held] == [
            ("ArmPart", ArmSide.RIGHT)
        ]

    def test_nothing_is_held_while_no_robot_is_bound(self):
        assert HeldObject.of_bodies(None, {CEREAL_KEY: body(CEREAL_KEY)}) == []


# %% what the robot is doing


class PickUpDescription(ActionDescription):
    """
    A designator describing a pick-up, so its action node is labelled by it.
    """


def transporting_plan(
    transport_status: str = TaskStatusName.CREATED,
    pick_up_status: str = TaskStatusName.CREATED,
) -> Any:
    """
    A plan root holding a transport action that holds a pick-up action.

    :param transport_status: Status the outer action reports.
    :param pick_up_status: Status the inner action reports.
    """
    pick_up = make_plan_node(
        "ActionNode",
        status=pick_up_status,
        designator=PickUpDescription(arm="LEFT", target=CEREAL_KEY),
        children=[make_plan_node("MotionNode")],
    )
    transport = make_plan_node(
        "ActionNode", status=transport_status, children=[pick_up]
    )
    return make_plan_node("SequentialNode", children=[transport])


def actions_of(root: Any) -> List[RobotAction]:
    """
    The actions of a plan, as one bridge snapshot renders them.

    :param root: The plan's root node.
    """
    bridge = Bridge()
    bridge.publish_bodies({CEREAL_KEY: PublishedBody(name="world/" + CEREAL_KEY)})
    bridge.begin_plan(PlanWithRoot(root=root))
    return RobotAction.of_plan(bridge.plan_nodes())


def flat_plan(status: str = TaskStatusName.RUNNING) -> Any:
    """
    A plan root holding one action and nothing nested inside it.

    :param status: Status the action reports.
    """
    return make_plan_node(
        "SequentialNode",
        children=[
            make_plan_node(
                "ActionNode", status=status, designator=PickUpDescription(arm="LEFT")
            )
        ],
    )


def running_plan() -> Any:
    """
    A transport whose pick-up is running right now.
    """
    return transporting_plan(
        transport_status=TaskStatusName.RUNNING,
        pick_up_status=TaskStatusName.RUNNING,
    )


class TestPlanActions:
    def test_only_the_actions_of_the_plan_become_entities(self):
        assert [action.name for action in actions_of(transporting_plan())] == [
            "ActionNode",
            "PickUpDescription",
        ]

    def test_the_nesting_of_each_action_is_carried(self):
        assert [action.depth for action in actions_of(transporting_plan())] == [1, 2]

    def test_the_designators_arm_and_target_are_carried(self):
        pick_up = actions_of(transporting_plan())[-1]
        assert (pick_up.arm, pick_up.target) == ("LEFT", CEREAL_KEY)

    def test_nothing_is_the_goal_while_nothing_runs(self):
        actions = actions_of(transporting_plan())
        assert [action.is_goal for action in actions] == [False, False]
        assert [action.is_current_step for action in actions] == [False, False]

    def test_the_outermost_running_action_is_the_goal(self):
        assert [action.is_goal for action in actions_of(running_plan())] == [
            True,
            False,
        ]

    def test_the_innermost_running_action_is_the_current_step(self):
        assert [action.is_current_step for action in actions_of(running_plan())] == [
            False,
            True,
        ]

    def test_an_action_running_inside_another_leaves_the_goal_to_it(self):
        """
        A parent whose child runs is reported running too, so the goal is the enclosing
        action rather than the step being taken inside it.
        """
        actions = actions_of(transporting_plan(pick_up_status=TaskStatusName.RUNNING))
        assert [(action.is_goal, action.is_current_step) for action in actions] == [
            (True, False),
            (False, True),
        ]

    def test_the_only_running_action_of_a_flat_plan_is_both(self):
        running = actions_of(flat_plan())[0]
        assert (running.is_goal, running.is_current_step) == (True, True)


# %% the bridge's side of it


def running_bridge(offers_its_state: bool = True) -> Tuple[Bridge, World, Body, Body]:
    """
    A bridge whose demo is transporting a cereal box it is holding right now.

    :param offers_its_state: Whether the demo registers its state to be asked about, as
        the live visualization does on start.
    :return: The bridge, its world, the world's ground body and the cereal box.
    """
    ground, base, gripper = body("map", prefix="world"), body("base"), body("grip")
    cereal = body(CEREAL_KEY)
    world = chain(ground, base, gripper, cereal)
    bridge = Bridge()
    bridge.world = world
    bridge.robot = OneArmedRobot(arm=ArmPart(bodies=[gripper]), root=base)
    bridge.publish_bodies({CEREAL_KEY: cereal})
    bridge.refresh_held_objects()
    bridge.begin_plan(PlanWithRoot(root=running_plan()))
    if offers_its_state:
        bridge.register_query_source(RobotStateQuerySource(bridge=bridge))
    return bridge, world, ground, cereal


class TestQuerySourceRegistration:
    def test_a_bridge_without_a_source_answers_nothing(self):
        with pytest.raises(NoQuerySourceRegistered):
            Bridge().query_presets()

    def test_a_bridge_without_a_source_names_no_variables(self):
        with pytest.raises(NoQuerySourceRegistered):
            Bridge().query_variables()

    def test_the_offered_variables_are_the_sources_domains(self):
        bridge, _, _, _ = running_bridge()
        assert bridge.query_variables() == ["action", "held_object"]

    def test_the_title_names_the_bound_robot(self):
        bridge, _, _, _ = running_bridge()
        assert bridge.query_title() == "OneArmedRobot (live)"

    def test_a_source_without_a_robot_still_names_itself(self):
        assert RobotStateQuerySource(bridge=Bridge()).title() == "the running demo"

    def test_a_source_without_a_demo_offers_empty_domains(self):
        domains = RobotStateQuerySource(bridge=Bridge()).domains()
        assert [(domain.name, domain.objects) for domain in domains] == [
            ("action", []),
            ("held_object", []),
        ]


# %% answering the questions the panel offers


def answer(bridge: Bridge, code: str) -> Dict[str, Any]:
    """
    Run one query against a bridge's registered source.

    :param bridge: The bridge whose demo is asked.
    :param code: The EQL query source.
    """
    return EqlQueryRunner(domains=bridge.query_domains()).run(code).to_payload()


def preset_code(text: str) -> str:
    """
    The code of the offered question with the given label.

    :param text: The question's label, as the panel's button shows it.
    """
    return next(preset.code for preset in ROBOT_STATE_PRESETS if preset.text == text)


class TestAnsweringQuestions:
    @pytest.mark.parametrize("preset", ROBOT_STATE_PRESETS, ids=lambda p: p.text)
    def test_every_offered_question_runs(self, preset):
        bridge, _, _, _ = running_bridge()
        assert answer(bridge, preset.code)["ok"] is True

    def test_what_are_you_holding_names_the_carried_object(self):
        bridge, _, _, _ = running_bridge()
        rows = answer(bridge, preset_code("what are you holding right now?"))["rows"]
        assert [(row["__entity__"], row["arm"]) for row in rows] == [
            (CEREAL_KEY, "ArmPart")
        ]

    def test_a_released_object_is_no_longer_held(self):
        bridge, world, ground, cereal = running_bridge()
        hang(world, ground, cereal)
        bridge.refresh_held_objects()

        assert (
            answer(bridge, preset_code("what are you holding right now?"))["rows"] == []
        )

    def test_what_is_your_current_action_names_the_innermost_running_one(self):
        bridge, _, _, _ = running_bridge()
        rows = answer(bridge, preset_code("what is your current action?"))["rows"]
        assert [row["__entity__"] for row in rows] == ["PickUpDescription"]

    def test_what_is_your_current_goal_names_the_outermost_running_one(self):
        bridge, _, _, _ = running_bridge()
        rows = answer(bridge, preset_code("what is your current goal?"))["rows"]
        assert [row["__entity__"] for row in rows] == ["ActionNode"]

    def test_a_question_naming_something_unknown_raises(self):
        bridge, _, _, _ = running_bridge()
        with pytest.raises(NameError):
            answer(bridge, "an(entity(nonexistent))")


# %% the endpoints the panel asks through


def served(bridge: Bridge):
    """
    Serve one bridge on an ephemeral port for the duration of a test.

    :param bridge: The bridge to serve.
    """
    httpd = serve(bridge, 0)
    yield "http://localhost:%d" % httpd.server_address[1]
    httpd.shutdown()


@pytest.fixture()
def demo_server():
    """
    A server bound to a running demo that offers its state to be asked about.
    """
    bridge, _, _, _ = running_bridge()
    yield from served(bridge)


@pytest.fixture()
def unasked_demo_server():
    """
    A server bound to a running demo that offered nothing to be asked about.
    """
    bridge, _, _, _ = running_bridge(offers_its_state=False)
    yield from served(bridge)


class TestQueryEndpoints:
    def test_the_offered_questions_are_served(self, demo_server):
        payload = get_json(demo_server + "/presets")
        assert payload["ok"] is True
        assert payload["title"] == "OneArmedRobot (live)"
        assert [preset["text"] for preset in payload["presets"]] == [
            preset.text for preset in ROBOT_STATE_PRESETS
        ]
        assert payload["variables"] == ["action", "held_object"]

    def test_a_demo_that_offered_nothing_serves_no_questions(self, unasked_demo_server):
        payload = get_json(unasked_demo_server + "/presets")
        assert payload["ok"] is False
        assert payload["presets"] == []

    def test_a_question_is_answered_with_its_rows(self, demo_server):
        status, payload = post(
            demo_server + "/eql",
            {"code": preset_code("what are you holding right now?")},
        )
        assert status == 200
        assert payload["ok"] is True
        assert [row["__entity__"] for row in payload["rows"]] == [CEREAL_KEY]

    def test_an_empty_question_is_refused(self, demo_server):
        _, payload = post(demo_server + "/eql", {"code": "   "})
        assert payload["ok"] is False
        assert payload["error"].startswith(EmptyQuery.__name__)

    def test_a_question_naming_something_unknown_is_reported_by_its_type(
        self, demo_server
    ):
        _, payload = post(demo_server + "/eql", {"code": "an(entity(nonexistent))"})
        assert payload["ok"] is False
        assert payload["error"].startswith(NameError.__name__)

    def test_a_demo_that_offered_nothing_answers_nothing(self, unasked_demo_server):
        _, payload = post(unasked_demo_server + "/eql", {"code": "an(entity(action))"})
        assert payload["ok"] is False
