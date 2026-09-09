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

## Next

Wait for CI. If it's green on the working-memory half, this item's committed scope is
done pending the open question above. If the developer answers that question, add the
long-term counterpart test (fixing `values_agree`'s list case first if it needs fixing) —
straightforward once decided, since the harness itself needs no long-term-specific code.
