"""
Tests for answering a statement about the Montessori scene by looking at it: what the
statement tells the search, what is left to be checked over what came back, and what a
look refuses to answer at all.
"""

from __future__ import annotations

import pytest

from experiments.montessori.perception.backend import (
    MontessoriPerceptionBackend,
)
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    DetectedMontessoriShape,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import FixedScene, RecordedFrame
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.montessori.perception.exceptions import SightingHasNoBody
from krrood.entity_query_language.factories import an
from krrood.entity_query_language.exceptions import BackendCannotResolveCondition
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from semantic_digital_twin.reasoning.predicates import (
    Between,
    Colored,
    InContactWith,
    InsideRegion,
    Near,
    PlacementRelation,
    RightOf,
    SupportedBy,
    Turned,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body
from krrood.entity_query_language.factories import a, entity, variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.vocabulary.english import Directive

from .dataset import montessori_scene_fixtures
from .dataset.montessori_scene_renderer import MontessoriSceneRenderer, PlacedPiece

pytest_plugins = [montessori_scene_fixtures.__name__]
"""
The rendered scene and pipeline fixtures the tests below ask for by name.
"""


def looking_for_something_supported_by(surface: WorkspaceSurface):
    """
    A statement asking a look for whatever rests on a surface, said as a relation.

    The statement names the world entity, since that is what support is a relation
    between, and a measured surface carries the very entity it was measured of.

    :param surface: The measured surface whose world entity is asked about.
    """
    statement = a(DetectedMontessoriShape)()
    return statement.where(SupportedBy(statement.variable, surface.entity))


@pytest.fixture
def looking(scene: MontessoriScene) -> MontessoriPerceptionBackend:
    """
    A backend answering from one already-captured look at the rendered scene.
    """
    return MontessoriPerceptionBackend(source=FixedScene(captured=scene))


# %% what the statement tells the search


def test_what_the_search_narrows_by_is_a_relation_rather_than_an_attributes_name():
    """
    Support is a relation the world means something by, so the search is narrowed by the
    class that means it and there is no attribute name spelled a second time.
    """
    assert SupportedBy in MontessoriPerceptionBackend.narrowing_relations


def test_a_search_narrows_itself_by_where_a_statement_says_the_thing_lies():
    """
    Every relation that says where a thing may be answers the stretch it leaves, so a
    look stating one can cut its picture down to that before anything is detected --
    whatever the relation happens to be.
    """
    assert PlacementRelation in MontessoriPerceptionBackend.narrowing_relations
    assert issubclass(InsideRegion, PlacementRelation)


@pytest.mark.parametrize("relation", [RightOf, Between, Near])
def test_a_search_narrows_itself_by_any_relation_that_says_where_a_thing_lies(relation):
    """
    Naming the family rather than its members is what lets the vocabulary grow without
    the backend being edited for each new way of saying where something is.
    """
    assert issubclass(relation, PlacementRelation)
    assert issubclass(relation, MontessoriPerceptionBackend.narrowing_relations)


def test_a_search_narrows_itself_by_the_color_the_thing_sought_wears():
    """
    What colour a piece is, is knowledge about the piece, so a look asked for one marks
    that colour alone instead of every colour a piece of this set can wear.
    """
    assert Colored in MontessoriPerceptionBackend.narrowing_relations


def test_a_stated_color_is_what_the_look_is_asked_to_mark():
    color = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE].color
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(Colored(statement.variable, color))

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    assert request.color == color


def test_a_stated_placement_reaches_the_look_as_the_relation_that_says_it(
    pipeline: MontessoriPerceptionPipeline,
):
    """
    The relation itself rather than a patch in metres: what it allows is read where the
    frame the detections are reported in is known, which is the look.
    """
    lid = pipeline.lid.entity
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(Near(statement.variable, lid, radius=0.05))

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    [placement] = request.placements
    assert isinstance(placement, Near)
    assert placement.place is lid
    assert placement.radius == 0.05


