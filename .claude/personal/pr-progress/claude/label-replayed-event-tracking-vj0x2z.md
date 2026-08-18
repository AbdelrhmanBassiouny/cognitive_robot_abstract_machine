# montessori_replay_event_annotations - draft PR #177

Plan item `montessori_replay_event_annotations` (montessori-eql-stack, track
`replay-annotation`). Branch `claude/label-replayed-event-tracking-vj0x2z`,
based on `montessori_event_replay` (#165); the manifest records the real branch
name rather than the planned one.

## Done

- `ReplayedMoment` (window + label + objects) replaces the bare `ReplayWindow`
  on an answer row; `InvolvesObjects` protocol lets an entity name its objects.
- `SegmindEventRecord.involved_object_names()` names the piece (as the viewer
  publishes it), the related body, and the hole an insertion went through.
- Popup URL carries `event=` and `objects=`; `Replay.label` renamed to
  `Replay.timeSpan`.
- Scene panel floats the caption over those objects and aims one arrow at each,
  re-placed inside `applyLive` so tips follow the objects; geometry lives in the
  pure `core/event_annotation.js`.
- Tests: new `test_event_annotation.js` (8), extended `test_replay.js`,
  `test_query_runner.py`, `test_montessori_sorting_progress.py`,
  `test_montessori_live_query.py`, `test_web_assets.py`.

## State

- `test/cramera_test`: 551 passed locally (python 3.12 venv at
  `/home/user/venv312`; the system python is 3.11 and too old for krrood).
- `test/experiments_test` cannot run here - no `rclpy`. The three demo-side
  assertions were exercised outside pytest against the same fixtures and hold;
  CI is the real check.
- Draft PR #177 open against `montessori_event_replay`. Nothing outstanding
  from this session; CI has not been read.
