This designated branch carries no commits. `/plan-item-resolve rdr-refactor
d-core-backend` worked the item on its own branch, `D-core-backend` (PR #210),
following the precedent every sibling in this stack set.

The record lives where the tooling reads it, not here: the item's `notes` and
`blockers` in `.claude/personal/plans/rdr-refactor/plan.yaml`, and section 32 of
that plan's `roadmap.md`.

**Done this round** (`e70fd6ff6`): `RDRBackend` inherits `QueryBackend` and gains
`evaluate`, answering the `backend.py:92` review thread as asked; the new
`QueryIsNotAMatch` refuses an expression with no `...` to complete. Three tests,
each mutation-checked. `test_eql_rdr` 261 → 264 with zero baseline ids lost.

**Outstanding, both recorded as the item's blockers:**

1. The `backend.py:36` `GroundTruth` thread is answered and left open — three
   options are on it and the choice is the developer's.
2. `test_each_lib (semantic_digital_twin)` is red on a physics test this diff
   cannot reach. #190 fixed its cause on `main` on 2026-08-24; this branch is 342
   commits behind `main` and lacks it. Only a steward cascade clears it.
