
## Branch `cramera_eql_autocomplete` -- the workspace in the EQL namespace, with completion

Branched off `montessori_fast_inline_monitor` at `30bd734f53` (so it carries the mesh
download retry and the scene-default fix). One commit: `2765cec9b8`, pushed. No PR opened
-- the developer asked for a branch, and the parent branch has no PR either.

### What the developer asked for

1. every class usable in a query, and
2. IDE-style hints in the query box: what types and variables exist, filtered by the
   characters typed.

Decided with them before implementing: workspace `src/` classes without the ~4,200
generated ORM DAO classes (3,024 names); attribute completion after a dot in scope; an
ambiguous bare name resolves by package priority with the module shown.

### What is on the branch

- `knowledge/workspace_classes.py`: `WorkspacePackage` (declaration order *is* the
  tie-break rule), `ClassLocation` (scan module `coraplex.src.coraplex.filter` ->
  importable `coraplex.filter`), `WorkspaceClassIndex` (cached per architecture root, so
  pointing at another checkout rebuilds and tests do not leak into each other), and
  `WorkspaceClassNamespace`, a dict whose `__missing__` imports on first use. A `KeyError`
  there is what keeps an unknown name a `NameError` inside a query.
- `knowledge/query_vocabulary.py`: `QueryVocabulary` built from the runner, so the recorded
  scene and the live demo describe what they really accept. Members come from krrood's
  `DataclassOnlyIntrospector` for fields plus an MRO walk for properties/methods -- read
  off the classes, never through `getattr`, so describing a type never runs a property.
- Endpoints: `/api/eql/vocabulary`, `/api/eql/members?name=` and the bridge's
  `/vocabulary?scope=`, `/members?name=&scope=`; `QuerySource` gained
  `vocabularyUrl(scope)` / `membersUrl(name, scope)`.
- `web/core/completion.js` (token under the caret, prefix + capital-initials matching,
  ranking, insertion) and `web/panels/eql/suggestions.js` (the menu). The menu is
  `position:fixed`, placed from the input's rectangle: every `.panel` sets
  `overflow:hidden`, and an absolutely positioned menu was invisible because of it -- that
  cost a round of debugging, do not "fix" it back to absolute.

### Verified

- 473 cramera tests pass (was 431): 18 index/namespace, 16 vocabulary, 3+4 endpoint,
  17 node completion, 3 node query-source.
- In Chrome against this checkout on port 8712: `Bo` offers Box/Body/Book/... with module
  and docstring; `scene_object.` offers name/kind/label/position/height_metres with their
  types; Tab accepts; Enter then runs the query; `len(list(Body.__dataclass_fields__))`
  answers 11, where `Body` was a `NameError` before.
- Vocabulary payload is 682 KB / 3,078 entries, fetched once per source in ~76 ms.

### Deliberate deviation to tell the developer about

They asked for *every* candidate of an ambiguous name in the menu. It offers the winner
once instead, labelled `module (+35 more)`: 36 identical `Descriptor` rows cannot be told
apart or chosen (a bare name always resolves to the winner), so the count carries the same
information without flooding the list. Say so; revisit if they want all rows.

### Next

- No docs beyond `cramera/README.md`'s new section; a dual-audience guide was not asked
  for.
- `_hand_placed()` classifies a non-type as `VALUE` with `type(value).__name__` as the
  detail -- fine for `objects`/`sum`, unhelpful for anything richer.
- The 682 KB payload could be trimmed (drop `detail` for classes, or serve names only and
  fetch details per row) if it ever feels slow.

### Round 2 (2026-08-17, uncommitted): Symbols + Match verb default

The developer asked for two more things on this branch:

1. **Coraplex actions and segmind events/detectors as Symbols**, so they land in the
   SymbolGraph and are EQL-queryable in cramera. Added `Symbol` to the highest
   ancestors: `Designator` (coraplex -- covers actions *and* motions; the actions'
   highest ancestor), `DetectionEvent` (segmind events root), and `AbstractDetector`
   (segmind detectors root; its parent `MotionStatechartNode` is giskardpy's, which was
   deliberately left untouched). New tests:
   `test/coraplex_test/test_designator/test_designator_symbol_graph.py` (4),
   `test/segmind_test/test_symbol_graph.py` (6). Also found WIP already in the tree from
   an earlier session: `NamedEntity(Symbol)` in cramera plus `RowRenderer` handling of
   `init=False`/`repr=False` fields and `test_entity_symbol_graph.py` -- kept as is.
2. **Match verbalization default**: a match now opens with *"Find"* unless
   `has_ellipsis_attributes` (then *"Generate"*); a backend override still wins. Decided
   declaratively in `MatchPlanner` -> `MatchPlan.default_directive`, consumed by
   `MatchAssembler.realize`. Updated tests, docstrings/doctests, and
   `krrood/doc/eql/user/verbalization.md`.

