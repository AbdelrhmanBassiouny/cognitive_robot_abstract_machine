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

### Candidate #438 is red, and it is stale rather than broken
One failing check of 24 (19 still queued): **"Run the maintenance pass"**, exit
10 = `branch-needs-attention`. Not a test failure.

- It exited 10 because three branches conflicted, the first being
  `claude/plan-item-kickoff-workflow-cuare2` = **#185** - fixed ~20 minutes
  after that pass ran. Others: `claude/icra-experiments-ormatic-episodes-ib9lr3`,
  `claude/auto-run-setup-notes-02nhxv`. Plus 28 withheld.
- #438 was assembled 16:48 from a stack where #185 was blocked, so it carries
  **none** of #185/#154/#211/#437, and its tree lacks #211's `runs_started_on`
  fix - the one that stops a candidate being graded on the whole fork's health
  by a `pull_request`-triggered maintenance pass.
- **That pass pushed 5 branches**, two of them `in-review`: #262
  `montessori-results-recording-jnrgfy` and #264
  `eql-verbalization-aggregate-repeat-gdz9g2`, at 17:09 UTC = 19:09 Berlin.
  That is exactly what #437's window exists to stop. All three of the other
  pushed branches carry `integration-conflict`, which the running version does
  not withhold on either.

**Not done:** no rebuild triggered. `integration-refresh.yml` is dispatchable
and a fresh build would now carry the whole green chain - but opening a
candidate re-triggers that self-judging maintenance pass, which pushes
branches, so it needs the user's go-ahead.

### #437's red CI is main's, not the branch's
Three failures on b2f3a141b0, all docker matrix: `test_each_lib` for
**coraplex, semantic_digital_twin, giskardpy**. `test_basstler` - the job this
change actually affects - **passes**.

Evidence it is inherited, not caused:
- `origin/main` fails the **same three jobs** with the same error and the same
  tally (490 passed, 7 skipped, 7 errors).
- On #437's pre-merge head 01d09f9026 those three jobs **passed**. They only
  started failing once the chain merged main up - which is the propagation that
  was asked for, working as intended.

Root cause, located: **f3ca2f96b9** (Simon Stelter, 2026-09-21 12:34 +0200,
"feat(tests): add trajectory length limit and enhance kinematic structure
access for DAiSy") rewrote
`semantic_digital_twin/resources/collision_configs/daisy.srdf`, adding 28 lines
that reference `left_gripper_side_cylinder_link` /
`right_gripper_side_cylinder_link`. **No URDF or xacro in the tree defines
either link**, so loading the DAiSy world raises
`WorldEntityNotFoundError` -> `BrokenWorldModificationHistoryError`.

No fix is in flight: nothing anywhere defines those links, and the branches
whose `daisy.srdf` lacks the entries are simply older than that commit.

Two possible fixes, and which is right is the author's call, not a guess:
drop the 28 stale `disable_self_collision` entries, or add the missing links to
the DAiSy description. Not pushed - this is main's bug and somebody else's
commit.

### Main re-merged through the chain (2026-09-22)
Fork main and cram2 main are in sync at **86bca5ddb8**. Someone had already
merged it into #185, which also gained a real change - `608b72e926` "Name the
branches, labels and session link the tooling tests share".

Propagated it the rest of the way, every step verified:
- **#154** b08e1d475f -> **55b098ddde**, 911 passed. Two conflicts:
  `DefaultLabel` -> `StackLabel` (the new shared test vocabulary, which gained
  `INTEGRATION_CONFLICT` so this branch's fourth label has a name in it), and a
  collection error `UPSTREAM_REMOTE` - #185's refactor inlined `"cram2"` four
  times while this branch's three integration suites import it by name, so the
  constant is back and those sites read it.
- **#211** 843f62e30d -> **1769b511cc**, clean, 1166 passed.
- **#437** b2f3a141b0 -> **3c246b240f**, 1189 passed. One conflict, both sides
  kept: `FixtureFile`/`A_SESSION_LINK` from below and `A_MOMENT` here, which sat
  either side of a docstring closing after the conflict marker.

Whole chain now contains main and its parent.

**The daisy bug is NOT fixed.** main 86bca5ddb8 still has all 28
`side_cylinder` entries in `daisy.srdf` and still fails the same three
`test_each_lib` jobs, so #437's red CI stays red until somebody fixes
f3ca2f96b9. `test_basstler` passes throughout.
