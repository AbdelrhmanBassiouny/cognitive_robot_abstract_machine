"""
What a camera standing in the twin sees, and what the perception stack makes of it.

The frames are the point: a backend can only be swapped for another if every backend
reads its input from one place, so these tests are about the four places the twin's
vocabulary and the pipeline's differ -- the intrinsics, the depth, the colour order and
the way round the camera's frame is stated -- rather than about how well anything is
detected.

A test marked expected-to-fail names what would make it pass; the mark is strict, so the
day that lands the test reports the mark as stale rather than quietly passing.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest
from typing_extensions import Iterator, List

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.exceptions import SimulatedCameraIsNotLooking
from experiments.montessori.perception.recorded_setup import TABLE_HEIGHT
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.perception.simulated_camera import SimulatedCamera
from experiments.montessori.perception.simulated_setup import (
    CAMERA_FIELD_OF_VIEW,
    CAMERA_HEIGHT_ABOVE_THE_TABLE,
    CAMERA_PICTURE_HEIGHT,
    CAMERA_PICTURE_WIDTH,
    camera_over_the_table,
    lid_surface,
    looking_down_at,
    perception_pipeline,
    table_surface,
)
from experiments.montessori.pieces import (
    HUE_TOLERANCE,
    KNOWN_PIECE_BY_CATEGORY,
    hue_distance,
    hue_of,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingHole,
)
from experiments.montessori.world import MEASURED_BOARD_HUE, MontessoriWorld
from semantic_digital_twin.adapters.multi_sim import RegionAppearance
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world_description.geometry import Color

# %% the scene these tests look at

REFERENCE_CAPTURE = "tracy_pickup_demo"
"""
The capture the simulated camera is placed after, one of the six taken off the real rig.
"""

FAR_ENOUGH_TO_SEE_PAST_THE_FLOOR = 4.0
"""
How high above the table a camera has to hang, in metres, for the corners of its picture
to reach past everything the world holds.
"""


def one_of_each_known_piece(montessori_world: MontessoriWorld) -> None:
    """
    Leave the world holding exactly one piece of every kind perception knows.

    A Montessori world spawns a shape per hole plus a sphere, so it holds two cylinders
    and two shapes -- the disk and the sphere -- that perception has no piece
    description for at all. What a look can be judged against is one of each piece it
    knows to look for.

    :param montessori_world: The world to thin out, in place.
    """
    world = montessori_world.world
    kept: List[MontessoriShapeCategory] = []
    surplus = []
    for shape in world.get_semantic_annotations_by_type(MontessoriShape):
        if (
            shape.shape_category in KNOWN_PIECE_BY_CATEGORY
            and shape.shape_category not in kept
        ):
            kept.append(shape.shape_category)
        else:
            surplus.append(shape)
    with world.modify_world():
        for shape in surplus:
            world.remove_semantic_annotation(shape)
            world.remove_branch_from_world(shape.root)


@pytest.fixture
def montessori_world() -> MontessoriWorld:
    """
    The Montessori scene, holding the board and one of each piece perception knows.
    """
    built = MontessoriWorld()
    one_of_each_known_piece(built)
    return built


@pytest.fixture
def simulated_camera(montessori_world: MontessoriWorld) -> Iterator[SimulatedCamera]:
    """
    The camera over that scene, looking for as long as a test needs it.
    """
    with camera_over_the_table(montessori_world.world) as camera:
        yield camera


@pytest.fixture
def simulated_frame(simulated_camera: SimulatedCamera) -> RgbdFrame:
    """
    One look at the scene.
    """
    return simulated_camera.frame()


def pieces_in(montessori_world: MontessoriWorld) -> List[MontessoriShape]:
    """
    The pieces standing loose in a world, in the order it spawned them.

    :param montessori_world: The world to read.
    """
    return montessori_world.world.get_semantic_annotations_by_type(MontessoriShape)


def standing_at(
    montessori_world: MontessoriWorld, piece: MontessoriShape
) -> np.ndarray:
    """
    Where a piece's own frame stands, in the frame a look is reported in.

    :param montessori_world: The world the piece stands in.
    :param piece: The piece to locate.
    """
    return montessori_world.world.compute_forward_kinematics_np(
        montessori_world.world.root, piece.root
    )[:3, 3]


def top_of(montessori_world: MontessoriWorld, piece: MontessoriShape) -> np.ndarray:
    """
    The middle of the face a piece shows a camera looking down at it.

    A look measures the surface it lands on rather than the middle of the solid behind
    it, so this is the point a rendered picture can be asked about: reading a pixel of
    the piece's own centre back would answer a little further out, by the parallax
    between the two heights.

    :param montessori_world: The world the piece stands in.
    :param piece: The piece to measure.
    """
    standing = standing_at(montessori_world, piece)
    highest = float(
        piece.root.collision.as_bounding_box_collection_in_frame(
            montessori_world.world.root
        )
        .bounding_box()
        .max_z
    )
    return np.array([standing[0], standing[1], highest])


def seen_at(frame: RgbdFrame, pixel: np.ndarray) -> np.ndarray:
    """
    The point in the world a pixel of a look shows, read back out of the frame.

    The whole chain a frame carries -- its intrinsics, its depth and where it says the
    camera stood -- run backwards, so what it answers is only right if all three are.

    :param frame: The look to read.
    :param pixel: The pixel, as an ``(x, y)`` pair.
    :raises AssertionError: If the sensor measured no depth at that pixel.
    """
    column, row = int(round(float(pixel[0]))), int(round(float(pixel[1])))
    depth = float(frame.depth[row, column])
    assert depth > 0.0, f"no depth was measured at pixel {(column, row)}"
    in_the_camera = frame.intrinsics.deproject(
        np.array([[column, row]], dtype=float), np.array([depth])
    )[0]
    return (frame.reference_frame_T_camera @ np.append(in_the_camera, 1.0))[:3]


def color_at(frame: RgbdFrame, pixel: np.ndarray) -> Color:
    """
    The colour a look shows at one pixel, in the way round the world states a colour.

    :param frame: The look to read.
    :param pixel: The pixel, as an ``(x, y)`` pair.
    """
    column, row = int(round(float(pixel[0]))), int(round(float(pixel[1])))
    blue, green, red = frame.color[row, column]
    return Color(R=red / 255.0, G=green / 255.0, B=blue / 255.0)


# %% the camera stands where the real one does


def test_the_camera_hangs_as_high_above_the_table_as_the_real_one_stands() -> None:
    """
    The height the simulated rig states is the one the captures were taken from.
    """
    real = SceneCapture.load(REFERENCE_CAPTURE).to_frame()
    above_the_table = float(real.reference_frame_T_camera[2, 3]) - TABLE_HEIGHT
    assert CAMERA_HEIGHT_ABOVE_THE_TABLE == pytest.approx(above_the_table, abs=5e-4)


def test_the_camera_sees_the_angle_and_the_picture_the_real_one_does() -> None:
    """
    The field of view and picture size the simulated rig states are the captures' own.
    """
    real = SceneCapture.load(REFERENCE_CAPTURE).to_frame()
    seen = np.degrees(
        2.0 * np.arctan((real.height / 2.0) / real.intrinsics.focal_length_y)
    )
    assert CAMERA_FIELD_OF_VIEW == pytest.approx(float(seen), abs=5e-2)
    assert (CAMERA_PICTURE_WIDTH, CAMERA_PICTURE_HEIGHT) == (real.width, real.height)


def test_the_camera_stands_over_the_middle_of_the_stretch_it_searches(
    montessori_world: MontessoriWorld,
) -> None:
    """
    A look is taken of the table the pipeline searches, not of wherever the camera fell.
    """
    searched = table_surface(montessori_world.world).region
    camera = camera_over_the_table(montessori_world.world)
    standing = camera.reference_frame_T_camera[:3, 3]
    assert standing[0] == pytest.approx((searched.minimum_x + searched.maximum_x) / 2.0)
    assert standing[1] == pytest.approx((searched.minimum_y + searched.maximum_y) / 2.0)
    assert standing[2] == pytest.approx(
        table_surface(montessori_world.world).height + CAMERA_HEIGHT_ABOVE_THE_TABLE
    )


# %% what a rendered look carries


def test_a_look_is_the_size_the_twin_states_for_its_camera(
    simulated_frame: RgbdFrame,
) -> None:
    """
    The picture is as big as the camera the world places says it is.
    """
    assert (simulated_frame.width, simulated_frame.height) == (
        CAMERA_PICTURE_WIDTH,
        CAMERA_PICTURE_HEIGHT,
    )


def test_a_look_is_read_with_the_intrinsics_the_camera_amounts_to(
    simulated_camera: SimulatedCamera, simulated_frame: RgbdFrame
) -> None:
    """
    A frame carries the intrinsics its own angle and picture size make, so that whatever
    reads a look off a capture reads one off a rendering the same way.
    """
    assert simulated_frame.intrinsics == simulated_camera.intrinsics


def test_where_the_twin_says_a_piece_stands_is_where_the_look_shows_it(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    Every piece is seen at the pixel its own place projects to, and read back off that
    pixel it stands where the world put it.
    """
    for piece in pieces_in(montessori_world):
        showing = top_of(montessori_world, piece)
        found = seen_at(simulated_frame, simulated_frame.project(showing)[0])
        assert found == pytest.approx(showing, abs=2e-3)