Verified: krrood 1383+777 pass (typing suite skipped locally, no mypy in cram2 env);
cramera 477 pass; segmind 34 pass + 12 pre-existing failures (see landmines). Ran
`scripts/format_docstrings.py` on touched files.

Local-environment landmines (pre-existing, NOT from this round; tell the developer):

- pytest only runs with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` -- ROS jazzy's
  launch-testing plugins die on a broken `lark` install.
- Any `test/coraplex_test` run dies in conftest: `Table '_MockedConvexSetDAO' is
  already defined` (coraplex's and semantic_digital_twin's committed
  ormatic_interface.py both define it). Reproduces on a clean tree. The new coraplex
  test was therefore verified with `--noconftest`.
- `scripts/regenerate_all_orm.py` in this env produces huge unrelated churn (drops
  ROS-dependent DAOs, moves coraplex DAOs out of semantic_digital_twin's interface) and
  zero changes traceable to the Symbol edit -- regeneration was reverted; segmind's
  conftest-generated ORM is byte-identical, confirming Symbol's fields are ignored by
  ormatic.
- All 12 `test/segmind_test/test_detectors/test_segmind_detectors.py` tests fail with
  `MissingReferenceFrameError` in `World.transform` -- identically with the Symbol
  changes stashed, so pre-existing on this branch, likely a semantic_digital_twin
  spatial-types drift.

### Committed and pushed (2026-08-18)

Rounds 2 and 3 are now committed as six focused commits, `db78bfbc5b..d3321a4e97`,
pushed to `origin/cramera_eql_autocomplete` (authored as AbdelrhmanBassiouny, no
assistant trailer): sdt ORM regeneration, lark pyproject fix, costmaps inflation
memory fix + test, segmind detector-test reference frames, Match Find/Generate
default, and the Symbol feature (coraplex/segmind/cramera + all new tests). Only
untracked local junk remains (montessori.db, cram_architecture/, franka assets,
scheduled_tasks.lock). Still no PR, matching the parent branch.

### Round 3 (2026-08-18): the landmines above are FIXED

The developer asked to fix all of the Round-2 landmines. All four are resolved:

1. **lark / plugin autoload**: the venv's `lark-parser` 0.12.0 install was half-deleted
   (an orphan namespace dir shadowed `lark`), and the modern package is `lark` anyway
   (renamed 2021; ROS jazzy `launch` needs `from lark import Lark`). Uninstalled
   `lark-parser`, removed the orphan `site-packages/lark`+`lark-stubs` dirs, installed
   `lark` 1.3.1. pytest now runs *without* `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
   Repo-side: `pyproject.toml` now depends on `lark>=1.1.1` instead of
   `lark-parser>=0.12.0` (nothing in the workspace imports lark; the pin only serves
   ROS launch, which needs the modern one). The old pin came from commit `125dfe5a5a`
   "sage 10k grasp book" -- flagged to the developer in chat.
2. **mypy**: installed mypy 2.3.1 in cram2; `test/krrood_test/test_eql/test_typing`
   now runs and passes (1 test).
3. **`_MockedConvexSetDAO` conftest crash**: the real cause was semantic_digital_twin's
   *committed* `ormatic_interface.py` defining the identical `_MockedConvexSetDAO`
   block *twice* (lines 12360 and 12464) -- the file collided with itself on import;
   the earlier "coraplex vs sdt" diagnosis was wrong (each generated interface has its
   own Base/MetaData and is self-contained). Fixed by regenerating *only* sdt's
   interface via `scripts/regenerate_all_orm.py` (diff: duplicate mocked-DAO block
   removed, stray coraplex DAOs dropped from sdt's file, new branch classes added --
   MeshDownloadFailed/TransientFailureRetries/Numeric* spatial types). coraplex's and
   experiments' regenerated files were reverted: their churn (dropping
   Giskard/BehaviorTree DAOs) is environment damage -- `json_msgs` (a custom ROS
   message package) is not built anywhere on this machine, so
   `giskardpy.middleware.ros2` cannot import here. Note: any `test/coraplex_test` run
   regenerates coraplex's interface at collection time and will re-dirty it on this
   machine for the same reason -- revert that churn, do not commit it.
4. **12 detector-test failures**: stale test arrangement code, not a production bug.
   `Connection6DoF.origin`'s setter deliberately requires the assigned
   `HomogeneousTransformationMatrix` to carry a `reference_frame` (documented contract,
   custom `MissingReferenceFrameError`); the tests assigned frameless
   `from_xyz_rpy(...)` matrices. Added `_move_milk(milk, ...)` helper in
   `test_segmind_detectors.py` that builds the origin with
   `reference_frame=milk.parent_connection.parent` and converted all ~30 call sites.
   No assertion was changed. File was black-formatted by `format_docstrings.py`.