def test_a_stated_turn_reaches_the_look_as_the_relation_that_says_it():
    """
    Which way round to lay a piece is something the look can act on, so it is read off
    the statement like a placement is.
    """
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(Turned(statement.variable, yaw=0.3, spread=0.1))

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    assert isinstance(request.turn, Turned)
    assert request.turn.body is None
    assert (request.turn.yaw, request.turn.spread) == (0.3, 0.1)


def test_a_stated_turn_is_checked_over_what_came_back(
    scene: MontessoriScene, looking: MontessoriPerceptionBackend
):
    """
    A look already taken laid its pieces whichever way it did, so a stated turn is
    checked over what it reported.
    """

    def turned_to(yaw: float):
        statement = a(DetectedMontessoriShape)()
        return statement.where(Turned(statement.variable, yaw=yaw, spread=0.05))

    as_laid = list(turned_to(0.0).evaluate(backend=looking))
    a_turn_away = list(turned_to(1.0).evaluate(backend=looking))

    assert len(as_laid) == len(scene.shapes)
    assert a_turn_away == []


def test_a_relation_the_look_cannot_establish_is_asked_of_the_sightings_body(
    scene: MontessoriScene,
):
    """
    Contact is read off two bodies, so asked of a piece it is asked of the body the look
    stood in its world for that piece.
    """
    seen, another = scene.shapes[:2]
    stated = an(InContactWith)(body2=another.role_taker.root)

    [contradicted] = MontessoriPerceptionBackend.contradicted_by(seen, [stated])

    assert isinstance(contradicted, InContactWith)
    assert contradicted.subject is seen.role_taker.root


def test_a_relation_the_look_cannot_establish_needs_a_body_to_be_asked_of(
    scene: MontessoriScene,
):
    """
    The board is a sighting no body stands for, so a relation read off bodies cannot be
    asked of it, and says so rather than answering.
    """
    stated = an(InContactWith)(body2=Body(name=PrefixedName("table")))

    with pytest.raises(SightingHasNoBody):
        MontessoriPerceptionBackend.contradicted_by(scene.board, [stated])


def test_the_kind_of_detection_asked_for_is_what_the_look_is_asked_for():
    statement = a(DetectedMontessoriShape)()

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    assert request == SceneRequest(detection_type=DetectedMontessoriShape)


def test_a_stated_supporting_surface_narrows_the_look_to_it(
    pipeline: MontessoriPerceptionPipeline,
):
    statement = looking_for_something_supported_by(pipeline.lid)

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    assert request.detection_type is DetectedMontessoriShape
    assert request.supporting_surface.name == pipeline.lid.name


def test_an_attribute_the_look_cannot_act_on_leaves_it_searching_everywhere():
    statement = a(DetectedMontessoriShape)(category=MontessoriShapeCategory.CUBE)

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    assert request.supporting_surface is None


def test_a_surface_left_unstated_narrows_nothing(
    pipeline: MontessoriPerceptionPipeline,
):
    """
    Asserting no support says the statement does not know which surface and the look
    must report it, which is the opposite of naming one.
    """
    statement = a(DetectedMontessoriShape)(supporting_surface=...)

    request = MontessoriPerceptionBackend.scene_request(
        MontessoriPerceptionBackend.read_request(statement)
    )

    assert request.supporting_surface is None


def surfaces_of(pipeline: MontessoriPerceptionPipeline):
    """
    The bodies a statement can pick a surface out of by describing it.

    :param pipeline: The pipeline whose surfaces they stand for.
    """
    return [pipeline.table.entity, pipeline.lid.entity]


def test_a_surface_the_statement_describes_is_read_as_the_one_it_describes(
    pipeline: MontessoriPerceptionPipeline,
):
    """
    A statement can say which surface it means by describing it -- the body the world
    calls the lid -- rather than by handing that body over.

    The description is answered out of the world it was given before any look is taken,
    so what the relation says is a relation to something concrete and narrows the search
    like any other.
    """
    surface = variable(Body, surfaces_of(pipeline))
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(
        surface.name == pipeline.lid.name,
        SupportedBy(statement.variable, surface),
    )

    request = MontessoriPerceptionBackend.read_request(statement)

    assert (
        MontessoriPerceptionBackend.supporting_surface_asked_about(request).name
        == pipeline.lid.name
    )


