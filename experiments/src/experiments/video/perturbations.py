"""
The perturbation experiments, all playing at once, two of them brought to the front in
turn, and long term memory asked about them.

Each episode the robot recorded under a perturbation is one tile of a grid; every tile
plays the robot's own camera at the same speed-up, badged with the phase the run is in:
a person perturbing the scene, the robot perceiving it -- while it stands still, which
is when the look is asked, what the look finds is drawn over the picture, the way the
perception pipeline draws it -- or the robot executing. A tile whose recording has
ended stands on its last frame. The question long term memory answers about these runs
is put over the grid and the episodes its answer names are outlined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property

import cv2
import numpy as np
from rclpy.serialization import deserialize_message
from segmind.datastructures.events import MotionEvent
from sensor_msgs.msg import CompressedImage
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.montessori.perception.camera import RgbdFrame, decode_compressed_color_image
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.node import ROBOT_TABLE_PIECES
from experiments.montessori.perception.overlay import CameraView, DetectionOverlay
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.recordings import (
    RAW_DEPTH_TOPIC,
    CameraTopic,
    _decode_depth,
    open_bag,
)
from experiments.paper.lettering import Face
from experiments.video.cache import SceneCache
from experiments.video.canvas import (
    BODY_SIZE,
    DIM,
    LABEL_SIZE,
    MARGIN,
    VIDEO_RESOLUTION,
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Typesetting,
    dimmed,
    filled,
    fitted,
    framed,
)
from experiments.video.footage import (
    BADGE_HEIGHT,
    BADGE_PADDING,
    TABLE_FRAMING,
    CameraFilm,
    Framing,
    TimedImage,
    badged,
    speed_badged,
)
from experiments.video.long_term import RememberedQuestion
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased

IDLE_MARGIN = 0.5
"""
Seconds either side of a recorded motion the robot is not counted as standing still.
"""

MOTION_THRESHOLD = 1.0
"""
The mean difference between two frames of the film, in grey levels, over which
something in the scene is moving: a still scene differs by half a level from frame to
frame, a hand moving a piece by several.
"""

BACKEND_NAME = "LongTermMemoryBackend"
"""
What the card calls the backend that answers over the grid.
"""

HEADER_CLEAR = 96
"""
Pixels from the top kept clear for the header line and the speed badge.
"""

ZOOM = 0.45
"""
Seconds a tile takes to grow to the front, and to shrink back.
"""

ANSWER_FADE = 0.25
"""
Seconds the answer to the question takes to come up.
"""

# %% when the robot stood still


@dataclass(frozen=True)
class RecordingStretch:
    """
    A stretch of a recording, in seconds from its start.
    """

    start: float
    end: float

    def holds(self, seconds: float) -> bool:
        return self.start <= seconds <= self.end


@dataclass
class IdleStretches:
    """
    When, in a recording, the robot was not moving: everything outside the motions the
    episode's trials recorded, shifted from trial time to recording time.
    """

    run: RecordedRun
    """
    The run.
    """

    @cached_property
    def moving(self) -> List[RecordingStretch]:
        """
        Every stretch the robot moved through, in recording time, widened by the margin.
        """
        stretches = []
        for trial in self.run.trials:
            for motion in trial.motions:
                stretches.append(
                    RecordingStretch(
                        self.run.recording_second_of(trial, motion.start_moment) - IDLE_MARGIN,
                        self.run.recording_second_of(trial, motion.end_moment) + IDLE_MARGIN,
                    )
                )
        return stretches

    def idle_at(self, seconds: float) -> bool:
        """
        Whether the robot stood still at a moment of the recording.
        """
        return not any(stretch.holds(seconds) for stretch in self.moving)


# %% when a person was perturbing the scene


@dataclass
class PerturbingStretches:
    """
    When, in a recording, a person was moving something in the scene: from the moment
    the trial told them what to move until the film shows the scene still again, before
    the event segmentation reported the thing moved -- which it does once the robot has
    looked again, so the robot perceives between the two.
    """

    run: RecordedRun
    """
    The run.
    """

    film: CameraFilm
    """
    The robot's camera, whose frames show when the scene went still.
    """

    framing: Framing = TABLE_FRAMING
    """
    What of each frame is watched for motion: the table, not the room's edge.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("perturbations"))
    """
    Where the stretches are kept between renders.
    """

    @cached_property
    def perturbing(self) -> List[RecordingStretch]:
        """
        Every stretch a person was moving something through, in recording time.
        """
        key = f"{self.run.episode_identifier}_perturbing"
        kept = self.cache.record(key)
        if kept is None:
            kept = {"stretches": [[stretch.start, stretch.end] for stretch in self._measured()]}
            self.cache.keep_record(key, kept)
        return [RecordingStretch(start, end) for start, end in kept["stretches"]]

    def perturbing_at(self, seconds: float) -> bool:
        """
        Whether a person was moving something at a moment of the recording.
        """
        return any(stretch.holds(seconds) for stretch in self.perturbing)

    def told_and_reported(self) -> List[RecordingStretch]:
        """
        Every stretch from a trial telling a person what to move until the event
        segmentation reported the thing moved, in recording time.
        """
        stretches = []
        for trial in self.run.trials:
            for moved in trial.moved_by_someone_else:
                names = {str(name) for name in moved.things_moved}
                reported = [
                    tick.moment
                    for tick in trial.ticks
                    if tick.moment > moved.moment
                    and any(isinstance(event, MotionEvent) and str(event.tracked_object.name) in names for event in tick.events)
                ]
                end = min(reported) if reported else trial.duration
                stretches.append(
                    RecordingStretch(
                        self.run.recording_second_of(trial, moved.moment),
                        self.run.recording_second_of(trial, end),
                    )
                )
        return stretches

    def _measured(self) -> List[RecordingStretch]:
        """
        Each told-and-reported stretch cut short where the film last shows motion
        before the report.
        """
        return [
            RecordingStretch(stretch.start, self._still_from(stretch))
            for stretch in self.told_and_reported()
        ]

    def _still_from(self, stretch: RecordingStretch) -> float:
        """
        The moment after which nothing moves in the film until the stretch's end.
        """
        watched = [image for image in self.film.images if stretch.holds(image.seconds)]
        last_moving = stretch.start
        previous = None
        for image in watched:
            small = cv2.resize(cv2.cvtColor(self.framing.of(image.image), cv2.COLOR_RGB2GRAY), (240, 135))
            if previous is not None and float(np.mean(np.abs(small.astype(np.int16) - previous.astype(np.int16)))) > MOTION_THRESHOLD:
                last_moving = image.seconds
            previous = small
        return last_moving


