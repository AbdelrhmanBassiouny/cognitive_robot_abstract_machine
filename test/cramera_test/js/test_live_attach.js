// Unit tests for web/core/live_attach.js (node:test).
// A viewer opened without a named scene attaches itself to whatever demo is reachable.
// Whether it may do so again after it stopped being attached is the whole question here:
// a demo restarted from the viewer goes away and comes back, and a viewer that treats
// its first attach as final never follows it.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function load() {
  global.window = {};
  new Function(fs.readFileSync(path.join(WEB, 'core/live_attach.js'), 'utf8'))();
  return window.LiveAttach;
}

test('a reachable demo is attached to when no scene was named', function () {
  assert.strictEqual(
    load().shouldAttach({ reachable: true, attached: false, sceneNamed: false, userDetached: false }),
    true
  );
});

test('a viewer opened on a named scene stays on its recording', function () {
  assert.strictEqual(
    load().shouldAttach({ reachable: true, attached: false, sceneNamed: true, userDetached: false }),
    false
  );
});

test('an unreachable demo is not attached to', function () {
  assert.strictEqual(
    load().shouldAttach({ reachable: false, attached: false, sceneNamed: false, userDetached: false }),
    false
  );
});

test('an already attached viewer does not attach twice', function () {
  assert.strictEqual(
    load().shouldAttach({ reachable: true, attached: true, sceneNamed: false, userDetached: false }),
    false
  );
});

test('a demo that came back is attached to again', function () {
  // the restart case: the viewer was attached, lost the bridge, and the rebuilt run is
  // answering again. Nobody asked to stop watching, so watching resumes.
  assert.strictEqual(
    load().shouldAttach({ reachable: true, attached: false, sceneNamed: false, userDetached: false }),
    true
  );
});

test('a viewer detached by hand is left detached', function () {
  assert.strictEqual(
    load().shouldAttach({ reachable: true, attached: false, sceneNamed: false, userDetached: true }),
    false
  );
});
