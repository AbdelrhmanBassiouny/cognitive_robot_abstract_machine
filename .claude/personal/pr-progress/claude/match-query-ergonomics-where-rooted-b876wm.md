PR #182 (draft) — `where-query-rooted-attribute-no-filter`, wave 1 of the
`match-query-ergonomics` plan. This session handled three review rounds.

**Round 1: why not `apply_mapping_on_external_root`?**
Measured: it rebuilds `Attribute`/`Index`/`Call` chains onto a symbolic root, but
`FlatVariable` raises `TypeError: 'Attribute' object is not iterable`. Added the
flatten test (`c1206318`). Thread later resolved by the developer.

**Round 2: "is it a smell in flat_variable or CanBehaveLikeAVariable? be critical."**
Chasing it found a real bug in my own `_reroot_on_`.
- `FlatVariable` is an outlier twice over: only one-to-many mapping (so
  `apply_mapping_on_external_root`'s `next(...)` is already lossy on real
  values), and no traced operator.
- `__iter__ = None` is a guard: removing it re-enables the legacy `__getitem__`
  protocol, yielding `Cabinet[0], Cabinet[1], …` forever.
- Bug: the rebuild routed everything through `_get_mapped_variable_`, collapsing
  two flattenings into one, so `a != b` became `a != a`.
- Fixed in `b88a7e81`: flattenings rebuild fresh, every mapping rebuilds once per
  root so sharing survives, `_mapping_arguments_` replaced by `_rebuild_on_`.

**Round 3: does `set_of_query[variable].attribute` work?**
It did not — and on `main` it returned the cross product (54 rows where 3 is
correct); round 1's `AmbiguousQueryAttribute` had made it a loud rejection.
- Fixed in `87fb3983`: re-rooting now replaces whichever expression stands for
  the row, so an index naming a selected variable re-roots onto it and the index
  step drops out. `_reroot_on_` takes the replaced expression; the rebuild memo
  is keyed by that pair.
- Two tests added; `AmbiguousQueryAttribute` still fires for a bare attribute and
  for an index by a non-selected variable, and its suggestion now offers
  `query[body].name`.
- Measured boundaries: `having` on a `set_of` fails identically for both
  spellings (pre-existing, untouched); name-string indexing is not a language
  spelling at all (`UnificationDict` is keyed by variable objects).

**State**: full krrood suite green (2159 passed; 2 `test_object_diagram` failures
are this container missing the Graphviz `dot` binary). Plan manifest + roadmap
§§10–11 saved, dashboard republished, PR description current.

**Next / outstanding**
- Round-3 thread left open: I asked whether name-based selection
  (`query["Body"]`) should become its own issue.
- Still open from round 2, raised but not acted on:
  (a) `apply_mapping_on_external_root`'s `next(...)` truncation is a latent bug
  for its five callers in `parametrization/feature_extraction`;
  (b) the projection/iteration split is still implicit in the hierarchy.
- CI: `test_each_lib (experiments)` fails on a 300s ROS
  `/semantic_digital_twin/fetch_world` timeout — unrelated to this diff. Not
  monitored; prompt if it needs handling.
