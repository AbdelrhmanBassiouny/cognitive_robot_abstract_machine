# fix/eql-correlated-quantifiers — PR #495 (eql-existential-semantics / correlated-quantifiers)

## Done (2026-11-04)
- Merged `origin/main` (merge `9a6210279d`) to resolve the conflicts the maintenance pass
  kept reporting. The merge probe against cram2 `main` `f3c6df91` is CLEAN at that head.
  The PR description's "Merge with main" section has the details.
- Key change beyond the markers: main builds instances from bindings, which bypasses
  `construct_instance`. `_construct_argument_from_bindings_` therefore applies
  `_as_constructor_argument_`; without it, 16 construction tests fail.
- Local runs: the PR's modules 116 passed; `test_eql` 1548 passed; the rest of
  `krrood_test` passed apart from environment-only failures (docformatter, graphviz,
  semantic_digital_twin).

## State
- CI on `9a6210279d`: *not checked* yet.
- No upstream PR yet. The owner confirmed the item is finished, so the PR stays ready and
  is due for promotion on the next maintenance pass.

## Next
- Read CI on `9a6210279d`. Once the next maintenance pass sees a clean merge, the
  `needs-resolution` label clears.
- Still open, not this PR's blocker: which of `exists-semijoin` / `negation-antijoin` this
  item supersedes (see the item's notes).
