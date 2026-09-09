"""
A small local Flask app showing SegMind's detected events live, as they happen, in a
browser tab -- for watching a
:mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco` run without
having to read console log lines.

:class:`EventFeed` is the only piece a caller needs to wire in: publish to it (typically
via ``segmind_context.logger.add_callback(DetectionEvent, feed.publish)``, since
:class:`~segmind.event_logger.EventLogger` already calls back into every registered
callback synchronously as it logs each event -- see its own
:meth:`~segmind.event_logger.EventLogger.log_event`) and pass it to :func:`run_dashboard`.
Everything past that (the page, the live stream, serializing an event for the browser)
is this module's own concern.

Run standalone against nothing but example events with::

    python -m experiments.tracy_experiments.montessori.event_dashboard
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass, field

from flask import Flask, Response, jsonify, render_template_string, stream_with_context
from typing_extensions import List, Optional

from segmind.datastructures.events import DetectionEvent
from semantic_digital_twin.world_description.world_entity import Body, Region

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000

HEARTBEAT_INTERVAL_SECONDS = 15.0
"""
How long a browser's SSE connection may sit idle before this module sends a comment-only
keepalive line, so a quiet stretch between events doesn't read as a dropped connection.
"""

# %% event feed


@dataclass
class FeedEntry:
    """
    One published event, labelled with which shape it was detected for.
    """

    shape_name: str
    """
    The name of the shape :attr:`event` was detected for.
    """

    event: DetectionEvent
    """
    The event itself.
    """


@dataclass
class EventFeed:
    """
    Thread-safe hub that fans a growing sequence of :class:`FeedEntry` out to any number
    of live subscribers (see :meth:`subscribe`), while also keeping the full history so
    a subscriber that joins late still gets everything published before it connected.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _entries: List[FeedEntry] = field(default_factory=list, init=False)
    _subscribers: List[queue.Queue] = field(default_factory=list, init=False)

    def publish(self, shape_name: str, event: DetectionEvent) -> None:
        """
        Record a newly detected event and hand it to every current subscriber.

        :param shape_name: The name of the shape the event was detected for.
        :param event: The event itself.
        """
        entry = FeedEntry(shape_name=shape_name, event=event)
        with self._lock:
            self._entries.append(entry)
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(entry)

    def snapshot(self) -> List[FeedEntry]:
        """
        :return: Every entry published so far, oldest first.
        """
        with self._lock:
            return list(self._entries)

    def subscribe(self) -> queue.Queue:
        """
        Start a new live subscription.

        :return: A queue that already holds every entry published so far, and will keep
            receiving new ones until :meth:`unsubscribe` is called with it.
        """
        subscriber: queue.Queue = queue.Queue()
        with self._lock:
            for entry in self._entries:
                subscriber.put(entry)
            self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        """
        End a subscription started by :meth:`subscribe`.

        :param subscriber: The queue :meth:`subscribe` returned.
        """
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)


def _named(entity: Optional[Body | Region]) -> Optional[str]:
    """
    :param entity: A body or region, or ``None``.
    :return: Its own name, or ``None`` if ``entity`` is ``None``.
    """
    return str(entity.name) if entity is not None else None


def _entry_to_json(entry: FeedEntry) -> dict:
    """
    Reduce ``entry`` to the small set of JSON-safe fields the dashboard page displays --
    an event's other fields (bounding boxes, full poses, ...) carry types the browser
    has no use for.

    :param entry: The entry to serialize.
    """
    event = entry.event
    return {
        "shape": entry.shape_name,
        "event_type": type(event).__name__,
        "with_object": _named(getattr(event, "with_object", None)),
        "timestamp": event.timestamp.isoformat(),
    }


# %% flask app


_INDEX_HTML = """
<!doctype html>
<title>SegMind Live Events</title>
<style>
  :root { color-scheme: light dark; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 900px; margin: 2rem auto; padding: 0 1rem;
  }
  h1 { font-size: 1.25rem; }
  #status { color: #888; font-size: 0.9rem; margin-bottom: 1rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #8884; }
  tr:first-child td { font-weight: 600; }
  .event-type { font-family: ui-monospace, monospace; }
</style>
<h1>SegMind Live Events</h1>
<div id="status">connecting...</div>
<table>
  <thead><tr><th>Time</th><th>Shape</th><th>Event</th><th>With</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<script>
  const rows = document.getElementById("rows");
  const status = document.getElementById("status");

  function prependRow(entry) {
    const row = document.createElement("tr");
    const time = new Date(entry.timestamp).toLocaleTimeString();
    row.innerHTML =
      "<td>" + time + "</td>" +
      "<td>" + entry.shape + "</td>" +
      "<td class=\\"event-type\\">" + entry.event_type + "</td>" +
      "<td>" + (entry.with_object ?? "") + "</td>";
    rows.insertBefore(row, rows.firstChild);
  }

  const source = new EventSource("/events/stream");
  source.onopen = () => { status.textContent = "connected"; };
  source.onerror = () => { status.textContent = "disconnected -- retrying..."; };
  source.onmessage = (message) => { prependRow(JSON.parse(message.data)); };
</script>
"""


def create_app(feed: EventFeed) -> Flask:
    """
    Build the Flask app serving ``feed``'s events.

    :param feed: The feed to serve.
    """
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(_INDEX_HTML)

    @app.route("/events")
    def events_snapshot():
        return jsonify([_entry_to_json(entry) for entry in feed.snapshot()])

    @app.route("/events/stream")
    def events_stream():
        subscriber = feed.subscribe()

        def generate():
            try:
                while True:
                    try:
                        entry = subscriber.get(timeout=HEARTBEAT_INTERVAL_SECONDS)
                    except queue.Empty:
                        yield ": heartbeat\n\n"
                        continue
                    yield f"data: {json.dumps(_entry_to_json(entry))}\n\n"
            finally:
                feed.unsubscribe(subscriber)

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    return app


def run_dashboard(
    feed: EventFeed, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> threading.Thread:
    """
    Start serving ``feed``'s events on a background thread.

    ``threaded=True`` is required, not just a performance nicety: Flask's own
    development server otherwise handles one request at a time, and an open
    ``/events/stream`` connection would then block every other request (including the
    page itself) for as long as a browser tab stays open.

    :param feed: The feed to serve.
    :param host: Interface to bind to.
    :param port: Port to bind to.
    :return: The started daemon thread running the server.
    """
    app = create_app(feed)
    thread = threading.Thread(
        target=app.run,
        kwargs={
            "host": host,
            "port": port,
            "debug": False,
            "use_reloader": False,
            "threaded": True,
        },
        daemon=True,
        name="segmind-event-dashboard",
    )
    thread.start()
    logger.info("SegMind live event dashboard: http://%s:%d", host, port)
    return thread


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from segmind.datastructures.events import GraspEvent, PickUpEvent
    from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

    # Bare, world-unattached bodies: fine for GraspEvent/PickUpEvent (only read .name),
    # but not for e.g. ContactEvent, whose __post_init__ needs a real mesh and pose.
    demo_feed = EventFeed()
    run_dashboard(demo_feed)

    demo_shape = Body(name=PrefixedName("example_shape"))
    demo_tool_frame = Body(name=PrefixedName("example_tool_frame"))
    while True:
        demo_feed.publish(
            "example_shape",
            GraspEvent(tracked_object=demo_shape, with_object=demo_tool_frame),
        )
        time.sleep(2)
        demo_feed.publish("example_shape", PickUpEvent(tracked_object=demo_shape))
        time.sleep(2)
