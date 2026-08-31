# `perception-predicates-guide-the-search` (#227, off #222)

Plan item of `knowledge-directed-perception`, tracking issue #201. Branch reset
onto `origin/perception_eql_backend` before the first commit -- it arrived cut
from `integration`, the #199 hazard, same as #223 and #225.

## The claim, and it is delivered

A look is narrowed by a relation in the world's own vocabulary rather than by an
attribute spelled as a string. `SUPPORTING_SURFACE_ATTRIBUTE_NAME` and the
krrood mimic's `PLACE_ATTRIBUTE_NAME` are both gone, along with the tests that
guarded them; a grep over the tree finds neither.

## Done

- `7330848e` krrood: `StatedRelation` reads a `where` condition as a `Triple`
  asserted about the thing sought, keeping the operand already concrete.
  `LookRequest.stated_relations` / `related_by`. A backend declares
  `narrowing_relations` and checks them over its own answer in `relations_hold`.
  Mimic `StandingOn` in the test dataset; krrood stays self-contained.
- `b5de5f4b` semantic_digital_twin: the six view-dependent relations become
  `Predicate`s with their own verbalization clauses; `InsideOf` becomes a
  `SymbolicFunction` (it answers a ratio, and three call sites compare it to
  thresholds of their own); `SupportedBy` is the relation form of
  `is_supported_by`.
- `92337dbf` experiments: the Montessori backend narrows by `SupportedBy`, reads
  the surface off the entity the statement relates the detection to, and
  re-checks it over what came back.
- PR #227 opened as a draft, description rewritten to match the built work.
- Manifest: `open` + `record` written, roadmap section landed, dashboard
  republished. `perception-backend`'s stale `blockers` corrected (four of its
  five threads had since been resolved).
- #201 carries the split proposal and the correction.

## Verified

- krrood eql: 1091 passed vs 1087 on the parent; failing/erroring set identical
  (177 both).
- semantic_digital_twin: failing/erroring set byte-identical to the parent, 143
  lines both. Parent baseline taken in a worktree with its own `*/src` on
  `PYTHONPATH`, per #222's recorded trap.
- experiments: 362 passed, 1 skipped, 16 xfailed, 6 errors -- identical to the
  parent, error set matched by name.

## Next, if anything

Nothing outstanding on this branch. The two deferred halves are proposals on
#201 and are the developer's to accept:

- Predicate read as a `Region` with extents, clipping image/depth. Blocked
  behind `pieces-looked-for-where-expected`, which owns the shared believed-place
  type and has not started.
- Imagination-world rejection sampler. Proposed as its own item.

## Decision worth re-reading at review

A relation cannot be re-checked by evaluating it, because a look reports
sightings rather than the things the relation is written over -- a
`MontessoriShapeDetection` is a dataclass, not a `Body`. So a backend declaring a
relation as narrowing also promises to check it over its own answer. #222's
invariant that correctness never depends on the pushdown being honoured is kept;
what changed is who does the checking. The alternative -- a `SupportedBy` that
dispatches on whether its subject is a body or a detection -- was rejected as a
smell.
