## Branch `claude/resolve-skill-upstream-check-j0fh4q`

**No pull request opened.** This session ran `/add-plan-item` only, which never
creates a branch, writes code, or opens a pull request.

### Done
- Ran `/setup-personal-notes`: installed the missing dashboard dependencies
  (`markdown`, `nh3`); every other check was already `ok`. All three labels
  (`bug`, `merged`, `in-review`) already exist on the fork.
- Scope check via `check_scope_overlap.py` against `origin/main`:
  `paths_absent_from_base` empty, so the work is new rather than a change to an
  unlanded parent. Six unlanded branches share the file (#149, #151, #154/#191,
  #156, #185) but none is this work by purpose.
- Recorded item `always-read-upstream-reviews` in the `workflow-unification`
  manifest (track `personal-data`, wave `immediate`, `depends_on: []`,
  `not_started`) plus its `roadmap.md` section, via
  `plan_item_bootstrap.py record`.
- Republished the plan dashboard to its existing URL
  (https://claude.ai/code/artifact/07123af6-6f6d-47e4-9817-43900f5339fa).
  53 items, no drift, no auto-corrections. Rendered with `origin/main`'s
  tooling in a scratch worktree, deliberately: this checkout's renderer carries
  unlanded #157/#149 template changes that would otherwise have been published.
- Posted the structural record on tracking issue #102 (comment 5385713710).

### Next
- The item is unstarted. `/plan-item-kickoff workflow-unification always-read-upstream-reviews`.

### Carry into that kickoff
- **This branch is not on `main`.** It points at `899a04aa`, an integration-branch
  merge of many open PRs, not `origin/main` (`3f643cff`). Recreate the item's
  branch from `origin/main` before committing anything.
- The fix: in `.claude/skills/plan-item-resolve/SKILL.md` step 2, drop the
  `in_review_label` precondition and the "skip it otherwise" clause; invoke
  `/upstream-reviews` whenever the item has a branch. Keep the existing
  "a failed dispatch does not fail the skill" behaviour.
- Test precedent is `.claude/stack/tests/test_maintenance_skill.py` (asserts a
  phrasing absent and the safe one present). There is no `plan-item-resolve`
  tests directory, so adding one costs a constant in
  `resolve-personal-notes-config.sh` and one path in `ci.yml`'s
  `test_claude_dev_tooling` job.
- Pull request: `bug` label, opened as a draft, based off `main`, session link
  in the description.