def test_a_described_surface_is_answered_the_same_as_one_handed_over(
    pipeline: MontessoriPerceptionPipeline, looking: MontessoriPerceptionBackend
):
    surface = variable(Body, surfaces_of(pipeline))
    described = a(DetectedMontessoriShape)()
    described = described.where(
        surface.name == pipeline.lid.name,
        SupportedBy(described.variable, surface),
    )

    found = list(described.evaluate(backend=looking))

    assert found == list(
        looking_for_something_supported_by(pipeline.lid).evaluate(backend=looking)
    )


def test_a_description_no_single_thing_answers_is_refused_rather_than_guessed_at(
    pipeline: MontessoriPerceptionPipeline, looking: MontessoriPerceptionBackend
):
    """
    Which surface a look searches has to be settled before it is taken, so a description
    several surfaces answer is a condition this backend cannot resolve rather than one
    of them picked.
    """
    surface = variable(Body, surfaces_of(pipeline))
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(
        surface.name.prefix == pipeline.lid.name.prefix,
        SupportedBy(statement.variable, surface),
    )

    with pytest.raises(BackendCannotResolveCondition) as raised:
        list(statement.evaluate(backend=looking))

    assert raised.value.backend_type is MontessoriPerceptionBackend


def test_a_condition_about_something_other_than_what_is_looked_for_is_refused(
    looking: MontessoriPerceptionBackend,
):
    hole = variable(ShapeSortingHoleDetection, [])
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(hole.category == MontessoriShapeCategory.CUBE)

    with pytest.raises(BackendCannotResolveCondition) as raised:
        list(statement.evaluate(backend=looking))

    assert raised.value.backend_type is MontessoriPerceptionBackend


# %% what the look then does


