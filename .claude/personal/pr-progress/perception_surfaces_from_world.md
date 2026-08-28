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

## Done

- Branch cut off `montessori_perception_on_main`, pushed, draft PR #205 opened.
- `plan.yaml` records branch/session/PR and `status: in_progress`; roadmap
  section written.

## Next

1. Tests first, against `MontessoriWorld` (already carries a `Table`, a
   `Floor` and a `ShapeSortingBoard`): the derived region and both plane
   heights asserted against the world's own `TABLE_SCALE`/`TABLE_POSITION` and
   `BOARD_SCALE`/`BOARD_POSITION`, plus a test that `node.py` no longer
   imports either module.
2. Implement the surface derivation and rewire `build_node`.
3. Run `pytest test/experiments_test/test_montessori_perception.py` with
   `--noconftest` and the workspace on `PYTHONPATH` (the repo conftest
   regenerates the ORM interfaces, which needs a ROS 2 install the container
   lacks - it fails identically on unmodified `main`).
4. `scripts/format_docstrings.py` on every modified file.
5. Keep #205 a draft; update its description to match what landed.

## Held deliberately out of scope

- The pipeline keeps `region` / `table_height` / `board_height` as-is;
  restructuring it into one pass per surface is `detect-per-supporting-surface`.
- The region is the table, not a reachability envelope.

## Known, not a blocker

`supporting_surface` is `None` on every world in this workspace - nothing calls
`calculate_supporting_surface`. The fallback is the path that runs on the live
robot today; the annotated path is written because the item asks for it and
because the next item populates it.
