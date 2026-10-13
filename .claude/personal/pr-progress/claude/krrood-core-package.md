PR #506 (draft, base main): new light workspace package krrood_core; krrood re-exports.
Companion: basstler adopts it on claude/magical-albattani-9fbkd5 (stacked on #501).

Plan
- Keep #506 green; owner must create PyPI project + trusted publisher for krrood-core.

Done
- Package, re-exports, tests, CI matrix, publish workflow, AGENTS.md rules.
- Local: krrood_test 2690 pass (2 need graphviz `dot`), probabilistic_model 869,
  sdt JSON tests 534 (ROS-only errors). regenerate_all_orm.py fails on main (sdt MetaData).

Next
- Await CI / review. coraplex/giskardpy JSON tests only runnable in CI (need rclpy).
