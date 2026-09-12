## Branch claude/event-rules-eql-2syf3i — segmind composite detectors as EQL rules

Base: origin/claude/icra-experiments-simulation-pipeline-w4ep7n (#265)

### Plan
1. segmind/src/segmind/detectors/rules.py — `event_time_difference` (@symbolic_function),
   `interaction_event_detected_before` (not_/exists replacement for placing_pairs),
   and the shared interaction rule with `inference(event_type)(...)`, shift_threshold 15 s.
2. PickUpDetector / PlacingDetector rebuilt on that rule; `placing_pairs` removed from SegmindContext.
3. InsertionDetector (spatial_relation_detector_nodes.py) as the same rule shape over
   ContactEvent-with-a-hole + ContainmentEvent; `insertion_pairs` removed.
4. `DetectionEvent.participating_events()` via explain_inference + get_variable_nodes_of_given_type.
5. Tests: satisfied-conditions string, participating_events, verbalization sentence, timing.

### Done
- environment built (uv 0.12 sideloaded; .venv), baseline segmind suite green: 100 passed, 1 skipped.
- branch cut, sorinar remote added and reference file read.

### Next
- write failing tests first, then implement.

### Notes / deviations
- sorinar's literal `contains(context.holes, contact.with_object)` cannot match here:
  `SegmindContext.holes` holds `Aperture`s while a hole ContactEvent's `with_object` is the
  aperture's `Region` root. Rule binds an `Aperture` variable over `context.holes` and
  conditions `hole.root == contact.with_object`, which also supplies `through_hole`
  (existing test asserts `through_hole is hole`).
