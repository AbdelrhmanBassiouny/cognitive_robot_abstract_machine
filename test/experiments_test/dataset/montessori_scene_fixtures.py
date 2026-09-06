"""
The rendered Montessori scene, and the pipeline that reads it, shared by every test
module that needs detections rather than one component in isolation.
"""

from __future__ import annotations

import pytest

from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

from .montessori_scene_renderer import MontessoriSceneRenderer, PlacedPiece


@pytest.fixture
def renderer() -> MontessoriSceneRenderer:
    return MontessoriSceneRenderer()


@pytest.fixture
def placed_pieces() -> list[PlacedPiece]:
    return [
        PlacedPiece(MontessoriShapeCategory.CUBE, x=0.58, y=0.15),
        PlacedPiece(MontessoriShapeCategory.CYLINDER, x=0.58, y=0.25),
        PlacedPiece(MontessoriShapeCategory.TRIANGULAR_PRISM, x=0.58, y=0.35),
    ]


SCENE_REGION = WorkspaceRegion(
    minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
)
"""
The stretch of table the rendered scene is set up on.
"""


@pytest.fixture
def pipeline(renderer: MontessoriSceneRenderer) -> MontessoriPerceptionPipeline:
    return MontessoriPerceptionPipeline(
        table=WorkspaceSurface(
            entity=Body(name=PrefixedName("table", "montessori_scene")),
            region=SCENE_REGION,
            height=renderer.table_height,
        ),
        lid=WorkspaceSurface(
            entity=Body(name=PrefixedName("board_lid", "montessori_scene")),
            region=SCENE_REGION,
            height=renderer.lid_height,
        ),
    )


@pytest.fixture
def scene(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
) -> MontessoriScene:
    return pipeline.detect(renderer.render(placed_pieces))


@pytest.fixture
def piece_on_the_lid(renderer: MontessoriSceneRenderer) -> PlacedPiece:
    """
    A cube standing on the board's lid, clear of the holes cut through it.
    """
    x, y = renderer.clear_lid_position()
    return PlacedPiece(
        MontessoriShapeCategory.CUBE, x=x, y=y, surface_height=renderer.lid_height
    )


@pytest.fixture
def scene_with_a_piece_on_the_lid(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
) -> MontessoriScene:
    return pipeline.detect(renderer.render([*placed_pieces, piece_on_the_lid]))