def test_only_the_surface_asked_about_is_searched(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    request = SceneRequest(supporting_surface=pipeline.lid.entity)

    searches = pipeline.searched_surfaces(scene.board, request)

    assert [search.surface for search in searches] == [pipeline.lid]


def test_a_surface_that_only_shares_a_name_is_not_the_one_asked_about(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    """
    A statement names a thing of the world, and the world tells its things apart by
    which one they are rather than by what they are called, so a look asked about a body
    that merely carries the lid's name is asked about no surface this pipeline measured.
    """
    request = SceneRequest(supporting_surface=Body(name=pipeline.lid.name))

    searches = pipeline.searched_surfaces(scene.board, request)

    assert searches == []


def test_every_surface_is_searched_when_the_request_names_none(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    searches = pipeline.searched_surfaces(scene.board, SceneRequest())

    assert [search.surface for search in searches] == [pipeline.table, pipeline.lid]


def test_no_piece_is_looked_for_when_only_the_board_was_asked_about(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
):
    frame = renderer.render(placed_pieces)

    asked_about_the_board = pipeline.detect(
        frame, SceneRequest(detection_type=MontessoriBoardDetection)
    )

    assert asked_about_the_board.shapes == []
    assert asked_about_the_board.board is not None


def test_a_look_narrowed_to_one_surface_reports_only_what_rests_on_it(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
    scene_with_a_piece_on_the_lid: MontessoriScene,
):
    """
    Narrowing is the search itself running differently, not a filter over a full look:

    the table's pieces are never detected, rather than detected and discarded.
    """
    frame = renderer.render([*placed_pieces, piece_on_the_lid])

    asked_about_the_lid = pipeline.detect(
        frame, SceneRequest(supporting_surface=pipeline.lid.entity)
    )

    assert [found.supporting_surface for found in asked_about_the_lid.shapes] == [
        pipeline.lid.name
    ]
    assert len(scene_with_a_piece_on_the_lid.shapes) > len(asked_about_the_lid.shapes)


def test_a_look_asked_for_everything_still_finds_the_pieces(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    scene: MontessoriScene,
):
    frame = renderer.render(placed_pieces)

    asked_for_everything = pipeline.detect(frame, SceneRequest())

    assert len(asked_for_everything.shapes) == len(scene.shapes)


# %% answering a statement


def test_a_statement_runs_perception_to_answer_itself(scene: MontessoriScene):
    class CountingSource(FixedScene):
        looks: int = 0

        def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
            self.looks += 1
            return self.captured

    source = CountingSource(captured=scene)
    statement = a(DetectedMontessoriShape)()

    assert source.looks == 0
    results = list(
        statement.evaluate(backend=MontessoriPerceptionBackend(source=source))
    )
    assert source.looks == 1
    assert len(results) == len(scene.shapes)


def test_a_statement_selects_a_hole_by_the_shape_it_takes(
    looking: MontessoriPerceptionBackend, scene: MontessoriScene
):
    statement = a(ShapeSortingHoleDetection)(category=MontessoriShapeCategory.CUBE)

    holes = list(statement.evaluate(backend=looking))

    assert holes == [
        found for found in scene.holes if found.category is MontessoriShapeCategory.CUBE
    ]


def test_a_pose_left_unstated_is_what_the_look_answers_with(
    looking: MontessoriPerceptionBackend, scene: MontessoriScene
):
    """
    The shape of the question a plan actually asks: the robot knows the hole is there
    and asks perception only where it is.
    """
    expected = next(
        found
        for found in scene.holes
        if found.category is MontessoriShapeCategory.TRIANGULAR_PRISM
    )

    [found] = list(
        a(ShapeSortingHoleDetection)(
            category=MontessoriShapeCategory.TRIANGULAR_PRISM, pose=...
        ).evaluate(backend=looking)
    )

    assert found.pose.to_position().to_np() == pytest.approx(
        expected.pose.to_position().to_np()
    )


def test_a_statement_over_one_kind_does_not_return_the_other(
    looking: MontessoriPerceptionBackend,
):
    pieces = list(a(DetectedMontessoriShape)().evaluate(backend=looking))

    assert pieces
    assert all(not isinstance(found, ShapeSortingHoleDetection) for found in pieces)


def test_an_attribute_the_search_could_not_act_on_still_filters_the_answer(
    looking: MontessoriPerceptionBackend, scene: MontessoriScene
):
    statement = a(DetectedMontessoriShape)(category=MontessoriShapeCategory.CUBE)

    pieces = list(statement.evaluate(backend=looking))

    assert pieces == [
        found
        for found in scene.shapes
        if found.category is MontessoriShapeCategory.CUBE
    ]


def test_a_narrowed_search_still_has_its_own_condition_checked_on_the_answer(
    pipeline: MontessoriPerceptionPipeline,
    scene_with_a_piece_on_the_lid: MontessoriScene,
):
    """
    A source that cannot act on the narrowing answers with every surface's pieces, and
    the condition that narrowed the search is still what decides the answer.
    """
    statement = looking_for_something_supported_by(pipeline.lid)
    on_the_lid = [
        found
        for found in scene_with_a_piece_on_the_lid.shapes
        if found.supporting_surface == pipeline.lid.name
    ]

    pieces = list(
        statement.evaluate(
            backend=MontessoriPerceptionBackend(
                source=FixedScene(captured=scene_with_a_piece_on_the_lid)
            )
        )
    )

    assert on_the_lid
    assert len(on_the_lid) < len(scene_with_a_piece_on_the_lid.shapes)
    assert pieces == on_the_lid


# %% how it reads


def test_a_statement_answered_by_looking_verbalizes_as_looking(
    looking: MontessoriPerceptionBackend,
):
    piece = variable(MontessoriDetection, [])

    text = verbalize_expression(entity(piece), backend=looking)

    assert text.startswith(Directive.LOOK_FOR.value.text)


# %% what the search cannot narrow itself by


TABLE_THICKNESS = 0.05
"""
How thick the table the rendered scene stands on is, in metres, which only has to be
enough for a piece resting on it to touch it and one on the lid not to.
"""


@pytest.fixture
def world_the_look_is_taken_in(renderer: MontessoriSceneRenderer) -> World:
    """
    A world holding the table the rendered scene's pieces rest on.

    A relation the search cannot narrow itself by is read off bodies, so the thing a
    statement states it about has to be something the world holds rather than a
    measurement of it.
    """
    world = World()
    table = Body.from_shape_collection(
        PrefixedName("table", "montessori_scene"),
        ShapeCollection([Box(scale=Scale(4.0, 4.0, TABLE_THICKNESS))]),
    )
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("ground", "montessori_scene")))
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=table,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=renderer.table_height - TABLE_THICKNESS / 2,
                    reference_frame=world.root,
                ),
            )
        )
    return world


