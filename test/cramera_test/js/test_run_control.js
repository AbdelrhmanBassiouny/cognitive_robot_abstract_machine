// Unit tests for web/core/run_control.js (node:test).
// The demo's run state arrives as flags; this is the one place that turns them into the
// buttons the scene panel draws, so the panel never reasons about state itself.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function load() {
  global.window = {};
  new Function(fs.readFileSync(path.join(WEB, 'core/run_control.js'), 'utf8'))();
  return window.RunControl;
}

function state(overrides) {
  return Object.assign({
    paused: false,
    looping: false,
    restart_pending: false,
    activity: 'sorting',
    iteration: 1,
    title: 'Montessori sorting',
  }, overrides || {});
}

function commandsOf(buttons) {
  return buttons.map(function (button) { return button.command; });
}

function buttonFor(buttons, command) {
  return buttons.filter(function (button) { return button.command === command; })[0];
}

test('a demo that offers no control gets no buttons', function () {
  assert.deepStrictEqual(load().buttonsFor(null), []);
});

test('a running demo can be paused, restarted and looped', function () {
  const buttons = load().buttonsFor(state());
  assert.deepStrictEqual(commandsOf(buttons), ['pause', 'restart', 'enable_loop']);
});

test('a paused demo offers resume in place of pause', function () {
  const buttons = load().buttonsFor(state({ paused: true }));
  assert.deepStrictEqual(commandsOf(buttons), ['resume', 'restart', 'enable_loop']);
});

test('a looping demo offers to stop looping', function () {
  const buttons = load().buttonsFor(state({ looping: true }));
  assert.strictEqual(buttonFor(buttons, 'disable_loop').active, true);
});

test('the loop button is the same button either way', function () {
  const off = buttonFor(load().buttonsFor(state()), 'enable_loop');
  const on = buttonFor(load().buttonsFor(state({ looping: true })), 'disable_loop');
  assert.strictEqual(off.label, on.label);
  assert.strictEqual(off.active, false);
});

test('a restart already asked for is shown as pending, not offered again', function () {
  const restart = buttonFor(load().buttonsFor(state({ restart_pending: true })), 'restart');
  assert.strictEqual(restart.pending, true);
});

test('every button carries a label and an explanation', function () {
  load().buttonsFor(state()).forEach(function (button) {
    assert.ok(button.label.length > 0, button.command);
    assert.ok(button.title.length > 0, button.command);
  });
});

test('the status says what the run is doing and which run it is', function () {
  assert.strictEqual(load().statusOf(state({ iteration: 3 })), 'sorting · run 3');
});

test('a paused run says so rather than what it was doing', function () {
  assert.strictEqual(load().statusOf(state({ paused: true, iteration: 2 })), 'paused · run 2');
});

test('a pending restart says the run is on its way out', function () {
  assert.strictEqual(load().statusOf(state({ restart_pending: true })), 'restarting · run 1');
});

test('a finished run that loops says the next one is coming', function () {
  const status = load().statusOf(state({ activity: 'finished', looping: true }));
  assert.strictEqual(status, 'finished · looping · run 1');
});

test('nothing to control has nothing to say', function () {
  assert.strictEqual(load().statusOf(null), '');
});
