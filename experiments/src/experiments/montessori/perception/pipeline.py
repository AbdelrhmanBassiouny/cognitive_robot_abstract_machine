"""
Find the Montessori board, its holes, and the loose pieces in one RGB-D frame.

The scene splits into two horizontal surfaces, and each is rectified and searched on its
own: the table, and the board's raised lid, which carries the holes and takes a loose
piece just as the table does. Rectifying each surface at its own height is what keeps
what lies on it accurate -- read off the table's plane instead, the lid's outline is
magnified by the ratio of the two camera distances, which walks the outer holes several
centimetres away from where they are and pushes a piece standing on the lid out of its
own silhouette altogether.

Colour says where to look and edges say what is there. The pieces are brightly coloured
and the holes are dark openings in pale wood, both of which separate cleanly by
saturation and brightness, but the table under them is polished metal that throws a
coloured reflection of every piece back at the camera, so a coloured region is only ever
a place worth searching. Which piece stands there is settled by fitting the pieces this
set contains to the edges seen around that place. Depth is asked how tall a piece stands
and usually cannot say: the same reflections leave the depth image with large dropouts
and centimetre-scale noise, far too coarse to measure a thirty millimetre piece.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import cv2
import numpy as np
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import (
    BoardMissingFromWorld,
    LookHasNoReferenceFrame,
)
from experiments.montessori.perception.footprint import (
    CrossSectionClassifier,
    Footprint,
    FootprintClassifier,
)
from experiments.montessori.perception.hypotheses import (
    BelievedPlace,
    PieceHypothesis,
)
from experiments.montessori.perception.occupancy import Occupancy, OccupiedVolume
from experiments.montessori.perception.orthophoto import (
    Orthophoto,
    OrthophotoProjector,
    WorkspaceBox,
    WorkspaceRegion,
)
from experiments.montessori.perception.piece_matcher import PieceMatcher
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import (
    HUE_RANGE,
    HUE_TOLERANCE,
    KNOWN_PIECE_BY_CATEGORY,
    hues_of,
    pieces_colored,
)
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from experiments.montessori.world import BOARD_SCALE
from krrood.patterns.belief_source import BeliefSource
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import (
    Color,
    VolumetricBoundingBox,
)
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

# %% segmentation


@dataclass(frozen=True)
class SurfaceColors:
    """
    How the scene's surfaces separate in hue-saturation-value, measured off the table
    this runs on.

    The table is bare metal and so is almost colourless, while the wooden board and the
    plastic pieces both carry real colour; the holes are openings that fall into shadow
    and so are much darker than the lid around them.
    """

    minimum_saturation: int = 45
    """
    Saturation at or above which a pixel belongs to an object rather than to the bare
    table.

    The table reads around 13 and drops towards 6 under a specular highlight, while the
    palest thing standing on it, the board's own wood, reads around 53. Sitting just
    under that keeps the whole board and every piece while rejecting the coloured fringe
    that the specular streaks running down the table leave along their edges, which
    otherwise merges into a piece standing near one and inflates its outline.
    """

    minimum_value: int = 60
    """
    Brightness at or above which a coloured pixel belongs to an object at all, rather
    than to unlit background.

    Deliberately low: how dark a hole reads against its own lid varies with the light
    falling on the board, so the holes are cut out by comparing them against that lid
    (see :meth:`dark_mask`) rather than against a fixed brightness.
    """

    def surface_mask(self, orthophoto: Orthophoto) -> np.ndarray:
        """
        Mark the coloured surfaces in a rectified image, separating them from the bare
        table.

        :param orthophoto: The rectified image to segment.
        :return: A ``uint8`` mask, 255 on a surface and 0 elsewhere.
        """
        hue_saturation_value = orthophoto.hue_saturation_value
        mask = (
            (hue_saturation_value[:, :, 1] >= self.minimum_saturation)
            & (hue_saturation_value[:, :, 2] >= self.minimum_value)
            & orthophoto.observed
        )
        return mask.astype(np.uint8) * 255

    minimum_hue_saturation: int = 30
    """
    Saturation at or above which a pixel's hue is worth reading.

    Lower than :attr:`minimum_saturation`, which has to tell a coloured surface from a
    colourless one on its own: a pixel held against the pieces' own colours need only be
    colourful enough for its hue to mean something, and the pale pieces in this set wash
    out towards white where they catch the light.
    """

    def piece_mask(self, orthophoto: Orthophoto, hue: int) -> np.ndarray:
        """
        Mark the pixels wearing one of the loose pieces' colours.

        A piece is picked out by the colour it is rather than by standing out from the
        surface under it, because that surface is whatever the table happens to be
        covered with: bare metal has no colour to be told apart from, but paper laid
        over it to stop the reflections has plenty.

        One colour is marked at a time, and the pieces are searched for a colour at a
        time, because a surface can wear a piece's colour itself -- the board's wooden
        lid reads within a couple of hues of the amber prisms. Marking every piece
        colour at once merges a piece standing on such a surface into the surface's own
        region, where it has no outline of its own left to measure.

        :param orthophoto: The rectified image to segment.
        :param hue: The colour to mark, as OpenCV reports hue.
        :return: A ``uint8`` mask, 255 on that colour and 0 elsewhere.
        """
        hue_saturation_value = orthophoto.hue_saturation_value
        measured = hue_saturation_value[:, :, 0].astype(int)
        apart = np.abs(measured - hue)
        mask = (
            (np.minimum(apart, HUE_RANGE - apart) <= HUE_TOLERANCE)
            & (hue_saturation_value[:, :, 1] >= self.minimum_hue_saturation)
            & (hue_saturation_value[:, :, 2] >= self.minimum_value)
            & orthophoto.observed
        )
        return mask.astype(np.uint8) * 255

    def color_mask(self, orthophoto: Orthophoto, color: Color) -> np.ndarray:
        """
        Mark every pixel wearing a colour, whichever of this set's hues that colour is.

        The pieces are still searched one hue at a time, for the reason
        :meth:`piece_mask` records; this is the whole of what a look asked for one
        colour has left to read, which is what a viewer draws.

        :param orthophoto: The rectified image to segment.
        :param color: The colour to mark.
        :return: A ``uint8`` mask, 255 on that colour and 0 elsewhere.
        """
        marked = np.zeros(orthophoto.image.shape[:2], dtype=np.uint8)
        for hue in hues_of(pieces_colored(color)):
            marked = cv2.bitwise_or(marked, self.piece_mask(orthophoto, hue))
        return marked

    def measure_hue(self, orthophoto: Orthophoto, region: np.ndarray) -> Optional[int]:
        """
        Read the colour one region of a rectified image is.

        Only the coloured pixels are read: a specular highlight washes a lit face towards
        white, where the hue a pixel reports is noise. A piece's reflection in the table
        carries the piece's own colour, so a region that has taken some of that in still
        reports the colour of the piece.

        :param orthophoto: The rectified image the region was found in.
        :param region: Mask of the region to read, 255 inside it and 0 outside.
        :return: The middle of its coloured pixels' hue, or None where it has none.
        """
        hue_saturation_value = orthophoto.hue_saturation_value
        colored = (region > 0) & (
            hue_saturation_value[:, :, 1] >= self.minimum_hue_saturation
        )
        if not colored.any():
            return None
        return int(np.median(hue_saturation_value[:, :, 0][colored]))

    @staticmethod
    def dark_mask(orthophoto: Orthophoto, region: np.ndarray) -> np.ndarray:
        """
        Mark the darker part of one surface, which for the board's lid is its holes.

        The split is chosen by Otsu's method over that surface alone, so it follows
        however brightly the board happens to be lit instead of assuming a level.

        :param orthophoto: The rectified image the surface was found in.
        :param region: Mask of the surface to split, 255 inside it and 0 outside.
        :return: A ``uint8`` mask, 255 on the darker part of the surface and 0
            elsewhere.
        """
        brightness = orthophoto.hue_saturation_value[:, :, 2]
        inside = brightness[region > 0]
        if inside.size == 0:
            return np.zeros_like(region)
        threshold, _ = cv2.threshold(
            inside, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )
        return (((brightness < threshold) & (region > 0)).astype(np.uint8)) * 255


_CLOSING_KERNEL = np.ones((5, 5), np.uint8)
"""
Structuring element that bridges the one- and two-pixel gaps a rectified edge picks up,
without closing the smallest hole on the board.
"""

_OPENING_KERNEL = np.ones((3, 3), np.uint8)
"""
Structuring element that removes isolated speckles left by sensor noise.
"""


def _filled(contour: np.ndarray, orthophoto: Orthophoto) -> np.ndarray:
    """
    The area one contour encloses, as a mask over the image it was found in.

    :param contour: The contour, in rectified pixels.
    :param orthophoto: The rectified view it was found in.
    :return: A ``uint8`` mask, 255 inside the contour and 0 outside.
    """
    region = np.zeros(orthophoto.image.shape[:2], dtype=np.uint8)
    cv2.drawContours(region, [contour], -1, 255, cv2.FILLED)
    return region


def _wholly_within(contour: np.ndarray, orthophoto: Orthophoto) -> bool:
    """
    Whether a contour lies inside the rectified view rather than running off its edge.

    :param contour: The contour, in rectified pixels.
    :param orthophoto: The rectified view it was found in.
    """
    height, width = orthophoto.image.shape[:2]
    pixels = contour.reshape(-1, 2)
    return bool(
        (pixels[:, 0] > 0).all()
        and (pixels[:, 0] < width - 1).all()
        and (pixels[:, 1] > 0).all()
        and (pixels[:, 1] < height - 1).all()
    )


def _clean(mask: np.ndarray) -> np.ndarray:
    """
    Bridge the gaps a rectified edge picks up and drop isolated speckles.

    :param mask: The mask to clean.
    :return: The cleaned mask.
    """
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _CLOSING_KERNEL)
    return cv2.morphologyEx(closed, cv2.MORPH_OPEN, _OPENING_KERNEL)


# %% size expectations


@dataclass(frozen=True)
class SizeRange:
    """
    The range of outline areas a kind of thing is allowed to have.
    """

    minimum_area: float
    """
    Smallest area, in square metres, an outline may have and still be considered.
    """

    maximum_area: float
    """
    Largest area, in square metres, an outline may have and still be considered.
    """

    def admits(self, footprint: Footprint) -> bool:
        """
        Whether an outline's area falls in this range.

        :param footprint: The measured outline.
        """
        return self.minimum_area <= footprint.area <= self.maximum_area


LOOSE_PIECE_SIZE = SizeRange(minimum_area=0.0002, maximum_area=0.004)
"""
Area a loose Montessori piece's footprint may cover, spanning roughly a fourteen to a
sixty millimetre square -- wide enough for every piece in the set and narrow enough to
reject a hand reaching into the scene.
"""

HOLE_SIZE = SizeRange(minimum_area=0.00006, maximum_area=0.003)
"""
Area a hole in the board's lid may cover.

