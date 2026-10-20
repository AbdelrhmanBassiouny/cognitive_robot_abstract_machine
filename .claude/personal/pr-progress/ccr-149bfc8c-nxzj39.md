Draft PR #520 (bug): a query evaluated during another evaluation gets its own EvaluationContext.

Plan
- Public evaluate() starts a new evaluation (SymbolicExpression._start_evaluation_); _evaluate_ still joins the running one.

Done
- Failing test + mimics; fix; krrood EQL dirs green; draft PR #520 opened with bug label.

Next
- Wait for review/CI prompts. After merge, remove the contextvars.Context().run workaround in HoleRulesBackend.concluded_kind (PR #511).
