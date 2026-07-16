# PR plan: rdr/why-answer — why-question core (Why track, W1)

Not started. Base: `D-core-engine` (rebase onto main once the split stack merges).
Design source: plan session 2026-07-16 (roadmap "Why & Montessori track").

## Goal

A formal way to ask *why was conclusion X concluded* and get the fired rule and
its conditions as live, verbalizable EQL expressions.

## Design

- New `rdr/why.py`: frozen dataclasses `WhyQuestion` (case; `contrast` field
  reserved, NOT implemented in v1) and `WhyAnswer` (conclusion value, fired-rule
  condition expression, `Add` node, rule kind/depth, satisfied conditions with
  bindings, corner case).
- Content selection ONLY: build `WhyAnswer` from the existing
  `ClassificationTrace`/`FiredConclusion` (`rdr/observer.py`) — no new capture
  machinery. `rule_tree_view.walk_rules` + `resolve_status` give the full
  fired/skipped path; `CornerCaseStore.get(anchor_id)` gives creation provenance.
- `EQLSingleClassRDR.why(case) -> WhyAnswer`.
- `RDRBackend.infer` explain-aware path retaining per-result traces (strategy or
  decorator around the fast path — OCP, do not rewrite `infer`).
- Unify retrieval with the EQL side: an `Explanation` abstraction so
  `explain_inference`-style lookup also serves RDR attribute conclusions
  (`RDRConclusionExplanation` sibling of `InferenceExplanation`) — LSP; shares
  value objects with the future `rdr/justifications` (JTMS) work.

## Literature anchors (cite in the developer doc, W3 lands the bib)

Why-provenance witnesses (Green/Karvounarakis/Tannen 2007; Buneman 2001), JTMS
justifications (Doyle 1979), RDR rule-trace explanation (Compton & Jansen 1990),
contrastive explanation (Miller 2019).

## TDD anchors (zoo dataset, krrood self-contained)

1. `why(case)` returns exactly the fired rule's anchor + conditions (assert
   against `_trace(case)`).
2. Corner case attached to the answer.
3. Backend explain path yields a trace per result; fast path unchanged.
4. Contrast field present but raising `NotImplementedError` with a pointer.