class Phase(Enum):
    """
    What a run is doing at a moment, as its tile is badged: the values are the badge's
    word and its colour.
    """

    PERTURBATION = ("perturbation", Ink.ANSWER)
    PERCEIVING = ("perceiving", Ink.TEXT)
    EXECUTING = ("executing", Ink.TEXT)

    @property
    def word(self) -> str:
        return self.value[0]

    @property
    def color(self) -> Ink:
        return self.value[1]


# %% what the look found, drawn on the film


@dataclass
class DetectionsOnTheFilm:
    """
    The look run over the frames the robot stood still for, every so many of them, and
    its findings drawn on those frames, computed once and kept.
    """

    run: RecordedRun
    """
    The run.
    """

    idle: IdleStretches
    """
    When the robot stood still.
    """

    every_nth: int = 2
    """
    The look runs on one idle frame in this many.
    """

    cache: SceneCache = field(default_factory=lambda: SceneCache("perturbations"))
    """
    Where the drawn frames are kept between renders.
    """

    @cached_property
    def pipeline(self) -> MontessoriPerceptionPipeline:
        return perception_pipeline(recorded_world(), pieces=ROBOT_TABLE_PIECES)

    def _key(self, part: str) -> str:
        return f"{self.run.episode_identifier}_{part}"

    @cached_property
    def drawn_at(self) -> List[float]:
        """
        The moments of the recording a drawn frame was kept for, in order.
        """
        kept = self.cache.record(self._key("drawn"))
        if kept is None:
            kept = self._detect_and_keep()
        return kept["seconds"]

    def picture_at(self, seconds: float) -> Optional[Frame]:
        """
        The drawn frame kept for a moment, or None where the look was not run then.
        """
        matches = [moment for moment in self.drawn_at if abs(moment - seconds) < 1e-3]
        if not matches:
            return None
        return self.cache.picture(self._key(f"{matches[0]:09.3f}"))

    def _detect_and_keep(self) -> dict:
        camera = self.run.camera
        intrinsics = camera.intrinsics
        reference_frame_T_camera = camera.reference_frame_T_camera
        reader = open_bag(
            self.run.bag, [str(CameraTopic.COLOR), str(CameraTopic.DEPTH), RAW_DEPTH_TOPIC]
        )
        depth = None
        first = None
        index = 0
        seconds: List[float] = []
        while reader.has_next():
            topic, payload, stamp = reader.read_next()
            if topic != str(CameraTopic.COLOR):
                depth = _decode_depth(topic, payload)
                continue
            first = stamp if first is None else first
            moment = (stamp - first) / 1e9
            index += 1
            if depth is None or index % self.every_nth or not self.idle.idle_at(moment):
                continue
            message = deserialize_message(payload, CompressedImage)
            frame = RgbdFrame(
                color=decode_compressed_color_image(bytes(message.data), message.format),
                depth=depth,
                intrinsics=intrinsics,
                reference_frame_T_camera=reference_frame_T_camera,
            )
            scene = self.pipeline.detect(frame)
            drawn = DetectionOverlay(line_width=3).draw(CameraView(frame=frame), scene)
            self.cache.keep_picture(
                self._key(f"{moment:09.3f}"), cv2.cvtColor(drawn, cv2.COLOR_BGR2RGB)
            )
            seconds.append(moment)
        record = {"seconds": seconds}
        self.cache.keep_record(self._key("drawn"), record)
        return record


