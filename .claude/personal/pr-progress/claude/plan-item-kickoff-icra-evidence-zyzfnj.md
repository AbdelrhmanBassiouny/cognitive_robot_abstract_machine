# `question-set-and-ground-truth` (icra-evidence) — PR #295

Branch `claude/plan-item-kickoff-icra-evidence-zyzfnj`, cut off #278
(`episodes-queried-by-eql`). Kicked off in `auto` mode; the settled plan and
what building it found are both in `icra-evidence/roadmap.md` ("as planned" and
"as built", 2026-09-08).

## Done

- **Working-memory half** — `experiments/questions/` with `question.py`,
  `working_memory.py`, `question_set.py`. Thirteen questions across five
  buckets. **20 tests, run locally against a real twin, all passing.**
- **`a96531635` on #271's own branch** — `Episode.world` and
  `RecordedTrial.motion_statechart`, the fold `icra-foundation`'s roadmap
  recorded on 2026-09-08 but never made. Three round-trip tests; that PR's
  description and a comment carry the reasoning. Merged into this branch.
- **Long-term-memory half** — `long_term_memory.py`, six questions across three
  buckets through #278's `LongTermMemory.answer`, plus
  `test_long_term_questions.py`. CI-only.
- Manifest, roadmap and PR description all current; `question-set-answered-from-memory`
  and `episodes-recorded-through-ormatic` carry notes about what changed for them.

## Outstanding

1. **CI has not run yet.** Every long-term question crosses a to-many collection
   the episode model reaches through an association table, and nothing in the
   repository proves EQL translates a join across one — #278's own roadmap note
   left finding out to whoever needed it first, and that is this branch.
   `test_long_term_questions.py` is what answers it. If it fails, the shape
   changes in one place: each question's `query`.
2. **Three buckets have no long-term spelling** and one has none in either
   memory. Control waits on `control-constraints-and-degrees-of-freedom-queried`
   (its own recorded blocker); support and spatial relations over long-term
   memory waits on `query-routed-per-predicate` (not previously recorded
   anywhere); embodiment over long-term memory needs an episode to record which
   links were the robot's, which nobody owns yet.
3. **#271 is not a draft** and now carries a commit from this session. It was
   marked ready before, so it was left ready rather than re-drafted.

## Notes for whoever picks this up

- The workspace *does* install in a session container: a clean venv on Python
  3.12, `pip install -e` each package, plus stubs for the ROS message packages.
  What still cannot run is ORM generation (giskardpy's
  `DebugExpressionPublisher` needs a real `rclpy`), so anything touching the
  generated interface stays CI-only. The old "random_events needs a native
  library" note is wrong — the failures were `arff`/`dnutils`/`antlr4` against a
  Debian-patched setuptools.
