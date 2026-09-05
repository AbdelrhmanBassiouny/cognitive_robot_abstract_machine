# expectations-from-events (#257, draft) - knowledge-directed-perception

Kicked off and built 2026-09-03 in `auto` mode; the review rounds of 2026-09-04 (two) and
2026-09-05 resolved the same day each. Branch `claude/plan-item-kickoff-expectations-2zvpmn`,
cut from #255 (`claude/knowledge-directed-perception-imagination-g9hsnr`) with #246 merged
in; the pull request's base is #255. Full reasoning is in the plan's `roadmap.md` sections
of the same name.

## Done

- The re-base (2ea13b3c) and the relations rewrite (3dddd76e, 0fab8101).
- The round of 2026-09-05: `segmind.expectations` holds the general `Expectation` and
  `Expectations`, the Montessori halves are two thin subclasses; a release expects
  `InsideRegion` and `Near` only, since the twin's own `SupportedBy` refuses a sunk piece;
  `Effect.checks` and a pick-up that re-checks containment; `ComesToRestEvent`; two
  readings bound as generics, colour and turn asked of the body; `HasPose` in the twin
  and `yaw_of` through `Pose2D`; renames and wording.
- Replied on all nineteen threads; resolved the ones done as asked.
- Manifest, roadmap, and the new `icra-experiments` item
  `expectation-checked-under-perturbation-in-simulation`.
- The evening round of 2026-09-05 (e5d12093), which took both recommendations the morning
  had left open: `StatedRelation` is a `Match` over the relation's own class (with equality
  as mutual coverage, since `Match` is `eq=False`) and `stated_in` reads a statement's
  relations; an `Expectation` is a `Match` about its subject, so `holds_now()` answers it
  against the world; `WorkspaceSurface` carries the entity it was measured of, which
  inverted `recorded_setup`; `HasPosition` replaces the `Placed` union; `colors` answers
  every colour.
- The night round of 2026-09-05 (f7112120): `StatedRelation` is gone entirely, at the
  developer's rejection of the subclass. A relation stated about the thing sought is an
  ordinary `Match`; `Relation.subject_name()` / `Triple.object_name()`, `Match.stating`,
  `Match.covers`, `Match.states_the_same` and the four reading functions beside the backend
  are where its parts landed, and `Expectation.expects` is what a belief is asked in place
  of comparing statements.
- The late round of 2026-09-05 (3d4b8457), two questions rather than asks:
  `object_stated_by` names the read of what a stated relation relates the thing sought to,
  beside the other readers, and answers `None` where the statement leaves that side open
  rather than raising a bare `KeyError`; `Match.stating`'s docstring says what
  distinguishes it from `where`, since only an attribute reaches `construct_instance`.

## Next

- Nothing on the branch. CI on the new head (3d4b8457) unread; f7112120's was unread too.
- Two threads answered and left open for the developer, both krrood questions:
  whether `Match.stating` earns its place (it has one production caller, and the fold into
  that caller was offered), and whether subclassing `Match` was worth it (no -- the
  equality override contradicted `Match`'s identity equality silently, which is the
  argument, and the honest cost of dropping it is that reading an operand is now a call).
- One thread open for the developer: he proposed making `InsideOf` answer for regions to
  fold the containment check onto the statechart's detectors. It already answers for them
  -- 1.000 sunk, 0.500 standing over the hole, 0.000 clear, 23x cheaper than
  `InsideRegion` -- but it counts vertices in a bounding box, so its own 0.5 default reads
  the over-the-hole case as *in* while the detectors' 0.9 reads it right. His to settle,
  with `InsideRegion` being a `PlacementRelation` the second thing to weigh.
- The lid marks stay four; a history reaches two of them, and the rest is
  `competing-explanations`'.
- A look cannot tell a sunk piece from one standing over the hole; the success case is
  checked against a stated sighting only until the icra item runs it in simulation.

## Watch out

- #236 and #239 edit `pipeline.py` and `piece_matcher.py` on the other stack and meet
  `believed_from`, `placements_within` and the request seeding when the merge reaches them.
- Every later merge of #246 into the #238 stack meets the same `predicates.py` conflict;
  take 2ea13b3c's resolution. `HasPose` now sits on `spatial_types.py` and
  `world_entity.py` too, and `HasPosition` above `HasPose`.
- Nothing anywhere holds a `StatedRelation` any more; a branch that does states
  `an(<Relation>)(<operand>=...)` instead.
- Segmind's tests need the root `conftest.py` (apartment fixture); run them without
  `--noconftest`. The experiments modules run with `--noconftest`.
- Fetch the notes branch immediately before every save, and fetch the *branch* too: the
  remote gained a merge of #255 mid-round, so a push was refused until it was merged in.
- Edit the manifest and roadmap between CLAUDE.local.md's own markers and run
  `save-plan.sh <plan-id>`; that path works in this checkout where
  `plan_item_bootstrap.py` does not.
