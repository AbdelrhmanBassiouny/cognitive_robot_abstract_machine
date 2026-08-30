# D-ui (#76) — interactive expert interface

Plan item `D-ui` of plan `rdr-refactor`. Resolved by `/plan-item-resolve` on
2026-08-30; roadmap §36.

## Plan

1. Reset `D-ui` onto the rebuilt `D-ui-rendering` and re-apply this slice's own
   files, so #78's `cfe32ad0` does not survive the restack. — **done**
2. Bring the interactive layer onto the segregated `ExpertInterface`: `%save`
   through `ModelSaver`, and the shell's progress bar as this layer's default
   (the #159 review's outstanding work). — **done**
3. Port everything else the stack moved: `AnswerName`/`NamespaceName`,
   `conclusion_helper`'s mixins, `...` for `UNSET`, the validator and
   backward-inference renames, `ModelKey`. — **done**
4. Drop the tests pinning the removed `on_save`/`save_path` contract; keep and
   rewrite `%save`'s own coverage. — **done**
5. AGENTS.md conformance on files new in this PR: docstrings everywhere, `# %%`
   headers, no abbreviations, `format_docstrings.py`. — **done**
6. Bring both shipped guides onto the current API (the user one is executed by
   CI). — **done**

## Done

- `5269a778` force-pushed with lease; PR description rewritten; PR still draft.
- Two defects found and fixed with a failing test each: the
  `%conclusion`/`%conditions` magics no longer detected invalid answers after
  `validate()` became a list, and the user guide failed under
  `test_eql_documentation.sh`.
- test_eql_rdr 524 passed / 2 skipped (341 base, 183 added); rest of
  test/krrood_test 2104 passed / 7 skipped; EQL docs 15 of 16 notebooks.
- Manifest blockers cleared, roadmap §36 written, tracking issue #94 commented
  (`5469167156`).

## Next

Nothing outstanding on this branch. For whoever picks up the stack: **#80
(`D-store`) and #77 (`D-deco`) still sit on #76's pre-rebuild tip `c50d2109`**
and need the same reset-not-merge restack.

Not this branch's, reported not fixed: `test_object_diagram.py`'s two failures
and the `predicate_and_symbolic_function` notebook are identically red on the
base.
