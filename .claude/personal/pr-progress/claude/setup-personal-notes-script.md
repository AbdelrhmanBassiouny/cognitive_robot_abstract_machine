# PR #107 — setup-personal-notes-script (plan `workflow-unification`)

Draft PR #107, based on `claude/patch-pr-rheubx` (PR #101), not on `main` —
user overrode the item's "requires #101 merged" rule. Joins #106 as a second
sibling on that stack; GitHub retargets to `main` when #101 merges.

## Plan

Extract the mechanical half of `/setup-personal-notes` into a script that
needs no session, and shrink SKILL.md to what a script cannot supply.

## Done

- Re-checked the item's central premise and **disproved it**: both steps the
  roadmap called session-only are scriptable (`GET /user`,
  `GET /repos/{owner}/{repo}/labels/{name}`, `POST .../labels`). Verified live.
- `.claude/hooks/github-api.sh` — login, remote→owner/repo, label check/create.
  `gh` first, else `GH_TOKEN`/`GITHUB_TOKEN` + curl, else names both routes.
- `.claude/hooks/setup-personal-notes.sh --remote <name-or-url>
  [--starter-notes] [--create-labels]` — 10 steps, each gated on
  check-setup.sh's TSV verdict, exits with its status.
- SKILL.md 238 → 153 lines; check-setup.sh's stale "session-only" comment
  corrected; 4 new constants; README +11 lines.
- 254 tests pass (was 236 on base). All network- and credential-free via
  stub gh/curl/pip on PATH.
- Two incidental fixes, each its own commit: `current_branch_upstream_remote`
  returning 128 when a branch has no upstream (blocked branch creation
  outright), and the PATH-hiding helper removing `/usr/bin` wholesale.
- Structural changes comment-proposed on issue #102 (not the steward).

## CI on 3073c4e8

19/20 green, including `test_claude_dev_tooling` and both known flakes
(`semantic_digital_twin`, `giskardpy`). The `test_claude_dev_tooling`
failure on the first push (2cd9a8e8) was the PATH-hiding bug — fixed, and
verified locally under *both* conditions (gh present and absent) first.

Sole red: `test_each_lib (coraplex)`. **Not mine** — diff is `.claude/`-only.
`test/coraplex_test/conftest.py:35-40` regenerates
`coraplex/src/coraplex/orm/ormatic_interface.py` in `pytest_configure` with
no xdist guard; with `2/2 workers` two processes rewrite the same ~33.5k-line
file concurrently, and `ruff format` then fails to parse it (line 23528 of
33508), killing the worker. Committed file parses fine; sibling `.claude`-only
PR #106 had coraplex green an hour earlier — so, intermittent. Analysis posted
on the PR; `rerun_failed_jobs` queued on run 30498024255 to test it.

## Restacked onto #106 (2026-08-02, head c7887f05)

The user restacked this branch: base is now `claude/stack-tooling-on-main`
(#106), which had merged `origin/main`. **#101 has landed on main.** My work
survived intact — 3073c4e8 is still an ancestor, no history rewrite, all six
of my files present, and the diff against the new base is still `.claude/`-only
(16 files). `test_claude_dev_tooling` green on c7887f05, which is also the
first confirmation the restack didn't regress anything here (#106 edits
`resolve-personal-notes-config.sh` too, so a conflict was plausible).

New red: `test_each_lib (semantic_digital_twin)` — **not the old
`test_world_sim_state_sync` flake**, two different tests in `test_multi_sim.py`
(`test_builder_assigns_material_to_every_geom_sharing_a_texture`,
`test_builder_does_not_confuse_different_textures_sharing_a_basename`), both
`assert '' != ''`. Not mine: both tests come from `main` (added in 7c935c48,
2026-07-20, "Fix MujocoBuilder dropping materials on geoms sharing a texture")
and arrived here only via the restack. Analysis posted on the PR.

## Head 49f5b4c2 (2026-08-03) — third robotics failure, third cause

Branch merged #106 again (which merged main). Still `.claude/`-only vs base;
`test_claude_dev_tooling` green. New red: `test_each_lib (giskardpy)`,
`test_pacer.py::test_with_executor`, `assert 26.0 == 42` — a
`SimulationPacer(real_time_factor=2.0)` control-cycle count, so throughput
dependent on the runner. File is from main (2026-03-31), untouched here.

Three distinct causes across three heads (coraplex xdist race,
semantic_digital_twin materials, giskardpy pacer timing) with nothing in
common but the runner. **Decided to stop reporting these individually** — said
so on the PR. Only `test_claude_dev_tooling` going red is signal for this
branch.

## Merge conflict resolved, head f8bdcd07 (2026-08-05)

**Base is now `main`** — #101 and #106 have both landed, GitHub retargeted.
The routine reported `needs-resolution`: add/add conflict on
`.claude/hooks/tests/stubs/{gh,curl}.sh`. Fourth instance of the
same-artifact-twice pattern — main grew its own stubs via #115's
`plan-updates-since.sh`, which landed first, written when mine didn't exist
on any shared branch.

Resolved as a **union, not a winner**: the two recognize disjoint calls (login
+ labels here, issue comments there) and share the exit-64-on-unknown
discipline, so one stub per name now serves both callers with both sets of
`STUB_*` variables. Separate filenames would have been worse — both claim the
same name on PATH, so whichever suite ran second would silently get the
other's stub. Proven by mutation: breaking the issue-comments branch fails
exactly main's two backend tests, breaking the login branch fails exactly
mine. 286 pass (was 254 here, and main's `test_plan_updates_since_sh.py` is
included and green). PR description refreshed — base, test count and the
merge note were all stale.

## Next
- Do not fix semantic_digital_twin or coraplex here — separate root causes,
  other packages; AGENTS.md routes ORM issues via
  `scripts/regenerate_all_orm.py`/the developer.
- Still unverified: label **creation** against a real token. This
  environment's is a fine-grained installation token, so `POST .../labels`
  is exercised only through the stub. Flagged in the PR body.
- Leave as draft until told otherwise.
