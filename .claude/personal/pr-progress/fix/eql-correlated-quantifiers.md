## Plan
- Keep #495's per-outer-binding quantifiers over cram2#905's narrower exists fix (now on main).

## Done
- Merged main at b8b69c05e keeping this branch's logical_quantifiers.py; clean against main 8574ddfd0; 905's tests pass; added a local-scope regression test; test_eql + test_class_diagram 1623 passed, 3 skipped. Carried into #556 and #557 (both clean).

## Next
- Read CI at b8b69c05e.
- Owner: decide the open threads (bag vs set, flat_variable automation, performance) and the api-break label.
