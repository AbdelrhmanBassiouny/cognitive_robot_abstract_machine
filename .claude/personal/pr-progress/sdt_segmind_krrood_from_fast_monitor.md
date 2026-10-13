## Next
- Split idea flagged on #355 but NOT acted on: its coraplex half (Insertion action
  + dataset + tests, plus coraplex/exceptions.py which is on main) could stand as
  its own PR against main and unblock part of the stack. User's call.
- The real remaining work: revive the 36 closed sub-PRs (#292..#363, ~122
  commits) on top of #262 -> #271 -> #278/#294/#295/#296/#297, then replay the
  61 blocked commits on top.
- No test suite could be run: this container has none of the workspace's Python
  dependencies (no numpy/pytest importable). CI on each PR is the only check.

## Plan
1. Audit #265 for commits no pull request's diff contains. [done]
2. Extract the ones that stand on `main` as small pull requests. [done]
3. Fold the ones that only edit an unlanded PR's own files into that PR. [done]
4. Reparent the pull requests based on #265. [attempted; none possible]
5. Report the stranded closed-sub-PR stack. [done]
