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
from dataclasses import dataclass, field

import cv2
import numpy as np
from krrood.entity_query_language.factories import ConditionType
from typing_extensions import List, Optional, Sequence

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detector_choice import (
    DetectorRules,
    PieceDetector,
    SurfacePass,
    TargetOnSurface,
)
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    DetectedMontessoriShape,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.explanations import (
    BoardOutlines,
    CompetingExplanations,
    PlaceInThePicture,
)
from experiments.montessori.hole_geometry import BoardHoleLayout, PlacedHole
from experiments.montessori.perception.exceptions import (
    BoardMissingFromWorld,
)
from experiments.montessori.perception.footprint import RectifiedFootprint
from experiments.montessori.perception.hypotheses import (
    BelievedPlace,
    PieceHypothesis,
)
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.look_choice import (
    LookRules,
    SceneDetector,
    SceneToSearch,
)
from experiments.montessori.perception.occupancy import Occupancy
from experiments.montessori.perception.outline_fit import OutlineFitter, Placement
from experiments.montessori.perception.orthophoto import (
    Orthophoto,
    OrthophotoProjector,
    WorkspaceBox,
    WorkspaceRegion,
)
from experiments.montessori.perception.piece_matcher import PieceMatcher
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.surface_finding import SurfaceRules
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import (
    HUE_RANGE,
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KnownPiece,
    hues_of,
    pieces_colored,
    rectangle_boundary,
)
from experiments.montessori.planar_geometry import PlanarPoint, turned
from experiments.montessori.semantics import ShapeSortingBoard
from semantic_digital_twin.spatial_types.spatial_types import (
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import (
    Color,
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

    def outlines_wearing(
        self, hue: int, orthophoto: Orthophoto, top_orthophoto: Orthophoto
    ) -> List[np.ndarray]:
        """
        The outlines one colour covers on both of a surface's rectified views.

        Both views are read because a piece seen from off to one side shows its sides as
        well as its top, and what the two silhouettes agree on is roughly its footprint.

        :param hue: The colour to look for, as OpenCV reports hue.
        :param orthophoto: The rectified view of the surface's own plane.
        :param top_orthophoto: The rectified view of the plane a piece's top stands on.
        """
        mask = _clean(
            cv2.bitwise_and(
                self.piece_mask(orthophoto, hue),
                self.piece_mask(top_orthophoto, hue),
            )
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return list(contours)

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

    def admits(self, footprint: RectifiedFootprint) -> bool:
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

BOARD_SCALES_TRIED = tuple(round(0.70 + step * 0.01, 2) for step in range(41))
"""
The sizes a shape-sorting board of the mesh's shape is tried at when one is measured,
against that mesh.

Reaches from a board about a third smaller than the mesh to one about a third larger,
which is wider than any board that would still be recognisable as the same toy, at a
step of one part in a hundred -- finer than the two to three millimetres a fitted hole
lands from the opening it belongs to.
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

    What those openings are is then settled by fitting the board's whole known layout
    over them at once, rather than by measuring each dark patch and deciding from its
    proportions what shape it is. The patches only say roughly where to start.
    """

    layout: BoardHoleLayout = field(default_factory=BoardHoleLayout.of_board_mesh)
    """
    The holes the board's mesh is cut with, which is what is looked for.
    """

    rough_fitter: OutlineFitter = field(
        default_factory=lambda: OutlineFitter(
            coarse_angle_step=math.radians(12.0),
            angle_step=math.radians(12.0),
            coarse_reach=0.020,
            reach=0.020,
            coarse_step=0.006,
            step=0.006,
            coarse_outline_spacing=0.012,
            outline_spacing=0.012,
        )
    )
    """
    Finds roughly which way round the board lies, over every turn it could be at.

    A board can be stood on the table any way round, and nothing before the fit says
    which, so the turn has to be searched over a whole circle -- which is most of what a
    fit costs. This pass reaches wide enough, and compares at few enough points, that a
    circle is affordable, and it is only ever asked which twelfth of a turn to look in.
    """

    fitter: OutlineFitter = field(
        default_factory=lambda: OutlineFitter(
            angle_step=math.radians(0.5), coarse_outline_spacing=0.006
        )
    )
    """
    Settles the placement, around the turn the first pass came back with.

    Turned far more finely than a loose piece is: half a degree moves the outermost hole
    of a layout spanning a hundred and eighty millimetres by under a millimetre, where
    the two degrees a thirty millimetre piece is content with would move it by three --
    further than the fit's own reach. Its own coarse pass compares at a third of the
    points for the same reason from the other side: six outlines are hundreds of points.
    """

    colors: SurfaceColors = field(default_factory=SurfaceColors)
    """
    How the lid and its holes separate by colour.
    """

    hole_size: SizeRange = HOLE_SIZE
    """
    Area a dark patch may cover and still be worth taking as a hole to start from.
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

    seed_reach: float = 0.04
    """
    How far, in metres, the fit may move the board from where the dark patches put it.

    The patches are whatever the lighting made dark and are not the holes, so their
    middle is only ever a place to start: measured on the shipped captures they lie
    within about ten millimetres of the board's true centre, and this leaves room for
    several times that.
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
        :return: The board and its holes, or None if no surface in view had enough dark
            patches cut through it to be a board.
        """
        seed = self._seed_from_dark_patches(orthophoto)
        if seed is None:
            return None
        placement = self._fit(self.layout, EdgeDistances.of(orthophoto), seed)
        return self._board_at(placement, orthophoto, reference_frame)

    def measure_scale(
        self, orthophoto: Orthophoto, candidates: Sequence[float] = BOARD_SCALES_TRIED
    ) -> Optional[float]:
        """
        How large the board in view is, against the mesh its layout was read from.

        Where the holes lie relative to one another is cut into the board and cannot
        vary, so a look whose openings no placement of the layout can reach says
        something about the board rather than about the look: the board is not the size
        the mesh was drawn at. The size is then the hypothesis that makes the layout
        hold again, and it is measured by trying the sizes such a board could be and
        keeping the one whose holes land on the openings actually seen.

        Not something a look does for itself -- it costs one fit per size tried, and a
        board does not change size between frames. It is run once against a look at the
        board and its answer is stated with the scene, the way the surfaces are.

        :param orthophoto: A rectified view of the lid's plane, with the board in it.
        :param candidates: The sizes to try, against the mesh.
        :return: The size that best explains the openings, or None if no surface in view
            carried enough of them to measure against.
        """
        seed = self._seed_from_dark_patches(orthophoto)
        if seed is None:
            return None
        openings = np.array(
            [
                (patch.x, patch.y)
                for patch in self._board_sized_cluster(
                    self._dark_patches_within(
                        self._most_coloured_surface(orthophoto), orthophoto
                    )
                )
            ]
        )
        edges = EdgeDistances.of(orthophoto)
        return min(
            candidates,
            key=lambda scale: self._gap_to_openings(scale, edges, seed, openings),
        )

    def _gap_to_openings(
        self,
        scale: float,
        edges: EdgeDistances,
        seed: PlanarPoint,
        openings: np.ndarray,
    ) -> float:
        """
        How far the openings seen lie from the holes a board of one size would put
        there, once that board is fitted as well as it can be.

        :param scale: The size to try, against the mesh.
        :param edges: The edges seen in the lid's plane.
        :param seed: Roughly where the board stands.
        :param openings: World-frame ``(n, 2)`` middles of the openings seen.
        :return: The middle distance, in metres, from an opening to the nearest hole.
        """
        layout = BoardHoleLayout.of_board_mesh(scale)
        placement = self._fit(layout, edges, seed)
        holes = np.array(
            [
                (hole.center.x, hole.center.y)
                for hole in layout.placed(placement.center, placement.yaw)
            ]
        )
        return float(
            np.median(
                np.linalg.norm(openings[:, None, :] - holes[None, :, :], axis=2).min(
                    axis=1
                )
            )
        )

    def _fit(
        self, layout: BoardHoleLayout, edges: EdgeDistances, seed: PlanarPoint
    ) -> Placement:
        """
        Lay one layout over the edges, from anywhere within reach of the seed and at any
        turn.

        Searched twice over: once roughly, over every turn a board could be stood at,
        and once carefully around the answer. Sweeping a whole circle at the resolution
        the second pass needs would cost three times as much and answer the same, since
        all the first one has to say is which twelfth of a turn the board lies in.

        :param layout: The holes to look for.
        :param edges: The edges seen in the lid's plane.
        :param seed: Roughly where the board stands.
        """
        rough = self.rough_fitter.fit(
            layout,
            edges,
            center=seed,
            radius=self.seed_reach,
            angles=list(
                np.arange(-math.pi, math.pi, self.rough_fitter.coarse_angle_step)
            ),
        )
        turns = round(
            self.rough_fitter.coarse_angle_step / self.fitter.coarse_angle_step
        )
        return self.fitter.fit(
            layout,
            edges,
            center=rough.center,
            radius=2 * self.rough_fitter.coarse_step,
            angles=list(
                rough.yaw + np.arange(-turns, turns + 1) * self.fitter.coarse_angle_step
            ),
        )

    def _seed_from_dark_patches(self, orthophoto: Orthophoto) -> Optional[PlanarPoint]:
        """
        Roughly where in view the board stands, from the hole-sized dark patches on the
        most perforated surface.

        Which patch is which hole is not asked, and neither is whether a patch is a hole
        at all: the layout fit answers both, and a middle is all it needs to start from.

        :param orthophoto: The rectified view of the lid's plane.
        :return: The middle of the largest board-sized group of patches, or None if no
            surface in view carried enough of them.
        """
        best: List[PlanarPoint] = []
        for contour in self._surfaces_large_enough_to_be_a_lid(orthophoto):
            patches = self._board_sized_cluster(
                self._dark_patches_within(contour, orthophoto)
            )
            if len(patches) > len(best):
                best = patches
        if len(best) < self.minimum_hole_count:
            return None
        middle = np.array([(patch.x, patch.y) for patch in best]).mean(axis=0)
        return PlanarPoint(float(middle[0]), float(middle[1]))

    def _surfaces_large_enough_to_be_a_lid(
        self, orthophoto: Orthophoto
    ) -> List[np.ndarray]:
        """
        The coloured surfaces in view big enough to be the board's lid.

        :param orthophoto: The rectified view of the lid's plane.
        :return: Their contours, in rectified pixels.
        """
        mask = _clean(self.colors.surface_mask(orthophoto))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [
            contour
            for contour in contours
            if RectifiedFootprint.from_contour(
                contour, orthophoto.region.resolution
            ).area
            >= self.minimum_lid_area
        ]

    def _most_coloured_surface(self, orthophoto: Orthophoto) -> np.ndarray:
        """
        The largest surface in view that could be the board's lid.

        :param orthophoto: The rectified view of the lid's plane.
        :return: Its contour, in rectified pixels.
        """
        return max(
            self._surfaces_large_enough_to_be_a_lid(orthophoto),
            key=lambda contour: RectifiedFootprint.from_contour(
                contour, orthophoto.region.resolution
            ).area,
        )

    def _dark_patches_within(
        self, surface: np.ndarray, orthophoto: Orthophoto
    ) -> List[PlanarPoint]:
        """
        Where the hole-sized dark patches on one candidate surface lie.

        The surface is filled in first, so that a patch is a dark spot within a solid
        region rather than a gap that the surface's own outline has to enclose; a hole
        broken open at the board's edge would otherwise be missed entirely.

        :param surface: The candidate surface's own contour, in rectified pixels.
        :param orthophoto: The rectified view it was found in.
        :return: The middle of each patch that could be a hole, in world coordinates.
        """
        region = _filled(surface, orthophoto)
        # Left unopened on purpose: the narrowest hole on the board is five millimetres
        # across, which the speckle-removing kernel would eat entirely. Slivers are
        # rejected by area instead, in :attr:`hole_size`.
        dark = self.colors.dark_mask(orthophoto, region)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return [
            orthophoto.contour_center(contour)
            for contour in contours
            if self.hole_size.admits(
                RectifiedFootprint.from_contour(contour, orthophoto.region.resolution)
            )
        ]

    def _board_sized_cluster(self, patches: List[PlanarPoint]) -> List[PlanarPoint]:
        """
        Keep only the patches that could lie on one board.

        A surface that has merged with an arm reaching over the table carries dark
        patches scattered far beyond any board, so they are grouped by how close
        together they lie and only the largest group that still fits on a board is kept.

        :param patches: Every hole-sized dark patch found on one surface.
        :return: The largest group of them that fits within one board's lid.
        """
        if not patches:
            return []
        centers = np.array([(patch.x, patch.y) for patch in patches])
        groups = [self._grow_from(seed, patches, centers) for seed in centers]
        return max(groups, key=len)

    def _grow_from(
        self,
        seed: np.ndarray,
        patches: List[PlanarPoint],
        centers: np.ndarray,
    ) -> List[PlanarPoint]:
        """
        Grow a group outwards from one patch, taking in the next nearest patch for as
        long as the group still fits on a single lid.

        :param seed: World-frame ``(x, y)`` of the patch to grow from.
        :param patches: Every hole-sized dark patch found on one surface.
        :param centers: Those patches' world-frame ``(x, y)``, in the same order.
        :return: The grown group.
        """
        order = np.argsort(np.linalg.norm(centers - seed, axis=1))
        group: List[PlanarPoint] = []
        for index in order:
            candidate = group + [patches[index]]
            if self._fits_on_a_lid(candidate):
                group = candidate
        return group

    def _fits_on_a_lid(self, patches: List[PlanarPoint]) -> bool:
        """
        Whether a group of patches is packed tightly enough to have come from one lid.

        :param patches: The group to check.
        """
        centers = np.array([(patch.x, patch.y) for patch in patches], dtype=np.float32)
        if len(centers) < 2:
            return len(centers) > 0
        (_, _), (first_side, second_side), _ = cv2.minAreaRect(centers)
        span = sorted((first_side, second_side))
        allowed = sorted((self.layout.size.x, self.layout.size.y))
        return all(measured <= reach for measured, reach in zip(span, allowed))

    def _board_at(
        self,
        placement: Placement,
        orthophoto: Orthophoto,
        reference_frame: Optional[KinematicStructureEntity],
    ) -> MontessoriBoardDetection:
        """
        Build the board standing at the placement its layout was fitted to.

        The lid's own edges are not used: they run into whatever the board is standing
        against. The layout is what says where the board is, and it says it better than
        the lid's outline could, since six holes constrain a placement that one
        rectangle leaves free to slide along itself.

        :param placement: Where the layout was fitted to.
        :param orthophoto: The rectified view of the lid's plane.
        :param reference_frame: Frame the resulting pose is expressed in.
        :return: The board.
        """
        width, length = self.layout.size.x, self.layout.size.y
        return MontessoriBoardDetection(
            pose=Pose.from_xyz_rpy(
                placement.center.x,
                placement.center.y,
                orthophoto.plane_height,
                yaw=placement.yaw,
                reference_frame=reference_frame,
            ),
            footprint=RectifiedFootprint(
                area=width * length,
                width=width,
                length=length,
                fill_ratio=1.0,
                corner_count=4,
                yaw=(placement.yaw + math.pi / 2) % math.pi - math.pi / 2,
            ),
            outline=turned(rectangle_boundary(width, length), placement.yaw)
            + np.array([placement.center.x, placement.center.y]),
            holes=[
                self._hole_at(hole, orthophoto, reference_frame)
                for hole in self.layout.placed(placement.center, placement.yaw)
            ],
            lid_height=orthophoto.plane_height,
        )

    @staticmethod
    def _hole_at(
        hole: PlacedHole,
        orthophoto: Orthophoto,
        reference_frame: Optional[KinematicStructureEntity],
    ) -> ShapeSortingHoleDetection:
        """
        Report one hole of a fitted layout.

        Its shape comes from the board's own mesh rather than from measuring the patch
        it was found over, so a hole can be neither mislabelled nor invented.

        :param hole: The hole, placed where the layout puts it.
        :param orthophoto: The rectified view of the lid's plane.
        :param reference_frame: Frame the resulting pose is expressed in.
        """
        return ShapeSortingHoleDetection(
            pose=Pose.from_xyz_rpy(
                hole.center.x,
                hole.center.y,
                orthophoto.plane_height,
                reference_frame=reference_frame,
            ),
            footprint=RectifiedFootprint.from_contour(
                _to_rectified_contour(hole.outline, orthophoto),
                orthophoto.region.resolution,
            ),
            outline=hole.outline,
            category=hole.footprint.category,
        )


@dataclass(eq=False)
class EdgeFitDetector(PieceDetector):
    """
    Finds the loose Montessori pieces by fitting their known outlines to the edges the
    camera saw, searching for the placement that follows those edges best.

    Needs nothing of the surface: an outline is fitted to edges whatever threw them, which
    is why this is the general answer and the one a reflective table leaves standing.
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

    hue_tolerance: int = HUE_TOLERANCE
    """
    How far a measured colour may sit from a piece's own before a colour seen at a place
    stops suggesting that piece.
    """

    def capability(self, look: TargetOnSurface) -> ConditionType:
        """
        Answers a look for a piece whose outline is modelled, on any surface.

        :param look: The look to state the condition over.
        """
        return look.target_outline_is_known

    def detect(self, surface_pass: SurfacePass) -> List[DetectedMontessoriShape]:
        """
        Find the pieces resting on one surface, by evaluating what is expected there.

        Every hypothesis this surface owns is fitted against the edges of the view
        rectified onto a piece's top, where a piece's own top face lies at exactly its
        footprint, undistorted and sharply bounded. A colour seen in the picture is one
        source of hypotheses; whatever the caller already believes is another, and a
        piece is found at a place it was expected whether or not any colour separated it
        from what it rests on.

        What is reported is then settled by comparing the accounts of each place against
        each other rather than by a level a fit clears: against the board's own known
        geometry, against the next piece that fitted there, and against nothing being
        there at all.

        :param surface_pass: Everything this pass over this surface reads.
        :return: One detection per recognised piece.
        """
        seen = surface_pass.edges.positions
        pieces = []
        for hypothesis in [
            *self._colors_seen_in(surface_pass),
            *surface_pass.expected,
        ]:
            if not self._is_on_this_surface(hypothesis, surface_pass.search):
                continue
            piece = self._piece_at(hypothesis, seen, surface_pass)
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

    def _colors_seen_in(self, surface_pass: SurfacePass) -> List[PieceHypothesis]:
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

        :param surface_pass: The pass over the surface these colours are read on.
        """
        orthophoto = surface_pass.orthophoto
        seen = []
        for hue in hues_of(surface_pass.sought_pieces):
            for contour in self.colors.outlines_wearing(
                hue, orthophoto, surface_pass.top_orthophoto
            ):
                footprint = RectifiedFootprint.from_contour(
                    contour, orthophoto.region.resolution
                )
                if not self.piece_size.admits(footprint):
                    continue
                if not _wholly_within(contour, orthophoto):
                    continue
                seen.append(
                    PieceHypothesis.of_color(
                        place=BelievedPlace(
                            surface=surface_pass.search.surface.name,
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

    def _piece_at(
        self,
        hypothesis: PieceHypothesis,
        seen: np.ndarray,
        surface_pass: SurfacePass,
    ) -> Optional[DetectedMontessoriShape]:
        """
        Recognise the piece a hypothesis expects, if the picture bears it out better
        than anything else could have.

        The outline the fit settled on is what the piece is measured by, rather than the
        colour blob a hypothesis may have come from: it is the piece's own footprint,
        and it is the only outline a hypothesis expected from anything but a colour has.

        Three accounts of the same place are what the best fit has to lead: the board's
        own geometry, the next candidate the belief allowed, and nothing being there. A
        belief naming one piece therefore has less to lead than an unguided look over the
        whole set, which is knowledge making the same evidence go further.

        :param hypothesis: What is expected, and where it is believed to be.
        :param seen: Where the edges of the top view stand, as ``(n, 2)`` world-frame
            points.
        :param surface_pass: The pass over the surface the piece is looked for on.
        :return: The piece, or None where nothing expected explains the edges there
            better than the alternatives.
        """
        orthophoto = surface_pass.orthophoto
        imagined = surface_pass.imagined
        fitted_pieces = self.matcher.fits(surface_pass.edges, hypothesis)
        if not fitted_pieces:
            return None
        match, *runners_up = fitted_pieces
        outline = match.outline
        place = PlaceInThePicture.around(
            outline,
            surface_pass.edges,
            seen,
            self.matcher.fitter.reach,
            self.matcher.fitter.outline_spacing,
        )
        account = place.explained_by(outline)
        rivals = [surface_pass.board_outlines.account_of(place)]
        if runners_up:
            rivals.append(place.explained_by(runners_up[0].outline))
        if not surface_pass.explanations.is_reported(account, *rivals):
            return None
        fitted = _to_rectified_contour(outline, orthophoto)
        height = _measure_height(
            fitted, orthophoto, surface_pass.frame, self.piece_height
        )
        pose = Pose.from_xyz_rpy(
            match.center.x,
            match.center.y,
            orthophoto.plane_height + height / 2,
            yaw=match.yaw,
            reference_frame=imagined.reference_frame,
        )
        return DetectedMontessoriShape(
            role_taker=imagined.spawn(match.piece, pose),
            pose=pose,
            footprint=RectifiedFootprint.from_contour(
                fitted, orthophoto.region.resolution
            ),
            outline=outline,
            category=match.piece.category,
            height=height,
            explanation=account,
            supporting_surface=surface_pass.search.surface.name,
            hypothesis=hypothesis,
        )


@dataclass(eq=False)
class ColorBlobDetector(PieceDetector):
    """
    Finds the loose Montessori pieces by cutting them out of the surface by colour and
    reading the placement off the blob itself.

    Where colour separates a piece from what it rests on, the blob already says where
    the piece stands and roughly how it is turned, so the known outline is scored at
    that one placement instead of being searched for. It reports the same outline
    agreement the :class:`EdgeFitDetector` does, measured the same way, so the two can
    be compared.
    """

    matcher: PieceMatcher = field(default_factory=PieceMatcher)
    """
    Scores a known piece's outline where the blob says it stands.
    """

    colors: SurfaceColors = field(default_factory=SurfaceColors)
    """
    How a piece separates from the surface by colour.
    """

    piece_size: SizeRange = LOOSE_PIECE_SIZE
    """
    Area a piece's outline may cover.
    """

    def capability(self, look: TargetOnSurface) -> ConditionType:
        """
        Answers a look only where colour separates the piece from the surface, since a
        piece that shares the surface's colour has no blob to be cut out of it.

        :param look: The look to state the condition over.
        """
        return look.target_separates_from_the_surface_by_color

    def detect(self, surface_pass: SurfacePass) -> List[DetectedMontessoriShape]:
        """
        Find the pieces resting on one surface, from the colour they wear.

        :param surface_pass: Everything this pass over this surface reads.
        :return: One detection per recognised piece.
        """
        orthophoto = surface_pass.orthophoto
        seen = surface_pass.edges.positions
        pieces = []
        for hue in hues_of(surface_pass.sought_pieces):
            for contour in self.colors.outlines_wearing(
                hue, orthophoto, surface_pass.top_orthophoto
            ):
                piece = self._piece_at(contour, seen, surface_pass)
                if piece is not None:
                    pieces.append(piece)
        return pieces

    def _piece_at(
        self,
        contour: np.ndarray,
        seen: np.ndarray,
        surface_pass: SurfacePass,
    ) -> Optional[DetectedMontessoriShape]:
        """
        Recognise the piece one blob covers, scored where the blob says it stands.

        The blob fixes the place and, up to its own symmetry, the turn, so the piece is
        scored there rather than searched for -- which is the whole of why this detector
        is cheaper than the edge fit. What is reported is settled the same way either
        detector settles it: by comparing the accounts of the place against each other.

        :param contour: The outline to read, in rectified pixels.
        :param seen: Where the edges of the top view stand, as ``(n, 2)`` world-frame
            points.
        :param surface_pass: The pass over the surface the piece is looked for on.
        :return: The piece, or None where the outline is not one of this surface's, or
            where nothing standing there explains the edges better than the alternatives.
        """
        orthophoto = surface_pass.orthophoto
        imagined = surface_pass.imagined
        footprint = RectifiedFootprint.from_contour(
            contour, orthophoto.region.resolution
        )
        if not self.piece_size.admits(footprint):
            return None
        if not _wholly_within(contour, orthophoto):
            return None
        center = orthophoto.contour_center(contour)
        if not surface_pass.search.claims(center.x, center.y):
            return None
        hypothesis = PieceHypothesis.of_color(
            place=BelievedPlace(
                surface=surface_pass.search.surface.name,
                center=center,
                radius=0.0,
            ),
            hue=self.colors.measure_hue(orthophoto, _filled(contour, orthophoto)),
            source=self,
            hue_tolerance=self.hue_tolerance,
        )
        fitted_pieces = self.matcher.match_at(
            surface_pass.edges, hypothesis, self._turns_of(contour)
        )
        if not fitted_pieces:
            return None
        match, *runners_up = fitted_pieces
        outline = match.outline
        place = PlaceInThePicture.around(
            outline,
            surface_pass.edges,
            seen,
            self.matcher.fitter.reach,
            self.matcher.fitter.outline_spacing,
        )
        account = place.explained_by(outline)
        rivals = [surface_pass.board_outlines.account_of(place)]
        if runners_up:
            rivals.append(place.explained_by(runners_up[0].outline))
        if not surface_pass.explanations.is_reported(account, *rivals):
            return None
        height = _measure_height(
            contour, orthophoto, surface_pass.frame, self.piece_height
        )
        pose = Pose.from_xyz_rpy(
            match.center.x,
            match.center.y,
            orthophoto.plane_height + height / 2,
            yaw=match.yaw,
            reference_frame=imagined.reference_frame,
        )
        return DetectedMontessoriShape(
            role_taker=imagined.spawn(match.piece, pose),
            pose=pose,
            footprint=footprint,
            outline=outline,
            category=match.piece.category,
            height=height,
            explanation=account,
            supporting_surface=surface_pass.search.surface.name,
            hypothesis=hypothesis,
        )

    @staticmethod
    def _turns_of(contour: np.ndarray) -> List[float]:
        """
        The turns a blob's own bounding rectangle says its piece may stand at.

        The rectangle fixes the turn only up to a quarter of a circle, since a rectangle
        laid a quarter turn round covers the same ground, so all four are offered and
        the edges decide between them. The rectification is axis-aligned and both its
        axes grow with the world's, so an angle measured in it is a world turn
        unchanged.

        :param contour: The outline to read, in rectified pixels.
        """
        quarter_turn = math.pi / 2
        _, _, degrees = cv2.minAreaRect(contour)
        return [math.radians(degrees) + turn * quarter_turn for turn in range(4)]


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

# %% the ways a look is answered


@dataclass(eq=False)
class FindTheBoard(SceneDetector):
    """
    Answers a look by finding the shape-sorting board and the holes cut through its lid.

    Compared by identity rather than by value, since the rules conclude this object
    itself and two ways configured alike are not the same way.
    """

    board_detector: BoardDetector = field(default_factory=BoardDetector)
    """
    Finds the board and its holes.
    """

    def capability(self, request: SceneRequest) -> ConditionType:
        """
        Answers a request the board, or one of its holes, can answer.

        :param request: The request to state the condition over.
        """
        return request.the_board_is_asked_for

    def detect(self, scene: SceneToSearch) -> MontessoriScene:
        """
        Find the board.

        :param scene: What was asked for, and the frame to answer it from.
        """
        return MontessoriScene(board=self.board_in(scene))

    def board_in(self, scene: SceneToSearch) -> Optional[MontessoriBoardDetection]:
        """
        The board as this look sees it, rectified onto the plane its lid stands in.

        :param scene: The frame to find it in, and the surfaces it stands among.
        :return: The board, or None if it was not in view.
        """
        return self.board_detector.detect(
            scene.rectified.at(scene.lid.height), scene.reference_frame
        )


@dataclass(eq=False)
class FindThePieces(SceneDetector):
    """
    Answers a look by searching every surface the request asks about for the loose
    pieces standing on it.

    The board is found first whatever was asked for, because how far each surface
    reaches is read from the board as it was seen rather than from the world, and it is
    reported along with the pieces since this look measured it.
    """

    find_the_board: FindTheBoard = field(default_factory=FindTheBoard)
    """
    Finds the board that says how far each surface reaches.
    """

    detector_rules: DetectorRules = field(
        default_factory=lambda: DetectorRules(
            edge_fit=EdgeFitDetector(), color_blob=ColorBlobDetector()
        )
    )
    """
    Says which detector looks for each piece on each of the scene's surfaces.

    A look is answered by the detector the rules choose from what the world states about
    the surface and the piece, so a scene the twin describes better is looked at better
    without this way of looking changing.
    """

    def capability(self, request: SceneRequest) -> ConditionType:
        """
        Answers a request a loose piece can answer.

        :param request: The request to state the condition over.
        """
        return request.pieces_are_asked_for

    def detect(self, scene: SceneToSearch) -> MontessoriScene:
        """
        Search each surface the request asks about, on its own plane.

        A piece standing on the board's lid is rectified from the lid rather than from
        the table eighty millimetres below it, where parallax would have pushed its two
        silhouettes past each other. Each pass evaluates what is expected on its own
        surface -- what its colours suggest, and what the board and the world already
        say -- rather than only what a colour separated. The same frame seen from two
        planes reports one thing twice, so what every surface found is settled against
        the places already taken.

        :param scene: What was asked for, and the frame to answer it from.
        :raises NoDetectorAnswersTheLook: If no detector answers one of the looks.
        """
        board = self.find_the_board.board_in(scene)
        imagined = scene.imagine()
        expected = scene.expected_pieces()
        pieces = []
        for search in scene.searched_surfaces(board):
            for detector, candidates in self.detector_rules.detectors_for(
                search.surface, KNOWN_PIECES
            ):
                pieces.extend(
                    detector.detect(
                        self.surface_pass(
                            scene, search, detector, candidates, board, imagined, expected
                        )
                    )
                )
        occupancy = Occupancy(explanations=scene.explanations)
        if board is not None:
            occupancy.claim(scene.table_hidden_by(board))
        kept = occupancy.keep_one_detection_per_place(pieces)
        for rejected in pieces:
            if rejected not in kept:
                imagined.remove(rejected.role_taker)
        return MontessoriScene(shapes=kept, board=board, imagined=imagined)

    @staticmethod
    def surface_pass(
        scene: SceneToSearch,
        search: SurfaceSearch,
        detector: PieceDetector,
        candidates: Sequence[KnownPiece],
        board: Optional[MontessoriBoardDetection],
        imagined: ImaginedWorld,
        expected: Sequence[PieceHypothesis],
    ) -> SurfacePass:
        """
        What one detector is handed to search one surface once.

        :param scene: The frame to read, rectified onto whichever planes are asked for.
        :param search: The surface being searched, and the part of it it may claim.
        :param detector: The detector chosen for these pieces on this surface.
        :param candidates: The pieces it was chosen to look for.
        :param board: The board as this look found it, or None if it was not in view.
        :param imagined: Where what is found comes to stand.
        :param expected: What is believed to be in the workspace already.
        """
        top = search.surface.height + detector.piece_height
        return SurfacePass(
            orthophoto=scene.rectified.at(search.surface.height),
            top_orthophoto=scene.rectified.at(top),
            edges=scene.rectified.edges_at(top),
            frame=scene.frame,
            search=search,
            imagined=imagined,
            candidates=candidates,
            expected=[*expected, *scene.believed_from(search)],
            color=scene.request.color,
            board_outlines=_board_outlines_in(board, top, scene.frame),
            explanations=scene.explanations,
        )


def _board_outlines_in(
    board: Optional[MontessoriBoardDetection],
    plane_height: float,
    frame: RgbdFrame,
) -> BoardOutlines:
    """
    Where the board's own edges fall in one rectified plane, or none where no board was
    in view.

    :param board: The board as this look found it.
    :param plane_height: Height of the plane they are wanted in, in metres.
    :param frame: The camera data, for where the camera stands.
    """
    if board is None:
        return BoardOutlines()
    return board.outlines_in(plane_height, frame.camera_position)


def default_look_rules(
    board_detector: Optional[BoardDetector] = None,
) -> LookRules:
    """
    The rules a pipeline starts with, sharing the one board search between the two ways
    of looking so a look that reports both runs it once.

    :param board_detector: The detector that finds the board, for a setup whose board is
        not the size the mesh was drawn at, or None for the one every scene starts with.
    """
    find_the_board = FindTheBoard(
        board_detector=board_detector or BoardDetector()
    )
    return LookRules(
        find_the_board=find_the_board,
        find_the_pieces=FindThePieces(find_the_board=find_the_board),
    )


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

    look_rules: LookRules = field(default_factory=default_look_rules)
    """
    Says how a look is answered: which detectors run over which surfaces, concluded from
    what the request asks for rather than configured here.

    A kind of request nobody foresaw is given a rule while the rules are in use, so the
    pipeline does not have to change for perception to answer something new.
    """

    surface_rules: SurfaceRules = field(default_factory=SurfaceRules)
    """
    Says how far each of the scene's surfaces reaches, from what the world states about
    it.

    A surface the world describes well enough to recognise in a picture is measured
    there rather than taken from the model it is described by, so a table the model has
    drifted away from is still searched where it really stands.
    """

    explanations: CompetingExplanations = field(default_factory=CompetingExplanations)
    """
    How much better one account of a place must be than the next before it is reported.

    A statement about what a wrong report costs whoever asked for the look, so it
    belongs to the look rather than to the detector that takes it.
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
        The space the world says this pipeline looks at, before anything has been seen.
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

    def table_in(self, frame: RgbdFrame) -> WorkspaceSurface:
        """
        The table one frame shows, which is what that look searches.

        Where the world describes the table well enough to recognise it in a picture the
        rules answer by measuring it, so a run searches the table rather than a
        rectangle drawn around it; where it does not, the answer is the modelled table
        itself.

        :param frame: The camera data the table is looked for in.
        """
        return self.surface_rules.surface_in(self.table, frame)

    def rectify(
        self,
        frame: RgbdFrame,
        height: float,
        region: Optional[WorkspaceRegion] = None,
    ) -> Orthophoto:
        """
        Rectify a frame onto one horizontal plane, which is where outlines lying in that
        plane are measured.

        :param frame: The camera data to rectify.
        :param height: Height of the plane, above the world frame's origin, in metres.
        :param region: The patch of the plane to rectify, or None for the whole stretch
            of table this pipeline looks at.
        :return: That plane's top-down view.
        """
        patch = self.table.region if region is None else region
        return OrthophotoProjector(region=patch).project(frame, height)

    def board_in(self, frame: RgbdFrame) -> Optional[MontessoriBoardDetection]:
        """
        The board as one frame shows it, which is what says how far its lid reaches and
        where each of its holes lies.

        :param frame: The camera data to search.
        :return: The board, or None if it was not in view.
        """
        return self.look_rules.find_the_board.detect(self.scene_to_search(frame)).board

    def detect(
        self, frame: RgbdFrame, request: SceneRequest = SceneRequest()
    ) -> MontessoriScene:
        """
        Recognise what one frame was asked about.

        How the look is answered is concluded from the request rather than written here:
        the rules say which way of looking answers it, and that way says which detectors
        run over which surfaces.

        The table is found in the frame before anything is searched on it, so a look
        reads the stretch of table the camera actually shows rather than a rectangle
        drawn around it.

        :param frame: The camera data to search.
        :param request: What the look was asked for, unnarrowed by default.
        :raises NoDetectorAnswersTheRequest: If no rule says how to answer it.
        :return: What the look found.
        """
        scene = self.scene_to_search(frame, request)
        return self.look_rules.detector_for(request).detect(scene)

    def scene_to_search(
        self, frame: RgbdFrame, request: SceneRequest = SceneRequest()
    ) -> SceneToSearch:
        """
        The material one look works over: what was asked for, the surfaces the world
        describes, and the frame to answer it from.

        The table is the one this look found rather than the one the world models, so
        every plane rectified and every surface searched is the stretch the camera
        actually shows.

        :param frame: The camera data to search.
        :param request: What the look was asked for, unnarrowed by default.
        """
        return SceneToSearch(
            frame=frame,
            table=self.table_in(frame),
            lid=self.lid,
            reference_frame=self.reference_frame,
            request=request,
            world=self.world,
            explanations=self.explanations,
            headroom=self.headroom,
        )
