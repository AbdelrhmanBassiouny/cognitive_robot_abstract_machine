# `question-set-and-ground-truth` (icra-evidence) — PR #295

Branch `claude/plan-item-kickoff-icra-evidence-zyzfnj`, cut off #278
(`episodes-queried-by-eql`) so `LongTermMemory.answer(query)` is reused rather
than a second copy of it written. Kicked off in `auto` mode; the settled plan
and its reasoning are in `icra-evidence/roadmap.md`'s
"`question-set-and-ground-truth` (#295), as planned 2026-09-08" section.

## Plan

New package `experiments/src/experiments/questions/`:

- `question.py` — `Bucket`, `BloomLevel`, `Memory`, `RequiredFact`,
  `GroundTruthSource`, and `Question[SourceType, AnswerType]`
  (`SubClassSafeGeneric`) carrying `english`, `bucket`, `required_facts`, with
  `query`/`ask`/`ground_truth`.
- `working_memory.py` — `WorkingMemory` (world, robot, segmind events),
  `WorkingMemoryQuestion` (Understanding), and the scene, support/spatial,
  temporal-and-agency, embodiment and self-model spellings.
- `long_term_memory.py` — `LongTermMemoryQuestion` (Remembering) over #278's
  `LongTermMemory`, and the scene, temporal-and-agency and embodiment
  spellings plus the recoverable half of support.
- `question_set.py` — `QuestionSet`, built by a classmethod, with
  `for_bucket`/`for_memory`/`for_bloom_level`.
- `experiments/scripts/generate_orm.py` — the questions modules join the
  ignore list; a question is asked, not recorded.
- `test/experiments_test/test_questions.py` — tests first.

## Done

- Context gathered, scope-overlap check run (no in-flight branch touches
  `experiments/src/experiments/questions/` or `test_questions.py`).
- Branch cut, pushed; draft PR #295 opened.
- `plan.yaml` carries branch/session/PR/`in_progress`; roadmap section written.

## Next

1. `test_questions.py` — failing tests for the working-memory half.
2. `question.py` + `working_memory.py` until they pass (statically; see below).
3. Same for the long-term-memory half.
4. `generate_orm.py` ignore list; `scripts/format_docstrings.py`.
5. Fill in PR #295's description; keep it a draft.

## Known hazards

- **Nothing runs in this session container.** Installing the workspace fails
  (`random_events`, `antlr4-python3-runtime`, `arff`, `dnutils` all fail to
  build), so verification is static plus CI, as every item of this track has
  recorded.
- **EQL across a to-many association table is unproven**, and this item is the
  first to need it (#278's roadmap note said so). Every long-term spelling
  reaches `RecordedTrial.ticks` then `Tick.events`. CI answers it; if it
  fails, the shape changes in `LongTermMemoryQuestion.query` alone.
- **Three of the twelve spellings cannot be written yet** — control (both) and
  self-model over long-term memory. The first two are the item's own recorded
  blocker; the third is too, and #271 has not yet grown the episode→world
  reference the fold recorded. Support/spatial over long-term memory needs
  routed predicates (`icra-mechanism`) — the one gap the plan had not already
  recorded.
