"""
Tests for what perception expects of a piece after something has acted on it, stated in
the digital twin's own relation vocabulary, and for what it reports when a look finds
something else.
"""

from __future__ import annotations

import math

import pytest

from typing_extensions import List, Optional, Type

from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.perception.exceptions import LookHasNoReferenceFrame
from experiments.montessori.perception.expectations import (
    Expectation,
    Expectations,
)
from experiments.montessori.perception.footprint import Footprint
from experiments.montessori.perception.hypotheses import (
    BelievedPlace,
    PieceHypothesis,
)
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import (
    CubeShape,
    CylinderShape,
    MontessoriShapeCategory,
    ShapeSortingHole,
    TriangularPrismShape,
)
from krrood.entity_query_language.backends import StatedRelation
from krrood.entity_query_language.predicate import Relation
from segmind.datastructures.events import (
    InsertionEvent,
    LossOfSupportEvent,
    PickUpEvent,
    PlacingEvent,
    SupportEvent,
    TranslationEvent,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import (
    Colored,
    InsideRegion,
    Near,
    SupportedBy,
    Turned,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

from .dataset import montessori_scene_fixtures
from .dataset.montessori_belief_sources import SomethingThatAskedForALook
from .dataset.montessori_scene_renderer import (
    MontessoriSceneRenderer,
    PlacedPiece,
)

pytest_plugins = [montessori_scene_fixtures.__name__]

# %% the world these tests state their expectations over

SETUP = "expectations_test"
"""
The prefix every entity of these tests is named under.
"""

LID_HEIGHT = 0.96
"""
Height of the lid's plane above the world's origin, in metres, for these tests.
"""

HOLE_WIDTH = 0.04
"""
How wide the square hole is, in metres, along either side.
"""

HOLE_DEPTH = 0.03
"""
How far below the lid's plane the square hole's region reaches, in metres.
"""

PIECE_HEIGHT = 0.03
"""
How tall the cube a look reports stands, in metres.
"""

RELEASE_SPREAD = 0.03
"""
How far from a hole a released piece may come to rest, in metres, for these tests.

Stated here rather than defaulted, because :class:`Expectations` refuses to invent it -
see its own :attr:`~Expectations.release_spread`.
"""


def body_named(name: str) -> Body:
    """
    A body of the world these tests state their events over.

    :param name: What the world calls it.
    """
    return Body(name=PrefixedName(name, SETUP))


def hole_region_named(name: str) -> Region:
    """
    The region of a hole cut through the lid: as wide as the hole, reaching from the
    lid's plane down into the board, so a piece that went through lies in it and one
    resting on the lid does not.

    :param name: What the world calls it.
    """
    return Region(
        name=PrefixedName(name, SETUP),
        area=ShapeCollection(
            [
                Box(
                    scale=Scale(HOLE_WIDTH, HOLE_WIDTH, HOLE_DEPTH),
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        z=-HOLE_DEPTH / 2
                    ),
                )
            ]
        ),
    )


def world_with_a_hole_at(x: float, y: float, height: float = LID_HEIGHT) -> World:
    """
    A world holding the square hole's region, its top flush with the lid's plane.

    :param x: Where the hole's centre lies along the world's x-axis, in metres.
    :param y: Where it lies along the world's y-axis, in metres.
    :param height: The lid's plane, in metres.
    """
    world = World()
    with world.modify_world():
        world.add_body(body_named("ground"))
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=hole_region_named("square_hole"),
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=x, y=y, z=height, reference_frame=world.root
                ),
            )
        )
    return world


WORLD = world_with_a_hole_at(0.8, 0.1)
LID = body_named("board_lid")
TABLE = body_named("table_surface")
SQUARE_HOLE = ShapeSortingHole(
    root=[region for region in WORLD.regions][0],
    shape_category=MontessoriShapeCategory.CUBE,
)
CUBE = CubeShape(root=body_named("cube"))
CYLINDER = CylinderShape(root=body_named("cylinder"))


@pytest.fixture
def expectations() -> Expectations:
    """
    An empty set of expectations over the board's lid, with a release spread stated.
    """
    return Expectations(lid=LID, release_spread=RELEASE_SPREAD)


@pytest.fixture
def asker() -> SomethingThatAskedForALook:
    """
    Whatever asked for the look, standing in for the action that declared an effect.
    """
    return SomethingThatAskedForALook()


def release_the_cube(
    expectations: Expectations, asker: SomethingThatAskedForALook
) -> None:
    """
    Arm the expectation the events below then confirm or refute.

    :param expectations: What perception expects.
    :param asker: What declared the effect.
    """
    expectations.released_over(piece=CUBE, hole=SQUARE_HOLE, source=asker)