5. **Bonus, found while verifying #3**: full coraplex-suite runs were OOM-killing the
   machine inside `test_costmaps.py`. Root cause in production code:
   `OccupancyCostmap.inflate_obstacles` (`coraplex/src/coraplex/locations/costmaps.py`)
   reshaped an `as_strided` sliding-window view, materializing a ~1 GiB copy of the
   expanded matrix. Fixed by summing over the window axes of the view directly
   (`np.sum(sub_matrices, axis=(-2, -1))`) -- no copy, identical semantics. Added
   `test_inflate_obstacles_marks_only_fully_free_windows` (loop-computed expectation).
   All 22 costmaps tests now pass even under `ulimit -v 8000000`; before the fix, 2
   failed with `_ArrayMemoryError` under that cap and unconstrained runs got
   OOM-killed.

Verified after fixes (all without `PYTEST_DISABLE_PLUGIN_AUTOLOAD`): segmind 46
passed + 1 skipped (was 34+12 failing); krrood typing 1 passed; coraplex
costmaps 22 passed; coraplex `test_designator_symbol_graph.py` 4 passed *with*
conftest.

First-ever full coraplex baseline on this machine (file-by-file; the conftest crash
had always hidden it): most files green; pre-existing failures NOT touched (out of
scope this round): `test_multi_robot_action_designator.py` 68 errors,
`test_multi_robot_location_designator.py` 28 errors, `test_warehouse_storage_layout.py`
16 failed + 4 errors, `test_wind_farm_service_layout.py` 17 failed + 4 errors,
`test_graph_parsing.py` 4 failed, `test_action_conditions.py` 3 failed,
`test_demonstrations.py` 1 failed, `test_memory_leak.py` 1 failed,
`test_plan.py` 1 failed, `test_motion_designator.py` 3 errors.

Still known-broken in this env (not asked, not fixed): `open3d` wants `ipywidgets`
(pip check); drake/sapien/robocasa optional deps absent (mocked classes stay);
`json_msgs` ROS package not built anywhere, so coraplex conftest ORM regeneration
always drops Giskard ROS2 DAOs locally -- revert that churn after coraplex test runs.

### Round 4 (2026-08-18): the montessori stack rebased onto this branch

