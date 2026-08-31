# `perception-predicates-guide-the-search` (#227) + `predicates-answer-whether-they-hold` (#229)

Both items of `knowledge-directed-perception`, tracking issue #201.

## #229 -- the predicate vocabulary, off `main`

The developer's correction of a call #227 made: a relation that reads a measurement
is still a relation. `InsideOf.__call__` answers a truth value again, the fraction
is on `compute_containment_ratio`, and `minimum_containment_ratio` states the
judgement between them.

Nine relations converted, not one: `InsideOf`, `InsideRegion` (was
`is_body_in_region`), `SupportedBy`, `Supports`, `InContactWith`, `VisibleTo`,
`Reachable`, `Stable`, `PlaceIsOccupied`, plus the six view-dependent spatial
relations. `symbolic_callable_to_function` keeps every function spelling working
off one implementation, so giskardpy/coraplex/segmind are untouched -- which
mattered, since none of the three imports in this container.

Boundary: `get_visible_bodies`, `occluding_bodies` and
`compute_euclidean_planar_distance` stay functions. They answer lists and a
distance, not assertions.

Verified: `test_predicates.py` 24 passed vs 8 on `main`; whole-package
failing/erroring set byte-identical to `main`, diffed by name in a worktree with
its own `*/src` on `PYTHONPATH`.

## #227 -- the narrowing, off #222

`StatedRelation` reads a `where` condition as a `Triple` asserted about the thing
sought; `LookRequest.related_by` reads it back by class; a backend declares
`narrowing_relations` and checks them in `relations_hold`. Both attribute-name
constants are gone.

#229 merged in (`d874b32b`), taking its side of `predicates.py` and
`test_predicates.py` whole and keeping only #227's own `StatedRelation` test.

Verified after the merge: krrood 1091 passed (177 errors, same as parent);
experiments 362 passed / 6 errors, identical to parent; sdt set identical to
`main`.

## Plan state

25 items. Three added this round:
- `predicates-answer-whether-they-hold` -- in progress, #229.
- `search-clipped-to-a-predicates-region` -- not started; waits on #227 and
  `pieces-looked-for-where-expected` (which owns the believed place).
- `imagination-world-rejects-what-a-predicate-refuses` -- not started; waits on
  #227.

Manifest, roadmap and dashboard all current.

## Next, if anything

Nothing outstanding on either branch. CI was still queued on both when this was
written; neither is subscribed, per the standing rule.

## Decision worth re-reading at review

#227's `relations_hold`: a look reports sightings rather than the things a
relation is written over, so a backend declaring a relation as narrowing promises
to check it over its own answer. That keeps #222's invariant but moves who checks
it. `imagination-world-rejects-what-a-predicate-refuses` is what closes the gap
properly -- spawn the sightings into a copy of the world and every predicate has a
real subject.
