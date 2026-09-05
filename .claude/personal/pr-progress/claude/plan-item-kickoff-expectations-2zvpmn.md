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

## Next

- Nothing on the branch. CI on the new head unread.
- Two discussions open for the developer: `StatedRelation` as a `Match` (on #227's
  ground), and the measured surface carrying its entity (recorded_setup / #238).
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
- Fetch the notes branch immediately before every save; `plan_item_bootstrap.py update`
  is not in this checkout, so edit the manifest in a worktree and save with
  `save-plan.sh --manifest --roadmap`.
