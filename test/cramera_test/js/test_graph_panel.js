// Unit tests for panels/graph/panel.js (node:test): the live-plan colour-group mapping.
//
// panel.js is loaded with its free variables (Panels, Graph, fetch, ResponseUtil)
// bound as explicit function parameters rather than through global/window stubs, since
// the file itself never touches `window` or `document` directly (it only reaches DOM
// elements handed to it via its own `root` parameter). ResponseUtil is the real
// core/response.js, so the panel's error handling is exercised, not a stub of it.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');
const SOURCE = fs.readFileSync(path.join(WEB, 'panels/graph/panel.js'), 'utf8');

function loadResponseUtil() {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, 'core/response.js'), 'utf8'))(scope);
  return scope.ResponseUtil;
}

function flush() {
  return new Promise(function (resolve) { setTimeout(resolve, 0); });
}

// %% stubs of the interfaces panel.js reads
function makeElement() {
  return {
    style: {},
    textContent: '',
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener() {},
    querySelectorAll() { return []; },
  };
}

function makeButton(view) {
  let onClick = null;
  return {
    dataset: { view: view },
    classList: { toggle() {} },
    addEventListener(event, cb) { if (event === 'click') onClick = cb; },
    click() { if (onClick) onClick(); },
  };
}

function makeRoot() {
  const byId = {
    '#graph-empty': makeElement(),
    '#graph-nav': makeElement(),
    '#gnav-up': makeElement(),
    '#gnav-home': makeElement(),
    '#gnav-path': makeElement(),
    '#gt-live': makeElement(),
    '#graph': makeElement(),
    '#legend': makeElement(),
  };
  const buttons = ['knowledge', 'kinematics', 'plan', 'chart'].map(makeButton);
  byId['#graph-tabs'] = { querySelectorAll() { return buttons; } };
  return {
    innerHTML: '',
    querySelector(selector) { return byId[selector]; },
    buttons: buttons,
  };
}

function makeBus() {
  const handlers = {};
  return {
    on(event, cb) { (handlers[event] = handlers[event] || []).push(cb); },
    emit(event, payload) { (handlers[event] || []).forEach(function (cb) { cb(payload); }); },
  };
}

function makeFetch(responses) {
  return async function fetch(url) {
    const body = responses[url];
    if (!body) throw new Error('unexpected fetch: ' + url);
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

function loadPanel(responses) {
  let factory = null;
  let lastBuild = null;
  const Panels = { define(id, f) { factory = f; } };
  const Graph = {
    attach() {}, build(payload) { lastBuild = payload; },
    onSelect() {}, onDoubleSelect() {}, highlight() {}, reset() {},
    setStatuses() { return false; },
  };
  new Function('Panels', 'Graph', 'fetch', 'ResponseUtil', SOURCE)(
    Panels, Graph, makeFetch(responses), loadResponseUtil()
  );
  return { factory: factory, lastBuild: function () { return lastBuild; } };
}

// %% live plan colour groups
test('AttachNode and DetachNode plan nodes render in the object colour group', async function () {
  const panel = loadPanel({
    '/api/knowledge': { ok: true, nodes: [], edges: [], details: {} },
    '/api/knowledge/view?name=plan': { ok: true, nodes: [], edges: [], details: {}, live: 'plan' },
    'http://bridge/plan': {
      signature: 's1',
      nodes: [
        { id: 'a1', kind: 'AttachNode', label: 'AttachNode', status: 'CREATED' },
        { id: 'd1', kind: 'DetachNode', label: 'DetachNode', status: 'CREATED' },
      ],
    },
  });
  const root = makeRoot();
  const bus = makeBus();
  const instance = panel.factory(root, bus);
  try {
    await flush();

    root.buttons.find(function (b) { return b.dataset.view === 'plan'; }).click();
    await flush();

    bus.emit('live:changed', { on: true, url: 'http://bridge' });
    await flush();

    const byId = {};
    panel.lastBuild().nodes.forEach(function (n) { byId[n.id] = n; });
    assert.strictEqual(byId.a1.group, 'object');
    assert.strictEqual(byId.d1.group, 'object');
  } finally {
    instance.destroy();       // clears the live-poll setInterval even if an assertion above throws
  }
});

// %% a route with no backend
test('a view whose route has no backend reports the status, not a JSON.parse error', async function () {
  const panel = loadPanel({
    '/api/knowledge': { ok: true, nodes: [], edges: [], details: {} },
    '/api/knowledge/view?name=kinematics': 502,
  });
  const root = makeRoot();
  const instance = panel.factory(root, makeBus());
  try {
    await flush();

    root.buttons.find(function (b) { return b.dataset.view === 'kinematics'; }).click();
    await flush();

    const reported = root.querySelector('#graph-empty').textContent;
    assert.match(reported, /HTTP 502/);
    assert.doesNotMatch(reported, /JSON\.parse/);
  } finally {
    instance.destroy();
  }
});
