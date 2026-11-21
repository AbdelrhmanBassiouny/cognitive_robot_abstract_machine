### Outstanding
- Nothing on this session's side. Both review threads are answered and deliberately left
  open for the developer: the `Point2`-or-`PlanarPoint` choice, and whether an RDR
  `Expert` should be a `BeliefSource`.
- Landing hazards on the PR: #223's `Footprint` -> `RectifiedFootprint` rename, now also
  meeting this branch's edit to `hole_geometry.py`; #223 meeting `PieceHypothesis.candidates`
  (a tuple of dataclasses) and `PieceHypothesis.source` (an abstract krrood mixin `World`
  also inherits) when it walks this package for the ORM; and #231's `LoosePieceDetector`
  -> `EdgeFitDetector` rename, which changes the same `detect` this branch rewrites and
  must keep its new `BeliefSource` base - the only conflict of the three that is not
  purely mechanical.
- Environment note worth keeping: this container's default `uv` (0.8.17) cannot parse the
  repo's `pyproject.toml`; `/usr/local/bin/uv` (0.12.7) can. `docformatter`/`black` need
  installing before `scripts/format_docstrings.py` runs, and it needs them on `PATH`, not
  only importable.
