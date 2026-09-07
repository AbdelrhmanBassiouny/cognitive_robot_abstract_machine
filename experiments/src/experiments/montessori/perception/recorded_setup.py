"""
The Montessori setup the shipped captures and the recordings they come from were made
on.

Perception reads which stretch of table to search, and how high each surface lies, from
the world the robot publishes -- see
:meth:`~experiments.montessori.perception.pipeline.MontessoriPerceptionPipeline.of_world`.
A recording carries no world, so the two surfaces it was taken over are written down
here, measured off the transform tree those same recordings publish. Nothing that runs
against the live robot reads this.
"""

from __future__ import annotations

from pathlib import Path

from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import (
    BoardDetector,
    MontessoriPerceptionPipeline,
)
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

SETUP_NAME = "tracy"
"""
Prefix naming the physical setup these surfaces were measured on.
"""

TABLE_HEIGHT = 0.88
"""
Height of Tracy's own table top above the reference frame, in metres.

Read off the ``map`` to ``table`` transform the robot publishes into every recording.
"""

WIDEST_WORKSPACE = WorkspaceRegion(
    minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
)
"""
The whole stretch of that table the camera looks over, and the widest a run may search.

A workspace tuned for this setup is cut out of this one, so an edge brought in by
:mod:`~experiments.montessori.perception.tune_workspace` can always be pushed back out
to where it started.
"""

BOARD_SCALE_AGAINST_THE_MESH = 0.865
"""
How large the shape-sorting board on this table is, against ``resources/board.stl``.

The mesh is not cut to the size of the board these recordings hold: laid over the lid at
its own size, its holes miss the openings actually seen by about nineteen millimetres,
and no plane the board could be rectified onto brings them together. Fitted at this size
they land two to three millimetres from them, which is what
:meth:`~experiments.montessori.perception.pipeline.BoardDetector.measure_scale` answers
on each of the six shipped captures -- 0.82, 0.84, 0.86, 0.87, 0.90 and 0.92, whose
middle this is. Measuring the board itself would settle it more tightly than six looks
from one angle can.

Stated here rather than on the detector because it is knowledge about a particular
board, not about how a board is looked for: a scene built from the mesh is the mesh's
own size, and reads one.
"""

TUNED_WORKSPACE_FILE = (
    Path(__file__).parent.parent / "resources" / f"{SETUP_NAME}_workspace.json"
)
"""
Where the stretch of table tuned for this setup is kept.
"""


def searched_workspace(path: Path = TUNED_WORKSPACE_FILE) -> WorkspaceRegion:
    """
    The stretch of table a run over this setup's recordings searches.

    :param path: The file a tuned workspace was written to.
    :return: That workspace, or the whole of :data:`WIDEST_WORKSPACE` where none has
        been tuned.
    """
    if not path.is_file():
        return WIDEST_WORKSPACE
    return WorkspaceRegion.load(path)


def table_surface() -> WorkspaceSurface:
    """
    :return: The bare steel table the scene is set up on.
    """
    return WorkspaceSurface(
        name=PrefixedName("table", SETUP_NAME),
        region=searched_workspace(),
        height=TABLE_HEIGHT,
    )


def lid_surface() -> WorkspaceSurface:
    """
    :return: The board's lid, the second surface pieces rest on.
    """
    return WorkspaceSurface(
        name=PrefixedName("board_lid", SETUP_NAME),
        region=searched_workspace(),
        height=TABLE_HEIGHT + float(BOARD_SCALE.z),
    )


def board_detector() -> BoardDetector:
    """
    :return: The detector that looks for the board this setup holds, at the size that
        board was measured to be.
    """
    return BoardDetector(
        layout=BoardHoleLayout.of_board_mesh(BOARD_SCALE_AGAINST_THE_MESH)
    )


def perception_pipeline() -> MontessoriPerceptionPipeline:
    """
    :return: The pipeline that reads a recording of this setup.
    """
    return MontessoriPerceptionPipeline(
        table=table_surface(), lid=lid_surface(), board_detector=board_detector()
    )
