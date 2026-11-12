# ccr-b32c8432-18ncpi — #541 (upstream cram2#922)

## State at 73014d8f24 (2026-11-12)
- Merged main b0e961c745 in 258d5dcb92. main had made krrood keyword-only (#923); the 12 conflicting files keep this branch's domains, quantifier operands and MatchedEntity, written against main's keyword-only signatures. FlatVariable stays removed (main only changed its signatures); transporting.py keeps main's module docstring.
- 73014d8f24: test dataclasses/mimics kw_only, test docstrings, module docstrings, State/MatchedEntity docstrings within four lines, State doctest uses from_(domain=...).
- Merge probe against main clean at 73014d8f24.
- Locally (py3.12): test_eql + test_planning + test_ormatic + test_symbol_graph + test_class_diagram 1977 passed / 4 skipped; other krrood dirs 1600 passed, 4 environment failures (no Graphviz `dot`, casadi version).
- Upstream #922: approved by tomsch420 and LucaKro, CI 1/1 green at 66bdac8d35; not read at 73014d8f24.

## Open
- Upstream thread state.py:74 (tomsch420): frozendict. Needs a new dependency on py3.12, owner to decide. Thread left unresolved.
- krrood check flags with_facts / with_objects_added / with_objects_removed (preposition prefix). Renaming changes #535's API, owner to decide.
- Main-owned docstrings still over the 4-line limit: State class, Match.from_.
- #605 merges this branch at 66bdac8d35 (stacked on #556's branch), so it hasn't got this merge yet.
