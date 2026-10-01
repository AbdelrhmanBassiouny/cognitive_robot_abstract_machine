# PR #229 — predicates-answer-whether-they-hold (knowledge-directed-requests)

Branch `sdt_predicates_answer_whether_they_hold`, off `main`. Out of draft and promoted
upstream as cram2#655 (`in-review`). Last worked via `/plan-item-resolve PR 229` in `auto`
mode, 2026-10-01 (session_016LRmUnGe5NAuEmCxZy9E6t).

## What stalled it (found 2026-10-01)

1. **Upstream review**, invisible from the fork PR: tomsch420 requested changes on
   cram2#655 (2026-09-22); three threads open, all agreed by the developer on 2026-10-01.
   LucaKro's thread (drop the function aliases) was already settled by `f218400e`.
2. **sdt CI red with every test passing**: the combined worlds-in-memory budget in
   `test/conftest.py` (31 vs 30), flipping between runs of the same tree. Not root-caused.
3. **`integration-conflict` label** blaming #226 — a misattribution of that same budget.
4. **Head CI not run**: bot-pushed merges of `main` sit at `action_required`.

## Done this round (pushed as `27f88034`)

- `9fcff7cf`: removed `Stable` (r4069020640), which also settles r4069017507 (`obj`).
- `27f88034`: segmind `get_relation` takes the relation class; lambdas gone (r4069013391);
  new test `test_a_relation_relates_only_the_bodies_it_holds_between` (CI-only, ROS).
- PR description rewritten to the branch's current state.
- Formatter deliberately not applied to segmind files (would reformat ~450 lines).

## Next

- Approve CI on the new head; confirm segmind's new test and the sdt job.
- Root-cause the 31/30 world budget in a ROS environment (which ROS-only test leaves a
  per-process world), or decide the budget on `main` is set too tight.
- Developer to decide whether to drop the `integration-conflict` label.
- Upstream threads: the developer replies/resolves on cram2#655 (sessions may not).
