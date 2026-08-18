// Demo tests for panels/eql/panel.js (node:test): asking a question end to end.
//
// panel.js is loaded with its free variables bound as explicit function parameters
// (the test_graph_panel.js pattern). QuestionDisplay, PresetGroups, AnswerTable,
// ResponseUtil and SceneContext are the real core modules, so the flow a viewer
// drives — presets load, a preset is picked, the question shows big in English, the
// query runs, the answer renders — is exercised against the real string building,
// with only the DOM and fetch stubbed.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');
const SOURCE = fs.readFileSync(path.join(WEB, 'panels/eql/panel.js'), 'utf8');

function loadCore(name, scope) {
  new Function('window', fs.readFileSync(path.join(WEB, name), 'utf8'))(scope);
}

function coreModules() {
  const scope = { location: { search: '' } };
  loadCore('core/scene.js', scope);
  loadCore('core/query_source.js', scope);
  loadCore('core/question_display.js', scope);
  loadCore('core/preset_groups.js', scope);
  loadCore('core/answer_table.js', scope);
  loadCore('core/response.js', scope);
  return scope;
}

function flush() {
  return new Promise(function (resolve) { setTimeout(resolve, 0); });
}

// %% a miniature DOM: just what the panel reaches for
function makeElement(tag) {
  const listeners = {};
  return {
    tagName: tag || 'div',
    innerHTML: '',
    textContent: '',
    title: '',
    className: '',
    value: '',
    children: [],
    classList: {
      classes: new Set(),
      add(c) { this.classes.add(c); },
      remove(c) { this.classes.delete(c); },
    },
    appendChild(child) { this.children.push(child); return child; },
    scrolledIntoView: 0,
    scrollIntoView() { this.scrolledIntoView += 1; },
    addEventListener(event, cb) { (listeners[event] = listeners[event] || []).push(cb); },
    click() { (listeners.click || []).forEach(function (cb) { cb(); }); },
    querySelectorAll() { return []; },
  };
}

function makeRoot() {
  const byId = {
    '#knowledge-status': makeElement('span'),
    '#answer': makeElement(),
    '#query-input': makeElement('textarea'),
    '#query-run': makeElement('button'),
    '#question': makeElement(),
    '#presets': makeElement(),
  };
  return {
    innerHTML: '',
    querySelector(selector) { return byId[selector]; },
    part(selector) { return byId[selector]; },
  };
}

function makeBus() {
  const handlers = {};
  const emitted = [];
  return {
    on(event, cb) { (handlers[event] = handlers[event] || []).push(cb); },
    emit(event, payload) {
      emitted.push({ event: event, payload: payload });
      (handlers[event] || []).forEach(function (cb) { cb(payload); });
    },
    emitted: emitted,
  };
}

function makeFetch(routes, requests) {
  return async function fetch(url, options) {
    requests.push({ url: url, options: options });
    const answer = routes[url.split('?')[0]];
    if (!answer) return { ok: false, status: 404 };
    return { ok: true, status: 200, json: async function () { return answer; } };
  };
}

// every button the presets area currently shows, at any depth
function presetButtons(presetsEl) {
  const buttons = [];
  (function walk(children) {
    children.forEach(function (child) {
      if (child.className === 'preset' || child.className === 'preset unavailable') {
        buttons.push(child);
      }
      walk(child.children);
    });
  })(presetsEl.children);
  return buttons;
}

// %% the harness
const WORDED_PRESET = {
  text: 'which robot is this?',
  code: 'the(entity(robot))',
  requires_live: false,
  scope: 'current_state',
  verbalization: {
    text: 'The Robot.',
    html: '<span style="color:#ff7a9c">The Robot</span>.',
  },
};

const UNWORDED_PRESET = {
  text: 'success rate per shape',
  code: 'set_of(shape.name)',
  requires_live: false,
  scope: 'current_state',
  verbalization: null,
};

const ANSWER = {
  ok: true,
  kind: 'entities',
  rows: [{ __entity__: 'tracy', __type__: 'Robot' }],
  count: 1,
  more: false,
  highlight: ['tracy'],
  verbalization: {
    text: 'The one Robot there is.',
    html: '<span style="color:#5b8cff">The one</span> <span style="color:#ff7a9c">Robot</span> there is.',
  },
};

function mountPanel(overrides) {
  const core = coreModules();
  const root = makeRoot();
  const bus = makeBus();
  const requests = [];
  const routes = Object.assign(
    {
      '/api/knowledge': {
        ok: true,
        status: 'EQL ready',
        presets: [WORDED_PRESET, UNWORDED_PRESET],
        details: {},
      },
      '/api/eql': ANSWER,
    },
    overrides || {}
  );
  let panelFactory = null;
  const define = function (name, factory) { panelFactory = factory; };
  new Function(
    'Panels', 'SceneContext', 'QuerySource', 'QuestionDisplay', 'PresetGroups',
    'AnswerTable', 'ResponseUtil', 'EqlSuggestions', 'Replay', 'fetch', 'window',
    'document',
    SOURCE
  )(
    { define: define }, core.SceneContext, core.QuerySource, core.QuestionDisplay,
    core.PresetGroups, core.AnswerTable, core.ResponseUtil,
    { of() { return { forget() {}, handledKey() { return false; } }; } },
    { popupUrl() { return ''; } },
    makeFetch(routes, requests),
    { location: { pathname: '/', search: '' }, open() {} },
    { createElement: makeElement }
  );
  panelFactory(root, bus);
  return { root: root, bus: bus, requests: requests };
}

