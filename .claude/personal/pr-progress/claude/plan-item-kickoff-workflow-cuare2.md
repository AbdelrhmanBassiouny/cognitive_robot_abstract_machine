# bastler-package (#185) — `claude/plan-item-kickoff-workflow-cuare2`

Plan `workflow-unification`, track `bastler`, wave `upstream`. Draft PR #185, based on
`main`. Session https://claude.ai/code/session_01GE3r3XXEJpr9DUUk78Y2sT.

## Why this session was here

`/plan-item-resolve workflow-unification bastler-package`. Unlike the two before it,
nothing about the pull request was broken: `mergeable_state` clean, all 23 checks green,
no label left on it. The one open thread was posted the same day, on
`bastler/package_layout.py`, and asks for the opposite of what this branch had recorded
twice — install the requirements automatically rather than declare who runs without them.

## The plan, as settled

1. `session-start.sh` installs whatever of `bastler/requirements.txt` is missing, gated on
   the notes-branch fetch it already exits on, reporting a failure and finishing the run.
2. Delete `UNINSTALLED_INVOCATIONS`, the derived closure, `third_party_import_names()` and
   the unavailable-import harness, with the 32 test cases derived from them.
3. Ask about the seventh caller before deciding it — an Actions runner reaches no hook.
4. Tests first, then five mutations; verify the install for real, not only against a stub.

## Done

- All of the above, in `cb4d789a3`, pushed. The user chose adding a `pip` step to
  `upstream-reviews.yml` and deleting the mechanism outright, over keeping a one-entry
  version — recorded in `roadmap.md` because it reverses the 2026-08-23 entry.
- What replaces the guarantee names nothing: a test reads `.github/workflows/*.yml`, finds
  every workflow running a module, and holds each to installing the requirements first.
- The lookup moved beside the installer as `missing_requirements`, so `check-setup.sh` and
  `session-start.sh` stop carrying two copies of the same heredoc. `executable_stubs.py`
  holds the stub directory and PATH-hiding helper, now that two suites need them.
- Three docstrings that justified being stdlib-only by a caller the 2026-08-23 round had
  already disproved now give decision 12's krrood independence instead.
- 615 tests pass, from 642 — 32 deleted cases, 5 new, arithmetic stated. Five mutations,
  each caught by the test that names it. `nh3` uninstalled for real and put back by one
  hook run, which also proves the ordering against `check-setup.sh`.
- PR description rewritten; review thread replied to and resolved; `roadmap.md`, `notes`
  and `blockers` saved.

## Next

- Nothing outstanding on this branch. CI will re-run on `cb4d789a3`.
- **A defect in #151's tool, found while using it**: `plan_item_bootstrap update` has no
  way to clear a `blockers` list — `--blockers <empty file>` writes one empty blocker. The
  manifest was corrected by hand. #151 is blocked and unlanded, so this is a note for
  whoever resumes it, not work for this branch.
- **For the user, not for a session to decide**: `main` retired every workspace member's
  `requirements.txt` for static `[project] dependencies` (`4b4cfdf4`). `bastler` is not a
  workspace member so nothing fails, but its `requirements.txt` is now the last in the
  repository, and a session start is now one more thing that reads it.
- Two of the 2026-08-23 round's threads stay open on purpose (the `RESTACK_STEPS` name
  `monkeypatch.setattr` takes as a string, and the surviving `status_label` assertion).
- Landing order, not dependencies: #198 fixes a bug this branch carries verbatim at
  `bastler/stack.py`; #203 adds `.claude/setup_steps.py`, the same
  new-`.py`-under-`.claude/` problem a third time.
