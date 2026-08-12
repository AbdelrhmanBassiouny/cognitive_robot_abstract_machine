# PR #158 - pin the stack tooling for the length of a maintenance pass

Plan item: `workflow-unification` / `pinned-stack-tooling` (stack-tooling track).
Branch off `main`, draft, `bug` label. One root cause, no unrelated cleanup.

## Plan

1. Prove the bug: a scratch checkout carrying the tooling, a second branch carrying a
   version whose command set differs, and the in-tree invocation failing after the switch.
2. `stack.py pin-tooling`: copy the tool outside every checkout, print the copy's
   `stack.py`.
3. `SKILL.md` step 0c pins right after `configuration`; every later command names the
   pinned copy; a test asserts nothing else runs from the working tree.

## Done

- Failing tests first, then `WorkingTreeTooling` / `PinnedTooling` and the `pin-tooling`
  subcommand in `stack.py`; board snapshot deliberately not copied.
- `SKILL.md` step 0c plus every invocation after it repointed at `<pinned>/…`; README
  command list updated.
- Verified the behavioural tests fail against a `pin_to` that returns the in-tree
  directory, so they detect the bug and not just the missing subcommand.
- 163 tests pass in `.claude/stack/tests/`, 253 across the three directories CI runs.
- Draft PR #158 opened, `bug` label applied, plan item and roadmap saved.

## Review round 2026-08-12 (applied in 0c7eef93)

- Inline comment (use the GitCommandRunner class from the branch that has it): applied
  using main's copy - #139 landed it hours earlier at
  `.claude/stack/maintenance_git_commands.py:130`, so there was nothing to base on.
  Declined basing on #151 (unlanded, 159 behind main). Replied, left open, since the
  literal ask was answered differently.
- Applying it exposed that the helper wrote the other tool version itself, so the file
  changed because the test wrote it rather than because git moved it. Both versions are
  committed at install time now and the step is only a branch switch; mutation-checked
  that removing the switch fails the hazard test, where before the write masked it.
- Review-level question (fast-forward main and restack everything instead): answered on
  the PR, no change - circular (the restack is run by the tool in question), skips the
  branches that differ most (#110/#111 are needs-resolution and carry `preflight`, no
  `check-move`, no `maintenance.py`), and a branch editing the tooling is meant to differ.
- 471 tests across the three CI directories. Manifest notes, roadmap entry and dashboard
  all updated; PR description corrected (it had said 253, which was two directories).

## Next

- Nothing outstanding. Two review threads exist; both replied to, one deliberately left
  open for the user to close.
