/* ============================================================================
 * core/event_summary.js — what the timeline says about one detected event when
 * it is pointed at.
 *
 * Wording and time formatting only, on the plain payload the bridge sends, so
 * panels/event_timeline/panel.js is left with the DOM wiring alone — the same
 * split core/timeline_layout.js makes for the positions.
 * ==========================================================================*/
(function (global) {
  'use strict';

  const SECONDS_PER_MINUTE = 60;

  function padded(value) {
    return value < 10 ? '0' + value : String(value);
  }

  /* The wall-clock time of day an instant fell on, to the second. */
  function timeOfDay(secondsSinceEpoch) {
    const at = new Date(secondsSinceEpoch * 1000);
    return at.getHours() + ':' + padded(at.getMinutes()) + ':' + padded(at.getSeconds());
  }

  /* How far into the run an instant fell, as minutes and seconds. */
  function intoRun(seconds) {
    const elapsed = seconds > 0 ? seconds : 0;
    const minutes = Math.floor(elapsed / SECONDS_PER_MINUTE);
    const rest = elapsed - minutes * SECONDS_PER_MINUTE;
    return '+' + minutes + ':' + (rest < 10 ? '0' : '') + rest.toFixed(1);
  }

  global.EventSummary = {
    /* The few lines describing one detected event: what it was, what it happened
       to, and when. Everything is text ready to be shown, so nothing downstream
       has to know the payload's shape. */
    of: function (event) {
      return {
        kind: event.kind,
        objects: (event.participants || []).join(', '),
        time: timeOfDay(event.detected_at) + ' · ' + intoRun(event.seconds_into_run),
      };
    },
  };
})(window);
