from __future__ import annotations

import json
from dataclasses import dataclass, field
from threading import Thread
from time import sleep
from typing_extensions import Any

import rclpy
from json_msgs.action import JsonAction
from json_msgs.action._json_action import JsonAction_Result
from std_msgs.msg import String
from cramph.composites import ChildChooserAccess
from cramph.context import ContextExtension, StatechartContext
from cramph.executor import Executor, ExecutorExtension
from cramph.statechart import Statechart
from giskardpy.middleware.ros2 import rospy
from giskardpy.middleware.ros2.child_choices import (
    ChildChoiceClient,
    child_choices_topic,
)
from giskardpy.middleware.ros2.client_presence import ClientHeartbeatPublisher
from giskardpy.middleware.ros2.exceptions import (
    NoActiveGoalToCancelError,
    StatechartNotEndedByResultError,
)
from giskardpy.middleware.ros2.feedback_publisher import MotionStatechartPayloadKey
from giskardpy.middleware.ros2.motion_goal import MotionGoal
from giskardpy.middleware.ros2.ros2_interface import MyActionClient
from giskardpy.middleware.ros2.state_updates import StatechartStateUpdate
from giskardpy.middleware.ros2.world_updates import ClientWorldUpdates
from giskardpy.motion_control import MotionControl
from rclpy import Context, Parameter, Future
from action_msgs.msg import GoalStatus
from rclpy.action.client import ClientGoalHandle
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from semantic_digital_twin.adapters.ros.messages import MetaData
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.adapters.world_entity_kwargs_tracker import (
    WorldEntityWithIDKwargsTracker,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World


@dataclass
class GiskardClientExecutor(Executor):
    """
    Executes a statechart by sending it to Giskard over ROS and waiting until it ended
    there.

    The statechart is built in :attr:`context`, whose world is kept in step with the
    world of Giskard. The nodes of the statechart that choose their child are answered
    with the :class:`~cramph.composites.ChildChooserAccess` of :attr:`context`, if it
    has one.

    :param node_handle: node used to talk to Giskard
    :param giskard_node_name: node name of Giskard
    :param world: world to keep in step with the world of Giskard, fetched from Giskard
        when neither it nor :attr:`context` is given
    """

    context: StatechartContext | None = field(default=None, kw_only=True)
    """
    The context the statecharts sent to Giskard are built in.

    When not given, it is built over :attr:`world` with what
    :class:`~giskardpy.motion_control.MotionControl` adds to a context, which the motion
    nodes need to expand.
    """

    node_handle: Node
    giskard_node_name: str = "giskard"
    _goal_handle: ClientGoalHandle | None = None
    _goal_result: JsonAction_Result | None = None
    _result_future: Future | None = None
    world: World = None
    _client: MyActionClient = None

    world_updates: ClientWorldUpdates = field(init=False, default=None)
    """
    Keeps this world in step with the world Giskard controls around a goal.
    """

    heartbeat_publisher: ClientHeartbeatPublisher = field(init=False, default=None)
    """
    Announces to Giskard that this client is still waiting for its goal.
    """

    def __post_init__(self):
        super().__post_init__()
        if self.context is not None:
            self.world = self.context.world
        if self.world is None:
            self.node_handle.get_logger().info(
                "No world provided, fetching from service"
            )
            self.world = fetch_world_from_service(self.node_handle, timeout_seconds=300)
            self.node_handle.get_logger().info("world synced")
            WorldSynchronizer(_world=self.world, node=self.node_handle)
        if self.context is None:
            self.context = StatechartContext(world=self.world)
            MotionControl().extend_context(self.context)
        self.world_updates = ClientWorldUpdates(
            world_synchronizer=WorldSynchronizer.of_world(self.world)
        )
        self.heartbeat_publisher = ClientHeartbeatPublisher(
            node=self.node_handle,
            client=self.client,
            giskard_node_name=self.giskard_node_name,
        )
        giskard_topic = f"{self.giskard_node_name}/command"
        self._client = MyActionClient(self.node_handle, JsonAction, giskard_topic)
        sleep(0.3)

    def default_context_extensions(self) -> list[ContextExtension]:
        return []

    def default_executor_extensions(self) -> list[ExecutorExtension]:
        return []

    @property
    def client(self) -> MetaData:
        """
        Who this client is, as it names itself in its goals and its heartbeats.
        """
        return self.world_updates.world_synchronizer.meta_data

    @property
    def robot_name(self) -> PrefixedName:
        return self.robot.name

    @property
    def robot(self) -> AbstractRobot:
        return self.world.get_semantic_annotations_by_type(AbstractRobot)[0]

    def compile(self, statechart: Statechart) -> None:
        """
        Does what :meth:`Executor.compile` does, then tells every extension that the
        statechart is compiled.
        """
        super().compile(statechart)
        self._notify_compiled()

    def execute_async(self) -> Future:
        """
        Sends the compiled statechart to Giskard without waiting for it to end, see
        :meth:`get_result`.

        :return: future that completes once Giskard accepted or rejected the goal
        """
        self.statechart.sanity_check()
        return self._client.send_goal_async(self._create_goal_message())

    def execute(self) -> None:
        """
        Sends the compiled statechart to Giskard, keeps its states in step with the ones
        Giskard reports while it runs, waits until it ended there, takes over its final
        states and tells every extension that the run stopped.

        A goal that fails raises the exception that made Giskard abort it, for example
        :class:`WorldModelModifiedDuringMotionError` when another process modified the
        world model while the motion was running.
        """
        self.statechart.sanity_check()
        child_chooser_access = self.context.get_extension(ChildChooserAccess)
        try:
            if child_chooser_access is None:
                result = self._client.send_goal(
                    self._create_goal_message(),
                    feedback_callback=lambda feedback_message: self._follow_states(
                        json.loads(feedback_message.feedback.feedback)
                    ),
                )
            else:
                result = self._send_action_goal_choosing_children(child_chooser_access)
            self._take_over_result(result)
        finally:
            self.finish_run()

    def _follow_states(self, feedback: dict[str, Any]) -> None:
        """
        Write the states Giskard reports in `feedback` into the compiled statechart.

        :param feedback: The feedback of the running goal.
        """
        StatechartStateUpdate.from_json(feedback, statechart=self.statechart).apply()

    def _send_action_goal_choosing_children(
        self, child_chooser_access: ChildChooserAccess
    ) -> JsonAction_Result:
        """
        Send the goal, follow the states Giskard reports, see :meth:`_follow_states`,
        and answer every node Giskard reports as waiting for a child.

        .. note:: The states are followed and the children are chosen in the thread that
            receives the feedback.

        :param child_chooser_access: holds the chooser of the children
        :return: result of the finished goal
        """
        client = ChildChoiceClient(
            statechart=self.statechart,
            chooser=child_chooser_access.chooser,
            world_updates=self.world_updates,
            required_position=self.world_updates.required_position(),
        )
        publisher = self.node_handle.create_publisher(
            String, child_choices_topic(self.giskard_node_name), 10
        )

        def answer(feedback_message) -> None:
            feedback = json.loads(feedback_message.feedback.feedback)
            self._follow_states(feedback)
            for choice in client.answer(feedback):
                publisher.publish(String(data=json.dumps(choice.to_json())))

        try:
            return self._client.send_goal(
                self._create_goal_message(), feedback_callback=answer
            )
        finally:
            self.node_handle.destroy_publisher(publisher)

    def _take_over_result(self, result: JsonAction_Result) -> None:
        """
        Copy the final states of a finished goal into the compiled statechart.

        An aborted goal whose statechart never compiled reports no states.

        :param result: result of a goal that succeeded or was aborted
        :raises Exception: The exception that made Giskard abort the goal, see
            :meth:`MyActionClient.create_abort_exception`.
        :raises StatechartNotEndedByResultError: If a goal that succeeded leaves the
            statechart not ended.
        """
        result_json = json.loads(result.result.result)
        if result.status == GoalStatus.STATUS_ABORTED:
            if MotionStatechartPayloadKey.LIFE_CYCLE_STATE in result_json:
                StatechartStateUpdate.from_json(
                    result_json, statechart=self.statechart
                ).apply()
            raise self._client.create_abort_exception(
                result,
                **WorldEntityWithIDKwargsTracker.from_world(self.world).create_kwargs(),
            )
        self.world_updates.wait_for_the_changes_of_a_goal(result_json)
        StatechartStateUpdate.from_json(result_json, statechart=self.statechart).apply()
        if not self.statechart.is_ended():
            raise StatechartNotEndedByResultError()

    def _create_goal_message(self) -> JsonAction.Goal:
        """
        Wrap the compiled statechart into a goal that names the change of this world it
        was built on.

        :return: action goal message holding the serialized motion goal
        """
        goal_msg = JsonAction.Goal()
        goal = MotionGoal.for_motion_statechart(
            self.statechart,
            client=self.client,
            required_position=self.world_updates.required_position(),
        )
        goal_msg.goal = json.dumps(goal.to_json())
        return goal_msg

    def cancel_goal_async(self) -> Future:
        """
        Stops the goal that was last sent to Giskard.

        :return: future that completes once the cancel request was answered
        """
        try:
            future = self._client._goal_handle.cancel_goal_async()
        except AttributeError as e:
            raise NoActiveGoalToCancelError()
        return future

    async def get_result(self):
        """
        Wait for the goal sent with :func:`execute_async`, sync its final states and
        tell every extension that the run stopped.

        A goal that fails raises the exception that made Giskard abort it, for example
        :class:`WorldModelModifiedDuringMotionError` when another process modified the
        world model while the motion was running.
        """
        try:
            result = await self._client.get_result()
            self._take_over_result(result)
        finally:
            self.finish_run()

    def close(self) -> None:
        """
        Stop announcing this client's heartbeat to Giskard.

        Does not touch :attr:`node_handle`: it was given to this executor by its caller,
        who owns its lifecycle.
        """
        self.heartbeat_publisher.stop()


@dataclass
class GiskardClientExecutorNode(GiskardClientExecutor):
    is_spinning: bool = False
    node_name: str = "giskard_client"
    giskard_node_name: str = "giskard"
    avoid_name_conflict: bool = True
    ros_context: Context | None = field(kw_only=True, default=None)
    cli_args: list[str] | None = field(kw_only=True, default=None)
    namespace: str | None = field(kw_only=True, default=None)
    use_global_arguments: bool = field(kw_only=True, default=True)
    enable_rosout: bool = field(kw_only=True, default=True)
    start_parameter_services: bool = field(kw_only=True, default=True)
    parameter_overrides: list[Parameter] | None = field(kw_only=True, default=None)
    allow_undeclared_parameters: bool = field(kw_only=True, default=False)
    automatically_declare_parameters_from_overrides: bool = field(
        kw_only=True, default=False
    )
    enable_logger_service: bool = field(kw_only=True, default=False)
    node_handle: Node = field(init=False)

    def __post_init__(self):
        self.node_handle = Node(
            self.node_name,
            context=self.ros_context,
            cli_args=self.cli_args,
            namespace=self.namespace,
            use_global_arguments=self.use_global_arguments,
            enable_rosout=self.enable_rosout,
            start_parameter_services=self.start_parameter_services,
            parameter_overrides=self.parameter_overrides,
            allow_undeclared_parameters=self.allow_undeclared_parameters,
            automatically_declare_parameters_from_overrides=self.automatically_declare_parameters_from_overrides,
        )
        rospy.executor.add_node(self.node_handle)
        self.is_spinning = False
        super().__post_init__()

    def __spin(self):
        self.my_executor = MultiThreadedExecutor()
        self.my_executor.add_node(self.node_handle)
        self.is_spinning = True
        while rclpy.ok():
            self.my_executor.spin_once(timeout_sec=1)
        self.is_spinning = False

    def spin_in_background(self):
        self.spinner = Thread(
            target=self.__spin, daemon=False, name="background giskard wrapper spinner"
        )
        self.spinner.start()

    def close(self) -> None:
        """
        Stop the heartbeat and destroy the node this executor created for itself.

        Removes the node from Giskard's shared executor before destroying it, since a
        destroyed node left registered there would break the next spin.
        """
        super().close()
        rospy.executor.remove_node(self.node_handle)
        self.node_handle.destroy_node()
