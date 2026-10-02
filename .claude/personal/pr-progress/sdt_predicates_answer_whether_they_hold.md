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

## Fork review round, 2026-10-01 (pushed as `581d941a`)

Four threads from the developer on `base.py` / `predicates.py`:
- TypeVar bound to `Triple` for `get_relation`'s relation (`BodyRelation`): done, resolved.
- `obj` loop variable in `get_relation` -> `tracked_body`: done, resolved.
- `VisibleTo.obj` -> `VisibleTo.entity` (tests, coraplex updated): done, resolved.
- "Restricted to Triple, not Predicate?": answered (Triple is the nearest existing bound,
  not exact; a dedicated body-to-body base would close it) — left open for the developer.
- `.living_worlds_tally/master.json` committed by accident in `581d941a` (a local pytest
  run + `git add -A`): removed in `498306d8`, replied, resolved. `main`'s `.gitignore`
  lacks the entry - a separate one-line fix off `main`, offered, not done.
- Developer chose `Triple.from_subject_object` + closing both gaps: done in `a326db09`
  (krrood `Triple` generic over `SubjectType`/`ObjectType` with `SubClassSafeGeneric`,
  `from_subject_object`, `subject_field_name`/`object_field_name`; sdt relations bind
  their types, `VisibleTo` via forward ref "Camera" (import cycle); segmind bound
  `Triple[Body, Body]`). Thread replied + resolved. krrood 2441 passed (2 graphviz env
  failures); sdt failures identical with change stashed.
- `.gitignore` fix opened separately as #481 (`bug`, draft, off `main`).
- `92bd9199`: `get_visible_bodies`, `VisibleTo`, `occluding_bodies` moved to
  `reasoning/robot_predicates.py` (above `robot_parts`), so `VisibleTo` binds `Camera`
  unquoted - the developer disliked the forward ref. Cause: annotation layer (`mixins.py`
  SupportedBy, `semantic_annotations.py` InsideOf, `robot_part_mixins.py` LeftOf/RightOf)
  imports `predicates.py`, and Camera is built on it. Deeper layering fix (annotations not
  calling predicates) offered as separate work, not done.

## Fork review round, 2026-10-02 (pushed as `0b35f6fa`)

- "Is the Camera not importable here?" (outdated, pre-`92bd9199`): answered (import cycle,
  fixed by the move), resolved.
- "Use typevars bounded to these types, everywhere (TBody, TRegion, ...)": done in
  `0b35f6fa` - InContactWith/SupportedBy `Triple[TBody, TBody]`, InsideRegion
  `Triple[TBody, TRegion]`, VisibleTo `Triple[TKinematicStructureEntity, TCamera]`, fields
  and subject/object typed the same. TBody/TRegion in world_entity.py, TCamera after
  Camera in robot_parts.py, TKinematicStructureEntity reused from mixins.py. Test now
  `test_a_relation_is_generic_in_the_kinds_of_thing_it_relates` (failed first).
  Not applied: segmind BodyRelation bound (TypeVars not allowed in a bound), krrood
  HasType (subject Any), krrood mimic (tests concrete read-back). Trade-off: mypy now
  accepts `get_relation(..., VisibleTo)` (bare generic = Any). Replied, left OPEN for the
  developer.
- sdt CI on `92bd9199`: 1770 passed, failed only on the combined world budget, 32/30
  (gw0 13, gw1 19). Same on `78510c56` (31); passed on `27f88034`, `581d941a`,
  `498306d8`; #481 (main) passed. Locally (no ROS) main and this branch both leave the
  same 2 worlds (test_body_filter, test_door_add_to_world). Session fixtures are torn down
  before pytest_sessionfinish, so the ~30 are held by something outliving the tests in
  ROS-only tests; CI prints only per-worker totals, so which tests is unknown. Suggested
  (not done): make the combined-limit failure print the per-test tally (a main change).

## CI world budget fixed, 2026-10-02 (pushed as `2502db19`)

- Reproduced in the CI image (docker in this container: start `dockerd`, pull
  `ghcr.io/abdelrhmanbassiouny/cognitive_robot_abstract_machine:jazzy`, `uv sync --extra dev
  --active` + `uv pip install drake` with `--network host` and the proxy CA, committed as
  `cram-ci:deps`; run with each worktree's `*/src` on PYTHONPATH, `-n auto`).
- Same 25 worlds on main and this branch. Holders (traced with a reverse-reference map):
  test_robot_joint_names' module-level lru_cache (11 per worker), CaseReasoner.rdrs
  class-level rule trees keeping the last case (4-5 per worker), unittest class attrs
  (ProcTHOR/Pipeline, 1 each).
- Fixes as separate bug PRs off main: #483 (each reasoner reads its own rules,
  cached_property; test test_each_reasoner_applies_rules_of_its_own) and #484
  (module-scoped indirect fixture). Both merged into this branch (0f5f498d, 2502db19).
  CI-image run after: 6 worlds (4/1/0/1), 1729 passed; rerun/sage10k failures are
  container-network only (same on main).

## Next

- Approve CI on the new head; confirm segmind's new test and the sdt job.
- Confirm sdt CI green on `2502db19`; land #483 and #484 on main.
- Developer to settle the TypeVar thread's exceptions/trade-off and close it.
- Developer to decide whether to drop the `integration-conflict` label.
- Upstream threads: the developer replies/resolves on cram2#655 (sessions may not).