def test_the_depth_where_the_board_is_seen_is_the_height_of_its_lid(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    Depth comes back in metres along the camera's own axis, so a point read off the
    board's middle stands exactly as high as the world says its lid does.
    """
    lid = lid_surface(montessori_world.world)
    middle_of_the_board = montessori_world.world.compute_forward_kinematics_np(
        montessori_world.world.root, montessori_world.board.root
    )[:3, 3]
    pixel = simulated_frame.project(
        np.array([middle_of_the_board[0], middle_of_the_board[1], lid.height])
    )[0]
    assert seen_at(simulated_frame, pixel)[2] == pytest.approx(lid.height, abs=2e-3)


def test_a_look_reaching_past_everything_the_world_holds_measures_nothing_there(
    montessori_world: MontessoriWorld,
) -> None:
    """
    A pixel no surface falls in carries no reading, rather than the distance a renderer
    answers with where it sees nothing.
    """
    table = table_surface(montessori_world.world)
    over_the_table = Point3(
        x=(table.region.minimum_x + table.region.maximum_x) / 2.0,
        y=(table.region.minimum_y + table.region.maximum_y) / 2.0,
        z=table.height,
    )
    with looking_down_at(
        montessori_world.world,
        over_the_table,
        height_above_the_target=FAR_ENOUGH_TO_SEE_PAST_THE_FLOOR,
    ) as camera:
        frame = camera.frame()
    assert frame.carries_depth
    assert frame.depth[0, 0] == 0.0
    assert frame.depth[-1, -1] == 0.0


def test_a_piece_is_seen_wearing_the_colour_the_world_states_for_it(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    The colour comes back in the order a look is read in, so the hue measured off a
    piece is the hue the world gave it rather than the one its channels swapped to.
    """
    for piece in pieces_in(montessori_world):
        pixel = simulated_frame.project(top_of(montessori_world, piece))[0]
        known = KNOWN_PIECE_BY_CATEGORY[piece.shape_category]
        measured = hue_of(color_at(simulated_frame, pixel))
        assert hue_distance(measured, known.hue) <= HUE_TOLERANCE


# %% a camera that is not looking


def test_a_camera_that_was_never_started_answers_no_look(
    montessori_world: MontessoriWorld,
) -> None:
    """
    Asking a camera with no mirror behind it for a frame says so, rather than failing
    somewhere inside the renderer.
    """
    camera = camera_over_the_table(montessori_world.world)
    with pytest.raises(SimulatedCameraIsNotLooking):
        camera.frame()


# %% what a region shows in a picture


def square_hole(montessori_world: MontessoriWorld) -> ShapeSortingHole:
    """
    The board's square hole, whose region wears a piece's own colour.

    :param montessori_world: The world to read.
    """
    return next(
        hole
        for hole in montessori_world.world.get_semantic_annotations_by_type(
            ShapeSortingHole
        )
        if hole.shape_category is MontessoriShapeCategory.CUBE
    )


def hue_of_the_middle_of(
    montessori_world: MontessoriWorld, hole: ShapeSortingHole, frame: RgbdFrame
) -> int:
    """
    The hue a look shows at the pixel a hole's own middle falls on.

    :param montessori_world: The world the hole is in.
    :param hole: The hole to look at.
    :param frame: The look to read.
    """
    middle = montessori_world.world.compute_forward_kinematics_np(
        montessori_world.world.root, hole.root
    )[:3, 3]
    return hue_of(color_at(frame, frame.project(middle)[0]))


def test_a_region_is_not_drawn_into_a_look(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    A camera shows the things a world holds and not the names it gives to volumes of
    space: where a hole's region stands, a look shows the board it is cut into.
    """
    seen = hue_of_the_middle_of(
        montessori_world, square_hole(montessori_world), simulated_frame
    )
    assert hue_distance(seen, MEASURED_BOARD_HUE) <= HUE_TOLERANCE


def test_a_region_asked_for_is_drawn_see_through(
    montessori_world: MontessoriWorld,
) -> None:
    """
    Asked to draw them, the same camera shows a region tinting what it covers rather
    than hiding it: the hue moves towards the region's own without reaching it.
    """
    hole = square_hole(montessori_world)
    region_hue = hue_of(hole.root.area.shapes[0].color)
    camera = camera_over_the_table(montessori_world.world)
    with camera:
        hidden = hue_of_the_middle_of(montessori_world, hole, camera.frame())
    camera.region_appearance = RegionAppearance.TRANSPARENT
    with camera:
        drawn = hue_of_the_middle_of(montessori_world, hole, camera.frame())
    assert hue_distance(drawn, region_hue) < hue_distance(hidden, region_hue)
    assert hue_distance(drawn, region_hue) > HUE_TOLERANCE


# %% what the perception stack makes of a rendered look


def test_every_piece_the_world_places_on_the_table_is_found(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    The stack that reads a capture reads a rendering: every kind of piece standing on
    the table is reported standing on it.
    """
    scene = RecordedFrame(
        pipeline=perception_pipeline(montessori_world.world), frame=simulated_frame
    ).scene()
    table = table_surface(montessori_world.world)
    reported = {
        shape.category
        for shape in scene.shapes
        if shape.supporting_surface == table.name
    }
    assert reported >= {piece.shape_category for piece in pieces_in(montessori_world)}


HOLE_PLACING_TOLERANCE = 0.006
"""
How far, in metres, a hole seen in a rendering may stand from the one the twin cut.

The layout is fitted as one piece, so every hole is placed by all six at once and none
of them is placed on its own: measured on this scene the worst of the six lands 5.4 mm
from the hole it was cut for and the middle of them 1.2 mm.
"""


def holes_cut_in(montessori_world: MontessoriWorld) -> List[ShapeSortingHole]:
    """
    Every hole the twin cut through the board's lid.

    :param montessori_world: The world to read.
    """
    return list(
        montessori_world.world.get_semantic_annotations_by_type(ShapeSortingHole)
    )


def test_the_board_is_found_by_the_holes_the_camera_measures_through_it(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    A look at the simulated scene finds the board, and puts every hole where the twin
    cut the hole of that same category.

    Nothing the picture's own colours carry says where they are: a rendered hole's walls
    are lit like the lid they are cut through, where a real one falls into shadow. What
    a look has of them there is what the camera measured -- the drawer under the lid,
    ten millimetres down.
    """
    scene = RecordedFrame(
        pipeline=perception_pipeline(montessori_world.world), frame=simulated_frame
    ).scene()
    cut = holes_cut_in(montessori_world)

    assert scene.board is not None
    assert len(scene.board.holes) == len(cut)
    for seen in scene.board.holes:
        middle = np.asarray(seen.outline, dtype=float).mean(axis=0)
        nearest = min(cut, key=lambda hole: distance_to(hole, middle))
        assert seen.category is nearest.shape_category
        assert distance_to(nearest, middle) < HOLE_PLACING_TOLERANCE


def distance_to(hole: ShapeSortingHole, middle: np.ndarray) -> float:
    """
    How far a place on the lid lies from a hole the twin cut, in metres.

    :param hole: The hole the twin cut.
    :param middle: The place, as a world-frame ``(x, y)`` point.
    """
    position = hole.root.global_transform.to_position()
    return float(
        np.linalg.norm(np.array([float(position.x), float(position.y)]) - middle)
    )


def test_every_piece_on_the_table_is_reported_once_with_its_own_category(
    montessori_world: MontessoriWorld, simulated_frame: RgbdFrame
) -> None:
    """
    A look at the simulated scene reports what stands in it, and nothing else.
    """
    scene = RecordedFrame(
        pipeline=perception_pipeline(montessori_world.world), frame=simulated_frame
    ).scene()
    assert Counter(shape.category for shape in scene.shapes) == Counter(
        piece.shape_category for piece in pieces_in(montessori_world)
    )
