# perception-backend (#222, branch `perception_eql_backend`, base #221)

Plan item `perception-backend` of `knowledge-directed-perception`. Kicked off
2026-08-30 in `auto` mode. The full reasoning is in that plan's `roadmap.md`
section of the same name; this is the working state.

## Plan

1. **krrood** - `Directive.LOOK_FOR = KeyWord("Look for")` in
   `verbalization/vocabulary/english.py`, and `BackendCannotResolveCondition` in
   `entity_query_language/exceptions.py` beside
   `SelectiveBackendCannotResolveEllipsisMatch`. krrood's tests use a mimic backend
   in `test/krrood_test/dataset` (self-containment rule), never the perception one.
2. **`SceneRequest`** in `perception/scene_source.py`: the detection type asked for
   and the supporting surface asked about. `MontessoriSceneSource.scene` takes it;
   `PerceivedObjects` is deleted.
3. **Pipeline** honours it: `searched_surfaces(board, request)` narrows to the named
   surface, `detect(frame, request)` skips the piece detector when no piece was asked
   for.
4. **`PerceptionBackend(SelectiveBackend)`** in `perception/backend.py`: compile the
   query to a `SceneRequest`, look, put the detections in the selected variable's
   domain, evaluate natively so residual conditions filter. Raise
   `BackendCannotResolveCondition` for a condition over any other variable.
5. **Node** keeps serving its newest look and ignores the narrowing - recorded, not
   accidental.
6. **Tests**, first, at three levels: the compiler alone, `searched_surfaces` alone,
   and end to end over the rendered scene fixture (the four retired `PerceivedObjects`
   tests, rewritten against the backend, plus a residual-condition test).

## Done

- Branch cut from `perception_per_supporting_surface`, draft #222 opened.
- Manifest: `status: in_progress`, branch/session/PR recorded; `depends_on` gained
  `detect-per-supporting-surface` (the attribution the pushdown compiles against is
  #221's, which the manifest had never recorded though #221's roadmap section had).
- Roadmap section written and pushed.

## Next

- Step 1 onward, tests first.

## Watch out for

- Base is #221, not #205. Do not restack onto #205.
- Correctness must never depend on the pushdown being honoured: pushed-down conditions
  stay in the `where` clause so native evaluation re-checks them.
- Run tests with `--noconftest` and the workspace on `PYTHONPATH`; #216/#221 recorded
  how to get the suite running in a container.
