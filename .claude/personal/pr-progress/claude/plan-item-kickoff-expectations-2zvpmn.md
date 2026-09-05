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

## Next

- Nothing on the branch. CI on the new head unread.
- Two threads open for the developer: whether an event's declared effect should fold onto
  the statechart's own containment detectors (it should, once a hole's region is a
  containment candidate and the relation is settled), and `HasPosition` versus his
  `HasLocation`.
- The lid marks stay four; a history reaches two of them, and the rest is
  `competing-explanations`'.
- A look cannot tell a sunk piece from one standing over the hole; the success case is
  checked against a stated sighting only until the icra item runs it in simulation.

## Watch out

- #236 and #239 edit `pipeline.py` and `piece_matcher.py` on the other stack and meet
  `believed_from`, `placements_within` and the request seeding when the merge reaches them.
- Every later merge of #246 into the #238 stack meets the same `predicates.py` conflict;
  take 2ea13b3c's resolution. `HasPose` now sits on `spatial_types.py` and
  `world_entity.py` too.
- Segmind's tests need the root `conftest.py` (apartment fixture); run them without
  `--noconftest`. The experiments modules run with `--noconftest`.
- Fetch the notes branch immediately before every save, and fetch the *branch* too: the
  remote gained a merge of #255 mid-round, so a push was refused until it was merged in.
- Edit the manifest and roadmap between CLAUDE.local.md's own markers and run
  `save-plan.sh <plan-id>`; that path works in this checkout where
  `plan_item_bootstrap.py` does not.
