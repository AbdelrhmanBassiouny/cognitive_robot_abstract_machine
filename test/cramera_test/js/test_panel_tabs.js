// Unit tests for web/core/panel_tabs.js and the tab groups core/registry.js mounts
// through it (node:test).
//
// The contract a tab group has to keep: every tab's panel is mounted up front, exactly
// one is visible, and becoming visible is announced on the bus — a panel that renders to
// a canvas has no size while it is hidden and has to be told when it gains one.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', '..', '..', 'cramera', 'src', 'cramera', 'web');

// %% a DOM stub with the parts a tab bar touches
function makeElement(tag) {
  const classes = {};
  return {
    tagName: tag,
    children: [],
    dataset: {},
    className: '',
    innerHTML: '',
    textContent: '',
    title: '',
    style: {},
    listeners: {},
    classList: {
      add(name) { classes[name] = true; },
      remove(name) { delete classes[name]; },
      toggle(name, on) { if (on) classes[name] = true; else delete classes[name]; },
      contains(name) { return !!classes[name]; },
    },
    appendChild(child) { this.children.push(child); return child; },
    addEventListener(event, callback) { this.listeners[event] = callback; },
    click() { if (this.listeners.click) this.listeners.click(); },
  };
}

function freshDom() {
  const slots = {};
  global.document = {
    createElement: makeElement,
    querySelector(selector) {
      const match = /\[data-slot="(.+)"\]/.exec(selector);
      if (!match) return null;
      if (!slots[match[1]]) slots[match[1]] = makeElement('div');
      return slots[match[1]];
    },
  };
  global.window = {};
  return slots;
}

function load(file) {
  new Function(fs.readFileSync(path.join(WEB, file), 'utf8'))();
}

function loadShell() {
  const slots = freshDom();
  load('core/bus.js');
  load('core/panel_tabs.js');
  load('core/registry.js');
  return slots;
}

// The container a tab group mounts into a slot, and the tab bar's buttons.
function groupIn(slot) {
  const container = slot.children[0];
  return { container: container, buttons: container.children[0].children };
}

// Where each tab's panel actually ended up: the tab body is the panel root's parent.
function bodyOf(container, index) {
  return container.children[index + 1];
}

function mountTwoTabs(labels) {
  const slots = loadShell();
  const mountedInto = {};
  ['graph', 'timeline'].forEach(function (id) {
    window.Panels.define(id, function (root) { mountedInto[id] = root; });
  });
  window.CRAMERA_CONFIG = {
    layout: {
      right: [{
        tabs: [
          { panel: 'graph', label: (labels || {}).graph || 'Graph' },
          { panel: 'timeline', label: (labels || {}).timeline || 'Events' },
        ],
      }],
    },
  };
  window.Panels.boot();
  return { slots: slots, mountedInto: mountedInto };
}

// %% mounting
test('every tab of a group is mounted up front, not on first activation', function () {
  const { mountedInto } = mountTwoTabs();
  assert.deepStrictEqual(window.Panels.mounted(), ['graph', 'timeline']);
  assert.ok(mountedInto.graph);
  assert.ok(mountedInto.timeline);
});

test('a tab group is one child of the slot, marked as a group rather than a panel', function () {
  const { slots } = mountTwoTabs();
  const { container } = groupIn(slots.right);
  assert.strictEqual(slots.right.children.length, 1);
  assert.strictEqual(container.dataset.panel, undefined);
  assert.strictEqual(container.dataset.tabs, 'graph timeline');
});

test('each tab button carries its configured label', function () {
  const { slots } = mountTwoTabs({ graph: 'Knowledge', timeline: 'Detections' });
  const { buttons } = groupIn(slots.right);
  assert.deepStrictEqual(buttons.map(function (b) { return b.textContent; }),
    ['Knowledge', 'Detections']);
});

// %% one visible at a time
test('the first tab is shown and every other is hidden', function () {
  const { slots } = mountTwoTabs();
  const { container, buttons } = groupIn(slots.right);
  assert.strictEqual(bodyOf(container, 0).style.display, '');
  assert.strictEqual(bodyOf(container, 1).style.display, 'none');
  assert.strictEqual(buttons[0].classList.contains('active'), true);
  assert.strictEqual(buttons[1].classList.contains('active'), false);
});

