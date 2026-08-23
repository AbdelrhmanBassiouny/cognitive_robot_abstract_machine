**Session: `/plan-item-resolve rdr-refactor d-core-single-class` (PR #159, branch
`D-core-single-class`).** Mode: `auto`. Work goes on the item branch; this session's own
harness branch `claude/rdr-refactor-d-core-single-xbadko` stays unused (§15/§20 precedent).

## What was stalling it

A review round on 2026-08-23 09:48-18:41Z, submitted 18:45:31Z against the current head
`34df6172`: **30 threads, none answered, none resolved, none outdated.** The item's `notes`
end at §28's rename and never recorded it. Sixth instance of this plan's staleness class
(§5, §14, §18, §19, §23, §27). Nothing else is wrong: dependency `d-core-expert` is
`open_ready`, the base merges into the branch clean, baseline is 228 passed / 0 failed.

Secondary, not a blocker: the branch is one commit behind its base (`af77399b`), and CI has
queued nothing on `34df6172` (`total_count: 0`, `mergeable_state: unknown`) - §21's
base-moved-then-push mechanism says the push at the end of this round should trigger it.

## Plan

1. **Mechanical asks** - renames (`template` -> `underspecified_query`, `knowable` ->
   `satisfiable`, `knowledge` -> `*_sufficient_conditions`, `bird_conditions_before`,
   `returns_ellipsis`), docstring fixes (`case context`, the stale `target-knowledge`
   reference), drop the word `live`, drop the redundant `bool()`.
2. **Dedupe** - `first(species)` unified (3 copies), `ExpertCall` takes the context and
   requests, `labelling_answer` reuses `maximally_specific_answer`.
3. **Assertions** - structural alternative/refinement assertions (3 threads), the failed
   domain validation, and the 0.95 percentage replaced by the exact ambiguous-row set.
4. **pytest conversion** - this PR's two `unittest` files. The "everywhere / previous PRs"
   half is 7 more files on earlier branches: raised, not done unilaterally.
5. **Two TDD probes the reviewer asked for** - the convergence-detection condition
   (`single_class.py:488`) and whether `conditions_root` is always correct (`:504`). Probe,
   report, leave the design call open.
6. **10 design questions** answered on their threads and **left open** - the standing rule
   that a thread asking a question is the developer's to close.

## Status

Not started - plan just written.
