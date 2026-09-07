"""
Tests for what a running demo tells the viewer it has detected.

The bridge only relays events: what counts as one belongs to the demo that registered
itself, so these use a stand-in that reports a fixed list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from typing_extensions import List

from cramera.live.bridge import Bridge
from cramera.live.events import (
    DetectedEvent,
    LiveEventSource,
    NoEventSourceRegistered,
)
from cramera.live.run_clock import RunClockReading


# %% a stand-in demo
@dataclass
class ReportingEventSource(LiveEventSource):
    """
    A stand-in demo that reports whichever events it was built with.
    """

    detected: List[DetectedEvent] = field(default_factory=list)
    """
    The events this stand-in reports, oldest first.
    """

    reading: RunClockReading = RunClockReading(elapsed=0.0, running=True)
    """
    Where this stand-in says its run has got to.
    """

    def title(self) -> str:
        """
        What the viewer names the run these events came from.
        """
        return "record demo"

    def events(self) -> List[DetectedEvent]:
        """
        Everything this stand-in has to report.
        """
        return self.detected

    def clock_reading(self) -> RunClockReading:
        """
        Where this stand-in says its run has got to.
        """
        return self.reading


def event_at(second: int, kind: str = "PickUpEvent") -> DetectedEvent:
    """
    One event, at a fixed instant offset by whole seconds, for a readable expectation.

    :param second: Seconds past the epoch the event is stamped with, and how far into
        the run it was noticed.
    :param kind: What kind of event to build.
    """
    return DetectedEvent(
        kind=kind,
        detected_at=datetime.fromtimestamp(second, tz=timezone.utc),
        seconds_into_run=float(second),
        participants=["square_shape"],
    )


# %% the wire shape
class TestDetectedEventPayload:
    def test_the_instant_is_sent_as_seconds_since_the_epoch(self):
        """
        Seconds are the unit the timeline's own arithmetic works in.
        """
        event = event_at(90)

        assert event.to_payload()["detected_at"] == 90.0

    def test_the_instant_is_also_sent_as_the_point_of_the_run_it_fell_at(self):
        """
        A run that pauses stands still where the wall clock does not, so the timeline
        plots the run's own axis rather than the wall clock's.
        """
        assert event_at(90).to_payload()["seconds_into_run"] == 90.0

    def test_the_payload_carries_the_kind_and_every_participant(self):
        event = DetectedEvent(
            kind="InsertionEvent",
            detected_at=datetime.fromtimestamp(5, tz=timezone.utc),
            seconds_into_run=5.0,
            participants=["square_shape", "square_hole"],
        )

        payload = event.to_payload()

        assert payload["kind"] == "InsertionEvent"
        assert payload["participants"] == ["square_shape", "square_hole"]

    def test_the_payload_names_exactly_the_events_own_fields(self):
        """
        A key the viewer reads that no field produces would drift silently.
        """
        assert set(event_at(0).to_payload()) == {
            "kind",
            "detected_at",
            "seconds_into_run",
            "participants",
        }


# %% registration on the bridge
class TestEventSourceRegistration:
    def test_a_fresh_bridge_has_no_event_source(self):
        bridge = Bridge()

        with pytest.raises(NoEventSourceRegistered):
            bridge.event_payload()

    def test_the_payload_carries_the_registered_sources_title(self):
        bridge = Bridge()
        bridge.register_event_source(ReportingEventSource())

        assert bridge.event_payload()["title"] == "record demo"

    def test_the_payload_carries_every_event_the_source_reports(self):
        source = ReportingEventSource(detected=[event_at(1), event_at(2)])
        bridge = Bridge()
        bridge.register_event_source(source)

        assert bridge.event_payload()["events"] == [
            event.to_payload() for event in source.detected
        ]

    def test_the_payload_follows_the_source_as_it_detects_more(self):
        """
        The timeline polls one bridge over and over; a snapshot taken at registration
        would leave it frozen at whatever had happened by then.
        """
        source = ReportingEventSource(detected=[event_at(1)])
        bridge = Bridge()
        bridge.register_event_source(source)

        source.detected.append(event_at(2))

        assert len(bridge.event_payload()["events"]) == 2


class TestTheRunsClockOnTheWire:
    def test_the_payload_carries_where_the_run_has_got_to(self):
        """
        Without it the timeline would point at the wall clock, which keeps moving while
        the run it plots stands still.
        """
        reading = RunClockReading(elapsed=12.5, running=False)
        bridge = Bridge()
        bridge.register_event_source(ReportingEventSource(reading=reading))

        assert bridge.event_payload()["clock"] == reading.to_payload()

    def test_the_clock_follows_the_source_as_the_run_carries_on(self):
        source = ReportingEventSource()
        bridge = Bridge()
        bridge.register_event_source(source)

        source.reading = RunClockReading(elapsed=30.0, running=True)

        assert bridge.event_payload()["clock"]["elapsed"] == 30.0


class TestEventSourceInTheBridgeStatus:
    def test_a_fresh_bridge_reports_no_event_source(self):
        assert Bridge().status()["events"] is False

    def test_a_registered_source_is_reported(self):
        bridge = Bridge()
        bridge.register_event_source(ReportingEventSource())

        assert bridge.status()["events"] is True
