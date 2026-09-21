/* ============================================================================
 * panels/event_timeline/panel.js — what the running demo has noticed, on a
 * timeline that moves exactly as far as the run does.
 *
 * One lane per kind of event, a mark per detection, and a vertical bar at the
 * point the run has reached sweeping left to right. The lanes are learnt from
 * what arrives: the viewer knows nothing of a demo's own catalogue of events.
 *
 * The axis is the run's own clock, sent along with the detections, so pausing
 * the run stops the bar and restarting it takes the timeline back to the start.
 *
 * Everything is drawn in percentages of the plot rather than pixels, so the
 * panel needs no measurement of itself and follows a resize on its own. The
 * elements are kept and moved rather than rebuilt, so the pointer never loses
 * the mark it is resting on.
 *
 * Bus events:
 *   listens  live:changed {on, url}   start/stop polling the bridge
 *
 * Positions come from core/timeline_layout.js and the wording of a pointed-at
 * mark from core/event_summary.js, which own the arithmetic and the phrasing.
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

  const RUN_START = 0;
  /* Where the axis begins: the run's clock counts up from its own start. */

  const STOPPED_CLOCK = { elapsed: 0, running: false };
  /* What a run that has not said where it is counts as: nowhere, and not moving. */

  const NOTHING_SUMMARISED = -1;
  /* No mark is being pointed at. */

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
    '    <div id="timeline-summary" class="timeline-summary"></div>' +
    '    <div id="timeline-empty" class="timeline-empty"></div>' +
    '  </div>' +
    '</div>';

  const plot = root.querySelector('#timeline-plot');
  const titleEl = root.querySelector('#timeline-title');
  const emptyEl = root.querySelector('#timeline-empty');
  const summaryEl = root.querySelector('#timeline-summary');

  let attachedUrl = '';
  let events = [];
  let unavailable = null;       // what the demo said instead of a list of events
  let clock = STOPPED_CLOCK;    // where the run had got to when it last answered
  let clockReadAt = 0;          // when that answer arrived, in seconds
  let pollTimer = null;
  let redrawTimer = null;

  let laneElements = [];        // one per lane ever needed, surplus ones hidden
  let markElements = [];        // one per event ever seen, surplus ones hidden
  let nowBarElement = null;
  let summarisedIndex = NOTHING_SUMMARISED;

  function nowInSeconds() {
    return Date.now() / 1000;
  }

  // %% the run's own clock
  function readClock(reading) {
    clock = reading || STOPPED_CLOCK;
    clockReadAt = nowInSeconds();
  }

  //: the bridge only answers once a second, so the reading is carried forward here
  //: in between — and only while it is running, which is what holds the now-bar
  //: still for as long as the run is paused
  function elapsedNow() {
    if (!clock.running) return clock.elapsed;
    return clock.elapsed + (nowInSeconds() - clockReadAt);
  }

  // %% drawing
  function newElement(className) {
    const element = document.createElement('div');
    element.className = className;
    return element;
  }

  function place(element, left, top) {
    element.style.left = left + '%';
    element.style.top = top + '%';
  }

  function show(element, visible) {
    element.style.display = visible ? '' : 'none';
  }

  function newMark(index) {
    const mark = newElement('timeline-mark');
    mark.addEventListener('mouseenter', function () { summarise(index); });
    mark.addEventListener('mouseleave', function () { forgetSummary(index); });
    return mark;
  }

  //: an element is grown into rather than rebuilt, so an event keeps the same mark
  //: for as long as it is on screen and the pointer keeps whatever it is resting on
  function laneAt(index) {
    while (laneElements.length <= index) {
      laneElements.push(plot.appendChild(newElement('timeline-lane')));
    }
    return laneElements[index];
  }

  function markAt(index) {
    while (markElements.length <= index) {
      markElements.push(plot.appendChild(newMark(markElements.length)));
    }
    return markElements[index];
  }

  function hideFrom(elements, first) {
    for (let index = first; index < elements.length; index++) show(elements[index], false);
  }

  function drawLanes(kinds) {
    kinds.forEach(function (kind, index) {
      const lane = laneAt(index);
      lane.textContent = kind;
      place(lane, 0, TimelineLayout.laneCentre(index, kinds.length, FULL_HEIGHT));
      show(lane, true);
    });
    hideFrom(laneElements, kinds.length);
  }

  function drawMarks(bounds, kinds) {
    events.forEach(function (event, index) {
      const mark = markAt(index);
      const inside = TimelineLayout.isInside(bounds, event.seconds_into_run);
      show(mark, inside);
      if (!inside) return forgetSummary(index);
      place(
        mark,
        TimelineLayout.horizontalPosition(bounds, event.seconds_into_run, FULL_WIDTH),
        TimelineLayout.laneCentre(kinds.indexOf(event.kind), kinds.length, FULL_HEIGHT)
      );
      if (summarisedIndex === index) positionSummary(index);
    });
    hideFrom(markElements, events.length);
    if (summarisedIndex >= events.length) hideSummary();
  }

  function drawNowBar(bounds, elapsed) {
    if (!nowBarElement) nowBarElement = plot.appendChild(newElement('timeline-now'));
    nowBarElement.style.left =
      TimelineLayout.horizontalPosition(bounds, elapsed, FULL_WIDTH) + '%';
    show(nowBarElement, true);
  }

  function hideThePlot() {
    hideFrom(laneElements, 0);
    hideFrom(markElements, 0);
    if (nowBarElement) show(nowBarElement, false);
    hideSummary();
  }

  function sayNothingToShow(message) {
    emptyEl.textContent = message;
    emptyEl.style.display = '';
  }

  function draw() {
    if (!attachedUrl) {
      hideThePlot();
      return sayNothingToShow(NOT_ATTACHED);
    }

    const elapsed = elapsedNow();
    const bounds = TimelineLayout.boundsFor(RUN_START, elapsed, SPAN_SECONDS);
    const kinds = TimelineLayout.kindsOf(events);
    drawLanes(kinds);
    drawMarks(bounds, kinds);
    drawNowBar(bounds, elapsed);

    if (unavailable) return sayNothingToShow(unavailable);
    if (!events.length) return sayNothingToShow(NOTHING_DETECTED);
    emptyEl.style.display = 'none';
  }

  // %% what a pointed-at mark says
  function summaryLine(className, text) {
    const line = newElement(className);
    line.textContent = text;
    return line;
  }

  function summarise(index) {
    const event = events[index];
    if (!event) return;
    const summary = EventSummary.of(event);
    summaryEl.innerHTML = '';
    summaryEl.appendChild(summaryLine('timeline-summary-kind', summary.kind));
    if (summary.objects) {
      summaryEl.appendChild(summaryLine('timeline-summary-objects', summary.objects));
    }
    summaryEl.appendChild(summaryLine('timeline-summary-time', summary.time));
    summarisedIndex = index;
    positionSummary(index);
    summaryEl.style.display = '';
  }

  function positionSummary(index) {
    const mark = markElements[index];
    const placement = TimelineLayout.summaryPlacement(
      parseFloat(mark.style.left), parseFloat(mark.style.top), FULL_WIDTH, FULL_HEIGHT);
    summaryEl.className =
      ['timeline-summary', placement.horizontal, placement.vertical].join(' ');
    summaryEl.style.left = mark.style.left;
    summaryEl.style.top = mark.style.top;
  }

  function forgetSummary(index) {
    if (summarisedIndex === index) hideSummary();
  }

  function hideSummary() {
    summarisedIndex = NOTHING_SUMMARISED;
    summaryEl.style.display = 'none';
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
    readClock(payload.clock);
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
      readClock(null);
      titleEl.textContent = '';
      draw();
      return;
    }
    pollTimer = setInterval(poll, POLL_MILLISECONDS);
    redrawTimer = setInterval(draw, REDRAW_MILLISECONDS);
    poll();
  });

  hideSummary();
  draw();

  return { destroy: stopFollowing };
});
