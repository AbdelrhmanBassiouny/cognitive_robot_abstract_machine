# `perception-predicates-guide-the-search` (#227, off #222)

Plan item of `knowledge-directed-perception`, tracking issue #201. Branch reset
onto `origin/perception_eql_backend` before the first commit -- it arrived cut
from `integration`, the #199 hazard, same as #223 and #225.

## The claim

Replace #222's attribute-name narrowing with a predicate in the world's own
vocabulary. `SUPPORTING_SURFACE_ATTRIBUTE_NAME` and the krrood mimic's
`PLACE_ATTRIBUTE_NAME` both die; a predicate is its own source of truth, so
there is no name to spell twice.

## Plan

1. `semantic_digital_twin/reasoning/predicates.py` -- the bool-returning spatial
   relations (`LeftOf`, `RightOf`, `Above`, `Below`, `Behind`, `InFrontOf`)
   inherit `Predicate` instead of `Symbol`, each supplying the abstract
   `_verbalization_fragment_`. `InsideOf` returns a containment ratio, so it
   becomes a `SymbolicFunction` -- three call sites read that ratio and would
   break if `__call__` returned a truth value. A `SupportedBy` predicate class
   makes support statable in a query.
2. `krrood/entity_query_language/backends.py` -- `LookRequest` carries the
   predicates a statement states about the thing sought, alongside the attribute
   equalities it already carries. `PerceptionBackend.read_request` reads them off
   the `where` conditions; a backend asks for one by predicate type. The pushdown
   reads the operand that is already concrete (the world entity), since the sought
   thing has no value yet.
3. `experiments/.../perception/backend.py` -- narrow by `SupportedBy` read off the
   statement; delete `SUPPORTING_SURFACE_ATTRIBUTE_NAME` and the test guarding it.
4. `test/krrood_test/dataset/backend_that_looks_at_the_world.py` -- same, for
   `PLACE_ATTRIBUTE_NAME`.

Tests first at each level.

## Deliberately out of scope, recorded on #201 and in the PR description

- **Predicate read as a `Region` with extents, clipping image/depth**
  (r3893602153). Ends at the believed-place type that the roadmap settled is
  defined once by `pieces-looked-for-where-expected` -- `not_started`, behind
  #225. Building it here would build it out of order and twice.
- **Imagination-world rejection sampler** (r3893499716). This item's alone, but a
  second PR's worth of work. Proposed as its own plan item.

## Done

- Branch reset onto #222's tip; bootstrap commit pushed.
- Draft PR #227 opened; manifest `open` + `record` written; roadmap section landed.

## Next

- Publish the dashboard.
- Raise the two out-of-scope halves on #201.
- Write the tests, then implement, step 1 through 4.

## Open, not settled by anything gathered

- `MontessoriShapeDetection` is a dataclass, not a `Body`, so the geometric
  `is_supported_by` cannot evaluate a detection. The pushdown does not need it
  (it reads the concrete operand only), but re-checking the pushed-down predicate
  over what came back does. Decide during implementation whether the detection
  answers the predicate about itself, or whether a pushed-down predicate is
  exempted from the residual re-check -- the second weakens #222's recorded
  invariant that correctness never depends on the pushdown being honoured, so
  prefer the first and record whichever it turns out to be.
