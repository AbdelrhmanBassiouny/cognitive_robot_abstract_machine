/* ============================================================================
 * core/run_control.js — the running demo's state, as buttons and a status line.
 *
 * The bridge publishes a handful of flags (paused, looping, restart_pending,
 * activity, iteration). Turning those into what the viewer shows is decided here
 * and nowhere else, so a panel only renders what it is handed.
 * ==========================================================================*/
(function (window) {
  'use strict';

  //: the loop button reads the same either way; only its active state differs, so
  //: turning looping on and off is one control rather than two
  const LOOP_LABEL = '∞ Loop';

  function buttonsFor(control) {
    if (!control) return [];
    return [
      control.paused
        ? { command: 'resume', label: '▶ Resume', title: 'Let the run carry on from where it stopped' }
        : { command: 'pause', label: '⏸ Pause', title: 'Freeze the run where it stands, so it can be asked about' },
      {
        command: 'restart',
        label: '⟲ Restart',
        title: 'Run the whole thing again from the start, at the end of the current attempt',
        pending: !!control.restart_pending,
      },
      control.looping
        ? { command: 'disable_loop', label: LOOP_LABEL, title: 'Stop after the run in progress', active: true }
        : { command: 'enable_loop', label: LOOP_LABEL, title: 'Keep starting a new run each time one finishes', active: false },
    ];
  }

  function statusOf(control) {
    if (!control) return '';
    const parts = [control.restart_pending ? 'restarting' : (control.paused ? 'paused' : control.activity)];
    if (control.looping) parts.push('looping');
    parts.push('run ' + control.iteration);
    return parts.join(' · ');
  }

  window.RunControl = { buttonsFor: buttonsFor, statusOf: statusOf };
})(window);
