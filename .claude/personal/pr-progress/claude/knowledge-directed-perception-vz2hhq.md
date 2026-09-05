# a-look-is-described-by-a-match (PR #275, draft)

Plan `knowledge-directed-requests`, track `method-selection`. Base
`claude/plan-item-kickoff-perception-idzwsk` (#266), with #259 merged in.

## The plan

Apply #266's shape - a `Look` subclass holding the world's own entities, a
`PerceptionDetector` stating its own capability, and a rule tree built by
`EQLSingleClassRDR.from_underspecified(a(TheLook)(detector=...))` - to the two
families that still predate it.

1. Merge #259 (`claude/plan-item-kickoff-kdp-34snn0`) in. Three additive conflicts:
   `exceptions.py`, `pipeline.py`, `test_montessori_perception_backend.py` - keep both
   sides. Verify both siblings' tests still pass.
2. `SoughtSurface` -> a `Look` with an open `finder` slot; `SurfaceFinder` ->
   `PerceptionDetector[SoughtSurface]`; `SurfaceRules` -> `from_underspecified` fitted
   through an `Expert` with `state_the_detectors_own_condition`. Deletes the
   hand-built `entity()/refinement()/Alternative.insert_at` tree and the re-declared
   `capability`/`stated_surface`/`answerable_surfaces`/`answers` quartet.
3. `TargetOnSurface`'s three copied fields -> the surface and the target themselves,
   with the readings restated as properties over them, plus an open `detector` slot.
   `DetectorRules` -> `from_underspecified` like the others.
4. Docstrings, `scripts/format_docstrings.py`, full experiments test run.

Tests first for each of 2 and 3.

## Settled while planning

- The item's title says "not by a case class", but `UnderspecifiedMatch.case_type` is
  `match.type` and its target is an attribute of that type, so a match over a bare twin
  entity is not something the engine can take. The item's own notes already resolved
  this: what is left is *the vocabulary the conditions are stated in*, not eliminating
  the case class. A `Look` that holds the world's entities is not a flattening.
- Every path this touches is absent from `main` (all three files come from unlanded
  siblings). It still gets its own branch because it changes files from *three*
  different in-flight branches - there is no single parent to fold into.

## Done

- Branch cut from #266, draft PR #275 opened, `plan.yaml` and the roadmap section
  recorded on personal-notes, dashboard republished.
- Step 1 done and pushed (`e1d8206dc`): #259 merged in, three conflicts resolved.
  `pipeline.detect` keeps #266's delegation to `LookRules` and now builds its
  `SceneToSearch` from `table_in(frame)`, which is where #259's find-the-table-by-looking
  takes effect. 456 passed, 2 skipped, 16 xfailed across `test/experiments_test`.
- Environment: this container had no project dependencies. `uv sync --extra dev` (with a
  pip-installed uv 0.12, the preinstalled 0.8 cannot parse this `pyproject.toml`), ROS
  Jazzy `rclpy` and friends from apt, and a `ros_jazzy.pth` in the venv. Run tests with
  `LD_LIBRARY_PATH=/opt/ros/jazzy/lib AMENT_PREFIX_PATH=/opt/ros/jazzy .venv/bin/python -m
  pytest ... --orm-build=never`; `--orm-build=never` is needed because the experiments ORM
  wants `json_msgs`, which exists only in the CI image.

## Next — blocked on a design call

Steps 2 and 3 are stated in the plan above, but authoring either tree through
`EQLSingleClassRDR.from_underspecified` hits something `LookRules` did not:

- `DetectorRules`'s discriminating condition is `surface.finish == MATTE`, which is the
  *rules'* knowledge (the colour blob is cheaper there — #231 measured 89 ms against
  126 ms), not either detector's capability. #266's
  `state_the_detectors_own_condition` expert therefore cannot author this tree, and
  `ConditionResolver` cannot either — it only reuses conditions already in the tree.
  Fitting on capabilities alone would answer a mirror-finished surface by the colour
  blob wherever colour separates the piece, reversing #231's measured decision.
- `SurfaceRules`'s fitting cases need an `RgbdFrame`, because
  `MeasuredSurfaceFinder.capability` reads `frame.carries_depth`. Authoring by `fit`
  means constructing example pictures inside production code.

Put to the developer rather than decided.

## Also found, not fixed here

- `TargetOnSurface.target_outline_is_known` is `target.outline is not None` over a
  `KnownPiece` whose `outline` is a non-optional `np.ndarray`, so it is unconditionally
  True — the same defect the item's own notes record for `SoughtSurface`. Semantics kept
  for now; it is a question about `KnownPiece`, not about this item.

## Blocked / to report

- `subscribe_pr_activity` on tracking issue #201 was refused by the permission
  classifier, so this session will not see structural changes announced there.
- `.claude/hooks/plan_item_bootstrap.py`'s `apply_item_fields` writes a rewritten
  `status:` line at 4-space indent when it follows a `depends_on` list, producing
  invalid YAML and failing both `open` and `record`. Pre-existing (reproduces on
  untouched items). Worked around by hand-patching; wants its own bug-fix PR off `main`.
- `test_each_lib` is red across the whole stack from #222 onward, waiting on #251.
