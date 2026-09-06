## PR #284 - tooling label from changed files (branch: claude/ready-tooling-integration-fkd5b5, base: #281)

**Plan**: automate the `tooling` label #281 introduced, from a pull request's changed
paths, so merge priority stops depending on somebody remembering to label.

**Done**
- `changed_paths.py`: TOOLING / SHARED / SOFTWARE per path, from stack.toml's
  `tooling_paths` + `shared_paths`; a change is tooling when it touches the tooling and
  nothing outside it.
- `maintenance.py label-tooling` (both directions) + `.github/workflows/tooling-label.yml`
  on every push to a pull request.
- 16 tests; full tooling suite 804 passed. Draft PR #284 open, and the workflow already
  labelled #284 itself on its first run - proven end to end.

**Next / outstanding (not this PR's)**
- Bulk-label the fork's other 26 tooling pull requests: `maintenance.py label-tooling`
  with no `--pull-request`. Not run yet - waiting on the user, it writes to ~100 PRs.

## Integration + stacking actions - findings, no branch yet

- **Integration refresh fails every scheduled run** (6 in a row). Root cause: the build
  carries #111/#185's `.claude/` -> `bastler/` relocation, then the pipeline re-invokes
  `.claude/stack/integration.py` from the checked-out build tree, where it no longer
  exists. #158 / #198 (tooling pinning) are the fixes and are both skipped out of the
  build by the same collision.
- **Stack maintenance action fails**: its workflow runs `maintenance.py run-report`
  with no `board --write` step, and run-report consumes board.json rather than
  exporting one -> `board-unavailable (3)`. One-step fix, belongs on #280.
- **Build is `tip-left-out`**: 13 ready tooling tips skipped against #111 (the
  relocation), 1 against #206. Resolutions via stage-conflict/record-resolution live in
  the clone's rr-cache, which no CI runner has - so they cannot fix the scheduled
  rebuild. Reported to the user rather than attempted.
- **Ready tooling PRs red on their own checks**: #194 (`test_the_upstream_read_is_not_
  conditioned_on_the_promotion_label`, reproduced locally), #280 (above), #157 and #273
  (robokudo/giskardpy matrix, green on main - flakes).
