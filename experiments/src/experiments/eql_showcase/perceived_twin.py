"""
A digital twin of what the camera saw: perceive, commit, then ask.

One look at the Montessori scene is committed into a world -- the table, the board's
lid, each hole cut into it and each piece found -- so that what the robot saw is asked
about with the same predicates and the same query language as anything it knows. A new
look replaces what the previous one committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Dict, List, Type

from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    MontessoriShapeDetection,
)
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.pieces import PieceSet
from experiments.montessori.semantics import MontessoriShape
from krrood.entity_query_language.utils import camel_case_to_words
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
    Region,
    SemanticAnnotation,
)

SHAPE_SUFFIX = " shape"
"""
The word every kind of piece's class name ends in, left out when a piece is named.
"""

TWIN_PREFIX = "seen"
"""
The prefix every entity committed from a look is named under.
"""

TABLE_THICKNESS = 0.04
"""
How thick the table top is drawn, in metres; the camera sees only its upper face.
"""

HOLE_DEPTH = 0.03
"""
How far below the lid a hole's region reaches, in metres, so a piece standing in a hole
lies inside it as well as one resting on top of it.
"""

HOLE_HEADROOM = 0.02
"""
How far above the lid a hole's region reaches, in metres, so a piece resting over a hole
lies inside it.
"""

BOARD_COLOR = Color(0.62, 0.45, 0.3)
"""
The colour the board is drawn in.
"""

TABLE_COLOR = Color(0.75, 0.76, 0.78)
"""
The colour the steel table is drawn in.
"""

HOLE_COLOR = Color(0.08, 0.08, 0.08, 0.85)
"""
The colour a hole's region is drawn in.
"""

UNKNOWN_PIECE_COLOR = Color(0.6, 0.6, 0.6)
"""
The colour of a kind of piece the full-size set has no measured colour for.
"""

# %% the colour a piece is drawn in


def piece_colors() -> Dict[Type[MontessoriShape], Color]:
    """
    The colour measured off the real piece of each kind the full-size set contains.
    """
    return {
        type(piece): PieceSet.color_of(piece) for piece in PieceSet.full_size().pieces
    }


# %% the twin


@dataclass
class PerceivedTwin:
    """
    A world holding what one look at the Montessori scene saw, on the table it was seen
    on.
    """

    region: WorkspaceRegion
    """
    The stretch of table the camera looks over.
    """

    table_height: float
    """
    Height of the table top, in metres.
    """

    world: World = field(default_factory=World)
    """
    The world the look is committed into.
    """

    root: Body = field(init=False)
    """
    The frame every look is placed in, which the camera's poses are measured in.
    """

    table: Body = field(init=False)
    """
    The table the scene is set up on.
    """

    committed: List[KinematicStructureEntity] = field(init=False, default_factory=list)
    """
    What the current look committed, removed again when the next look is committed.
    """

    colors: Dict[Type[MontessoriShape], Color] = field(default_factory=piece_colors)
    """
    The colour each kind of piece is drawn in.
    """

    def __post_init__(self) -> None:
        width = self.region.maximum_x - self.region.minimum_x
        depth = self.region.maximum_y - self.region.minimum_y
        with self.world.modify_world():
            self.root = Body(name=self._name("map"))
            self.world.add_kinematic_structure_entity(self.root)
            self.table = self._place_body(
                "table",
                Box(scale=Scale(width, depth, TABLE_THICKNESS), color=TABLE_COLOR),
                HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=self.region.minimum_x + width / 2,
                    y=self.region.minimum_y + depth / 2,
                    z=self.table_height - TABLE_THICKNESS / 2,
                ),
            )
            self.world.add_semantic_annotation(
                Table(name=self.table.name, root=self.table)
            )

    # %% committing a look

    def commit(self, scene: MontessoriScene) -> None:
        """
        Replace whatever the previous look committed with what this one saw.

        :param scene: The look to commit.
        """
        with self.world.modify_world():
            self._remove_committed()
            if scene.board is not None:
                self._commit_board(scene.board)
            for index, piece in enumerate(scene.shapes):
                self._commit_piece(piece, index)

    def _commit_board(self, board: MontessoriBoardDetection) -> None:
        """
        Add the board's lid and a region for each of its holes.

        :param board: The board the look found.
        """
        height = board.lid_height - self.table_height
        lid = self._place_body(
            "board",
            Box(
                scale=Scale(board.footprint.width, board.footprint.length, height),
                color=BOARD_COLOR,
            ),
            self._resting_on(board, self.table_height + height / 2),
        )
        self.committed.append(lid)
        for index, hole in enumerate(board.holes):
            region = Region(
                name=self._name(f"{self.kind_of(hole.category)} hole {index + 1}"),
                area=ShapeCollection(
                    [
                        Box(
                            scale=Scale(
                                hole.footprint.width,
                                hole.footprint.length,
                                HOLE_DEPTH + HOLE_HEADROOM,
                            ),
                            color=HOLE_COLOR,
                        )
                    ]
                ),
            )
            self._attach(
                region,
                self._resting_on(
                    hole, board.lid_height + (HOLE_HEADROOM - HOLE_DEPTH) / 2
                ),
            )
            self.committed.append(region)

    def _commit_piece(self, piece: MontessoriShapeDetection, index: int) -> None:
        """
        Add one piece, named and annotated as the kind of piece it was recognised as.

        :param piece: The piece the look found.
        :param index: Its position among the pieces of the look, to tell pieces of the
            same kind apart.
        """
        body = self._place_body(
            f"{self.kind_of(piece.category)} {index + 1}",
            Box(
                scale=Scale(
                    piece.footprint.width, piece.footprint.length, piece.height
                ),
                color=self.colors.get(piece.category, UNKNOWN_PIECE_COLOR),
            ),
            self._resting_on(piece, piece.surface_height + piece.height / 2),
        )
        self.committed.append(body)
        self.world.add_semantic_annotation(piece.category(name=body.name, root=body))

    # %% placing entities

    def _place_body(
        self, name: str, box: Box, pose: HomogeneousTransformationMatrix
    ) -> Body:
        """
        Add a body of one box, fixed to the map frame.

        :param name: The body's name, under :data:`TWIN_PREFIX`.
        :param box: Its geometry, both seen and collided with.
        :param pose: Where it stands, in the map frame.
        """
        body = Body.from_shape_collection(self._name(name), ShapeCollection([box]))
        self._attach(body, pose)
        return body

    def _attach(
        self, entity: KinematicStructureEntity, pose: HomogeneousTransformationMatrix
    ) -> None:
        """
        Add an entity to the world, fixed to the map frame at a pose.

        :param entity: The body or region to add.
        :param pose: Where it stands, in the map frame.
        """
        self.world.add_kinematic_structure_entity(entity)
        self.world.add_connection(
            FixedConnection(
                parent=self.root,
                child=entity,
                parent_T_connection_expression=pose,
            )
        )

    def _remove_committed(self) -> None:
        """
        Remove everything the previous look committed, with the annotations naming it.
        """
        committed = set(self.committed)
        for annotation in list(self.world.semantic_annotations):
            if self._annotates_one_of(annotation, committed):
                self.world.remove_semantic_annotation(annotation)
        for entity in self.committed:
            self.world.remove_connection(entity.parent_connection)
            self.world.remove_kinematic_structure_entity(entity)
        self.committed.clear()

    @staticmethod
    def _annotates_one_of(
        annotation: SemanticAnnotation, entities: set[KinematicStructureEntity]
    ) -> bool:
        """
        Whether an annotation names one of the given entities.

        :param annotation: The annotation to check.
        :param entities: The entities committed by the previous look.
        """
        return isinstance(annotation, MontessoriShape) and annotation.root in entities

    def _resting_on(
        self, detection: MontessoriDetection, height: float
    ) -> HomogeneousTransformationMatrix:
        """
        Where a detection stands, turned the way its footprint lies: a footprint's
        length runs across its yaw, its width along it.

        :param detection: The detection to place.
        :param height: Height of its centre, in metres.
        """
        x, y = detection.pose.position.to_np()[:2]
        return HomogeneousTransformationMatrix.from_xyz_rpy(
            x=float(x), y=float(y), z=height, yaw=detection.footprint.yaw
        )

    @staticmethod
    def kind_of(category: Type[MontessoriShape]) -> str:
        """
        The kind of piece a category is, as it is said, e.g. ``"triangular prism"``.

        :param category: The kind of piece.
        """
        return camel_case_to_words(category.__name__).removesuffix(SHAPE_SUFFIX)

    @staticmethod
    def _name(name: str) -> PrefixedName:
        """
        A name for an entity committed from a look.

        :param name: The entity's own name.
        """
        return PrefixedName(name, TWIN_PREFIX)
