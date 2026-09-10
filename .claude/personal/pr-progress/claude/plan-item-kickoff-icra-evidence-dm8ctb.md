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

## Round 4: the developer pushed further, and found a real bug in round 3 (2026-09-09)

Two new comments on `episode.py`'s `question_type` field, minutes after round 3's reply:
"why is it optional? This should replace the text field as well, and be a required
field", then "Actually, I think this must be a Role[Question], and find a clean way to
solve the ormatic issue... AlternativeMapping... as a last resort".

**Investigated `Role`/`AlternativeMapping`, and found a cleaner mechanism already in
place that neither needs.** `krrood.ormatic.ormatic.py` already sets
`type_mappings[SubclassJSONSerializer] = JSON`, and `TypeDict.__getitem__` resolves that
by nearest inheritance distance — so any class that inherits
`krrood.adapters.json_serializer.SubclassJSONSerializer` gets mapped to a JSON column
automatically, with no new `AlternativeMapping` subclass or column type needed. `Question`
now inherits it, delegating `to_json`/`_from_json` to the already-existing generic
`DataclassJSONSerializer` (which introspects a dataclass's own fields, skipping
`ClassVar`s) — a two-method addition, not new infrastructure.

**This also fixed a real bug round 3 introduced.** Re-reading `long_term_memory.py` while
investigating found `episode_identifier: str` is a genuine per-instance field on every
`LongTermMemoryQuestion` (which run the question is about) — round 3's `Type[Question]`
reference would have silently discarded it, so a recorded long-term answer couldn't say
which episode it was actually asked of. `RecordedQuery.question_type: Optional[Type[Question]]`
is now `question: Optional[Question]` — the instance, not the class — which is what makes
this correct rather than merely simpler.

