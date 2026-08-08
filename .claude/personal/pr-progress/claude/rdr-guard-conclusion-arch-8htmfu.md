# `claude/rdr-guard-conclusion-arch-8htmfu` — GuardCondition / conclusion-selector architecture

## What this session is

`/plan-item-resolve rdr-refactor rdr-backward-inference` plus a design question:
should `GuardCondition` move into `rules/conclusion_selector.py`, should the
selectors move into `rdr/`, or is the current shape fine?

## Findings (2026-08-08)

- The item is **not stalled**. #41: open, `draft: false`, `mergeable_state:
  clean`, 23/23 review threads resolved, CI 20/20 green on head `b224ec2e`.
  `depends_on: ripple-down-rules-refactor` is `done` (#53). Nothing on #94 about
  this topic; `roadmap.md` §12 settled `negated`-vs-`Not()` only, never placement.
- Answer given: **no** to both moves (layering — `conclusion_selector.py` has
  EQL-core consumers in `factories.py`/`scope.py`/`query_graph.py`;
  `GuardCondition` has only `rdr/` consumers), **yes** to the open/closed
  instinct, landed as a strategy family in `rdr/` modelled on `PhraseRule` /
  `SpecificityRule` + `krrood/patterns/specificity_ranking.py`.
- Scoping test run (`git ls-tree main -- …`): `backward_inference.py` is not on
  `main`. Under the recommendation the change touches only files #41 introduces,
  so it **folds into #41** — this branch must not become a separate PR.

## Next

Awaiting the developer's call on: implement now (re-drafts #41 a third time),
defer until after #41 merges / after #96's non-mutating negation, or leave as-is.
Full plan at `/root/.claude/plans/rdr-refactor-rdr-backward-inference-do-y-resilient-pillow.md`.

Open sub-question to settle first if implementing: whether
`_leaf_guards(Alternative, negated=False)` returning `[A, B]` into a conjunctive
`SufficientConditionSet` is reachable (would read `A AND B` where semantics is
`A OR B`). Hypothesis only — pin with a test before claiming it.
