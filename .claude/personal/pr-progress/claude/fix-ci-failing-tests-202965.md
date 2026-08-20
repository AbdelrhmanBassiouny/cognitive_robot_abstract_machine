## claude/fix-ci-failing-tests-202965 -> PR #183 (draft, `bug`)

The **ormatic PR**. Five commits:

- `a4990cfe` krrood: build an import scope past an unimportable module + unit test
- `a2385ec0` full-recovery regression test
- `6884cfcf` design B: ignore + untrack every interface, delete the guard
  machinery, build once per test run from the root conftest
- `d70a8d03` drop CI's now-redundant Build ORM step for test jobs
- `0ac188b0` tqdm progress bar, generator output captured, `--debug` to show it,
  `OrmGenerationFailedError` carrying what a failed generator wrote

**CI: all 15 jobs green** on run 32385354680. Design B + the krrood fix work.

**The ~3s premise was wrong - measured.** Comparing "Run tests" against main's
last green run (main's separate Build ORM step folded in): a build costs ~100s.
The 4 libs that already built one pay about what they did (work moved out of
its own step); the **7 that never built one now pay ~99s each** (min 88, max
106) - most of the runtime of the short jobs. Table is in the PR body. The
one-word alternative is `ensure_generated()` instead of `regenerate()` in
`test/orm_interface_build.py`, at the cost of a stale interface surviving a
branch switch. **User has not decided yet - do not change it unprompted.**

**Design evidence** (scratchpad `orm_experiment/`): tracked-empty fails every
branch switch that moves the interface path, and skip-worktree does not help -
it only hides the file, so the checkout still fails with nothing on the
checkout explaining why.

**Ported from #169** (so #169 must drop its copies): `orm_interfaces.py`,
`exceptions.py`, `ensure_orm_interfaces.py`, rewritten `regenerate_all_orm.py`,
`test/cognitive_robot_abstract_machine_test/`, gitignore rule, CI untracked
check, AGENTS.md rule, contributing.rst.

**Ordering, measured not assumed.** For `pytest test/<lib>_test` pytest imports
*every* conftest of the run before calling *any* hook, and several per-package
conftests import a mapped datastructure at module level. So the build is a
plain call at the top of `test/conftest.py`, not a hook. Controller-only guard
verified: controller imports conftest first, gw0/gw1 after. Logic lives in
`test/orm_interface_build.py` so it is testable without the heavy root conftest.

**Next.** CI re-running for `0ac188b0`. Nothing else outstanding. Not
subscribed to any PR; no check-ins armed.
