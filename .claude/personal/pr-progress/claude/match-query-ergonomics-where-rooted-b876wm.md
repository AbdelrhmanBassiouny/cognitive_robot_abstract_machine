PR #182 (draft) — `where-query-rooted-attribute-no-filter`, wave 1 of the
`match-query-ergonomics` plan. This session handled the 2026-08-20 review round.

**Plan for this round**
1. Answer the review thread on `_reroot_on_` (why not `apply_mapping_on_external_root`,
   and is `_mapping_arguments_` needed) with a measurement, not an opinion.
2. Cover whatever the measurement exposes with a test.
3. Record the outcome on the plan and republish the dashboard.

**Done**
- Measured the suggestion: it rebuilds `Attribute`/`Index`/`Call` chains onto a
  symbolic root, but `FlatVariable` raises `TypeError: 'Attribute' object is not
  iterable` because `CanBehaveLikeAVariable.__iter__` is `None` on purpose.
- Added `test_query_rooted_condition_through_a_flattened_attribute_filters`
  (commit `c1206318`, pushed) — the only one of the seven that fails under the
  suggested reuse, and one of six that fail before the fix itself.
- Full `test/krrood_test/test_eql` suite green locally (1186 passed, 3 skipped).
- Replied on the review thread and left it open: the answer differs from what it
  asked, so the call is the developer's. PR description's Tests section updated.
- Plan manifest + roadmap section 9 updated and saved; dashboard republished.

**Next / outstanding**
- The review thread is open, waiting on the developer: keep `_reroot_on_` +
  `_mapping_arguments_`, or teach `_apply_mapping_` about symbolic values (or
  re-enable `__iter__`) and drop them, or make a flattened query-rooted condition
  raise instead of working.
- CI: `test_each_lib (experiments)` fails on a 300s ROS
  `/semantic_digital_twin/fetch_world` timeout in
  `test_real_stretch_demo_process_boundary.py`. `main` was green at the same base,
  but nothing in this diff leaves `krrood/entity_query_language`; the `c1206318`
  push re-runs it. Not monitored — per notes, prompt if it needs handling.
