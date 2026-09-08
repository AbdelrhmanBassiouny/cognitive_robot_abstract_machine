# `question-set-and-ground-truth` (icra-evidence) — PR #295

Branch `claude/plan-item-kickoff-icra-evidence-zyzfnj`, cut off #278
(`episodes-queried-by-eql`). Kicked off in `auto` mode, resolved a second time on
2026-09-08 via `/plan-item-resolve`; the rounds are written up in
`icra-evidence/roadmap.md` ("as planned", "as built", "reviewed", "resolved").

## Done

- **The question set** — `experiments/questions/` with `question.py`,
  `working_memory.py`, `long_term_memory.py`, `question_set.py`. Thirteen
  working-memory questions across five buckets, six long-term across three.
  **20 working-memory tests, run locally against a real twin, all passing**, in
  fixed and random order.
- **Nothing is handed to a question** (first review round). Every variable is
  domainless and ranges over the symbol graph, what a question is about is a
  condition, and the source is the robot. `DetectionEvent` inherits `Symbol`; the
  set is read off the question subclasses.
- **`a96531635` on #271's own branch** — `Episode.world` and
  `RecordedTrial.motion_statechart`, the fold `icra-foundation`'s roadmap recorded
  but never made. Merged into this branch, so it lands wherever #271 lands.
- **The collection-membership defect is fixed in krrood** (`ecc05af5`, second
  round, at the developer's request on the thread — it overrode the earlier call
  that this belonged to an EQL plan). `EQLTranslator` binds every variable to the
  FROM element it ranges over: the owner gets an alias of its own so it is told
  apart from members sharing its mapped base, joining a relationship is separate
  from caching a path so two variables over one collection reach two members, and
  a member of one collection can own the next. **krrood's ORM suite: 138 passed,
  from 135 passed + 1 xfailed.** The seven `NEEDS_A_COLLECTION_JOIN` xfails are
  gone.
- **`AgentInteractionEvent` replaces the `ManipulatesBodies` mixin** in segmind
  (second round, review thread). Every implementation returned
  `[self.tracked_object]`, so the mixin restated `EventWithTrackedObjects`. It also
  made the long-term agency question translatable: `tracked_object` is a mapped
  relationship where `manipulated_bodies` was a Python property.
- Manifest, roadmap, dashboard and PR description all current. Ten review threads
  replied to; seven resolved.

## Outstanding

1. **CI has not run on this round.** All four checks were still `queued` at the
   time of the push. `test_long_term_questions.py` is now expected to *pass* rather
   than xfail, and it cannot be run in a session container, so CI is what confirms
   the long-term questions answer end to end.
2. **Three threads deliberately left open**, each needing the developer:
   - whether a body in the gripper counts as an object the robot sees (it does not
     any more, because `AbstractRobot.bodies` includes it);
   - whether an episode should record which links were the robot's;
   - whether coraplex's actions should gain the mixin removed from segmind here —
     I asked rather than doing it, since it is another package's design.
3. **Three buckets still have no long-term spelling** and control has none in
   either memory. Support-and-spatial waits on `query-routed-per-predicate`,
   embodiment on an episode recording the robot's own links, control on
   `control-constraints-and-degrees-of-freedom-queried`.
4. **This PR now changes krrood, segmind and experiments.** That breadth is the
   finding the branch was chartered to produce, but splitting the krrood half out
   is reasonable if the developer prefers.

## Notes for whoever picks this up

- A clean venv on **Python 3.12** (not 3.11 — `make_dataclass(module=...)` needs
  3.12) with `pip install -e ./krrood pytest objgraph` runs krrood's ORM suite:
  `pytest test/krrood_test/test_ormatic --confcutdir=test/krrood_test`. The
  `--confcutdir` is what skips the root `conftest.py`'s ROS imports.
- `test/krrood_test/dataset/ormatic_interface.py` is regenerated from the dataset
  classes at conftest import, so adding a mimic class needs no manual regeneration.
- Running the verbalization tests rewrites
  `test/krrood_test/test_eql/test_verbalization/verbalization_results.py`; revert it
  before committing unless the wording genuinely changed.
- What still needs CI is ORM generation (`rclpy`) and anything importing
  `experiments.episodes.episode` (ROS message packages).
- `test/experiments_test/conftest.py` regenerates every ORM interface, so a test in
  that package cannot run locally even when it needs no generated interface.
- The symbol graph holds instances **weakly**; a test must hold its own events.
