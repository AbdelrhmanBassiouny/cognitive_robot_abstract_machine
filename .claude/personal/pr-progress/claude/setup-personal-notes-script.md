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

## Next

- Outstanding comparison: `test_each_lib (semantic_digital_twin)` on **#106**
  itself, which was still running. If it fails there too, this is inherited
  from the base and settled. Named in the PR comment so it can be checked by
  whoever looks next — no scheduled check armed (personal-notes rule).
- Do not fix semantic_digital_twin or coraplex here — separate root causes,
  other packages; AGENTS.md routes ORM issues via
  `scripts/regenerate_all_orm.py`/the developer.
- Still unverified: label **creation** against a real token. This
  environment's is a fine-grained installation token, so `POST .../labels`
  is exercised only through the stub. Flagged in the PR body.
- The PR body still says "Stacked on `claude/patch-pr-rheubx`" — stale after
  the restack, worth one edit next time it's touched.
- Leave as draft until told otherwise.
