
# First-time setup for the Bastler system (PR #203)

Plan item: workflow-unification / bastler-first-time-setup.

## Plan

Give a newcomer one short page and one command, and put the three steps no
script can perform - fork labels, Claude's access to the fork, the
CLAUDE_PERSONAL_NOTES_* variables - where they are read rather than in prose.

## Done

- .claude/SETUP.md (41 lines): /setup-personal-notes, setup_steps.py,
  check-setup.sh.
- .claude/hooks/setup_steps.py: SetupChecklist.for_clone prints the three steps
  filled in from the resolved notes remote; repository-specific steps dropped
  when no GitHub remote resolves; only non-default settings listed as variables.
- 20 tests, each mutation-checked. .claude suite 551, was 531.
- Both READMEs point at SETUP.md; hooks/README.md keeps the reference role.
- Committed, pushed, draft PR #203 opened off main. Manifest and roadmap
  (decision 14) saved to the notes branch.

## Next

- Dashboard republish for workflow-unification.
- After #107 lands: wire setup_steps.py into setup-personal-notes/SKILL.md's
  steps 4 and 8, which this PR left untouched to avoid conflicting with that
  rewrite.

