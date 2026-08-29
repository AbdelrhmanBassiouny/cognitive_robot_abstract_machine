# d-core-backend (PR #210, branch `D-core-backend`, base `D-core-single-class`)

Last slice of #68's three-way split: `d-core-expert` (#98) -> `d-core-single-class`
(#159) -> **this**. Planned and implemented in one `auto`-mode session; full
rationale in the plan's `roadmap.md` section 31.

## Done

- Branch cut from `origin/D-core-single-class`; draft PR #210 opened before any code.
- `rdr/backend.py` + `test_eql_rdr/test_rdr_backend.py` pushed as `8cb490de1`
  (543 lines, two new files, nothing else touched).
- #68's eleven `backend.py` threads applied. Nine as asked; the `fill_in_place`
  split was already settled by the review (lazy `infer` / eager `fill`); and
  `key_from_attribute` became `ModelKey.from_attribute` rather than moving to
  `core/helpers.py` - answered differently from the ask, so stated on the PR and
  in the roadmap rather than done quietly.
- Two changes beyond the threads, both forced by what landed underneath:
  `fit` calls `EQLSingleClassRDR.fit` once (a per-case `fit_case` loop would save
  once per case since #159 and would not converge), and the no-ground-truth path
  passes `targets=None` rather than a sentinel.
- Verified: `test_eql_rdr` 244 -> 261 passed, zero baseline ids lost (sorted id
  lists, not counts); `test_eql` 1181 passed / 3 skipped; six mutants each fail
  exactly the tests that name them.
- `plan.yaml` (status, PR, session, notes) and roadmap section 31 pushed; PR
  description rewritten to match what landed. PR left as a draft.

## Next

Nothing outstanding in this session. What a reviewer may want to decide:

- Whether `RDRBackend` should implement `QueryBackend`. Flagged and not done -
  `SelectiveBackend` raises on an ellipsis match and `GenerativeBackend`
  constructs new instances, so attribute completion fits neither, and
  `rdr-decision-queries` is the item that actually needs the conformance.
- `parameterizer.py:167`'s `InvalidEllipsis` narrowing now has a concrete call
  site in `fill`; the probe stays filed on `no-rule-fired-resolution`.

## Watch

- CI queued **21 jobs** on the first push and the PR reads `mergeable_state:
  unstable`, overturning the plan's expectation of silence. Since #159 and #98
  still queue nothing and read `unknown`, the wedge is each of those pull
  requests' own merge ref, not the stack or the base. Recorded in roadmap 31.
- The harness designated `claude/plan-item-kickoff-rdr-refactor-7c99yj`; the
  manifest and every sibling say `D-core-backend`, which is what was used
  (section 20's precedent, confirmed with the developer then).
