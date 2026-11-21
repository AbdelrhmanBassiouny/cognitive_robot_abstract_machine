# A look is described by a match (PR #275, draft)

Plan item `a-look-is-described-by-a-match` of `knowledge-directed-requests`, track
`method-selection`. Base `claude/plan-item-kickoff-perception-idzwsk` (#266).

## Review rounds

Round 1 (`0098923a1`), threads r3942253246 + r3942264406 -- one change:
`EQLSingleClassRDR.state_rules` plus the shared `DetectorChoice` base. Both resolved.

Round 2 (`c9f126833`), thread r3943261173 -- "why not just write a normal rule using
`with` and `add`?" The answer is that we should, so `StatedRule` is deleted and
`state_rules` takes the rule tree itself. A list of pairs was `where`/`add`/`alternative`
in a second vocabulary, and could not express a refinement at all. `DetectorChoice` gains
`chosen_detector`; `RulesAlreadyPresent` / `RulesOverAnotherCase` guard adoption;
`_add_alternative` folded back into `_splice_rule`. Thread resolved.

## Verification

2518 passed, 5 skipped across `test/krrood_test`; 1572 passed, 3 skipped across
`test_eql` + `test_eql_rdr`; 70 passed across the three montessori perception suites.
The two `test_object_diagram.py` failures are graphviz `dot` absent here (identical on an
untouched tree). Experiments need `--orm-build=never` in this container (`json_msgs`).

## Next

Nothing outstanding. PR description updated to match `c9f126833`; still a draft. CI not
read.

## Related

#283 (draft, `bug`, off `main`) fixes the `insert_at` splice this branch found. #275
needs nothing from it -- the trees now build each condition at the point it is spliced.
