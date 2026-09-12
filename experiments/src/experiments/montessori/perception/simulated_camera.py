"""
What a camera standing in the twin sees, rendered by MuJoCo.

The fourth place an :class:`~experiments.montessori.perception.camera.RgbdFrame` comes
from, beside a saved capture, a recording and the live camera. Because it answers with
that same frame, whatever reads a look off the real camera reads one off a simulated
scene without knowing the difference, and a backend can be swapped for another without
anything above it changing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import TracebackType

import cv2
import mujoco
import numpy as np
from typing_extensions import Optional, Self, Type

from experiments.montessori.perception.camera import CameraIntrinsics, RgbdFrame
from experiments.montessori.perception.exceptions import (
    SimulatedCameraIsAlreadyLooking,
    SimulatedCameraIsNotLooking,
)
from physics_simulators.mujoco_simulator import MujocoSimulator
from semantic_digital_twin.adapters.multi_sim import (
    MujocoCamera,
    MujocoSim,
    MujocoSynchronizer,
    RegionAppearance,
    select_offscreen_rendering_backend,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Quaternion,
    RotationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% the two ways round a camera's frame is stated

CAMERA_T_OPTICAL = np.diag([1.0, -1.0, -1.0, 1.0])
"""
The turn from the way a simulator states a camera's frame to the way a look is read in.

A simulator points a camera down the way a screen is drawn: x to the right of the
picture, y up it, and the camera looking along its own negative z. A look is read in the
optical frame instead -- x to the right, y *down* the picture, and z along the axis the
camera looks down -- so the two are a half turn about x apart. Getting it wrong leaves
every picture upright and every *left of* the wrong way round.
"""

BACKGROUND_STARTS_AT_FRACTION_OF_THE_FAR_PLANE = 0.999
"""
How much of the way to the far plane a reading has to be to count as showing nothing.

