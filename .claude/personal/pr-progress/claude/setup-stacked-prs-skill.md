# PR #110 — `/setup-stacked-prs`, its setup script and read-only checker

Plan item `setup-stacked-prs-skill` of `workflow-unification` (tracking issue #102).
Draft, based on `claude/setup-personal-notes-script` (#107).

## Where it stands (2026-08-28)

Resolved from `/plan-item-resolve`. Two things were blocking it and only the first was
recorded:

- **The merge conflict** with its base — `needs-resolution` since 2026-08-12, reported by
  the pass seven times. Cleared: `git merge-tree` against the base is clean, label removed.
- **A review round of 2026-08-20 nothing had touched**, because the branch's last commit was
  2026-08-10. Both threads applied.

Head `b940a4fe`, two commits: the base merge, then the review round.

## Done

- Fourth base merge. Four conflicts; three additive, one (`test_check_setup_sh.py`) where
  each side alone is broken and the answer is neither — `main`'s `run_hook_script` *plus*
  this branch's `SetupCheck` argument.
- Four integration breaks behind clean markers: `maintenance.py` importing two error classes
  this branch deletes; `test_maintenance.py`'s `Configuration` missing the two new settings;
  its `ForkCheckout` standing in for a checkout nobody ran setup on; `write-branch-files.sh`
  inventing a second wording for the no-op three sibling hooks already word.
- `install_hook_scripts` derives a script's siblings instead of taking a list — the same
  break had been fixed by hand at three call sites already, and this incidentally fixed two
  of the base's own failures.
- Review round: `remote_branch_commit` uses `run_git`; `SetupReport.exit_code` is an
  `ExitCode(IntEnum)`, read by fourteen assertions.
- 626 tests pass across the four directories CI runs, from 463.
- PR description, plan manifest and roadmap all brought current.

## Outstanding — none of it this branch's

- **Five red tests**, all `test_setup_personal_notes_sh.py`, a strict subset of the seven red
  on #107 itself (measured by running the base's own tree). `main`'s new `git_identity` check
  makes `setup-personal-notes.sh` exit 1. #107's script, #107 lands first; proposed fix stated
  on the PR.
- **Both review threads still open**, and answered. They sit in a *pending* review, and
  GitHub allows one per user, so inline replies are refused. The replies are in a conversation
  comment. Submitting that draft is the user's call; once it is, the threads can be closed
  where they were raised.
- CI has not re-run since the push — check `test_claude_dev_tooling` on `b940a4fe`.

## Next

Nothing until the user acts: submit the pending review, or land #107 so the five inherited
failures go away.
