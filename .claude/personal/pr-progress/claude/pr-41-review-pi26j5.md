## PR #41 (rdr-backward-inference) - latest review round

**Review being handled** (2026-07-31, review 4829128805, thread PRRT_kwDOQhJw3c6Vb644):
`base_expressions.py:275` still defined `_last_parent_of_type_`; PR #89 removed it
on main. "Revise this and all related parts."

**Plan**
1. Restack: merge latest `main` into PR #41's head. [done]
2. Verify the backward-inference slice against #89's new `_conditions_root_` /
   `_filter_condition_` / `_has_condition_` API. [done]
3. Reply to the review thread + resolve it. [pending]
4. Get permission to push to `rdr-backward-inference` (PR #41's head). [pending]

**Done**
- Working branch `claude/pr-41-review-pi26j5` reset to PR #41 head (214667ba) and
  merged with `origin/main` (82501888). Clean merge, no conflicts - PR #41 touches
  only `rdr/` + `test_eql_rdr/`, never `base_expressions.py`.
- Commit 7459a5b0, first parent = 214667ba, so it fast-forwards
  `rdr-backward-inference`. Pushed to `claude/pr-41-review-pi26j5`.
- `_last_parent_of_type_`: zero references repo-wide after the merge.
- Slice compatibility: `backward_inference.py:308` only reads
  `expression._conditions_root_`, which is now non-Optional; nothing in the slice
  used the removed method or #89's other new API (`_true_results_`,
  `set_active_root_if_not_set`).
- Tests (python3.12 venv in scratchpad; container python is 3.11 and too old -
  `make_dataclass(module=...)` needs 3.12): `test_eql_rdr` 31/31 pass. Broad krrood
  sweep 288 failed / 1181 passed / 7 errors, versus **identical** 288 failed / 1150
  passed / 7 errors on a clean `origin/main` worktree - the 288 are pre-existing
  container/dependency failures, and the merge adds zero new ones (+31 = the slice).

**Next**
- Ask before pushing to `rdr-backward-inference`; that push is what actually
  updates PR #41 and closes out this review round.
