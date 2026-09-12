## Branch claude/event-rules-eql-2syf3i -- segmind composite detectors as EQL rules

Base: origin/claude/icra-experiments-simulation-pipeline-w4ep7n (#265)
PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/324 (draft)

### Done
- `segmind/src/segmind/detectors/rules.py`: `TimeDifference`, `ObjectsInsertedInto`,
  `interaction_event_detected_before`, `interaction_rule`, `insertion_rule`. shift_threshold 15 s.
- PickUpDetector / PlacingDetector / InsertionDetector each one call to a rule;
  `placing_pairs` and `insertion_pairs` removed from SegmindContext.
- `DetectionEvent.participating_events()` via explain_inference.
- `test/segmind_test/test_detectors/test_event_rules.py`: conditions string, participating
  events, verbalization, inserted-into identity, timing vs. the scan (bounded by control_dt).
- Review round 1 (thread r3996249357, "make these SymbolicCallable/SymbolicFunction classes
  with custom verbalization"): the two @symbolic_functions are now SymbolicFunction classes
  with `_verbalization_fragment_` (TimeDifference -> "the time difference between A and B";
  ObjectsInsertedInto -> the containing object itself). The operands elsewhere in the sentence
  are named directly now instead of through a path into the function's fields. Two per-operation
  verbalization tests added; the three rule-sentence tests updated. Commit f35dd080bb.
- `segmind/scripts/generate_orm.py` ignores `recursive_subclasses(SymbolicCallable)`, as
  semantic_digital_twin's generator does. Unverified locally (ORM build needs geometry_msgs).
- Suites green: test/segmind_test + test/experiments_test/test_montessori_event_monitoring.py
  -> 129 passed, 1 skipped (`--orm-build=never`).

### Next
- Review thread r3996249357 left OPEN on purpose: replied with what changed and asked whether
  `interaction_event_detected_before` should become a Predicate too (it stays the declarative
  `not_(exists(...))` the port specifies, and already verbalizes naturally). Resolve once he
  answers.

### Notes
- Deviation from the sorinar port: `contains(context.holes, contact.with_object)` cannot match
  (holes are Apertures, a hole ContactEvent's with_object is the aperture's Region root). Rule
  binds an Aperture variable and conditions `hole.root == contact.with_object`, which also
  supplies `through_hole`.
- Defect found and fixed: `inference(...)(inserted_into_objects=[attr])` leaves the list element
  symbolic. Built by a symbolic function now; asserted by identity (== is fooled by Attribute).
- PickUpEvent now carries with_object (the lost support), which the scan left unset.
- Local env: ROS message packages absent, so the ORM interface build fails (same on the base
  branch). Ran with `--orm-build=never`; the rest of test/experiments_test needs rclpy.
- Environment build: uv 0.12.13 sideloaded into the scratchpad (repo's pyproject needs > 0.8.17),
  then `uv sync --extra dev`; interpreter at `.venv/bin/python`.
