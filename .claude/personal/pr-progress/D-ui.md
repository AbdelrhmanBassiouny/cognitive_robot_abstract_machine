# PR plan: D-ui — interactive expert interface (Wave 0, S1)

Not started. See `.claude/personal/rdr-roadmap.md` §3 Wave 0.

## Goal

Next slice of the `rdr-engine` umbrella (#38): the interactive
expert-facing layer of `entity_query_language/rdr`, stacked on
`D-core-engine` (#68).

## Scope (copy from `abdel/rdr-engine`, reconcile onto D-core-engine)

- Source: `rdr/interactive.py` (IPythonInterface), `rdr/magics.py`
  (%knows / %save magics), `rdr/case_table.py`, `rdr/prompt_examples.py`,
  `rdr/prompt_sections.py`; wire exports into `rdr/__init__.py`.
- Tests: test_interactive_expert, test_interactive_human_fit,
  test_interactive_human_fit_drawer, test_ipython_side_by_side,
  test_case_table_side_by_side, test_prompt_sections, test_hint_mode,
  test_no_target_rendering, test_no_target_integration, test_save_magic,
  test_save_rdr_with_case, test_case_serializer, test_variable_completion,
  test_progress_bar, test_rule_order, test_corner_case_store,
  test_correct_drawer + `fitted_models/` + doc
  `eql_rdr_conclusion_asking.md` (developer + user halves).
- If a test in this list turns out to import decorator/file_store, move it
  to D-deco instead — keep each PR self-contained and green.

## SOLID anchors

- `ExpertInterface` ABC owns the interact loop (template method); concrete
  `IPythonInterface` implements only `_run` — do not let policy
  (validation, re-prompt rules) leak out of `Expert`.
- Keep the injectable `shell_runner` seam so tests simulate the human.
- Magics are thin adapters over engine API calls; no engine logic in
  `magics.py`.

## Procedure

1. `git checkout -B D-ui abdel/D-core-engine`, `git checkout abdel/rdr-engine -- <files>`.
2. Fix imports against the split tip (code_generation package paths).
3. Full `test/krrood_test/test_eql_rdr` + `test/krrood_test/test_eql`;
   revert generated ORM artifacts; docformatter.
4. Draft PR `D-ui -> D-core-engine`, session link, subscribe, bug label
   NOT applicable (not a bug fix).
