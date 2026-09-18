### PR #374 - an alternative mapping is converted after the mappings it holds

Handling the review round on PR #374 (fork). Two reviews:
- tomsch420 (changes requested): inferring the order is not doable, no topological
  sort of the dependencies need exist; declare the dependency on PlanMapping instead.
- Abdelrhman (owner, overrides): keep inferring, but check for a cycle first and raise
  instead of letting the sort hide one; where there is no cycle take the topological
  sort; a cycle is for the author to break by declaring the dependency explicitly, and
  the error should suggest how.

Plan
1. Split the ordering out of FromDataAccessObjectState into
   `data_access_objects/conversion_order.py`: `ConversionOrderConstraint` with
   `DeclaredOrder`/`HoldingOrder` subclasses carrying their own description and
   suggested fix, and `ConversionOrder` building the graph and sorting it.
2. Declared orders win over holding orders that point the other way (so declaring is
   what breaks a cycle); everything else is added, then `rustworkx.digraph_find_cycle`
   decides. A cycle raises `ConversionOrderCycle` (krrood/ormatic/exceptions.py)
   listing the constraints and the declaration that would break each one.
3. Tests (test_dao_conversion.py): mutually holding mappings report the cycle; a
   declared dependency decides where holding disagrees; the existing
   held-before-holder test stays.

Done
- conversion_order.py, ConversionOrderCycle, from_dao rewired, dataset mimics
  (OneSideOfAHoldingCycle / OtherSideOfAHoldingCycle + mappings), 2 new tests.

Next
- Full test/krrood_test run, format_docstrings, commit.
- Open question for the user: the work belongs on PR 374's branch
  (claude/recalled-plan-world-is-a-world), not on the session's designated branch
  claude/pr-374-comments-zpalus - needs their go-ahead before pushing there.
- Then reply to both review threads (reviews, not inline comments - nothing to
  resolve inline).
