## Plan
- State objects, default domains through TermReader.instances_of, expression domains as FlatVariable / InstanceFilteredFlatVariable; removed objects filtered from list/tuple/set values

## Done
- First review addressed in fa1dc1af6e; 7 of 8 threads resolved
- Merged main (#535 landed) in ff1fa9d22b: value_of_term/TermValue, EvaluationContext.current_term_reader; test_eql + test_planning 1601 passed
- Parked on ccr-a0dcce67-u1j40w: maintenance push failed (exit 12, upstream-reviews Action cancelled)

## Next
- git checkout -B ccr-b32c8432-18ncpi origin/ccr-a0dcce67-u1j40w, then maintenance push and maintenance restack --stacked-on ccr-b32c8432-18ncpi
- Last thread stays open: set_of still does not correlate a match on main (checked after #915)
- Owner: fold the filtering rule into the roadmap (12-entry limit)
