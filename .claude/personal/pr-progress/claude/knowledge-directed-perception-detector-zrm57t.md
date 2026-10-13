## Next
- Step 3: `DetectionParameters`.


## The plan
1. ~~Merge #159 (`EQLSingleClassRDR`) in.~~ Done, no conflict, 9,236 lines.
2. ~~The twin states its surfaces' measured colour and finish.~~ Done.
3. `DetectionParameters` - the numbers one look reads the picture with, in one
   value object the detectors are handed instead of carrying as fields. This is
   the literal ask in seven of the nine #202 threads. Touches `pipeline.py`
   (`SurfaceColors`, `SizeRange`, both `PieceDetector`s) and `piece_matcher.py`.
4. `DetectionParameterRules` - an `EQLSingleClassRDR` over #231's
   `TargetOnSurface`, concluding a `DetectionParameters`, rendered by
   `render_tree`. Needs a scripted `ExpertInterface`: the engine's `query` is
   `init=False`, so rules are authored by fitting known situations with targets,
   and only `AnswerName.CONDITIONS` is asked for.
5. `EdgeFitDetector._piece_at`'s guard chain becomes rules that say which
   condition refused a contour - the `pipeline.py:619` ask.


## Deliberately out of scope, recorded on the roadmap
The reach of a seeded search (#232 already moved it onto `BelievedPlace`), how
much better one explanation must be (`competing-explanations`), the mesh
classification thresholds (#236 deletes the classifier), and the interactive
presenter (its own item).
