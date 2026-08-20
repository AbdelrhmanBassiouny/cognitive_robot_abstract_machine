PR #182 (draft) — `where-query-rooted-attribute-no-filter`, wave 1 of the
`match-query-ergonomics` plan. This session handled two review rounds.

**Round 1 (2026-08-20): why not `apply_mapping_on_external_root`?**
- Measured: it rebuilds `Attribute`/`Index`/`Call` chains onto a symbolic root,
  but `FlatVariable` raises `TypeError: 'Attribute' object is not iterable`.
- Added `test_query_rooted_condition_through_a_flattened_attribute_filters`
  (`c1206318`). Replied; left the thread open.

**Round 2: "is it a smell in flat_variable or CanBehaveLikeAVariable? be critical."**
Chasing it found a real bug in my own `_reroot_on_`.
- `FlatVariable` is an outlier for two independent reasons: it is the only
  one-to-many mapping (so `apply_mapping_on_external_root`'s `next(...)` is
  already lossy on *real* values — measured, drops all but the first drawer),
  and it has no traced operator.
- `__iter__ = None` is a guard, not a smell: removing it re-enables the legacy
  `__getitem__` protocol, so `iter(var)` yields `Cabinet[0], Cabinet[1], …`
  forever.
- The bug: `_reroot_on_` rebuilt everything through `_get_mapped_variable_`, so
  two flattenings of one attribute collapsed into one node and `a != b` became
  `a != a` (query-rooted returned 0 where variable-rooted returned 1).
- Fixed in `b88a7e81`: a flattening rebuilds as a fresh node, every mapping
  rebuilds once per root so sharing survives, and `_mapping_arguments_` is
  replaced by a per-subclass `_rebuild_on_` (which also drops the positional
  constructor coupling). Two tests pin both directions.
- Full krrood suite green (2157 passed; 2 `test_object_diagram` failures are
  this container missing the Graphviz `dot` binary).
- Plan manifest + roadmap §10 saved; dashboard republished; PR description
  updated.

**Next / outstanding**
- Review thread left open for the developer, with two questions raised:
  (a) `apply_mapping_on_external_root`'s `next(...)` truncation is a latent bug
  for its five callers in `parametrization/feature_extraction` — own issue?
  (b) the projection/iteration split is still implicit in the hierarchy;
  making it explicit is a wider refactor than this bug fix.
- CI: `test_each_lib (experiments)` fails on a 300s ROS
  `/semantic_digital_twin/fetch_world` timeout in
  `test_real_stretch_demo_process_boundary.py` — unrelated to this diff. Not
  monitored; prompt if it needs handling.
