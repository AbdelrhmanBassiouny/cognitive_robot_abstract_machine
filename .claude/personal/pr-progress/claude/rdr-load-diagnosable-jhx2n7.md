# The krrood `test_each_lib` check: #268 closed as a duplicate, #269 carries what was left

## What happened

Root-caused the red `test_each_lib (krrood)` check from
`/plan-item-resolve knowledge-directed-perception perception-backend`, opened #268
for it, and then found it was a duplicate: **#251 had been open off `main` since
2026-09-03 with the same diagnosis and the same fix**, down to the same
`saved_drawer_cabinet_rdr` fixture and the same `SavedRDRModel` return type. #251's
version is better - per-test directory, so no shared write either, and verified under
`pytest -n 4`.

#268 is closed. Its two non-duplicated changes are **#269**, draft off `main`,
`bug`-labelled.

## #269, what it carries

- `GeneralRDR.load` chains the error that prevented the load (`from e`), so a failure
  says why. Its test derives the expected cause from `from_python` rather than holding
  a second copy of which exception it is.
- `make_path_importable` puts a generated model's import root on the search path, so a
  model loads from wherever it was saved rather than only from inside a package whose
  root is already importable. Its test saves into `tmp_path`; it fails on `main`.
- The root walk is factored out of `get_import_path_from_path`, which keeps its
  behaviour and loses a hand-rolled `/` split.
- `test_ripple_down_rules` 78 passed against 76 on `main`; full `test/krrood_test` 2280
  passed. Only the two graphviz-`dot` failures this container cannot run either way.

## Outstanding

- **#222 and everything stacked past it stay red until they take `main` in after #251
  lands.** Not #269 - it is a different root cause and clears nothing on that check.
- `pytest -n` is blocked by this session's sandbox, so the ordering half was
  demonstrated by running each test alone rather than in parallel. #251 already did the
  parallel run.
- The `needs-resolution` label on #222 is untouched; still the maintenance routine's.

## The lesson, recorded in the plan's roadmap too

The gathering read the plan's items, its roadmap and #222's state, and never looked at
the open `bug` pull requests. That is the compare-by-purpose check, and it is the fourth
time this repo has paid for skipping it (#110/#106, #117/#106, #229/#33). The cheap
version: search the open bug-fix PRs for the failing test's own name before cutting a
branch.
