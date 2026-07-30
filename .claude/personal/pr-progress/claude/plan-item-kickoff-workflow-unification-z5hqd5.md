# /plan-item-kickoff workflow-unification routine-cutover (2026-07-30)

Kickoff-only session: no code branch, no PR (the item is a Routine-prompt change).

Done:
- Gathered full context; found the live Routine (trigger trig_01N79jHmLo3bSbg8pLM6MNTB,
  "PR Stack Monitor and Update") and diffed its prompt against #106's ROUTINE.md.
- Plan approved: slim pointer prompt (3 inline HARD RULES + read-ROUTINE.md-and-execute),
  executable via update_trigger. Exact text + execution checklist recorded in the
  workflow-unification roadmap addendum of 2026-07-30.
- plan.yaml: routine-cutover -> in_progress with this session's link; also restored PR 3's
  clobbered kickoff state (stale-scaffold save race, bdd0beaa reverting 973ff31a).
- Subscribed to tracking issue #102. No send_later armed (no-scheduled-checks rule).

Next:
- Wait for the gate: PR 1 (#106) on cram2/main and fork main fast-forwarded (observable:
  .claude/stack/ROUTINE.md present on origin/main). #101 still open in-review, so not yet.
- At the gate: run the execution checklist in the roadmap addendum (any session can),
  then one green routine cycle -> item done, unblocking tooling-branch-retirement.
- Done (user-approved): relayed the two wording nits to #106 as a conversation comment
  (https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/106#issuecomment-5132585483).
