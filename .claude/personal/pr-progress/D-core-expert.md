## D-core-expert (PR #98) — RDR engine: Expert policy split

First of the three PRs superseding closed-for-splitting `D-core-engine` (#68), per that
PR's review: `d-core-expert` (this one) → `d-core-single-class` → `d-core-backend`. Base:
`D-core-support` (#67, open/ready/CI-green). Plan came from `/plan-item-kickoff rdr-refactor
d-core-expert` (see that session's plan-mode transcript for full sourcing/citations).

### Status: DONE, PR #98 open as draft, subscribed to activity

- Extracted `expert.py` from the `D-core-engine` mega-branch and applied the #68 review's
  design decisions: `AnswerName(StrEnum)` (not `str, Enum` — decided during planning),
  `RuleAnswer` dataclass, `CaseContext` now built by the caller (not by `Expert`,
  per roadmap.md §6), every validator returns a `DataclassException` (new exceptions.py
  entries + `ConclusionDomain.hint()`/`validate()`), `_validate_conditions` stays a free
  function. Also retyped `interface.py`'s `AnswerRequest.validate`/`ExpertInterface.interact`
  (`Optional[str]` → `Optional[DataclassException]`) even though that file technically
  belongs to the already-merged-clean `D-core-support` slice — confirmed with the developer
  before doing so (no prior recorded resolution existed for that specific point).
- Tests rewritten as true `Expert` unit tests (hand-built `CaseContext` + stub
  `ExpertInterface`), decoupled from `EQLSingleClassRDR`/`single_class.py` (doesn't exist in
  this PR's dependency chain yet). `test_expert.py` (11), `test_conclusion_validator.py`
  (ported, 15), `test_exceptions.py` (8, new), `test_conclusion_domain.py` (+6). Full
  `test_eql_rdr` suite: 118 passed, same 22 pre-existing `jpt`-import failures as baseline
  (confirmed present before this change too, unrelated).
- Formatted with `scripts/format_docstrings.py`; hand-fixed one docformatter mangling of a
  pre-existing, untouched docstring on `ConclusionDomain.allows_none` it shouldn't have
  touched. Reverted an incidental `ormatic_interface.py` regeneration that running the test
  suite triggers as a side effect (never hand-edit that file, per AGENTS.md).
- PR #98 opened as draft; subscribed to all activity. CI just kicked off (all jobs
  in_progress at last check) — no review comments yet (brand new). Scheduled a ~1h
  check-in.

### Next steps (not done in this PR, flagged for the next kickoff)

- `test_ask_for_rule.py` on the `D-core-engine` mega-branch is actually an
  `EQLSingleClassRDR` integration test in disguise (every test calls `fit_case`/`fit`/
  `classify`) — it was **not** ported here. It needs to be carried into
  `d-core-single-class`'s own test suite when that item is kicked off.
- Once `d-core-single-class`/`d-core-backend` open, they should re-point onto this PR's
  tip (`D-core-expert`) instead of `D-core-support`.
- Watch for CI failures / review comments per the standing subscription posture; this is
  a PR I (the assistant) opened, so drive-to-green applies.
