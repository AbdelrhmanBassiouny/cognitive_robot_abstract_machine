"""
Tests for :mod:`experiments.tracy_experiments.pickup.pickup_demo_real`: loose shapes are
spawned resting on the table with the grasp target lifted back to where the pick aimed
before the spawn was lowered, and while a shape is carried the gripper is re-closed and
watched for the shape slipping out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from coraplex.datastructures.enums import Arms
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    RECLOSE_SETPOINT,
    GripperClosure,
    GripperSlipEvent,
)
from experiments.tracy_experiments.pickup.pickup_demo_real import (
    GRASP_HEIGHT_OFFSET,
    PICK_TARGETS,
    _add_montessori_shape,
    _grasp_target_pose,
    _SortingRig,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

TABLE_TOP_Z = 0.75
"""
An arbitrary table-top height to spawn against.
"""


def _world_with_root() -> World:
    """
    A world holding only its root body, ready for a shape to be added.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(
            Body(name=PrefixedName(name="root", prefix="world"))
        )
    return world


# %% spawn height and grasp offset


def test_grasp_target_pose_sits_the_offset_above_the_body_origin():
    body = Body(name=PrefixedName("shape"))

    pose = _grasp_target_pose(body, GRASP_HEIGHT_OFFSET)

    translation = pose.to_homogeneous_matrix()[:3, 3]
    assert [float(component) for component in translation] == [
        0.0,
        0.0,
        GRASP_HEIGHT_OFFSET,
    ]
    assert pose.reference_frame is body


def test_a_loose_shape_is_spawned_resting_on_the_table():
    world = _world_with_root()
    target = PICK_TARGETS[0]

    body = _add_montessori_shape(world, TABLE_TOP_Z, target)

    spawned_z = float(world.compute_forward_kinematics_np(world.root, body)[2, 3])
    assert spawned_z == TABLE_TOP_Z + target.half_height


def test_the_grasp_is_aimed_where_the_pre_offset_spawn_put_it():
    world = _world_with_root()
    target = PICK_TARGETS[0]
    body = _add_montessori_shape(world, TABLE_TOP_Z, target)

    grasp_target = _grasp_target_pose(body, GRASP_HEIGHT_OFFSET)

    world_grasp_z = float(
        world.transform(grasp_target.to_homogeneous_matrix(), world.root)[2, 3]
    )
    assert world_grasp_z == TABLE_TOP_Z + target.half_height + GRASP_HEIGHT_OFFSET


# %% slip watch while carrying


@dataclass
class RecordingGripper:
    """
    Records every re-close instead of driving the real action server.
    """

    close_to_setpoints: list[float] = field(default_factory=list)
    """
    Setpoint of every :meth:`close_to` call, in order.
    """

    def close_to(self, arm: Arms, setpoint: float) -> None:
        self.close_to_setpoints.append(setpoint)


@dataclass
class SequencedClosureListener:
    """
    Serves a fixed sequence of knuckle readings, holding the last one.
    """

    readings: list[GripperClosure]
    """
    Readings handed out on successive accesses.
    """

    _next: int = 0
    """
    Index of the next reading to serve.
    """

    @property
    def latest_closure(self) -> GripperClosure:
        reading = self.readings[min(self._next, len(self.readings) - 1)]
        self._next += 1
        return reading


@dataclass
class PublishedEvent:
    """
    One event handed to the dashboard feed.
    """

    shape_name: str
    """
    Name the event was published under.
    """

    event: object
    """
    The event object.
    """


@dataclass
class RecordingFeed:
    """
    Records what the slip watch streams to the dashboard.
    """

    published: list[PublishedEvent] = field(default_factory=list)
    """
    Every :meth:`publish` call, in order.
    """

    def publish(self, shape_name: str, event: object) -> None:
        self.published.append(PublishedEvent(shape_name=shape_name, event=event))


def _slip_watch_rig(
    gripper: RecordingGripper,
    listener: SequencedClosureListener,
    feed: RecordingFeed | None = None,
) -> _SortingRig:
    """
    A rig with only the fields :meth:`_SortingRig._carry_watching_for_slip` reads.
    """
    return _SortingRig(
        context=None,
        world=None,
        robot=None,
        feed=feed,
        gripper=gripper,
        gripper_listener=listener,
        grasp_description=None,
        tool_frame=None,
        table_top_z=0.0,
        slip_watch_interval=0.01,
    )


def _held(*extra: float) -> SequencedClosureListener:
    """
    A listener whose grasp confirms as held, then serves ``extra`` poll readings.
    """
    return SequencedClosureListener(
        [GripperClosure(knuckle_position=position) for position in (0.45, *extra)]
    )


def _no_slip_watch_thread_left_running() -> bool:
    return not any(
        thread.name.startswith("slip-watch") and thread.is_alive()
        for thread in threading.enumerate()
    )


def _wait_until(predicate) -> None:
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.005)


def test_a_missed_grasp_skips_the_slip_watch_but_still_carries():
    gripper = RecordingGripper()
    listener = SequencedClosureListener(
        [GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION)]
    )
    rig = _slip_watch_rig(gripper, listener)
    carried: list[bool] = []

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("cube")), 0.5, lambda: carried.append(True)
    )

    assert carried == [True]
    assert gripper.close_to_setpoints == [0.5]
    assert _no_slip_watch_thread_left_running()


def test_a_held_grasp_re_closes_past_fully_closed_while_the_shape_is_carried():
    gripper = RecordingGripper()
    rig = _slip_watch_rig(gripper, _held())

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("cube")),
        0.5,
        lambda: _wait_until(lambda: len(gripper.close_to_setpoints) > 1),
    )

    assert gripper.close_to_setpoints[0] == 0.5
    assert RECLOSE_SETPOINT in gripper.close_to_setpoints[1:]
    assert _no_slip_watch_thread_left_running()


def test_a_slip_streams_a_gripper_slip_event_to_the_feed():
    gripper = RecordingGripper()
    feed = RecordingFeed()
    rig = _slip_watch_rig(gripper, _held(0.5), feed)
    body = Body(name=PrefixedName("cube"))

    rig._carry_watching_for_slip(
        body, 0.5, lambda: _wait_until(lambda: bool(feed.published))
    )

    assert feed.published
    assert all(entry.shape_name == "cube" for entry in feed.published)
    first_event = feed.published[0].event
    assert isinstance(first_event, GripperSlipEvent)
    assert first_event.tracked_object is body
    assert _no_slip_watch_thread_left_running()
