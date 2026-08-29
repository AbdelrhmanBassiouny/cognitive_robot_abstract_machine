"""
Tests for the continuous Montessori perception pipeline and the query interface it
answers through.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytest
from typing_extensions import Dict, List, Tuple

from experiments.montessori.perception.camera import (
    CameraIntrinsics,
    CompressedImageFormat,
    DepthQuantization,
    ImageEncoding,
    RgbdFrame,
    decode_color_image,
    decode_compressed_color_image,
    decode_compressed_depth_image,
    decode_depth_image,
)
from experiments.montessori.perception.detections import (
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.exceptions import (
    DepthAndColourNotRegistered,
    UndecodableCompressedImage,
    UnsupportedImageEncoding,
    WorkspaceOutOfView,
)
from experiments.montessori.perception.footprint import (
    CrossSectionClassifier,
    Footprint,
)
from experiments.montessori.perception.colors import (
    HOLE_COLOR,
    PIECE_COLOR,
    DetectionColor,
)
from experiments.montessori.perception.orthophoto import (
    Orthophoto,
    OrthophotoProjector,
    WorkspaceRegion,
)
from experiments.montessori.perception.overlay import (
    CameraView,
    DetectionOverlay,
    RectifiedView,
    project_to_pixels,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.piece_matcher import PieceMatcher
from experiments.montessori.perception.pipeline import (
    MontessoriPerceptionPipeline,
    SurfaceColors,
)
from experiments.montessori.pieces import (
    CYAN_HUE,
    HUE_RANGE,
    KNOWN_PIECES,
    KNOWN_PIECE_BY_CATEGORY,
    YELLOW_HUE,
    KnownPiece,
    hue_distance,
)
from experiments.montessori.perception.scene_source import FixedScene, PerceivedObjects
from experiments.montessori.perception.viewer import (
    CameraFrameViewer,
    PerceptionWindow,
    ImageDisplay,
    colorize_depth,
    scale_to_fit,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from krrood.entity_query_language.factories import a, the

from .dataset.montessori_scene_renderer import (
    MontessoriSceneRenderer,
    PlacedPiece,
    piece_color,
)

# %% fixtures


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


@pytest.fixture
def pipeline(renderer: MontessoriSceneRenderer) -> MontessoriPerceptionPipeline:
    return MontessoriPerceptionPipeline(
        region=WorkspaceRegion(
            minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
        ),
        table_height=renderer.table_height,
        board_height=renderer.board_height,
    )


@pytest.fixture
def scene(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
) -> MontessoriScene:
    return pipeline.detect(renderer.render(placed_pieces))


# %% measuring an outline


def _contour_of(boundary: np.ndarray, resolution: float) -> np.ndarray:
    """
    Turn a metric polygon into the pixel contour a rectified image would yield.
    """
    return np.round(boundary / resolution).astype(np.int32).reshape(-1, 1, 2)


def test_square_footprint_measures_its_own_side_length():
    side = 0.032
    corners = np.array([[0, 0], [side, 0], [side, side], [0, side]])

    footprint = Footprint.from_contour(_contour_of(corners, 0.001), 0.001)

    assert footprint.width == pytest.approx(side, abs=0.002)
    assert footprint.length == pytest.approx(side, abs=0.002)
    assert footprint.area == pytest.approx(side * side, rel=0.1)


def test_footprint_fill_ratio_separates_the_shape_families():
    side = 0.04
    square = np.array([[0, 0], [side, 0], [side, side], [0, side]])
    triangle = np.array([[0, 0], [side, 0], [side / 2, side]])
    circle = np.array(
        [
            [side / 2 * (1 + math.cos(angle)), side / 2 * (1 + math.sin(angle))]
            for angle in np.linspace(0, 2 * math.pi, 64, endpoint=False)
        ]
    )

    measured = {
        name: Footprint.from_contour(_contour_of(boundary, 0.0005), 0.0005).fill_ratio
        for name, boundary in (
            ("square", square),
            ("triangle", triangle),
            ("circle", circle),
        )
    }

    assert measured["triangle"] == pytest.approx(0.5, abs=0.05)
    assert measured["circle"] == pytest.approx(math.pi / 4, abs=0.05)
    assert measured["square"] == pytest.approx(1.0, abs=0.05)


@pytest.mark.parametrize(
    "fill_ratio, aspect_ratio, expected",
    [
        (0.5, 1.15, MontessoriShapeCategory.TRIANGULAR_PRISM),
        (math.pi / 4, 1.0, MontessoriShapeCategory.CYLINDER),
        (1.0, 1.0, MontessoriShapeCategory.CUBE),
        (1.0, 1.9, MontessoriShapeCategory.RECTANGULAR_PRISM),
        (1.0, 9.6, MontessoriShapeCategory.DISK),
    ],
)
def test_classifier_names_each_shape_from_its_proportions(
    fill_ratio: float, aspect_ratio: float, expected: MontessoriShapeCategory
):
    width = 0.02
    footprint = Footprint(
        area=fill_ratio * width * width * aspect_ratio,
        width=width,
        length=width * aspect_ratio,
        fill_ratio=fill_ratio,
        corner_count=4,
        yaw=0.0,
    )

    assert CrossSectionClassifier().classify(footprint) is expected


def test_footprint_yaw_follows_a_rotated_rectangle():
    angle = math.radians(30.0)
    rotation = np.array(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
    )
    rectangle = np.array([[-0.03, -0.01], [0.03, -0.01], [0.03, 0.01], [-0.03, 0.01]])
    rotated = rectangle @ rotation.T + np.array([0.06, 0.06])

    footprint = Footprint.from_contour(_contour_of(rotated, 0.0005), 0.0005)

    assert footprint.yaw == pytest.approx(angle, abs=math.radians(3.0))


# %% rectification


def test_rectified_plane_puts_a_known_point_back_where_it_came_from(
    renderer: MontessoriSceneRenderer,
):
    region = WorkspaceRegion(
        minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
    )
    frame = renderer.render([])
    world_x, world_y = 0.83, 0.12

    homography = OrthophotoProjector.pixel_T_region(frame, renderer.lid_height)
    pixel = homography @ np.array([world_x, world_y, 1.0])
    recovered = np.linalg.inv(homography) @ pixel

    assert recovered[0] / recovered[2] == pytest.approx(world_x, abs=1e-9)
    assert recovered[1] / recovered[2] == pytest.approx(world_y, abs=1e-9)


def test_a_hole_lands_at_its_own_world_position_in_the_rectified_lid(
    renderer: MontessoriSceneRenderer,
):
    region = WorkspaceRegion(
        minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
    )
    orthophoto = OrthophotoProjector(region=region).project(
        renderer.render([]), renderer.lid_height
    )
    [widest] = sorted(
        renderer.hole_footprints(), key=lambda hole: -hole.size[0] * hole.size[1]
    )[:1]
    expected_x, expected_y = renderer.hole_center(widest)

    darkness = cv2.cvtColor(orthophoto.image, cv2.COLOR_BGR2HSV)[:, :, 2]
    hole_mask = ((darkness > 0) & (darkness < 120)).astype(np.uint8)
    contours, _ = cv2.findContours(
        hole_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    centers = [orthophoto.contour_center(contour) for contour in contours]

    assert min(
        math.hypot(x - expected_x, y - expected_y) for x, y in centers
    ) == pytest.approx(0.0, abs=0.003)


# %% the pipeline


def test_pipeline_finds_every_hole_the_board_has(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    assert scene.board is not None
    assert len(scene.holes) == len(renderer.hole_footprints())


def test_pipeline_puts_each_hole_within_three_millimetres_of_its_true_centre(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    detected = [tuple(hole.pose.to_position().to_np()[:2]) for hole in scene.holes]

    for footprint in renderer.hole_footprints():
        expected_x, expected_y = renderer.hole_center(footprint)
        nearest = min(math.hypot(x - expected_x, y - expected_y) for x, y in detected)
        assert nearest == pytest.approx(0.0, abs=0.003)


def test_pipeline_reports_hole_centres_on_the_board_lid(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    for hole in scene.holes:
        assert float(hole.pose.to_position().to_np()[2]) == pytest.approx(
            renderer.lid_height
        )


def test_pipeline_recognises_the_shape_of_the_widest_holes(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    expected = {
        footprint.category
        for footprint in renderer.hole_footprints()
        if min(footprint.size) > 0.02
    }

    assert expected <= {hole.category for hole in scene.holes}


def test_pipeline_finds_each_loose_piece_where_it_stands(
    scene: MontessoriScene, placed_pieces: list[PlacedPiece]
):
    detected = [tuple(piece.pose.to_position().to_np()[:2]) for piece in scene.shapes]

    for placed in placed_pieces:
        nearest = min(math.hypot(x - placed.x, y - placed.y) for x, y in detected)
        assert nearest == pytest.approx(0.0, abs=0.006)


def test_pipeline_cancels_the_parallax_that_stretches_a_piece(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer, placed_pieces
):
    [cube] = [
        placed
        for placed in placed_pieces
        if placed.category is MontessoriShapeCategory.CUBE
    ]
    [true_footprint] = [
        footprint
        for footprint in renderer.hole_footprints()
        if footprint.category is MontessoriShapeCategory.CUBE
    ]
    nearest = min(
        scene.shapes,
        key=lambda piece: math.hypot(
            float(piece.pose.to_position().to_np()[0]) - cube.x,
            float(piece.pose.to_position().to_np()[1]) - cube.y,
        ),
    )

    assert nearest.footprint.length == pytest.approx(
        max(true_footprint.size), abs=0.008
    )


def test_pipeline_does_not_report_the_board_lid_as_a_loose_piece(
    scene: MontessoriScene,
):
    assert scene.board is not None
    for piece in scene.shapes:
        position = piece.pose.to_position().to_np()
        assert not scene.board.encloses(float(position[0]), float(position[1]))


def test_pipeline_reports_no_board_when_none_is_in_view(
    pipeline: MontessoriPerceptionPipeline, renderer: MontessoriSceneRenderer
):
    empty = renderer.render([])
    empty.color[:, :] = cv2.cvtColor(
        np.full((1, 1, 3), (30, 13, 156), dtype=np.uint8), cv2.COLOR_HSV2BGR
    )[0, 0]

    assert pipeline.detect(empty).board is None


# %% querying it


def test_a_query_over_perceived_objects_runs_perception_to_answer_itself(
    scene: MontessoriScene,
):
    class CountingSource(FixedScene):
        looks: int = 0

        def scene(self) -> MontessoriScene:
            self.looks += 1
            return self.captured

    source = CountingSource(captured=scene)
    perceived = PerceivedObjects(source=source)
    query = a(MontessoriShapeDetection).from_(perceived)

    assert source.looks == 0
    results = query.tolist()
    assert source.looks == 1
    assert len(results) == len(scene.shapes)


def test_a_query_selects_a_hole_by_the_shape_it_takes(scene: MontessoriScene):
    perceived = PerceivedObjects(source=FixedScene(captured=scene))

    holes = (
        a(ShapeSortingHoleDetection)(category=MontessoriShapeCategory.CUBE)
        .from_(perceived)
        .tolist()
    )

    assert holes
    for hole in holes:
        assert hole.category is MontessoriShapeCategory.CUBE


def test_a_query_answers_a_pose_a_plan_can_reach_for(scene: MontessoriScene):
    perceived = PerceivedObjects(source=FixedScene(captured=scene))
    [expected] = [
        hole
        for hole in scene.holes
        if hole.category is MontessoriShapeCategory.TRIANGULAR_PRISM
    ][:1]

    hole = the(
        a(ShapeSortingHoleDetection)(category=MontessoriShapeCategory.TRIANGULAR_PRISM)
        .from_(perceived)
        .expression
    ).tolist()[0]

    assert hole.pose.to_position().to_np() == pytest.approx(
        expected.pose.to_position().to_np()
    )


def test_a_query_over_one_kind_does_not_return_the_other(scene: MontessoriScene):
    perceived = PerceivedObjects(source=FixedScene(captured=scene))

    pieces = a(MontessoriShapeDetection).from_(perceived).tolist()

    assert pieces
    assert all(not isinstance(piece, ShapeSortingHoleDetection) for piece in pieces)


# %% reading camera messages


def test_colour_image_is_read_into_opencv_channel_order():
    height, width = 2, 3
    red_pixel = bytes([255, 0, 0]) * (height * width)

    image = decode_color_image(red_pixel, height, width, width * 3, ImageEncoding.RGB8)

    assert image.shape == (height, width, 3)
    assert image[0, 0].tolist() == [0, 0, 255]


def test_colour_image_honours_a_row_stride_wider_than_the_image():
    height, width, step = 2, 2, 8
    data = bytes([1, 2, 3, 4, 5, 6, 0, 0] + [7, 8, 9, 10, 11, 12, 0, 0])

    image = decode_color_image(data, height, width, step, ImageEncoding.BGR8)

    assert image[1, 1].tolist() == [10, 11, 12]


def test_millimetre_depth_is_read_as_metres():
    data = np.array([[1500, 0]], dtype=np.uint16).tobytes()

    depth = decode_depth_image(data, 1, 2, 4, ImageEncoding.DEPTH_IN_MILLIMETRES)

    assert depth[0, 0] == pytest.approx(1.5)
    assert depth[0, 1] == pytest.approx(0.0)


def test_an_unknown_encoding_is_refused():
    with pytest.raises(UnsupportedImageEncoding):
        decode_color_image(b"", 0, 0, 0, "mono8")


def test_a_frame_whose_images_are_not_registered_is_refused():
    intrinsics = CameraIntrinsics(1.0, 1.0, 0.0, 0.0)

    with pytest.raises(DepthAndColourNotRegistered):
        RgbdFrame(
            color=np.zeros((4, 4, 3), dtype=np.uint8),
            depth=np.zeros((2, 2), dtype=np.float32),
            intrinsics=intrinsics,
            reference_frame_T_camera=np.eye(4),
        )


# %% reading transport-compressed camera messages

COLOR_FORMAT_FIELD = "rgb8; jpeg compressed bgr8"
"""
The ``format`` the camera stamps on its compressed colour stream.
"""

DEPTH_FORMAT_FIELD = "16UC1; compressedDepth png"
"""
The ``format`` the camera stamps on its compressed depth stream.
"""


def encode_compressed_depth(
    quantized: np.ndarray, quantization: DepthQuantization
) -> bytes:
    """
    Build the payload ``compressedDepth`` publishes: its header, then a PNG.

    :param quantized: The image as ``compressedDepth`` stores it.
    :param quantization: The header to put in front of the PNG.
    :return: The bytes a ``sensor_msgs/CompressedImage`` would carry.
    """
    return quantization.to_header_bytes() + cv2.imencode(".png", quantized)[1].tobytes()


def test_a_colour_format_field_names_the_encoding_its_payload_is_stored_in():
    parsed = CompressedImageFormat.from_format_field(COLOR_FORMAT_FIELD)

    assert parsed.source_encoding == ImageEncoding.RGB8
    assert parsed.payload_encoding == ImageEncoding.BGR8


def test_a_depth_format_field_names_no_payload_encoding():
    parsed = CompressedImageFormat.from_format_field(DEPTH_FORMAT_FIELD)

    assert parsed.source_encoding == ImageEncoding.DEPTH_IN_MILLIMETRES
    assert parsed.payload_encoding is None


def test_a_compressed_colour_image_is_read_into_opencv_channel_order():
    blue_pixel = np.full((2, 3, 3), (255, 0, 0), dtype=np.uint8)
    payload = cv2.imencode(".png", blue_pixel)[1].tobytes()

    image = decode_compressed_color_image(payload, "bgr8; png compressed bgr8")

    assert image.shape == (2, 3, 3)
    assert image[0, 0].tolist() == [255, 0, 0]


def test_a_compressed_colour_payload_stored_in_rgb_order_is_swapped():
    payload_pixel = np.full((1, 1, 3), (255, 0, 0), dtype=np.uint8)
    payload = cv2.imencode(".png", payload_pixel)[1].tobytes()

    image = decode_compressed_color_image(payload, "rgb8; png compressed rgb8")

    assert image[0, 0].tolist() == [0, 0, 255]


def test_compressed_millimetre_depth_is_read_as_metres():
    millimetres = np.array([[1500, 0]], dtype=np.uint16)
    payload = encode_compressed_depth(millimetres, DepthQuantization(0, 0.0, 0.0))

    depth = decode_compressed_depth_image(payload, DEPTH_FORMAT_FIELD)

    assert depth[0, 0] == pytest.approx(1.5)
    assert depth[0, 1] == pytest.approx(0.0)


def test_compressed_metre_depth_is_read_back_through_its_own_quantisation():
    quantization = DepthQuantization(0, 1000.0, 100.0)
    metres = 2.5
    quantized = np.array(
        [[quantization.quantization_a / metres + quantization.quantization_b, 0]],
        dtype=np.uint16,
    )
    payload = encode_compressed_depth(quantized, quantization)

    depth = decode_compressed_depth_image(payload, "32FC1; compressedDepth png")

    assert depth[0, 0] == pytest.approx(metres, abs=1e-3)
    assert depth[0, 1] == pytest.approx(0.0)


def test_a_compressed_image_whose_payload_is_not_an_image_is_refused():
    with pytest.raises(UndecodableCompressedImage):
        decode_compressed_color_image(b"not an image", COLOR_FORMAT_FIELD)


def test_a_compressed_depth_image_in_an_unknown_encoding_is_refused():
    payload = encode_compressed_depth(
        np.zeros((1, 1), dtype=np.uint16), DepthQuantization(0, 0.0, 0.0)
    )

    with pytest.raises(UnsupportedImageEncoding):
        decode_compressed_depth_image(payload, "mono8; compressedDepth png")


# %% watching the frames as they arrive


@dataclass
class RecordingDisplay(ImageDisplay):
    """
    Stands in for a screen, remembering what it was asked to draw.
    """

    drawn: Dict[str, np.ndarray] = field(default_factory=dict)
    """
    The newest image drawn in each window, by window name.
    """

    waits: List[int] = field(default_factory=list)
    """
    How long each call to :meth:`wait` was given, in milliseconds.
    """

    closed: bool = False
    """
    Whether the windows have been taken off screen.
    """

    def draw(self, window_name: str, image: np.ndarray) -> None:
        self.drawn[window_name] = image

    def wait(self, milliseconds: int) -> None:
        self.waits.append(milliseconds)

    def close(self) -> None:
        self.closed = True


def test_unmeasured_depth_pixels_are_drawn_black():
    depth = np.array([[1.0, 0.0]], dtype=np.float32)

    colored = colorize_depth(depth)

    assert colored.shape == (1, 2, 3)
    assert colored[0, 1].tolist() == [0, 0, 0]


def test_the_nearest_and_furthest_depths_are_drawn_in_different_colours():
    depth = np.array([[0.5, 2.5]], dtype=np.float32)

    colored = colorize_depth(depth)

    assert colored[0, 0].tolist() != colored[0, 1].tolist()


def test_a_depth_image_with_nothing_measured_is_drawn_black():
    colored = colorize_depth(np.zeros((2, 3), dtype=np.float32))

    assert colored.shape == (2, 3, 3)
    assert not colored.any()


def test_an_image_smaller_than_the_window_is_drawn_at_its_own_size():
    image = np.zeros((4, 8, 3), dtype=np.uint8)

    assert scale_to_fit(image, 16, 16) is image


def test_a_wide_image_is_shrunk_to_the_window_keeping_its_proportions():
    image = np.zeros((100, 400, 3), dtype=np.uint8)

    scaled = scale_to_fit(image, 200, 200)

    assert scaled.shape == (50, 200, 3)


def test_a_tall_image_is_shrunk_to_the_window_keeping_its_proportions():
    image = np.zeros((400, 100, 3), dtype=np.uint8)

    scaled = scale_to_fit(image, 200, 200)

    assert scaled.shape == (200, 50, 3)


def test_the_viewer_draws_the_newest_frame_it_was_shown():
    display = RecordingDisplay()
    viewer = CameraFrameViewer(display=display)
    viewer.show_color(np.zeros((2, 2, 3), dtype=np.uint8))
    viewer.show_depth(np.ones((2, 2), dtype=np.float32))
    viewer.show_color(np.full((2, 2, 3), 7, dtype=np.uint8))

    viewer.refresh()

    assert display.drawn[PerceptionWindow.COLOR][0, 0].tolist() == [7, 7, 7]
    assert set(display.drawn) == {PerceptionWindow.COLOR, PerceptionWindow.DEPTH}


def test_the_rectified_view_is_drawn_in_its_own_window():
    display = RecordingDisplay()
    viewer = CameraFrameViewer(display=display)
    viewer.show_color(np.zeros((2, 2, 3), dtype=np.uint8))
    viewer.show_rectified(np.full((2, 2, 3), 5, dtype=np.uint8))

    viewer.refresh()

    assert display.drawn[PerceptionWindow.RECTIFIED][0, 0].tolist() == [5, 5, 5]
    assert set(display.drawn) == {PerceptionWindow.COLOR, PerceptionWindow.RECTIFIED}


def test_a_stream_that_has_not_arrived_leaves_only_its_own_window_empty():
    display = RecordingDisplay()
    viewer = CameraFrameViewer(display=display)
    viewer.show_color(np.zeros((2, 2, 3), dtype=np.uint8))

    viewer.refresh()

    assert set(display.drawn) == {PerceptionWindow.COLOR}


def test_the_viewer_draws_nothing_before_a_frame_has_arrived():
    display = RecordingDisplay()

    CameraFrameViewer(display=display).refresh()

    assert display.drawn == {}
    assert display.waits


def test_closing_the_viewer_takes_its_windows_off_screen():
    display = RecordingDisplay()

    CameraFrameViewer(display=display).close()

    assert display.closed


# %% drawing the detections onto the frame


@pytest.fixture
def frame(
    renderer: MontessoriSceneRenderer, placed_pieces: list[PlacedPiece]
) -> RgbdFrame:
    return renderer.render(placed_pieces)


def looking_straight_down(height: float) -> np.ndarray:
    """
    A camera hanging at a height above the world origin, pointing down.

    :param height: How far above the origin it hangs, in metres.
    :return: Its pose as a 4x4 homogeneous transformation.
    """
    pose = np.eye(4)
    pose[:3, :3] = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]])
    pose[:3, 3] = (0.0, 0.0, height)
    return pose


def frame_seen_from_above(height: float = 1.0) -> RgbdFrame:
    """
    An empty frame taken by a camera hanging above the world origin.

    :param height: How far above the origin the camera hangs, in metres.
    """
    return RgbdFrame(
        color=np.zeros((480, 640, 3), dtype=np.uint8),
        depth=np.full((480, 640), height, dtype=np.float32),
        intrinsics=CameraIntrinsics(100.0, 100.0, 320.0, 240.0),
        reference_frame_T_camera=looking_straight_down(height),
    )


def test_the_point_under_the_camera_lands_on_its_principal_point():
    pixels = project_to_pixels(frame_seen_from_above(), np.array([[0.0, 0.0]]), 0.0)

    assert pixels[0] == pytest.approx([320.0, 240.0])


def test_a_point_in_space_lands_where_its_own_plane_puts_it():
    frame = frame_seen_from_above()
    standing_at = 0.3

    pixels = frame.project(np.array([[0.1, 0.2, standing_at]]))

    assert pixels[0] == pytest.approx(
        project_to_pixels(frame, np.array([[0.1, 0.2]]), standing_at)[0]
    )


def test_a_point_beside_the_camera_axis_lands_beside_the_principal_point():
    pixels = project_to_pixels(frame_seen_from_above(), np.array([[0.1, 0.0]]), 0.0)

    assert pixels[0] == pytest.approx([330.0, 240.0])


def test_a_piece_rests_half_its_height_below_its_own_pose(scene: MontessoriScene):
    piece = scene.shapes[0]

    assert piece.surface_height == pytest.approx(
        float(piece.pose.to_position().to_np()[2]) - piece.height / 2
    )


def test_a_hole_lies_on_the_surface_its_pose_names(scene: MontessoriScene):
    hole = scene.holes[0]

    assert hole.surface_height == pytest.approx(
        float(hole.pose.to_position().to_np()[2])
    )


def test_drawing_nothing_leaves_the_frame_as_it_was():
    frame = frame_seen_from_above()

    drawn = DetectionOverlay().draw(CameraView(frame), MontessoriScene())

    assert np.array_equal(drawn, frame.color)


def test_the_overlay_leaves_the_frame_it_drew_from_untouched(
    frame: RgbdFrame, scene: MontessoriScene
):
    before = frame.color.copy()

    DetectionOverlay().draw(CameraView(frame), scene)

    assert np.array_equal(frame.color, before)


def test_each_kind_of_detection_is_drawn_in_its_own_colour(
    frame: RgbdFrame, scene: MontessoriScene
):
    drawn = DetectionOverlay().draw(CameraView(frame), scene)

    for color in (PIECE_COLOR, HOLE_COLOR):
        assert (drawn == np.array(color.to_bgr(), dtype=np.uint8)).all(axis=2).any()


def _extent_drawn_in(
    image: np.ndarray, color: DetectionColor
) -> Tuple[int, int, int, int]:
    """
    The bounding box of everything one colour was drawn in.

    :param image: The image that was drawn on.
    :param color: The colour to look for.
    :return: Its leftmost, topmost, rightmost and bottommost pixel.
    """
    marked = (image == np.array(color.to_bgr(), dtype=np.uint8)).all(axis=2)
    rows, columns = np.nonzero(marked)
    return columns.min(), rows.min(), columns.max(), rows.max()


def test_a_standing_piece_is_boxed_around_the_top_face_the_camera_sees(
    renderer: MontessoriSceneRenderer, pipeline: MontessoriPerceptionPipeline
):
    frame = renderer.render([PlacedPiece(MontessoriShapeCategory.CUBE, x=0.58, y=0.15)])
    [piece] = pipeline.detect(frame).shapes
    view = CameraView(frame)

    drawn = DetectionOverlay().draw(view, MontessoriScene(shapes=[piece]))

    left, top, right, bottom = _extent_drawn_in(drawn, PIECE_COLOR)
    for height in (piece.surface_height, piece.top_height):
        pixels = view.to_pixels(piece.outline, height)
        assert pixels[:, 0].min() >= left
        assert pixels[:, 0].max() <= right
        assert pixels[:, 1].min() >= top
        assert pixels[:, 1].max() <= bottom


# %% cutting the view down to the workspace


def _colored_pixels(image: np.ndarray, piece: KnownPiece) -> int:
    """
    How many pixels of an image the renderer drew in one piece's own colour.

    :param image: The image to count in, blue/green/red.
    :param piece: The piece whose colour is counted.
    """
    wanted = cv2.cvtColor(
        np.array([[piece_color(piece)]], dtype=np.uint8), cv2.COLOR_HSV2BGR
    )[0, 0]
    return int((image == wanted).all(axis=2).sum())


def test_the_view_is_cut_down_to_the_workspace(
    renderer: MontessoriSceneRenderer,
    pipeline: MontessoriPerceptionPipeline,
    placed_pieces: List[PlacedPiece],
):
    frame = renderer.render(placed_pieces)

    clipped = pipeline.workspace.clip(frame.color, frame)

    assert clipped.shape[0] < frame.height
    assert clipped.shape[1] < frame.width


def test_everything_standing_in_the_workspace_stays_in_view(
    renderer: MontessoriSceneRenderer,
    pipeline: MontessoriPerceptionPipeline,
    placed_pieces: List[PlacedPiece],
):
    frame = renderer.render(placed_pieces)

    clipped = pipeline.workspace.clip(frame.color, frame)

    for placed in placed_pieces:
        assert _colored_pixels(clipped, placed.known_piece) == _colored_pixels(
            frame.color, placed.known_piece
        )


def test_the_depth_image_is_cut_down_the_same_way_as_the_colour_one(
    renderer: MontessoriSceneRenderer,
    pipeline: MontessoriPerceptionPipeline,
    placed_pieces: List[PlacedPiece],
):
    frame = renderer.render(placed_pieces)
    workspace = pipeline.workspace

    assert (
        workspace.clip(frame.depth, frame).shape
        == workspace.clip(frame.color, frame).shape[:2]
    )


def test_a_camera_that_is_not_looking_at_the_workspace_has_nothing_to_show(
    renderer: MontessoriSceneRenderer, pipeline: MontessoriPerceptionPipeline
):
    elsewhere = looking_straight_down(pipeline.table_height + 1.0)
    elsewhere[0, 3] = 100.0
    frame = RgbdFrame(
        color=np.zeros((64, 64, 3), dtype=np.uint8),
        depth=np.zeros((64, 64), dtype=np.float32),
        intrinsics=renderer.intrinsics,
        reference_frame_T_camera=elsewhere,
    )

    with pytest.raises(WorkspaceOutOfView):
        pipeline.workspace.clip(frame.color, frame)


# %% the rectified view


def test_a_point_on_the_rectified_plane_lands_on_the_pixel_that_samples_it(
    frame: RgbdFrame, pipeline: MontessoriPerceptionPipeline
):
    orthophoto = pipeline.rectify_table(frame)
    x, y = 0.6, 0.2

    [pixel] = RectifiedView(frame, orthophoto).to_pixels(
        np.array([[x, y]]), orthophoto.plane_height
    )

    assert orthophoto.region.to_world_position(*pixel) == pytest.approx((x, y))


def test_a_point_above_the_rectified_plane_lands_further_from_the_camera_axis(
    frame: RgbdFrame, pipeline: MontessoriPerceptionPipeline
):
    orthophoto = pipeline.rectify_table(frame)
    view = RectifiedView(frame, orthophoto)
    below_camera = np.array(frame.reference_frame_T_camera[:2, 3]).reshape(1, 2)
    point = below_camera + np.array([[0.2, 0.0]])

    on_plane, above_plane = (
        view.to_pixels(point, height)[0]
        for height in (orthophoto.plane_height, orthophoto.plane_height + 0.03)
    )
    [nadir] = view.to_pixels(below_camera, orthophoto.plane_height)

    assert np.linalg.norm(above_plane - nadir) > np.linalg.norm(on_plane - nadir)


def test_the_rectified_view_draws_on_the_rectified_image(
    frame: RgbdFrame, pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    orthophoto = pipeline.rectify_table(frame)

    drawn = DetectionOverlay().draw(RectifiedView(frame, orthophoto), scene)

    assert drawn.shape == orthophoto.image.shape
    assert (drawn == np.array(PIECE_COLOR.to_bgr(), dtype=np.uint8)).all(axis=2).any()


# %% how tall a piece is taken to stand


def test_a_piece_the_depth_image_cannot_resolve_stands_at_its_nominal_height(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    nominal = pipeline.piece_detector.piece_height

    for piece in scene.shapes:
        assert piece.height == pytest.approx(nominal)
        assert piece.surface_height == pytest.approx(pipeline.table_height)
        assert piece.top_height == pytest.approx(pipeline.table_height + nominal)


def test_a_hole_has_no_thickness_to_stand_above_its_own_surface(
    scene: MontessoriScene,
):
    hole = scene.holes[0]

    assert hole.top_height == hole.surface_height


# %% reading a piece's colour


def _painted(hue_saturation_value: np.ndarray) -> Orthophoto:
    """
    A rectified view of one flat patch painted a given colour.

    :param hue_saturation_value: The colour of every pixel, as a hue-saturation-value
        image.
    """
    return Orthophoto(
        image=cv2.cvtColor(hue_saturation_value, cv2.COLOR_HSV2BGR),
        region=WorkspaceRegion(
            minimum_x=0.0,
            maximum_x=0.001 * hue_saturation_value.shape[1],
            minimum_y=0.0,
            maximum_y=0.001 * hue_saturation_value.shape[0],
        ),
        plane_height=0.0,
    )


def test_a_region_is_read_as_the_colour_of_its_own_pixels():
    painted = np.zeros((8, 8, 3), dtype=np.uint8)
    painted[:, :4] = (CYAN_HUE, 200, 200)
    painted[:, 4:] = (YELLOW_HUE, 200, 200)
    region = np.zeros((8, 8), dtype=np.uint8)
    region[:, :4] = 255

    assert SurfaceColors().measure_hue(_painted(painted), region) == CYAN_HUE


def test_a_washed_out_region_carries_no_colour_to_read():
    colors = SurfaceColors()
    painted = np.zeros((8, 8, 3), dtype=np.uint8)
    painted[:, :] = (CYAN_HUE, colors.minimum_hue_saturation - 1, 250)

    assert colors.measure_hue(_painted(painted), np.full((8, 8), 255, np.uint8)) is None


def test_hue_is_measured_the_short_way_round_the_colour_circle():
    assert hue_distance(2, HUE_RANGE - 3) == 5
    assert hue_distance(20, 25) == 5


# %% recognising a piece and how it is turned

TURNABLE_PIECES = [piece for piece in KNOWN_PIECES if piece.rotation_period is not None]
"""
The pieces a turn can be told on at all, so the ones a period means something for.
"""

DRAWN_TABLE_COLOR = (60, 60, 60)
"""
Blue, green and red of the bare table a test draws a piece's top face onto.
"""

DRAWN_PIECE_COLOR = (200, 220, 230)
"""
Blue, green and red of the top face a test draws.
"""

CLEAN_FIT_AGREEMENT = 0.75
"""
How well a piece laid exactly over the outline it was drawn at agrees with it.

