// Unit tests for web/core/query-source.js (node:test): where a question is sent.
//
// A recorded scene is asked of the server, which needs the scene named; a demo the
// viewer is attached to is asked of its own bridge, which serves one demo and knows no
// scenes. Getting this wrong asks the wrong thing entirely -- the bundle a demo was
// recorded from rather than the run in progress -- so both routes are pinned here.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

const SCENE = 'PR2_Apartment';

function load() {
  const scope = {
    SceneContext: {
      name: SCENE,
      withScene: function (url) { return url + '?scene=' + SCENE; },
    },
  };
  new Function('window', fs.readFileSync(path.join(WEB, 'core/query-source.js'), 'utf8'))(scope);
  return scope.QuerySource;
}

// %% the recorded scene
test('a viewer attached to nothing asks the server about its scene', function () {
  const source = load().of(null);
  assert.strictEqual(source.live, false);
  assert.strictEqual(source.presetsUrl, '/api/knowledge?scene=' + SCENE);
  assert.strictEqual(source.runUrl, '/api/eql?scene=' + SCENE);
});

test('a detached stream leaves the recording answering, stale url and all', function () {
  const source = load().of({ on: false, url: 'http://localhost:8765' });
  assert.strictEqual(source.live, false);
  assert.strictEqual(source.runUrl, '/api/eql?scene=' + SCENE);
});

test('a stream that names no bridge cannot be asked either', function () {
  assert.strictEqual(load().of({ on: true, url: '' }).live, false);
});

// %% the running demo
test('an attached viewer asks the demo bridge, which knows no scenes', function () {
  const source = load().of({ on: true, url: 'http://localhost:8765' });
  assert.strictEqual(source.live, true);
  assert.strictEqual(source.presetsUrl, 'http://localhost:8765/presets');
  assert.strictEqual(source.runUrl, 'http://localhost:8765/eql');
});

test('a bridge url with a trailing slash builds the same routes', function () {
  const source = load().of({ on: true, url: 'http://localhost:8765//' });
  assert.strictEqual(source.presetsUrl, 'http://localhost:8765/presets');
  assert.strictEqual(source.runUrl, 'http://localhost:8765/eql');
});