def kinds_of(expectation: Expectation) -> List[Type[Relation]]:
    """
    The kinds of relation an expectation holds, in the order it states them.

    :param expectation: What is expected of a piece.
    """
    return [stated.relation_type for stated in expectation.holds]


def piece_seen_at(
    x: float,
    y: float,
    yaw: float = 0.0,
    supporting_surface: PrefixedName = LID.name,
    sunk: bool = False,
) -> DetectedMontessoriShape:
    """
    A cube detection, as a look would report it, standing as a body in a world of its
    own the way a look stands what it found.

    :param x: Where it was seen along the world frame's x-axis, in metres.
    :param y: Where it was seen along the world frame's y-axis, in metres.
    :param yaw: How far it is turned about the world frame's z-axis, in radians.
    :param supporting_surface: What the look says is supporting it.
    :param sunk: Whether it went through the hole, standing below the lid's plane rather
        than on it.
    """
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    centre_height = LID_HEIGHT + (-PIECE_HEIGHT if sunk else PIECE_HEIGHT) / 2
    pose = Pose.from_xyz_rpy(
        x, y, centre_height, 0.0, 0.0, yaw, reference_frame=WORLD.root
    )
    return DetectedMontessoriShape(
        role_taker=ImaginedWorld.copied_from(None).spawn(cube, pose),
        pose=pose,
        footprint=Footprint(
            area=HOLE_WIDTH**2,
            width=HOLE_WIDTH,
            length=HOLE_WIDTH,
            fill_ratio=1.0,
            corner_count=4,
            yaw=yaw,
        ),
        outline=cube.turned_outline(yaw),
        category=MontessoriShapeCategory.CUBE,
        supporting_surface=supporting_surface,
        height=PIECE_HEIGHT,
        outline_agreement=0.8,
        hypothesis=PieceHypothesis(
            place=BelievedPlace(
                surface=supporting_surface, center=PlanarPoint(x=x, y=y)
            ),
            source=SomethingThatAskedForALook(),
        ),
    )


def expectation_of_the_cube(
    *further: StatedRelation, source: Optional[SomethingThatAskedForALook] = None
) -> Expectation:
    """
    The cube expected in the square hole, resting on the lid, and whatever else is
    stated.

    :param further: Anything else expected of it.
    :param source: What put the belief there.
    """
    return Expectation(
        piece=CUBE,
        holds=(
            StatedRelation.of(SupportedBy, LID),
            StatedRelation.of(InsideRegion, SQUARE_HOLE.root),
            StatedRelation.of(Near, SQUARE_HOLE.root, radius=RELEASE_SPREAD),
            *further,
        ),
        source=SomethingThatAskedForALook() if source is None else source,
    )


# %% what an action's declared effect believes


