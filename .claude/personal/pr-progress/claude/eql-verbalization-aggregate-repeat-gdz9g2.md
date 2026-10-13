## Next
- Developer answer on r3941192834 (the unranked *"For each month"* frame), still open. Round 2
  answers one of the two questions asked back there — his sentence did mean the ranked test —
  so what is left is the unranked frame itself and whether the possessive-vs-plural-generic
  wording for a directly aggregated attribute is a third item.
- CI on `4a5541d2c` finished 22/23 green; the one red is `test_each_lib (giskardpy)`, a
  15-second subprocess-launch timeout in `test_collision_matrix_tool.py`, in a package this
  branch does not touch. Not re-run, not watched. CI for `ccb7a780a` not polled. No check-in is
  armed (personal notes forbid scheduled checks).


## Watch out
- `plan_item_bootstrap.py open` is broken on `main` (four-space indent into a two-space
  manifest — PR #160's bug, closed unmerged). The manifest entry here was written by hand;
  do not trust `open`/`record` on this plan until that is fixed.
- Local test environment: `python3.12 -m venv` with `random_events`, `probabilistic_model`,
  `krrood` installed editable, plus `objgraph` and `docformatter`; run pytest with
  `--confcutdir=test/krrood_test` to skip the root `conftest.py`'s sdt imports. `test_typing`
  needs `mypy`, which is not installed there.

## The plan
A repeat mention of an aggregate shortens to its bare aggregation word (*"the sum"*), which
only identifies it while it is the only aggregate of its kind. Give the aggregate's noun
phrase a `referent_id` only when its aggregation names one aggregate, so a query selecting
two sums describes each in full at every mention.
