"""
Tests for :mod:`experiments.tracy_experiments.montessori.event_dashboard`: the event
feed keeps full history, replays it to a late subscriber before delivering live entries,
stops delivering once unsubscribed, and reduces an entry to the compact shape the
dashboard page reads.
"""

from __future__ import annotations

from experiments.tracy_experiments.montessori.event_dashboard import (
    EventFeed,
    FeedEntry,
    _entry_to_json,
)
from experiments.tracy_experiments.montessori.gripper_feedback import GripperSlipEvent
from segmind.datastructures.events import GraspEvent, PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body


def _bodies() -> tuple[Body, Body]:
    """
    A tracked shape body and a tool-frame body, unattached to any world.
    """
    return Body(name=PrefixedName("cube")), Body(name=PrefixedName("tool"))


def test_snapshot_returns_every_published_entry_in_order():
    feed = EventFeed()
    shape, tool = _bodies()
    grasp = GraspEvent(tracked_object=shape, with_object=tool)
    pick_up = PickUpEvent(tracked_object=shape)

    feed.publish("cube", grasp)
    feed.publish("cube", pick_up)

    snapshot = feed.snapshot()
    assert [entry.event for entry in snapshot] == [grasp, pick_up]
    assert [entry.shape_name for entry in snapshot] == ["cube", "cube"]


def test_a_late_subscriber_receives_the_history_then_live_entries():
    feed = EventFeed()
    shape, _ = _bodies()
    before = PickUpEvent(tracked_object=shape)
    feed.publish("cube", before)

    subscriber = feed.subscribe()
    after = PickUpEvent(tracked_object=shape)
    feed.publish("cube", after)

    assert subscriber.get_nowait().event is before
    assert subscriber.get_nowait().event is after


def test_unsubscribe_stops_further_delivery():
    feed = EventFeed()
    shape, _ = _bodies()
    subscriber = feed.subscribe()

    feed.unsubscribe(subscriber)
    feed.publish("cube", PickUpEvent(tracked_object=shape))

    assert subscriber.empty()


def test_entry_to_json_is_the_compact_page_shape():
    shape, tool = _bodies()
    grasp = GraspEvent(tracked_object=shape, with_object=tool)
    entry = FeedEntry(shape_name="cube", event=grasp)

    assert _entry_to_json(entry) == {
        "shape": "cube",
        "event_type": "GraspEvent",
        "with_object": str(tool.name),
        "timestamp": grasp.timestamp.isoformat(),
    }


def test_entry_to_json_leaves_with_object_absent_for_a_single_object_event():
    shape, _ = _bodies()
    entry = FeedEntry(shape_name="cube", event=PickUpEvent(tracked_object=shape))

    assert _entry_to_json(entry)["with_object"] is None


def test_entry_to_json_renders_a_gripper_slip_event():
    shape, _ = _bodies()
    slip = GripperSlipEvent(tracked_object=shape)
    entry = FeedEntry(shape_name="cube", event=slip)

    assert _entry_to_json(entry) == {
        "shape": "cube",
        "event_type": "GripperSlipEvent",
        "with_object": None,
        "timestamp": slip.timestamp.isoformat(),
    }
