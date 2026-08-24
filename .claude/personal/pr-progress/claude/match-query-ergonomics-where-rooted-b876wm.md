# PR #182 - re-root query-rooted attributes (plan `match-query-ergonomics`,
# item `where-query-rooted-attribute-no-filter`)

## Plan (session 2026-08-24, resolve round)

Nothing on the fork said this was stuck: #182 is open, out of draft, all six of
its review threads resolved, and all 23 checks green on `15f31d1e`. The block is
on the upstream pull request cram2#563, which no fork-side call can see -
LucaKro approved, **tomsch420 requested changes**, and the one unresolved thread
(`query.py:297`) asks whether `correlate` is the right word. The developer had
already replied there agreeing the name is misleading, so the ask is settled and
the deliverable is a rename, not a design decision.

1. Rename `_correlate_conditions_` / `_correlate_condition_` to
   `_reroot_conditions_` / `_reroot_condition_` - the word the rest of this diff
   already uses (`_reroot_on_`, `_rerooted_chains_`, `_rerooted_on_selection_`,
   and both methods' own docstrings).
2. Reword the one test section header that had spread the term.
3. Leave `query.py:111`'s "uncorrelated subquery" alone: pre-existing on `main`,
   and there the SQL term is the accurate one.
4. Run the tests, format docstrings, push; update the fork PR title and
   description; record roadmap §22, the manifest and the dashboard.

## Done

- Upstream state read via `/upstream-reviews` (the `in-review` label is what
  says there is an upstream PR at all).
- Rename applied in `query.py` (definition + 3 call sites, no other reader
  anywhere in the repository) and the test header reworded to "conditions that
  must keep their subquery meaning", matching its one test's own name.
- `test/krrood_test/test_eql`: 1191 passed, 3 skipped.
- Container again started with no project dependencies - scratch venv on Python
  3.12 with `krrood`, `probabilistic_model`, `semantic_digital_twin` and
  `giskardpy` editable, plus `objgraph`, `mujoco`, `giskardpy_bullet_bindings`,
  `mypy`. `test/conftest.py` needs all of it before anything can be collected.

## Next

- Nothing outstanding from this session once the push lands.
- The upstream thread is tomsch420's to resolve; `AGENTS.md` forbids commenting
  on or resolving anything on `cram2`, so the push is the whole answer.
- cram2#563's own title still reads "Correlate query-rooted attributes ..." -
  only the developer can change that upstream.

## Notes

- The fork PR is **left ready, not re-drafted**: it is out of draft with the
  `in-review` label, i.e. promoted after the developer's own approval, which the
  personal notes name as the one exception to the re-draft rule.
- Landing-order hazard still open (unchanged): #186 made `Index` abstract while
  this PR's `Index._rebuild_on_` constructs `Index` directly, so whichever lands
  second moves `_rebuild_on_` onto `IndexByValue` / `IndexByExpression`.
- Running the verbalization tests rewrites
  `test_eql/test_verbalization/verbalization_results.py`; that edit is the
  suite's, not the change's - check `git status` before committing.
- `subscribe_pr_activity` on tracking issue #181 was again denied by the
  auto-mode classifier; #181's comments were read directly instead.

