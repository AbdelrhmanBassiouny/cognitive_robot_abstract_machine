## Push window (#437) - marked ready by the user; this session's job on it is done

PR #437 is ready-for-review (user flipped it), based on #211, tip 01d09f9026.
No further commits pushed to it.

### Answer to "did you add it already?"
Added to the `integration` BRANCH by hand (8927b828dc, old `.claude/stack/`
shape). NOT added by a build. Build candidate #438
(`integration-20260921-164733`, opened 16:48) does not carry #437 and has no
`push_window` in its tree at all.

### Why the next build still will not add it
A build leaves out a blocked branch and everything standing on it. #437's base
chain: #437 -> #211 -> #154 -> **#185** -> main. #185 carries
`needs-resolution` AND `integration-conflict`, and is `dirty` against main.

Both are cheap, and both were measured:
- `needs-resolution` is warranted but tiny: #185's ONLY conflict with main is
  one file-location conflict (`narrowly-indented-plan.yaml`, added on main
  inside a directory #185 renamed). Resolved locally at
  /tmp/claude-0/p185 - place the fixture under
  `test/basstler_test/dataset/`, plus the one stale reference it hid
  (`FIXTURES_DIRECTORY` -> `DATASET_DIRECTORY` in
  `test_plan_item_bootstrap.py`). **665 passed, 0 failed.** Not pushed - #185
  is not this session's PR.
- `integration-conflict` has NO recorded block: `refs/integration/blocked/185/*`
  is empty, so by the tooling's own rule it is `blocked-without-record` and no
  build will ever lift it. Needs a hand removal.

### Hard dependency nobody has met yet
The `ReproductionRecorder` fix (`@dataclass(eq=False)`) exists only on
`integration` (6c49cd2411). #211 - and therefore #437's own tree - still has the
bug, so the moment a build carries this chain its suite fails those 4 tests and
the build goes red. The fix must land on #211 for a build of this chain to
succeed.

### Waiting on the user
- Push the #185 merge fix? (ready, verified, 665 passing)
- Remove `integration-conflict` from #185 by hand?
- Where should the `ReproductionRecorder` fix land durably - #211?
