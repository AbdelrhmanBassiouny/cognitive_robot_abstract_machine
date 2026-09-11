# #265 — integrated-simulation-pipeline (plan icra-foundation)

## Plan for this session (/plan-item-resolve, auto mode)

The item was stalled, not on review and not on a failing check: the branch had
conflicted with `main` since 2026-09-07, so the stack maintenance routine labelled
#265 `needs-resolution` and skipped it on every pass after — twelve comments, nobody
picking it up, and the manifest saying `in_progress` with no mention of it.

1. Record the real blocker on the item before resolving anything. — done
2. Merge `main`, resolving the two conflicting files. — done
3. Sweep for the stale readers git cannot flag, per the roadmap's standing hazard. — done
4. Test first, then fix, then push; keep #265 a draft. — done
5. Update roadmap, manifest, PR description, dashboard. — done

## Done

- **`b5e2e2669` merges `main`.** Two conflicts: an import union in
  `test/coraplex_test/test_plan/test_executables.py` (this branch's `ExecutionType`,
  main's `Context`, both used), and `world_description/geometry.py`, where main's
  `f4c15c243` gave every `to_json` a `**kwargs` parameter while this branch's
  `Shape.to_json` names its four fields because a `finish` is a `StrEnum` the generic
  `_serialized_fields` reading does not restore. Kept this branch's fields and main's
  keyword arguments.
- **The hazard's fourth instance, first as a signature.** `Sphere`, `Cylinder` and `Box`
  override `to_json` on this branch and on no ancestor of `f4c15c243`, so git reported no
  conflict for them, and `ShapeCollection.to_json` — which hands its shapes the keyword
  arguments it was given — raised
  `TypeError: Box.to_json() got an unexpected keyword argument` for any shape of a body
  serialized with a `ReferenceWriter`. Migrated all three plus `Shape` itself.
- **Test written first**:
  `test_a_shape_is_serialized_where_its_frame_is_written_as_a_reference` in
  `test/semantic_digital_twin_test/test_adapters/test_json_parsing.py`. It fails on the
  merge without the migration with exactly that `TypeError`.
- **The roadmap's field-diff sweep was run and came back clean** — of the nine names
  `main` removed, every one is still defined there, so all nine were moves.
- **Measured** (python3.12 venv, `CRAM_ORM_BUILD=never`): `test_json_parsing.py` 41
  passed; `test/semantic_digital_twin_test` 1097 passed against 1082 on the pre-merge tip
  with the identical 41 failures; `test/krrood_test` 2952 passed with the same four
  failures the pre-merge tip has there.
- `mergeable_state` is `unstable` rather than `dirty` — the conflict is gone.
- Roadmap section, manifest `blockers`/`notes` and the PR description are all updated;
  #265 is still a draft.

## Next / outstanding

- **CI is running on `b5e2e2669` and nothing is armed to watch it** (standing rule). It
  is the first run this lineage has ever had: `db9561fa6` carried zero check runs and no
  commit status, so the `tracy_icra` merge, both earlier `main` merges and the #304 merge
  have never been exercised by CI. Read the run directly.
- The `needs-resolution` label clears itself on the next maintenance pass.
- Still open from before, untouched: `SimulationTimePacer.sleep()` is unbounded — what a
  stalled simulation should do is the developer's call.
- Writing the PR description through the GitHub MCP server escapes the backticks in the
  `## Promote` block, so each write grows the stray run of backticks around the link. The
  URL is intact; the block is the stack tooling's own.
