## NEXT
- Watch CI on #85 (now at head 9b32570a) after the verbalize() fix; keep
  draft; keep description current.
- If a reviewer wants the `all_bindings` recursion fixed here rather than in
  Track T, that is a scoped follow-up — flag, don't bundle.

---
(historical design rationale below)


## Restack watch + upstream API follow (2026-07-19)
Base `eql/causal-verbalization` restacked repeatedly under #85 (steward-driven,
not my session): 2849bcff -> 7bb17d23 -> 3b3bea61 -> 2bb7503e, each merged
cleanly into my branch. One restack merge commit (d74425ef) was authored as
Claude/noreply@anthropic.com — flagged to the developer; their call: leave it
as-is permanently, non-issue, don't raise it again.

One restack (-> 2bb7503e) carried a real upstream API change: `WhyAnswer` lost
`rule_kind` and its `.verbalize()` convenience method — callers now call
`verbalize_expression(why_answer)` from the pipeline directly. CI caught it
(`test_three_liner_verbalizes`: AttributeError). Fixed in 9b32570a: updated
`test_decision_queries.py` and the three-liner in `underspecified.md` to call
`verbalize_expression()` directly; no behavior change on this branch's side.
Full `test_eql_rdr` re-verified green (290) after the fix. PR description
updated to match (code sample + test count); kept draft.


# PR plan: rdr/decision-queries — backend explanation semantics + the decision-query pattern (Why track, C1 — REFRAMED 2026-07-17)
Base: `eql/causal-verbalization` (W2, PR #82). **Draft PR #85 open**
(`rdr/decision-queries -> eql/causal-verbalization`).
Session: https://claude.ai/code/session_013NepUGgubeWHnLT5TUPLdu


## STATUS — implemented, pushed, CI watch (2026-07-17)
All five scope items + six TDD anchors done. Full `test_eql_rdr` = 291 passed
(273 baseline + 18 new). docformatter via `scripts/format_docstrings.py`; stray
downloads reverted, zoo pickles are gitignored.

Delivered:
