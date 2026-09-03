## icra-experiments / segmind-detectors-on-the-demo-branch

**No pull request, by instruction.** A merge between two of the developer's own
branches, pushed straight to `tracy_icra` with explicit permission.

**Done.** `origin/tracy_icra_segmind` merged into `tracy_icra` as `a80e86926`
and pushed. All three predicted conflicts resolved:

- `experiments/requirements.txt` kept deleted; `flask` *and* `segmind` declared
  in `experiments/pyproject.toml`. The `segmind` half was not in the plan: the
  merge is what first makes `experiments/src` import `segmind`, which
  `test_imported_workspace_members_are_declared` requires be declared. Verified
  failing without it.
- `segmind/datastructures/events.py`: the incoming content whole, over
  `tracy_icra`'s `BoundingBox` -> `VolumetricBoundingBox` rename (the old name
  no longer exists in `semantic_digital_twin`, so it was not optional).
- `pickup_demo_real.py`: both sides kept. `SHAPE_TABLE_CLEARANCE` is gone (the
  incoming branch removed both its readers); `tracy_icra`'s hardware-tuned 0.04
  carried onto the `GRASP_HEIGHT_OFFSET` that replaced it.

**Silent-conflict sweep, six passes, all clean:** module-level name inventory on
both sides, tree-wide import resolution diffed against both parents,
identifier-shaped string literals, attribute reads, keyword arguments against
merged signatures, and enum members against 204 enums. Near miss worth
remembering: `grasp_detector_nodes.py` calls `contact()` expecting a bool while
`tracy_icra` turned `contact` into `symbolic_callable_to_function(InContactWith)`
— safe only because that wrapper preserves the name's call behaviour.

**Outstanding.** `test/segmind_test` and `test/experiments_test` were not run:
no ROS in a web session (`rclpy` has no PyPI distribution, and
`segmind.datastructures.events` imports `geometry_msgs` at module scope). CI
triggers only on `main` pushes and pull requests, so this push ran nothing.
**Both suites still need a run** — in the ROS container, or on the next pull
request carrying this branch. What did run locally: every touched file parses,
the six sweeps, and `test_dependency_declarations.py` over all ten workspace
members (20 checks, all passing).

**Also worth a second look:** `GRASP_HEIGHT_OFFSET = 0.04`. If that 0.04 was
tuned against the old spawn-hovering geometry rather than against where the arm
has to reach, it is the one number in the merge to revisit.

