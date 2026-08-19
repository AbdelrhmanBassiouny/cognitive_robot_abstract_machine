# PR #182 — query-rooted attribute in a query's own conditions does not filter

Plan item `match-query-ergonomics` / `where-query-rooted-attribute-no-filter`.
Branch `claude/match-query-ergonomics-where-rooted-b876wm`, off `main`, draft PR
#182, `bug` label. Roadmap §8 carries the reasoning.

## Plan

1. Failing tests first (TDD), in a dedicated module for the behaviour:
   - query-rooted `where` condition filters, equal to the variable-rooted result
   - it does not multiply result rows (`>= -1` over N rows returns N, not N*N)
   - the `Match` spelling `match.where(match.expression.<attr> ...)` filters
   - multi-variable query raises `AmbiguousQueryAttribute`
   - a chain rooted at *another* query keeps uncorrelated subquery semantics
2. `MappedVariable._reroot_on_` + per-subclass `_mapping_arguments_` so a chain
   can be rebuilt on a different base.
3. `Query.where` / `Query.having` re-root chains rooted at the same query onto
   the selected variable; raise `AmbiguousQueryAttribute` when the query selects
   more than one variable.
4. New `AmbiguousQueryAttribute(UsageError)` in `exceptions.py`.
5. Run the full krrood suite; `scripts/format_docstrings.py` on touched files.

## Done

- Item bootstrapped: branch pushed, draft PR #182 opened with the `bug` label,
  manifest flipped to `in_progress`, roadmap §8 written.
- Bug reproduced and mechanism pinned (existential + cross product, not a
  dropped condition).
- Cross-check against `eql-existential-semantics` #137 done: it does not
  subsume this fix. To be recorded on both tracking issues.

## Next

- Implement steps 1-5 above.
- Post the #137 cross-check on issue 181 and issue 137.
- Republish `/plan-dashboard match-query-ergonomics` after the manifest change.

## Notes / hazards

- Self-reference must be detected by `_id_`, never `is`: attaching a mapped
  variable copies the query node (same `_id_`), and `Query._compile_` replays
  conditions onto a product that also shares the `_id_`.
- Must not touch the *selection* path: `set_of(match.expression.parent, ...)`
  relies on the chain staying rooted at the lowered query so the match's
  conditions come with it (roadmap §3/§4).
- Environment: krrood is not installed in this container. Run tests with
  `PYTHONPATH=krrood/src`; deps were pip-installed by hand (omegaconf could not
  build, so anything importing it is unavailable here).
