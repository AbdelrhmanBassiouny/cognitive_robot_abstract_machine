"""
What an answer looks like in the twin: the things it names picked out of the scene, with
everything else faded behind them.

The picture half of a query card. A reader shown a query and a table of numbers has to
take on trust that the answer means anything in the world; shown the same answer drawn
into the scene it was asked of, they can see that it does.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.simulated_camera import SimulatedCamera
from semantic_digital_twin.adapters.multi_sim import (
    MujocoCamera,
    MujocoSim,
    RegionAppearance,
    select_offscreen_rendering_backend,
)
from semantic_digital_twin.spatial_computations.raytracer import RayTracer
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    RotationMatrix,
    Vector3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

# %% the colours a picture tells an answer apart in

ANSWER_COLOR = Color(1.0, 0.78, 0.06, 1.0)
"""
What a body the answer names is drawn in: fully opaque, so it reads as the subject of
the picture rather than as one more thing standing in it.
"""

BACKGROUND_COLOR = Color(0.72, 0.72, 0.74, 0.45)
"""
What everything else is drawn in: one grey, see-through enough that the scene reads as
context without competing with the answer.
"""

LABEL_COLOR = Color(1.0, 1.0, 1.0, 1.0)
"""
What an answer's name is written in.
"""

PICTURE_WIDTH = 960
"""
Width of the picture a render takes when it places the camera itself, in pixels.
"""

PICTURE_HEIGHT = 720
"""
Height of the picture a render takes when it places the camera itself, in pixels.
"""

OVERVIEW_CAMERA_NAME = "paper_overview_camera"
"""
What a render calls the camera it hangs over a scene to frame the whole of it.
"""

POINT_OF_VIEW_CAMERA_NAME = "paper_point_of_view_camera"
"""
What a render calls the camera it puts in a body's own frame.
"""


def drawn(color: Color) -> Tuple[int, int, int]:
    """
    A colour of the twin as the channel values a captured picture is drawn on with.

    A capture holds red, green and blue in that order, one byte each, which is the order
    it is written out in; opacity is not drawn, since a line laid over a picture
    replaces what it covers.

    :param color: The colour the twin states.
    """
    return tuple(round(channel * 255) for channel in color.to_rgb())


# %% asking for a picture of nothing


@dataclass
class NothingToDrawError(DataclassException):
    """
    Raised when a picture is asked of a world holding no geometry to frame a camera
    around.
    """

    world: World
    """
    The world that holds nothing to draw.
    """

    def error_message(self) -> str:
        return "The world holds no geometry, so there is no scene to frame a camera on."

    def suggest_correction(self) -> str:
        return (
            "Render an episode whose world was kept, or hand SceneRender a camera of "
            "its own so it does not have to place one around what the world holds."
        )


# %% where a scene is looked at from


@dataclass(frozen=True)
class PointOfView:
    """
    A scene looked at from something standing in it, which is what a question about one
    object being to a side of another is asked from.
    """

    body: Body
    """
    The body the picture is taken from, in whose frame *left* and *right* mean what the
    question means by them.
    """

    field_of_view: float = 60.0
    """
    The angle the picture spans from its top to its bottom, in degrees.
    """

    width: int = PICTURE_WIDTH
    """
    Width of the picture taken from here, in pixels.
    """

    height: int = PICTURE_HEIGHT
    """
    Height of the picture taken from here, in pixels.
    """

    def camera(self) -> MujocoCamera:
        """
        A camera sitting in :attr:`body`'s own frame and facing the way it faces,
        already attached to it.

        The twin faces a looker down its x-axis with y to its left and z up, while
        MuJoCo points a camera down its own negative z with y up the picture, so the two
        frames are a fixed turn apart -- the turn that makes a body's left the left of
        the picture.
        """
        body_R_camera = RotationMatrix.from_vectors(
            x=Vector3(0.0, -1.0, 0.0), z=Vector3(-1.0, 0.0, 0.0)
        )
        camera = MujocoCamera(
            name=POINT_OF_VIEW_CAMERA_NAME,
            body=self.body,
            quaternion=MujocoCamera.quaternion_of(
                HomogeneousTransformationMatrix.from_point_rotation_matrix(
                    rotation_matrix=body_R_camera
                )
            ),
            fovy=self.field_of_view,
            resolution=[float(self.width), float(self.height)],
        )
        self.body.simulator_additional_properties.append(camera)
        return camera


# %% the picture that comes out


@dataclass
class RenderedScene:
    """
    One picture of a scene with an answer picked out of it.
    """

    image: np.ndarray
    """
    The picture as red, green and blue in that order, shape ``(height, width, 3)`` of
    ``uint8``.
    """

    def holds(self, color: Color) -> bool:
        """
        Whether any pixel of the picture was drawn in the given colour.

        :param color: The colour to look for.
        """
        return bool(np.any(np.all(self.image[:, :, :3] == drawn(color), axis=-1)))

    def write(self, path: Path) -> Path:
        """
        Leave this picture at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.image)
        return path


