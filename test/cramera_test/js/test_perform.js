// Unit tests for web/core/perform.js (node:test).
// A queried action's button says what pressing it would do and what became of it once
// pressed; this is the one place that turns the demo's execution state into that
// button, so the EQL panel never reasons about the state itself.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function load() {
  global.window = {};
  new Function(fs.readFileSync(path.join(WEB, 'core/perform.js'), 'utf8'))();
  return window.PerformControl;
}

const ACTION = { name: 'insert_cube', description: 'insert the cube into the square hole' };

function state(overrides) {
  return Object.assign({ performing: null, requested: [], title: 'Montessori sorting' }, overrides || {});
}

test('a row naming no action gets no button', function () {
  assert.strictEqual(load().buttonFor(null, state()), null);
});

test('an action nothing is doing yet can be asked for', function () {
  const button = load().buttonFor(ACTION, state());
  assert.strictEqual(button.disabled, false);
});

test('the button says what performing it would do', function () {
  assert.ok(load().buttonFor(ACTION, state()).title.indexOf(ACTION.description) >= 0);
});

test('an action already asked for cannot be asked for twice', function () {
  const button = load().buttonFor(ACTION, state({ requested: [ACTION.name] }));
  assert.strictEqual(button.disabled, true);
});

test('an action being carried out cannot be asked for again', function () {
  const button = load().buttonFor(ACTION, state({ performing: ACTION.name }));
  assert.strictEqual(button.disabled, true);
});

test('waiting and being carried out read differently', function () {
  const waiting = load().buttonFor(ACTION, state({ requested: [ACTION.name] }));
  const running = load().buttonFor(ACTION, state({ performing: ACTION.name }));
  assert.notStrictEqual(waiting.label, running.label);
});

test('an action someone else asked for is still offered', function () {
  const button = load().buttonFor(ACTION, state({ performing: 'insert_star' }));
  assert.strictEqual(button.disabled, false);
});

test('a demo doing nothing has nothing to say', function () {
  assert.strictEqual(load().statusOf(state()), '');
});

test('the status names what is being carried out', function () {
  const status = load().statusOf(state({ performing: 'insert_cube' }));
  assert.strictEqual(status, 'performing insert_cube');
});

test('the status counts what is still waiting', function () {
  const status = load().statusOf(state({ performing: 'insert_cube', requested: ['insert_star'] }));
  assert.strictEqual(status, 'performing insert_cube · 1 waiting');
});

test('nothing to perform has nothing to say', function () {
  assert.strictEqual(load().statusOf(null), '');
});