A renderer answers with the far plane's own distance for a pixel no surface falls in,
while an
:attr:`~experiments.montessori.perception.camera.RgbdFrame.depth` of zero is what means
*not measured*, so the two have to be told apart. It is a share of the distance rather
than a distance because the far plane is set from the scene's own size; single-precision
rendering puts the value a fraction either side of it, and nothing a scene holds stands
within a thousandth of a far plane tens of metres away.
"""

# %% a camera in the twin


@dataclass
class SimulatedCamera:
    """
    A camera the twin places, answering with what MuJoCo renders through it.

    Rendering needs a MuJoCo mirror of the world, so the camera is started before it is
    asked for a look and stopped afterwards; used as a context manager it does both. A
    camera standing in a world that is already being simulated draws from that
    simulation instead (:attr:`drawn_by`), since two mirrors of one world cannot be run
    side by side.
    """

    world: World
    """
    The twin the camera stands in and looks at.
    """

    camera: MujocoCamera
    """
    The camera as the twin states it: which body it hangs on and where, how wide an
    angle it sees, and how big a picture it takes.
    """

    reference_frame: Optional[KinematicStructureEntity] = None
    """
    The frame a rendered look reports the camera's pose in, or None for the world's own
    root.
    """

    region_appearance: RegionAppearance = RegionAppearance.HIDDEN
    """
    How much of the regions the twin holds is drawn into the picture.

    Hidden by default, because a region names a volume of space rather than a thing
    standing in it and the real camera this one stands in for sees no such thing.
    """

    drawn_by: Optional[MujocoSim] = None
    """
    A running simulation of :attr:`world` the pictures are drawn from, or None for a
    mirror of the camera's own, built when it starts looking.

    The camera has to be attached to its body before that simulation is built, since a
    simulation draws only the cameras its model was built with.
    """

    _mirror: Optional[MujocoSim] = field(default=None, init=False, repr=False)
    """
    The MuJoCo copy of :attr:`world` the pictures are drawn from, while the camera is
    looking through a mirror of its own.
    """

    def __post_init__(self) -> None:
        if self.reference_frame is None:
            self.reference_frame = self.world.root

    @property
    def width(self) -> int:
        """
        Width of the picture this camera takes, in pixels.
        """
        return int(self.camera.resolution[0])

    @property
    def height(self) -> int:
        """
        Height of the picture this camera takes, in pixels.
        """
        return int(self.camera.resolution[1])

    @property
    def intrinsics(self) -> CameraIntrinsics:
        """
        The pinhole intrinsics the angle and the picture size the twin states amount to.
        """
        return CameraIntrinsics.of_field_of_view(
            self.camera.fovy, self.width, self.height
        )

    @property
    def reference_frame_T_camera(self) -> np.ndarray:
        """
        Where the camera's optical frame stands, in the frame a look is reported in.
        """
        reference_frame_T_body = self.world.compute_forward_kinematics_np(
            self.reference_frame, self.camera.body
        )
        return reference_frame_T_body @ self.body_T_camera @ CAMERA_T_OPTICAL

    @property
    def body_T_camera(self) -> np.ndarray:
        """
        Where the camera hangs on the body it is attached to.

        A simulator orders a quaternion's parts with the real one first, while the twin
        states one with the real part last, so the two are the same turn written two
        ways.
        """
        real, x, y, z = self.camera.quaternion
        body_T_camera = HomogeneousTransformationMatrix.from_point_rotation_matrix(
            rotation_matrix=RotationMatrix.from_quaternion(Quaternion(x, y, z, real))
        ).to_np()
        body_T_camera[:3, 3] = self.camera.position
        return body_T_camera

    def start(self) -> None:
        """
        Build the MuJoCo mirror this camera draws its pictures from, or make room for
        its pictures in the simulation it draws from.

        :raises SimulatedCameraIsAlreadyLooking: If the camera is already looking
            through a mirror of its own.
        """
        if self.drawn_by is not None:
            self._make_room_for_the_picture(self.drawn_by.simulator._mj_model)
            return
        if self._mirror is not None:
            raise SimulatedCameraIsAlreadyLooking(self.camera.name)

        select_offscreen_rendering_backend()
        self._mirror = MujocoSim(
            world=self.world,
            headless=True,
            region_appearance=self.region_appearance,
        )
        self._mirror.synchronizer.sync_rate_hz = (
            MujocoSynchronizer.UNTHROTTLED_SYNC_RATE_HZ
        )
        self._mirror.simulator.start(simulate_in_thread=False, render_in_thread=False)
        self._make_room_for_the_picture(self._mirror.simulator._mj_model)

    def stop(self) -> None:
        """
        Tear the mirror down; a camera drawing from a running simulation leaves that
        simulation running.

        :raises SimulatedCameraIsNotLooking: If a camera with a mirror of its own was
            never started.
        """
        if self.drawn_by is not None:
            return
        if self._mirror is None:
            raise SimulatedCameraIsNotLooking(self.camera.name)
        self._mirror.simulator.stop()
        self._mirror = None

    @property
    def _simulator(self) -> MujocoSimulator:
        """
        What the pictures are drawn from.

        :raises SimulatedCameraIsNotLooking: If the camera has not been started.
        """
        if self.drawn_by is not None:
            return self.drawn_by.simulator
        if self._mirror is None:
            raise SimulatedCameraIsNotLooking(self.camera.name)
        return self._mirror.simulator

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exception_type: Optional[Type[BaseException]],
        exception: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.stop()

    def frame(self) -> RgbdFrame:
        """
        Look at the world as it stands now.

        :raises SimulatedCameraIsNotLooking: If the camera has not been started.
        """
        simulator = self._simulator
        # Only MuJoCo's own stepping recomputes body poses from the joint values, and
        # this mirror is not stepped in the background, so a world moved since the last
        # picture needs the poses worked out again before anything is drawn. Held under
        # one lock with both renders so nothing moves between them.
        with simulator._model_lock:
            mujoco.mj_forward(simulator._mj_model, simulator._mj_data)
            color = simulator.capture_rgb(
                camera_name=self.camera.name, height=self.height, width=self.width
            ).result
            depth = simulator.capture_depth(
                camera_name=self.camera.name, height=self.height, width=self.width
            ).result
            far_plane = self._far_plane(simulator._mj_model)

        return RgbdFrame(
            color=cv2.cvtColor(color, cv2.COLOR_RGB2BGR),
            depth=self._measured_depth(depth, far_plane),
            intrinsics=self.intrinsics,
            reference_frame_T_camera=self.reference_frame_T_camera,
        )

    def _make_room_for_the_picture(self, model: mujoco.MjModel) -> None:
        """
        Widen a model's offscreen buffer to the picture this camera takes.

        A model states how large a picture may be drawn away from a window, and its
        default is smaller than a camera's picture usually is; a renderer asked for more
        than the model allows refuses outright.

        :param model: The MuJoCo model the pictures are drawn from.
        """
        model.vis.global_.offwidth = max(model.vis.global_.offwidth, self.width)
        model.vis.global_.offheight = max(model.vis.global_.offheight, self.height)

    @staticmethod
    def _far_plane(model: mujoco.MjModel) -> float:
        """
        How far a camera of this model sees, in metres.

        :param model: The MuJoCo model the pictures are drawn from.
        """
        return float(model.stat.extent * model.vis.map.zfar)

    @staticmethod
    def _measured_depth(depth: np.ndarray, far_plane: float) -> np.ndarray:
        """
        The rendered depth with the background marked as unmeasured.

        :param depth: What the renderer answered, in metres.
        :param far_plane: How far this model's cameras see.
        """
        background = depth >= far_plane * BACKGROUND_STARTS_AT_FRACTION_OF_THE_FAR_PLANE
        return np.where(background, 0.0, depth).astype(float)
