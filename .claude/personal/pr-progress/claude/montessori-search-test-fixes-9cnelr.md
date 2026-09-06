## `/plan-item-resolve icra-foundation integrated-simulation-pipeline` — the four narrowing tests

**What this session is for.** Clearing the second blocker on #265: the four failing
tests in `test_montessori_search_narrowing.py`. Not a separate piece of work — the
scope check (`git ls-tree origin/main -- test/experiments_test/test_montessori_search_narrowing.py
experiments/src/experiments/montessori/perception/watch_narrowing.py`) is empty, and
removing the edits leaves nothing, so this belongs on #265's own branch
`claude/icra-experiments-simulation-pipeline-w4ep7n`, not on this session's
`claude/montessori-search-test-fixes-9cnelr`. Needs the developer's say-so before
pushing there.

**Done so far (2026-09-06).**
- Built a working environment for the montessori perception suite in the session
  container, which the roadmap says is impossible — it is not: python3.12 venv,
  `pip install -e ./random_events`, then numpy, opencv-python-headless,
  `casadi~=3.7.0` (3.8 breaks `FunctionBuffer.set_res`), scipy, mujoco, trimesh +
  networkx + manifold3d, pillow, plyfile, urdf_parser_py, xacro,
  giskardpy_bullet_bindings, daqp, objgraph. Only `pytest` over `test/experiments_test`
  still fails, in the conftest's ORM generation (`CouldNotResolveType: QPControllerConfig`
  walking giskardpy), so the pipeline is driven from a script instead.
- Measured every piece against every hole on `tracy_pickup_demo` at `e6c665cec`, and
  evaluated the candidate replacements end to end through `MontessoriPerceptionBackend`.
  Reproduces the recorded numbers exactly (cube 50.3 mm, cylinder 51.6 mm, cylinder
  5.0 mm left).
- Item blockers updated on `claude/personal-notes` and the dashboard republished:
  it is three tests plus one production statement, not two tests.

**Proposed, awaiting the developer's approval (no test edited yet).**
- `..._reaches_as_far_as_the_radius_it_was_asked_for` → the **triangle hole**, radii
  0.07 and 0.12 (cube 50.0 mm, cylinder 93.8 mm).
- `test_the_two_sides_of_a_hole_hold_different_pieces` → keep the square hole, pair
  **`InFrontOf`/`Behind`** (cube 16.2 mm in front, cylinder 49.1 mm behind).
- `test_which_way_a_piece_lies_from_a_hole_is_read_from_where_it_is_seen` → keep the
  square hole, `RightOf` → **`Below`** (cube 18.6 mm up the picture, cylinder 45.4 mm
  down).
- `test_the_demonstration_states_its_way_down_to_the_cube_alone` → **no test edit**;
  `watch_narrowing.look_for_the_cube_on_the_lid`'s `LeftOf(square_hole)` becomes
  `Above(square_hole)`, and the asserted sequence holds unchanged.

**Next.** On approval: apply the four changes plus their docstrings on #265's branch,
re-run the measurement scripts as the evidence, push, re-draft #265, and record the
outcome in the item's blockers/roadmap. The experiments job stays red regardless —
the third blocker (the duplicate `RecordedLook`) is a separate call.
