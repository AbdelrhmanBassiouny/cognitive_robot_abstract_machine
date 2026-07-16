# PR plan: rdr/why-query-surface — why(...) EQL factory + docs (Why track, W3)

Not started. Base: `eql/causal-verbalization` (W2).

## Goal

The formal ask surface: a `why(...)` factory in
`krrood.entity_query_language.factories` returning a query construct over
`WhyAnswer`s that composes inside EQL and verbalizes via W2's grammar.

## Scope

- The factory + its expression node (dispatchable through the rule registry).
- Docs: `doc/eql/user/why_questions.md` + developer doc; BibTeX entries into
  `krrood/doc/references.bib` (provenance semirings/witnesses, JTMS, RDR
  rule-trace explanation, Miller contrastive explanations).
- Contrast argument: reserved, documented as follow-up (uses
  `SufficientConditionSet.evaluate_against` for "first failing guard for Q").
- `%why` interactive magic: explicitly DEFERRED until D-ui PR C (interactive
  interface) lands; note in the doc, do not implement here.

## TDD anchors

`why(...)` composes inside an `entity(...)` query; verbalized output matches W2
golden text; docs build warning-clean.
