/* ============================================================================
 * core/live_attach.js — whether the viewer should attach itself to a demo.
 *
 * A viewer opened without ?scene= has no recording of its own to show, so it follows
 * whichever demo is reachable. The decision is made on every bridge probe rather than
 * once, because a demo restarted from the viewer stops answering and starts again: a
 * viewer that treated its first attach as final would sit on a dead world.
 *
 * Only an explicit detach is remembered — that is the one case where staying detached
 * is what was asked for.
 * ==========================================================================*/
(function () {
  'use strict';

  // state: {reachable, attached, sceneNamed, userDetached}
  function shouldAttach(state) {
    if (!state || !state.reachable || state.attached) return false;
    return !state.sceneNamed && !state.userDetached;
  }

  window.LiveAttach = { shouldAttach: shouldAttach };
})();
