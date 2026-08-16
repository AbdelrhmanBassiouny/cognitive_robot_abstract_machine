# EQL where-is queries + general viewer highlighting (montessori)

Branch is based on `origin/montessori_fast_inline_monitor` (per request), not main.

Plan:
1. cramera query runner: `highlightable_ids` set on EqlQueryRunner/RowRenderer —
   any string answer value naming a published viewer object gets highlighted
   (general, not query-tied; unknown values are ignored client-side anyway).
2. cramera live bridge: demos can register extra fixed scene entities (board
   Body, hole Regions) so the viewer renders + highlights them;
   body_geometry learns Region (`area`) measurement/mesh serving;
   run_query passes published keys as highlightable ids.
3. experiments/montessori: scene_layout.py records (HoleRecord, BoardRecord,
   InsertionGoalRecord + SceneLayout.of_world); new `hole`/`board`/`goal`
   domains + where-is presets (square hole, all holes, montessori box, goal
   per shape); ShapeUnderTest.related_highlight_ids -> its published shape
   body; _attach_cramera registers board+holes and builds the layout.
   New presets stay OUT of MONTESSORI_PRESETS (bundle presets.json submodule
   pin is unfetchable, sync test must keep passing).
4. Tests in test/cramera_test + test/experiments_test; format; push.

Status: environment synced with uv; design settled; implementing (1).
Frontend needs no change: latest query already replaces highlights, unknown
ids are ignored.
