Research spike: can semantic_digital_twin drop `world.modify_world()` and rely on the
modification decorators alone (each modifying call commits its own block)?

Plan
1. Prototype policies behind `SEMANTIC_DIGITAL_TWIN_MODIFICATION_POLICY`
   (explicit / eager / eager_tolerant / deferred) in world.py.  DONE
2. Benchmarks + per-commit profile + thread stress + ROS sync stress
   (semantic_digital_twin/scripts/world_modification_policy/).  benchmark/profile/thread DONE, ROS pending
3. Run test/semantic_digital_twin_test under each policy, compare failures.  explicit baseline running
4. Report (pros/cons, recommendation) as an Artifact; commit prototype + scripts;
   open draft PR (research, not for merge).

Findings so far
- Per-commit cost is a full O(N) rebuild (FK expr cache, casadi compile, collision FK
  compile, pybullet shape rebuild): ~8ms@10 bodies, ~160ms@200, ~270ms@400.
- Eager per-op commit: O(N^2) builds (200 fixed bodies 0.3s -> 4.6s; 200 revolute 0.5s -> 12.5s)
  and breaks `create_with_dofs` (orphan DOF deleted) and add_body-before-connection (two roots).
- Deferred (implicit block committed on next read) matches explicit perf but needs
  thread ownership rules; unguarded cross-thread readers already see KeyErrors today.
- 139 production call sites: 28 pass through invalid intermediate states, 15 loops,
  ~24 read FK inside the block; giskard polls `world_is_being_modified`.
