/* ============================================================================
 * core/panel-arrangement.js — where each Scene panel sits.
 *
 * Every panel is draggable by its header: drop it above or below another panel, or
 * into the other column, and the layout follows. The arrangement persists in the
 * browser's localStorage — install() replaces the configured layout with the stored
 * one before the panels mount, so every reload comes back to the same arrangement.
 *
 * The layout rules (normalizing a stored arrangement against the configured
 * panels, moving a panel to a slot position) are pure and testable under node;
 * only init() touches the page.
 * ==========================================================================*/
(function (global) {
  'use strict';

  const STORAGE_KEY = 'cramera.panel-arrangement';
  /* localStorage key the arrangement persists under, as JSON {slotName: [ids]}. */

  /* A stored arrangement, cleaned against what is actually configured: ids that
     left the configuration are dropped, ids new to the configuration appear at
     their configured spot, and slots stay in the configured order. */
  function read(storage, configuredLayout) {
    let stored = {};
    try {
      stored = JSON.parse(storage.getItem(STORAGE_KEY) || '{}') || {};
    } catch (error) {
      stored = {};   // an unreadable value means "the configured layout"
    }
    return normalize(stored, configuredLayout);
  }

  function normalize(stored, configuredLayout) {
    const configuredIds = allIds(configuredLayout);
    const layout = {};
    const placed = {};
    Object.keys(configuredLayout).forEach(function (slotName) {
      layout[slotName] = (stored[slotName] || []).filter(function (id) {
        const known = configuredIds.indexOf(id) !== -1 && !placed[id];
        if (known) placed[id] = true;
        return known;
      });
    });
    Object.keys(configuredLayout).forEach(function (slotName) {
      configuredLayout[slotName].forEach(function (id) {
        if (placed[id]) return;
        placed[id] = true;
        layout[slotName].push(id);
      });
    });
    return layout;
  }

  function write(storage, layout) {
    storage.setItem(STORAGE_KEY, JSON.stringify(layout));
  }

  /* The layout after moving one panel into a slot at a position. */
  function moved(layout, id, targetSlot, index) {
    const next = {};
    Object.keys(layout).forEach(function (slotName) {
      next[slotName] = layout[slotName].filter(function (other) { return other !== id; });
    });
    if (!(targetSlot in next)) return layout;
    const at = Math.max(0, Math.min(index, next[targetSlot].length));
    next[targetSlot].splice(at, 0, id);
    return next;
  }

  function allIds(layout) {
    return Object.keys(layout).reduce(function (ids, slotName) {
      return ids.concat(layout[slotName]);
    }, []);
  }

  // %% wiring the page

  /* Replace the configured layout with the stored arrangement, before boot. */
  function install() {
    const config = global.CRAMERA_CONFIG || {};
    if (!config.layout) return;
    config.layout = read(global.localStorage, config.layout);
  }

  /* Make every mounted panel draggable by its header and every slot a drop target. */
  function init() {
    document.querySelectorAll('[data-panel]').forEach(makeDraggable);
    document.querySelectorAll('[data-slot]').forEach(makeDropTarget);
  }

  function makeDraggable(panel) {
    const handle = panel.querySelector('.panel-head') || panel.firstElementChild || panel;
    handle.setAttribute('draggable', 'true');
    handle.style.cursor = 'grab';
    handle.addEventListener('dragstart', function (event) {
      event.dataTransfer.setData('text/panel-id', panel.dataset.panel);
      event.dataTransfer.effectAllowed = 'move';
      panel.classList.add('dragging');
    });
    handle.addEventListener('dragend', function () {
      panel.classList.remove('dragging');
      clearDropMarkers();
    });
  }

  function makeDropTarget(slot) {
    slot.addEventListener('dragover', function (event) {
      if (!event.dataTransfer.types.includes('text/panel-id')) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      clearDropMarkers();
      const before = insertionReference(slot, event.clientY);
      if (before) before.classList.add('drop-before');
      else slot.classList.add('drop-end');
    });
    slot.addEventListener('dragleave', function (event) {
      if (!slot.contains(event.relatedTarget)) clearDropMarkers();
    });
    slot.addEventListener('drop', function (event) {
      event.preventDefault();
      clearDropMarkers();
      const id = event.dataTransfer.getData('text/panel-id');
      const panel = document.querySelector('[data-panel="' + id + '"]');
      if (!panel) return;
      const before = insertionReference(slot, event.clientY);
      slot.insertBefore(panel, before);
      persistFromPage();
    });
  }

  /* The visible panel the drop would land in front of, or null for "at the end". */
  function insertionReference(slot, pointerY) {
    const panels = Array.from(slot.querySelectorAll('[data-panel]')).filter(function (panel) {
      return !panel.classList.contains('dragging') && !panel.classList.contains('hidden');
    });
    return panels.find(function (panel) {
      const box = panel.getBoundingClientRect();
      return pointerY < box.top + box.height / 2;
    }) || null;
  }

  function clearDropMarkers() {
    document.querySelectorAll('.drop-before').forEach(function (element) {
      element.classList.remove('drop-before');
    });
    document.querySelectorAll('.drop-end').forEach(function (element) {
      element.classList.remove('drop-end');
    });
  }

  /* Read the arrangement off the page, store it, and let the layout follow. */
  function persistFromPage() {
    const layout = {};
    document.querySelectorAll('[data-slot]').forEach(function (slot) {
      layout[slot.dataset.slot] = Array.from(slot.querySelectorAll('[data-panel]'))
        .map(function (panel) { return panel.dataset.panel; });
    });
    (global.CRAMERA_CONFIG || {}).layout = layout;
    write(global.localStorage, layout);
    if (global.PanelVisibility && global.PanelVisibility.refresh) {
      global.PanelVisibility.refresh();
    }
  }

  global.PanelArrangement = {
    STORAGE_KEY: STORAGE_KEY,
    read: read,
    write: write,
    normalize: normalize,
    moved: moved,
    install: install,
    init: init,
  };
})(typeof window !== 'undefined' ? window : this);
