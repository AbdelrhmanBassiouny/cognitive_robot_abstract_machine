# `surfaces-found-by-looking` - PR #259 (draft)

`knowledge-directed-perception`, `method-selection` track. Branch
`claude/plan-item-kickoff-kdp-34snn0`, based on **#231**
(`claude/choose-detection-method-gf64yp`), not on #222: `WorkspaceSurface.finish`
and `.color` are #231's fields and the capability/rule-tree mechanism is #231's,
so `depends_on` now records `choose-detection-method` alongside #222 and #216.
#231 already carries #216.

## The plan

Replace the tuned rectangle (`recorded_setup.searched_workspace()`) and the model
read (`WorkspaceSurface.of_body`) with a surface *described* by what the twin
states - a large horizontal plane, mirror-finished, colourless, of about the
modelled size - and a finder compiled from that description.

1. `SurfaceFinder` family, each member declaring what it can find as an EQL
   condition, mirroring `PieceDetector.capability`.
2. Two members: the model read (base rule, always answerable) and a plane
   measured in the depth image (refinement, only where the description says
   enough to recognise one).
3. `SurfaceRules` - the live tree, stated once, grown by `add_rule`, following
   `DetectorRules`.
4. Pipeline and `recorded_setup` ask the rules instead of reading the tuned file.
5. `recorded_setup` states the recorded table's finish and colour beside
   `TABLE_HEIGHT` (a recording carries no world; #239 owns saying the same about
   the world).

## Verification, tests first

- Plane measurement alone: synthetic depth of a known plane with clutter recovers
  its height and extent; no dominant plane raises.
- Rules alone: described surface -> measurement, undescribed -> model, and a rule
  added while the tree is in use changes the next answer (#231's behavioural test).
- Captures: measured region strictly inside `WIDEST_WORKSPACE`, holds every
  detection reported on all six, same detections measured as tuned. Extents read
  from the run, never retyped. Cost as a ratio to a same-run baseline.

## Done so far

- Context gathered; roadmap read in full; deps `open_ready`; scope check run.
- Branch cut off #231's tip (it arrived from `integration` - the #199 hazard, the
  ninth time on this plan).
- Draft PR #259 opened; manifest + roadmap section saved to personal-notes.

## Next

- Write the failing tests for the plane measurement and the rules.
- Build `SurfaceFinder`, its two members, and `SurfaceRules`.
- Wire the pipeline and `recorded_setup`; measure over the six captures.
- Ask on the PR whether `tune_workspace` should be removed (used only by its own
  tests once this lands).

## Flags

- Tracking-issue subscription refused by the permission classifier - no push
  channel for concurrent structural changes this round.
- `plan_item_bootstrap.py open` failed on the known indentation fault (7th round).
