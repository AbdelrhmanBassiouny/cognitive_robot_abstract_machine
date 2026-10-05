Branch claude/transport-reads-what-its-steps-state, draft PR #494 on the fork, base
rip_grasp_descriptions (= a copy of cram2#588's head 689095c099, LucaKro's
rip_grasp_descriptions). Started 2026-10-05.

Ask: TransportAction.transported_object / carrying_arm (from #588) read their values with
_kwargs_["..."]. The user wants it string-free, using the EQL path already written on the
step when the step is a Match.

- [x] krrood change (also its own draft PR #493 off main, branch
      claude/access-path-reads-what-a-pattern-states): apply_mapping_on_external_root reads a
      pattern's stated value on an attribute step (HasFactoryAndKwargs._stated_values_,
      SingleValueMapping/Attribute._apply_mapping_on_external_value_). 4 tests in
      test_access_path_values.py; full krrood suite green (2635 passed).
- [x] both krrood commits cherry-picked here; both properties rewritten as
      `self.place.place.object_designator` + `apply_mapping_on_external_root(self.place)`
      when self.place is a Match. test_transporting.py 32 passed.
- [x] review thread 4185265491 (mapped_variable.py, Attribute's isinstance on
      HasFactoryAndKwargs): user asked for a shared mixin so the if goes away. Replied
      (r4185287354) that the check can only move (values on a path are arbitrary objects);
      offered 1 value-side double dispatch, 2 singledispatchmethod, 3 keep. User chose 3
      (keep as is, no commit); replied on the thread, left open for the user to close.
- [ ] user review. test_multi_robot_action_designator.py cannot run locally (Stretch URDF
      not installed). If #588 moves, restack this onto its new head and refresh
      rip_grasp_descriptions on the fork.