The lower bound sits below the narrowest hole, the disk's five by forty-eight millimetre
slot, and above the slivers of shadow that fall along the lid's own edges.
"""


# %% detectors


@dataclass
class BoardDetector:
    """
    Finds the shape-sorting board and the holes in its lid, in a view rectified onto
    that lid.

    The board is picked out by the holes themselves rather than by being the largest
    thing in view: an arm reaching over the table is both larger and just as strongly
    coloured, but only the board is a surface with several openings cut through it.
    """

    classifier: FootprintClassifier = field(default_factory=CrossSectionClassifier)
    """
    Decides which shape each hole is cut for.
    """

    colors: SurfaceColors = field(default_factory=SurfaceColors)
    """
    How the lid and its holes separate by colour.
    """

    hole_size: SizeRange = HOLE_SIZE
    """
    Area a hole's outline may cover.
    """

    minimum_hole_count: int = 3
    """
    How many holes a surface must have cut through it to be taken for the board.
    """

    minimum_lid_area: float = 0.01
    """
    Area, in square metres, a surface must cover before its holes are looked for.

    The board's lid covers about three hundred square centimetres; this keeps the search
    off the loose pieces, whose own shading would otherwise split into hole-sized dark
    patches.
    """

    board_footprint: Tuple[float, float] = (float(BOARD_SCALE.x), float(BOARD_SCALE.y))
    """
    How large the board's lid is, in metres, taken from the same board the demo builds
    its world from.

    Sets how far apart two holes may lie and still belong to the same board.
    """

    def detect(
        self,
        orthophoto: Orthophoto,
        reference_frame: Optional[KinematicStructureEntity],
    ) -> Optional[MontessoriBoardDetection]:
        """
        Find the board in a view rectified onto its lid.

        :param orthophoto: The rectified view of the lid's plane.
        :param reference_frame: Frame the resulting poses are expressed in.
        :return: The board and its holes, or None if no surface in view had enough holes
            cut through it.
        """
        mask = _clean(self.colors.surface_mask(orthophoto))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best: List[ShapeSortingHoleDetection] = []
        for contour in contours:
            footprint = Footprint.from_contour(contour, orthophoto.region.resolution)
            if footprint.area < self.minimum_lid_area:
                continue
            holes = self._board_sized_cluster(
                self._holes_within(contour, orthophoto, reference_frame)
            )
            if len(holes) > len(best):
                best = holes
        if len(best) < self.minimum_hole_count:
            return None
        return self._board_around(best, orthophoto, reference_frame)

    def _holes_within(
        self,
        surface: np.ndarray,
        orthophoto: Orthophoto,
        reference_frame: Optional[KinematicStructureEntity],
    ) -> List[ShapeSortingHoleDetection]:
        """
        Recognise the holes cut through one candidate surface.

        The surface is filled in first, so that a hole is a dark patch within a solid
        region rather than a gap that the surface's own outline has to enclose; a hole
        broken open at the board's edge would otherwise be missed entirely.

        :param surface: The candidate surface's own contour, in rectified pixels.
        :param orthophoto: The rectified view it was found in.
        :param reference_frame: Frame the resulting poses are expressed in.
        :return: One detection per hole that is the right size and a recognisable shape.
        """
        region = _filled(surface, orthophoto)
        # Left unopened on purpose: the narrowest hole on the board is five millimetres
        # across, which the speckle-removing kernel would eat entirely. Slivers are
        # rejected by area instead, in :attr:`hole_size`.
        dark = self.colors.dark_mask(orthophoto, region)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        holes = []
        for contour in contours:
            footprint = Footprint.from_contour(contour, orthophoto.region.resolution)
            if not self.hole_size.admits(footprint):
                continue
            category = self.classifier.classify(footprint)
            if category is None:
                continue
            holes.append(
                ShapeSortingHoleDetection(
                    pose=self._pose(contour, orthophoto, reference_frame, footprint),
                    footprint=footprint,
                    outline=_to_world_outline(contour, orthophoto),
                    category=category,
                )
            )
        return holes

    def _board_sized_cluster(
        self, holes: List[ShapeSortingHoleDetection]
    ) -> List[ShapeSortingHoleDetection]:
        """
        Keep only the holes that could belong to one board.

        A surface that has merged with an arm reaching over the table carries dark
        patches scattered far beyond any board, so the holes are grouped by how close
        together they lie and only the largest group that still fits on a board is kept.

        :param holes: Every hole-shaped patch found on one surface.
        :return: The largest group of them that fits within one board's lid.
        """
        if not holes:
            return []
        centers = np.array([_position_of(hole) for hole in holes])
        groups = [self._grow_from(seed, holes, centers) for seed in centers]
        return max(groups, key=len)

    def _grow_from(
        self,
        seed: np.ndarray,
        holes: List[ShapeSortingHoleDetection],
        centers: np.ndarray,
    ) -> List[ShapeSortingHoleDetection]:
        """
        Grow a group outwards from one hole, taking in the next nearest hole for as long
        as the group still fits on a single lid.

        :param seed: World-frame ``(x, y)`` of the hole to grow from.
        :param holes: Every hole-shaped patch found on one surface.
        :param centers: Those holes' world-frame ``(x, y)``, in the same order.
        :return: The grown group.
        """
        order = np.argsort(np.linalg.norm(centers - seed, axis=1))
        group: List[ShapeSortingHoleDetection] = []
        for index in order:
            candidate = group + [holes[index]]
            if self._fits_on_a_lid(candidate):
                group = candidate
        return group

    def _fits_on_a_lid(self, holes: List[ShapeSortingHoleDetection]) -> bool:
        """
        Whether a group of holes is packed tightly enough to have come from one lid.

        :param holes: The group to check.
        """
        centers = np.array([_position_of(hole) for hole in holes], dtype=np.float32)
        if len(centers) < 2:
            return len(centers) > 0
        (_, _), (first_side, second_side), _ = cv2.minAreaRect(centers)
        span = sorted((first_side, second_side))
        return all(
            measured <= allowed
            for measured, allowed in zip(span, sorted(self.board_footprint))
        )

    def _board_around(
        self,
        holes: List[ShapeSortingHoleDetection],
        orthophoto: Orthophoto,
        reference_frame: Optional[KinematicStructureEntity],
    ) -> MontessoriBoardDetection:
        """
        Build the board that carries a group of holes.

        The lid's own edges are not used: they run into whatever the board is standing
        against, and the holes are laid out symmetrically about the lid's centre anyway,
        so the board is reported as a lid-sized rectangle centred on and aligned with
        its holes.

        :param holes: The holes the board carries.
        :param orthophoto: The rectified view of the lid's plane.
        :param reference_frame: Frame the resulting pose is expressed in.
        :return: The board.
        """
        centers = np.array([_position_of(hole) for hole in holes], dtype=np.float32)
        center = centers.mean(axis=0)
        (_, _), (_, _), angle_in_degrees = cv2.minAreaRect(centers)
        yaw = math.radians(angle_in_degrees)
        width, length = sorted(self.board_footprint)
        outline = cv2.boxPoints(
            ((float(center[0]), float(center[1])), (width, length), angle_in_degrees)
        )
        return MontessoriBoardDetection(
            pose=Pose.from_xyz_rpy(
                float(center[0]),
                float(center[1]),
                orthophoto.plane_height,
                yaw=yaw,
                reference_frame=reference_frame,
            ),
            footprint=Footprint(
                area=width * length,
                width=width,
                length=length,
                fill_ratio=1.0,
                corner_count=4,
                yaw=(yaw + math.pi / 2) % math.pi - math.pi / 2,
            ),
            outline=np.asarray(outline, dtype=float),
            holes=holes,
            lid_height=orthophoto.plane_height,
        )

    @staticmethod
    def _pose(
        contour: np.ndarray,
        orthophoto: Orthophoto,
        reference_frame: Optional[KinematicStructureEntity],
        footprint: Optional[Footprint] = None,
    ) -> Pose:
        """
        Where a contour's centre sits on the rectified plane.

        :param contour: The contour, in rectified pixels.
        :param orthophoto: The rectified view it was found in.
        :param reference_frame: Frame the pose is expressed in.
        :param footprint: The contour's own measurements, remeasured if not given.
        :return: The pose of the contour's centre, on the rectified plane.
        """
        if footprint is None:
            footprint = Footprint.from_contour(contour, orthophoto.region.resolution)
        center = orthophoto.contour_center(contour)
        return Pose.from_xyz_rpy(
            center.x,
            center.y,
            orthophoto.plane_height,
            yaw=footprint.yaw,
            reference_frame=reference_frame,
        )


@dataclass
class LoosePieceDetector(BeliefSource):
    """
    Finds the loose Montessori pieces in a view rectified onto the surface they rest on.
    """

    matcher: PieceMatcher = field(default_factory=PieceMatcher)
    """
    Recognises which piece stands where, and how far it is turned.
    """

    colors: SurfaceColors = field(default_factory=SurfaceColors)
    """
    How a piece separates from the bare table by colour.
    """

    piece_size: SizeRange = LOOSE_PIECE_SIZE
    """
    Area a piece's outline may cover.
    """

    piece_height: float = 0.03
    """
    Roughly how tall a loose piece stands, in metres, used to cancel the parallax that
    would otherwise stretch its outline (see :meth:`detect`) and reported as a piece's
    own height wherever the depth image cannot resolve it.

    The pieces in this set stand between twenty and thirty millimetres tall, and the
    cancellation is forgiving of the difference.
    """

    hue_tolerance: int = HUE_TOLERANCE
    """
    How far a measured colour may sit from a piece's own before a colour seen at a place
    stops suggesting that piece.
    """

    def detect(
        self,
        orthophoto: Orthophoto,
        top_orthophoto: Orthophoto,
        frame: RgbdFrame,
        reference_frame: Optional[KinematicStructureEntity],
        search: SurfaceSearch,
        expected: Sequence[PieceHypothesis] = (),
        color: Optional[Color] = None,
    ) -> List[MontessoriShapeDetection]:
        """
        Find the pieces resting on one surface, by evaluating what is expected there.

        Every hypothesis this surface owns is fitted against the edges of the view
        rectified onto a piece's top, where a piece's own top face lies at exactly its
        footprint, undistorted and sharply bounded. A colour seen in the picture is one
        source of hypotheses; whatever the caller already believes is another, and a
        piece is found at a place it was expected whether or not any colour separated it
        from what it rests on.

        :param orthophoto: The rectified view of the surface's own plane.
        :param top_orthophoto: The rectified view of the plane a piece's top stands on.
        :param frame: The camera data, for measuring how tall each piece stands.
        :param reference_frame: Frame the resulting poses are expressed in.
        :param search: The surface being searched, which settles what rests on it.
        :param expected: What is believed to be on this surface already, from anything
            other than this picture.
        :param color: The colour the piece sought wears, or None for any of them. A
            colour narrows what is marked and what is fitted, so a look asked for one
            reads less of the picture rather than discarding what it read.
        :return: One detection per recognised piece.
        """
        edges = EdgeDistances.of(top_orthophoto)
        pieces = []
        for hypothesis in [
            *self._colors_seen_in(orthophoto, top_orthophoto, search, color),
            *expected,
        ]:
            if not self._is_on_this_surface(hypothesis, search):
                continue
            piece = self._piece_at(
                hypothesis, orthophoto, edges, frame, reference_frame, search
            )
            if piece is not None:
                pieces.append(piece)
        return pieces

    @staticmethod
    def _is_on_this_surface(hypothesis: PieceHypothesis, search: SurfaceSearch) -> bool:
        """
        Whether the piece a hypothesis expects rests on the surface being searched.

        A belief names the surface it is about, and a position on this plane belongs to
        this surface only where nothing standing on it reaches -- which is what the
        surface's own pass reports instead.

        :param hypothesis: What is expected, and where.
        :param search: The surface being searched.
        """
        return hypothesis.place.surface == search.surface.name and search.claims(
            hypothesis.place.center.x, hypothesis.place.center.y
        )

    def _colors_seen_in(
        self,
        orthophoto: Orthophoto,
        top_orthophoto: Orthophoto,
        search: SurfaceSearch,
        color: Optional[Color] = None,
    ) -> List[PieceHypothesis]:
        """
        What the colours in this picture suggest is standing on the surface.

        A piece seen from off to one side hides none of itself but shows its sides as
        well as its top, so its silhouette rectified onto the surface it rests on is the
        piece's footprint together with its top face pushed away from the point directly
        below the camera -- on this table that stretches a thirty millimetre piece by
        nearly twenty. Rectifying onto the piece's top instead pushes the *base* the
        other way, so what the two silhouettes agree on is roughly the footprint, and
        roughly is as far as colour gets on a table that reflects each piece back at the
        camera. It is enough to say where to look.

        An outline that reaches the edge of the region is passed over: only part of it
        was seen, so neither how large it is nor what colour it wears was measured.

        :param orthophoto: The rectified view of the surface's own plane.
        :param top_orthophoto: The rectified view of the plane a piece's top stands on.
        :param search: The surface being searched.
        :param color: The colour the piece sought wears, or None for any of them.
        """
        seen = []
        for hue in hues_of(pieces_colored(color)):
            for contour in self._outlines_wearing(hue, orthophoto, top_orthophoto):
                footprint = Footprint.from_contour(
                    contour, orthophoto.region.resolution
                )
                if not self.piece_size.admits(footprint):
                    continue
                if not _wholly_within(contour, orthophoto):
                    continue
                seen.append(
                    PieceHypothesis.of_color(
                        place=BelievedPlace(
                            surface=search.surface.name,
                            center=orthophoto.contour_center(contour),
                        ),
                        hue=self.colors.measure_hue(
                            orthophoto, _filled(contour, orthophoto)
                        ),
                        source=self,
                        hue_tolerance=self.hue_tolerance,
                    )
                )
        return seen

    def _outlines_wearing(
        self, hue: int, orthophoto: Orthophoto, top_orthophoto: Orthophoto
    ) -> List[np.ndarray]:
        """
        The outlines one colour covers on both of a surface's rectified views.

        :param hue: The colour to look for, as OpenCV reports hue.
        :param orthophoto: The rectified view of the surface's own plane.
        :param top_orthophoto: The rectified view of the plane a piece's top stands on.
        """
        mask = _clean(
            cv2.bitwise_and(
                self.colors.piece_mask(orthophoto, hue),
                self.colors.piece_mask(top_orthophoto, hue),
            )
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return list(contours)

    def _piece_at(
        self,
        hypothesis: PieceHypothesis,
        orthophoto: Orthophoto,
        edges: EdgeDistances,
        frame: RgbdFrame,
        reference_frame: Optional[KinematicStructureEntity],
        search: SurfaceSearch,
    ) -> Optional[MontessoriShapeDetection]:
        """
        Recognise the piece a hypothesis expects, if the picture bears it out.

        The outline the fit settled on is what the piece is measured by, rather than the
        colour blob a hypothesis may have come from: it is the piece's own footprint,
        and it is the only outline a hypothesis expected from anything but a colour has.

        :param hypothesis: What is expected, and where it is believed to be.
        :param orthophoto: The rectified view of the surface's own plane.
        :param edges: How far each point of the top view lies from an edge the camera
            saw, which is what a piece's own outline is fitted to.
        :param frame: The camera data, for measuring how tall the piece stands.
        :param reference_frame: Frame the resulting pose is expressed in.
        :param search: The surface being searched.
        :return: The piece, or None where nothing expected follows the edges there.
        """
        match = self.matcher.match(edges, hypothesis)
        if match is None:
            return None
        outline = match.piece.turned_outline(match.yaw) + np.array(
            [match.center.x, match.center.y]
        )
        fitted = _to_rectified_contour(outline, orthophoto)
        height = _measure_height(fitted, orthophoto, frame, self.piece_height)
        return MontessoriShapeDetection(
            pose=Pose.from_xyz_rpy(
                match.center.x,
                match.center.y,
                orthophoto.plane_height + height / 2,
                yaw=match.yaw,
                reference_frame=reference_frame,
            ),
            footprint=Footprint.from_contour(fitted, orthophoto.region.resolution),
            outline=outline,
            category=match.piece.category,
            height=height,
            outline_agreement=match.outline_agreement,
            supporting_surface=search.surface.name,
            hypothesis=hypothesis,
        )


# %% measuring how tall a piece stands

_MINIMUM_DEPTH_SAMPLES = 50
"""
How many depth readings a piece's top must return before its height is trusted.

