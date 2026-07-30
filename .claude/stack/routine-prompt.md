# The Routine prompt to paste

The short prompt that goes into claude.ai/code/routines. `ROUTINE.md` next to this file is
the doctrine the Routine executes; this is only the pointer at it, plus the rules that have
to be in force *before* the Routine reads anything.

Why the hard rules are duplicated here rather than left in `ROUTINE.md` alone: a webhook
event can be delivered before the Routine's first tool call, so a rule that only exists in a
file the Routine has not opened yet has not taken effect when it is first needed.

`<FORK_REMOTE>` and `<UPSTREAM_REMOTE>` are placeholders.
`.claude/hooks/setup-stacked-prs.sh` prints this block with the resolved values substituted
in; pasting it by hand means substituting them yourself.

```text
You maintain a stacked-PR fork-staging workflow. `<FORK_REMOTE>` is my fork (the full stack);
`<UPSTREAM_REMOTE>` is the slow upstream review queue. Read `.claude/stack/ROUTINE.md` on the
checkout and execute it - it is the canonical doctrine for every phase, and it is on `main`, so
there is nothing to pull from another branch first. Do NOT use the Workflow tool. Use plain git
and the GitHub MCP.

HARD RULES, in force before you do anything else:
- NEVER call `subscribe_pr_activity`, and never stay subscribed - you learn CI by POLLING.
- If a review, review-comment, issue-comment, or any `<github-webhook-activity>` event is ever
  delivered to you, your ONLY valid action is to END THE TURN immediately: do not investigate,
  reply, plan, or ask me to confirm anything. The one exception is a CI/check *status* you were
  polling for your own restack.
- NEVER enter plan mode or post a "here's my plan" comment. You either perform a mechanical step
  from ROUTINE.md's phases or you stop.
- LABELS ARE REPLACE, NOT ADD: every label write takes the PR's entire new label set. Always read
  the current labels first and write the full computed set, or you silently wipe the others.
- Never force-push a branch with an open upstream PR unless it carries the `rebase` label.
```
