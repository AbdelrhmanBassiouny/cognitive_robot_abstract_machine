# perception-backend (#222, branch `perception_eql_backend`, base #221)

Plan item `perception-backend` of `knowledge-directed-perception`. Built 2026-08-30,
review round resolved 2026-08-31, both in `auto` mode. The reasoning is in that plan's
`roadmap.md` sections of the same name and in #222's description; this is the working
state.

## Done — the review round of 2026-08-31, pushed as `0eef6683`

The nine threads split five done, four deferred to a plan item.

- **Generative, not selective** (r3892957833). The developer's reasoning, which
  overrode this session's recommendation: with the instances already believed in we
  only ask for the pose, which is underspecified; with no belief, the look creates the
  instance. A statement is now a `Match` —
  `an(MontessoriShapeDetection)(supporting_surface=lid, pose=...)`. An attribute stated
  as `...` narrows nothing and rejects nothing.
- **The general half moved into krrood** (r3893140274, r3893153789). `PerceptionBackend`
  and `LookRequest` in `krrood.entity_query_language.backends` carry how a statement is
  read, narrowed and checked; `MontessoriPerceptionBackend` carries only the Montessori
  pipeline and the supporting-surface narrowing. krrood gains no `experiments` import.
- **`AttributeEquality` → `AttributeEqualityToLiteral`** (r3893535014), docstrings
  included, and the **inline import** in `_constrained_variables_` states its reason
  (r3893476097). Both in `a6aa37a3`.
- **`SceneRequest.admits` removed**, left dead by the move — `LookRequest.admits` does
  that job now.
- **Manifest/roadmap**: `status: in_progress`, the pending-review blocker recorded, the
  roadmap round written, the new item `perception-predicates-guide-the-search` added
  (22 items), the algorithm-capabilities thread recorded on `choose-detection-method`.
  Saved as `16c470cf`, dashboard republished, structural change on #201.
- **Tests**: `test/experiments_test/` **362 passed** against **348** on the parent;
  `test/krrood_test/test_eql/` **1087** against **1072**, failing-and-erroring set
  byte-identical (177 lines both sides).

## The round, replied to once the pending review was submitted

The developer submitted review `5064626804` on 2026-08-31, which unblocked every inline
reply (a pending review by the account the tooling authenticates as refuses them all).
All nine threads now carry a reply. **Four are resolved** - generative (r3892957833), the
krrood placement (r3893140274), the Montessori type out of the general half
(r3893153789), and the `AttributeEqualityToLiteral` rename (r3893535014).

## Done — the restack of 2026-09-02, pushed as `e88f9b00`

The maintenance routine reported at 00:45 that `perception_per_supporting_surface` would
not merge in, skipped this branch and labelled it `needs-resolution`, which holds it out
of every promotion pass. **The conflict was not #221's.** Its tip had moved only by taking
`main` in (`5d3615b1` → `6a2f1199`, the `eql-probabilistic-qa` work), so all three
conflicted files were `main`'s probabilistic-query work meeting this branch's own additions
— two sides adding beside each other. Kept both in each case; no new code was needed.

- `backends.py` imports `ProbabilisticQuery` and `Average` alongside `Attribute`,
  `Literal`, `Variable` and `Comparator`.
- `exceptions.py` carries `BackendCannotResolveCondition` and
  `BackendCannotEvaluateProbabilisticQuery` as the two separate exceptions they are.
- `Directive` carries `LOOK_FOR` and `DISTRIBUTION_OVER`. `main`'s docstring framing is
  kept — its whole point is that `DISTRIBUTION_OVER` is not an imperative — and its count
  corrected now that there are three imperatives and four members.
- **Tests**: `test/krrood_test/test_eql/` **1110 passed** against **1087** on the pre-merge
  tip `9eb4d747`, failing-and-erroring set identical (178 lines both sides, diffed by
  name, baseline taken in a worktree with its own `*/src` on `PYTHONPATH`).
  `test/experiments_test/` **362 passed**, 1 skipped, 16 xfailed, unchanged.
- **Record**: roadmap section written, `blockers`/`notes` updated, #222's description
  gained a restack section.

## Next

- **Nothing on the branch.** #222 is green on all 23 checks, `mergeable_state: clean`,
  out of draft, and **all nine review threads are now resolved** — the developer closed
  r3893312001 and its two follow-ups himself, so the five-open state this note used to
  describe is gone.
- **The `needs-resolution` label is still on #222** and is what still withholds it from
  promotion. The routine clears it on its own next pass now that the branch merges
  cleanly (`maintenance_restack_steps.py`'s `WithholdBlockedBranch` clears it as a side effect), so it was left alone
  rather than removed by hand.
- **Do not re-draft this pull request.** The developer took it out of draft himself, which
  in the stack workflow is how a branch is approved for promotion; re-drafting would undo
  that approval.

## Watch out for

- Base is #221, not #205. Do not restack onto #205.
- **`main`'s entity query language now moves under this track.** #227, #238 and everything
  stacked past them meet the same three krrood files when the merge reaches them; the
  resolution is in the plan's `roadmap.md` so it is not re-derived four times.
- **Native evaluation returns nothing for a `Match` carrying an ellipsis attribute**, so
  the ellipsis attributes must be dropped from the check and the stated ones re-applied.
- **Native evaluation does not narrow a domain by the declared type**, so the backend
  does it (`LookRequest.admits`). Verified, not assumed.
