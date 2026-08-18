/* ============================================================================
 * panels/event_timeline/panel.js — what the running demo has noticed, on a
 * timeline that keeps moving.
 *
 * One lane per kind of event, a mark per detection, and a vertical bar at the
 * current instant sweeping left to right. The lanes are learnt from what
 * arrives: the viewer knows nothing of a demo's own catalogue of events.
 *
 * Everything is drawn in percentages of the plot rather than pixels, so the
 * panel needs no measurement of itself and follows a resize on its own.
 *
 * Bus events:
 *   listens  live:changed {on, url}   start/stop polling the bridge
 *
 * Positions come from core/timeline_layout.js, which owns the arithmetic.
 * ==========================================================================*/
Panels.define('event-timeline', function (root, bus) {
  const SPAN_SECONDS = 60;
  /* How much of the run is on screen at once. Long enough to hold a whole
     insertion attempt, short enough that the marks within one stay apart. */

  const POLL_MILLISECONDS = 1000;
  /* How often the bridge is asked what else it has detected. */

  const REDRAW_MILLISECONDS = 200;
  /* How often the now-bar is moved. Separate from the poll, so the bar glides
     rather than stepping once a second. */

  const FULL_WIDTH = 100;
  const FULL_HEIGHT = 100;
  /* The plot's own extent, in the percentages everything is positioned in. */

  const NOT_ATTACHED = 'Not attached to a running demo — the timeline fills in ' +
    'as soon as one is reachable.';
  const NOTHING_DETECTED = 'Attached, but the demo has not detected anything yet.';

  root.innerHTML =
    '<div class="timeline-wrap">' +
    '  <div class="timeline-head">' +
    '    <span id="timeline-title" class="timeline-title"></span>' +
    '    <span class="timeline-span">last ' + SPAN_SECONDS + ' s</span>' +
    '  </div>' +
    '  <div class="timeline-body">' +
    '    <div id="timeline-plot" class="timeline-plot"></div>' +
    '    <div id="timeline-empty" class="timeline-empty"></div>' +
    '  </div>' +
    '</div>';

  const plot = root.querySelector('#timeline-plot');
  const titleEl = root.querySelector('#timeline-title');
  const emptyEl = root.querySelector('#timeline-empty');

  let attachedUrl = '';
  let attachedAt = 0;           // when this panel started watching, in seconds
  let events = [];
  let unavailable = null;       // what the demo said instead of a list of events
  let pollTimer = null;
  let redrawTimer = null;

  function nowInSeconds() {
    return Date.now() / 1000;
  }

  // %% drawing
  function runStart() {
    return events.length ? Math.min(attachedAt, events[0].detected_at) : attachedAt;
  }

  function place(element, left, top) {
    element.style.left = left + '%';
    element.style.top = top + '%';
    return element;
  }

  function addMark(bounds, event, laneIndex, laneCount) {
    const mark = document.createElement('div');
    mark.className = 'timeline-mark';
    mark.title = event.kind + ' · ' + (event.participants || []).join(' + ');
    plot.appendChild(place(
      mark,
      TimelineLayout.horizontalPosition(bounds, event.detected_at, FULL_WIDTH),
      TimelineLayout.laneCentre(laneIndex, laneCount, FULL_HEIGHT)
    ));
  }

  function addLane(kind, laneIndex, laneCount) {
    const lane = document.createElement('div');
    lane.className = 'timeline-lane';
    lane.textContent = kind;
    plot.appendChild(place(
      lane, 0, TimelineLayout.laneCentre(laneIndex, laneCount, FULL_HEIGHT)));
  }

  function addNowBar(bounds, now) {
    const bar = document.createElement('div');
    bar.className = 'timeline-now';
    bar.style.left = TimelineLayout.horizontalPosition(bounds, now, FULL_WIDTH) + '%';
    plot.appendChild(bar);
  }

  function sayNothingToShow(message) {
    emptyEl.textContent = message;
    emptyEl.style.display = '';
  }

  function draw() {
    plot.innerHTML = '';
    if (!attachedUrl) return sayNothingToShow(NOT_ATTACHED);

    const now = nowInSeconds();
    const bounds = TimelineLayout.boundsFor(runStart(), now, SPAN_SECONDS);
    const kinds = TimelineLayout.kindsOf(events);
    kinds.forEach(function (kind, index) { addLane(kind, index, kinds.length); });
    events.forEach(function (event) {
      if (!TimelineLayout.isInside(bounds, event.detected_at)) return;
      addMark(bounds, event, kinds.indexOf(event.kind), kinds.length);
    });
    addNowBar(bounds, now);

    if (unavailable) return sayNothingToShow(unavailable);
    if (!events.length) return sayNothingToShow(NOTHING_DETECTED);
    emptyEl.style.display = 'none';
  }

  // %% following the bridge
  async function poll() {
    let payload;
    try {
      payload = await fetch(attachedUrl + '/events').then(ResponseUtil.parseJson);
    } catch (err) {
      return;                              // bridge gone — the 3D side handles it
    }
    if (!payload) return;
    unavailable = payload.ok ? null : (payload.error || NOTHING_DETECTED);
    events = payload.events || [];
    titleEl.textContent = payload.title || '';
    draw();
  }

  function stopFollowing() {
    if (pollTimer) clearInterval(pollTimer);
    if (redrawTimer) clearInterval(redrawTimer);
    pollTimer = redrawTimer = null;
  }

  bus.on('live:changed', function (state) {
    stopFollowing();
    attachedUrl = state.on ? (state.url || '') : '';
    if (!attachedUrl) {
      events = [];
      unavailable = null;
      titleEl.textContent = '';
      draw();
      return;
    }
    attachedAt = nowInSeconds();
    pollTimer = setInterval(poll, POLL_MILLISECONDS);
    redrawTimer = setInterval(draw, REDRAW_MILLISECONDS);
    poll();
  });

  draw();

  return { destroy: stopFollowing };
});
