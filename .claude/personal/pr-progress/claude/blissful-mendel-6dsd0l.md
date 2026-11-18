## Plan
- Fix the regression the merge of main (145201d78f) caused in `test_realization_split`, once the developer chooses how: the symbol graph imports `krrood.parametrization`, whose `__init__` loads the grammar and so `inflect`.
- Answer the open question on CI enforcing boundaries (thread left open, reply posted).

## Done (read at 2ee94db3bd)
- Stack pass: main caught up, branch restacked, no conflicts (merge probe clean), no upstream pull request.
- Review threads: determiner table is an RST list-table; `MorphologyProcessor.rewrite` dispatches over `LeafRealization` subclasses; the split test derives its libraries from the realization modules' imports. Three threads resolved.
- 813 verbalization and core-boundary tests pass; the split test fails on the regression above.

## Next
- Developer's decision on the fix, then rerun the verbalization and core-boundary tests.
- CI checks on the new head were still running when read.
