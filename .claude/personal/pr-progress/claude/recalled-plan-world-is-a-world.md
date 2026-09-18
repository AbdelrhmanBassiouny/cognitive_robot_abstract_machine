### PR #374 - an alternative mapping is converted after the mappings it holds

Review round handled and pushed as 35515b9 on claude/recalled-plan-world-is-a-world.

The two reviews
- tomsch420 (changes requested): inferring the order is not doable, no topological
  sort need exist; declare the dependency on PlanMapping instead.
- Abdelrhman (owner, overrides): keep inferring, check for a cycle first and raise
  instead of letting the sort hide one; no cycle -> take the topological sort; a cycle
  is for the author to break by declaring, and the error should suggest how.

What shipped
- New krrood/ormatic/data_access_objects/conversion_order.py: ConversionOrderConstraint
  with DeclaredOrder/HoldingOrder subclasses (each carries its own description and
  suggested fix), and ConversionOrder building the graph and sorting it.
- A declaration wins over a holding order pointing the other way, so declaring is what
  breaks a cycle; every other holding order goes in, then digraph_find_cycle decides.
  A cycle raises ConversionOrderCycle (krrood/ormatic/exceptions.py).
- from_dao rewired, _conversion_order removed, declared edges now carry DeclaredOrder.
- Tests: test_mappings_that_hold_each_other_have_no_conversion_order (fails without
  the check), test_a_declared_dependency_decides_where_holding_disagrees, plus the
  existing held-before-holder test. Dataset mimics OneSideOfAHoldingCycle /
  OtherSideOfAHoldingCycle and their mappings.
- test/krrood_test: 2085 passed, 5 skipped; 2 failures are the sandbox missing the
  graphviz dot binary.

State
- PR description rewritten to match; one PR comment posted answering both reviews.
- Left ready-for-review (not re-drafted): the owner marked it ready themselves and it
  carries in-review.
- Not verified here: experiments / semantic_digital_twin suites (packages not
  installed in this sandbox) - CI covers them.
- Session's designated branch claude/pr-374-comments-zpalus was not pushed; the owner
  chose to put the work on the PR branch instead.
