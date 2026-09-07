/* ============================================================================
 * core/timeline_layout.js — where an event and the now-bar land on the timeline.
 *
 * Kept here, as arithmetic on plain numbers, so panels/event_timeline/panel.js
 * is left with the DOM wiring alone — the same split core/split-sizing.js makes
 * against core/split-resize.js.
 *
 * Instants are seconds since the epoch, the unit the bridge sends them in.
 *
 * A run younger than the span is shown from its own start, so the now-bar sweeps
 * across an otherwise empty panel instead of sitting pinned at the right edge
 * with nothing behind it. Once the run outgrows the span the bounds scroll with
 * it and the events slide leftwards instead.
 * ==========================================================================*/
(function (global) {
  'use strict';

  const NEAR_EDGE = 0.2;
  /* How close to a side edge a mark has to be for its summary to be pushed
     inwards rather than centred over it. */

  const ROOM_ABOVE = 0.4;
  /* How far down the panel a mark has to be for its summary to fit above it. */

  global.TimelineLayout = {
    /* The stretch of time on screen, as {start, end}, for a run that began at
       `runStart`, at the instant `now`, showing `span` seconds at a time. */
    boundsFor: function (runStart, now, span) {
      if (now - runStart <= span) return { start: runStart, end: runStart + span };
      return { start: now - span, end: now };
    },

    /* How far across a panel of `width` pixels `instant` lands. */
    horizontalPosition: function (bounds, instant, width) {
      const duration = bounds.end - bounds.start;
      if (!(duration > 0)) return 0;
      return (instant - bounds.start) / duration * width;
    },

    /* Whether `instant` is on screen at all. */
    isInside: function (bounds, instant) {
      return instant >= bounds.start && instant <= bounds.end;
    },

    /* The kinds of event to give a lane each, in the order they were first
       detected — the timeline learns its lanes from what arrives, since the
       viewer knows nothing of the demo's own catalogue of events. */
    kindsOf: function (events) {
      const lanes = [];
      events.forEach(function (event) {
        if (lanes.indexOf(event.kind) < 0) lanes.push(event.kind);
      });
      return lanes;
    },

    /* The vertical middle of lane `index` of `count`, down a panel of `height`
       pixels. With no lanes at all the whole height is the one lane. */
    laneCentre: function (index, count, height) {
      const lanes = count > 0 ? count : 1;
      return (index + 0.5) / lanes * height;
    },

    /* Which way a summary anchored at (`left`, `top`) has to be drawn to stay
       inside a panel of `width` by `height`: away from whichever edge it is
       against, and centred over its mark wherever there is room either side. */
    summaryPlacement: function (left, top, width, height) {
      const across = width > 0 ? left / width : 0;
      const down = height > 0 ? top / height : 0;
      return {
        horizontal: across < NEAR_EDGE ? 'from-left'
          : (across > 1 - NEAR_EDGE ? 'from-right' : 'centred'),
        vertical: down < ROOM_ABOVE ? 'below' : 'above',
      };
    },
  };
})(window);
