# `perception_surfaces_from_world` - PR #205 (draft)

Plan item `surfaces-from-world` of **knowledge-directed-perception**, wave
`grounding`, track `surfaces`. Stacked on `montessori_perception_on_main`
(#202, open and out of draft). Kicked off in `auto` mode 2026-08-28.

Full reasoning is in the plan's `roadmap.md` section
"`surfaces-from-world`: the plan, and what it deliberately leaves to the next
item". This note is the working state.

## The plan

Remove the two hand-written scene descriptions from `node.py` and read both
from the world it already fetches:

1. `TRACY_WORKSPACE` - the 1.0 x 1.2 m region guess (fault 1: the clip shows
   the floor).
2. `float(BOARD_SCALE.z)` - `build_node`'s lid offset, taken from the
   *simulated* scene's module constant.

`table_top_z(robot)` already picks the tabletop out of `robot.root.collision`
by largest `scale.x * scale.y` and keeps only the height; the bounds being
guessed at are the `scale.x`, `scale.y` and origin it discards.

Build one place that answers "which horizontal surface, where does it reach,
how high does it stand" as a single value, preferring
`HasSupportingSurface.supporting_surface` and falling back to the tabletop
collision shape. `build_node` reads the table and the board's lid from the
fetched world.

**Checkable outcome:** afterwards `node.py` imports neither
`experiments.montessori.world` nor `experiments.tracy_experiments.equipment` -
the two single-symbol couplings #202 had to drag onto `main`. Asserted, not
just observed.

## Done - the item is built and pushed

- Branch cut off `montessori_perception_on_main`; draft PR #205 opened.
- `plan.yaml` records branch/session/PR and `status: in_progress`; roadmap
  carries both the plan and the outcome section.
- `d8f30ffb` implements it: new `perception/surfaces.py` with
  `SupportingSurface.of` / `.of_body`, `MontessoriPerceptionPipeline.of_world`,
  `build_node` rewired, two new typed exceptions.
- 9 new tests. `137 passed, 1 skipped` across the four `test_montessori_*`
  modules vs `128 passed, 1 skipped` on the parent - no regressions.
- `scripts/format_docstrings.py` run; PR description rewritten to match.

## Outstanding, for the developer

1. **Open question raised on the PR, not decided here:** `of_body` picks the
   body's *widest* horizontal face, preserving `table_top_z`'s existing rule.
   The *highest* face is arguably truer to "the surface things rest on"; the
   two differ only for a body whose widest shape is not its top (a splayed
   base, or a mounting plate on the tabletop within the same body - plausibly
   why the original chose widest against the real URDF). Not overturned
   silently.
2. **`pipeline.py` still imports `BOARD_SCALE`** for
   `BoardDetector.board_footprint`, a detector tolerance rather than a plane.
   So the `world.py` coupling is narrowed, not deleted; `equipment.py`'s is
   gone outright. Left to `detect-per-supporting-surface`.
3. **Nothing verified against the live camera** - a container cannot. That the
   clip actually shows the table is `demo-runs-on-grounded-perception`'s job.
4. CI on #205 has not been read; per my notes this session does not watch it.

## Held deliberately out of scope

- The pipeline keeps `region` / `table_height` / `board_height` as-is;
  restructuring it into one pass per surface is `detect-per-supporting-surface`.
- The region is the table, not a reachability envelope.

## Behaviour change worth knowing

A fetched world carrying no `ShapeSortingBoard` is now refused
(`BoardMissingFromWorld`) rather than falling back to a constant: once the
constant is gone the lid's height cannot be invented.
`supporting_surface` is `None` on every world in this workspace, so the
body-shape fallback is the path that runs on the live robot today.
