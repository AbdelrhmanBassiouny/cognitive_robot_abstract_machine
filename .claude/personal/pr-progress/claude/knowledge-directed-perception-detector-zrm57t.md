# `detector-parameters-from-knowledge` - #239, off #231

Plan item of `knowledge-directed-perception` (tracking issue #201), track
`method-selection`. Branch `claude/knowledge-directed-perception-detector-zrm57t`,
re-cut off `claude/choose-detection-method-gf64yp` (#231, `open_ready`).

## The plan

1. Merge #159 (`EQLSingleClassRDR`) in. Trial-merged clean before the branch was
   opened: no conflict, 9,236 lines over 50 files. This is what the item was told
   to stack on - `render_tree` is what its own ask for "an inspectable rule tree"
   names, and #231 recorded that both this item and the tuning item belong on it.
2. `DetectionParameters` - the numbers one look needs, in one value object. The
   detectors read one per look instead of carrying their own fields.
3. The knowledge moves onto the twin: the board's measured surface colour, the
   board's own hole count / lid area / footprint, the hole marker's thickness, and
   each piece's measured hue and height.
4. `DetectionParameterRules` - an `EQLSingleClassRDR` over #231's `TargetOnSurface`,
   concluding a `DetectionParameters`, authored by fitting through a scripted expert
   and rendered by `render_tree`.
5. `EdgeFitDetector._piece_at`'s guard chain becomes rules that say which condition
   refused a contour - the developer's `pipeline.py:619` ask.

Tests first at each step, per TDD. The checkable outcome is that #231's amber-piece
rule fires on the real board once the measured colour is on the twin.

## Done

- Branch re-cut onto #231's tip; bootstrap commit pushed.
- Draft #239 opened; `plan.yaml` and `roadmap.md` recorded (by hand - the bootstrap
  script's four-space indentation fault again, fourth occurrence).

## Next

- Step 1: merge #159 in.

## Deliberately out of scope, recorded on the roadmap

The reach of a seeded search (#232 already moved it onto `BelievedPlace`), how much
better one explanation must be (`competing-explanations`), the mesh classification
thresholds (#236 deletes the classifier), and the interactive presenter (its own item).