Below this the reflective table around it dominates whatever the sensor did return.
"""

_HEIGHT_SAMPLE_STRIDE = 3
"""
Sample every third rectified pixel of a piece's interior, which keeps the reprojection
cheap while still leaving hundreds of readings for a piece of any usable size.
"""


def _measure_height(
    contour: np.ndarray,
    orthophoto: Orthophoto,
    frame: RgbdFrame,
    nominal_height: float,
) -> float:
    """
    Measure how far a piece's top surface stands above the plane it was rectified on.

    Reprojects the piece's interior back into the camera, takes the median of whatever
    depth readings came back, and turns that into a height along the world frame's
    z-axis.

    :param contour: The piece's outline, in rectified pixels.
    :param orthophoto: The rectified view it was found in.
    :param frame: The camera data to read depth from.
    :param nominal_height: Height to report where the depth image cannot answer.
    :return: The height in metres.
    """
    rows, columns = np.nonzero(_filled(contour, orthophoto))
    rows = rows[::_HEIGHT_SAMPLE_STRIDE]
    columns = columns[::_HEIGHT_SAMPLE_STRIDE]
    if rows.size == 0:
        return nominal_height

    pixel_T_region = OrthophotoProjector.pixel_T_region(frame, orthophoto.plane_height)
    homography = pixel_T_region @ orthophoto.region.region_T_pixel
    rectified = np.stack([columns, rows, np.ones_like(rows)], axis=0).astype(float)
    projected = homography @ rectified
    camera_pixels = np.round(projected[:2] / projected[2]).T

    depths = frame.depth_at(camera_pixels)
    if depths.size < _MINIMUM_DEPTH_SAMPLES:
        return nominal_height

    projected_center = homography @ np.array([columns.mean(), rows.mean(), 1.0])
    center_pixel = projected_center[:2] / projected_center[2]
    [camera_P_top] = frame.intrinsics.deproject(
        center_pixel.reshape(1, 2), np.array([float(np.median(depths))])
    )
    reference_frame_P_top = frame.reference_frame_T_camera @ np.append(
        camera_P_top, 1.0
    )
    measured = float(reference_frame_P_top[2]) - orthophoto.plane_height
    return measured if measured > 0.0 else nominal_height


def _position_of(detection: MontessoriDetection) -> np.ndarray:
    """
    A detection's world-frame ``(x, y)``.

    :param detection: The detection to read.
    """
    return detection.pose.to_position().to_np()[:2].astype(float)


def _to_world_outline(contour: np.ndarray, orthophoto: Orthophoto) -> np.ndarray:
    """
    Express a rectified contour as world-frame points on the plane it was found on.

    :param contour: The contour, in rectified pixels.
    :param orthophoto: The rectified view it was found in.
    :return: The outline as ``(n, 2)`` world-frame ``(x, y)`` points.
    """
    pixels = contour.reshape(-1, 2).astype(float)
    return np.stack(
        orthophoto.region.to_world_position(pixels[:, 0], pixels[:, 1]), axis=1
    )


def _to_rectified_contour(outline: np.ndarray, orthophoto: Orthophoto) -> np.ndarray:
    """
    Express a world-frame outline as a contour of the rectified view it lies in, which
    is where an outline is measured and where the depth behind it is read.

    :param outline: The outline, as ``(n, 2)`` world-frame ``(x, y)`` points.
    :param orthophoto: The rectified view it lies in.
    :return: The contour, in rectified pixels.
    """
    pixels = orthophoto.region.to_pixels(outline)
    return np.round(pixels).astype(np.int32).reshape(-1, 1, 2)


# %% the pipeline


@dataclass
class MontessoriPerceptionPipeline:
    """
    Turns one RGB-D frame into everything recognised in the Montessori scene.
    """

    table: WorkspaceSurface
    """
    The surface the scene is set up on, and the patch of it perception looks at.

    Read off the robot's own model rather than fitted to the depth image, which this
    reflective table is too noisy to support.
    """

    lid: WorkspaceSurface
    """
    The board's lid: the second surface pieces rest on, and the plane its holes are cut
    in.

    Its height must match the physical board, since it sets the plane the holes are
    rectified onto and so how far apart their centres come out. How far it reaches is
    not read from here but from the board as it was seen, because a board that has been
    slid across the table stands exactly as high as before somewhere else.
    """

    reference_frame: Optional[KinematicStructureEntity] = None
    """
    Frame the detections' poses are expressed in, which must be the frame the camera's
    own pose was given in.
    """

    world: Optional[World] = None
    """
    The world the robot already keeps, which says what pieces it has placed in the
    workspace and so where a look may expect to find them.

    None where a look has no world behind it at all, as a recorded frame does.
    """

    board_detector: BoardDetector = field(default_factory=BoardDetector)
    """
    Finds the board and its holes.
    """

    piece_detector: LoosePieceDetector = field(default_factory=LoosePieceDetector)
    """
    Finds the loose pieces resting on each of the scene's surfaces.
    """

    headroom: float = 0.15
    """
    How far above the table, in metres, the view still holds something worth seeing.

    Wide enough for the board's lid and for a piece held over it on its way in; anything
    higher is a passing arm or the room behind the table.
    """

    @classmethod
    def of_world(cls, world: World, table: Body) -> MontessoriPerceptionPipeline:
        """
        Build the pipeline that looks at the Montessori scene a world describes.

        The stretch of table to search and the plane each surface stands at are read
        from the world, so perception looks where the robot's own model says the scene
        is.

        :param world: The world the scene is described in.
        :param table: The body carrying the surface the scene is set up on.
        :raises BoardMissingFromWorld: If the world describes no shape-sorting board.
        :raises SurfaceHasNothingToMeasure: If a surface the scene needs has no shape.
        """
        reference_frame = world.root
        boards = world.get_semantic_annotations_by_type(ShapeSortingBoard)
        if not boards:
            raise BoardMissingFromWorld()
        [board] = boards
        return cls(
            table=WorkspaceSurface.of_body(table, reference_frame),
            lid=WorkspaceSurface.of(board, reference_frame),
            reference_frame=reference_frame,
            world=world,
        )

    @property
    def workspace(self) -> WorkspaceBox:
        """
        The space this pipeline looks at: its own patch of table, and the room above it
        a piece or the board can stand in.
        """
        return self.workspace_over(self.table.region)

    def workspace_over(self, region: WorkspaceRegion) -> WorkspaceBox:
        """
        The space standing over one patch of this pipeline's table.

        A look narrowed to less than the whole table stands over less of it, so what a
        window shows of the scene narrows with the search rather than staying the widest
        the pipeline could have searched.

        :param region: The patch of table to stand over.
        """
        return WorkspaceBox(
            region=region,
            minimum_height=self.table.height,
            maximum_height=self.table.height + self.headroom,
        )

    def rectify(
        self,
        frame: RgbdFrame,
        height: float,
        region: Optional[WorkspaceRegion] = None,
    ) -> Orthophoto:
        """
        Rectify a frame onto a horizontal plane, which is where outlines lying in that
        plane are measured.

        :param frame: The camera data to rectify.
        :param height: Height of the plane, above the world frame's origin, in metres.
        :param region: The patch of the plane to rectify, or None for the whole stretch
            of table this pipeline looks at.
        :return: That plane's top-down view.
        """
        patch = self.table.region if region is None else region
        return OrthophotoProjector(region=patch).project(frame, height)

    def stated_region(
        self, request: SceneRequest, search: SurfaceSearch
    ) -> Optional[WorkspaceRegion]:
        """
        The stretch of one surface's own plane a look's statement says the thing sought
        lies in.

        A relation is stated between things the world holds, so what it leaves in metres
        is read here, where the frame the detections are reported in is known, rather
        than where the statement was compiled. Each is asked about the stretch this
        surface was going to read rather than about the world, because a direction read
        from where the camera stands runs across the world's own axes and no axis-
        aligned patch holds everything such a direction allows, while the part of one
        surface's plane on that side of a thing is a patch. Several of them compose,
        each narrowing what the one before it left.

        :param request: What the look was asked for.
        :param search: The surface being searched, before this narrowing.
        :raises LookHasNoReferenceFrame: If the statement says where the thing lies but
            this pipeline reports its detections in no frame, which leaves the relation
            nothing to be read against.
        :return: The patch the statement leaves of this surface, or None where it leaves
            none of it.
        """
        if self.reference_frame is None:
            raise LookHasNoReferenceFrame(type(request.placements[0]).__name__)
        allowed = self._space_over(search)
        for placement in request.placements:
            allowed = placement.allowed_part_of(allowed)
            if allowed is None:
                return None
        return WorkspaceRegion(
            minimum_x=allowed.x_interval.lower,
            maximum_x=allowed.x_interval.upper,
            minimum_y=allowed.y_interval.lower,
            maximum_y=allowed.y_interval.upper,
            resolution=self.table.region.resolution,
        )

    def _space_over(self, search: SurfaceSearch) -> VolumetricBoundingBox:
        """
        The stretch of the world one pass of a surface reads: how far the surface itself
        reaches, and how high above it a thing standing on it is reported.

        A relation says where a thing stands rather than where its surface is, so the
        height matters: read at the plane alone, a direction tilted away from it would
        leave out ground a thing standing on that plane is allowed.

        :param search: The surface being searched.
        """
        reach = search.region
        standing = search.surface.height + self.piece_detector.piece_height
        return VolumetricBoundingBox.from_array_bounds(
            np.array([reach.minimum_x, reach.minimum_y, search.surface.height]),
            np.array([reach.maximum_x, reach.maximum_y, standing]),
            HomogeneousTransformationMatrix.from_xyz_rpy(
                reference_frame=self.reference_frame
            ),
        )

    def searched_surfaces(
        self,
        board: Optional[MontessoriBoardDetection],
        request: SceneRequest = SceneRequest(),
    ) -> List[SurfaceSearch]:
        """
        The surfaces one look searches, each with the part of its plane it may claim.

        The table is everything but where the board stands; the board's lid is the board
        itself, and only where it was actually seen. A request naming one of them drops
        the other, so a look asked about one surface rectifies and searches one plane,
        and a region the statement names cuts each remaining plane down to where the
        thing sought may actually be.

        :param board: The board, or None if it was not in view.
        :param request: What the look was asked for.
        :return: One entry per surface a piece can be found on that the request asked
            about and left anything of to search.
        """
        if board is None:
            searches = [SurfaceSearch(surface=self.table)]
        else:
            searches = [
                SurfaceSearch(surface=self.table, supported_surfaces=(board,)),
                SurfaceSearch(surface=self.lid, boundary=board),
            ]
        asked_about = [
            search for search in searches if request.searches(search.surface.name)
        ]
        narrowed = [self._narrowed(search, request) for search in asked_about]
        return [search for search in narrowed if search is not None]

    def _narrowed(
        self, search: SurfaceSearch, request: SceneRequest
    ) -> Optional[SurfaceSearch]:
        """
        One surface's search, cut down to the stretch of its own plane the statement
        allows.

        :param search: The surface being searched, before the statement narrows it.
        :param request: What the look was asked for.
        :return: The narrowed search, or None where the statement leaves none of this
            surface to read.
        """
        if not request.placements:
            return search
        allowed = self.stated_region(request, search)
        if allowed is None:
            return None
        return replace(search, narrowed_to=allowed)

    def table_hidden_by(
        self, board: MontessoriBoardDetection, frame: RgbdFrame
    ) -> OccupiedVolume:
        """
        The stretch of table the board takes out of the search: what it stands on, and
        what it stands in front of.

        A piece on the lid is seen against the table behind the board, so the table's
        own pass reads it as something resting there. The shadow is cast from the top of
        a piece standing on the lid rather than from the lid itself, since that is what
        actually stands between the camera and the table. Only the space up to the lid
        is taken, so a piece resting on the lid stands above it and keeps its own place.

        :param board: The board as it was seen.
        :param frame: The camera data the look was taken from.
        """
        standing_on_the_lid = OccupiedVolume(
            outline=board.outline,
            bottom=board.lid_height,
            top=board.lid_height + self.piece_detector.piece_height,
        )
        return standing_on_the_lid.hides(self.table.height, frame.camera_position)

    def expected_pieces(self) -> List[PieceHypothesis]:
        """
        Where a piece may be, from what the robot knows before anything is segmented.

        The world already places the pieces the robot has put in the workspace and names
        which piece each one is, and a belief that names one piece at one place needs no
        colour to separate it from what it rests on -- which is what a piece wearing
        that surface's own hue never has. Anything believed more particularly than the
        world can say is supplied by whoever asks for the look.

        :return: One hypothesis per place a piece is expected.
        """
        if self.world is None:
            return []
        placed = []
        for shape in self.world.get_semantic_annotations_by_type(MontessoriShape):
            position = shape.root.global_pose.to_position().to_np()[:2]
            if not self.table.region.contains(float(position[0]), float(position[1])):
                continue
            placed.extend(
                PieceHypothesis(
                    place=BelievedPlace(
                        surface=surface.name,
                        center=PlanarPoint(x=float(position[0]), y=float(position[1])),
                    ),
                    source=self.world,
                    candidates=(KNOWN_PIECE_BY_CATEGORY[shape.shape_category],),
                )
                for surface in (self.table, self.lid)
            )
        return placed

    def board_in(self, frame: RgbdFrame) -> Optional[MontessoriBoardDetection]:
        """
        The board as one frame shows it, which is what says how far its lid reaches and
        where each of its holes lies.

        :param frame: The camera data to search.
        :return: The board, or None if it was not in view.
        """
        return self.board_detector.detect(
            self.rectify(frame, self.lid.height, self.table.region),
            self.reference_frame,
        )

    def detect(
        self, frame: RgbdFrame, request: SceneRequest = SceneRequest()
    ) -> MontessoriScene:
        """
        Recognise what one frame was asked about.

        Every surface the request asks about is searched on its own plane, so a piece
        standing on the board's lid is rectified from the lid rather than from the table
        eighty millimetres below it, where parallax would have pushed its two silhouettes
        past each other. Each pass evaluates what is expected on its own surface -- what
        its colours suggest, and what the board and the world already say -- rather than
        only what a colour separated. The same frame seen from two planes reports one
        thing twice, so what every surface found is settled against the places already
        taken.

        The board is found whatever was asked for, and wherever the pipeline looks at
        all: it is the answer to a request about the board itself or its holes, and it
        is what says how far each surface reaches for a request about the pieces. So
        neither a stated surface nor a stated placement cuts the picture it is found in
        -- a statement about what rests on the board would otherwise decide how much of
        the board is seen, and with it how far its lid is taken to reach.

        Each piece pass then rectifies only the stretch its own surface reaches into,
        which is where a narrowing stops being a filter over what came back and becomes
        less picture to search.

        :param frame: The camera data to search.
        :param request: What the look was asked for, unnarrowed by default.
        :return: The pieces, the board, and its holes, as far as the request asked for
            them.
        """
        board = self.board_in(frame)
        expected = self.expected_pieces()
        pieces = []
        if request.wants(MontessoriShapeDetection):
            for search in self.searched_surfaces(board, request):
                pieces.extend(
                    self.piece_detector.detect(
                        self.rectify(frame, search.surface.height, search.region),
                        self.rectify(
                            frame,
                            search.surface.height + self.piece_detector.piece_height,
                            search.region,
                        ),
                        frame,
                        self.reference_frame,
                        search,
                        expected,
                        request.color,
                    )
                )
        occupancy = Occupancy()
        if board is not None:
            occupancy.claim(self.table_hidden_by(board, frame))
        return MontessoriScene(
            shapes=occupancy.keep_one_detection_per_place(pieces), board=board
        )