@pytest.fixture
def looking_in_a_world(
    pipeline: MontessoriPerceptionPipeline,
    world_the_look_is_taken_in: World,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
) -> MontessoriPerceptionBackend:
    """
    A backend answering by looking afresh at a scene laid out in a world, so what it
    finds comes to stand in a copy of that world.
    """
    pipeline.world = world_the_look_is_taken_in
    return MontessoriPerceptionBackend(
        source=RecordedFrame(
            pipeline=pipeline,
            frame=renderer.render([*placed_pieces, piece_on_the_lid]),
        )
    )


def touching_the_table(world: World):
    """
    A statement asking a look for a piece that is touching the table it was laid out on.

    Contact is read off two bodies' collision geometry, so no search narrows a look by
    it: it is answered in the world the look stood its findings in, or not at all.

    :param world: The world the look is taken in, which holds the table.
    """
    statement = a(DetectedMontessoriShape)()
    return statement.where(
        InContactWith(statement.variable.root, world.get_body_by_name("table"))
    )


def test_a_relation_the_search_cannot_narrow_itself_by_is_answered_rather_than_refused(
    looking_in_a_world: MontessoriPerceptionBackend,
    world_the_look_is_taken_in: World,
    placed_pieces: list[PlacedPiece],
):
    """
    A look reports what it saw, and what it saw now stands in a world as a body, so a
    relation the search could not act on is evaluated over something real instead of
    being refused for want of a subject.
    """
    found = list(
        touching_the_table(world_the_look_is_taken_in).evaluate(
            backend=looking_in_a_world
        )
    )

    assert {piece.category for piece in found} == {
        placed.category for placed in placed_pieces
    }


def test_what_the_relation_rejects_is_taken_out_of_the_world_the_look_stood_it_in(
    looking_in_a_world: MontessoriPerceptionBackend,
    world_the_look_is_taken_in: World,
):
    """
    The piece standing on the board's lid is not touching the table, so the world the
    look stood its findings in is left holding exactly what the statement answered.
    """
    found = list(
        touching_the_table(world_the_look_is_taken_in).evaluate(
            backend=looking_in_a_world
        )
    )

    standing = looking_in_a_world.seen.imagined.world.get_semantic_annotations_by_type(
        MontessoriShape
    )
    assert standing == [piece.role_taker for piece in found]


def touching_the_table_the_world_calls(name: PrefixedName, world: World):
    """
    The same statement, naming the table by describing it rather than handing it over.

    :param name: What the world calls the table.
    :param world: The world the look is taken in, whose bodies answer the description.
    """
    surface = variable(Body, world.bodies)
    statement = a(DetectedMontessoriShape)()
    return statement.where(
        surface.name == name,
        InContactWith(statement.variable.root, surface),
    )


def test_a_relation_to_something_the_statement_describes_is_answered_too(
    looking_in_a_world: MontessoriPerceptionBackend,
    world_the_look_is_taken_in: World,
    placed_pieces: list[PlacedPiece],
):
    """
    A statement can say which body it means by describing it, and a relation to that
    body is checked over what came back like any other -- the description is answered
    out of the world before the look, so what is left is a relation to something
    concrete.
    """
    found = list(
        touching_the_table_the_world_calls(
            PrefixedName("table", "montessori_scene"), world_the_look_is_taken_in
        ).evaluate(backend=looking_in_a_world)
    )

    assert {piece.category for piece in found} == {
        placed.category for placed in placed_pieces
    }
