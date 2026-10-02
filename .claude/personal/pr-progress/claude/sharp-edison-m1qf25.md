Research spike: can semantic_digital_twin drop `world.modify_world()` and rely on the
modification decorators alone? Draft PR #485 (research, not for merge).
Report: https://claude.ai/artifact/LiuDsivNGeG7px3cok81cT

Done
- Prototype policies explicit/eager/eager_tolerant/deferred + lazy compilation flag.
- Benchmarks, commit profile, URDF parse, thread + ROS stress, sdt suite per policy.
- Report published; draft PR opened.

Results
- Commit = full O(N) rebuild (~99ms@200 bodies); per-call commits O(N^2) (0.65s -> 12s).
- Suite new failures: lazy 0, eager_tolerant 508, deferred 420.
- Recommendation: keep modify_world for groups, implicit block for single calls,
  adopt lazy recompilation; don't remove the block.

Next (only if asked)
- Turn lazy recompilation into a real PR (tests, drop env flag).
- Implicit single-call block: make add_connection register its DOFs so
  create_with_dofs need not add them early.
