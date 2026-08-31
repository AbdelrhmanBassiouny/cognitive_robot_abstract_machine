# `choose-detection-method` — PR #231 (draft)

Plan `knowledge-directed-perception`, track `method-selection`. Branch
`claude/choose-detection-method-gf64yp`, based on `perception_eql_backend` (#222)
with `sdt_surface_finish_annotation` (#216) merged in. Built as `69f30348a`,
review round answered as `92afdcd82`.

## Status: first review round answered, one thread deliberately open

The item's work is done and the pull request is a draft. Of the two review
threads of 2026-08-31, the typing one is answered and resolved; the design one
is answered and **left open on purpose** — see "The review round" below. No
conflict. The developer merged the parent branches down the stack himself
(`2d73e8905`) before reviewing.

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
- Choosing for one surface costs **1.0 ms** stated once vs **4.4 ms** stated per
  look, over the four known pieces on a matte lid.
- Tests: **233 passed**, 1 skipped, 16 xfailed vs **205 / 1 / 16** on the parent.

## The review round of 2026-08-31

Two threads, both on `detector_choice.py`.

1. *"this returns a ConditionType right? not Any right?"* — yes. `capability` is
   `(self, look: TargetOnSurface) -> ConditionType` now, and stopped being a
   `@classmethod` so a detector can state a capability that depends on how it was
   configured. **Answered and resolved.**
2. *"if you are going to create the query/rule tree here and also evaluate it
   here then there's no point of using EQL here at all … The point of using EQL
   RDRs is extensibility with new situations through interaction with an
   expert."* — right, and it applied to `PieceDetector.answers` too.

   The tree is stated once now, in `__post_init__`, and a look is decided by
   binding it to the one variable every rule states its conditions over — the
   rebind krrood's own `GuardCondition.holds_for` performs. `add_rule` grows the
   tree while it is in use, via `Alternative.insert_at`, attaching beside the
   exceptions already stated (two refinements at one anchor return the same
   detector twice; an else-if chain answers once — measured). A test pins that a
   rule added at runtime changes the next look's answer, and it fails if the tree
   is rebuilt per look.

   **Left open** because the other half — *asking* an expert when no rule fires —
   is not here: that interface is on #98/#159/#76, and staying off the engine is
   the developer's own decision from earlier the same day. The reply offers to
   merge #159 in and puts the call back to him rather than reversing it silently.

## The blocker was not real — and the correction went further

"krrood's ripple-down rules are not usable yet" is true only of the *classic*
`krrood.ripple_down_rules` (source-string conditions, an `Expert` needed for every
tree mutation). Two things are usable:

- **EQL-native rule trees**, on `main` today — what #231 uses. `test_rules.py`
  24 passed, no skips.
- **The EQL-native RDR engine**, by stacking. #64 → #65 → #66 → #67 → #98 →
  #159 (`EQLSingleClassRDR`) → #210 → #79 → #76 → #80 → #77 (`@rdr`) are all
  open, out of draft and reviewed.

I first recorded the engine as unusable because it is unmerged. That was wrong:
this plan's rule is that `depends_on` means *stacked on*, never waiting for a
merge. **Read draft + review state, not merge state.**

`detector-parameters-from-knowledge` is therefore not blocked and should stack on
**#159** (`render_tree` is its "inspectable rule tree").
`tune-detection-rules-against-the-camera` is **un-deferred** (developer's call,
2026-08-31) and stacks on **#77**, the tip: #76/#80/#77 are most of its tooling
already, so what remains is the perception-side presenter, not the expert
interface underneath it.

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

Nothing required on #231 unless the developer takes up the offer on thread
`r3898606395` to put the tree behind `EQLSingleClassRDR` (#159). Follow-ups belong to other items: history conditions to
`pieces-looked-for-where-expected` (#232), a measured board colour to
`detector-parameters-from-knowledge`, and the RDR engine to that item (#159) and
to `tune-detection-rules-against-the-camera` (#77).

**Why #231 keeps its stated tree rather than using the engine** (developer's
call): `EQLSingleClassRDR.query` is `init=False`, so the engine grows its tree by
fitting cases through an `Expert` — two known rules would become
fitted-from-examples rather than stated; and merging #159 in adds 9,236 lines to a
600-line PR (#77 adds 22,745).
