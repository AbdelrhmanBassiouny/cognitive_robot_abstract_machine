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
