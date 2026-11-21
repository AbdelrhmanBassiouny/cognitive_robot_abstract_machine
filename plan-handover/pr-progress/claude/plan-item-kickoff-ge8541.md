## Outstanding, for you
- **`CrossSectionClassifier` / `FootprintClassifier`** are used by nothing but their own
  tests now. AGENTS.md says consult before removing; asked on the PR, left standing.
- **One regression, marked**: `tracy_pickup_demo`'s lid cylinder is displaced by a prism
  fitted to the round hole's rim, 0.682 against 0.673. Pre-existing ghost that a mis-placed
  board had been hiding; marked against `competing-explanations`.
- **Cost**: 0.560 s/frame against 0.370 s, over the node's 0.5 s period. #231's
  `RectifiedFrame` and a believed place from the previous frame are the two ways back.
- **0.865 is six looks from one angle.** Measuring the real board would settle it, and would
  say whether the mesh should simply be re-cut.
