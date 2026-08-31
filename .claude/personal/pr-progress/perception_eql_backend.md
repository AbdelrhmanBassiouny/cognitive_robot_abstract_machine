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

## Next

- **Five threads are open on purpose, and none is this branch's work.** Four schedule the
  predicate redesign rather than asking for a change here - r3893160382, r3893312001 with
  its two follow-ups, r3893576773 (all `perception-predicates-guide-the-search`) and
  r3893463818 (recorded on `choose-detection-method`) - so the developer closes those
  himself. The fifth, r3893476097, is done and carries a question back: whether the three
  older inline imports in `base_expressions.py` should gain reason comments too. It stays
  open until he answers, since resolving would bury the question.
- Nothing else outstanding. #222 is a draft awaiting review.

## Watch out for

- Base is #221, not #205. Do not restack onto #205.
- **Native evaluation returns nothing for a `Match` carrying an ellipsis attribute**, so
  the ellipsis attributes must be dropped from the check and the stated ones re-applied.
- **Native evaluation does not narrow a domain by the declared type**, so the backend
  does it (`LookRequest.admits`). Verified, not assumed.
- Correctness never depends on the narrowing being honoured: every stated attribute is
  checked again over what came back.
- A parent baseline taken in a `git worktree` is meaningless unless that worktree's own
  `*/src` are on `PYTHONPATH` — `uv sync` installs the workspace editable, so the
  worktree otherwise imports the branch's source. Check `krrood.__file__` first.
- The container: `uv sync --extra dev --python 3.12`, `--noconftest`.
  `test/krrood_test/test_eql/test_backends.py` and six ROS-dependent experiments modules
  do not collect here, identically on both sides.
