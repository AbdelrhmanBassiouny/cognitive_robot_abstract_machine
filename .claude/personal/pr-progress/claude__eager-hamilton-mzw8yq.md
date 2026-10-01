# PR #481 — Ignore the living-worlds tally a test run writes (`bug`)

Branch `claude/eager-hamilton-mzw8yq`, re-cut from `main` (it had descended from
`integration`). Draft. Session_016LRmUnGe5NAuEmCxZy9E6t, 2026-10-01.

## Why

`main`'s combined living-worlds limit writes `.living_worlds_tally/<worker>.json` at the
repository root; nothing ignored it, so `git add -A` committed it on #229 (r4158520836).

## Done

- `7e90d07d`: `/.living_worlds_tally/` in `.gitignore`, plus
  `test_this_repository_ignores_the_tallies_a_run_records` (failed first, then passed;
  `test_leaked_worlds.py` 21 passed).

## Next

- Nothing outstanding; CI on the PR is the remaining check.