Short of one because an edge found in a millimetre-resolution picture lies about a pixel
off the line that drew it, which costs a share of every point of the outline.
"""


def _piece_id(piece: KnownPiece) -> str:
    return str(piece.category)


def _drawn(
    outline: np.ndarray, center: Tuple[float, float] = (0.0, 0.0)
) -> EdgeDistances:
    """
    The edges of a rectified view holding one outline drawn on a bare table.

    :param outline: The outline to draw, as ``(n, 2)`` ``(x, y)`` points in metres about
        its own centre.
    :param center: Where in the world frame to draw it, in metres.
    :return: The edges seen in that view.
    """
    reach = 0.1
    region = WorkspaceRegion(
        minimum_x=center[0] - reach,
        maximum_x=center[0] + reach,
        minimum_y=center[1] - reach,
        maximum_y=center[1] + reach,
    )
    image = np.zeros((region.height_in_pixels, region.width_in_pixels, 3), np.uint8)
    image[:, :] = DRAWN_TABLE_COLOR
    corners = np.stack(
        [
            (outline[:, 0] + center[0] - region.minimum_x) / region.resolution,
            (outline[:, 1] + center[1] - region.minimum_y) / region.resolution,
        ],
        axis=1,
    )
    cv2.fillPoly(image, [np.round(corners).astype(np.int32)], DRAWN_PIECE_COLOR)
    return EdgeDistances.of(Orthophoto(image=image, region=region, plane_height=0.0))


@pytest.mark.parametrize("piece", KNOWN_PIECES, ids=_piece_id)
def test_each_known_piece_is_recognised_from_its_own_outline(piece: KnownPiece):
    matcher = PieceMatcher()
    placed = math.radians(17)

    match = matcher.match(_drawn(piece.turned_outline(placed)), (0.0, 0.0), piece.hue)

    assert match.piece.category is piece.category
    assert match.outline_agreement > CLEAN_FIT_AGREEMENT
    assert match.yaw == pytest.approx(
        piece.smallest_equivalent_turn(placed), abs=matcher.angle_step
    )


@pytest.mark.parametrize("piece", TURNABLE_PIECES, ids=_piece_id)
def test_a_piece_turned_by_its_own_period_looks_untouched(piece: KnownPiece):
    matcher = PieceMatcher()

    match = matcher.match(
        _drawn(piece.turned_outline(piece.rotation_period)), (0.0, 0.0), piece.hue
    )

    assert match.piece.category is piece.category
    assert match.yaw == pytest.approx(0.0, abs=matcher.angle_step)


def test_an_orientation_is_reported_as_the_smallest_turn_that_reaches_it():
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    matcher = PieceMatcher()
    placed = cube.rotation_period - math.radians(10)

    match = matcher.match(_drawn(cube.turned_outline(placed)), (0.0, 0.0), cube.hue)

    assert match.yaw == pytest.approx(math.radians(-10), abs=matcher.angle_step)


@pytest.mark.parametrize("piece", KNOWN_PIECES, ids=_piece_id)
def test_a_piece_is_found_where_it_stands_and_not_where_it_was_looked_for(
    piece: KnownPiece,
):
    """
    A piece read together with its reflection is seeded from the middle of the two, so
    the fit has to walk to the piece itself.
    """
    matcher = PieceMatcher()
    stands_at = (0.6, 0.2)
    looked_for = (stands_at[0] - 0.012, stands_at[1] + 0.009)

    match = matcher.match(_drawn(piece.outline, stands_at), looked_for, piece.hue)

    assert match.center == pytest.approx(stands_at, abs=matcher.step)


def test_a_piece_is_never_recognised_as_one_of_the_other_colour():
    cylinder = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CYLINDER]
    matcher = PieceMatcher()
    edges = _drawn(cylinder.outline)

    recognised = matcher.match(edges, (0.0, 0.0), cylinder.hue)
    seen_yellow = matcher.match(edges, (0.0, 0.0), YELLOW_HUE)

    assert recognised.piece.category is MontessoriShapeCategory.CYLINDER
    assert seen_yellow is None or seen_yellow.piece.hue == YELLOW_HUE


def test_a_colour_no_piece_wears_leaves_nothing_to_recognise():
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    unworn = (CYAN_HUE + YELLOW_HUE) // 2

    assert PieceMatcher().match(_drawn(cube.outline), (0.0, 0.0), unworn) is None


def test_edges_no_known_piece_follows_are_refused():
    reach = max(piece.radius for piece in KNOWN_PIECES) * 1.5
    sprawl = np.array(
        [[-reach, -reach], [reach, -reach], [reach, reach], [-reach, reach]]
    )

    assert PieceMatcher().match(_drawn(sprawl), (0.0, 0.0), CYAN_HUE) is None


def test_an_outline_with_no_colour_to_read_is_recognised_by_its_shape_alone():
    triangle = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM]

    match = PieceMatcher().match(_drawn(triangle.outline), (0.0, 0.0), None)

    assert match.piece.category is MontessoriShapeCategory.TRIANGULAR_PRISM


def test_a_reflection_around_a_piece_does_not_move_where_it_is_recognised():
    """
    The table throws a diffuse copy of each piece back at the camera, which segmenting
    by colour takes in along with the piece; the edges the fit follows are the piece's
    own.
    """
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    stands_at = (0.6, 0.2)
    edges = _drawn(cube.outline, stands_at)

    match = PieceMatcher().match(edges, (stands_at[0] - 0.015, stands_at[1]), cube.hue)

    assert match.piece.category is MontessoriShapeCategory.CUBE
    assert match.center == pytest.approx(stands_at, abs=0.002)


@pytest.mark.parametrize("piece", TURNABLE_PIECES, ids=_piece_id)
def test_a_piece_is_detected_at_the_angle_it_was_placed(
    renderer: MontessoriSceneRenderer,
    pipeline: MontessoriPerceptionPipeline,
    piece: KnownPiece,
):
    placed = math.radians(25)
    frame = renderer.render([PlacedPiece(piece.category, x=0.58, y=0.15, yaw=placed)])

    [detected] = pipeline.detect(frame).shapes

    assert detected.category is piece.category
    assert detected.yaw == pytest.approx(
        piece.smallest_equivalent_turn(placed), abs=math.radians(4)
    )


REFLECTION_SPREAD = 0.015
"""
How far this lab's table smears a piece's colour around it, in metres.

