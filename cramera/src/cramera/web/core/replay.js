/* ============================================================================
 * core/replay.js — replaying a recorded slice of the live demo.
 *
 * The pure logic of the replay popup: reading the replayed moment out of a URL,
 * building the popup URL that carries it (and an explicit bridge address) into a
 * fresh viewer, and mapping wall-clock playback time onto recorded frames. A
 * moment is the window to play plus what it shows — the event's own name and the
 * objects it happened to, which the popup annotates the clip with. The popup
 * itself is the ordinary viewer page mounted in replay mode; nothing here touches
 * the DOM.
 * ==========================================================================*/
(function () {
  'use strict';

  // how long the playback rests on the last frame before looping, in seconds
  const LOOP_HOLD_SECONDS = 1.0;

  // what the popup URL names the replayed event and its objects
  const EVENT_PARAMETER = 'event';
  const OBJECTS_PARAMETER = 'objects';
  // object names come from body names, which never carry one
  const OBJECT_SEPARATOR = ',';

  // one parameter's decoded value, or '' when the URL does not carry it
  function parameter(search, name) {
    const match = new RegExp('[?&]' + name + '=([^&]*)').exec(search || '');
    return match ? decodeURIComponent(match[1]) : '';
  }

  // ?replay=<start>,<end> (epoch seconds), with the event it shows -> the replayed
  // moment, or null when the window is absent or unusable. An unusable window is
  // treated as "not a replay page" rather than an error: the viewer then simply
  // behaves as the ordinary live page. A moment with no event named is still a
  // replay; it just has nothing to annotate.
  function fromSearch(search) {
    const match = /[?&]replay=([^&]+)/.exec(search || '');
    if (!match) return null;
    const parts = decodeURIComponent(match[1]).split(',');
    if (parts.length !== 2) return null;
    const start = parseFloat(parts[0]);
    const end = parseFloat(parts[1]);
    if (!isFinite(start) || !isFinite(end) || end <= start) return null;
    const objects = parameter(search, OBJECTS_PARAMETER);
    return {
      start: start,
      end: end,
      label: parameter(search, EVENT_PARAMETER),
      objects: objects ? objects.split(OBJECT_SEPARATOR) : [],
    };
  }

  // the URL a popup replays `moment` at, carrying the event it shows so the popup
  // can annotate the clip; an explicit live= bridge address in the opener's search
  // is carried along so the popup asks the same bridge
  function popupUrl(pathname, search, moment) {
    const live = /[?&](live=[\w.:-]+)/.exec(search || '');
    const objects = moment.objects || [];
    return pathname + '?replay=' + moment.start + ',' + moment.end +
      (live ? '&' + live[1] : '') +
      (moment.label ? '&' + EVENT_PARAMETER + '=' + encodeURIComponent(moment.label) : '') +
      (objects.length
        ? '&' + OBJECTS_PARAMETER + '=' + encodeURIComponent(objects.join(OBJECT_SEPARATOR))
        : '');
  }

  // how long the recorded clip runs, in seconds
  function duration(frames) {
    if (!frames || !frames.length) return 0;
    return frames[frames.length - 1].at - frames[0].at;
  }

  // the frame on screen after `elapsed` seconds of looping playback: the newest
  // frame not later than the playback time, holding the last frame for
  // LOOP_HOLD_SECONDS before starting over
  function frameAt(frames, elapsed) {
    if (!frames || !frames.length) return null;
    const at = frames[0].at + (elapsed % (duration(frames) + LOOP_HOLD_SECONDS));
    let shown = frames[0];
    for (let index = 0; index < frames.length; index++) {
      if (frames[index].at > at) break;
      shown = frames[index];
    }
    return shown;
  }

  // '12:00:25 – 12:00:35' — the wall-clock span the popup's badge names the clip by
  function timeSpan(moment) {
    function clock(at) {
      const date = new Date(at * 1000);
      function two(value) { return (value < 10 ? '0' : '') + value; }
      return two(date.getHours()) + ':' + two(date.getMinutes()) + ':' + two(date.getSeconds());
    }
    return clock(moment.start) + ' – ' + clock(moment.end);
  }

  window.Replay = {
    fromSearch: fromSearch,
    popupUrl: popupUrl,
    duration: duration,
    frameAt: frameAt,
    timeSpan: timeSpan,
  };
})();
