## `/plan-item-resolve rdr-core-engine D-core-support` — resolving PR #67

This session holds no branch of its own. The work landed on **`D-core-support`**
(PR #67) as merge commit `a5c26de7`, which is where any follow-up belongs.

### What was actually stalling it

Not CI (no checks had ever queued on the old head) and not a review: the steward
routine hit the **same merge conflict on six consecutive passes** — 2026-08-13,
08-18, 08-22, 08-23, and twice on 08-28 — and skipped the branch each time under
the `needs-resolution` label. Everything stacked above it (#98, #159, #210) was
waiting on that.

### Plan, and what was done

1. **`test/krrood_test/dataset/ormatic_interface.py` — untracked.** Tracked only
   on this branch; `main` and every other branch in the chain had dropped it, so
   integrating the base conflicted modify/delete. The merge also brings in
   `main`'s `**/ormatic_interface.py` ignore rule, absent from this branch's own
   `.gitignore`. Done.
2. **`verbalization_results.py` — took the base's version.** *This corrects the
   record*: the manifest and the PR body both described the conflict as one
   file's problem. This second file is tracked on `main` and everywhere else, so
   untracking would have been a regression. The whole difference was stale
   generator output (`typing_extensions.Tuple` vs stdlib `tuple[...]`). Done.
3. **Verify.** Not fully possible here — see below. Done as far as the container
   allows.
4. **Push, and update the record.** Done: PR description rewritten, `plan.yaml`
   notes and `roadmap.md` updated and saved at `6c29679a`.

### Verification status — read this before trusting the push

**The test suite was not run.** `random_events_lib` is an unbuilt compiled
extension in this container (not on PyPI; needs a bazel build), so the EQL
package cannot be imported at all. CI is the load-bearing check for `a5c26de7`.

Verified statically instead: the resolved generated file is byte-identical to the
base's and parses; nothing references the removed path; the merged `.gitignore`
carries the ignore rule; both core-EQL fixes are present at their intended
placement in the merged `base_expressions.py` (read, not trusted to the
auto-merge); and `origin/D-core-serialization` is now an ancestor of the head.

### Outstanding

- **CI on `a5c26de7` has not been read.** It had queued nothing at push time.
- **`needs-resolution` label still on #67.** It clears on the routine's next
  pass, per the routine's own comment — not removed by hand.
- **Two review threads open, both the developer's call, neither about code:**
  `rule_tree_view.py:255` (`enforce_parent_consistency` as a smell) and whether
  the "no planning wording in source" rule belongs in `AGENTS.md`.
- **#67 is not a draft, and was deliberately left that way.** `roadmap.md`'s
  standing hazards record that `open_ready` = open + non-draft is what tells
  dependents they can stack; re-drafting would flip #98/#159/#210 to not-ready.
  Put to the developer rather than decided.
