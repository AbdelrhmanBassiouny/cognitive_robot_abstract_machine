# `choose-detection-method` — PR #231 (draft)

Plan `knowledge-directed-perception`, track `method-selection`. Branch
`claude/choose-detection-method-gf64yp`, based on `perception_eql_backend` (#222)
with `sdt_surface_finish_annotation` (#216) merged in.

## The plan

Two layers, settled with the developer at kickoff (both, layered — not one or the other):

1. **Detectors declare what they can answer**, as an entity query language condition.
   Eligibility. Answers r3893463818 on #222.
2. **A ripple-down rule tree chooses among the eligible ones**, over the surface's finish,
   the target's hue separability from it, and (later, from sibling items) what lately
   happened to the target. Preference. This is the half the paper's claim rests on.

Three rules, which is the plan's promised two sharpened per #201's 2026-08-30 comment:
mirror surface → edge fit; matte surface + hue-separable target → colour blob (cheaper);
target wearing the surface's own hue → edge fit whatever the finish.

## Done

- Branch reset off `integration` onto #222's tip (the #199 hazard, 4th time on this plan).
- #216 merged in for `Shape.finish`.
- Draft PR #231 opened; manifest + roadmap section saved to personal-notes (`5d73be145`).
- **Blocker investigated and cleared.** The recorded "krrood's ripple-down rules are not
  usable yet" is true of classic `krrood.ripple_down_rules` (source-string conditions, an
  `Expert` required for every tree mutation) and of `EQLSingleClassRDR` (eight unmerged PRs
  deep in the `D-core-*` stack), but *not* of the EQL-native rule trees the item's note
  actually describes. `test_rules.py` = 24 passed here, no skips.
- Container environment working: python3.12 venv at `/tmp/venv312`, workspace installed
  editable, run pytest with `--confcutdir=test/krrood_test` to skip the ROS-importing
  top-level conftest. `uv sync` does **not** work — `pyproject.toml`'s
  `[tool.uv] override-dependencies` uses a map form uv rejects (fails on `main` too).

## Next

- Tests first: the detector interface and its capability declaration; the rule tree's three
  rules; end to end over the rendered scene fixture.
- Then: `PieceDetector` interface, `EdgeFitDetector` (today's `LoosePieceDetector`),
  `ColorBlobDetector` (new, cheaper), the rule tree, and the pipeline reading it.
- Annotate the table as `MIRROR` and the board lid as `MATTE` in `MontessoriWorld`.

## Flagged, not yet reported to the developer

`.claude/hooks/plan_item_bootstrap.py` writes item fields at 4-space indent
(`ITEM_FIELD_INDENT`) while this plan's manifest uses 2, producing invalid YAML — both
`open` and `record` fail. Same on `main`. Worked around by editing `plan.yaml` directly.
Worth its own bug-fix PR (the #160 family).