Measured off the outlines colour alone gives on the real table, where a twenty by forty
millimetre piece came out forty-seven by fifty-one; drawing the smear this wide brings
the rendered outlines to the same size.
"""


def test_a_piece_is_recognised_through_the_reflection_the_table_throws(
    pipeline: MontessoriPerceptionPipeline, placed_pieces: List[PlacedPiece]
):
    reflecting = MontessoriSceneRenderer(reflection_spread=REFLECTION_SPREAD)

    scene = pipeline.detect(reflecting.render(placed_pieces))

    assert {detected.category for detected in scene.shapes} == {
        placed.category for placed in placed_pieces
    }


def test_a_piece_is_reported_where_it_stands_and_not_where_its_reflection_reaches(
    pipeline: MontessoriPerceptionPipeline, placed_pieces: List[PlacedPiece]
):
    reflecting = MontessoriSceneRenderer(reflection_spread=REFLECTION_SPREAD)

    scene = pipeline.detect(reflecting.render(placed_pieces))

    stands_at = {placed.category: (placed.x, placed.y) for placed in placed_pieces}
    for detected in scene.shapes:
        assert detected.pose.to_position().to_np()[:2] == pytest.approx(
            stands_at[detected.category], abs=0.003
        )


def test_a_piece_only_half_in_view_is_not_reported(
    renderer: MontessoriSceneRenderer, placed_pieces: List[PlacedPiece]
):
    cut_through_a_piece = MontessoriPerceptionPipeline(
        region=WorkspaceRegion(
            minimum_x=0.35,
            maximum_x=1.35,
            minimum_y=placed_pieces[0].y,
            maximum_y=0.75,
        ),
        table_height=renderer.table_height,
        board_height=renderer.board_height,
    )

    scene = cut_through_a_piece.detect(renderer.render(placed_pieces))

    assert placed_pieces[0].category not in {
        detected.category for detected in scene.shapes
    }


def test_a_cleanly_seen_piece_reports_how_closely_it_fitted(scene: MontessoriScene):
    for detected in scene.shapes:
        assert detected.outline_agreement > PieceMatcher().minimum_agreement
