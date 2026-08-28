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
from typing_extensions import Dict, List

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
)
from experiments.montessori.perception.footprint import (
    CrossSectionClassifier,
    Footprint,
)
from experiments.montessori.perception.orthophoto import (
    OrthophotoProjector,
    WorkspaceRegion,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_source import FixedScene, PerceivedObjects
from experiments.montessori.perception.viewer import (
    CameraFrameViewer,
    CameraWindow,
    ImageDisplay,
    colorize_depth,
    scale_to_fit,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from krrood.entity_query_language.factories import a, the

from .dataset.montessori_scene_renderer import MontessoriSceneRenderer, PlacedPiece

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


def test_an_image_narrower_than_the_window_is_drawn_at_its_own_size():
    image = np.zeros((4, 8, 3), dtype=np.uint8)

    assert scale_to_fit(image, 16) is image


def test_a_wide_image_is_shrunk_to_the_window_keeping_its_proportions():
    image = np.zeros((100, 400, 3), dtype=np.uint8)

    scaled = scale_to_fit(image, 200)

    assert scaled.shape == (50, 200, 3)


def test_the_viewer_draws_the_newest_frame_it_was_shown():
    display = RecordingDisplay()
    viewer = CameraFrameViewer(display=display)
    viewer.show(np.zeros((2, 2, 3), dtype=np.uint8), np.zeros((2, 2), dtype=np.float32))
    viewer.show(
        np.full((2, 2, 3), 7, dtype=np.uint8), np.ones((2, 2), dtype=np.float32)
    )

    viewer.refresh()

    assert display.drawn[CameraWindow.COLOR][0, 0].tolist() == [7, 7, 7]
    assert set(display.drawn) == {CameraWindow.COLOR, CameraWindow.DEPTH}


def test_the_viewer_draws_nothing_before_a_frame_has_arrived():
    display = RecordingDisplay()

    CameraFrameViewer(display=display).refresh()

    assert display.drawn == {}
    assert display.waits


def test_closing_the_viewer_takes_its_windows_off_screen():
    display = RecordingDisplay()

    CameraFrameViewer(display=display).close()

    assert display.closed
