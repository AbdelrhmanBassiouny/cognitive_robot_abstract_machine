## claude/fix-ci-failing-tests-202965 -> PR #183 (draft, `bug`)

Now the **ormatic-focused PR**: user chose design B (ignore the interfaces) and
asked for it to live here rather than in #169. Four commits:

- `a4990cfe` krrood: build an import scope past an unimportable module + unit test
- `a2385ec0` full-recovery regression test
- `6884cfcf` design B: ignore + untrack every interface, delete the guard
  machinery, build once per test run from the root conftest
- `d70a8d03` drop CI's now-redundant Build ORM step for test jobs

**Decisions the user made.** B over tracked-empty. Do (a) krrood fix and (b)
conftest build. **No freshness check (c)** - always regenerate instead, because
they believe regeneration is ~3s.

**Ported from #169** (so #169 must drop its copies): `orm_interfaces.py`,
`exceptions.py`, `ensure_orm_interfaces.py`, rewritten `regenerate_all_orm.py`,
`test/cognitive_robot_abstract_machine_test/`, gitignore rule, CI untracked
check, AGENTS.md rule, contributing.rst.

**Ordering, measured not assumed.** For `pytest test/<lib>_test` pytest imports
*every* conftest of the run before calling *any* hook, and several per-package
conftests import a mapped datastructure at module level. So the build is a
plain call at the top of `test/conftest.py`, not a hook. Controller-only guard
verified: controller imports conftest first, gw0/gw1 after.

**Consolidation.** Replaced four per-package hooks (coraplex, giskardpy,
segmind, semantic_digital_twin) - each built only its own package, which cannot
build a checkout that has none, since a generator reads the interfaces before
it. Logic lives in `test/orm_interface_build.py` so it is testable without
importing the heavy root conftest.

**Open, flagged in the PR body.** The ~3s premise looks wrong: CI's Build ORM
step took 99-108s on main and #169's own docstring says "about a minute". With
always-regenerate *and* the root conftest, every job pays it now - including
libs that never touch the ORM. If CI confirms, `ensure_generated()` instead of
`regenerate()` is a one-word change. **Waiting on CI timings before pushing
that.**

**Next.** CI running (run 32385354680 / 32385354507, started 15:18Z). Check
job durations for the real regeneration cost, and whether the 10 previously red
#169-shaped jobs are green. Not subscribed to any PR; no check-ins armed.
