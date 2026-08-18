// Unit tests for panels/plan_graph/panel.js (node:test): which node reads as the one
// being executed, what the head line says, and where the tree comes from.
//
// panel.js is loaded with its free variables bound as explicit function parameters, the
// same way test_graph_panel.js and test_event_timeline_panel.js load theirs — the file
// reaches no DOM beyond the `root` it is handed. The timers are bound too, so a poll
// happens exactly when a test says it does. ResponseUtil and SceneContext are the real
// modules, so a route with no backend and a ?scene= url are exercised, not stubbed.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');
const SOURCE = fs.readFileSync(path.join(WEB, 'panels/plan_graph/panel.js'), 'utf8');

const RECORDED_URL = '/api/knowledge/view?name=plan';
const BRIDGE = 'http://bridge';
const PLAN_URL = BRIDGE + '/plan';

function loadResponseUtil() {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, 'core/response.js'), 'utf8'))(scope);
  return scope.ResponseUtil;
}

function loadSceneContext(search) {
  const scope = { location: { search: search || '' } };
  new Function('window', fs.readFileSync(path.join(WEB, 'core/scene.js'), 'utf8'))(scope);
  return scope.SceneContext;
}

function flush() {
  return new Promise(function (resolve) { setTimeout(resolve, 0); });
}

// %% stubs of the interfaces panel.js reads
function makeElement() {
  return {
    style: {},
    textContent: '',
    checked: true,
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(event, callback) { if (event === 'click') this.onClick = callback; },
    click() { if (this.onClick) this.onClick(); },
  };
}

function makeRoot() {
  const byId = {};
  ['#plan-empty', '#plan-executing', '#plan-follow', '#plan-live', '#plan-canvas',
   '#plan-legend', '#plan-zoom-in', '#plan-zoom-out', '#plan-zoom-fit',
  ].forEach(function (selector) { byId[selector] = makeElement(); });
  return {
    innerHTML: '',
    querySelector(selector) { return byId[selector]; },
    control(selector) { return byId[selector]; },
  };
}

function makeBus() {
  const handlers = {};
  const emitted = [];
  return {
    on(event, callback) { (handlers[event] = handlers[event] || []).push(callback); },
    emit(event, payload) {
      emitted.push({ event: event, payload: payload });
      (handlers[event] || []).forEach(function (callback) { callback(payload); });
    },
    emitted: emitted,
  };
}

// timers that only fire when a test tells them to
function makeSchedule() {
  const running = new Map();
  let nextHandle = 1;
  return {
    setInterval(callback) {
      const handle = nextHandle++;
      running.set(handle, callback);
      return handle;
    },
    clearInterval(handle) { running.delete(handle); },
    running() { return running.size; },
    fireAll() { Array.from(running.values()).forEach(function (callback) { callback(); }); },
  };
}

function makeFetch(answers, requested) {
  return async function fetch(url) {
    requested.push(url);
    const body = answers[url];
    if (body === undefined) throw new Error('unexpected fetch: ' + url);
    if (typeof body === 'number') return errorPage(body);
    return { ok: true, status: 200, json: async function () { return body; } };
  };
}

// what a host with no matching backend route answers: an HTML page, not JSON
function errorPage(status) {
  return {
    ok: false,
    status: status,
    json: async function () {
      throw new SyntaxError('JSON.parse: unexpected character at line 1 column 1');
    },
  };
}

function loadPanel(answers, options) {
  const settings = options || {};
  const schedule = settings.schedule || makeSchedule();
  const requested = [];
  const builds = [];
  const statusPatches = [];
  const focused = [];
  const resizes = [];
  let factory = null;
  const Panels = { define(id, built) { factory = built; } };
  const GraphView = {
    create() {
      return {
        build(payload) { builds.push(payload); },
        setStatuses(map) {
          statusPatches.push(map);
          return settings.knowsEveryNode !== false;
        },
        focus(id) { focused.push(id); },
        resize() { resizes.push('resize'); },
        zoomBy() {}, fit() {}, highlight() {}, reset() {},
        onSelect(callback) { this.selected = callback; },
        onDoubleSelect() {},
      };
    },
  };
  new Function(
    'Panels', 'GraphView', 'fetch', 'ResponseUtil', 'SceneContext',
    'setInterval', 'clearInterval', SOURCE
  )(
    Panels, GraphView, makeFetch(answers, requested), loadResponseUtil(),
    loadSceneContext(settings.search), schedule.setInterval, schedule.clearInterval
  );
  return {
    factory: factory,
    schedule: schedule,
    requested: requested,
    builds: builds,
    lastBuild: function () { return builds[builds.length - 1]; },
    statusPatches: statusPatches,
    focused: focused,
    resizes: resizes,
  };
}

// %% the plan the bridge publishes
function planNode(id, overrides) {
  return Object.assign({
    id: id, parent: null, kind: 'MotionNode', label: 'MotionNode',
    group: 'motion', status: 'CREATED', derived: false,
  }, overrides);
}

const EMPTY_RECORDED_PLAN = { ok: true, nodes: [], edges: [], details: {}, legend: [] };

