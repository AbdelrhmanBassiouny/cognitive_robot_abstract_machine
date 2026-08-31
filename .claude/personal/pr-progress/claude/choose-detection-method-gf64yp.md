# `choose-detection-method` — PR #231 (draft)

Plan `knowledge-directed-perception`, track `method-selection`. Branch
`claude/choose-detection-method-gf64yp`, based on `perception_eql_backend` (#222)
with `sdt_surface_finish_annotation` (#216) merged in. Built as `69f30348a`.

## Status: built, pushed, description and roadmap current

The item's work is done and the pull request is a draft awaiting review. Nothing
is outstanding on it: CI not yet reported at the time of writing, no review
threads, no conflict.

## What was built

Two layers, chosen by the developer at kickoff:

1. **Detectors declare what they can answer**, as an EQL condition
   (`PieceDetector.capability`).
2. **A ripple-down rule tree chooses among the eligible ones** — mirror → edge
   fit; matte + colour separates → colour blob.

The planned third rule turned out to be the colour blob's *capability* going
false rather than a rule, so the tree ships two rules, which is what the budget
section asks for.

## Measurements worth keeping

- Colour blob **89 ms** vs edge fit **126 ms** on the same work, same pieces
  found, comparable agreement. That is the "speed is the honest reason" claim.
- Choosing per piece splits a surface between detectors, which first made the
  annotated path **slower** (0.596 vs 0.521 s/frame). `RectifiedFrame` shares each
  plane and its edges per frame → **0.494 vs 0.491**, and the unannotated path
  improved too (0.521 → 0.491).
- Tests: **230 passed**, 1 skipped, 16 xfailed vs **205 / 1 / 16** on the parent.

## The blocker was not real

"krrood's ripple-down rules are not usable yet" is true of the *classic*
`krrood.ripple_down_rules` and of `EQLSingleClassRDR` (eight unmerged PRs deep),
and false of the EQL-native rule trees the item's own note describes — those are
on `main` today, `test_rules.py` 24 passed, no skips.
`detector-parameters-from-knowledge` is therefore not blocked either.

## Environment (this container)

- `uv sync` is **broken on `main`** — `[tool.uv] override-dependencies` uses a map
  form uv rejects (since `b37c29996`). Use a python3.12 venv (`/tmp/venv312`) with
  every workspace package `pip install --no-deps -e`, plus `casadi~=3.7.0` pinned
  (3.8 raises out of `FunctionBuffer_set_res`).
- Run montessori tests with `--noconftest`, ignoring the six ROS-importing modules.
- krrood tests: `--confcutdir=test/krrood_test` to skip the ROS-importing top-level
  conftest.

## Flagged to the developer, not yet acted on

`.claude/hooks/plan_item_bootstrap.py` writes item fields at 4-space indent while
this plan's `plan.yaml` uses 2, producing invalid YAML — `open` and `record` both
fail, and `save-plan.sh`'s error is swallowed by `capture_output=True`. Same on
`main`; the #160 family. Worked around by editing `plan.yaml` directly. Deserves
its own bug-fix PR.

## Next, if anyone picks this up

Nothing required. Follow-ups belong to other items: history conditions to
`pieces-looked-for-where-expected` (#232), a measured board colour to
`detector-parameters-from-knowledge`.
