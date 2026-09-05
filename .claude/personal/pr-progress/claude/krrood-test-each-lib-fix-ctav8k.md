# PR #268 - the red `test_each_lib (krrood)` check, root-caused off `main`

Opened as a draft off `main`, labelled `bug`. Came out of
`/plan-item-resolve knowledge-directed-perception perception-backend`, but is
*not* #222's work: it touches only files that already exist on `main` and
changes nothing #222 introduced, so it is its own bug-fix PR per the
one-root-cause rule.

## What was wrong

`test_draw_evaluated_tree_for_drawer_cabinet_rdr` loads a model directory that
only `test_save_and_load_drawer_cabinet_rdr`, earlier in the same file, writes,
and which is untracked generated output. Sequentially they line up; CI runs
`pytest -n auto` and they can land on different xdist workers. #222 flipped it
by being the first branch in the stack to add krrood tests, changing the count
xdist distributes by.

## Done

- Reproduced deterministically on a clean checkout (nothing deleted): the draw
  test alone gives CI's error verbatim.
- `saved_drawer_cabinet_rdr` fixture, so each test provisions the model itself.
  All six tests in the module pass individually with the directory absent.
- `GeneralRDR.load` chains its cause (`from e`), plus a test for it.
- `make_path_importable` puts a generated model's import root on the search
  path, so a model loads from wherever it was saved; plus a test for it.
- `test_ripple_down_rules` 78 passed against 76 on `main`; full
  `test/krrood_test` 2280 passed. Only the two graphviz-`dot` failures, which
  this container cannot run either way.

## Not done, and deliberately

- **#222 is still red.** It goes green when it takes `main` in after #268
  lands. That merge would mean pushing to `perception_eql_backend`, which this
  session was not asked to do.
- `pytest -n` could not be run here (sandbox blocks it), so the scheduling half
  is read off the workflow rather than observed. The order dependency itself
  needs no parallelism to demonstrate.
- The `needs-resolution` label on #222 is untouched; still the maintenance
  routine's to clear.
