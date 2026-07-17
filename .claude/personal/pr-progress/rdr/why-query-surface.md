# rdr/why-query-surface (W3) — why(...) EQL factory + docs. Base: eql/causal-verbalization (W2, #82). Draft PR #84.

Session: https://claude.ai/code/session_0148J38dvujaob3AYJqfNzwa

## Plan
Formal ask surface: a `why(...)` factory in `factories` returning a query construct that
composes over the explanation a RESULT already carries (2026-07-17 decision), verbalizable
via the W2 causal grammar. Plus user + developer docs and the bibliography. Contrast
reserved; %why deferred to D-ui #76.

## Design decision (2026-07-17, owner)
Explanations for RDR conclusions live model-side (weak-keyed store) and ride on YIELDED
RESULT HANDLES — never on the shared concluded value. why(...) composes over that surface.
The store + handle attachment + explain(result) routing are owned by the parallel
`rdr/decision-queries` (same base). Chosen: DECOUPLED SEAM NOW + primary input = YIELDED
RESULT HANDLE. So this PR stays decoupled and drops onto their handles unchanged.

## Done (reshaped)
- rdr/why.py: `ExplanationCarrier` Protocol (runtime_checkable seam: a yielded handle
  exposing `conclusion_explanation`), `WhyAnswerSource` = carrier | RDRConclusionExplanation
  | WhyAnswer, `resolve_why_answer(source)` (single subject->answer map), `WhyQuery`
  (source + reserved contrast; lazy, memoized; `.condition`; `.verbalize()`). Dropped the
  earlier WhyExplainer/answer_why re-classify model.
- factories.why(source, *, contrast=None) -> WhyQuery. Lazy import (rdr.why -> explanation ->
  factories cycle); WhyAnswerSource/WhyQuery under TYPE_CHECKING.
- grammar/causal/rules.py: WhyQueryRule (construct=WhyQuery, disjoint, no select tie) -> same
  CausalAssembler (identical verbalization). verbalizer._scan_target routes WhyQuery beside
  WhyAnswer.
- Works today via why(rdr.explain(case)) + carrier mimics; real handles land w/ decision-queries.
- Docs rewritten for the source model (user: runnable Fruit RDR; developer: grounds
  "explanation on the result not the value" in why-provenance witnesses green2007provenance/
  buneman2001why; JTMS doyle1979truth; RDR trace compton1990philosophical; contrastive
  miller2019explanation). BibTeX in references.bib; _toc.yml + both index.md. %why-deferred note.
- test_why_query_surface.py (21 tests) green. Isolated jupyter-book build: both pages execute,
  all 5 citations resolve, zero page warnings. docformatter via scripts/format_docstrings.py.

## Next
- Amend commit + force-with-lease; update PR #84 description to source model; keep draft;
  subscribe; watch CI. Re-run full test_eql_rdr + test_verbalization after reshape.
- Follow-ups: contrastive answering (SufficientConditionSet); %why once D-ui #76 lands.
- Coordinate: confirm decision-queries handles satisfy ExplanationCarrier (or adapt
  resolve_why_answer) — internal, no public signature change.

## CI fix (base advanced)
- CI red on first push: base `eql/causal-verbalization` advanced with 2849bcff
  "[RDR] Name the fired rule with a code" — rule-identity now renders "by the base rule R0"
  / "refinement rule R1" / "alternative rule A1" (WhyAnswer.rule_code). My golden text was
  stale ("by the if/except if rule").
- Fixed: rebased onto the new base (clean auto-merge of WhyQuery/ExplanationCarrier with
  rule_code), updated test golden strings + user-doc prose to the code vocabulary. Full
  test_eql_rdr = 294 passed; docs rebuild clean. Amended + force-with-lease pushed.
