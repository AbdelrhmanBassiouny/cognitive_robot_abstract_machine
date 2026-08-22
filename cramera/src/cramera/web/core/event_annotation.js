/* =============================================================================
 * event_annotation — where a replayed event's caption floats and how its arrows
 * reach the objects it happened to.
 *
 * A replay opened from an answer row shows one event, and the viewer says which:
 * a caption naming it floats over the objects the event involved, with an arrow
 * from the caption to each of them. Where the caption rests and how each arrow is
 * aimed is pure math and lives here; the panel only builds meshes out of it and
 * re-asks every frame, which is what keeps the tips on objects that are moving.
 * ==========================================================================*/
(function () {
  'use strict';

  const CAPTION_CLEARANCE = 0.3;   // gap between the tallest object and the caption, m
  const TIP_CLEARANCE = 0.03;      // gap between an arrow's tip and its object, m
  const HEAD_LENGTH = 0.07;        // the arrowhead cone's height, m
  const HEAD_RADIUS = 0.025;       // the arrowhead cone's base radius, m
  const SHAFT_RADIUS = 0.006;      // the arrow shaft's radius, m
  const COLOR = '#39d5c8';         // the highlight teal the rest of the UI uses

  // where the caption rests over the objects it names: centred over them, clear of
  // the tallest. `tops` are the objects' top points; no objects, no caption.
  function captionAnchor(tops) {
    if (!tops || !tops.length) return null;
    let x = 0, y = 0, highest = tops[0].z;
    tops.forEach(function (top) {
      x += top.x;
      y += top.y;
      if (top.z > highest) highest = top.z;
    });
    return { x: x / tops.length, y: y / tops.length, z: highest + CAPTION_CLEARANCE };
  }

  // the arrow from the caption at `from` down to the object top at `to`: the unit
  // direction to aim it along and the length of its shaft, the head taking the last
  // HEAD_LENGTH and the tip stopping TIP_CLEARANCE short of the object. An object
  // too close to leave room for the head gets no arrow.
  function arrowTo(from, to) {
    const span = { x: to.x - from.x, y: to.y - from.y, z: to.z - from.z };
    const distance = Math.sqrt(span.x * span.x + span.y * span.y + span.z * span.z);
    const shaftLength = distance - TIP_CLEARANCE - HEAD_LENGTH;
    if (shaftLength <= 0) return null;
    return {
      direction: { x: span.x / distance, y: span.y / distance, z: span.z / distance },
      shaftLength: shaftLength,
    };
  }

  window.EventAnnotation = {
    CAPTION_CLEARANCE: CAPTION_CLEARANCE,
    TIP_CLEARANCE: TIP_CLEARANCE,
    HEAD_LENGTH: HEAD_LENGTH,
    HEAD_RADIUS: HEAD_RADIUS,
    SHAFT_RADIUS: SHAFT_RADIUS,
    COLOR: COLOR,
    captionAnchor: captionAnchor,
    arrowTo: arrowTo,
  };
})();
