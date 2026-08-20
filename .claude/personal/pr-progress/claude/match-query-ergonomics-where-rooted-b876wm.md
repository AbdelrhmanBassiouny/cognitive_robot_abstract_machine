PR #182 (draft) — `where-query-rooted-attribute-no-filter`, wave 1 of the
`match-query-ergonomics` plan. Four review rounds handled; all threads resolved.

**Round 1 — why not `apply_mapping_on_external_root`?** It rebuilds
`Attribute`/`Index`/`Call` onto a symbolic root but `FlatVariable` raises
`TypeError`. Flatten test `c1206318`. Resolved by the developer.

**Round 2 — "is it a smell? be critical."** Found a real bug in my own rebuild:
everything went through `_get_mapped_variable_`, collapsing two flattenings into
one so `a != b` became `a != a`. `b88a7e81`: flattenings rebuild fresh, sharing
preserved per root, `_mapping_arguments_` replaced by `_rebuild_on_`. Also
established `__iter__ = None` is a guard against the legacy `__getitem__`
protocol, not a smell.

**Round 3 — `set_of_query[variable].attribute`.** Did not work; on `main` it
returned the cross product (54 rows where 3 is right). `87fb3983`: re-rooting
replaces whichever expression stands for the row.

**Round 4 — three comments, all in `62ec184aa`:**
- Naming a selection is now `SetOf`-only (polymorphic override, not an isinstance
  check). Indexing an `entity` indexes its selected *value* — it was silently
  dropping the index step.
- `SetOf.__getitem__` validates the key and raises a new `UnselectedQueryVariable`
  at the index rather than at the condition. This also settles the name-string
  question: `query["Body"]` now fails where it is written.
- The rebuild memo key is a `Rerooting` frozen `kw_only` dataclass.

**State**: full krrood suite green (2160 passed; 2 `test_object_diagram` failures
are this container missing the Graphviz `dot` binary). All five review threads
resolved. Plan manifest + roadmap §§10–12 saved, dashboard republished, PR
description current.

**Next / outstanding**
- Raised, not acted on (developer's call):
  (a) `apply_mapping_on_external_root`'s `next(...)` truncation is a latent bug
  for its five callers in `parametrization/feature_extraction`;
  (b) the projection/iteration split is still implicit in the hierarchy;
  (c) `having` without `grouped_by` crashes on a `None` deref
  (`query.py:628`) instead of raising a usage error — on any query type, not
  just `set_of`. Verified a one-line fix (extend the auto-`GroupedByBuilder`
  condition to include a present having builder) turns it into the existing
  `NonAggregatorInHavingConditionsError`. Offered as its own focused PR;
  awaiting a decision.
- CI: `test_each_lib (experiments)` fails on a 300s ROS
  `/semantic_digital_twin/fetch_world` timeout — unrelated. Not monitored.
