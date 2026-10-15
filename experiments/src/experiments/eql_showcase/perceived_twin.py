"""
A digital twin of what the camera saw: perceive, commit, then ask.

One look at the Montessori scene is committed into a world -- the table, the board's
lid, each hole cut into it and each piece found -- so that what the robot saw is asked
about with the same predicates and the same query language as anything it knows. A new
look replaces what the previous one committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from typing_extensions import Dict, List, Type

from experiments.montessori.hole_geometry import HoleFootprint
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.pieces import PieceSet
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import _BOARD_MESH, _HOLE_FOOTPRINTS, _board_body
from krrood.entity_query_language.utils import camel_case_to_words
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.grasping.grasp_candidates import HasGraspCandidates
from semantic_digital_twin.robots.robot_parts import MountingTable
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Color, Mesh, Scale
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

HOLE_HEADROOM = 0.005
"""
How far above the lid a hole's region reaches, in metres, so a piece sunk into a hole
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

HOLE_COLOR = Color(0.05, 0.05, 0.05, 0.6)
"""
The colour a hole's region is drawn in.
"""

UNKNOWN_PIECE_COLOR = Color(0.6, 0.6, 0.6)
"""
The colour of a kind of piece the full-size set has no measured colour for.
"""

# %% a seen piece the robot can take hold of


@dataclass(eq=False)
class SeenPiece(HasGraspCandidates):
    """
    A piece the camera saw, as something the robot can grasp.

    It names the same body as the annotation of the piece's kind, which says what the
    piece is; this one says how to take hold of it.
    """

    kind: Type[MontessoriShape] = field(kw_only=True)
    """
    The kind of piece it was recognised as.
    """


