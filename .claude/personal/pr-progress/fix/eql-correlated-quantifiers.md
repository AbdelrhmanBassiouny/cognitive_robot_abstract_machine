# fix/eql-correlated-quantifiers — PR #495 (eql-existential-semantics / correlated-quantifiers)

## Done (2026-11-04)
- Merged `origin/main` (`9a6210279d`); merge probe vs cram2 `main` `f3c6df91` CLEAN at that head.
- Review round 1 (owner, 27 threads): fixed in `6c450180be` (scope found top-down from the
  evaluated query, walk moved onto `QuantifiedConditional`, no `Literal` case, `flat_variable`
  element typing for dict/tuple) and `60899651e6` (a/an, names, `role_taker`, join example).
  23 threads replied + resolved. Local: `test_eql` + `test_class_diagram` 1647 passed.

## State
- PR is ready (owner kept it ready). CI on `60899651e6`: *not checked*.
- Branch is 25 commits behind `main` (not merged this round).

## Next
- Four open threads wait on the owner: element semantics in `match` (proposal: keep nested
  patterns, raise for plain values); bag vs set semantics (repeated 10, recommend bag);
  `flat_variable` automation (separate item, ask before `/add-plan-item`); performance (~4%).
- Act on the `match` decision; it touches docs, three test modules and the construction wrap.
- Still open: which of `exists-semijoin` / `negation-antijoin` this item supersedes.
