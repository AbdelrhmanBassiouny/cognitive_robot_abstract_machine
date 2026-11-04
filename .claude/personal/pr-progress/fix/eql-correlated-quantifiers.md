# fix/eql-correlated-quantifiers — PR #495 (eql-existential-semantics / correlated-quantifiers)

## Done (2026-11-04)
- Review round 1: 23 of 27 threads fixed and resolved (`6c450180be`, `60899651e6`).
- `match` on collections, option A (`3a67fd6030`): reading by declared type, error for a value
  of neither type; lists/tuples `==` by order/length (also plain `==`); list of patterns needs
  the same length. Nested pattern's domain restricts its object (`fa89a33f60`), and generative
  backends pick from it (`fee20b2900`). Local: `test_eql` + `test_class_diagram` 1671 passed.
- Shared doc for the vote: https://claude.ai/artifact/EjQU8z1th3N82LxWEdXNCT

## State
- PR is ready (owner kept it ready). CI on `fee20b2900`: *not checked*. Now `api-break`
  (suggest the label; discuss with the krrood code owners).

## Next
- `match` thread stays open until the doc's vote (A/B/C/D); B means an error for plain values.
- Three other open threads wait on the owner: bag vs set (repeated 10), `flat_variable`
  automation (separate item), performance (~4%).
- Still open: which of `exists-semijoin` / `negation-antijoin` this item supersedes.
