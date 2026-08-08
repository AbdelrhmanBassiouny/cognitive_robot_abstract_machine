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

## Decision and outcome (2026-08-08)

Developer chose: **strategy family in `rdr/`**, implemented **now, onto #41**.

Landed as `19e387a9` on `rdr-backward-inference`:

- New `rdr/branch_semantics.py` — `SelectorBranchSemantics` + one class per
  selector holding both `sibling_guards` and `branches`; dispatch via
  `krrood/patterns/specificity_ranking.py`, as `PhraseRule`/`SpecificityRule` do.
- New `rdr/exceptions.py` — `AmbiguousBranchSemanticsError`.
- `_leaf_guards` / `_collect_rule_paths` reduced to recursion + lookup;
  `Not(ConclusionSelector)` stays put (core operator, not selector dispatch).
- `test_backward_inference.py` dashed dividers → `# %%` per AGENTS.md.

The `Alternative` positive-guard hypothesis was **probed and not confirmed**:
0/0/0/1 positive calls across four DSL shapes, the 1 being a hand-built
`Refinement(Alternative(A,B), C)`. Unreachable because `refinement()` anchors on a
`with`-entered condition while `alternative()`/`next_rule()` anchor on the
conditions root. No semantics changed; constraint documented on
`AlternativeBranchSemantics`.

Verification: `test_eql_rdr` 33 → 45 (existing 33 untouched); the 3 open/closed
tests mutation-checked; sweep 109 failed/921 passed → 109 failed/933 passed with
264 failed+errored ids byte-for-byte identical.

`plan.yaml` + `roadmap.md` §15 updated and saved (`c50504f9`).

## Next

- #41 is back in **draft**; developer marks it ready when happy.
- **CI on `19e387a9` is unwatched** — both `subscribe_pr_activity` tools returned
  "Could not subscribe to this PR". Needs a manual check.
- This session's branch `claude/rdr-guard-conclusion-arch-8htmfu` is deliberately
  unused: the change folded into #41 per the fold-don't-stack rule.