# %% one tile


@dataclass
class PerturbationTile:
    """
    One episode of the grid: its film, and the look's findings over it.
    """

    run: RecordedRun
    """
    The episode.
    """

    film: CameraFilm = field(init=False)
    """
    The robot's camera, decoded.
    """

    idle: IdleStretches = field(init=False)
    """
    When the robot stood still.
    """

    perturbing: PerturbingStretches = field(init=False)
    """
    When a person was moving something.
    """

    detections: DetectionsOnTheFilm = field(init=False)
    """
    What the look found while the robot stood still.
    """

    framing: Framing = TABLE_FRAMING
    """
    What of each picture is shown.
    """

    def __post_init__(self) -> None:
        self.film = CameraFilm(self.run)
        self.idle = IdleStretches(self.run)
        self.perturbing = PerturbingStretches(self.run, self.film)
        self.detections = DetectionsOnTheFilm(self.run, self.idle)

    def picture_at(self, seconds: float) -> Tuple[Frame, Optional[Phase]]:
        """
        The film at a moment, with the look's findings drawn where it ran near then, and
        the phase the run is in: a person perturbing the scene before anything else, the
        robot executing while it moves, else perceiving where findings are drawn.

        :param seconds: The moment of the recording; past its end, the last frame stands.
        :return: The picture, and the phase, or None where nothing is going on.
        """
        image = self.film.at(seconds)
        picture, perceiving = self._drawn_at(image)
        if self.perturbing.perturbing_at(image.seconds):
            return picture, Phase.PERTURBATION
        if not self.idle.idle_at(image.seconds):
            return picture, Phase.EXECUTING
        return picture, Phase.PERCEIVING if perceiving else None

    def _drawn_at(self, image: TimedImage) -> Tuple[Frame, bool]:
        """
        The image with the look's findings drawn on it where the look ran near then.

        :return: The picture, framed, and whether findings are drawn on it.
        """
        drawn = self.detections.picture_at(image.seconds)
        if drawn is not None:
            return self.framing.of(drawn), True
        # the look ran on one idle frame in a few; the frame before carries its findings on
        earlier = [moment for moment in self.detections.drawn_at if 0 <= image.seconds - moment < 0.7]
        if earlier:
            return self.framing.of(self.detections.picture_at(earlier[-1])), True
        return self.framing.of(image.image), False


# %% the grid


