## Next
- Amend commit + force-with-lease; update PR #84 description to source model; keep draft;
  subscribe; watch CI. Re-run full test_eql_rdr + test_verbalization after reshape.
- Follow-ups: contrastive answering (SufficientConditionSet); %why once D-ui #76 lands.
- Coordinate: confirm decision-queries handles satisfy ExplanationCarrier (or adapt
  resolve_why_answer) — internal, no public signature change.


## Plan
Formal ask surface: a `why(...)` factory in `factories` returning a query construct that
composes over the explanation a RESULT already carries (2026-07-17 decision), verbalizable
via the W2 causal grammar. Plus user + developer docs and the bibliography. Contrast
reserved; %why deferred to D-ui #76.
