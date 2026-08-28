# bastler-package (#185) — `claude/plan-item-kickoff-workflow-cuare2`

Plan `workflow-unification`, track `bastler`, wave `upstream`. Draft PR #185, based on
`main`. Session https://claude.ai/code/session_01723FcMWYnpQHrq4fdxxs8j.

## Why this session was here

`/plan-item-resolve workflow-unification bastler-package`. The pull request was `dirty`,
labelled `needs-resolution`, and had been skipped by four maintenance passes since
2026-08-22. CI was green on the head commit, so the merge conflict was the whole blocker.

## The plan, as settled

1. Merge `origin/main`, then run `git ls-tree -r origin/main --name-only .claude/` against
   the merged tree — the 2026-08-23 lesson, since a conflict report cannot name a file a
   moved directory makes dangerous. It found `plan_item_mode.py` and `plan-item-modes.toml`,
   landed with #149, which git had not reported.
2. Fold both into `bastler/`, defaults resolved beside the module, `pyproject` package-data.
3. Repoint every caller at `python3 -m`, and add the two skill documents to
   `UNINSTALLED_INVOCATIONS` so the closure constrains the module.
4. Convert the incoming test to the package's own conventions (`PythonModuleRunner`,
   `constants.py`, `Location`).
5. Verify by mutation, not by a green suite.

## Done

- All of the above, in one merge commit `56d4f829`, pushed.
- 642 tests pass (617 before). Four mutations checked, each caught by its own test —
  including one that only failed *after* a prose mention of the module was removed from
  `plan-item-mode/SKILL.md`, because `names_of()` matches anywhere in a caller's file.
- `check-setup.sh` exits 0; all fourteen entry points answer `--help`; the built wheel
  carries `plan-item-modes.toml`.
- PR description updated; manifest `notes`/`session` and `roadmap.md` saved (`94240ab5`).

## Next

- Nothing outstanding on this branch. CI is re-running on `56d4f829`; the
  `needs-resolution` label clears itself once a pass sees the branch merge cleanly.
- **For the user, not for a session to decide**: `main` retired every workspace member's
  `requirements.txt` for static `[project] dependencies` (`4b4cfdf4`). `bastler` is not a
  workspace member so nothing fails, but its `requirements.txt` is now the last in the
  repository and four things read it. Whether it follows is a review call.
- Ten of the 2026-08-23 round's 34 review threads stay open on purpose (answered
  differently, or waiting on the user). Not this session's to resolve.
- Landing order, not dependencies: #198 fixes a bug this branch carries verbatim at
  `bastler/stack.py:823`; #203 adds `.claude/setup_steps.py`, which is the same
  new-`.py`-under-`.claude/` problem a third time.
