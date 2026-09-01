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
- [x] `SceneRequest` carries the statement's placements; the backend reads
      them, the pipeline turns them into metres.
- [x] Merge #229's tip, for the four relation wordings.
- [x] `recorded_setup.recorded_world()`, so a statement about a capture has
      entities to be written over.
- [x] `watch_narrowing.py` and its headless test.
- [x] Measure the cost against the unclipped pass in one run.
- [x] **Second round (2026-09-01), at the developer's ask**: every relation
      that says where a thing may be, not only support and containment.
  - [x] `PlacementRelation` in sdt: the stretch it leaves, and the exact check.
  - [x] The six directional relations over entities, as an axis and a side.
  - [x] `Between`, `Near`, `Colored`.
  - [x] krrood's `Relation` above `Triple`, so a three-operand relation is
        read whole; `StatedRelation.constraint()`.
  - [x] The colour narrowing through to the detector's hues.
  - [x] `board_holes_in`, so a statement can name the square hole.
  - [x] `watch_narrowing` states support, a direction, then the colour, and
        reports what each step finds.
  - [x] Re-measure the cost; push; rewrite the PR description and the roadmap.
- [x] **Third round (2026-09-01), at the developer's ask**: one whole query,
      read from where the camera stands, with pictures that show the answer.
  - [x] `RgbdFrame.point_of_view`: the optical frame in the convention a pose
        is stated in, so *right* is right on screen.
  - [x] `PlacementRelation.allowed_part_of`, since no box holds the half space
        a camera-relative direction leaves; each surface narrowed against the
        stretch it was about to read.
  - [x] The backend answers the things a statement *describes*, so the lid and
        the hole are named in the query rather than fetched.
  - [x] `Match.one_condition_at_a_time`, and `SearchNarrowing` reading one
        statement instead of a list of conditions.
  - [x] Draw what each step found, and the rectified plane through
        `ViewFromAbove` so it reads the way the camera sees it.
  - [x] Re-measure; push; rewrite the PR description, the roadmap and this.

## What the build found, beyond the plan

- **A clip that moves the sampling grid is not a clip.** A crop whose lower
  corner falls between the samples of the patch it came from rectifies every
  point half a pixel away — on `tracy_pickup_demo` that turned a cube into a
  second cylinder, non-monotonically in the size of the crop. Fixed by having
  `WorkspaceRegion.intersection` answer on its receiver's own grid; the clip
  is then behaviour-preserving to three decimals of agreement.
- **A stated stretch says where the *thing* is, not which pixels may be read.**
  A cube 25 mm inside the stretch a statement allowed was never fitted, its
  rectified silhouette crossing the boundary. The picture now reaches an
  overhang past a stated stretch as it already did past a surface's boundary.
  This was a fault in the first round's clip, `InsideRegion` included.
- **The board pass is narrowed by nothing**, since where the board stands is
  what every surface's extent is read from. Clipping it by a statement about
  what rests on it would let that statement decide how far the lid reaches.
- **Right of the square hole leaves the cylinder, not the cube**, from the
  camera's own point of view as well as from the robot's: the cylinder stands
  34 mm to the right of that hole in the picture and 36 mm below it, the cube
  28 mm above it and 6 mm to its left. So the demonstration states *above*,
  and a test pins both answers.
- **A camera-relative direction narrows nothing on its own.** It runs across
  the world's axes, and no axis-aligned box holds a half space, so the clip
  has to be asked about a stretch that is already bounded. That is
  `allowed_part_of`, and without it the direction step would have left the
  picture exactly as it found it.
- **Cost, one run, all six captures**, against an unnarrowed look at 0.333
  s/frame: 0.25x for the surface, 0.40x for a direction alone, 0.30x for a
  50 mm radius, 0.25x for all of them with the colour. 20 pieces unnarrowed,
  5 with everything.

## Notes to keep

- **The invariant**: a clip is an economy, never what makes an answer right.
  `relations_hold` re-checks every stated relation exactly — by the relation
  itself, not by its box — and raises `LookHasNoReferenceFrame` rather than
  quietly not checking.
- **Cube and cylinder are both cyan** in this set, so colour never separates
  those two. What it narrows is two hues to one and six candidates to two.
- **A rectified patch is indexed a quarter turn from the camera's view**, so a
  window drawn straight off it makes a stated direction read wrong on screen.
  `overlay.ViewFromAbove` already turned it; the demonstration uses it now.
- **A description answerable from its own domain is answered, not refused.**
  That reverses one krrood test's premise, deliberately: what a look cannot do
  is *fetch* another variable, not read one the statement already gave a
  domain for.
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

