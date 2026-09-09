# PR #304: Score the frozen question set against working memory and long-term memory

Plan item `question-set-answered-from-memory` (`icra-evidence`, tracking issue #252,
track `experiment-a`). Kicked off in `auto` mode. Full reasoning is in
`.claude/personal/plans/icra-evidence/roadmap.md`'s `question-set-answered-from-memory`
(#304), as planned 2026-09-09" section.

## Base

Cut off #265 (`claude/icra-experiments-simulation-pipeline-w4ep7n`), not `tracy_icra`.
`tracy_icra` doesn't yet contain #265 (verified by ancestry check), so it lacks
`question-set-and-ground-truth`'s (#295) frozen `Question`/`QuestionSet`/`LongTermMemory`
machinery this item needs. Confirmed with the developer before cutting. Will need
rebasing onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands that merge.

## Plan (revised after building the working-memory half)

1. `RecordedQuery` (`experiments/episodes/episode.py`) grows three optional fields:
   `bucket`, `bloom_level`, `answered_correctly` — `None` for an ordinary query, set for
   one answering a frozen question. Done.
2. `QuestionSet.answer_and_record(source)` — asks every question, times it, scores it
   against `ground_truth`. **Corrected from the original plan**: scoring uses
   `Question.values_agree`/`matches_ground_truth`, promoted out of `test_questions.py`'s
   own `answers_agree` free function (numeric for a spatial answer, position-by-position
   for a list, `==` otherwise) rather than the "compare as sets after `Question.distinct`"
   idea recorded in the roadmap's first pass — that idea was never actually how #295's own
   tests establish correctness, so it would have been an invented rule rather than the
   established one. Done for working memory.
3. Two new `PaperFigure`s in `paper/questions.py`: `AccuracyByBucket`,
   `AccuracyByBloomLevel`, registered in `FigureSet.for_the_paper`, plus the new module
   added to `generate_orm.py`'s ignore list. Done.
4. Working-memory half tested (`test_question_scoring.py`), against the scene
   `test_questions.py` (#295) already builds. Long-term half **deliberately not tested
   yet** — see the open question below.
5. TDD followed throughout, though nothing could be executed locally (see below).

## Open question found while building, left to the developer

`test_long_term_questions.py` compares a list-valued long-term answer by **sorted name**
(`names(answered) == names(true)`), not position-by-position — every long-term question
returning a list uses this, consistently. The working-memory test never sorts. Two
readings: either the database's row order genuinely doesn't match ground truth's (then
`values_agree`'s zip comparison would wrongly mark a right-but-differently-ordered
long-term answer as incorrect), or the sort was only ever a convenience. I don't know
which, and guessing risks exactly the class of scoring bug #295 already paid three CI
rounds to find. Recorded in the roadmap's `question-set-answered-from-memory` (#304), as
built 2026-09-09" section and in the PR description. Consequence: no long-term test of
`answer_and_record` on this branch, even though the method itself already works
unchanged for the long-term half.

## Done so far

- Branch cut from #265, draft PR #304 opened (and kept draft after this push).
- Manifest (`plan.yaml`) and roadmap updated by hand both times (the folded-title
  `plan_item_bootstrap.py` bug #297 already documented reproduces here too).
- Two stale blockers cleared, one satisfied by the base itself (see roadmap).
- `RecordedQuery`'s three new fields, `QuestionSet.answer_and_record`,
  `Question.values_agree`/`matches_ground_truth`, `AccuracyByBucket`,
  `AccuracyByBloomLevel`, `FigureSet` registration, `generate_orm.py` ignore-list entry,
  `test_question_scoring.py` (working-memory scoring + both figures), and the
  `test_questions.py` refactor to call the promoted method instead of its own copy — all
  committed and pushed (`ef9492cbf`).
- **Not run locally**: `uv sync` fails outright in this container on a `pyproject.toml`
  parse error unrelated to this branch (`docopt-ng`'s dependency entry, a table `uv`
  0.8.17 rejects). Neither half could be installed, so CI is what verifies this branch.

## Round 2: reviews + failing CI (2026-09-09)

The developer reviewed and left two threads, and CI on the first push failed broadly
(dozens of tests, not obviously mine).

**CI root-caused to #265 itself, fixed there, not papered over here.** The dominant
failure (`AttributeError: 'GiskardExecutable' object has no attribute 'is_paused'`) hit
every test that actually executes a simulated motion, across `coraplex_test` and
`experiments_test` — nothing I touched. Traced it: `is_paused`/`is_interrupted` existed
on `tracy_icra`'s own `GiskardExecutable` (delegating to each motion mapping's
`PlanNode.is_paused`/`is_interrupted`) but were silently dropped when tracy_icra merged
into #265 — `main` never had them at all, so this wasn't a main-merge casualty either.
Restored both properties + a unit test (`test_is_paused_reflects_a_paused_motion_mapping`,
`test_is_interrupted_reflects_an_interrupted_motion_mapping`) directly on
`claude/icra-experiments-simulation-pipeline-w4ep7n` (`b4397c229`), pushed, then merged
that commit into this branch (`7eecb81a3`) so #304's own CI picks it up too.

**A second, separate CI failure left unfixed and flagged, not guessed at:**
`test_orm_generation.py::test_generation_needs_no_ros_message_package` fails because
`giskardpy.orm.ormatic_interface` (a *generated* file — AGENTS.md forbids touching these
directly) now pulls in `giskardpy.middleware.ros2.control_loop` →
`feedback_publisher.py` → `json_msgs.action`, which is exactly the ROS message import
this test exists to prove generation doesn't need. Pre-existing on #265, unrelated to
either my item or the `is_paused` fix (same traceback before and after). Not attempted —
AGENTS.md says consult the developer rather than dig into generated ORM internals.

**Reviews**: replied to both threads.
- `question_set.py`'s "can't RecordQuery be a Role for a Question" — couldn't find the
  sibling question class in `experiments/scenarios` the developer meant; asked which one.
  Also raised a concrete blocker either way: `RecordedQuery` must survive a database
  round-trip after the `Question` that produced it is gone, and `Question` is explicitly
  excluded from ORM mapping (`generate_orm.py`'s own ignore list) for exactly that reason
  — a `Role[Question]` holds a live reference to its role taker, so it can't be what
  persists. Left open, no code change.
- `test_question_scoring.py`'s "why is the query a string?? / the second field 'cube'?" —
  fair; those were arbitrary inline literals. Fixed by reusing `test_paper_figures.py`'s
  already-named `WHAT_IS_ON_THE_TABLE`/`TWIN_BACKEND` constants everywhere this test built
  an "ordinary query" placeholder (three spots). Pushed (`b156d3af1`), thread resolved.

## Round 3: the Role thread resolved for real, and a schema change (2026-09-09)

The developer replied to both round-2 threads with the actual answer, and both landed on
the same design change.

**The sibling class was `Question` itself.** He pointed at `question.py` line 136 in
#265's diff — inside `Question`'s own field block — and clarified: not `Role[Question]`
(an instance), but "a reference field to the question class that is meant here, not the
instance." Same ask came independently on `test_paper_figures.py`'s `query()` helper:
"take the actual Question object... or the Question SubClass? I guess a class object is
serializable or recordable, right?"

**Both answered by one change.** `RecordedQuery.bucket`/`bloom_level` (two separate
persisted fields) are replaced by `question_type: Optional[Type[Question]]` — the class
object itself. `bucket`/`bloom_level` are now read-only properties reading
`question_type.bucket`/`.bloom_level` (both `ClassVar`s on `Question`), so they can never
disagree with the class that defines them. Storing a class reference is not new
machinery: ORMatic's `TypeType` decorator (`krrood/ormatic/custom_types.py`) already
stores a `Type[X]` field as `module.ClassName` and resolves it back, wired into
`type_mappings` for bare `type`/`Type` regardless of `X`, and already exercised
end-to-end by `KRROODPositionTypeWrapper.position_type: Type[KRROODPosition]` in
krrood's own `test_ormatic/test_interface.py` — so this needed no new ORM support,
just using what was already there.

`question_set.py`'s `answer_and_record` now passes `question_type=type(question)`
instead of `bucket=question.bucket, bloom_level=question.bloom_level`.
`test_paper_figures.py`'s `query()` helper takes `question_type: Type[Question] | None`
instead of separate `bucket=`/`bloom_level=` kwargs; `text` stays a separate parameter
since `english` is an abstract *instance* property (some questions need instance state,
like `AnythingMovedInTheEpisode.episode_identifier`, to render it), so there's no
class-level text to read without constructing one. `test_question_scoring.py`'s scored
corpus now references real classes (`ObjectsSeen`, `ObjectColours`,
`AnythingMovedInTheEpisode`) instead of independently-chosen bucket/level combinations
that could drift from them — exactly what the reviewer was pointing at.

`figure.py`'s `scored_queries_of` and `paper/questions.py`'s two figures needed no
changes at all: they read `query.bucket`/`query.bloom_level`, which now resolve through
the properties transparently.

Pushed (`6f2a370f2`); PR description updated to describe `question_type` in place of the
old two-field description; both threads replied to and resolved. Formatted with
`scripts/format_docstrings.py` (had to build a throwaway venv for black/docformatter/tqdm
since this container still can't `uv sync`); byte-compiled all four touched files to
catch syntax errors since nothing can be run here. Not run against real tests — same
container limitation as every round on this branch.

## Next

CI just re-triggered on #304 (`6f2a370f2`) — pending as of this update, not polled
further per standing instructions. The two remaining open items are unchanged: the
long-term list-comparison question (`values_agree`'s sorted-vs-positional disagreement),
and the `json_msgs`/generated-ORM-interface CI failure, both left to the developer.
