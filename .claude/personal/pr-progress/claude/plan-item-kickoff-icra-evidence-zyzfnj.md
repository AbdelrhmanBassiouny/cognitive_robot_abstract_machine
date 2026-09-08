
# `question-set-and-ground-truth` (icra-evidence) — PR #295

Branch `claude/plan-item-kickoff-icra-evidence-zyzfnj`, cut off #278. Reviewed
2026-09-08 and largely rebuilt in response; the round is written up in
`icra-evidence/roadmap.md` ("reviewed 2026-09-08").

## Done

- **Working-memory half rebuilt around the reviewer's direction.** Nothing is
  handed to a question: every variable is domainless and ranges over the symbol
  graph, what a question is about is a condition, and the source is the robot.
  `DetectionEvent` inherits `Symbol`; agency goes through a new
  `ManipulatesBodies` mixin; the set is read off the question subclasses.
  **20 tests, run locally against a real twin, fixed and random order.**
- **Two EQL defects measured, not assumed.** `exists` answers the agency shape
  with every object that moved whether the robot acted on it or not — both
  spellings now use a join. Selecting a collection returned association rows
  rather than members — fixed in `_apply_relationship_join`, covered by
  `test_selecting_a_collection_yields_its_members`.
- **All 8 review threads replied to; 6 resolved.**
- Manifest, roadmap, dashboard and the PR description are current.

## Outstanding

1. **CI has not run on the rebuild yet.** The long-term tests are marked xfail
   (non-strict) because a membership condition over a collection still does not
   translate to a join and I could not execute them here. If any unexpectedly
   passes, flip it to strict.
2. **Two threads deliberately left open**, both needing the developer's call:
   whether a body in the gripper counts as an object the robot sees (it does not
   any more, because `AbstractRobot.bodies` includes it), and whether an episode
   should record which links were the robot's.
3. **The krrood fix widened this PR** into another package. It is the finding
   this branch was chartered to produce, but splitting it out is reasonable if
   the developer prefers.

## Notes for whoever picks this up

- A clean venv on Python 3.12 runs the working-memory tests against a real twin;
  what still needs CI is ORM generation (`rclpy`) and anything importing
  `experiments.episodes.episode` (ROS message packages).
- `test/experiments_test/conftest.py` regenerates every ORM interface, so a test
  in that package cannot run locally even when it needs no generated interface.
  Copy it out to a scratch directory with a minimal conftest providing the
  SymbolGraph cleanup fixture.
- The symbol graph holds instances **weakly**; a test must hold its own events.

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
