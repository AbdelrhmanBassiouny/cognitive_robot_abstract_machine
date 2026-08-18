// Unit tests for panels/event_timeline/panel.js (node:test).
//
// panel.js is loaded with its free variables bound as explicit function parameters
// rather than through global stubs, the same way test_graph_panel.js loads the graph
// panel — the file reaches no DOM beyond the `root` it is handed. The clock and the
// timers are bound too, so time passes exactly when a test says it does instead of
// while the test waits.
//
// The zone is fixed because the summary a pointed-at mark shows carries a time of day.
'use strict';

process.env.TZ = 'UTC';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');
const SOURCE = fs.readFileSync(path.join(WEB, 'panels/event_timeline/panel.js'), 'utf8');

function loadCore(file, name) {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, file), 'utf8'))(scope);
  return scope[name];
}

const ResponseUtil = loadCore('core/response.js', 'ResponseUtil');
const TimelineLayout = loadCore('core/timeline_layout.js', 'TimelineLayout');
const EventSummary = loadCore('core/event_summary.js', 'EventSummary');

const SPAN_SECONDS = 60;
const POLL_MILLISECONDS = 1000;
const REDRAW_MILLISECONDS = 200;
const FULL_WIDTH = 100;

function flush() {
  return new Promise(function (resolve) { setTimeout(resolve, 0); });
}

// %% stubs of the interfaces panel.js reads
function makeElement() {
  const element = {
    tagName: 'div',
    children: [],
    dataset: {},
    className: '',
    textContent: '',
    title: '',
    style: {},
    listeners: {},
    appendChild(child) { this.children.push(child); return child; },
    addEventListener(name, callback) {
      (this.listeners[name] = this.listeners[name] || []).push(callback);
    },
    fire(name) { (this.listeners[name] || []).forEach(function (callback) { callback(); }); },
  };
  Object.defineProperty(element, 'innerHTML', {
    get() { return this._innerHTML || ''; },
    set(value) { this._innerHTML = value; this.children = []; },
  });
  return element;
}

function makeRoot() {
  const byId = {
    '#timeline-title': makeElement(),
    '#timeline-plot': makeElement(),
    '#timeline-empty': makeElement(),
    '#timeline-summary': makeElement(),
  };
  return {
    innerHTML: '',
    querySelector(selector) { return byId[selector]; },
    control(selector) { return byId[selector]; },
  };
}

function makeBus() {
  const handlers = {};
  return {
    on(event, callback) { (handlers[event] = handlers[event] || []).push(callback); },
    emit(event, payload) {
      (handlers[event] || []).forEach(function (callback) { callback(payload); });
    },
  };
}

// A clock the test winds forward by hand, and timers that only fire when told to —
// each on its own interval, so the poll and the redraw can be fired apart.
function makeSchedule(startSeconds) {
  let millis = startSeconds * 1000;
  const running = new Map();
  let nextHandle = 1;
  return {
    Date: { now() { return millis; } },
    setInterval(callback, everyMillis) {
      const handle = nextHandle++;
      running.set(handle, { callback: callback, every: everyMillis });
      return handle;
    },
    clearInterval(handle) { running.delete(handle); },
    running() { return running.size; },
    advance(seconds) { millis += seconds * 1000; },
    fire(everyMillis) {
      Array.from(running.values()).forEach(function (timer) {
        if (timer.every === everyMillis) timer.callback();
      });
    },
    fireAll() { Array.from(running.values()).forEach(function (timer) { timer.callback(); }); },
  };
}

function makeFetch(answers, requested) {
  return async function fetch(url) {
    if (requested) requested.push(url);
    const answer = answers[url];
    if (!answer) throw new Error('unexpected fetch: ' + url);
    const body = typeof answer === 'function' ? answer() : answer;
    return { ok: true, status: 200, json: async function () { return body; } };
  };
}

const BRIDGE = 'http://bridge';
const EVENTS_URL = BRIDGE + '/events';

function loadPanel(answers, schedule) {
  let factory = null;
  const requested = [];
  const Panels = { define(id, built) { factory = built; } };
  new Function(
    'Panels', 'fetch', 'ResponseUtil', 'TimelineLayout', 'EventSummary', 'document',
    'setInterval', 'clearInterval', 'Date', SOURCE
  )(
    Panels, makeFetch(answers, requested), ResponseUtil, TimelineLayout, EventSummary,
    { createElement: makeElement }, schedule.setInterval, schedule.clearInterval,
    schedule.Date
  );
  return { factory: factory, requested: requested };
}

// 2026-08-13 09:05:07 UTC — when every event in these tests was noticed.
const DETECTED_AT = Date.UTC(2026, 7, 13, 9, 5, 7) / 1000;

