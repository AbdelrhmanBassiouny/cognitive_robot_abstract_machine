# montessori_replay_event_annotations (plan item, montessori-eql-stack / replay-annotation)

Branch: `claude/label-replayed-event-tracking-vj0x2z` (the session's designated
branch; the manifest planned `montessori_replay_event_annotations`, and the
manifest entry has been corrected to the real branch name).
Based on `montessori_event_replay` (#165), which the item depends on.

## Plan

1. Python: an answer row's replay entry carries what the replay shows, not only
   when it happened - the event's label and the objects it involved
   (`ReplayedMoment` in `knowledge/replay.py`, a protocol in `query_runner.py`
   for entities that name their objects).
2. Demo: `SegmindEventRecord` names its objects (the piece, the other body, the
   hole) so its rows carry them.
3. Web: the replay popup URL carries label + objects; the scene panel floats a
   caption naming the event over those objects and draws an arrow from it to
   each, re-aimed every frame so the tips follow the objects as the clip plays.
   Arrow/caption geometry lives in a pure `core/event_annotation.js`.

## State

- Environment: python 3.12 venv at `/home/user/venv312` runs the cramera suite;
  `test/experiments_test` cannot run here (no `rclpy`).
- Next: write the failing tests, then implement.
