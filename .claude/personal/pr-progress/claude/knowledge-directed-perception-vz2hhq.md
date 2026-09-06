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

## Done (continued)

- Steps 2 and 3 done and pushed (`d3413bb08`). `TargetOnSurface` stops flattening and
  holds the surface and the piece; `SoughtSurface` gains the open slot; both trees moved
  onto `EQLSingleClassRDR.from_underspecified`; `SurfaceFinder` became a
  `PerceptionDetector[SoughtSurface]`. 461 passed, 2 skipped, 16 xfailed against the
  456 baseline. Docstrings formatted.

## The two design calls, as answered

Both were put to the developer and both took the recommended option:

- **Where the discriminating condition comes from.** Each rules class supplies its own
  expert, answering with the detector's capability and'ed with the situation the rules
  choose it in (`surface.finish == MATTE` for the colour blob, `== MIRROR` for the
  measurement). The situation is read off the look the rule is being stated from, not
  hardcoded — which is also what makes `add_rule` work for a finish nobody foresaw. The
  first build did hardcode it, and the glossy `add_rule` test caught that.
- **How `SurfaceRules` gets its fitting cases.** Minimal example pictures built in the
  rules: a one-pixel `RgbdFrame` that does or does not carry depth, which is everything
  a rule reads of a picture.

## Review round of 2026-09-06 (`0098923a1`, pushed)

Two threads, one change, plus a mid-turn question that changed the tests.

- r3942253246 asked for the RDR to take a pre-fitted tree instead of a family inventing
  example cases. `EQLSingleClassRDR.state_rules` + `StatedRule`; alternatives in stated
  order, first-holding-condition wins; same tree `fit_case` grows. Every invented
  example deleted, the one-pixel `RgbdFrame` included. Left **open** on purpose: I asked
  a question in it (see the hazard below).
- r3942264406 named the duplication between `surface_finding` and `detector_choice`; it
  was three files, `look_choice` too. All three now subclass krrood's `DetectorChoice`,
  which subsumes `state_the_detectors_own_condition`. **Resolved.**
- The chat question ("can't we do the corner cases by fitting on the captures?") is
  answered by checking rather than authoring: `SurfaceRules` is put to all six shipped
  captures, `DetectorRules` to the two surfaces the modelled scene states, each fitted
  with the detector it should get and each leaving the tree the size it was. Authoring
  from a run's own data was rejected because the pipeline builds its rules before any
  frame exists and the surfaces differ per setup — the colour-blob rule would not exist
  at all on `recorded_setup`.

468 passed, 1 skipped, 16 xfailed (experiments, was 461); 1569 passed, 3 skipped
(`test_eql` + `test_eql_rdr`, was 1563). PR body updated; still a draft.

## Next

Nothing outstanding on the branch. CI has not been read for this push.

## Blocked / to report

- A bare shared attribute node used as one rule's *whole* condition, together with a
  second rule wrapping that same node, splices into a structure `classify` never returns
  from. Sharing an attribute as a *subexpression* is fine and is now pinned by a test.
  Fitting escapes it only by building each condition at insertion time, so it is the
  expression machinery rather than `state_rules`. Worked around in the krrood mimic
  (`look.depth_is_returned == True`); whether `insert_at`'s cleaning should cover the
  bare case is put back to the developer on r3942253246.
- `subscribe_pr_activity` on tracking issue #201 was refused by the permission
  classifier, so this session will not see structural changes announced there.
- `.claude/hooks/plan_item_bootstrap.py`'s `apply_item_fields` writes a rewritten
  `status:` line at 4-space indent when it follows a `depends_on` list, producing
  invalid YAML and failing both `open` and `record`. Pre-existing (reproduces on
  untouched items). Worked around by hand-patching; wants its own bug-fix PR off `main`.
- `test_each_lib` is red across the whole stack from #222 onward, waiting on #251.
- `test_real_stretch_demo_process_boundary` errors in this container
  (`stretch_standalone.py` cannot start here); it fails the same way on an untouched
  tree.
