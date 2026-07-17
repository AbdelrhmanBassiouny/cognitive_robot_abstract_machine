# rdr/why-answer (W1) — draft PR #81 -> D-core-engine

Session: https://claude.ai/code/session_01V2DJMF1C2bQjhLcPo5sFkx
Branch: claude/rdr-why-answer-6fnw2o (base D-core-engine; rebase onto main once
the split stack merges).

## Plan
Why-question core: WhyQuestion/WhyAnswer value objects built by content
selection over ClassificationTrace/FiredConclusion, EQLSingleClassRDR.why(case),
RDRBackend explain path, Explanation unification with explain_inference. Plain
why in v1; contrast reserved.

## Done
- rdr/why.py: frozen WhyQuestion (contrast reserved) + WhyAnswer + builder from
  trace; RDRConclusionExplanation(Explanation); CONTRAST_NOT_IMPLEMENTED pointer.
- observer.ClassificationTrace now retains its winning FiredConclusion (content
  selection only — no new capture machinery).
- explanation.py: Explanation ABC; InferenceExplanation is now a sibling of
  RDRConclusionExplanation; get_satisfied_conditions_as_string pulled up.
- EQLSingleClassRDR.why / answer_why / explain.
- RDRBackend.infer InferenceStrategy seam (FastInference / ExplainingInference),
  fast path unchanged.
- NoConclusionToExplainError.
- test_why.py (22 tests) green; test_eql_rdr (250) + test_eql (1058) green;
  docformatter matched to package single-line style; generated artifacts reverted.
- Draft PR #81 opened, subscribed.

## Next
- Watch PR #81 CI; keep it green and re-check on the ~1h check-in.
- Follow-ups (separate PRs): W2 eql/causal-verbalization (WhyAnswer.verbalize),
  W3 rdr/why-query-surface (why(...) factory + bibliography).
