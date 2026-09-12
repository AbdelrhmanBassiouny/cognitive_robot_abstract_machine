"""
:mod:`~experiments.tracy_experiments.pickup.pickup_demo_real` with MuJoCo standing in
for the robot and for the camera: the same run, on the same table, seen through the same
camera, with the robot's own world knowing no more than the real one does.

Two worlds stand for the lab. The *reality* is what the simulation runs: Tracy on its
own table, the shape-sorting board and the smaller set of pieces standing where the tape
put them on 2026-09-11, all of it physics. The *belief* is what the robot plans in, and
it starts as the real demo's fetched world does, holding Tracy and nothing else; the
board and the pieces reach it only by looking, through a camera hung on Tracy's
``camera_link`` at the optical pose the shipped captures carry, rendering the reality.
Every plan is then made in the belief and played back on the reality's actuators, the
belief's joints following the simulated ones, so a piece is picked from where the look
put it and not from where it is.

Run with (the ``iai_tracy_description`` ROS package must be built and sourced)::

    python -m experiments.tracy_experiments.pickup.pickup_demo_mujoco

Pass ``--headless`` to run without the viewer, and ``--video-directory`` to say where the
run's videos -- the whole table from above, and what the robot's camera saw -- and the
picture of what the look found are written.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")

import cv2
import mujoco
import numpy as np
from typing_extensions import Dict, List, Optional

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ApproachDirection, Arms, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.factories import sequential
from coraplex.view_manager import ViewManager
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.overlay import CameraView, DetectionOverlay
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.perception.scene_source import RepeatedLook
from experiments.montessori.perception.simulated_camera import (
    CAMERA_T_OPTICAL,
    SimulatedCamera,
)
from experiments.montessori.perception.simulated_setup import (
    CAMERA_FIELD_OF_VIEW,
    CAMERA_PICTURE_HEIGHT,
    CAMERA_PICTURE_WIDTH,
)
from experiments.montessori.pieces import SMALLER_PIECES, KnownPieceSet
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.montessori.world import BOARD_SCALE
from experiments.tracy_experiments.equipment import (
    TRACY_MOUNT_ROOT_NAME,
    apply_gravity_compensation,
    equip_arms_with_servos,
    equip_grippers_with_servos,
    exclude_self_collision,
    joint_state_of_type,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.grasp_contact import (
    BOARD_FRICTION,
    apply_contact_friction,
    apply_montessori_grasp_contact_parameters,
)
from experiments.tracy_experiments.montessori.world import TracyMontessoriWorld
from experiments.tracy_experiments.pick_and_place_action import (
    GRASP_CLOSE_SWING_CLEARANCE,
    PickUpActionMujoco,
    PlaceActionMujoco,
)
from experiments.tracy_experiments.pickup.perceived_sorting import (
    PerceivedSorting,
    ShapeSorter,
)
from experiments.tracy_experiments.real_time_simulation import (
    RealTimeSimulation,
    SimulationObserver,
)
from semantic_digital_twin.adapters.multi_sim import MujocoCamera, RegionAppearance
from semantic_digital_twin.adapters.mujoco_video_recording import (
    RecordedVideo,
    VideoResolution,
)
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Actuator

logger = logging.getLogger(__name__)

PICK_ARM = Arms.LEFT
"""
Which arm sorts every piece, as in the real demo.
"""

TRACY_MOUNT_X = 0.0
TRACY_MOUNT_Y = 0.0
"""
Where Tracy's own root is bolted, in the reality's root frame, so that the reality's x
and y are the real table's.
"""

# %% the table as the tape measured it

LAB_BOARD_FRONT_LEFT_CORNER = PlanarPoint(0.99, 0.30)
"""
Where the tape put the corner of the board's lid nearest the robot on the robot's left,
in the robot's frame, on 2026-09-11; the drawers face the robot.
"""

LAB_BOARD_CENTRE = PlanarPoint(
    LAB_BOARD_FRONT_LEFT_CORNER.x + BOARD_SCALE.x / 2,
    LAB_BOARD_FRONT_LEFT_CORNER.y - BOARD_SCALE.y / 2,
)
"""
Where the board's centre stands, from that corner and the lid's own size.
"""

LAB_PIECE_ROW_X = 0.79
"""
How far from the robot the tape put the row of pieces, in metres.
"""

LAB_PIECE_PLACES: Dict[MontessoriShapeCategory, PlanarPoint] = {
    MontessoriShapeCategory.CYLINDER: PlanarPoint(LAB_PIECE_ROW_X, 0.0),
    MontessoriShapeCategory.TRIANGULAR_PRISM: PlanarPoint(LAB_PIECE_ROW_X, 0.10),
    MontessoriShapeCategory.RECTANGULAR_PRISM: PlanarPoint(LAB_PIECE_ROW_X, 0.20),
    MontessoriShapeCategory.CUBE: PlanarPoint(LAB_PIECE_ROW_X, 0.30),
}
"""
Where the tape put the middle of each piece, in the robot's frame.
"""

# %% the camera on Tracy's camera link

CAMERA_NAME = "tracy_camera"
"""
What the simulated camera is called.
"""

CAMERA_LINK_NAME = "camera_link"
"""
The body of Tracy's description the camera hangs on.
"""

CAMERA_LINK_T_OPTICAL = HomogeneousTransformationMatrix.from_xyz_rpy(
    x=0.041737,
    y=-0.014025,
    z=0.009141,
    roll=-1.363448,
    pitch=0.003959,
    yaw=-1.546731,
).to_np()
"""
Where the colour camera's optical frame stands on the ``camera_link`` this scene is
built on.

