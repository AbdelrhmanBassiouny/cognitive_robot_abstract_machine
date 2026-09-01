# `detector-parameters-from-knowledge` - #239, off #231

Plan item of `knowledge-directed-perception` (tracking issue #201), track
`method-selection`. Branch `claude/knowledge-directed-perception-detector-zrm57t`,
re-cut off `claude/choose-detection-method-gf64yp` (#231, `open_ready`), with
#159 merged in.

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

## Done

- Branch re-cut onto #231's tip (arrived cut from `integration` - the #199
  hazard, seventh time on this plan); draft #239 opened; `plan.yaml` and
  `roadmap.md` recorded by hand (bootstrap script's four-space indentation
  fault again, fourth occurrence); dashboard republished.
- #159 merged in, clean.
- `3a493be9` - the board's lid states the hue measured off the real board and a
  matte finish; Tracy's table states its own near-colourless grey and a mirror
  finish. #231's rule tree fires on a real world for the first time. 7 new
  tests; **397 passed** against **390** on the parent, nothing else moved.

## Findings worth keeping

- **The finish, not the colour, was the gate.** #221 and #231 both record
  `BOARD_COLOR` as "eleven hues from the wood the camera measures". Measured:
  `Color.BEIGE()` is hue **17** against the wood's **19** - two hues, inside the
  four-hue tolerance either way, so the amber rule already fell back to the edge
  fit. What kept the tree from ever firing was that no world stated a finish.
- **An appearance must be on the collision geometry.** `WorkspaceSurface.of_body`
  reads the widest horizontal *collision* shape, so a finish stated only on the
  board's visual mesh is invisible to perception. Found by the test failing.
- Every `KNOWN_PIECE` stands 0.03 m, so moving `piece_height` off the detector
  onto the candidates is behaviour-identical on this set - worth knowing for
  step 3.

## Next

- Step 3: `DetectionParameters`.

## Deliberately out of scope, recorded on the roadmap

The reach of a seeded search (#232 already moved it onto `BelievedPlace`), how
much better one explanation must be (`competing-explanations`), the mesh
classification thresholds (#236 deletes the classifier), and the interactive
presenter (its own item).

## Environment

uv 0.12.8 from `astral.sh` into `/tmp/uvbin` (the `uv` on `PATH` is 0.8.17 and
cannot parse this repo's `pyproject.toml`); then `uv sync --extra dev --python
3.12`. Run pytest with `--noconftest`, deselecting the six ROS-2 modules.
`black`/`docformatter` need installing into `.venv` before
`scripts/format_docstrings.py` will run, and `.venv/bin` must be on `PATH`.
