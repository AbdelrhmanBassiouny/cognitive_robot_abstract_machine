// Unit tests for web/core/event_annotation.js (node:test).
// A replayed event is annotated by two pure pieces: where its caption floats over the
// objects it happened to, and how each arrow reaches one of them. Both are checkable
// here, without a browser or a 3D scene.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function load() {
  global.window = {};
  new Function(fs.readFileSync(path.join(WEB, 'core/event_annotation.js'), 'utf8'))();
  return window.EventAnnotation;
}

function at(x, y, z) {
  return { x: x, y: y, z: z };
}

// %% where the caption floats
test('the caption floats over a lone object by its clearance', function () {
  const annotation = load();

  assert.deepStrictEqual(
    annotation.captionAnchor([at(0.4, -0.2, 0.9)]),
    at(0.4, -0.2, 0.9 + annotation.CAPTION_CLEARANCE)
  );
});

test('the caption is centred over the objects it names', function () {
  const anchor = load().captionAnchor([at(0, 0, 0.5), at(1, 2, 0.5)]);

  assert.strictEqual(anchor.x, 0.5);
  assert.strictEqual(anchor.y, 1);
});

test('the caption clears the tallest object, not the last one', function () {
  const annotation = load();

  const anchor = annotation.captionAnchor([at(0, 0, 1.2), at(0, 0, 0.3)]);

  assert.strictEqual(anchor.z, 1.2 + annotation.CAPTION_CLEARANCE);
});

test('an event with no object on screen has nothing to caption', function () {
  const annotation = load();

  assert.strictEqual(annotation.captionAnchor([]), null);
  assert.strictEqual(annotation.captionAnchor(null), null);
});

// %% how an arrow reaches its object
test('an arrow points from the caption at the object', function () {
  const arrow = load().arrowTo(at(0, 0, 1), at(0, 0, 0.2));

  assert.deepStrictEqual(arrow.direction, at(0, 0, -1));
});

test('an arrow off to one side is aimed by a unit direction', function () {
  const direction = load().arrowTo(at(0, 0, 0), at(3, 0, 4)).direction;

  assert.deepStrictEqual(direction, at(0.6, 0, 0.8));
});

test('the shaft stops short of the object by the head and the tip clearance', function () {
  const annotation = load();

  const arrow = annotation.arrowTo(at(0, 0, 1), at(0, 0, 0));

  assert.strictEqual(
    arrow.shaftLength,
    1 - annotation.TIP_CLEARANCE - annotation.HEAD_LENGTH
  );
});

test('an object too close to fit an arrowhead gets no arrow', function () {
  const annotation = load();
  const tooClose = annotation.TIP_CLEARANCE + annotation.HEAD_LENGTH;

  assert.strictEqual(annotation.arrowTo(at(0, 0, tooClose), at(0, 0, 0)), null);
  assert.strictEqual(annotation.arrowTo(at(0, 0, 0), at(0, 0, 0)), null);
});
