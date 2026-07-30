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

## Next

- Check-in armed (`trig_01L17zAuoW5TNXde1t6kHvuc`): did the coraplex re-run
  pass? Same error at a *different* line supports the race; a fixed line
  would mean a real generator bug instead.
- Do not fix coraplex here — separate root cause, another package, and
  AGENTS.md routes ORM issues via `scripts/regenerate_all_orm.py`/the
  developer. Offered a separate PR in the comment.
- Still unverified: label **creation** against a real token. This
  environment's is a fine-grained installation token, so `POST .../labels`
  is exercised only through the stub. Flagged in the PR body.
- Leave as draft until told otherwise.