function detected(fields) {
  return Object.assign(
    {
      kind: 'PickUpEvent',
      detected_at: DETECTED_AT,
      seconds_into_run: 0,
      participants: ['square_shape'],
    },
    fields
  );
}

// A run the test moves and stops by hand, as the bridge reports it to the timeline.
function makeRun(events) {
  return {
    events: events,
    elapsed: 0,
    running: true,
    reaches(seconds) { this.elapsed = seconds; },
    stop() { this.running = false; },
    start() { this.running = true; },
    payload() {
      return {
        ok: true,
        title: 'sort',
        clock: { elapsed: this.elapsed, running: this.running },
        events: this.events,
      };
    },
  };
}

function elementsOf(plot, className) {
  return plot.children.filter(function (child) {
    return child.className.indexOf(className) >= 0;
  });
}

function shownOnly(elements) {
  return elements.filter(function (element) { return element.style.display !== 'none'; });
}

function marksIn(plot) { return shownOnly(elementsOf(plot, 'timeline-mark')); }
function lanesIn(plot) { return shownOnly(elementsOf(plot, 'timeline-lane')); }
function nowBarIn(plot) { return elementsOf(plot, 'timeline-now')[0]; }

function linesOf(summary) {
  return summary.children.map(function (line) { return line.textContent; });
}

// Where the now-bar sits, in the percentages the panel positions everything in.
function barPosition(plot) {
  return parseFloat(nowBarIn(plot).style.left);
}

// Mount the panel already attached to a bridge reporting `run`.
async function attachedPanel(run, startSeconds) {
  const schedule = makeSchedule(startSeconds === undefined ? 1000 : startSeconds);
  const panel = loadPanel({ [EVENTS_URL]: function () { return run.payload(); } }, schedule);
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  bus.emit('live:changed', { on: true, url: BRIDGE });
  await flush();
  return {
    panel, root, bus, instance, schedule, run,
    plot: root.control('#timeline-plot'),
    summary: root.control('#timeline-summary'),
  };
}

// %% only polls a demo it is attached to
test('nothing is fetched before the viewer attaches to a demo', async function () {
  const schedule = makeSchedule(1000);
  const panel = loadPanel({}, schedule);
  const root = makeRoot();
  const instance = panel.factory(root, makeBus());
  try {
    await flush();
    assert.deepStrictEqual(panel.requested, []);
    assert.strictEqual(schedule.running(), 0);
  } finally {
    instance.destroy();
  }
});

test('an unattached panel says the timeline fills in once a demo runs', async function () {
  const schedule = makeSchedule(1000);
  const panel = loadPanel({}, schedule);
  const root = makeRoot();
  const instance = panel.factory(root, makeBus());
  try {
    await flush();
    const empty = root.control('#timeline-empty');
    assert.strictEqual(empty.style.display, '');
    assert.ok(empty.textContent.length > 0);
  } finally {
    instance.destroy();
  }
});

test('attaching polls the bridge the viewer attached to', async function () {
  const { panel, instance } = await attachedPanel(makeRun([]));
  try {
    assert.deepStrictEqual(panel.requested, [EVENTS_URL]);
  } finally {
    instance.destroy();
  }
});

test('detaching stops every timer the attach started', async function () {
  const { bus, schedule, instance } = await attachedPanel(makeRun([]));
  try {
    assert.ok(schedule.running() > 0);
    bus.emit('live:changed', { on: false, url: '' });
    assert.strictEqual(schedule.running(), 0);
  } finally {
    instance.destroy();
  }
});

test('destroying the panel stops every timer too', async function () {
  const { schedule, instance } = await attachedPanel(makeRun([]));
  instance.destroy();
  assert.strictEqual(schedule.running(), 0);
});

test('detaching goes back to saying no demo is attached', async function () {
  const { bus, root, plot, instance } = await attachedPanel(makeRun([detected({})]));
  try {
    bus.emit('live:changed', { on: false, url: '' });
    assert.strictEqual(root.control('#timeline-empty').style.display, '');
    assert.deepStrictEqual(marksIn(plot), []);
  } finally {
    instance.destroy();
  }
});

// %% what it draws
test('an attached demo that has detected nothing says so', async function () {
  const { root, plot, instance } = await attachedPanel(makeRun([]));
  try {
    assert.strictEqual(root.control('#timeline-empty').style.display, '');
    assert.deepStrictEqual(marksIn(plot), []);
  } finally {
    instance.destroy();
  }
});

test('a demo offering no event source reports why, in its own words', async function () {
  const schedule = makeSchedule(1000);
  const panel = loadPanel(
    { [EVENTS_URL]: { ok: false, error: 'no event source is registered', events: [] } },
    schedule
  );
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    bus.emit('live:changed', { on: true, url: BRIDGE });
    await flush();
    assert.strictEqual(
      root.control('#timeline-empty').textContent, 'no event source is registered');
  } finally {
    instance.destroy();
  }
});

