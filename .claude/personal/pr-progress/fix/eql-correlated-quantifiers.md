# fix/eql-correlated-quantifiers — PR #495 (eql-existential-semantics / correlated-quantifiers)

## Done (2026-11-04)
- Split: quantifiers only now (`661a3d92f2`); base is #555. Match moved to #556/#557.
- Review round 1 fixes in `6c450180be`, `60899651e6`. Local at `36c1619306`: 1583 passed.

## State
- Ready (owner kept it ready). CI on `36c1619306`: *not checked*. Suggest `api-break`
  (for_all on empty domains, exists rows) and talk to the krrood code owners.

## Next
- Open threads wait on the owner: bag vs set (repeated 10), `flat_variable` automation,
  performance (~4%). The match.md thread points at #556 and stays open until the vote.
- Still open: which of `exists-semijoin` / `negation-antijoin` this item supersedes.
