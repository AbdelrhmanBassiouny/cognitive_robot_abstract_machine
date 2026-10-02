# PR #484 — Release each robot's world once the joint-name tests of that robot have run (`bug`)

Branch `robot-joint-name-tests-release-their-worlds`, off `main`. Draft.
Session_016LRmUnGe5NAuEmCxZy9E6t, 2026-10-02. Found while root-causing #229's sdt CI
world-budget failure (also merged there).

## Done

- `1ce81950`: module-level `lru_cache` -> module-scoped `robot_world` fixture, parametrized
  indirectly. CI image, one process: 11 -> 0 worlds alive at session end, 22 passed. No new
  test (a test-module memory fix; the suite's world budget is the check).

## Next

- CI on the PR.
