
# PR #196 - aggregate signature reads a missing attribute

Plan item `match-query-ergonomics / aggregate-signature-reads-a-missing-attribute`,
kicked off in auto mode. Branch `claude/plan-item-kickoff-match-query-npzr78` off `main`
at `2b44f1e5`. Draft PR #196, `bug` label. Roadmap section 21.

## Plan

1. Failing tests first, in `test/krrood_test/test_eql/test_verbalization/test_set_of_ranking.py`:
   - two `Sum`s over different chains have different signatures;
   - a restated `Sum` over the same chain keeps the same signature (what `_is_order_key` exists for);
   - a ranked `set_of` names the aggregate it is `ordered_by`, not the first one selected.
2. Fix: `QueryAssembler._expression_signature` walks `expression._child_` instead of the
   undefined `expression._chain_expression_`.
3. Verify: the seven existing `test_set_of_ranking` tests, then the whole
   `test/krrood_test/test_eql` suite.

## Done

- Context gathered; bug and its user-visible symptom re-measured on today's `main`.
- Scope check (`check_scope_overlap.py`): no path shared with #182 or #192.
- Branch, draft PR #196, manifest fields and roadmap section 21 recorded.
- Manifest corrections saved: #186 `in_progress` -> `done` (merged 2026-08-24), and a new
  item `chain-signature-reads-attribute-only-names` for the second read (see below).

## Next

- Write the three tests, watch them fail, apply the one-word fix, run the suite.
- Republish the dashboard.

## Decisions

- **The second read is a separate item, not part of this PR.** `_expression_signature`
  also builds its path from `step._attribute_name_` / `step._owner_class_`, which only
  `Attribute` defines - so `order.lines[0].price` and `order.lines[1].price` get equal
  signatures on `main`. Same root cause, different fix: a faithful key needs each mapping
  subclass to report its constructor arguments (no existing name works - `Call._name_`
  drops the call's arguments), which is core API in `mapped_variable.py` that #182 is
  rewriting. Tracked as `chain-signature-reads-attribute-only-names`, blocked on #182.
- The environment needs a Python 3.12 venv (roadmap section 14): the container ships no
  project dependencies, and 3.11 is too old for `make_dataclass(module=...)`.

## Outstanding

- The tracking-issue subscription (issue 181) was refused by the permission classifier, so
  this session will not see concurrent structural changes to the plan as events.
