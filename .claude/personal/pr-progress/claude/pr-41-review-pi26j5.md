## PR #41 (rdr-backward-inference) - latest review round

**Review being handled** (2026-07-31, review 4829128805, thread PRRT_kwDOQhJw3c6Vb644):
`base_expressions.py:275` still defined `_last_parent_of_type_`; PR #89 removed it
on main. "Revise this and all related parts."

**Plan**
1. Restack: merge latest `main` into PR #41's head. [done]
2. Verify the backward-inference slice against #89's new `_conditions_root_` /
   `_filter_condition_` / `_has_condition_` API. [done]
3. Reply to the review thread + resolve it. [done]
4. Get permission to push to `rdr-backward-inference` (PR #41's head). [done]
5. Shrink PR #41's diff back to its 7 files. [blocked - see below]

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

- Pushed 214667ba..7459a5b0 to `rdr-backward-inference` (fast-forward, user approved).
  PR #41 set back to draft, subscribed to its activity, review thread
  PRRT_kwDOQhJw3c6Vb644 replied to and resolved.

**Blocked: PR #41's diff is now 268 files / +27825**
- Cause: base branch `ripple-down-rules-refactor` is pinned at 34f160df while its
  content has since landed on `main`, so merge-base(base, head) is stale.
- Retargeting #41 to `main` via the API fails twice with
  `422 - Cannot change the base branch because the pull request is part of a stack`
  (GitHub's stacked-PR feature; no unstack mutation available through the MCP tools).
- Workaround offered, awaiting decision: fast-forward `ripple-down-rules-refactor`
  to `main` (34f160df is an ancestor, so non-destructive). PR #40 - the only PR with
  that branch as head - is closed, and #41 is the only open PR based on it.
- Alternative: retarget in the GitHub UI, which may offer to leave the stack.

**Next**
- Resolve the base-branch situation, then refresh #41's description (its "Stack"
  section still lists #40 as a live parent).
- No scheduled check-ins armed, per personal notes.