function livePlan(signature, nodes, executing, legend) {
  return {
    signature: signature, nodes: nodes,
    executing: executing || [], legend: legend || [],
  };
}

// a plan whose action is running only because the motion under it is
function reachingPlan(executing) {
  return livePlan('s1', [
    planNode('a1', { kind: 'ActionNode', label: 'PickUpAction', group: 'action', status: 'RUNNING', derived: true }),
    planNode('m1', { parent: 'a1', label: 'MoveTCP', status: 'RUNNING', derived: true }),
  ], executing);
}

async function attached(panel, root, bus) {
  await flush();                                  // the recorded plan the panel boots with
  bus.emit('live:changed', { on: true, url: BRIDGE });
  await flush();
}

function statusById(build) {
  const statuses = {};
  build.nodes.forEach(function (node) { statuses[node.id] = node.status; });
  return statuses;
}

// %% what the bridge says is being executed
test('a live plan is drawn with the groups and legend the bridge sent', async function () {
  const panel = loadPanel({
    [RECORDED_URL]: EMPTY_RECORDED_PLAN,
    [PLAN_URL]: livePlan('s1', [
      planNode('a1', { kind: 'AttachNode', label: 'AttachNode', group: 'attachment' }),
      planNode('m1', { parent: 'a1' }),
    ], [], [{ group: 'attachment', label: 'Attach / detach' }]),
  });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    const groups = {};
    panel.lastBuild().nodes.forEach(function (node) { groups[node.id] = node.group; });
    assert.deepStrictEqual(groups, { a1: 'attachment', m1: 'motion' });
    assert.deepStrictEqual(panel.lastBuild().legend, [
      { group: 'attachment', label: 'Attach / detach' },
    ]);
  } finally {
    instance.destroy();
  }
});

test('only the node execution reached is executing, not the ones running above it', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    assert.deepStrictEqual(statusById(panel.lastBuild()), { a1: 'RUNNING', m1: 'EXECUTING' });
  } finally {
    instance.destroy();
  }
});

test('the head line names the step being executed', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    assert.strictEqual(root.control('#plan-executing').textContent, 'executing: MoveTCP');
  } finally {
    instance.destroy();
  }
});

test('a plan with nothing running says so rather than naming a step', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan([]) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    assert.strictEqual(root.control('#plan-executing').textContent,
                       'nothing is being executed right now');
  } finally {
    instance.destroy();
  }
});

test('a node label loses the redundant Action suffix, and only that', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan([]) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    const labels = {};
    panel.lastBuild().nodes.forEach(function (node) { labels[node.id] = node.label; });
    assert.deepStrictEqual(labels, { a1: 'PickUp', m1: 'MoveTCP' });
  } finally {
    instance.destroy();
  }
});

// %% keeping up with the run
test('execution moving on re-colours the tree instead of laying it out again', async function () {
  const answers = { [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) };
  const panel = loadPanel(answers);
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);
    const builtOnce = panel.builds.length;

    answers[PLAN_URL] = livePlan('s1', [
      planNode('a1', { kind: 'ActionNode', label: 'PickUpAction', group: 'action', status: 'RUNNING', derived: true }),
      planNode('m1', { parent: 'a1', label: 'MoveTCP', status: 'SUCCEEDED', derived: true }),
    ], ['a1']);
    panel.schedule.fireAll();
    await flush();

    assert.strictEqual(panel.builds.length, builtOnce);
    assert.deepStrictEqual(panel.statusPatches, [{ a1: 'EXECUTING', m1: 'SUCCEEDED' }]);
  } finally {
    instance.destroy();
  }
});

test('a plan that grew is laid out again', async function () {
  const answers = { [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) };
  const panel = loadPanel(answers);
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);
    const builtOnce = panel.builds.length;

    answers[PLAN_URL] = livePlan('s2', [
      planNode('a1', { kind: 'ActionNode', label: 'PickUpAction', group: 'action', status: 'RUNNING', derived: true }),
      planNode('m1', { parent: 'a1', label: 'MoveTCP', status: 'SUCCEEDED', derived: true }),
      planNode('m2', { parent: 'a1', label: 'CloseGripper', status: 'RUNNING', derived: true }),
    ], ['m2']);
    panel.schedule.fireAll();
    await flush();

    assert.strictEqual(panel.builds.length, builtOnce + 1);
    assert.deepStrictEqual(statusById(panel.lastBuild()),
                           { a1: 'RUNNING', m1: 'SUCCEEDED', m2: 'EXECUTING' });
  } finally {
    instance.destroy();
  }
});

test('a status the drawn tree has no node for is laid out again', async function () {
  const answers = { [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) };
  const panel = loadPanel(answers, { knowsEveryNode: false });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);
    const builtOnce = panel.builds.length;

    panel.schedule.fireAll();
    await flush();

    assert.strictEqual(panel.builds.length, builtOnce + 1);
  } finally {
    instance.destroy();
  }
});

