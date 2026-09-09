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

## Plan

1. `RecordedQuery` (`experiments/episodes/episode.py`) grows three optional fields:
   `bucket`, `bloom_level`, `answered_correctly` — `None` for an ordinary query, set for
   one answering a frozen question.
2. `QuestionSet.answer_and_record(source)` — asks every question, times it, compares its
   answer against `ground_truth` (as sets, after `Question.distinct`), returns scored
   `RecordedQuery` rows.
3. Two new `PaperFigure`s in a new `paper/questions.py`: `AccuracyByBucket`,
   `AccuracyByBloomLevel`, registered in `FigureSet.for_the_paper`.
4. Working-memory half: scored against the scene `test_questions.py` (#295) already
   builds. Long-term half: scored against one recorded episode via
   `open_recording`/`ResultsDatabase`, CI-only per the standing ROS/generated-ORM
   limitation.
5. TDD throughout — failing test before `answer_and_record` exists, failing test before
   each new figure exists.

## Done so far

- Branch cut from #265, draft PR #304 opened.
- Manifest (`plan.yaml`) and roadmap updated by hand (the folded-title
  `plan_item_bootstrap.py` bug #297 already documented reproduced here too — `open`
  failed on `save-plan.sh`'s YAML validation).
- Two stale blockers cleared (`episodes-queried-by-eql` merged into #265;
  `episode-corpus-generated-at-scale` isn't needed at this item's scale), one blocker
  (`integrated-simulation-pipeline`) satisfied by the base itself.

## Next

Implementation has not started yet — this is the kickoff/bootstrap turn. Next turn:
write the failing tests for `RecordedQuery`'s new fields and `answer_and_record`, then
make them pass; then the two new figures, same TDD order.