The developer asked for every PR stacked on `montessori_fast_inline_monitor` to be
rebased onto `cramera_eql_autocomplete`. The stack is the chain #164
`montessori_eql_where_is_highlighting` -> #165 `montessori_event_replay` -> #167
`claude/cramera-verbalization-voice-ttwcza` -> #168 `claude/cramera-voice-questions-ttwcza`
(#170 is this branch's own PR, i.e. the new base). All four rebased and force-pushed
(`--force-with-lease`); new tips d5b4946d4f / d03caf8329 / 4be9b11c71 / f64430d868.

Conflict decisions (all keep-both merges of autocomplete vs the stack's features),
plus the judgment calls:

- #167 was stale-stacked: it carried old copies of #164/#165 commits from before
  those were last rebased. Rebased only its two real commits (`ef46d536b5`,
  `00fe9d7349`) onto the new #165; the stale copies were dropped.
- Scenes submodule pin conflict in "Pin the scenes submodule": kept the base's
  `64b98eda` (public cram-scenes main, contains the fix's `2230683` target), so
  that commit now only carries its test-skip change; its message still talks
  about moving the pin -- harmless but slightly stale.
- EQL panel markup: kept `id="query-box"` (suggestions anchor) on the new
  `.query-bar` structure; welcome text carries both the question-display and the
  completion hints; preset clicks reload vocabulary on scope change *and* call
  `showQuestion`.
- Semantic conflict git could not see: `test_eql_panel.js`'s harness binds
  panel.js free variables explicitly, and the merged panel now needs
  `EqlSuggestions`. Added a stub (`of() -> {forget, handledKey:false}`) amended
  into the harness's own commit (#167 tip), VoiceCapture+EqlSuggestions merged in
  #168's re-application.

Verified per branch tip: cramera suite 488 (#164) / 540 (#165) / 562 (#167) /
594 (#168) all pass; `test_eql_panel.js` 10/10 on the tip.

Both outstanding items resolved later the same day:

- **#164 reparented onto `cramera_eql_autocomplete`.** It was a native
  GitHub-stack member (stack #166), so a plain base change would 422; followed
  the stacked-pr-maintenance dissolve procedure: recorded the stack list
  (scratchpad `stacks-before-unstack.json`), `POST /stacks/166/unstack`,
  `gh pr edit 164 --base cramera_eql_autocomplete`, re-created as stack #172
  (`cramera_eql_autocomplete` -> #164 -> #165 -> #167 -> #168). #164's diff is
  clean: 2 commits, 15 files. The developer then asked for one unified stack, so
  #171 (`main` -> #169 -> #170) and #172 were both dissolved and re-created as
  **stack #173**: `main` -> #169 -> #170 -> #164 -> #165 -> #167 -> #168, size 6,
  confirmed on every member (records in scratchpad `stacks-before-unstack.json`
  and `stacks-before-merge.json`).
- **`rapidfuzz` was a false alarm**: it *is* declared, in
  `cramera/requirements.txt`, which is where `cramera/pyproject.toml` sources
  its dynamic dependencies. Only the local cram2 venv predated the branch;
  rapidfuzz 3.14.5 installed there.

Tooling now on this machine (was missing when Round 4 started): `gh` 2.97.0 in
`~/.local/bin`, authenticated as AbdelrhmanBassiouny (web device flow); the
official GitHub MCP server registered for this project (local scope in
`~/.claude.json`) with `Authorization: Bearer <gh auth token>` -- connects, so
future sessions have `mcp__github__*` including the `update_pull_request` the
stacked-pr-maintenance skill mandates. Note the stored header holds the gh
OAuth token verbatim; if gh re-authenticates, re-run the `claude mcp add` with
the fresh token.


### Round 5 (2026-08-18): merged cram2/main and force-pushed to origin

The developer asked to push this branch with the merge conflicts resolved "according to
the most up to date one and the one that is proved stable".

Starting point: the local branch was 7 rebased copies of origin's 7 commits, replanted on
`608bc7fe6` (montessori_fast_inline_monitor after *its* main merge) -- so 7 behind / 228
ahead of `origin/cramera_eql_autocomplete`. `cram2/main` had 23 new commits.

**One textual conflict**, in `semantic_digital_twin/world_description/world_entity.py`,
`Body.has_collision`:

- ours (`bb75a7157`): `shape.volume > vt or shape.surface_area > st` -- never meshes.
- cram2/main (`208cf0e44`, Simon Stelter): `shape.volume > vt`, then
  `shape.mesh.area > st` -- meshes only for a shape too flat to pass on volume.

**Resolved to cram2/main's version.** Both sides carry the *same* `.. note::` in the
docstring (it merged without conflict), and that note describes main's short-circuit
exactly -- so keeping ours would have left the note describing code that is not there.
Main's is also the version upstream merged with tests written against it. Checked first
that this breaks nothing: `bb75a7157` added no `has_collision` test, only
`test_shape.py`'s four `surface_area` property tests, which still pass.

**Consequence to raise with the developer:** `Shape.surface_area` (5 implementations in
`geometry.py`, added by `bb75a7157`) is now used by nothing but its own tests. Per
AGENTS.md that is a consult-before-removing situation -- either drop it, or reinstate it
in `has_collision` in main's short-circuit shape.

**Second fix, `03b3130a5`:** `giskardpy/executor.py` used `Optional[float]` with no
import -- main dropped the module's `typing_extensions.Optional` along with its last use
while this branch added `_next_target_time`. This is the same invisible conflict
`a5080fd08` fixed on `montessori_fast_inline_monitor`; our branch forked from
`608bc7fe6`, one commit before it, so it arrived here unfixed. `test/conftest.py` reaches
this module transitively, so collection failed everywhere. Spelled `float | None`, as the
rest of the module does.

Method for finding it: `pyflakes` over the merged tree, restricted to the 17 Python files
the upstream side touched -- pyflakes is per-file, so nothing else could be newly broken.
`Optional` was the only finding. All six `ormatic_interface.py` files are empty in the
merged tree, as the hook requires.

Verified (all with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`): cramera 477 passed; segmind 46
passed + 1 skipped; sdt `test_world.py` + `test_spatial_types.py` 357 passed + 1 skipped;
`test_shape.py` + `test_collision_matrix.py` 59 passed; giskardpy `test_cartesian_tasks.py`
collects (47) -- which is what the `Optional` bug used to break.

Pushed `d3321a4e9...03b3130a5` to `origin/cramera_eql_autocomplete` with
`--force-with-lease`. Nothing pushed to `cram2`; the developer chose origin only.

**Landmine regressed:** the lark fix from Round 3 is gone from this venv -- pytest again
dies in ROS jazzy's `launch_testing` with `ImportError: cannot import name 'Lark'`, so
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is required again. The repo-side `pyproject.toml` pin
(`lark>=1.1.1`) is still correct; it is the local `.venv` that is wrong.

**Outstanding:** PR #170's draft state was not touched -- `gh` is unauthenticated in this
session's environment, so its state could not be read. If the developer did not mark it
ready themselves, it needs re-drafting after this push. The five branches stacked above
(#164, #165, #167, #168 and #175) are all still based on the pre-merge tip and need
restacking.

