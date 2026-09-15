Branch claude/collision-rule-tolerates-missing-buffer-zone-distance, based on main.
Bug-fix draft PR #386, label bug. Unrelated to the insertion branch below; created while
generating the paper's reproduction-package figures (see the reproduction_package README's
"Known limitation: read-back on old episodes") because episode 25f5161da5584bac9554b686711a01fe
needs it to deserialize.

Plan:
- [x] proved the bug with a failing test first (TDD): serialize a default
      AvoidExternalCollisions, delete buffer_zone_distance/violated_distance, from_json
      raised KeyError -> BrokenWorldModificationHistoryError during a world-modification
      replay.
- [x] fix: _from_json only reads whichever of the two keys is present; AvoidCollisionRule's
      own dataclass defaults (0.05, 0.0) supply the rest.
- [x] tests: new TestAvoidExternalCollisionsReadsOldSerializations passes; full
      test_collision_matrix.py + test_json_parsing.py (125 passed, 2 pre-existing skips).
- [x] pushed, opened draft PR #386.
- [ ] nothing else outstanding on this PR; session used the fix branch's checkout (cherry-
      picked locally, not pushed) to run the reproduction-package pipeline against real
      episodes -- see the other work in this session's chat, not tracked here since it is
      not this PR's own work.

