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
  a member of one collection can own the next. The seven `NEEDS_A_COLLECTION_JOIN`
  xfails are gone.
- **The half of that fix CI found missing** (`63b1a99e8`, third round). CI is where
  the long-term questions actually run, and it failed three of them: the join
  translated but the rows came back multiplied. Selecting an attribute reached
  through a collection -- `entity(event.tracked_object)`, the shape of most
  long-term questions -- left the table it selects from with nothing joining it, and
  a condition relating two members was dropped as a table-level join between two
  aliases of one class.
- **A member is read as the class the query asks for** (`d6c1104f8`, fourth round,
  again found by CI). `Tick.events` holds events; the agency question asks two of
  them for their `tracked_object`, which only some events have. The member was
  aliased as the class the collection declares, so the column really was not there.
  `MissingColumnError` hid it by failing while being built -- it read its columns off
  `inspect(dao_class).columns`, which an alias has none of. **krrood's ORM suite:
  142 passed, from 135 passed + 1 xfailed.**
- **The review's other two asks** (`0576c840b`): `CONDITION_COMBINERS` is
  `(LogicalOperator, Filter)` rather than four names, and coraplex's actions carry
  `ManipulatesBodies` -- the mixin the first round asked for, in the package it was
  meant for, inheriting `Symbol` so the actions are queryable.
- **`AgentInteractionEvent` replaces the `ManipulatesBodies` mixin** in segmind
  (second round, review thread). Every implementation returned
  `[self.tracked_object]`, so the mixin restated `EventWithTrackedObjects`. It also
  made the long-term agency question translatable: `tracked_object` is a mapped
  relationship where `manipulated_bodies` was a Python property.
- **A designator reports its constructor's parameters** (`40ee37485`, fifth round,
  found by CI). Giving nine coraplex actions a `Symbol`-inheriting mixin enrolled
  them in the class diagram the root `conftest.py` builds over every `Symbol`
  subclass in an autouse fixture, and `Designator.fields` looked every dataclass
  field up in `get_type_hints(cls.__init__)`. `_inference_explanation_` is
  `init=False`, so it has no hint there: **437 errors in coraplex, 282 in
  experiments**, every test in both, at setup.
- **The robot is recorded already** (`8a4c57777`). The robot is a semantic
  annotation and `World.semantic_annotations` is mapped, so `Episode.world` carries
  it; the previous round's claim that recording the world does not answer this was
  wrong. Now a round-trip test rather than a claim.
- Manifest, roadmap, dashboard and PR description all current. Eleven review threads
  replied to; seven resolved.

## Outstanding

1. **CI is running on the fifth round.** Round four never reported on the long-term
   questions at all: the class-diagram fixture died at setup, so all 282 experiments
   tests errored before any of them ran. So the fourth round's krrood fix -- reading
   a collection's members as the class the query asks for -- is still unconfirmed,
   and this round is the first that can confirm it. Neither
   `test_long_term_questions.py` nor coraplex's suite can run in a session container.
2. **One thread left open**, needing the developer, and it is no longer about the
   recording: the robot's own degree-of-freedom count. No run sets `Episode.world`
   (the runner releases a trial's world before the trial is recorded), and the count
   itself is not one query because `SemanticAnnotation.bodies` is a computed property
   with no mapped path from an annotation to its entities.
3. **Three buckets still have no long-term spelling** and control has none in
   either memory. Support-and-spatial waits on `query-routed-per-predicate`,
   embodiment on a run that keeps its world, control on
   `control-constraints-and-degrees-of-freedom-queried`.
4. **This PR now changes krrood, segmind and experiments.** That breadth is the
   finding the branch was chartered to produce, but splitting the krrood half out
   is reasonable if the developer prefers.

## Notes for whoever picks this up
- **Inheriting `Symbol` is never a local change.** It puts the class into a
  process-wide class diagram that the root `conftest.py` builds in an autouse
  fixture, and into a process-wide instance graph, so the change is measured against
  every package that imports the class rather than the one being edited.
- **Assert the rows a query returns, not the set of them.** Every membership test
  the second round added sorted distinct names, so the duplicated rows CI caught
  could not fail any of them -- and none selected an attribute *off* a member.


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