// %% the flow a viewer drives
test('before anything is asked the display shows how to ask', async function () {
  const panel = mountPanel();
  await flush();
  const question = panel.root.part('#question').innerHTML;
  assert.ok(question.indexOf('question-hint') >= 0, question);
});

test('picking a preset shows its wording big and runs its query', async function () {
  const panel = mountPanel();
  await flush(); await flush();

  const button = presetButtons(panel.root.part('#presets'))[0];
  assert.strictEqual(button.textContent, WORDED_PRESET.text);
  button.click();

  // the picked query fills the bar, and the question is on display under it
  // before the answer arrives
  assert.strictEqual(panel.root.part('#query-input').value, WORDED_PRESET.code);
  assert.strictEqual(panel.root.part('#question').innerHTML, WORDED_PRESET.verbalization.html);
  assert.strictEqual(panel.root.part('#question').title, WORDED_PRESET.code);

  await flush(); await flush();

  const run = panel.requests.find(function (r) { return r.url === '/api/eql'; });
  assert.deepStrictEqual(JSON.parse(run.options.body), {
    code: WORDED_PRESET.code,
    scope: 'current_state',
  });
  const answer = panel.root.part('#answer').innerHTML;
  assert.ok(answer.indexOf('<b>1</b> result') >= 0, answer);
  assert.ok(answer.indexOf('tracy') >= 0, answer);
});

test('the answered query\'s own wording replaces the label it was picked by', async function () {
  const panel = mountPanel();
  await flush(); await flush();

  presetButtons(panel.root.part('#presets'))[1].click();
  // unworded until the answer arrives: the plain label stands in
  assert.strictEqual(panel.root.part('#question').innerHTML, UNWORDED_PRESET.text);

  await flush(); await flush();

  assert.strictEqual(panel.root.part('#question').innerHTML, ANSWER.verbalization.html);
});

test('the answer highlights what it names', async function () {
  const panel = mountPanel();
  await flush(); await flush();

  presetButtons(panel.root.part('#presets'))[0].click();
  await flush(); await flush();

  const highlight = panel.bus.emitted.filter(function (e) { return e.event === 'entity:highlight'; }).pop();
  assert.deepStrictEqual(highlight.payload.ids, ['tracy']);
});

test('a typed query runs from the bar and its wording appears under it', async function () {
  const panel = mountPanel();
  await flush(); await flush();

  panel.root.part('#query-input').value = 'the(entity(robot))';
  panel.root.part('#query-run').click();
  await flush(); await flush();

  const run = panel.requests.find(function (r) { return r.url === '/api/eql'; });
  assert.deepStrictEqual(JSON.parse(run.options.body), {
    code: 'the(entity(robot))',
    scope: null,
  });
  // the answered query's own wording shows under the bar
  assert.strictEqual(panel.root.part('#question').innerHTML, ANSWER.verbalization.html);
  assert.ok(panel.root.part('#answer').innerHTML.indexOf('tracy') >= 0);
});

test('a failed query is reported in the answer area, not swallowed', async function () {
  const panel = mountPanel({ '/api/eql': { ok: false, error: 'NameError: shape' } });
  await flush(); await flush();

  presetButtons(panel.root.part('#presets'))[0].click();
  await flush(); await flush();

  const answer = panel.root.part('#answer').innerHTML;
  assert.ok(answer.indexOf('NameError: shape') >= 0, answer);
});

// %% the answer sits under everything asked, so it is scrolled to when it arrives
test('an answered query is scrolled to', async function () {
  const panel = mountPanel();
  await flush(); await flush();
  const answer = panel.root.part('#answer');
  assert.strictEqual(answer.scrolledIntoView, 0);

  presetButtons(panel.root.part('#presets'))[0].click();
  await flush(); await flush();

  assert.strictEqual(answer.scrolledIntoView, 1);
});

test('a described entity is shown where the answer is, without scrolling to it', async function () {
  const panel = mountPanel();
  await flush(); await flush();

  panel.bus.emit('entity:select', {
    id: 'tracy', detail: { group: 'robot', label: 'Tracy', lines: [] }, relations: [],
  });

  const answer = panel.root.part('#answer');
  assert.ok(answer.innerHTML.indexOf('Tracy') >= 0, answer.innerHTML);
  assert.strictEqual(answer.scrolledIntoView, 0);
});
