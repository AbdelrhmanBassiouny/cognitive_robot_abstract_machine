### Plan
Resolve the 17 owner review threads (11-23, 11-25), the only blocker. CI green and merge probe clean at 29b8c992ba; no upstream PR.
- Move field-type logic out of `match.py` into `WrappedField`: element types as a tuple (union members, tuple positions), `CollectionKind` for the collection classes, element `Variable` typed
- Comparator: convert sequences only when their types differ
- Rename `TSymbol` to `GenericSymbol`; drop empty `()` after patterns in docs and tests
- New tests: nested-list domain; a Role conditioned on its own name
- Reply to every thread; resolve only finished ones; leave the questions (equality set-vs-list, live list domain, duplicate conditions) open
### Done
- Research, stack pass, merge probe, baseline 85 passed
### Next
- Implement task by task, TDD