@dataclass(frozen=True)
class SeenHole:
    """
    A hole the camera saw in the board's lid, and the kind of piece it is cut for.
    """

    region: Region
    """
    The region of the twin the hole is.
    """

    kind: Type[MontessoriShape]
    """
    The kind of piece the hole was recognised as cut for.
    """

    lid_height: float
    """
    Height of the lid the hole is cut into, in metres.
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

    world: World
    """
    The world the look is committed into.
    """

    root: KinematicStructureEntity
    """
    The frame every look is placed in, which the camera's poses are measured in.
    """

    table: Body
    """
    The table the scene is set up on.
    """

    table_height: float
    """
    Height of the table top in the frame looks are placed in, in metres.
    """

    holes: List[SeenHole] = field(init=False, default_factory=list)
    """
    The holes the current look saw.
    """

    committed: List[KinematicStructureEntity] = field(init=False, default_factory=list)
    """
    What the current look committed, removed again when the next look is committed.
    """

    sightings: Dict[SeenPiece, MontessoriShapeDetection] = field(
        init=False, default_factory=dict
    )
    """
    What the current look saw each piece as.
    """

    colors: Dict[Type[MontessoriShape], Color] = field(default_factory=piece_colors)
    """
    The colour each kind of piece is drawn in.
    """

    @classmethod
    def beside_tracy(cls) -> PerceivedTwin:
        """
        A twin of Tracy, whose own table the camera looks at.

        Tracy's description places its table top in the frame the camera's poses are
        measured in, so what is seen lands on it as it lay on the real table.
        """
        world = URDFParser.from_file(file_path=Tracy.get_ros_file_path()).parse()
        Tracy.from_world(world)
        [table] = world.get_semantic_annotations_by_type(MountingTable)
        return cls(
            world=world,
            root=world.root,
            table=table.root,
            table_height=float(table.root.global_pose.position.to_np()[2]),
        )

    @classmethod
    def on_bare_table(
        cls, region: WorkspaceRegion, table_height: float
    ) -> PerceivedTwin:
        """
        A twin of nothing but the stretch of table the camera looks over.

        :param region: The stretch of table the camera looks over.
        :param table_height: Height of the table top, in metres.
        """
        world = World()
        width = region.maximum_x - region.minimum_x
        depth = region.maximum_y - region.minimum_y
        with world.modify_world():
            root = Body(name=cls._name("map"))
            world.add_kinematic_structure_entity(root)
            table = Body.from_shape_collection(
                cls._name("table"),
                ShapeCollection(
                    [Box(scale=Scale(width, depth, TABLE_THICKNESS), color=TABLE_COLOR)]
                ),
            )
            world.add_kinematic_structure_entity(table)
            world.add_connection(
                FixedConnection(
                    parent=root,
                    child=table,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=region.minimum_x + width / 2,
                        y=region.minimum_y + depth / 2,
                        z=table_height - TABLE_THICKNESS / 2,
                    ),
                )
            )
            world.add_semantic_annotation(Table(name=table.name, root=table))
        return cls(world=world, root=root, table=table, table_height=table_height)

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
        Add the board, drawn from its model with the holes cut through it, where the
        look found it, and a region for each hole the look saw.

        A hole the look saw is placed where the board's model has its hole of that
        kind: the camera finds the board's pose well, but a hole's outline too coarsely
        to put a piece through it.

        :param board: The board the look found.
        """
        height = board.lid_height - self.table_height
        board_pose = self._resting_on(board, self.table_height + height / 2)
        shape = Mesh.from_trimesh(mesh=_BOARD_MESH)
        shape.color = BOARD_COLOR
        body = _board_body(self._name("board"), shape, _HOLE_FOOTPRINTS)
        self._attach(body, board_pose)
        self.committed.append(body)
        for index, hole in enumerate(board.holes):
            footprint = self._model_hole_for(board, hole)
            outline = footprint.boundary.bounding_box
            center_x, center_y = footprint.center.to_np()[:2]
            region = Region(
                name=self._name(f"{self.kind_of(hole.category)} hole {index + 1}"),
                area=ShapeCollection(
                    [
                        Box(
                            scale=Scale(
                                outline.max_x - outline.min_x,
                                outline.max_y - outline.min_y,
                                HOLE_DEPTH + HOLE_HEADROOM,
                            ),
                            color=HOLE_COLOR,
                        )
                    ]
                ),
            )
            self._attach(
                region,
                board_pose
                @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=float(center_x + (outline.min_x + outline.max_x) / 2),
                    y=float(center_y + (outline.min_y + outline.max_y) / 2),
                    z=height / 2 + (HOLE_HEADROOM - HOLE_DEPTH) / 2,
                ),
            )
            self.committed.append(region)
            self.holes.append(SeenHole(region, hole.category, board.lid_height))

    @staticmethod
    def _model_hole_for(
        board: MontessoriBoardDetection, hole: ShapeSortingHoleDetection
    ) -> HoleFootprint:
        """
        The hole of the board's model that a hole the look saw is.

        :param board: The board the look found.
        :param hole: A hole the look saw in it.
        :return: The model's hole of the same kind nearest to where the hole was seen.
        """
        offset = hole.pose.position.to_np()[:2] - board.pose.position.to_np()[:2]
        cosine, sine = np.cos(board.footprint.yaw), np.sin(board.footprint.yaw)
        seen_at = np.array(
            [
                cosine * offset[0] + sine * offset[1],
                -sine * offset[0] + cosine * offset[1],
            ]
        )
        return min(
            (
                footprint
                for footprint in _HOLE_FOOTPRINTS
                if footprint.category is hole.category
            ),
            key=lambda footprint: np.linalg.norm(
                footprint.center.to_np()[:2] - seen_at
            ),
        )

    def _commit_piece(self, piece: MontessoriShapeDetection, index: int) -> None:
        """
        Add one piece, named and annotated as the kind of piece it was recognised as.

        :param piece: The piece the look found.
        :param index: Its position among the pieces of the look, to tell pieces of the
            same kind apart.
        """
        body = Body.from_shape_collection(
            self._name(f"{self.kind_of(piece.category)} {index + 1}"),
            ShapeCollection(
                [
                    Box(
                        scale=Scale(
                            piece.footprint.width, piece.footprint.length, piece.height
                        ),
                        color=self.colors.get(piece.category, UNKNOWN_PIECE_COLOR),
                    )
                ]
            ),
        )
        self.world.add_kinematic_structure_entity(body)
        # a piece is free to be picked up, so it hangs on its own six degrees of freedom
        connection = Connection6DoF.create_with_dofs(
            world=self.world, parent=self.root, child=body
        )
        self.world.add_connection(connection)
        connection.origin = self._resting_on(
            piece, piece.surface_height + piece.height / 2
        )
        self.committed.append(body)
        self.world.add_semantic_annotation(piece.category(name=body.name, root=body))
        seen = SeenPiece(name=body.name, root=body, kind=piece.category)
        self.world.add_semantic_annotation(seen)
        self.sightings[seen] = piece

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
        self.holes.clear()
        self.sightings.clear()
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
        return (
            isinstance(annotation, (MontessoriShape, SeenPiece))
            and annotation.root in entities
        )

    def _resting_on(
        self, detection: MontessoriDetection, height: float
    ) -> HomogeneousTransformationMatrix:
        """
        Where a detection stands in the map frame, turned the way its footprint lies: a
        footprint's length runs across its yaw, its width along it.

        :param detection: The detection to place.
        :param height: Height of its centre, in metres.
        """
        x, y = detection.pose.position.to_np()[:2]
        return HomogeneousTransformationMatrix.from_xyz_rpy(
            x=float(x),
            y=float(y),
            z=height,
            yaw=detection.footprint.yaw,
            reference_frame=self.root,
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