@dataclass(frozen=True)
class GridLabels:
    """
    The words the grid carries: one per column, one per row, one header line over it,
    and what the question put to long term memory is asked over.
    """

    columns: Sequence[str] = ("no perturbation", "piece shoved", "board moved")
    rows: Sequence[str] = ("scene stands still", "robot sorts")
    header: str = ""
    """
    The one line over the grid: what the trials are, and what of them is shown.
    """

    long_term_header: str = ""
    """
    What the question is asked over, on its card.
    """

    def tag(self, row: int, column: int) -> str:
        """
        What a tile is called while it stands enlarged: its column and its row.
        """
        return f"{self.columns[column]} · {self.rows[row]}"


@dataclass(frozen=True)
class GridLayout:
    """
    Where everything of the grid lies, at the video's size.
    """

    resolution: Resolution
    """
    The size the grid draws itself at.
    """

    rows: int
    """
    How many rows of tiles.
    """

    columns: int
    """
    How many columns of tiles.
    """

    band_height: int = 200
    """
    Pixels the band over the grid takes: the header line, or the question's card.
    """

    row_label: int = 150
    """
    Pixels the row labels take, left of the tiles.
    """

    column_label: int = 36
    """
    Pixels the column names take, over the tiles.
    """

    gap: int = 12

    @property
    def band(self) -> Area:
        """
        The band over the grid, where the trials are named and long term memory asked.
        """
        return Area(MARGIN, HEADER_CLEAR, self.resolution.width - 2 * MARGIN, self.band_height)

    @property
    def rows_top(self) -> float:
        return self.band.bottom + self.column_label

    @property
    def room(self) -> Area:
        """
        Where the tiles may lie: right of the row labels, under the column names, above
        the band left for captions.
        """
        left = MARGIN + self.row_label
        return Area(left, self.rows_top, self.resolution.width - MARGIN - left, self.resolution.stage_height - MARGIN / 2 - self.rows_top)

    @property
    def tile_height(self) -> float:
        by_width = (self.room.width - (self.columns - 1) * self.gap) / self.columns * 9 / 16
        by_height = (self.room.height - (self.rows - 1) * self.gap) / self.rows
        return min(by_width, by_height)

    @property
    def tile_width(self) -> float:
        return self.tile_height * 16 / 9

    def tile(self, row: int, column: int) -> Area:
        across = self.columns * self.tile_width + (self.columns - 1) * self.gap
        left = self.room.x + (self.room.width - across) / 2
        return Area(
            left + column * (self.tile_width + self.gap),
            self.rows_top + row * (self.tile_height + self.gap),
            self.tile_width,
            self.tile_height,
        )

    @property
    def front(self) -> Area:
        """
        Where a tile lies enlarged: near the full frame, over the grid, above the
        captions.
        """
        room = Area(MARGIN, HEADER_CLEAR, self.resolution.width - 2 * MARGIN, self.resolution.stage_height - MARGIN / 2 - HEADER_CLEAR)
        return room.fitting(16 / 9)


@dataclass(frozen=True)
class Zoom:
    """
    One tile brought to the front: which, from where in its recording it replays, how
    fast, and for how long it is held.
    """

    row: int
    column: int
    replay_from: float
    """
    Seconds into the recording the tile replays from: just before the person moves.
    """

    held_for: float
    """
    Seconds the tile is held at the front.
    """

    speed: float = 3.0
    """
    How many recorded seconds pass per second played while it is held.
    """

    @property
    def lasts(self) -> float:
        """
        Seconds the zoom takes in all: growing, held, and shrinking back.
        """
        return 2 * ZOOM + self.held_for


