## Plan
- Keep #495's per-outer-binding quantifiers over cram2#905's narrower exists fix (now on main), with bag semantics; set semantics is plan item plain-where-locals-existential.

## Done
- Merged main (b8b69c05e): 1623 passed, 3 skipped; carried into #556/#557.
- 3b99b73cf: scoping tests compare distinct sizes; test_eql 1522 passed, 3 skipped; carried into #556/#557; replied on the bag vs set thread (left open).

## Next
- Read CI at 3b99b73cf.
- Owner: resolve the bag vs set thread; decide flat_variable automation, performance and the api-break label.
