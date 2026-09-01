# `search-clipped-to-a-predicates-region` — PR #238

Plan item of `knowledge-directed-perception` (tracking issue #201).
Branch `claude/kdp-search-constraints-pfaph7`, draft PR #238, based on #227
with #232 and #229's tip merged in.

**The work is built and pushed.** What remains is review.

## Steps

- [x] Re-cut the branch off #227 (it arrived cut from `integration`).
- [x] Merge #232 in; two files conflicted, both resolved as a union.
- [x] Open draft PR #238, record manifest state, append the roadmap section.
- [x] `WorkspaceRegion` narrowing arithmetic, tests first.
- [x] `SurfaceSearch` answers the stretch its own pass rectifies.
- [x] `SceneRequest` carries a stated region; the backend reads
      `InsideRegion`, the pipeline turns it into metres.
- [x] Merge #229's tip, for the four relation wordings.
- [x] `recorded_setup.recorded_world()`, so a statement about a capture has
      entities to be written over.
- [x] `watch_narrowing.py` and its headless test.
- [x] Measure the cost against the unclipped pass in one run.
- [x] Format docstrings, push, update the PR description and the roadmap.

## What the build found, beyond the plan

- **A clip that moves the sampling grid is not a clip.** A crop whose lower
  corner falls between the samples of the patch it came from rectifies every
  point half a pixel away — on `tracy_pickup_demo` that turned a cube into a
  second cylinder, non-monotonically in the size of the crop. Fixed by having
  `WorkspaceRegion.intersection` answer on its receiver's own grid; the clip
  is then behaviour-preserving to three decimals of agreement.
- **Cost, same run, all six captures**: unclipped 0.273 s/frame with nothing
  stated and 0.118 asked about the lid; clipped 0.207 and 0.056. Same 20 and
  6 pieces.
- **Precision, unasked for**: the lid pass reports 6 detections unclipped,
  three of them `competing-explanations`' ghost prisms, and 2 clipped.
- **The board pass is not narrowed by support**, since where the board stands
  is what the lid's extent is read from. Recorded rather than designed around.

## Notes to keep

- **The invariant**: a clip is an economy, never what makes an answer right.
  `relations_hold` re-checks containment and raises `LookHasNoReferenceFrame`
  rather than quietly not checking.
- **First item on this plan with parents on two different stacks.** #227 and
  #232 diverge at #221. `expectations-from-events` and
  `competing-explanations` face the same divide and it only grows.
- **Landing hazard worth more than the mechanical ones**: #231's
  `RectifiedFrame` shares a rectified plane across detectors, and a region
  that differs per pass means the sharing has to be keyed by region as well
  as height.
- **Environment**: no `/usr/local/bin/uv` in this container, against what
  #232 recorded; the `uv` on `PATH` is 0.8.17 and cannot parse this repo's
  `pyproject.toml`. Install uv 0.12.8 from `astral.sh` into a scratch dir.
- **Tooling**: `plan_item_bootstrap.py`'s four-space indent still breaks
  `open`/`record` on this plan's two-space `plan.yaml` (third time, after
  #231 and #236). Worked around by editing `plan.yaml` directly.
- Tracking-issue subscription was refused by the permission classifier this
  session, so structural changes on #201 do not arrive as events here.

# `search-clipped-to-a-predicates-region` — PR #238

Plan item of `knowledge-directed-perception` (tracking issue #201).
Branch `claude/kdp-search-constraints-pfaph7`, draft PR #238, based on #227
with #232 merged in.

## The plan

Read a spatial predicate as a region with extents and clip the picture to it
*before* anything is detected. #227 narrows which pass runs; this narrows how
much picture each pass reads.

Two routes, both asked for:

1. `InsideRegion(body, region)` — the predicate names a `Region` outright, so
   its extent is the world's answer and is used directly.
2. `SupportedBy(piece, surface_body)` — the surface's extent, which
   `WorkspaceSurface.of` already reads. **Table from the world, lid from the
   detection**, following the split #221 and #225 already made because the
   world's board pose has drifted from the real one. Lid extent grown by a
   margin read off `KNOWN_PIECES` so a piece at the lid's edge still fits.

## Steps

- [x] Re-cut the branch off #227 (it arrived cut from `integration`).
- [x] Merge #232 in; two files conflicted, both resolved as a union.
- [x] Open draft PR #238, record manifest state, append the roadmap section.
- [ ] `WorkspaceRegion.intersection` / margin — tests first.
- [ ] `SceneRequest` carries the search region; `MontessoriPerceptionBackend`
      fills it from the statement's predicates via `LookRequest.related_by`.
- [ ] `MontessoriPerceptionPipeline.rectify` / `searched_surfaces` take the
      region per pass rather than always the table's.
- [ ] `watch_narrowing.py` — the step-by-step viewer, one keypress per
      condition, windows labelled by `verbalize_expression` with the
      perception backend (`Directive.LOOK_FOR`).
- [ ] Headless test of the same steps through a recording `ImageDisplay`.
- [ ] Measure over the captures: same detections for the surface asked about,
      lower cost, as a ratio to a same-run baseline.
- [ ] Re-draft the PR after each push; rewrite its description to match.

## Notes to keep

- **The invariant**: a clip is an economy, never what makes an answer right.
  Every clip is a subset of what the statement already asserted, and
  `relations_hold` re-checks over what came back.
- **First item on this plan with parents on two different stacks.** #227 and
  #232 diverge at #221. Merging is the plan's standing rule; the merge only
  gets more expensive while both stacks grow, and
  `expectations-from-events`/`competing-explanations` face the same divide.
- **Landing hazards**: #223's `Footprint` → `RectifiedFootprint`; #231's
  `LoosePieceDetector` → `EdgeFitDetector` plus `RectifiedFrame` (a region
  that differs per pass is what makes a shared rectification non-trivial);
  #236 on #232 also edits `pipeline.py`.
- **Environment**: `/usr/local/bin/uv` (0.12.7); the `uv` first on `PATH`
  cannot parse this repository's `pyproject.toml`. `docformatter` and `black`
  need installing before `scripts/format_docstrings.py`.
- **Tooling**: `plan_item_bootstrap.py`'s four-space indent still breaks
  `open`/`record` on this plan's two-space `plan.yaml` (third time, after #231
  and #236). Worked around by editing `plan.yaml` directly.
- Tracking-issue subscription was refused by the permission classifier this
  session, so structural changes on #201 will not arrive as events here.
