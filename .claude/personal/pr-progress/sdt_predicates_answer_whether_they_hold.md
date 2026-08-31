# PR #229 — predicates-answer-whether-they-hold (knowledge-directed-perception)

Branch `sdt_predicates_answer_whether_they_hold`, off `main`, draft.
Worked here via `/plan-item-resolve` in `auto` mode, 2026-08-31.

## What this resolve did

1. Verified the duplication against #33. **It was real and substantial.** Evidence in
   https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/229#issuecomment-5482272328
2. Fixed CI (`1120178b`): `mixins.py:942` called `is_supported_by` with the pre-rename
   keywords. The local verification could not see it — that test module needs ROS.
3. `Reachable` reads the pose as subject (`17631592`), as r3896606294 asked.
4. All four `Triple`-based relations state their own clause (`0b1234a0`), taking #33's
   reviewed wordings rather than a third set.

## The fold, settled by the developer

**#229 carries the predicate classes; #33 rebases onto it** and ports its 34 reviewed
wordings across. Recorded on both plans: knowledge-directed-perception's roadmap, and
eql-verbalization's `p4-sdt-migration` blockers + roadmap. Both dashboards republished.

## Still outstanding

- **The `Reachable` wording**, thread r3896606294, deliberately left open: this branch
  says what he asked; eql-verbalization decision 11 says the same thing at greater
  length. His pick applies to both branches.
- **CI on the latest push** is the only confirmation the `mixins.py` fix works, since
  `test_reasoning_queries.py` cannot be collected without ROS.
