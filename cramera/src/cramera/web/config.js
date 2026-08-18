/* ============================================================================
 * config.js — *which* panels are shown *where*. This is the file you edit to swap
 * a visualization: remove an id, add your own (define it via Panels.define in
 * a new panels/<name>/panel.js and include that script in index.html).
 *
 * Slots are the data-slot elements in index.html ('left', 'right'); a slot
 * with several entries stacks them vertically. An entry is either a panel id or
 * {tabs: [{panel, label}, …]} — several panels sharing one frame, one shown at a
 * time (core/panel_tabs.js).
 * ==========================================================================*/
window.CRAMERA_CONFIG = {
  layout: {
    left: ['robot-scene'],
    right: ['eql', {
      tabs: [
        { panel: 'graph', label: 'Graph' },
        { panel: 'event-timeline', label: 'Events' },
      ],
    }],
  },
};