Read off the shipped captures, which agree on it to a ten-millionth of a metre. It is
not the plain quarter turns a description states between a camera link and its optical
frame: the lab calibrates the camera in the description in Tracy's own ROS workspace,
not in the published one this scene is built from, and this pose carries the difference
between the two so that the simulated camera looks where the real one looked.
"""

OVERVIEW_VIDEO_RESOLUTION = VideoResolution(width=960, height=540)
"""
The size of the film of the whole table.
"""

CAMERA_VIDEO_RESOLUTION = VideoResolution(width=960, height=540)
"""
The size of the film of what the robot's camera saw: the camera's own picture at half
its width, since a film is watched rather than measured.
"""

FRAMES_PER_SECOND = 15
"""
How many frames a second the films keep.
"""


class RunArtifact(StrEnum):
    """
    What a run leaves behind, by the file each is written to.
    """

    OVERVIEW_VIDEO = "table_from_the_side.mp4"
    CAMERA_VIDEO = "robot_camera.mp4"
    DETECTIONS = "what_the_look_found.jpg"


OVERVIEW_CAMERA_NAME = "overview_camera"
"""
What the camera filming the whole table is called.
"""

OVERVIEW_CAMERA_STANDS_AT = Point3(1.55, 0.95, 1.45)
"""
Where the camera filming the table stands, in the reality's root frame: beyond the board
on the robot's left, high enough to see the pieces, the board and the arm at once.
"""

OVERVIEW_CAMERA_LOOKS_AT = Point3(0.85, 0.15, 0.95)
"""
What that camera looks at: the middle of the stretch of table between the pieces and the
board.
"""


def camera_looking_at(
    world: World,
    name: str,
    stands_at: Point3,
    looks_at: Point3,
    resolution: VideoResolution,
) -> MujocoCamera:
    """
    Hang a camera on the world's root, standing somewhere and looking at something.

    :param world: The world the camera is added to.
    :param name: What the camera is called.
    :param stands_at: Where it stands, in the world root frame.
    :param looks_at: The point it looks at, in the world root frame.
    :param resolution: The size of the picture it takes.
    :return: The camera, attached to the world root.
    """
    backwards = np.array(
        [
            float(stands_at.x) - float(looks_at.x),
            float(stands_at.y) - float(looks_at.y),
            float(stands_at.z) - float(looks_at.z),
        ]
    )
    backwards /= np.linalg.norm(backwards)
    right = np.cross([0.0, 0.0, 1.0], backwards)
    right /= np.linalg.norm(right)
    up = np.cross(backwards, right)
    root_R_camera = np.column_stack([right, up, backwards])
    root_T_camera = np.eye(4)
    root_T_camera[:3, :3] = root_R_camera
    x, y, z, real = (
        HomogeneousTransformationMatrix(root_T_camera).to_quaternion().to_np().tolist()
    )
    camera = MujocoCamera(
        name=name,
        body=world.root,
        position=[float(stands_at.x), float(stands_at.y), float(stands_at.z)],
        quaternion=[real, x, y, z],
        resolution=[float(resolution.width), float(resolution.height)],
    )
    world.root.simulator_additional_properties.append(camera)
    return camera


def camera_on_tracy(world: World) -> MujocoCamera:
    """
    Hang the camera on Tracy's ``camera_link``, where the real one stands, looking the
    way it looks and seeing as wide as it sees.

    :param world: The world holding Tracy.
    :return: The camera, attached to the link.
    """
    link_T_camera = CAMERA_LINK_T_OPTICAL @ np.linalg.inv(CAMERA_T_OPTICAL)
    x, y, z, real = (
        HomogeneousTransformationMatrix(link_T_camera).to_quaternion().to_np().tolist()
    )
    camera_link = world.get_body_by_name(CAMERA_LINK_NAME)
    camera = MujocoCamera(
        name=CAMERA_NAME,
        body=camera_link,
        position=link_T_camera[:3, 3].tolist(),
        quaternion=[real, x, y, z],
        fovy=CAMERA_FIELD_OF_VIEW,
        resolution=[float(CAMERA_PICTURE_WIDTH), float(CAMERA_PICTURE_HEIGHT)],
    )
    camera_link.simulator_additional_properties.append(camera)
    return camera


@dataclass
class SimulatedLook(RepeatedLook):
    """
    A look through a camera standing in the simulation, taken afresh for every request.
    """

    camera: SimulatedCamera
    """
    The camera to look through.
    """

    frame: RgbdFrame = field(init=False)
    """
    The last picture taken, kept so what the look found can be drawn over it.
    """

    scene_found: MontessoriScene = field(init=False)
    """
    What the last look found.
    """

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        self.frame = self.camera.frame()
        self.scene_found = self.pipeline.detect(self.frame, request)
        return self.scene_found

    def picture_of_what_was_found(self) -> np.ndarray:
        """
        :return: The last picture taken, with what the look found drawn over it.
        """
        return DetectionOverlay().draw(CameraView(self.frame), self.scene_found)


# %% the two worlds


@dataclass
class SimulatedLab:
    """
    The lab twice: as the simulation runs it, and as the robot knows it.
    """

    reality: World
    """
    The world the physics runs: Tracy, the board and the pieces.
    """

    scene: TracyMontessoriWorld
    """
    The board and the pieces, as the reality was built from them.
    """

    robot: Tracy
    """
    Tracy as the reality holds it, whose joints the actuators drive.
    """

    belief: World
    """
    The world the robot plans in: Tracy and nothing else, until a look adds to it.
    """

    believed_robot: Tracy
    """
    Tracy as the belief holds it, whose joints follow the reality's.
    """

    camera: SimulatedCamera
    """
    Tracy's camera, standing in the reality and reporting in the belief's frame.
    """

    actuators: Dict[str, Actuator]
    """
    Every joint's own actuator in the reality, keyed by joint name.
    """

    @classmethod
    def build(
        cls,
        pieces: KnownPieceSet = SMALLER_PIECES,
        board_centre: PlanarPoint = LAB_BOARD_CENTRE,
        piece_places: Dict[MontessoriShapeCategory, PlanarPoint] = LAB_PIECE_PLACES,
    ) -> SimulatedLab:
        """
        Build both worlds, with the reality laid out as the lab table was.

        :param pieces: The set of pieces standing on the table.
        :param board_centre: Where the board's centre stands, in the robot's frame.
        :param piece_places: Where the middle of each piece stands, in the robot's
            frame.
        """
        tracy = parse_tracy()
        mount_position, table_top_z = tracy_table_mount_position(
            tracy, x=TRACY_MOUNT_X, y=TRACY_MOUNT_Y
        )
        scene = TracyMontessoriWorld(
            shapes_are_movable=True,
            table_top_z=table_top_z,
            pieces=pieces,
            board_position=Point3(board_centre.x, board_centre.y, 0.0),
        )
        robot = scene.mount_stationary_robot(Tracy, tracy, mount_position, 0.0)
        reality = scene.world
        for shape in reality.get_semantic_annotations_by_type(MontessoriShape):
            cls._stand_piece_at(reality, shape, piece_places[shape.shape_category])
        cls._park(reality, robot)

        apply_montessori_grasp_contact_parameters(
            reality.get_semantic_annotations_by_type(MontessoriShape)
        )
        apply_contact_friction([scene.board.root], BOARD_FRICTION)
        apply_gravity_compensation(reality, robot)
        exclude_self_collision(reality, robot)
        actuators = {
            **equip_arms_with_servos(reality, robot),
            **equip_grippers_with_servos(reality, robot),
        }

        belief = parse_tracy()
        believed_robot = Tracy.from_world(belief)
        cls._park(belief, believed_robot)

        camera = SimulatedCamera(
            world=reality,
            camera=camera_on_tracy(reality),
            reference_frame=reality.get_body_by_name(TRACY_MOUNT_ROOT_NAME),
            region_appearance=RegionAppearance.HIDDEN,
        )
        return cls(
            reality=reality,
            scene=scene,
            robot=robot,
            belief=belief,
            believed_robot=believed_robot,
            camera=camera,
            actuators=actuators,
        )

    @staticmethod
    def _stand_piece_at(
        world: World, shape: MontessoriShape, place: PlanarPoint
    ) -> None:
        """
        Move a free piece to a place on the table, at the height it already rests at.

        :param world: The world holding the piece.
        :param shape: The piece to move.
        :param place: Where its middle stands, in the world root frame.
        """
        connection = shape.root.parent_connection
        resting_height = float(connection.origin.to_np()[2, 3])
        connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=place.x, y=place.y, z=resting_height, reference_frame=world.root
        )
        world.notify_state_change()

    @staticmethod
    def _park(world: World, robot: Tracy) -> None:
        """
        Put both arms in their parked pose and open the picking gripper.

        :param world: The world holding the robot.
        :param robot: The robot to park.
        """
        joint_state_of_type(robot.left_arm.end_effector, GripperState.OPEN).apply_to(
            world
        )
        joint_state_of_type(robot.left_arm, StaticJointState.PARK).apply_to(world)
        joint_state_of_type(robot.right_arm, StaticJointState.PARK).apply_to(world)
        world.notify_state_change()

    def hold_the_parked_pose(self, simulation: RealTimeSimulation) -> None:
        """
        Command every arm actuator to the parked pose the reality was built in, so the
        arms stay there once the physics runs.

        :param simulation: The running simulation.
        """
        for arm in (self.robot.left_arm, self.robot.right_arm):
            parked = joint_state_of_type(arm, StaticJointState.PARK)
            for connection, target in zip(parked.connections, parked.target_values):
                simulation.command(self.actuators[connection.raw_dof.name.name], target)
        simulation.advance(0.5)

    def perception_pipeline(
        self, pieces: KnownPieceSet
    ) -> MontessoriPerceptionPipeline:
        """
        :param pieces: The set of pieces the look fits.
        :return: The pipeline reading a look at the belief, the way the real node builds
            it from the world the robot publishes.
        """
        return MontessoriPerceptionPipeline.of_world(
            self.belief, self.believed_robot.root, pieces
        )

    def believed_position_of(self, piece: MontessoriShape) -> np.ndarray:
        """
        :param piece: A piece the belief holds.
        :return: Where the belief stands it, in the reality's root frame.
        """
        tracy_root = self.reality.get_body_by_name(TRACY_MOUNT_ROOT_NAME)
        tracy_root_T_piece = self.belief.compute_forward_kinematics_np(
            self.belief.root, piece.root
        )
        reality_T_tracy_root = self.reality.compute_forward_kinematics_np(
            self.reality.root, tracy_root
        )
        return (reality_T_tracy_root @ tracy_root_T_piece)[:3, 3]

    def real_piece_of(self, category: MontessoriShapeCategory) -> MontessoriShape:
        """
        :param category: The kind of piece.
        :return: The reality's one piece of that kind.
        """
        [shape] = [
            shape
            for shape in self.reality.get_semantic_annotations_by_type(MontessoriShape)
            if shape.shape_category is category
        ]
        return shape

    def real_position_of(self, category: MontessoriShapeCategory) -> np.ndarray:
        """
        :param category: The kind of piece.
        :return: Where the reality's one piece of that kind stands, in the reality's root
            frame.
        """
        return self.reality.compute_forward_kinematics_np(
            self.reality.root, self.real_piece_of(category).root
        )[:3, 3]

    def containment_in_its_hole(self, category: MontessoriShapeCategory) -> float:
        """
        How much of the reality's piece of a kind stands in the space under the hole it
        belongs in: one once it has gone through the hole, zero while it rests on the
        table or on the lid.

        :param category: The kind of piece.
        """
        piece = self.real_piece_of(category)
        hole = self.scene.board.hole_for(piece)
        return InsideOf(piece.root, hole.landing_region).compute_containment_ratio()


# %% sorting with the actuators


@dataclass
class MujocoSortingRig(ShapeSorter):
    """
    Sorts a piece the belief holds by driving the reality's actuators: each reach is
    planned in the belief and played back on the simulation.
    """

    simulation: RealTimeSimulation
    """
    The running simulation of the reality.
    """

    actuators: Dict[str, Actuator]
    """
    Every joint's own actuator, keyed by joint name.
    """

    context: Context
    """
    The plan context, bound to the belief and the robot as the belief holds it.
    """

    grasp_description: GraspDescription
    """
    Grasp used for every piece.
    """

    def sort(self, piece: MontessoriShape, release_pose: Pose) -> None:
        plan = sequential(
            [
                PickUpActionMujoco(
                    object_designator=piece.root,
                    arm=PICK_ARM,
                    grasp_description=self.grasp_description,
                    sim=self.simulation,
                    actuators=self.actuators,
                ),
                # The fingers hold the piece the grasp's swing clearance below their
                # midpoint, so opening with the midpoint that far above the release pose
                # lets the piece go with its centre there.
                PlaceActionMujoco(
                    object_designator=piece.root,
                    target_location=release_pose,
                    arm=PICK_ARM,
                    sim=self.simulation,
                    actuators=self.actuators,
                    place_hover_clearance=GRASP_CLOSE_SWING_CLEARANCE,
                ),
            ],
            self.context,
        ).plan
        plan.perform()
        logger.info("%s sorted.", piece.name)


# %% filming


@dataclass
class SimulationFilm(SimulationObserver):
    """
    Films a running simulation through one of its cameras, a frame every so much
    simulated time.
    """

    simulation: RealTimeSimulation
    """
    The simulation to film.
    """

    camera_name: str
    """
    The camera to film through, which the simulation's model was built with.
    """

    resolution: VideoResolution
    """
    The size of the frames.
    """

    frames_per_second: int = FRAMES_PER_SECOND
    """
    How many frames a second of simulated time the film keeps.
    """

    frames: List[np.ndarray] = field(init=False, default_factory=list)
    """
    The frames kept so far.
    """

    _next_frame_at: float = field(init=False, default=0.0)
    """
    The simulated time the next frame is due at.
    """

    _renderer: Optional[mujoco.Renderer] = field(init=False, default=None, repr=False)
    """
    What draws the frames, built on the first frame and kept: a renderer is expensive to
    build, and a film asks for hundreds of frames.
    """

    def simulation_advanced(self, simulated_time: float) -> None:
        if simulated_time < self._next_frame_at:
            return
        self._next_frame_at = simulated_time + 1.0 / self.frames_per_second
        simulator = self.simulation.multi_sim.simulator
        with simulator._model_lock:
            if self._renderer is None:
                self._renderer = mujoco.Renderer(
                    simulator._mj_model, self.resolution.height, self.resolution.width
                )
            self._renderer.update_scene(simulator._mj_data, self.camera_name)
            self.frames.append(self._renderer.render().copy())

    def video(self) -> RecordedVideo:
        """
        :return: The film, ready to be written.
        """
        return RecordedVideo(
            frames=self.frames, frames_per_second=self.frames_per_second
        )

    def close(self) -> None:
        """
        Let go of the renderer, once the simulation it drew from has stopped.
        """
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None


# %% the run


@dataclass
class SimulatedPickupDemo:
    """
    The real demo's run, performed in the simulated lab and filmed.
    """

    lab: SimulatedLab
    """
    The two worlds the run is performed in.
    """

    headless: bool = True
    """
    Whether the simulation runs without a viewer window.
    """

    paced_to_the_wall_clock: bool = False
    """
    Whether the motion runs at life speed, for watching, or as fast as it can.
    """

    pieces: KnownPieceSet = SMALLER_PIECES
    """
    The set of pieces the look is told stands on the table.
    """

    filmed: bool = True
    """
    Whether the run is filmed; drawing the frames is most of what an unpaced run costs.
    """

    sorting: PerceivedSorting = field(init=False)
    """
    The run, once :meth:`perform` has built it.
    """

    look: SimulatedLook = field(init=False)
    """
    The camera as the run looks through it, once :meth:`perform` has built it.
    """

    overview: SimulationFilm = field(init=False)
    """
    The film of the whole table, once :meth:`perform` has run.
    """

    camera_film: SimulationFilm = field(init=False)
    """
    The film of what the robot's camera saw, once :meth:`perform` has run.
    """

    def perform(self) -> None:
        """
        Start the simulation, look, sort every piece the look found, and stop.
        """
        overview_camera = camera_looking_at(
            self.lab.reality,
            OVERVIEW_CAMERA_NAME,
            OVERVIEW_CAMERA_STANDS_AT,
            OVERVIEW_CAMERA_LOOKS_AT,
            OVERVIEW_VIDEO_RESOLUTION,
        )
        simulation = RealTimeSimulation(
            world=self.lab.reality,
            headless=self.headless,
            paced_to_the_wall_clock=self.paced_to_the_wall_clock,
            region_appearance=RegionAppearance.HIDDEN,
            followers=[self.lab.belief],
        )
        self.overview = SimulationFilm(
            simulation, OVERVIEW_CAMERA_NAME, OVERVIEW_VIDEO_RESOLUTION
        )
        self.camera_film = SimulationFilm(
            simulation, CAMERA_NAME, CAMERA_VIDEO_RESOLUTION
        )
        if self.filmed:
            simulation.observers.extend([self.overview, self.camera_film])
        self.lab.camera.drawn_by = simulation.multi_sim
        self.look = SimulatedLook(
            pipeline=self.lab.perception_pipeline(self.pieces), camera=self.lab.camera
        )
        context = Context(
            self.lab.belief, self.lab.believed_robot, evaluate_conditions=False
        )
        self.sorting = PerceivedSorting(
            scene=PerceivedScene(
                world=self.lab.belief, look=self.look, described_board=lab_board()
            ),
            sorter=MujocoSortingRig(
                simulation=simulation,
                actuators=self.lab.actuators,
                context=context,
                grasp_description=GraspDescription(
                    ApproachDirection.FRONT,
                    VerticalAlignment.TOP,
                    ViewManager.get_end_effector_view(
                        PICK_ARM, self.lab.believed_robot
                    ),
                ),
            ),
        )
        with simulation, self.lab.camera:
            self.lab.hold_the_parked_pose(simulation)
            self.sorting.perceive()
            self.sorting.sort_every_piece()
            simulation.advance(1.0)
            self.overview.close()
            self.camera_film.close()
        overview_camera.body.simulator_additional_properties.remove(overview_camera)

    def write_artifacts(self, directory: Path) -> List[Path]:
        """
        Write the two films and the picture of what the look found.

        :param directory: Where to write them; created if it does not exist.
        :return: The files written.
        """
        directory.mkdir(parents=True, exist_ok=True)
        detections = directory / RunArtifact.DETECTIONS
        cv2.imwrite(str(detections), self.look.picture_of_what_was_found())
        return [
            self.overview.video().write(directory / RunArtifact.OVERVIEW_VIDEO),
            self.camera_film.video().write(directory / RunArtifact.CAMERA_VIDEO),
            detections,
        ]


def parse_arguments() -> argparse.Namespace:
    """
    :return: The demo's own command line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without opening MuJoCo's viewer window, as fast as the machine allows",
    )
    parser.add_argument(
        "--video-directory",
        type=Path,
        default=Path.cwd() / "pickup_demo_videos",
        help="where the run's videos and the picture of what the look found are written",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    demo = SimulatedPickupDemo(
        lab=SimulatedLab.build(),
        headless=arguments.headless,
        paced_to_the_wall_clock=not arguments.headless,
    )
    demo.perform()
    for written in demo.write_artifacts(arguments.video_directory):
        logger.info("Written %s.", written)


if __name__ == "__main__":
    main()
