## A branch under upstream review is only pushed inside a push window

PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/437
draft, **base is now #211's branch** (`claude/plan-item-kickoff-workflow-unification-wg4w4x`).

### Why it is stacked on #211
#185 moves every `.claude/` Python module into the `basstler/` package, and 11 of
the 14 files this change touches do not exist under their old paths there. Based
on `main` it could never have merged past #185. #185 is an ancestor of #211, so
rebasing onto #211 picks up both and gives `integration_selection.py` as well.

### Done
- Rebased by cherry-pick with rename detection; 11 conflicts resolved, all of
  them `basstler.X` absolute imports vs the old bare ones. `push_window.py` ->
  `basstler/`, its suite -> `test/basstler_test/`.
- `pytest test/basstler_test --confcutdir=test/basstler_test` (what
  `integration_test_command` names on that branch): **1183 passed, 5 failed**.
  Clean #211: **1160 passed, the same 5**. So +23 passing, no new failure.
- `integration` is **green**: 1064 passed, 0 failed, under the repo's pinned
  pytest 7.4.4.
- Fixed a real bug found while doing it, pushed to `integration` as 6c49cd2411:
  `ReproductionRecorder` is a plain `@dataclass`, so it has no `__hash__`, and
  pytest keeps scanned plugins in a set - every reproduction run aborted with
  `TypeError: unhashable type`. `@dataclass(eq=False)`; its four tests now pass.

### Outstanding for the user
- **The recorder fix needs a durable home.** It is on `integration` only, which
  is regenerated from the tips, so the next build loses it and integration goes
  red again. The module lives on #211. Not pushed there - it is not my PR.
- **A real build cannot carry #437 yet.** #185 carries `needs-resolution` and
  `integration-conflict` and is `dirty` against main; a build leaves out a
  blocked branch and everything standing on it, which is #211 and #437. #437 is
  also still a draft, and builds carry only reviewed tips.
- Stale `in-review` labels (unchanged from last turn): #248, #261, #262, #264
  stale; #229, #251, #269 genuinely open upstream.
- Copyable prompt for the in-review label automation handed over in chat.
