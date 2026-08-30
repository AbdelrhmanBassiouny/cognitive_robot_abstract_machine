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

from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

SETUP_NAME = "tracy"
"""
Prefix naming the physical setup these surfaces were measured on.
"""

REFERENCE_FRAME = "map"
"""
Frame the recordings root their transform tree in, and so the frame detections made on
them come out in.
"""

TABLE_HEIGHT = 0.88
"""
Height of Tracy's own table top above the reference frame, in metres.

Read off the ``map`` to ``table`` transform the robot publishes into every recording.
"""

WORKSPACE = WorkspaceRegion(
    minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
)
"""
The stretch of that table the scene stands on, as the demo searched it.
"""


def table_surface() -> WorkspaceSurface:
    """
    :return: The bare steel table the scene is set up on.
    """
    return WorkspaceSurface(
        name=PrefixedName("table", SETUP_NAME),
        region=WORKSPACE,
        height=TABLE_HEIGHT,
    )


def lid_surface() -> WorkspaceSurface:
    """
    :return: The board's lid, the second surface pieces rest on.
    """
    return WorkspaceSurface(
        name=PrefixedName("board_lid", SETUP_NAME),
        region=WORKSPACE,
        height=TABLE_HEIGHT + float(BOARD_SCALE.z),
    )


def perception_pipeline() -> MontessoriPerceptionPipeline:
    """
    :return: The pipeline that reads a recording of this setup.
    """
    return MontessoriPerceptionPipeline(table=table_surface(), lid=lid_surface())
