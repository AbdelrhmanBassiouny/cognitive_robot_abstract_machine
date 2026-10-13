# knowledge-directed-grounding — standing rules

- The perception package lands on `main` first (`montessori-perception-on-main`), since every item across all three successors edits files that exist on no branch but `tracy_icra`.
- The `surfaces` track (this plan) is sequential: each item edits the same pipeline the previous one left behind, so branches stack rather than run in parallel.
- `surface-finish-annotation` (`knowledge-directed-requests`) depends on nothing and can start immediately, off `main` - it touches only `semantic_digital_twin`.
