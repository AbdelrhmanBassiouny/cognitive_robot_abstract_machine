# fix/eql-match-collection-attributes — PR #556 (eql-existential-semantics / match-collection-attributes)

## Done (2026-11-04)
- Split out of #495, stacked on it (`ca2cc78382`): option A collection matching, list/tuple
  `==` by order, nested domain as a filter, optional collections. Local: 1652 passed.

## Resolved (2026-11-09)
- The owner chose **option A** in the shared doc vote, so no code change is needed. Recorded on the
  #495 match.md thread (discussion_r4516037143). The owner resolves that thread.
- Read at head `51441f7ebf`, which merges the base `b8b69c05ea`: the merge probe against the base is
  clean; #556 has no review threads or comments; the branch has no upstream PR.
- CI at `51441f7ebf`: still running when read. krrood, giskardpy, semantic_digital_twin, coraplex,
  cramph, segmind, experiments and probabilistic_model were in progress; every completed check passed.
  Local tests were *not* run at this head (krrood is not installed in this session).

## Next
- Draft. Labels: bug-fix, bug, api-break.
- Read CI at `51441f7ebf`.
