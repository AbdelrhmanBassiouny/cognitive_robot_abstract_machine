## PR #4: Generative match .where() without an explicit resolve()

Status: MERGED. Webhook confirmed the merge and auto-unsubscribed this
session from the PR's activity. Nothing further to track here -- do not
reopen or create a follow-up PR for this change unless explicitly asked.
Final pushed state: eac372c09 -> merged into f55221a12 with an origin/main
sync (rename `create_variable` -> `create_or_update_variable`, last review
round). Thread PRRT_kwDOQhJw3c6RIfVG was left unresolved at merge time
(the PR owner never explicitly weighed in on the in-place-mutation vs.
decorator approach before merging) -- if it comes up again, the reasoning
is preserved in the thread's replies on GitHub.

### Done

- User asked to set the session link in PR #4's description and subscribe
  to its activity (they already had review comments there). Did both.
- Investigated the open review comment on `from_()`'s eager-variable note:
  "What if somebody uses or points to the first created variable somehow?
  Could that happen? And could it create problems?" -- confirmed yes: a
  `where()` (or anything triggering `resolve()`) called before `from_()`
  silently leaves the domain unapplied, because `Match.expression` caches
  itself permanently and `create_variable()` replaced `self.variable` with
  a new object, orphaning any condition already built against the old one.
- Replied with analysis, proposed a raise-on-illegal-order guard, asked the
  user how to proceed (AskUserQuestion tool errored once transiently, asked
  again immediately after -- worked the second time).
- User suggested a `modifies_query`-style decorator (invalidate + rebuild
  fresh on `from_`/`where`, matching the `Query.modifies_query_structure`
  pattern) and asked "what do you think?".
- Implemented that decorator approach first. It broke an existing test,
  `test_nested_predict_with_where_range_on_sub_object`: a nested `Match`
  guards its own `resolve()` with `if self.resolved: return self`, so
  invalidating+rebuilding the *outer* match after the nested one already
  resolved loses the nested match's "predict" ellipsis-attribute semantics
  (falls back to a trivial equality condition instead). Rebuilding safely
  would need cascading invalidation into children -- much bigger than this
  PR's scope.
- Found the actual minimal fix instead: `create_variable()` (called by
  `from_()`) was replacing `self.variable` with a brand-new `Variable`
  object. Changed it to update the *existing* variable's domain in place
  via `Variable._update_domain_()` when one already exists, preserving
  object identity so earlier-built conditions and nested matches stay
  connected. Reverted the decorator/lazy-where changes entirely -- not
  needed, and risked the nested-match regression.
- Added `test_from_after_where_still_restricts_the_search` to
  `test/krrood_test/test_eql/test_match.py`; verified via `git stash` it
  fails without the fix (empty result set) and passes with it.
- Full `test/krrood_test` (1696 passed, 9 skipped) and
  `test/semantic_digital_twin_test/test_spatial_types` (252 passed) both
  green. Pushed as e49995d73. Replied to the original review thread with
  full reasoning (including why the suggested decorator doesn't work) --
  left that thread (PRRT_kwDOQhJw3c6RIfVG) **unresolved** since the fix
  diverges from what was explicitly suggested; wanted the PR owner's
  input/agreement before considering it closed.
- CI on e49995d73: `test_each_lib (krrood)` failed on an unrelated test,
  `test_rdr_alchemy.py::TestAlchemyRDR::test_fit_scrdr`
  (`FileNotFoundError` on a git-tracked, present file, with a suspicious
  triple-nested path in the error -- `/__w/<repo>/<repo>/<repo>/...`).
  Diagnosed as CI container/environment flakiness, not caused by this
  diff: the file is tracked and present, my full local suite run (same
  test) passed cleanly both before and after this push, and no other job
  in the same workflow run failed. Attempted `rerun_failed_jobs` but it
  was rejected (409-style "workflow already running", other jobs in the
  same run were still in progress) -- did not retry further since the two
  follow-up review comments below arrived and took priority; revisit
  (rerun failed jobs once the run settles) if it's still red.
- 2 more inline review comments on `create_variable()`, both simplification
  requests: (1) only call `variable()` inside the `if self.variable is
  None:` branch, not unconditionally; (2) don't build a throwaway
  `Variable` just to steal its domain -- compute the domain directly.
  Addressed by extracting the domain-resolution branch that `variable()`
  already had (`is_iterable` -> `InstanceFilteredDomain`, `None` + Symbol
  type -> `SymbolGraph`, else passthrough) into a new `_resolve_domain()`
  helper in `factories.py` (private, per the user's naming request --
  originally named it `resolve_domain` without the underscore, user asked
  for `_resolve_domain`), so `variable()` itself uses it too (no
  duplicated logic) and `create_variable()`'s else-branch calls
  `self.variable._update_domain_(_resolve_domain(self.type, self.domain))`
  directly. Hit the same docformatter bug as earlier in the session (it
  strips the space after a field marker like `:return:` when the value
  starts immediately with a double-backtick RST literal, confirmed via
  isolated repro -- unconditional bug, not about line length/wrapping);
  reworded to start the `:return:` value with a plain word instead of
  ``` `` ``` to dodge it, verified `docformatter --check` exits 0. Also
  caught and reverted an unrelated docstring reformat that `docformatter
  --in-place` made to the pre-existing (not-mine) `__call__` docstring
  while I was fixing the `_resolve_domain` one -- kept the diff scoped to
  only what I actually changed. Verified full `test/krrood_test/test_eql`
  (1009 passed) and black/docformatter clean. Pushed as a8bfb09ce, replied
  to both threads, resolved both.

### Next

- Recheck CI on a8bfb09ce once the workflow run settles; rerun failed jobs
  if `test_each_lib (krrood)` is still flaking on the unrelated RDR test.
- Thread PRRT_kwDOQhJw3c6RIfVG stays open until the PR owner weighs in on
  the in-place-mutation approach (vs. the originally-suggested decorator).
- Otherwise continue watching the active subscription for further review
  comments or CI results.