**Left one part of the ask unresolved, flagged rather than guessed at.** Making `question`
required and dropping `text` (as literally asked) conflicts with `QueryDeterminism`
(`paper/queries.py`, already merged in #297): it groups *any* recorded query by `text`,
including plain ad hoc EQL queries with no `Question` at all, and its own tests
(`test_paper_figures.py`) exercise exactly that. Making `question` required would mean
either giving `Bucket`/`BloomLevel` a "not part of the frozen set" member — touching a
taxonomy #295 already froze and reviewed four rounds on — or breaking that shipped
feature. Kept `question` optional and `text` in place; replied on the thread with the
concrete conflict and asked which he wants, rather than picking silently.

Verified the JSON round trip against a standalone mimic reproducing `Question`'s exact
shape (`SubclassJSONSerializer` + dataclass + `ClassVar`s), since this container still
can't import the full `experiments` package (`casadi` and friends). Added two real tests
in `test_questions.py` against `ObjectsSeen`/`AnythingMovedInTheEpisode` for CI to verify
end to end. Pushed `1129fd72a`; PR description updated; both new comments replied to,
thread left **unresolved** since the answer differs from what was asked, per the
review-comment rule.

## Round 5: `question` made required via `Role[Question]` (2026-09-10)

Resolved via `/plan-item-resolve icra-evidence question-set-answered-from-memory` in a
fresh session on a fresh 6184xo placeholder branch — switched to the item's real branch
(`claude/plan-item-kickoff-icra-evidence-dm8ctb`) before doing anything, since the
placeholder was just fresh off `integration` and unrelated to this PR.

The developer answered the round-4 thread this morning (07:01, before this session):
"I still want it the question required and it becomes the role_taker and
RecordedQuestion is a Role[Question]." Implemented, with one deliberate deviation.

**`RecordedQuery` split rather than mutated.** Base `RecordedQuery` keeps only what an
ordinary query needs (`text`, `answer`, `latency`, `moment`, `answered_predicates`). New
`ScoredQuery(RecordedQuery, Role[Question])` carries `question` as the required
`role_taker` plus `answered_correctly`; `bucket`/`bloom_level` are explicit read-only
properties reading through it (kept explicit for type hints/docstrings rather than left
to `Role.__getattr__`'s implicit delegation). `answer_and_record` and
`scored_queries_of` (was `query.bucket is not None`, now `isinstance(query, ScoredQuery)`)
updated. Same multi-inheritance shape `DetectedMontessoriShape(MontessoriDetection,
Role[MontessoriShape])` already uses in this codebase (ORM-mapped today), not a new
pattern.

**Verified before implementing, for real this time.** Nothing in krrood's own suite
exercises `Role` through ORMatic, so built a standalone mimic of the exact shape
(plain-dataclass base with a default field + `Role[T]`-based subclass with a required,
`SubclassJSONSerializer`-typed `role_taker`), ran it through `ORMatic.from_package` and a
real SQLite session (`krrood.ormatic.utils.create_engine`, not bare `sqlalchemy`, for the
JSON (de)serializer wiring) — confirmed `role_taker` generates `nullable=False`
correctly, no `AlternativeMapping` needed, and a mixed plain/scored row list round-trips
via SQLAlchemy's joined-table polymorphism with the right concrete type. Then, unlike
every prior round: got the *actual* `experiments` package importable here.
`uv sync` still fails on the same `docopt-ng`/`pyproject.toml` bug, but
`pip install -e <pkg>` for every workspace package under a fresh Python 3.12 venv (this
container's default `python3` is 3.11, which the project's `pyproject.toml` rejects)
installs cleanly and lets `experiments.episodes.episode` import and `ScoredQuery`
construct/attribute-check for real. Could not get past regenerating the ORM interfaces
though — giskardpy's `generate_orm.py` still hits `DebugExpressionPublisher`/`rclpy`, so
the new DB round-trip test (`test_episodes.py::
test_a_scored_query_keeps_the_question_it_answered_apart_from_an_ordinary_one`) is
CI-only, same as everything else on this branch.

**Left `text` on `RecordedQuery`/`ScoredQuery`, not dropped.** Round 4's first comment
also asked to drop `text`; today's comment doesn't repeat that part. Kept it since
`QueryDeterminism` still groups any recorded query (Question or not) by literal `text` —
same conflict as round 4, unchanged. Replied on the thread explaining this, **left
unresolved** since only half the ask is done, per the review-comment rule.

**Two more CI failures found, both confirmed pre-existing/unrelated, not fixed:**
`test_panda_ground_cubes_demo.py::test_park_arms_is_actually_reached`
(`DofNotInWorldStateError`, MuJoCo world-building code this branch never touches — file
has no history on `main`, only exists inside #265's own merge) and three
`experiments_test` collection errors sharing one `ImportError: cannot import name
'AttachNode' from 'coraplex.plans.attachment_nodes'` root cause, also outside this
branch's diff.

**One real CI bug found and fixed on this branch:** `test_question_scoring.py` imported
the `scene`/`robot` fixtures from `test_questions.py` but not `two_arm_robot_world`,
which `scene` itself needs — pytest resolves a fixture's own dependencies against the
*requesting* module, not where the fixture was defined, so importing `scene` alone left
it unresolvable there even though `test_questions.py`'s own tests (which import
`two_arm_robot_world` directly) passed in the same CI run. Fixed by importing it directly
in `test_question_scoring.py` too, matching `test_questions.py`/`test_episodes.py`'s own
convention.

Pushed (`773096210`); PR description updated with a "Round 2" section; formatted with
`scripts/format_docstrings.py` and `black --check` (via the pip-installed venv, not a
throwaway one this time). `RecordedTrial.queries`-round-trip test added
(`test_episodes.py`), all other touched tests updated to the new `ScoredQuery`/isinstance
shape — not run against the real DB here (still needs CI, per the `rclpy` limitation
above), but constructed and attribute-checked against the real classes directly, further
than any prior round on this branch managed locally.

## Next

Still open, all three left to the developer as before: whether `text` should also go
from `ScoredQuery` (replied on the thread, not resolved), the long-term
`values_agree` sorted-vs-positional list-comparison question, and the pre-existing
`AttachNode`/`DofNotInWorldStateError` CI failures on the base (#265). CI not polled
further this session per standing instructions against scheduled/timed checks.
