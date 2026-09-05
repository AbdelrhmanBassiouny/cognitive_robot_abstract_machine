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

## Next

- Nothing outstanding on the branch. It is a draft, as the convention asks. Head is
  e339b2ef2; `mergeable_state: unstable` with checks running, none red when last read.
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
