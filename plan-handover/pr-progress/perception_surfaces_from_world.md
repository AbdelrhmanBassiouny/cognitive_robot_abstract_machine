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
