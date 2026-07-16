# PR plan: eql/causal-verbalization — "because" grammar (Why track, W2)

Not started. Base: `rdr/why-answer` (W1).

## Goal

Verbalize causal explanations: "<conclusion> because <conditions> (rule R)".

## Design (exploration-confirmed seams)

- Vocabulary: causal connectives (`BECAUSE`, ...) added to
  `verbalization/vocabulary/english.py` — none exist today.
- New grammar family `verbalization/grammar/causal/` (planner + assembler +
  rules.py; auto-registered by the RULES walker). Model on
  `grammar/inference/InferenceAssembler`'s two-block `BlockFragment` (IF…THEN):
  conclusion clause + "because"-headed coordinated verbalized conditions +
  rule-identity clause; optional "although" clauses for non-fired refinements.
- Routing: branch in `EQLVerbalizer.build` / `pipeline.verbalize` beside the
  existing `Match` special case (Match is the precedent for non-foldable roots).
- Bindings: thread concrete instances via the existing `binding_overrides`
  (`RuleContext.scope`) so answers read "the star block", not "a MontessoriShape".
- `WhyAnswer.verbalize()` entry point.
- Unsupported nodes keep raising `UnverbalizableExpressionError` (fail loudly).
- Optional: a `DiscourseScopeRule` subclass so the conclusion's referent
  pronominalizes into the because-clause ("… because ITS container …").

## Conflict watch

`tomsch420/montessori_ijcai` also modifies `vocabulary/english.py`,
`fragments/base.py`, `parts_of_speech.py` — check overlap early, keep the diff
minimal in those files, coordinate via the montessori sessions.

## TDD anchors

Golden-text tests on zoo why-answers ("… because the animal produces milk");
`AmbiguousRuleError`-free registration; fail-loudly test for an unverbalizable
node inside an explanation.
