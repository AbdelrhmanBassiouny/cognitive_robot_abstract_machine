/* ============================================================================
 * core/perform.js — a queried action, as a button and a status line.
 *
 * The bridge publishes what the demo is doing with the actions asked of it (which one
 * it is carrying out, which are still waiting). Turning that into what the viewer shows
 * is decided here and nowhere else, so a panel only renders what it is handed.
 * ==========================================================================*/
(function (window) {
  'use strict';

  const OFFERED_LABEL = '⏵ perform';
  const WAITING_LABEL = '⏳ waiting';
  const PERFORMING_LABEL = '⚙ performing';

  function isWaiting(action, state) {
    return (state.requested || []).indexOf(action.name) >= 0;
  }

  // the button a row's action gets, or null for a row naming no action. An action the
  // demo already has in hand is shown as such rather than offered a second time.
  function buttonFor(action, state) {
    if (!action) return null;
    const doing = state || {};
    if (doing.performing === action.name) {
      return { label: PERFORMING_LABEL, title: 'the robot is doing this now', disabled: true };
    }
    if (isWaiting(action, doing)) {
      return { label: WAITING_LABEL, title: 'asked for; waiting for the robot', disabled: true };
    }
    return {
      label: OFFERED_LABEL,
      title: 'have the robot ' + action.description,
      disabled: false,
    };
  }

  function statusOf(state) {
    if (!state) return '';
    const parts = [];
    if (state.performing) parts.push('performing ' + state.performing);
    const waiting = (state.requested || []).length;
    if (waiting) parts.push(waiting + ' waiting');
    return parts.join(' · ');
  }

  window.PerformControl = { buttonFor: buttonFor, statusOf: statusOf };
})(window);
