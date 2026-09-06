PR #281: Prioritize bug-fix and tooling branches in the integration build's
merge order. Base: claude/plan-item-kickoff-workflow-ixbvxl (#154) - this is
where integration_selection.py and the current stack.py/Configuration shape
live; main doesn't have them yet.

Plan: add `bug`/`tooling` DefaultLabel members + Configuration fields, a
BranchPriority enum (BUG < TOOLING < ORDINARY), Stack.priority(), and make
tips_of() sort by (priority, pull_request_number) instead of PR number alone.

Status: DONE and pushed. All .claude/stack/tests pass (320 on this branch's
base). Docstrings formatted. PR opened as draft against #154.

Next: none from this session - opening the PR ends this session's
obligation to it per the personal workflow notes. Outstanding for the
user: create the `tooling` label on GitHub (no available tool can create
repo labels); the PR body says so. Whoever reviews should also watch
whether this collides with the same `.claude/stack/`-touching cluster the
#111/shared-pr-state-chips rename is already colliding with (see the
Integration Status artifact from earlier this session) - this PR is small
and additive so it likely doesn't, but it wasn't rebuilt against that build
to confirm.
