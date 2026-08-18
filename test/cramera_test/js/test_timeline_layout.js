// Unit tests for web/core/timeline_layout.js (node:test): the timeline's geometry,
// as arithmetic on plain numbers with no DOM anywhere near it.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function loadLayout() {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, 'core/timeline_layout.js'), 'utf8'))(scope);
  return scope.TimelineLayout;
}

const TimelineLayout = loadLayout();
const SPAN = 60;

// %% which stretch of time is on screen
test('a young run is shown from its start, so the now-bar has room to sweep', function () {
  assert.deepStrictEqual(TimelineLayout.boundsFor(100, 110, SPAN), { start: 100, end: 160 });
});

test('the whole span is on screen the moment the run starts', function () {
  assert.deepStrictEqual(TimelineLayout.boundsFor(100, 100, SPAN), { start: 100, end: 160 });
});

test('a run older than the span scrolls, keeping now at the right edge', function () {
  assert.deepStrictEqual(TimelineLayout.boundsFor(100, 500, SPAN), { start: 440, end: 500 });
});

test('the switch to scrolling happens exactly when now reaches the end', function () {
  const atTheEdge = TimelineLayout.boundsFor(100, 160, SPAN);
  assert.deepStrictEqual(atTheEdge, { start: 100, end: 160 });
});

// %% where an instant lands
test('the start of the bounds is the left edge and the end is the right', function () {
  const bounds = { start: 100, end: 160 };
  assert.strictEqual(TimelineLayout.horizontalPosition(bounds, 100, 300), 0);
  assert.strictEqual(TimelineLayout.horizontalPosition(bounds, 160, 300), 300);
});

test('an instant halfway through the bounds lands halfway across', function () {
  assert.strictEqual(
    TimelineLayout.horizontalPosition({ start: 100, end: 160 }, 130, 300), 150);
});

test('bounds of no duration put everything at the left edge rather than nowhere', function () {
  assert.strictEqual(
    TimelineLayout.horizontalPosition({ start: 100, end: 100 }, 100, 300), 0);
});

test('an instant outside the bounds is reported as outside', function () {
  const bounds = { start: 100, end: 160 };
  assert.strictEqual(TimelineLayout.isInside(bounds, 99), false);
  assert.strictEqual(TimelineLayout.isInside(bounds, 100), true);
  assert.strictEqual(TimelineLayout.isInside(bounds, 160), true);
  assert.strictEqual(TimelineLayout.isInside(bounds, 161), false);
});

// %% one lane per kind of event
test('lanes are the distinct kinds, in the order they were first detected', function () {
  const events = [
    { kind: 'PickUpEvent' },
    { kind: 'ContactEvent' },
    { kind: 'PickUpEvent' },
    { kind: 'InsertionEvent' },
  ];
  assert.deepStrictEqual(TimelineLayout.kindsOf(events),
    ['PickUpEvent', 'ContactEvent', 'InsertionEvent']);
});

test('nothing detected yet means no lanes', function () {
  assert.deepStrictEqual(TimelineLayout.kindsOf([]), []);
});

test('lanes split the height evenly and sit in the middle of their share', function () {
  assert.strictEqual(TimelineLayout.laneCentre(0, 2, 100), 25);
  assert.strictEqual(TimelineLayout.laneCentre(1, 2, 100), 75);
});

test('a single lane sits in the middle of the whole height', function () {
  assert.strictEqual(TimelineLayout.laneCentre(0, 1, 100), 50);
});

test('no lanes at all still gives a usable centre rather than nothing', function () {
  assert.strictEqual(TimelineLayout.laneCentre(0, 0, 100), 50);
});
