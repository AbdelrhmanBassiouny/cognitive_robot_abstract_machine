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

## Next

- Nothing outstanding in this session. CI has not reported yet on the pushed head.
- Note for whoever reviews: the pinned path is a placeholder (`<pinned>`) in the skill
  rather than a shell variable, because a variable does not survive between the commands
  a session runs.
