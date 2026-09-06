# Knowledge-directed perception: expectation and failure detection

One of three successors to `knowledge-directed-perception`, split on 2026-09-05 for
`plan-size-limits` (tracking issue #200). **See `knowledge-directed-grounding`'s
roadmap.md for the programme-wide why, the three waves, the deadline budget, the shared
"stacked on, never waiting for a merge" and "demo merges into `tracy_icra` as soon as it
works" rules, and the sequencing decisions this plan inherits.** Per-round implementation
narrative about already-built items is compressed into each item's own `notes` in
`plan.yaml`; the full predecessor roadmap stays reachable in the personal-notes branch's
history immediately before the split commit.

## The recording constraint that shapes what this wave can ask for

Measured on `episode-replayed-into-the-world`: of the six rosbags recorded on 2026-08-28,
only `tracy_pickup_demo` carries the robot itself (`/tf`, `/tf_static`, `/joint_states`).
The other five hold camera topics only. So a replayed episode gives an event history for
the pick-up demo and for anything recorded from now on, but not for the five scene
captures - those get their expectations from the board and the action model directly,
which is why `pieces-looked-for-where-expected` (`knowledge-directed-grounding`) does not
depend on this track. Recording `/tf` and `/joint_states` alongside the camera in future
recordings would remove the split entirely; worth doing before the next capture session.

## Standing decision: a belief decays only when something acts on it

`expectations-from-events`'s central rule: an object's believed pose does not decay on its
own between frames. Released over a hole, it is believed to be at that hole, turned any
way within the release's spread; still grasped, its pose is the gripper's; acted on by
nothing, its pose is exactly where it was last seen. This is what makes a history
tractable where a single frame is not, and it is the rule any future extension of belief
tracking in this programme should preserve rather than re-derive.

## Standing hazard: a generic that is also a context manager broke ORM generation workspace-wide

Fixed as `1e93c138` on `expectations-from-events`. `make_specialized_dataclass`'s
memoization cached on the type alias object itself rather than on the class it names,
which is fine for an ordinary `Generic` subscript but raises `AttributeError:
'types.GenericAlias' object has no attribute '__memo__'` for a class whose
`__class_getitem__` returns a bare `types.GenericAlias` - which krrood's own `Variable` is,
being a context manager. Every ORM-building CI job failed identically regardless of which
package it was building for, because the failure is in the shared code path. A generic
that is also a context manager is now in krrood's shared test dataset, so its own conftest
would fail at collection if this regressed. Worth checking first if any future item in
this programme sees every CI job fail identically.

## Open, at the developer's own discretion (not this plan's to resolve)

- `expectations-from-events`: whether `InsideOf` (which already answers the sunk/over/
  clear cases at 23x less cost than `InsideRegion`, but reads a bounding box rather than a
  shape's volume) may absorb `InsideRegion`'s statechart role at a 0.9 threshold, and
  whether `InsideRegion` should carry `PlacementRelation`'s `allowed_space`.
- `expectations-from-events`: `HasPosition` versus `HasLocation` as the field's name -
  resolved without a rename being asked for, recorded only because the name is still his
  to change.
- `expectations-from-events`: the four lid expected-to-fail marks do not come off yet. Two
  of the four now get a history-seeded fit, but it loses to a ghost cylinder at the same
  place by a small margin - which is `competing-explanations`'s claim
  (`knowledge-directed-grounding`, `surfaces` track) to settle, not a threshold to tune
  here.

## The ICRA convergence pass, 2026-09-06

Both in-flight items of this plan are now carried by one branch: `episode-replayed-into-the-world` (#246) and `expectations-from-events` (#257).

The pass merged every one of them into the ICRA integration branch (#265,
`claude/icra-experiments-simulation-pipeline-w4ep7n`) rather than into each other,
so each conflict set was resolved once. Each item keeps its own branch and pull
request and its own status here; what changed is that its work now also stands on a
tree with everything else, which is what the ICRA experiments run on.

Merge order, resolutions, the duplication removed and the two collisions git could
not flag are recorded once, in `icra-foundation`'s `roadmap.md` under *The
convergence pass, 2026-09-06*. Read it there rather than re-deriving it here.

The #257 merge is where the second silent collision of the pass showed up, and it
was this plan's fix that would have been lost: #257 replaced the grid a sweep walks
with one laid out from the centre outwards, so that widening a belief's reach only
*adds* placements, while the `knowledge-directed-grounding` lineage extracted the
whole sweep into `OutlineFitter` and carried its own edge-anchored grid with it.
Merged textually, `offsets_within` would have arrived unused beside the phase bug it
was written to fix, with #257's four tests still passing against code no longer
reached.

The pass's first answer — unify them on the centred grid — was wrong, and the shipped
captures are what caught it. The two grids mean different things. A believed reach is a
bound the answer must be monotonic in, so its grid is centred on the claim and stops
inside it, which is exactly what this plan measured and fixed. The board's seed search
is pointed at the middle of whatever the lighting made dark, and it has to reach the
whole radius it was given; walking the centred grid there shortened its forty millimetre
search to thirty-six and left three of the board's six holes over wood on
`tracy_pickup_demo`. So this plan's fix stands where it belongs — `offsets_within` and
`OutlineFitter.placements_within`, for a belief — and the fitter keeps its own lattice
for a search.
