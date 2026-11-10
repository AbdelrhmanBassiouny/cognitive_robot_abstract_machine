## Plan
- State objects, default domains through TermReader.instances_of, expression domains as FlatVariable / InstanceFilteredFlatVariable; removed objects filtered from list/tuple/set values

## Done
- First review addressed in fa1dc1af6e; 7 of 8 threads resolved
- Merged main (#535 landed) in ff1fa9d22b and pushed; merge probe clean; test_eql + test_planning 1601 passed

## Next
- Read CI on ff1fa9d22b; the next maintenance pass clears needs-resolution (this run's pass hit the Action race)
- Last thread stays open: a match in set_of still does not correlate after #915
- Owner: fold the filtering rule into the roadmap (12-entry limit)