test('every detected event inside the window gets a mark', async function () {
  const { root, plot, instance } = await attachedPanel(makeRun([
    detected({ seconds_into_run: 0 }),
    detected({ seconds_into_run: 10 }),
    detected({ seconds_into_run: 20 }),
  ]));
  try {
    assert.strictEqual(marksIn(plot).length, 3);
    assert.strictEqual(root.control('#timeline-empty').style.display, 'none');
  } finally {
    instance.destroy();
  }
});

test('each kind of event gets one lane, however often it is detected', async function () {
  const { plot, instance } = await attachedPanel(makeRun([
    detected({ kind: 'PickUpEvent', seconds_into_run: 0 }),
    detected({ kind: 'ContactEvent', seconds_into_run: 5 }),
    detected({ kind: 'PickUpEvent', seconds_into_run: 10 }),
  ]));
  try {
    assert.deepStrictEqual(
      lanesIn(plot).map(function (lane) { return lane.textContent; }),
      ['PickUpEvent', 'ContactEvent']
    );
  } finally {
    instance.destroy();
  }
});

test('an event older than the window on screen is left off it', async function () {
  const { plot, run, schedule, instance } = await attachedPanel(makeRun([
    detected({ seconds_into_run: 0 }),
    detected({ seconds_into_run: 150 }),
  ]));
  try {
    run.reaches(200);
    schedule.fire(POLL_MILLISECONDS);
    await flush();
    const shown = marksIn(plot);
    assert.strictEqual(shown.length, 1);
    assert.strictEqual(
      parseFloat(shown[0].style.left),
      TimelineLayout.horizontalPosition({ start: 140, end: 200 }, 150, FULL_WIDTH)
    );
  } finally {
    instance.destroy();
  }
});

// %% the bar follows the run, not the wall clock
test('the now-bar reaches wherever the run says it has got to', async function () {
  const { plot, run, schedule, instance } = await attachedPanel(makeRun([]));
  try {
    run.reaches(30);
    schedule.fire(POLL_MILLISECONDS);
    await flush();
    assert.strictEqual(
      barPosition(plot),
      TimelineLayout.horizontalPosition({ start: 0, end: SPAN_SECONDS }, 30, FULL_WIDTH)
    );
  } finally {
    instance.destroy();
  }
});

test('the now-bar glides on between the answers of a run that is going', async function () {
  const { plot, run, schedule, instance } = await attachedPanel(makeRun([]));
  try {
    run.reaches(5);
    schedule.fire(POLL_MILLISECONDS);
    await flush();

    schedule.advance(10);
    schedule.fire(REDRAW_MILLISECONDS);

    assert.strictEqual(
      barPosition(plot),
      TimelineLayout.horizontalPosition({ start: 0, end: SPAN_SECONDS }, 15, FULL_WIDTH)
    );
  } finally {
    instance.destroy();
  }
});

test('the now-bar stands still for as long as the run is paused', async function () {
  const { plot, run, schedule, instance } = await attachedPanel(makeRun([]));
  try {
    run.reaches(20);
    run.stop();
    schedule.fire(POLL_MILLISECONDS);
    await flush();
    const paused = barPosition(plot);

    schedule.advance(45);
    schedule.fireAll();
    await flush();

    assert.strictEqual(barPosition(plot), paused);
  } finally {
    instance.destroy();
  }
});

test('a resumed run carries the now-bar on from where the pause stopped it', async function () {
  const { plot, run, schedule, instance } = await attachedPanel(makeRun([]));
  try {
    run.reaches(20);
    run.stop();
    schedule.fire(POLL_MILLISECONDS);
    await flush();
    schedule.advance(45);

    run.start();
    schedule.fire(POLL_MILLISECONDS);
    await flush();
    schedule.advance(4);
    schedule.fire(REDRAW_MILLISECONDS);

    assert.strictEqual(
      barPosition(plot),
      TimelineLayout.horizontalPosition({ start: 0, end: SPAN_SECONDS }, 24, FULL_WIDTH)
    );
  } finally {
    instance.destroy();
  }
});

test('a restarted run takes the now-bar back to the start of the panel', async function () {
  const { plot, run, schedule, instance } = await attachedPanel(makeRun([
    detected({ seconds_into_run: 30 }),
  ]));
  try {
    run.reaches(40);
    schedule.fire(POLL_MILLISECONDS);
    await flush();

    run.events = [];
    run.reaches(0);
    schedule.fire(POLL_MILLISECONDS);
    await flush();

    assert.strictEqual(barPosition(plot), 0);
    assert.deepStrictEqual(marksIn(plot), []);
  } finally {
    instance.destroy();
  }
});