def test_a_piece_released_over_a_hole_is_expected_in_it_on_the_lid_within_the_spread(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    The insertion's own promise, armed before any event confirms it, said in the world's
    vocabulary: on the lid, in the hole's region, no further from the hole than a
    release scatters.
    """
    release_the_cube(expectations, asker)

    expected = expectations.of(CUBE)

    assert expected.holds == (
        StatedRelation.of(SupportedBy, LID),
        StatedRelation.of(InsideRegion, SQUARE_HOLE.root),
        StatedRelation.of(Near, SQUARE_HOLE.root, radius=RELEASE_SPREAD),
    )
    assert expected.source is asker


def test_a_released_piece_may_be_turned_any_way_the_release_allows(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    A release settles where a piece lands, not which way round it lands.
    """
    release_the_cube(expectations, asker)

    assert Turned not in kinds_of(expectations.of(CUBE))


def test_a_piece_nothing_has_acted_on_is_expected_nowhere(expectations: Expectations):
    """
    Perception expects nothing of a piece it has been told nothing about.
    """
    assert expectations.of(CUBE) is None


# %% what the events do to a belief


def test_picking_a_piece_up_leaves_it_resting_on_nothing_and_in_no_region(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    Picked up, a piece is held rather than supported: what the event says nothing about
    -- how far from the hole it was believed -- is all that survives.
    """
    release_the_cube(expectations, asker)

    expectations.record(PickUpEvent(tracked_object=CUBE.root))

    assert kinds_of(expectations.of(CUBE)) == [Near]


def test_placing_a_piece_leaves_it_resting_on_what_it_was_placed_on(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    After a placing, the thing the event names is what supports the piece, instead of
    whatever it rested on before.
    """
    release_the_cube(expectations, asker)

    expectations.record(PlacingEvent(tracked_object=CUBE.root, with_object=TABLE))

    assert StatedRelation.of(SupportedBy, TABLE) in expectations.of(CUBE).holds
    assert StatedRelation.of(SupportedBy, LID) not in expectations.of(CUBE).holds


def test_an_insertion_confirms_the_hole_the_piece_went_through(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    The event confirms what the declared effect had already armed, and takes the lid out
    from under a piece that went through it.
    """
    release_the_cube(expectations, asker)

    expectations.record(
        InsertionEvent(tracked_object=CUBE.root, with_object=SQUARE_HOLE.root)
    )

    assert kinds_of(expectations.of(CUBE)) == [InsideRegion, Near]


def test_support_by_a_surface_is_what_the_piece_is_then_expected_to_rest_on(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    A support event refutes a belief that named anything else.
    """
    release_the_cube(expectations, asker)

    expectations.record(SupportEvent(tracked_object=CUBE.root, with_object=TABLE))

    assert StatedRelation.of(SupportedBy, TABLE) in expectations.of(CUBE).holds
    assert StatedRelation.of(SupportedBy, LID) not in expectations.of(CUBE).holds


def test_losing_support_leaves_the_piece_expected_on_nothing(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    After LossOfSupport the piece rests on nothing that was seen supporting it, which is
    the item's own "stop searching the table".
    """
    release_the_cube(expectations, asker)
    expectations.record(SupportEvent(tracked_object=CUBE.root, with_object=TABLE))

    expectations.record(LossOfSupportEvent(tracked_object=CUBE.root, with_object=TABLE))

    assert SupportedBy not in kinds_of(expectations.of(CUBE))


def test_losing_support_from_something_else_leaves_the_belief_alone(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    A piece stops resting on what it is losing support from, not on whatever it happens
    to be believed to rest on.
    """
    release_the_cube(expectations, asker)

    expectations.record(LossOfSupportEvent(tracked_object=CUBE.root, with_object=TABLE))

    assert StatedRelation.of(SupportedBy, LID) in expectations.of(CUBE).holds


def test_a_belief_only_decays_when_something_acts_on_that_piece(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    The rule that carries the weight: an event about another piece leaves this piece's
    belief exactly where it was.
    """
    release_the_cube(expectations, asker)
    before = expectations.of(CUBE)

    expectations.record(PickUpEvent(tracked_object=CYLINDER.root))

    assert expectations.of(CUBE) == before


def test_an_event_leaves_what_it_says_nothing_about_exactly_as_it_was(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    A support event says what a piece rests on and nothing about where it lies, so the
    hole and the spread survive it whole.
    """
    release_the_cube(expectations, asker)

    expectations.record(SupportEvent(tracked_object=CUBE.root, with_object=TABLE))

    assert StatedRelation.of(InsideRegion, SQUARE_HOLE.root) in (
        expectations.of(CUBE).holds
    )
    assert StatedRelation.of(Near, SQUARE_HOLE.root, radius=RELEASE_SPREAD) in (
        expectations.of(CUBE).holds
    )


def test_an_event_that_states_no_effect_leaves_the_belief_alone(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    That something moved says nothing about what holds of it, so a belief survives it
    whole.
    """
    release_the_cube(expectations, asker)
    before = expectations.of(CUBE)

    expectations.record(TranslationEvent(tracked_object=CUBE.root, with_object=TABLE))

    assert expectations.of(CUBE) == before


def test_an_event_about_a_piece_nothing_is_expected_of_changes_nothing(
    expectations: Expectations,
):
    """
    An event moves a belief rather than creating one: only a declared effect says what
    to expect of a piece the robot has not acted on.
    """
    expectations.record(SupportEvent(tracked_object=CUBE.root, with_object=LID))

    assert expectations.of(CUBE) is None


# %% how an expectation reaches a look


def test_an_expectation_reaches_a_look_as_the_relations_it_states(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    The same relations that are expected of the piece are what the look is asked for, so
    the search narrows itself by them the way it narrows itself by any statement.
    """
    release_the_cube(expectations, asker)

    [request] = expectations.scene_requests()

    assert request.supporting_surface == LID.name
    assert [type(placement) for placement in request.placements] == [
        InsideRegion,
        Near,
    ]
    assert request.placements[1].radius == RELEASE_SPREAD


def test_a_look_is_asked_for_the_colour_the_expected_piece_wears(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    Which piece is expected is what makes a seeded fit cheap, and a look is told which
    piece by the colour it wears.
    """
    release_the_cube(expectations, asker)

    [request] = expectations.scene_requests()

    assert request.color == KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE].color


def test_a_look_fits_a_piece_where_the_expectation_confines_it_on_the_askers_say_so(
    expectations: Expectations, asker: SomethingThatAskedForALook
):
    """
    The hole's region and the release's spread together confine the piece to a stretch a
    fit can sweep, and whoever declared the effect is who vouches for it.
    """
    release_the_cube(expectations, asker)

    [request] = expectations.scene_requests()
    stretch = request.believed_stretch()

    assert request.believed_by is asker
    assert stretch.x_interval.lower == pytest.approx(0.8 - HOLE_WIDTH / 2)
    assert stretch.x_interval.upper == pytest.approx(0.8 + HOLE_WIDTH / 2)
    assert stretch.y_interval.lower == pytest.approx(0.1 - HOLE_WIDTH / 2)


def test_a_look_asked_for_a_turn_lays_the_piece_that_way(
    asker: SomethingThatAskedForALook,
):
    """
    An expectation about which way the piece is turned reaches the look as the turns
    worth trying.
    """
    expectation = expectation_of_the_cube(
        StatedRelation.of(Turned, 0.3, spread=0.1), source=asker
    )

    request = expectation.scene_request()

    assert isinstance(request.turn, Turned)
    assert (request.turn.yaw, request.turn.spread) == (0.3, 0.1)


# %% what a look that differs from the expectation reports


def test_a_piece_found_where_it_was_promised_meets_the_expectation():
    """
    Nothing is violated when the look agrees with the promise: in the hole, on the lid.
    """
    report = expectation_of_the_cube().check(piece_seen_at(0.8, 0.1, sunk=True))

    assert report.holds
    assert report.violated == ()


def test_a_piece_found_on_something_else_violates_the_support_it_was_promised():
    """
    The insertion promised the cube would rest on the lid; the look says the table.
    """
    report = expectation_of_the_cube().check(
        piece_seen_at(0.8, 0.1, supporting_surface=TABLE.name, sunk=True)
    )

    assert [type(violated) for violated in report.violated] == [SupportedBy]


def test_a_piece_found_on_the_lid_beside_the_hole_violates_being_in_it():
    """
    The insertion promised the cube would end up in the hole; it is lying on the lid
    over it, near enough and on the right surface, but not in.
    """
    report = expectation_of_the_cube().check(piece_seen_at(0.8, 0.1))

    assert [type(violated) for violated in report.violated] == [InsideRegion]


def test_a_piece_found_beyond_the_release_spread_violates_being_near_the_hole():
    """
    Displaced from the hole by further than the release allows, and so out of it too.
    """
    report = expectation_of_the_cube().check(
        piece_seen_at(0.8 + RELEASE_SPREAD * 2, 0.1)
    )

    assert [type(violated) for violated in report.violated] == [InsideRegion, Near]


def test_a_piece_found_turned_out_of_the_expected_turn_violates_it():
    """
    In the hole, and thirty degrees from where it would have had to be to fit.
    """
    expectation = expectation_of_the_cube(
        StatedRelation.of(Turned, 0.0, spread=math.radians(5))
    )

    report = expectation.check(piece_seen_at(0.8, 0.1, yaw=math.radians(30), sunk=True))

    assert [type(violated) for violated in report.violated] == [Turned]


def test_an_expectation_that_says_nothing_about_a_turn_cannot_be_contradicted_about_one():
    """
    A release allows every turn, so no turn a look reports differs from it.
    """
    report = expectation_of_the_cube().check(
        piece_seen_at(0.8, 0.1, yaw=math.radians(30), sunk=True)
    )

    assert report.holds


def test_every_relation_the_look_contradicts_is_named_at_once():
    """
    A report names each relation that fails, since a recovery acts on all of them.
    """
    expectation = expectation_of_the_cube(
        StatedRelation.of(Turned, 0.0, spread=math.radians(5))
    )

    report = expectation.check(
        piece_seen_at(
            0.8 + RELEASE_SPREAD * 2,
            0.1,
            yaw=math.radians(30),
            supporting_surface=TABLE.name,
        )
    )

    assert [type(violated) for violated in report.violated] == [
        SupportedBy,
        InsideRegion,
        Near,
        Turned,
    ]


def test_a_violated_relation_is_reported_about_the_body_the_look_stood_for_the_piece():
    """
    What is reported is the claim that failed, written over the sighting's own body, so
    it reads and evaluates like any relation of the world.
    """
    seen = piece_seen_at(0.8, 0.1)

    [violated] = expectation_of_the_cube().check(seen).violated

    assert isinstance(violated, InsideRegion)
    assert violated.body is seen.role_taker.root
    assert violated.region is SQUARE_HOLE.root


def test_finding_nothing_where_the_action_promised_is_its_own_outcome():
    """
    Perception looked exactly where the action promised and found nothing, which is an
    absence rather than a relation being contradicted.
    """
    report = expectation_of_the_cube().check(None)

    assert not report.holds
    assert report.nothing_was_found
    assert report.violated == ()


def test_a_report_carries_the_look_it_was_answered_by():
    """
    A recovery needs what was actually seen, not only which relation failed.
    """
    seen = piece_seen_at(0.8, 0.1, sunk=True)

    assert expectation_of_the_cube().check(seen).seen is seen


# %% a look armed by what the robot just did


@pytest.fixture
def prism_on_the_lid(renderer: MontessoriSceneRenderer) -> PlacedPiece:
    """
    A triangular prism standing on the board's lid, wearing the lid's own hue.
    """
    x, y = renderer.clear_lid_position()
    return PlacedPiece(
        MontessoriShapeCategory.TRIANGULAR_PRISM,
        x=x,
        y=y,
        surface_height=renderer.lid_height,
    )


@pytest.fixture
def released_prism(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    prism_on_the_lid: PlacedPiece,
) -> Expectation:
    """
    What an insertion promised of the prism: released over a triangle hole where the
    prism happens to stand, in a world the pipeline reads and reports in.
    """
    world = world_with_a_hole_at(
        prism_on_the_lid.x, prism_on_the_lid.y, renderer.lid_height
    )
    pipeline.world = world
    pipeline.reference_frame = world.root
    expectations = Expectations(
        lid=Body(name=pipeline.lid.name), release_spread=RELEASE_SPREAD
    )
    prism = TriangularPrismShape(root=body_named("prism"))
    expectations.released_over(
        piece=prism,
        hole=ShapeSortingHole(
            root=[region for region in world.regions][0],
            shape_category=MontessoriShapeCategory.TRIANGULAR_PRISM,
        ),
        source=SomethingThatAskedForALook(),
    )
    return expectations.of(prism)


def test_a_piece_a_colour_cannot_separate_is_found_because_an_action_promised_it(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    prism_on_the_lid: PlacedPiece,
    released_prism: Expectation,
):
    """
    The end of the whole path, in one test: an action declares that it released a prism.

    over a hole, that promise becomes the relations a look is asked for, and the look
    finds a piece wearing the lid's own hue - which no colour mask can cut out of it,
    and which the same look reports nothing of when it is asked for nothing.
    """
    frame = renderer.render([prism_on_the_lid])

    unarmed = pipeline.detect(frame)
    armed = pipeline.detect(frame, released_prism.scene_request())

    assert not found_at(unarmed, prism_on_the_lid)
    assert found_at(armed, prism_on_the_lid).category is prism_on_the_lid.category


def test_a_look_that_finds_the_piece_elsewhere_reports_the_relation_that_fails(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    prism_on_the_lid: PlacedPiece,
    released_prism: Expectation,
):
    """
    The item's own story end to end: the insertion promised the prism would end up in.

    the hole, the look finds it resting on the lid over it, and what is reported is
    that it is not in the hole - near it and on the lid as promised, but not in.
    """
    scene = pipeline.detect(
        renderer.render([prism_on_the_lid]), released_prism.scene_request()
    )

    report = released_prism.check(found_at(scene, prism_on_the_lid))

    assert not report.holds
    assert [type(violated) for violated in report.violated] == [InsideRegion]
    assert report.seen.supporting_surface == pipeline.lid.name


def test_a_look_armed_with_a_placement_needs_a_frame_to_read_it_in(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    prism_on_the_lid: PlacedPiece,
    released_prism: Expectation,
):
    """
    Where a hole is, in metres, can only be read against the frame the detections are
    reported in.
    """
    pipeline.reference_frame = None

    with pytest.raises(LookHasNoReferenceFrame):
        pipeline.detect(
            renderer.render([prism_on_the_lid]), released_prism.scene_request()
        )


def found_at(scene, piece: PlacedPiece) -> Optional[DetectedMontessoriShape]:
    """
    What a look reported where a piece was placed, or None where it reported nothing.

    :param scene: What the look found.
    :param piece: The piece the scene was rendered with.
    """
    at_the_piece = [
        seen
        for seen in scene.shapes
        if math.hypot(
            float(seen.pose.to_position().to_np()[0]) - piece.x,
            float(seen.pose.to_position().to_np()[1]) - piece.y,
        )
        <= 0.01
    ]
    return at_the_piece[0] if at_the_piece else None
