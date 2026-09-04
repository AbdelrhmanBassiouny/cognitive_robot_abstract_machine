/* ============================================================================
 * core/panel_tabs.js — several panels sharing one slot, shown one at a time.
 *
 * A slot normally stacks its panels; a tab group puts them on top of each other
 * behind a bar of buttons instead, so a frame can hold more than one view
 * without shrinking either. config.js declares a group in place of a panel id:
 *
 *   right: ['eql', { tabs: [{panel: 'graph', label: 'Graph'},
 *                           {panel: 'event-timeline', label: 'Events'}] }]
 *
 * Every tab's panel is mounted at once rather than on first activation: a panel
 * only receives bus events while it is mounted, and one that started late would
 * have missed whatever happened before its tab was first opened.
 *
 * Bus events:
 *   emits  panel:shown {id}   a tab's panel became visible
 *
 * A hidden panel has no size, so anything drawing to a canvas has to redraw when
 * it hears that — the container cannot do it on the panel's behalf without
 * knowing what the panel draws with.
 * ==========================================================================*/
(function (global) {
  'use strict';

  /* Mount one tab group into `slotElement`.
   *
   * `tabs` are the group's entries as config.js declares them ({panel, label}).
   * `mountPanel(parentElement, id)` mounts one registered panel and returns its
   * root, or a falsy value if there is no such panel — the registry owns that
   * decision, so a tab is created only for a panel that really mounted.
   * `bus` is what becoming visible is announced on. */
  function mount(slotElement, tabs, mountPanel, bus) {
    const container = document.createElement('section');
    container.className = 'panel-tabs';
    const bar = document.createElement('div');
    bar.className = 'tab-bar';
    container.appendChild(bar);
    slotElement.appendChild(container);

    const mounted = [];   // {id, button, body}

    tabs.forEach(function (tab) {
      const body = document.createElement('div');
      body.className = 'tab-body';
      if (!mountPanel(body, tab.panel)) return;
      const button = document.createElement('button');
      button.dataset.panel = tab.panel;
      button.textContent = tab.label || tab.panel;
      bar.appendChild(button);
      container.appendChild(body);
      mounted.push({ id: tab.panel, button: button, body: body });
      button.addEventListener('click', function () { show(tab.panel); });
    });

    container.dataset.tabs = mounted.map(function (tab) { return tab.id; }).join(' ');

    let showing = null;

    function show(id) {
      if (id === showing) return;
      showing = id;
      mounted.forEach(function (tab) {
        const visible = tab.id === id;
        tab.body.style.display = visible ? '' : 'none';
        tab.button.classList.toggle('active', visible);
      });
      bus.emit('panel:shown', { id: id });
    }

    if (mounted.length) show(mounted[0].id);
  }

  global.PanelTabs = { mount: mount };
})(window);