// %% what a pointed-at mark says
test('pointing at a mark says what was detected, to what, and when', async function () {
  const event = detected({
    kind: 'InsertionEvent',
    seconds_into_run: 83.44,
    participants: ['square_shape', 'square_hole'],
  });
  const { plot, summary, run, schedule, instance } = await attachedPanel(makeRun([event]));
  try {
    run.reaches(90);
    schedule.fire(POLL_MILLISECONDS);
    await flush();
    marksIn(plot)[0].fire('mouseenter');

    assert.strictEqual(summary.style.display, '');
    assert.deepStrictEqual(linesOf(summary), [
      'InsertionEvent',
      'square_shape, square_hole',
      EventSummary.of(event).time,
    ]);
  } finally {
    instance.destroy();
  }
});

test('an event involving no objects is summarised without an empty line', async function () {
  const { plot, summary, instance } = await attachedPanel(
    makeRun([detected({ participants: [] })]));
  try {
    marksIn(plot)[0].fire('mouseenter');

    assert.strictEqual(linesOf(summary).length, 2);
  } finally {
    instance.destroy();
  }
});

test('the summary is anchored at the mark it describes', async function () {
  const { plot, summary, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 30 })]));
  try {
    const mark = marksIn(plot)[0];
    mark.fire('mouseenter');

    assert.strictEqual(summary.style.left, mark.style.left);
    assert.strictEqual(summary.style.top, mark.style.top);
  } finally {
    instance.destroy();
  }
});

test('the summary is placed the way the layout says it has to be', async function () {
  const { plot, summary, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 55 })]));
  try {
    const mark = marksIn(plot)[0];
    mark.fire('mouseenter');
    const placement = TimelineLayout.summaryPlacement(
      parseFloat(mark.style.left), parseFloat(mark.style.top), 100, 100);

    assert.ok(summary.className.indexOf(placement.horizontal) >= 0, summary.className);
    assert.ok(summary.className.indexOf(placement.vertical) >= 0, summary.className);
  } finally {
    instance.destroy();
  }
});

test('a summary is nowhere to be seen until a mark is pointed at', async function () {
  const { summary, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 5 })]));
  try {
    assert.strictEqual(summary.style.display, 'none');
  } finally {
    instance.destroy();
  }
});

test('leaving a mark takes its summary away again', async function () {
  const { plot, summary, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 5 })]));
  try {
    marksIn(plot)[0].fire('mouseenter');
    marksIn(plot)[0].fire('mouseleave');

    assert.strictEqual(summary.style.display, 'none');
  } finally {
    instance.destroy();
  }
});

test('a mark keeps its summary while the timeline is redrawn under it', async function () {
  const { plot, summary, run, schedule, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 5 })]));
  try {
    marksIn(plot)[0].fire('mouseenter');

    run.reaches(20);
    schedule.fireAll();
    await flush();

    assert.strictEqual(summary.style.display, '');
    assert.strictEqual(summary.style.left, marksIn(plot)[0].style.left);
  } finally {
    instance.destroy();
  }
});

test('a summarised mark that scrolls off the panel takes its summary with it', async function () {
  const { plot, summary, run, schedule, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 5 })]));
  try {
    marksIn(plot)[0].fire('mouseenter');

    run.reaches(200);
    schedule.fire(POLL_MILLISECONDS);
    await flush();

    assert.strictEqual(summary.style.display, 'none');
  } finally {
    instance.destroy();
  }
});

test('a restart takes away the summary of an event the new run has not detected', async function () {
  const { plot, summary, run, schedule, instance } = await attachedPanel(
    makeRun([detected({ seconds_into_run: 5 })]));
  try {
    marksIn(plot)[0].fire('mouseenter');

    run.events = [];
    run.reaches(0);
    schedule.fire(POLL_MILLISECONDS);
    await flush();

    assert.strictEqual(summary.style.display, 'none');
  } finally {
    instance.destroy();
  }
});

test('a bridge that stops answering leaves the last drawing standing', async function () {
  const run = makeRun([detected({ seconds_into_run: 0 })]);
  const schedule = makeSchedule(1000);
  const panel = loadPanel({ [EVENTS_URL]: function () { return run.payload(); } }, schedule);
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    bus.emit('live:changed', { on: true, url: BRIDGE });
    await flush();
    const plot = root.control('#timeline-plot');
    assert.strictEqual(marksIn(plot).length, 1);

    bus.emit('live:changed', { on: true, url: 'http://gone' });
    await flush();

    assert.strictEqual(marksIn(plot).length, 1);
  } finally {
    instance.destroy();
  }
});
