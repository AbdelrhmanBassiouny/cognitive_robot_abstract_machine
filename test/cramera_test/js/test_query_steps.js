const BrowserSource = require('./browser_source');
// Unit tests for web/core/query_steps.js (node:test).
// Each query a running robot asked is shown with the code that asks it, the question
// in English and its answers; the panel follows the step the robot is held at unless
// one was picked to look back at.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

function load() {
  global.window = {};
  new Function(BrowserSource.read(path.join(WEB, 'core/query_steps.js')))();
  return window.QuerySteps;
}

const CODE = {
  file: 'experiments/demo.py',
  function: 'holes_of',
  firstLine: 10,
  lines: ['def holes_of(kind):', '    hole = variable(Hole, holes)', '    return an(entity(hole))'],
  focus: [11, 12],
};

function step(number, asker, extra) {
  return Object.assign({
    number: number, asker: asker, depth: 0, moment: 'answered', answers: ['a'],
    question: { text: 'Find a Hole ' + number, html: '<span>Find</span>' }, backend: 'B',
  }, extra || {});
}

test('only the lines of the statement asking the query are in focus', function () {
  const html = load().codeHtml(CODE);
  const focused = html.split('qs-codeline qs-focus').length - 1;
  assert.strictEqual(focused, CODE.focus[1] - CODE.focus[0] + 1);
});

test('each line is numbered where it is in its file', function () {
  const html = load().codeHtml(CODE);
  CODE.lines.forEach(function (_, index) {
    assert.ok(html.indexOf('<span class="qs-ln">' + (CODE.firstLine + index) + '</span>') >= 0);
  });
});

test('the query language words of a line are picked out', function () {
  const html = load().lineHtml('an(entity(hole))');
  assert.ok(html.indexOf('<span class="qs-eql">an</span>') >= 0);
  assert.ok(html.indexOf('<span class="qs-eql">entity</span>') >= 0);
});

test('a string in a line is kept whole and escaped', function () {
  const html = load().lineHtml('name = "<a>"');
  assert.ok(html.indexOf('<span class="qs-string">&quot;&lt;a&gt;&quot;</span>') >= 0);
});

test('the robot is followed at the step it is held at', function () {
  const published = { steps: [step(0, null), step(1, null)], held: 1 };
  assert.strictEqual(load().shown(published, null), published.steps[1]);
});

test('a step picked to look back at is shown instead', function () {
  const published = { steps: [step(0, null), step(1, null)], held: 1 };
  assert.strictEqual(load().shown(published, 0), published.steps[0]);
});

test('nothing is shown while the robot is not held and nothing is picked', function () {
  assert.strictEqual(load().shown({ steps: [step(0, null)], held: null }, null), null);
});

test('the steps that asked a nested query are listed outermost first', function () {
  const steps = [step(0, null), step(1, 0), step(2, 1)];
  assert.deepStrictEqual(load().askers(steps, steps[2]).map(function (s) { return s.number; }), [0, 1]);
});

test('a query still being answered shows no answer yet', function () {
  const html = load().answersHtml(step(0, null, { moment: 'asked', answers: [] }), 500);
  assert.ok(html.indexOf('qs-waiting') >= 0);
});

test('the first answer of an answered query is marked as the one taken', function () {
  const html = load().answersHtml(step(0, null, { answers: ['first', 'second'] }), 500);
  assert.ok(html.indexOf('qs-answer qs-in qs-first" style="animation-delay:0ms">first') >= 0);
});

// %% where a query is asked
const PLAN = {
  kind: 'plan being resolved', title: 'put the cylinder into its hole', statement: 'Generate a SortPieceAction',
  variables: [
    { name: 'piece', role: 'answered', values: ['cylinder 1'] },
    { name: 'side', role: 'being answered', values: [] },
  ],
};
const SOUGHT = { name: 'hole', role: 'sought', values: [], kind: 'SeenHole', looked_at: null };

test('the stack runs from the enclosing statements through the asking queries to the query', function () {
  const QuerySteps = load();
  const asker = step(0, null, { variables: [SOUGHT] });
  const asked = step(1, 0, { enclosing: [PLAN], variables: [SOUGHT] });
  const html = QuerySteps.stackHtml([asker, asked], asked);
  const order = [PLAN.title, 'query #' + (asker.number + 1), 'this query #' + (asked.number + 1)]
    .map(function (text) { return html.indexOf(text); });
  assert.ok(order.every(function (at) { return at >= 0; }));
  assert.deepStrictEqual(order.slice().sort(function (a, b) { return a - b; }), order);
});

test('each part of an enclosing statement shows what it holds so far', function () {
  const html = load().stackHtml([], step(0, null, { enclosing: [PLAN], variables: [] }));
  assert.ok(html.indexOf('<b>piece</b><i>cylinder 1</i>') >= 0);
  assert.ok(html.indexOf('qs-part qs-r-asking" title="being answered"><b>side</b>') >= 0);
});

test('a sought variable is open until the query is answered', function () {
  const QuerySteps = load();
  const asked = QuerySteps.variablesHtml(step(0, null, { moment: 'asked', variables: [SOUGHT] }));
  const answered = QuerySteps.variablesHtml(step(0, null, {
    variables: [Object.assign({}, SOUGHT, { values: ['cylinder hole 1'] })],
  }));
  assert.ok(asked.indexOf('qs-pending') >= 0);
  assert.ok(answered.indexOf('<i>cylinder hole 1</i>') >= 0);
});
