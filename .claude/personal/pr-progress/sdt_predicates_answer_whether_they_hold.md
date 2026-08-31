# PR #229 — predicates-answer-whether-they-hold (knowledge-directed-perception)

Branch `sdt_predicates_answer_whether_they_hold`, off `main`, draft.
Worked here via `/plan-item-resolve` in `auto` mode, 2026-08-31.

## Plan for this resolve

1. Verify the developer's review question — does this duplicate #33? **Done: yes,
   substantially.** Evidence and the recommendation are in
   https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/229#issuecomment-5482272328
   and in the plan's roadmap.
2. Fix the CI failure. **Done** (`1120178b`): `mixins.py:942` called `is_supported_by`
   by keyword with the pre-rename names.
3. Answer review thread r3896606294 (`Reachable` wording). **Done** (`17631592`),
   thread left open on purpose — #33's decision 11 words it differently.
4. Record the duplication on `blockers`/roadmap and republish the dashboard. **Done.**

## Blocked on

**The developer's fold decision.** Recommended: this branch carries the predicate
classes, #33 rebases onto it and ports its reviewed wordings across. The alternative
is closing this and moving the threshold field onto #33. Nothing else here moves
until that is answered, because it decides which set of wordings survives.

## Known and deliberately not fixed

The four `Triple`-based relations render ungrammatically (*"a Body supports by
another Body"*, *"visibles to a Camera"*, *"is in a contact with"*, *"supports a
something"*). #33 already has correct reviewed wordings for all four; writing a third
set before the fold question is settled would be one more copy of the same argument.
