# PR #255 - imagination-world-rejects-what-a-predicate-refuses

Plan `knowledge-directed-perception`, track `request-language`. Branch
`claude/knowledge-directed-perception-imagination-g9hsnr`, based on
`claude/kdp-search-constraints-pfaph7` (#238), draft.

## The plan

1. Rename `MontessoriShapeDetection` to `DetectedMontessoriShape` and make it a
   `Role[MontessoriShape]` (53 references, 11 files on #238's tree).
2. A look spawns what it recognised into a copy of the world it was taken in, so every
   detection has a real `Body` as its role taker and the original world is untouched.
3. krrood: a relation the look could not narrow itself by is checked over what came back
   instead of refused - described things are pinned to the domain that answered them so
   the condition evaluates natively. A variable neither sought nor described still raises.
4. `PerceptionBackend.discard` - what the statement rejected leaves the imagined world.

Tests first at both levels: krrood through the `BackendThatLooksAtTheWorld` mimic,
experiments through the pipeline and one capture end to end.

## Done

- Branch re-cut from #238 (it arrived cut from `integration`), pushed, draft #255 opened.
- `plan.yaml` and `roadmap.md` written on the notes branch: status `in_progress`,
  `search-clipped-to-a-predicates-region` added to `depends_on` (the rename is counted on
  #238's tree and six of its files exist only there).

## Next

- Environment: `pip install -U uv`, then `/usr/local/bin/uv sync --extra dev --python 3.12`.
- Write the failing krrood test for a refused relation, then the experiments tests.
- Decide the end-to-end relation by what evaluates offline: `InContactWith` needs a
  collision detector, `Supports` and `SupportedBy` are pure geometry. Record the choice.

## Known

- `plan_item_bootstrap.py open` fails again (`save-plan.sh` exits 1 through it); the
  manifest and roadmap were written directly and pushed with `save-plan.sh`, as six
  previous rounds on this plan did.
