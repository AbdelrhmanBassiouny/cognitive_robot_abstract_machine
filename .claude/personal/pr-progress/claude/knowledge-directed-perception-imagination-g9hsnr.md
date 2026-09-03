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

## Next

- Nothing outstanding on the branch. It is a draft, as the convention asks.
- The dashboard republish is owed: the live artifact has to be read back first (474KB of
  generated HTML), which is why it is left to the end of the session.

## Known

- This container has no ROS: `test/experiments_test/` cannot be collected (rclpy,
  geometry_msgs) and `scripts/regenerate_all_orm.py` fails in giskardpy's generator - both
  before this branch changed anything. The Montessori modules were run outside that conftest,
  identically on this branch and its base.
- `plan_item_bootstrap.py open` fails through `save-plan.sh` again (seventh round); the
  manifest and roadmap were written directly.
