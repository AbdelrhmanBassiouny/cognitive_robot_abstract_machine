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

from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.geometry import SurfaceFinish

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

TUNED_WORKSPACE_FILE = (
    Path(__file__).parent.parent / "resources" / f"{SETUP_NAME}_workspace.json"
)
"""
Where the stretch of table tuned for this setup is kept.
"""


def searched_workspace(path: Path = TUNED_WORKSPACE_FILE) -> WorkspaceRegion:
    """
    The stretch of table a run over this setup's recordings searches.

    This is the widest a look may search rather than what it does search: the stretch
    of it the camera actually shows is measured every frame, and on these recordings
    that measurement reaches the same answer from :data:`WIDEST_WORKSPACE` as from a
    workspace already cut down by hand.

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
        finish=SurfaceFinish.MIRROR,
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


def perception_pipeline() -> MontessoriPerceptionPipeline:
    """
    :return: The pipeline that reads a recording of this setup.
    """
    return MontessoriPerceptionPipeline(table=table_surface(), lid=lid_surface())