# %% the render itself


@dataclass
class SceneRender:
    """
    Draws one world with the things an answer names picked out of it.

    The twin is left exactly as it was: only the MuJoCo copy the picture is drawn from is
    recoloured, so the same world answers the next query the way it answered this one.
    """

    world: World
    """
    The twin the picture is drawn of.
    """

    camera: Optional[MujocoCamera] = None
    """
    The camera to draw through, already attached to :attr:`world`.

    When none is given, an overview camera framing the whole scene is hung on the
    world's root for the one render and taken off again afterwards.
    """

    highlight: Color = ANSWER_COLOR
    """
    What the things the answer names are drawn in.
    """

    faded: Color = BACKGROUND_COLOR
    """
    What everything else is drawn in.
    """

    region_appearance: RegionAppearance = RegionAppearance.TRANSPARENT
    """
    How much of the regions the twin holds is drawn, since an answer naming a region has
    to be visible to be picked out.
    """

    label_answers: bool = True
    """
    Whether each thing the answer names is written over in the picture.
    """

    line_width: int = 2
    """
    Thickness of the outline drawn around the answer, in pixels.
    """

    label_height: float = 0.6
    """
    Size a name is written at, as OpenCV's own multiple of its base font.
    """

    def of(self, answers: Sequence[KinematicStructureEntity]) -> RenderedScene:
        """
        Draw the world with the given things picked out of it.

        :param answers: The bodies and regions the answer names, which may be none where
            the query answered nothing.
        :raises NothingToDrawError: If no camera was given and the world holds no
            geometry to frame one around.
        """
        select_offscreen_rendering_backend()
        placed_camera = self._overview_camera() if self.camera is None else None
        camera = self.camera if placed_camera is None else placed_camera
        scene = MujocoSim(
            world=self.world,
            headless=True,
            region_appearance=self.region_appearance,
        )
        scene.simulator.start(simulate_in_thread=False, render_in_thread=False)
        scene.make_room_for_a_picture(
            int(camera.resolution[0]), int(camera.resolution[1])
        )
        try:
            self.pick_out(scene, answers)
            return self._drawn(scene, camera, answers)
        finally:
            scene.simulator.stop()
            if placed_camera is not None:
                placed_camera.body.simulator_additional_properties.remove(placed_camera)

    def pick_out(
        self, scene: MujocoSim, answers: Sequence[KinematicStructureEntity]
    ) -> None:
        """
        Recolour an already-built scene so the answer stands out of it.

        :param scene: The MuJoCo copy of :attr:`world` the picture is drawn from.
        :param answers: The bodies and regions the answer names.
        """
        for entity in self.world.kinematic_structure_entities:
            scene.recolor(entity, self.faded)
        for answer in answers:
            scene.recolor(answer, self.highlight)

    # %% placing the camera

    def _overview_camera(self) -> MujocoCamera:
        """
        A camera hung on the world's root looking diagonally down on the whole scene,
        already attached to it.

        :raises NothingToDrawError: If the world holds no geometry to frame one around.
        """
        bounds = RayTracer(self.world).scene.bounds
        if bounds is None:
            raise NothingToDrawError(world=self.world)
        pose = MujocoCamera.overview_pose(np.asarray(bounds))
        camera = MujocoCamera(
            name=OVERVIEW_CAMERA_NAME,
            body=self.world.root,
            position=pose.to_position().to_np()[:3].tolist(),
            quaternion=MujocoCamera.quaternion_of(pose),
            resolution=[float(PICTURE_WIDTH), float(PICTURE_HEIGHT)],
        )
        self.world.root.simulator_additional_properties.append(camera)
        return camera

    # %% drawing

    def _drawn(
        self,
        scene: MujocoSim,
        camera: MujocoCamera,
        answers: Sequence[KinematicStructureEntity],
    ) -> RenderedScene:
        """
        Take the picture and mark the answer on it.

        :param scene: The recoloured MuJoCo copy of :attr:`world`.
        :param camera: The camera the picture is taken through.
        :param answers: The bodies and regions the answer names.
        """
        viewpoint = SimulatedCamera(world=self.world, camera=camera)
        simulator = scene.simulator
        # Nothing but MuJoCo's own stepping works body poses out from the joint values,
        # and this copy is never stepped, so they are worked out once before anything is
        # drawn. Both renders are held under the one lock so the scene cannot move
        # between the picture and the labelling of it.
        with simulator._model_lock:
            mujoco.mj_forward(simulator._mj_model, simulator._mj_data)
            colors = simulator.capture_rgb(
                camera_name=camera.name,
                height=viewpoint.height,
                width=viewpoint.width,
            ).result
            segmentation = simulator.capture_segmentation(
                camera_name=camera.name,
                height=viewpoint.height,
                width=viewpoint.width,
            ).result

        picture = np.ascontiguousarray(colors)
        self._outline(picture, segmentation, scene, answers)
        if self.label_answers:
            self._label(picture, viewpoint, answers)
        return RenderedScene(image=picture)

    def _outline(
        self,
        picture: np.ndarray,
        segmentation: np.ndarray,
        scene: MujocoSim,
        answers: Sequence[KinematicStructureEntity],
    ) -> None:
        """
        Draw the edge of every pixel the answer covers.

        The recolouring alone leaves an answer standing behind something else with no
        edge to read it by; the segmentation says exactly which pixels are the answer's,
        so the outline follows what is actually visible of it.

        :param picture: The picture to draw on, changed in place.
        :param segmentation: Each pixel's ``(model id, object type)``.
        :param scene: The scene the picture was drawn from.
        :param answers: The bodies and regions the answer names.
        """
        answered_geoms = [geom for answer in answers for geom in scene.geoms_of(answer)]
        if not answered_geoms:
            return
        covered = np.isin(segmentation[:, :, 0], answered_geoms) & (
            segmentation[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM
        )
        edges, _ = cv2.findContours(
            covered.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(picture, edges, -1, drawn(self.highlight), self.line_width)

    def _label(
        self,
        picture: np.ndarray,
        viewpoint: SimulatedCamera,
        answers: Sequence[KinematicStructureEntity],
    ) -> None:
        """
        Write each thing's name where it stands in the picture.

        :param picture: The picture to write on, changed in place.
        :param viewpoint: The camera the picture was taken through, which is what says
            where a place in the world falls in it.
        :param answers: The bodies and regions the answer names.
        """
        if not answers:
            return
        frame = RgbdFrame(
            color=picture,
            depth=np.zeros(picture.shape[:2]),
            intrinsics=viewpoint.intrinsics,
            reference_frame_T_camera=viewpoint.reference_frame_T_camera,
        )
        for answer, pixel in zip(answers, frame.project(self._places_of(answers))):
            cv2.putText(
                picture,
                answer.name.name,
                (round(pixel[0]), round(pixel[1])),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.label_height,
                drawn(LABEL_COLOR),
                self.line_width,
                cv2.LINE_AA,
            )

    def _places_of(self, answers: Sequence[KinematicStructureEntity]) -> np.ndarray:
        """
        Where each thing the answer names stands, in the frame the camera's pose is
        given in.

        :param answers: The bodies and regions the answer names.
        :return: Their positions as ``(n, 3)`` ``(x, y, z)`` in metres.
        """
        places: List[np.ndarray] = [
            self.world.compute_forward_kinematics_np(self.world.root, answer)[:3, 3]
            for answer in answers
        ]
        return np.vstack(places)
