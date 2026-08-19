# Match query access-pattern study (investigation session, no PR yet)

Task: study why match queries force `query.expression` / `query.variable`
detours, propose a clean way to omit them, and decide new plan vs existing
plan item.

Done:
- Swept all consumers of Match/AttributeMatch public attributes across the
  workspace (krrood source, coraplex/experiments/probabilistic_model,
  tests, docs). ~30 `.expression` sites and ~20 `.variable` sites are
  user-facing detours; both are documented idioms (underspecified.md,
  inference_explanation.md).
- Root cause: Match does not participate in the CanBehaveLikeAVariable
  underscore-sandwich convention that Query uses; its plain public fields
  (`parent`, `variable`, `type`, `conditions`, `domain`, `factory`,
  `kwargs`, ...) shadow domain attribute names, so symbolic access cannot
  be forwarded.
- Verified empirically that the two handles are NOT interchangeable and
  fail silently when swapped:
  * `q.where(q.expression.battery >= 50)` does not filter at all (returned
    the full domain) - latent correctness bug, possibly same root cause as
    eql-existential-semantics' uncorrelated-evaluation findings.
  * `set_of(match.variable.parent, ...)` silently drops the match's
    conditions (only `match.expression.parent` carries them).
- `the(match)` / `entity(match)` also mis-route (Match is not a
  SymbolicExpression; falls into Match(factory=match) -> assert_never).
- Proposed design: (1) bug-fix PR for the silent where no-filter, (2)
  underscore-rename Match internals + guarded `__getattr__` forwarding to
  the lowered query, (3) factories unwrap Match; consumer + docs migration.
- Recommendation delivered: new plan (multi-PR, cross-package migration,
  coordination with in-flight D-core stack #63+ which adds
  test_underspecified_match.py); no existing plan covers EQL match API
  ergonomics.

2026-08-19: developer approved tracking. Created plan
`match-query-ergonomics` (2 waves / 2 tracks / 3 items, tracking issue
#181, dashboard
https://claude.ai/code/artifact/cc14baa7-487a-4ff3-b902-516ec077e1d4).
Developer chose (AskUserQuestion) to home the where no-filter bug in this
plan (item where-query-rooted-attribute-no-filter, with a cross-check
against eql-existential-semantics #137 at kickoff) and to create the
tracking issue. This session's investigation role is complete; item work
starts via /plan-item-kickoff from the dashboard.