test('clicking a tab shows its panel and hides the one that was showing', function () {
  const { slots } = mountTwoTabs();
  const { container, buttons } = groupIn(slots.right);

  buttons[1].click();

  assert.strictEqual(bodyOf(container, 0).style.display, 'none');
  assert.strictEqual(bodyOf(container, 1).style.display, '');
  assert.strictEqual(buttons[0].classList.contains('active'), false);
  assert.strictEqual(buttons[1].classList.contains('active'), true);
});

// %% announcing what became visible
test('the tab shown at boot is announced, so a panel can size itself', function () {
  const slots = loadShell();
  const shown = [];
  window.Bus.on('panel:shown', function (payload) { shown.push(payload.id); });
  window.Panels.define('graph', function () {});
  window.Panels.define('timeline', function () {});
  window.CRAMERA_CONFIG = {
    layout: { right: [{ tabs: [{ panel: 'graph' }, { panel: 'timeline' }] }] },
  };
  window.Panels.boot();
  assert.deepStrictEqual(shown, ['graph']);
});

test('switching tabs announces the panel that became visible', function () {
  const { slots } = mountTwoTabs();
  const shown = [];
  window.Bus.on('panel:shown', function (payload) { shown.push(payload.id); });

  groupIn(slots.right).buttons[1].click();

  assert.deepStrictEqual(shown, ['timeline']);
});

test('clicking the tab already showing announces nothing', function () {
  const { slots } = mountTwoTabs();
  const shown = [];
  window.Bus.on('panel:shown', function (payload) { shown.push(payload.id); });

  groupIn(slots.right).buttons[0].click();

  assert.deepStrictEqual(shown, []);
});

// %% a group is as forgiving as a plain slot
test('an unknown panel in a group gets no tab and the rest still mount', function () {
  const slots = loadShell();
  window.Panels.define('real', function () {});
  window.CRAMERA_CONFIG = {
    layout: { right: [{ tabs: [{ panel: 'ghost' }, { panel: 'real' }] }] },
  };
  const errors = [];
  const err = console.error;
  console.error = function (message) { errors.push(String(message)); };
  window.Panels.boot();
  console.error = err;

  const { container, buttons } = groupIn(slots.right);
  assert.deepStrictEqual(window.Panels.mounted(), ['real']);
  assert.strictEqual(buttons.length, 1);
  assert.strictEqual(container.dataset.tabs, 'real');
  assert.ok(errors.some(function (message) { return message.indexOf('ghost') >= 0; }));
});

test('a slot mixing a plain panel with a group keeps both', function () {
  const slots = loadShell();
  ['eql', 'graph'].forEach(function (id) {
    window.Panels.define(id, function () {});
  });
  window.CRAMERA_CONFIG = {
    layout: { right: ['eql', { tabs: [{ panel: 'graph' }] }] },
  };
  window.Panels.boot();

  assert.deepStrictEqual(window.Panels.mounted(), ['eql', 'graph']);
  assert.strictEqual(slots.right.children.length, 2);
  assert.strictEqual(slots.right.children[0].dataset.panel, 'eql');
  assert.strictEqual(slots.right.children[1].dataset.tabs, 'graph');
});

test('unmounting tears down the panels inside a group too', function () {
  const slots = loadShell();
  const destroyed = [];
  ['graph', 'timeline'].forEach(function (id) {
    window.Panels.define(id, function () {
      return { destroy: function () { destroyed.push(id); } };
    });
  });
  window.CRAMERA_CONFIG = {
    layout: { right: [{ tabs: [{ panel: 'graph' }, { panel: 'timeline' }] }] },
  };
  window.Panels.boot();
  window.Panels.unmountAll();

  assert.deepStrictEqual(destroyed, ['graph', 'timeline']);
  assert.deepStrictEqual(window.Panels.mounted(), []);
});
