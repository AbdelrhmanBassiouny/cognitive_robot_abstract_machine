## Push window (#437) - ready for review; chain restacked and unblocked

### The recorder fix had no home but `integration`
Scanned every branch: `integration` was the ONLY ref carrying
`@dataclass(eq=False)`. All 8 other branches with the module still had the plain
`@dataclass`. The direct push to `integration` was the wrong place - a build
regenerates the branch, so it was an orphan. #154 introduces
`integration_reproduction.py` (#185 does not have it), so the fix now lives
there and propagates up.

### What was pushed this turn (bottom-up)
- **#185** `cuare2` 8c6c57d196 -> **37723c0b52**: merged main. Its only conflict
  was one file-location conflict (`narrowly-indented-plan.yaml` added on main
  inside a renamed directory), which hid a merged-clean test referring to a
  `FIXTURES_DIRECTORY` that does not exist here -> `DATASET_DIRECTORY`.
  **665 passed.** `mergeable_state` dirty -> unstable.
- **#154** `ixbvxl` bc00266181 -> **b08e1d475f**: merged the new #185 (two real
  content conflicts, both sides kept: a manifest key renders its own styles AND
  takes the field indent read from the block; the caller splits into lines) plus
  the recorder fix. **911 passed.**
- **#211** `wg4w4x` 8a7691cffa -> **843f62e30d**: merged the new #154, clean.
  **1166 passed.**
- **#437** `zen-feynman` 01d09f9026 -> **b2f3a141b0**: merged the new #211,
  clean. **1189 passed, 0 failed.** Left ready (user flipped it).

### #185 unblocked
Labels rewritten through `basstler.stack labels` to the complete set
`cram2-link-sent, tooling` - `needs-resolution` (conflict genuinely resolved)
and `integration-conflict` (no record at
`refs/integration/blocked/185/*`, so no build would ever lift it) both removed.
The chain #185 -> #154 -> #211 -> #437 is now unblocked and green.

### Test environment note
The suite needs `pip install ./basstler` (as CI's `test_basstler` job does) plus
pytest 7.x; without the install `test_a_missing_credential_is_its_own_exit_status`
fails with `ModuleNotFoundError: No module named 'basstler'`.

### Next
- A build should now be able to carry #437. Not triggered from here.
- `integration`'s own direct commits (8927b828dc, 6c49cd2411) are superseded and
  will be erased by the next successful build.
