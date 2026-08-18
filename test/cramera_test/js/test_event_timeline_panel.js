// Unit tests for panels/event_timeline/panel.js (node:test).
//
// panel.js is loaded with its free variables bound as explicit function parameters
// rather than through global stubs, the same way test_graph_panel.js loads the graph
// panel — the file reaches no DOM beyond the `root` it is handed. The clock and the
// timers are bound too, so time passes exactly when a test says it does instead of
// while the test waits.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');
const SOURCE = fs.readFileSync(path.join(WEB, 'panels/event_timeline/panel.js'), 'utf8');

function loadResponseUtil() {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, 'core/response.js'), 'utf8'))(scope);
  return scope.ResponseUtil;
}

function loadTimelineLayout() {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, 'core/timeline_layout.js'), 'utf8'))(scope);
  return scope.TimelineLayout;
}

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
    appendChild(child) { this.children.push(child); return child; },
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

// A clock the test winds forward by hand, and timers that only fire when told to.
function makeSchedule(startSeconds) {
  let millis = startSeconds * 1000;
  const running = new Map();
  let nextHandle = 1;
  return {
    Date: { now() { return millis; } },
    setInterval(callback) {
      const handle = nextHandle++;
      running.set(handle, callback);
      return handle;
    },
    clearInterval(handle) { running.delete(handle); },
    running() { return running.size; },
    advance(seconds) { millis += seconds * 1000; },
    fireAll() { Array.from(running.values()).forEach(function (c) { c(); }); },
  };
}

function makeFetch(answers, requested) {
  return async function fetch(url) {
    if (requested) requested.push(url);
    const body = answers[url];
    if (!body) throw new Error('unexpected fetch: ' + url);
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
    'Panels', 'fetch', 'ResponseUtil', 'TimelineLayout', 'document',
    'setInterval', 'clearInterval', 'Date', SOURCE
  )(
    Panels, makeFetch(answers, requested), loadResponseUtil(), loadTimelineLayout(),
    { createElement: makeElement }, schedule.setInterval, schedule.clearInterval,
    schedule.Date
  );
  return { factory: factory, requested: requested };
}

function detectedAt(second, kind) {
  return { kind: kind || 'PickUpEvent', detected_at: second, participants: ['square_shape'] };
}

function marksIn(plot) {
  return plot.children.filter(function (child) {
    return child.className.indexOf('timeline-mark') >= 0;
  });
}

function lanesIn(plot) {
  return plot.children.filter(function (child) {
    return child.className.indexOf('timeline-lane') >= 0;
  });
}

function nowBarIn(plot) {
  return plot.children.find(function (child) {
    return child.className.indexOf('timeline-now') >= 0;
  });
}

// Mount the panel already attached to a bridge answering with `events`.
async function attachedPanel(events, startSeconds) {
  const schedule = makeSchedule(startSeconds === undefined ? 1000 : startSeconds);
  const panel = loadPanel({ [EVENTS_URL]: { ok: true, title: 'sort', events: events } }, schedule);
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  bus.emit('live:changed', { on: true, url: BRIDGE });
  await flush();
  return { panel, root, bus, instance, schedule, plot: root.control('#timeline-plot') };
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
  const { panel, instance } = await attachedPanel([]);
  try {
    assert.deepStrictEqual(panel.requested, [EVENTS_URL]);
  } finally {
    instance.destroy();
  }
});

test('detaching stops every timer the attach started', async function () {
  const { bus, schedule, instance } = await attachedPanel([]);
  try {
    assert.ok(schedule.running() > 0);
    bus.emit('live:changed', { on: false, url: '' });
    assert.strictEqual(schedule.running(), 0);
  } finally {
    instance.destroy();
  }
});

test('destroying the panel stops every timer too', async function () {
  const { schedule, instance } = await attachedPanel([]);
  instance.destroy();
  assert.strictEqual(schedule.running(), 0);
});

test('detaching goes back to saying no demo is attached', async function () {
  const { bus, root, instance } = await attachedPanel([detectedAt(1000)]);
  try {
    bus.emit('live:changed', { on: false, url: '' });
    const empty = root.control('#timeline-empty');
    assert.strictEqual(empty.style.display, '');
  } finally {
    instance.destroy();
  }
});

// %% what it draws
test('an attached demo that has detected nothing says so', async function () {
  const { root, plot, instance } = await attachedPanel([]);
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
  const { root, plot, instance } = await attachedPanel(
    [detectedAt(1000), detectedAt(1010), detectedAt(1020)]
  );
  try {
    assert.strictEqual(marksIn(plot).length, 3);
    assert.strictEqual(root.control('#timeline-empty').style.display, 'none');
  } finally {
    instance.destroy();
  }
});

test('each kind of event gets one lane, however often it is detected', async function () {
  const { plot, instance } = await attachedPanel([
    detectedAt(1000, 'PickUpEvent'),
    detectedAt(1005, 'ContactEvent'),
    detectedAt(1010, 'PickUpEvent'),
  ]);
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
  const { plot, schedule, instance } = await attachedPanel(
    [detectedAt(1000), detectedAt(1150)], 1000
  );
  try {
    schedule.advance(200);
    schedule.fireAll();
    await flush();
    assert.strictEqual(marksIn(plot).length, 1);
  } finally {
    instance.destroy();
  }
});

test('the now-bar advances across the panel as time passes', async function () {
  const { plot, schedule, instance } = await attachedPanel([], 1000);
  try {
    const before = nowBarIn(plot).style.left;
    schedule.advance(30);
    schedule.fireAll();
    await flush();
    const after = nowBarIn(plot).style.left;
    assert.ok(parseFloat(after) > parseFloat(before), before + ' -> ' + after);
  } finally {
    instance.destroy();
  }
});

test('a bridge that stops answering leaves the last drawing standing', async function () {
  const schedule = makeSchedule(1000);
  const panel = loadPanel({ [EVENTS_URL]: { ok: true, title: 'sort', events: [detectedAt(1000)] } }, schedule);
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

    assert.strictEqual(marksIn(root.control('#timeline-plot')).length, 1);
  } finally {
    instance.destroy();
  }
});
