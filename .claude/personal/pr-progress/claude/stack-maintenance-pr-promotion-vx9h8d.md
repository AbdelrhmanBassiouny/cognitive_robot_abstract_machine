## Branch `claude/stack-maintenance-pr-promotion-vx9h8d` - planning only, no implementation

The user asked for the promotion phase of `/stacked-pr-maintenance` to be reworked, and
explicitly asked for the plan item only: create it, record it, republish the dashboard,
end the session. No branch work, no PR.

### What the user asked for

- The compare-and-create link is built by a script, not assembled by the session.
- That script takes a title (the fork PR's own by default) and always puts the link back
  to the fork PR in the body.
- It also takes body text from its caller, and the skill always supplies that as a
  point-based summary.
- Neither the skill nor the Routine sends a notification.
- Every promoted PR is reported as a table - number, title, branch, ready open/compare
  link - in whichever session the skill ran in.
- As scripted, as model-based and as SOLID as possible, per AGENTS.md and personal notes.

### Done

- Read the promotion path end to end: `maintenance_promotion.promote`,
  `PromotionLink.build`, `stack.py promotion-link`, `maintenance_commands.py`,
  `SKILL.md`'s Finish section, `routine-prompt.md`.
- Established what already exists (title pass-through, fork-PR "Full detail" link, URL
  budget, truncation) versus what is missing (the body is derived from the fork
  description's first paragraph, not written; the table is hand-assembled by the session;
  the delivery assumes a completion email).
- New-vs-change checked mechanically with `git ls-tree main` over the three files: all
  landed, so this is a new item rather than a change to an unlanded PR.
- Overlaps found: #158 (`pinned-stack-tooling`) rewrites every SKILL.md invocation and
  asserts the allowed working-tree set - recorded as a `depends_on`. #155 is untracked,
  unlanded, and introduces the "turn its completion email on" paragraph this item
  reverses - flagged for a fold decision at kickoff.
- Filed `promotion-summaries-and-table` in `workflow-unification`, `stack-tooling` track,
  `not_started`, no branch, with the design and the open questions in `notes`; roadmap
  entry written; both saved to `claude/personal-notes`.

### Next

- Republish the `workflow-unification` dashboard, then end the session.
- Anything further is a kickoff session's work: `/plan-item-kickoff workflow-unification
  promotion-summaries-and-table`.

### Open questions left for kickoff, deliberately not invented

- Whether an already-registered Routine's completion email can be turned off in place -
  `update_trigger` has no notification field - or only by re-registering it.
- One invocation or two for the summaries (`run-report --summaries` versus `run-report`
  then `promote --summaries`). Two is recommended, since a summary cannot exist before
  the pass has decided a branch is promotable.
- Whether the #155 notification paragraph is folded into #155 or carried by this item.
