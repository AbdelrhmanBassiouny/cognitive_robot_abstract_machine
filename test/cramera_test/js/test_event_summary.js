// Unit tests for core/event_summary.js (node:test).
//
// The time of day an event fell on is read out of a Date, so the zone is fixed here
// rather than left to whichever one the machine running the suite happens to be in.
'use strict';

process.env.TZ = 'UTC';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function loadEventSummary() {
  const scope = {};
  new Function('window', fs.readFileSync(path.join(WEB, 'core/event_summary.js'), 'utf8'))(scope);
  return scope.EventSummary;
}

const EventSummary = loadEventSummary();

// 2026-08-13 09:05:07 UTC, a time of day whose minutes and seconds both need padding.
const DETECTED_AT = Date.UTC(2026, 7, 13, 9, 5, 7) / 1000;

function detected(fields) {
  return Object.assign(
    { kind: 'PickUpEvent', detected_at: DETECTED_AT, seconds_into_run: 0, participants: [] },
    fields
  );
}

// %% what happened
test('the summary leads with the kind of event the demo detected', function () {
  assert.strictEqual(EventSummary.of(detected({ kind: 'InsertionEvent' })).kind, 'InsertionEvent');
});

test('every object the event involved is named, in the order it was given', function () {
  const summary = EventSummary.of(detected({ participants: ['square_shape', 'square_hole'] }));

  assert.strictEqual(summary.objects, 'square_shape, square_hole');
});

test('an event involving nothing names nothing', function () {
  assert.strictEqual(EventSummary.of(detected({ participants: [] })).objects, '');
});

test('an event that reports no objects at all is read as involving none', function () {
  assert.strictEqual(EventSummary.of({ kind: 'PickUpEvent', detected_at: DETECTED_AT, seconds_into_run: 0 }).objects, '');
});

// %% when it happened
test('the time of day is padded to hours, minutes and seconds', function () {
  assert.strictEqual(EventSummary.of(detected({})).time.split(' · ')[0], '9:05:07');
});

test('how far into the run it was is given as minutes and tenths of a second', function () {
  const summary = EventSummary.of(detected({ seconds_into_run: 83.44 }));

  assert.strictEqual(summary.time.split(' · ')[1], '+1:23.4');
});

test('seconds under ten are padded, so the two halves of a run time line up', function () {
  assert.strictEqual(
    EventSummary.of(detected({ seconds_into_run: 65 })).time.split(' · ')[1], '+1:05.0');
});

test('an event in the first minute is still given a minute', function () {
  assert.strictEqual(
    EventSummary.of(detected({ seconds_into_run: 7.25 })).time.split(' · ')[1], '+0:07.3');
});

test('a run time before the start of the run reads as the start of it', function () {
  assert.strictEqual(
    EventSummary.of(detected({ seconds_into_run: -3 })).time.split(' · ')[1], '+0:00.0');
});

test('both the time of day and the run time are shown, in that order', function () {
  assert.strictEqual(EventSummary.of(detected({ seconds_into_run: 83.44 })).time, '9:05:07 · +1:23.4');
});
