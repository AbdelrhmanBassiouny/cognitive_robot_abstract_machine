# insert-at splices above an outside parent (PR #283, draft, `bug`)

Off `main`. One root cause, no unrelated cleanup.

## The bug

Reading an attribute answers with the same node every time, so one rule's whole
condition can be the node another rule's condition is written over
(`drawer.correct` and `not_(drawer.correct)`). When the wrapping condition is
written *before* the query, it becomes that attribute's primary parent and belongs
to no rule tree; `insert_at` took `anchor._parent_` as the edge to splice above and
told that foreign node to hold the new branch, so the branch ended up holding what
holds it — `Attribute -> Alternative -> Not -> Alternative -> ...`. `_root_` walks
parents until they run out, so evaluation afterwards never returned.

Written the other way round the attribute's primary parent is the tree's own
`Where`, and it works — which is why fitting an RDR case by case never hit it: the
expert builds each condition at the moment it is inserted.

## The fix

`insert_at`'s cleaning now covers the anchor as well as the incoming conditions: it
splices above a parent from *outside* the branch being added. `SymbolicExpression`
gains `_contains_` and `_parent_outside_`. Where the primary parent is already
outside the branch — every case but this one — it is still chosen, so nothing else
moves.

## Tests

`test/krrood_test/test_eql/test_core/test_rules.py`, both failing before and passing
after:

- `test_splicing_beside_a_condition_the_new_branch_wraps_leaves_the_branch_alone`
- `test_a_rule_whose_condition_the_next_rule_wraps_is_still_answered` — acyclicity
  asserted first, walking parents with a seen-set, so a regression fails in under a
  second rather than hanging CI.

## Verification

2280 passed, 5 skipped across `test/krrood_test`. The two
`test_ripple_down_rules/test_object_diagram.py` failures are environmental
(graphviz `dot` absent here) and fail identically on an untouched tree.

## Next

Nothing outstanding. Draft PR #283 opened with the `bug` label; CI not read.

## Related

Found while building `state_rules` on #275, which works around it by having its
mimic detector state `look.depth_is_returned == True` rather than a bare attribute.
Once #283 lands that workaround is optional, not required — #275 needs no change.
