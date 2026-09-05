# PR #255 - imagination-world-rejects-what-a-predicate-refuses

Plan `knowledge-directed-perception`, track `request-language`. Branch
`claude/knowledge-directed-perception-imagination-g9hsnr`, based on
`claude/kdp-search-constraints-pfaph7` (#238), draft.

## Done

- Branch re-cut from #238 (it arrived cut from `integration`), draft #255 opened, manifest
  and roadmap written on the notes branch (`search-clipped-to-a-predicates-region` added to
  `depends_on`, since the rename is counted on #238's tree).
- `MontessoriShapeDetection` renamed `DetectedMontessoriShape` and made a
  `Role[MontessoriShape]` (53 references, 11 files).
- `ImaginedWorld`: a copy of the world a look was taken in, where each finding stands as a
  body built from the known piece's own measured outline. `MontessoriPerceptionPipeline.imagine()`
  makes one per look; `MontessoriScene` carries it; the piece detector spawns into it.
- krrood: a relation to something the statement describes is checked over what came back
  instead of refused, with each description held to the answer that resolved it; and
  `PerceptionBackend.discard`, which the Montessori backend uses to take rejected findings
  out of the imagined world.
- Tests: 2 in krrood (through the existing mimic), 8 for the imagined world, 3 for the
  backend end to end. All mutation-checked.
- Verified: krrood eql 1326 passed vs 1324 on the base; Montessori experiments modules 321
  passed vs 310. Docstrings formatted. Pushed; PR description matches.

## Review round of 2026-09-03

Two threads, both answered exactly as asked, replied to and resolved (32471b172).

- *"`a` not `an`"* on the backend docstring: the rename had left every statement about the
  type reading `an(DetectedMontessoriShape)`, at 20 further sites across the two backend
  test modules. All say `a` now, which is krrood's own function for consonant-initial
  names and delegates to `an`. Two pre-existing `an(ShapeSortingHoleDetection)` in the same
  file came with them, since the import moved.
- *"rename this method to what it actually does"*: `ImaginedWorld._solid` is `_mesh_of`,
  which says what it answers and about what, and reads with its siblings `_frame_of` and
  `_transform_to`.

321 passed, 1 skipped, 11 xfailed across the Montessori modules - unchanged.

## Review round of 2026-09-05

One thread, *"why a fixed connection?"* on the connection `ImaginedWorld.spawn` builds.
Answered and left open at ae70e39a5, since the answer is a design justification rather
than a change he asked for.

A look reports one placement and nothing in the imagined world moves what it found, so
the measured pose is the connection rather than a state something could change.
`MontessoriWorld` already makes the same split for the same pieces and names the case a
free joint is for - `_spawn` welds, `_spawn_free_body` gives a `Connection6DoF` only
where gravity or a gripper has to move the shape, and `shapes_are_movable` is off by
default. A `Connection6DoF` would also register seven degrees of freedom per finding in a
world deep-copied every frame, and carry its placement in those dofs rather than in
`parent_T_connection_expression`, which `world.py:1012` already records as a hazard. None
of that was written down anywhere, which is why the question exists, so `spawn`'s
docstring says it now.

The remote head had advanced while this ran: the stack maintenance routine merged `main`
up through all seven branches into this one, three times over. Merged in cleanly (no
conflicts) and re-verified before pushing - 478 passed, 1 skipped, 11 xfailed across
`test/experiments_test/` with the six ROS-dependent modules excluded.

## Review round of 2026-09-05, second pass

He came back on the fixed-connection thread and overturned the answer, rightly: *"a
fixed connection is an information we do not have ... if we saw this in a later image
moved to another place that means it must not be a fixed connection"*. The first answer
argued from what the imagined world does today; his is about what the connection
*claims*, and a look measures where a piece is, never that it cannot move.

Changed at 90ff3861c. A finding hangs from a `Connection6DoF` and its measured placement
is written through `connection.origin`, whose setter un-composes the transform into the
seven dof values - so a later look that finds the piece elsewhere re-places it rather
than needing a different connection. `FixedConnection` refuses that with
`NotImplementedError`, which is the mutation check on the new test
`test_a_finding_can_be_placed_somewhere_else_by_a_later_look`.

Two things the first reply guessed at and this round measured. Spawning alone is
1.7-1.9x, but per look it is inside the noise - three alternating rounds on one capture,
same process, welded 0.243/0.233/0.240 s against free 0.236/0.226/0.216 s, same 3 pieces
each time. And the dof-accumulation worry was wrong: `remove_branch_from_world` takes the
seven degrees of freedom with it (20 findings give 140 dofs; removing them all leaves 0).

479 passed, 1 skipped, 11 xfailed across `test/experiments_test/` against 478.

**The reply could not be posted.** A pending review of his own (5120880820, on e339b2ef2)
sits unsubmitted on #255, and GitHub allows one pending review per user - the API acts as
that account, so every inline reply is refused with *"user_id can only have one pending
review per pull request"*. Exactly what #222's round of 2026-08-31 recorded. The reply is
written and waiting in the session scratchpad
(`reply_r3940306683.md`); submitting or discarding that draft unblocks it. The thread
stays unresolved until it can carry the reply, since resolving without one is forbidden.

## CI, traced 2026-09-05

Red since 32471b172, and not this branch's. The only failing job is
`test_each_lib (semantic_digital_twin)`, and its only entry is the `count_worlds`
module teardown in `test/conftest.py`, which raises when more than 30 `World`
objects survive `gc.collect()`. No test fails: 1545 passed, 1 error.

What says it is not ours:

- It names a different test each run - `test_the_world_can_be_named_as_what_put_a_belief_somewhere`,
  `test_reset_state_context_restores_state_on_exception`,
  `test_column_indices_of_degree_of_freedom_outside_the_state` - because a module-scoped
  teardown reports against whichever test ran last on that xdist worker. It is a
  threshold on a count, not an assertion about a behaviour.
- It is on the ancestor #227, which carries none of this branch's changes. #222, one
  below it, fails a *krrood* job instead and its sdt job passes; `main`'s red runs are
  the unrelated probabilistic_model jpt failure and its sdt job passes. So the leak
  enters the stack at #227, where #229's predicate classes arrive.
- This branch changes krrood's `backends.py` and experiments only, neither of which the
  sdt job runs, so its own commits cannot move that count. 32471b172 is docstrings and
  test articles.

`SupportedBy` retaining its bodies' world past `SymbolGraph.clear_instance()` was the
obvious mechanism and was measured here: no leak over five rounds. The sdt module cannot
be run in this container to narrow it further - it needs `iai_pr2_description` and the
other robot description packages.

Not fixed here deliberately: it is #227's, and fixing it on this branch would put
another item's work in this one's review.

## Next

- Nothing outstanding on the branch. It is a draft, as the convention asks. Head is
  e339b2ef2; the one red job is the inherited world-leak count above.
- The dashboard republish is still owed: the live artifact has to be read back first
  (474KB of generated HTML), which is more than a working session's context affords.
  `/plan-dashboard knowledge-directed-perception` in a fresh session does it.

## Known

- This container has no ROS: `test/experiments_test/` cannot be collected (rclpy,
  geometry_msgs) and `scripts/regenerate_all_orm.py` fails in giskardpy's generator - both
  before this branch changed anything. The Montessori modules were run outside that conftest,
  identically on this branch and its base.
- `plan_item_bootstrap.py open` fails through `save-plan.sh` again (seventh round); the
  manifest and roadmap were written directly.