// %% following the step being executed
test('the tree centres on the step execution moves to', async function () {
  const answers = { [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) };
  const panel = loadPanel(answers);
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);
    panel.schedule.fireAll();                    // same step: nothing to follow
    await flush();

    answers[PLAN_URL] = reachingPlan(['a1']);
    panel.schedule.fireAll();
    await flush();

    assert.deepStrictEqual(panel.focused, ['m1', 'a1']);
  } finally {
    instance.destroy();
  }
});

test('following switched off leaves the view where the user put it', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) });
  const root = makeRoot();
  const bus = makeBus();
  root.control('#plan-follow').checked = false;
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    assert.deepStrictEqual(panel.focused, []);
  } finally {
    instance.destroy();
  }
});

// %% where the tree comes from
test('the recorded plan is what an unattached panel shows', async function () {
  const panel = loadPanel({
    [RECORDED_URL]: {
      ok: true, legend: [], nodes: [{ id: 'r1', label: 'PickUp', group: 'action', status: 'SUCCEEDED' }],
      edges: [], details: { r1: { label: 'PickUp', group: 'action', lines: [] } },
    },
  });
  const root = makeRoot();
  const instance = panel.factory(root, makeBus());
  try {
    await flush();

    assert.deepStrictEqual(panel.requested, [RECORDED_URL]);
    assert.deepStrictEqual(statusById(panel.lastBuild()), { r1: 'SUCCEEDED' });
    assert.strictEqual(root.control('#plan-executing').textContent, 'the recorded plan');
  } finally {
    instance.destroy();
  }
});

test('the recorded plan is asked for the scene the url names', async function () {
  const panel = loadPanel({ [RECORDED_URL + '&scene=lab']: EMPTY_RECORDED_PLAN },
                          { search: '?scene=lab' });
  const instance = panel.factory(makeRoot(), makeBus());
  try {
    await flush();

    assert.deepStrictEqual(panel.requested, [RECORDED_URL + '&scene=lab']);
  } finally {
    instance.destroy();
  }
});

test('detaching from a demo falls back to the recorded plan', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    bus.emit('live:changed', { on: false, url: '' });
    await flush();

    assert.strictEqual(panel.schedule.running(), 0);
    assert.deepStrictEqual(panel.requested, [RECORDED_URL, PLAN_URL, RECORDED_URL]);
    assert.strictEqual(root.control('#plan-executing').textContent, 'the recorded plan');
  } finally {
    instance.destroy();
  }
});

// A bundle with no recorded plan is the normal case for a demo that is running right
// now, so a recorded view that fails must not be what the live plan waits for.
test('a live plan is shown even when the recorded one has no backend', async function () {
  const panel = loadPanel({ [RECORDED_URL]: 502, [PLAN_URL]: reachingPlan(['m1']) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await flush();
    const reported = root.control('#plan-empty').textContent;
    assert.match(reported, /HTTP 502/);
    assert.doesNotMatch(reported, /JSON\.parse/);

    bus.emit('live:changed', { on: true, url: BRIDGE });
    await flush();

    assert.deepStrictEqual(statusById(panel.lastBuild()), { a1: 'RUNNING', m1: 'EXECUTING' });
  } finally {
    instance.destroy();
  }
});

test('a plan the demo has not started yet says so', async function () {
  const panel = loadPanel({
    [RECORDED_URL]: EMPTY_RECORDED_PLAN,
    [PLAN_URL]: livePlan('', [], []),
  });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await attached(panel, root, bus);

    assert.strictEqual(root.control('#plan-empty').textContent,
                       'Attached, but the demo has not started its plan yet.');
  } finally {
    instance.destroy();
  }
});

// %% coming back into view inside a tab group
test('the tree re-fits when its own tab becomes the visible one', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN });
  const bus = makeBus();
  const instance = panel.factory(makeRoot(), bus, 'plan-graph');
  try {
    await flush();

    bus.emit('panel:shown', { id: 'plan-graph' });

    assert.deepStrictEqual(panel.resizes, ['resize']);
  } finally {
    instance.destroy();
  }
});

test('the tree re-fits when the panes are resized around it', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN });
  const bus = makeBus();
  const instance = panel.factory(makeRoot(), bus, 'plan-graph');
  try {
    await flush();

    bus.emit('panel:resized', {});

    assert.deepStrictEqual(panel.resizes, ['resize']);
  } finally {
    instance.destroy();
  }
});

test('another tab becoming visible leaves the tree alone', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN });
  const bus = makeBus();
  const instance = panel.factory(makeRoot(), bus, 'plan-graph');
  try {
    await flush();

    bus.emit('panel:shown', { id: 'graph' });

    assert.deepStrictEqual(panel.resizes, []);
  } finally {
    instance.destroy();
  }
});

// %% the panel is torn down with the page
test('destroying the panel stops it polling the bridge', async function () {
  const panel = loadPanel({ [RECORDED_URL]: EMPTY_RECORDED_PLAN, [PLAN_URL]: reachingPlan(['m1']) });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  await attached(panel, root, bus);
  assert.strictEqual(panel.schedule.running(), 1);

  instance.destroy();

  assert.strictEqual(panel.schedule.running(), 0);
});