@dataclass
class GridSequence(Scene):
    """
    The six episodes playing together at one speed-up, each badged with what it is
    doing; then one tile after another brought to the front and replayed slower from
    just before the person moves, the rest paused and dimmed; then the grid playing on
    with long term memory asked which episodes the robot picked the cube up in, the
    episodes it names outlined.
    """

    tiles: List[List[PerturbationTile]]
    """
    The tiles, row by row, matching the labels.
    """

    labels: GridLabels
    """
    What the rows and columns are called, and the lines over the grid.
    """

    zooms: Tuple[Zoom, ...]
    """
    The tiles brought to the front, in order.
    """

    question: RememberedQuestion
    """
    What long term memory is asked once the grid plays on.
    """

    speed: float = 6.0
    """
    How many recorded seconds pass per second played while the grid plays.
    """

    play_for: float = 4.0
    """
    Seconds the grid plays before the first zoom.
    """

    asked_after: float = 0.5
    """
    Seconds the grid plays on after the last zoom before the question comes up.
    """

    question_for: float = 6.0
    """
    Seconds the question takes, from arriving to its answer having been read.
    """

    answered_after: float = 4.0
    """
    Seconds after the question arrives that its answer is given: as the line asking it
    ends.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size the grid draws itself at.
    """

    @property
    def layout(self) -> GridLayout:
        return GridLayout(self.resolution, rows=len(self.tiles), columns=len(self.labels.columns))

    # %% when things happen

    def zoom_starts(self, number: int) -> float:
        """
        Seconds into the scene a zoom starts growing.
        """
        return self.play_for + sum(zoom.lasts for zoom in self.zooms[:number])

    @property
    def resumes_at(self) -> float:
        """
        Seconds into the scene the grid plays on after the last zoom.
        """
        return self.zoom_starts(len(self.zooms))

    @property
    def asked_at(self) -> float:
        return self.resumes_at + self.asked_after

    @property
    def duration(self) -> float:
        return self.asked_at + self.question_for

    @property
    def dissolves_in(self) -> bool:
        # the scene before writes text where this one does: a cut, not a crossfade
        return False

    def recording_at(self, seconds: float) -> float:
        """
        The moment of the recordings the grid shows at a moment of the scene: playing,
        paused through the zooms, playing on after them.
        """
        if seconds < self.play_for:
            return seconds * self.speed
        if seconds < self.resumes_at:
            return self.play_for * self.speed
        return (self.play_for + seconds - self.resumes_at) * self.speed

    def zoom_at(self, seconds: float) -> Optional[Tuple[Zoom, float, float]]:
        """
        The zoom under way at a moment, how far its tile is out at the front, from
        zero to one, and how long it has been held there.
        """
        for number, zoom in enumerate(self.zooms):
            since = seconds - self.zoom_starts(number)
            if 0.0 <= since < zoom.lasts:
                if since < ZOOM:
                    return zoom, eased(since / ZOOM), 0.0
                if since < ZOOM + zoom.held_for:
                    return zoom, 1.0, since - ZOOM
                return zoom, 1.0 - eased((since - ZOOM - zoom.held_for) / ZOOM), zoom.held_for
        return None

    def asked_since(self, seconds: float) -> Optional[float]:
        """
        Seconds the question has been up at a moment, or None before it.
        """
        since = seconds - self.asked_at
        return since if since >= 0 else None

    def answered_at(self, seconds: float) -> float:
        """
        How far the answer has come up at a moment, from zero to one.
        """
        since = self.asked_since(seconds)
        return eased((since - self.answered_after) / ANSWER_FADE) if since is not None else 0.0

    # %% drawing

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        zoom = self.zoom_at(seconds)
        lit = self.answered_at(seconds)
        frame = self._band(frame, self.asked_since(seconds), lit)
        frame = self._grid(frame, self.recording_at(seconds), zoom, lit)
        speed = zoom[0].speed if zoom is not None and zoom[1] >= 1.0 else self.speed
        return speed_badged(frame, speed)

    def _grid(self, frame: Frame, recording: float, zoom: Optional[Tuple[Zoom, float, float]], lit: float) -> Frame:
        """
        The tiles, named by row and column, each badged with its phase; the ones the
        answer names outlined once lit; and the zoomed tile drawn last, at the front.
        """
        layout = self.layout
        heading = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.TEXT.rgb)
        for column, name in enumerate(self.labels.columns):
            frame = heading.written(frame, name, (layout.tile(0, column).centre[0], layout.band.bottom + layout.column_label / 2), Anchor.CENTRE_MIDDLE)
        for row, name in enumerate(self.labels.rows):
            cell = layout.tile(row, 0)
            frame = heading.written(frame, name.replace(" ", "\n", 1), (MARGIN + layout.row_label / 2 - 8, cell.centre[1]), Anchor.CENTRE_MIDDLE)
        front = None
        for row, tiles in enumerate(self.tiles):
            for column, tile in enumerate(tiles):
                cell = layout.tile(row, column)
                zoomed = zoom is not None and (zoom[0].row, zoom[0].column) == (row, column)
                if zoomed:
                    front = (tile, cell, zoom)
                    continue
                picture, phase = tile.picture_at(recording)
                named = self.question.names(tile.run.episode_identifier)
                faded = DIM if zoom is not None and zoom[1] > 0.0 else (0.55 * lit if lit > 0 and not named else 0.0)
                frame = self._tile_drawn(frame, cell, dimmed(picture, faded) if faded else picture, phase, tag="")
                if lit > 0 and named:
                    frame = framed(frame, cell.inset(-3), Ink.ANSWER.rgb, thickness=6)
        if front is not None:
            tile, cell, (zoom, out, held) = front
            where = cell.towards(layout.front, out)
            # from the moment it replays from as soon as it comes forward, not the grid's paused moment
            moment = zoom.replay_from + held * zoom.speed
            picture, phase = tile.picture_at(moment)
            frame = self._tile_drawn(frame, where, picture, phase, tag=self.labels.tag(zoom.row, zoom.column) if out >= 1.0 else "")
        return frame

    @staticmethod
    def _tile_drawn(frame: Frame, cell: Area, picture: Frame, phase: Optional[Phase], tag: str) -> Frame:
        frame = filled(frame, cell, Ink.TEXT.rgb)
        frame = fitted(frame, picture, cell)
        if phase is not None:
            frame = _phase_badged(frame, cell, phase)
        if tag:
            frame = badged(frame, tag, (cell.x + 8, cell.y + 8))
        return frame

    def _band(self, frame: Frame, since: Optional[float], lit: float) -> Frame:
        """
        The header line over the grid while no question is up; the question's card
        once it is: what it is asked over, the question, the query behind it and, in
        its turn, the answer.

        :param frame: The frame.
        :param since: Seconds the question has been up, or None before it.
        :param lit: How far the answer has come up, from zero to one.
        """
        band = self.layout.band
        if since is None:
            return Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb).written(
                frame, self.labels.header, (band.x, band.y + 14), Anchor.LEFT_MIDDLE
            )
        question = self.question
        frame = framed(frame, band, Ink.HAIRLINE.rgb, thickness=2)
        frame = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.MEMORY.rgb).written(
            frame, BACKEND_NAME, (band.x + 16, band.y + 18), Anchor.LEFT_MIDDLE
        )
        frame = Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb).written(
            frame, self.labels.long_term_header, (band.x + 16 + Typesetting(size=LABEL_SIZE, face=Face.BOLD).width_of(BACKEND_NAME) + 16, band.y + 18), Anchor.LEFT_MIDDLE
        )
        frame = Typesetting(size=BODY_SIZE, face=Face.BOLD).written(
            frame, question.english, (band.x + 16, band.y + 46), Anchor.LEFT_MIDDLE
        )
        code = CodeTypesetting(size=LABEL_SIZE)
        for number, line in enumerate(question.statement):
            frame = code.written(frame, line, (band.x + 16, band.y + 76 + number * 24))
        if lit > 0:
            on_screen = sum(question.names(tile.run.episode_identifier) for row in self.tiles for tile in row)
            answer = f"→ {len(question.episodes)} episodes; {on_screen} of them are on screen"
            written = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.ANSWER.rgb).written(
                frame, answer, (band.right - 16, band.bottom - 22), Anchor.RIGHT_MIDDLE
            )
            frame = blended(frame, written, lit)
        return frame


def _phase_badged(frame: Frame, cell: Area, phase: Phase) -> Frame:
    """
    A tile's phase on a badge low in the tile, where the board is not: neutral dark,
    the perturbation in the accent.
    """
    lettering = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.PAPER.rgb)
    badge = Area(cell.x + 8, cell.bottom - 8 - BADGE_HEIGHT, lettering.width_of(phase.word) + 2 * BADGE_PADDING, BADGE_HEIGHT)
    frame = filled(frame, badge, phase.color.rgb)
    return lettering.written(frame, phase.word, badge.centre, Anchor.CENTRE_MIDDLE)
