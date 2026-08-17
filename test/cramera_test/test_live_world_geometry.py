"""
Unit tests for writing a running world's own geometry as URDF.

A demo whose world was assembled in code, or parsed out of MJCF/SDF, remembers no URDF
source, so the models the viewer draws have to be written from the world itself. What
matters here is the split: the robot as a branch in its own base frame, because the
bridge places it by publishing that frame, and everything else -- minus what the viewer
already draws as a loose object -- as one environment model.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

import pytest
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    FixedConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.geometry import Box, Mesh, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List, Optional

from cramera.live.model_source import GeneratedModelSource
from cramera.live.world_geometry import GeneratedWorldModels
from cramera.onboard.world_to_urdf import UrdfDocument


@dataclass
class RobotWithARootBody:
    """
    The only thing the writer asks a robot about: which body its branch hangs off.
    """

    root: Body


def _link_names(source: GeneratedModelSource) -> List[str]:
    """
    Link names of a written model, in document order.

    :param source: The written model to read back.
    """
    root = ElementTree.parse(source.path).getroot()
    return [element.attrib["name"] for element in root.findall("link")]


def _joint_names(source: GeneratedModelSource) -> List[str]:
    """
    Joint names of a written model, in document order.

    :param source: The written model to read back.
    """
    root = ElementTree.parse(source.path).getroot()
    return [element.attrib["name"] for element in root.findall("joint")]


def _mesh_references(source: GeneratedModelSource) -> List[str]:
    """
    Every ``filename`` a written model's meshes carry.

    :param source: The written model to read back.
    """
    root = ElementTree.parse(source.path).getroot()
    return [element.attrib["filename"] for element in root.iter("mesh")]


def _model_named(
    sources: List[GeneratedModelSource], name: str
) -> Optional[GeneratedModelSource]:
    """
    The written model with a given file name, or None when it was not written.

    :param sources: The models written by one call.
    :param name: The model name, without its ``.urdf`` suffix.
    """
    return next((source for source in sources if Path(source.path).stem == name), None)


@pytest.fixture()
def mesh_file(tmp_path) -> str:
    """
    A mesh file on disk, so a reference to it resolves.
    """
    path = tmp_path / "meshes" / "cup.obj"
    path.parent.mkdir(parents=True)
    path.write_text("o cup\n")
    return str(path)


@pytest.fixture()
def mounted_arm_world(mesh_file) -> World:
    """
    A one-joint arm bolted to a stand, next to a table and a loose cup.
    """
    world = World()
    root = Body(name=PrefixedName("root"))
    stand = Body(
        name=PrefixedName("stand"),
        visual=ShapeCollection(shapes=[Box(scale=Scale(0.4, 0.4, 0.8))]),
    )
    base = Body(
        name=PrefixedName("base_link"),
        visual=ShapeCollection(shapes=[Box(scale=Scale(0.2, 0.2, 0.2))]),
    )
    upper_arm = Body(
        name=PrefixedName("upper_arm"),
        visual=ShapeCollection(shapes=[Box(scale=Scale(0.1, 0.1, 0.5))]),
    )
    table = Body(
        name=PrefixedName("table"),
        visual=ShapeCollection(shapes=[Box(scale=Scale(1.0, 0.6, 0.7))]),
    )
    cup = Body(
        name=PrefixedName("cup"),
        visual=ShapeCollection(shapes=[Mesh(filename=mesh_file)]),
    )
    shoulder_dof = DegreeOfFreedom(name=PrefixedName("shoulder_dof"))
    with world.modify_world():
        for body in (root, stand, base, upper_arm, table, cup):
            world.add_kinematic_structure_entity(body)
        world.add_degree_of_freedom(shoulder_dof)
        world.add_connection(
            FixedConnection(
                parent=root,
                child=stand,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=1.0, y=2.0, z=0.0
                ),
            )
        )
        world.add_connection(
            FixedConnection(
                parent=stand,
                child=base,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=0.8
                ),
            )
        )
        world.add_connection(
            RevoluteConnection(
                parent=base,
                child=upper_arm,
                axis=Vector3.from_iterable([0, 0, 1]),
                raw_dof=shoulder_dof,
            )
        )
        world.add_connection(FixedConnection(parent=root, child=table))
        world.add_connection(FixedConnection(parent=root, child=cup))
    return world


@pytest.fixture()
def robot(mounted_arm_world) -> RobotWithARootBody:
    """
    The arm of :func:`mounted_arm_world`, as the bridge hands it over.
    """
    return RobotWithARootBody(root=mounted_arm_world.get_body_by_name("base_link"))


# %% the robot's own branch
class TestRobotModel:
    def test_the_branch_is_rooted_in_the_robot_base(self, mounted_arm_world, robot):
        [written] = [
            source
            for source in GeneratedWorldModels().write(
                world=mounted_arm_world, robot=robot, drawn_as_objects=set()
            )
            if source.robot
        ]

        assert _link_names(written) == ["base_link", "upper_arm"]

    def test_the_base_link_carries_no_joint_placing_it(self, mounted_arm_world, robot):
        """
        The bridge publishes the base's pose separately, and the viewer applies it to
        the model's root; a joint here would place the robot twice.
        """
        [written] = [
            source
            for source in GeneratedWorldModels().write(
                world=mounted_arm_world, robot=robot, drawn_as_objects=set()
            )
            if source.robot
        ]

        assert _joint_names(written) == ["base_link_T_upper_arm"]
        assert UrdfDocument.SYNTHESIZED_ROOT_LINK not in _link_names(written)

    def test_the_written_urdf_parses_back_into_a_world(self, mounted_arm_world, robot):
        """
        The viewer only ever loads URDF, so the document has to be a well-formed one:

        a single root, and no joint naming a link it does not contain.
        """
        [written] = [
            source
            for source in GeneratedWorldModels().write(
                world=mounted_arm_world, robot=robot, drawn_as_objects=set()
            )
            if source.robot
        ]

        reparsed = URDFParser.from_file(written.path).parse()

        assert sorted(str(body.name).split("/")[-1] for body in reparsed.bodies) == [
            "base_link",
            "upper_arm",
        ]

    def test_a_world_without_a_robot_yields_only_an_environment(
        self, mounted_arm_world
    ):
        written = GeneratedWorldModels().write(
            world=mounted_arm_world, robot=None, drawn_as_objects=set()
        )

        assert [source.robot for source in written] == [False]


# %% everything the robot's branch does not cover
class TestEnvironmentModel:
    def test_it_holds_every_body_outside_the_robot(self, mounted_arm_world, robot):
        written = GeneratedWorldModels().write(
            world=mounted_arm_world, robot=robot, drawn_as_objects=set()
        )

        assert sorted(_link_names(_model_named(written, "environment"))) == sorted(
            [UrdfDocument.SYNTHESIZED_ROOT_LINK, "root", "stand", "table", "cup"]
        )

    def test_a_body_the_viewer_draws_itself_is_left_out(self, mounted_arm_world, robot):
        """
        A loose object is drawn from its own geometry and moved per frame, so a copy of
        it in the environment would be a second, motionless one.
        """
        written = GeneratedWorldModels().write(
            world=mounted_arm_world, robot=robot, drawn_as_objects={"cup"}
        )

        assert "cup" not in _link_names(_model_named(written, "environment"))

    def test_a_mesh_is_referenced_where_it_already_lies(
        self, mounted_arm_world, robot, mesh_file
    ):
        """
        The world that loaded the mesh is still running, so copying it would only
        duplicate megabytes the bridge can serve from the original path.
        """
        written = GeneratedWorldModels().write(
            world=mounted_arm_world, robot=robot, drawn_as_objects=set()
        )

        assert _mesh_references(_model_named(written, "environment")) == [mesh_file]


# %% rewriting the world as it changes
class TestRewriting:
    def test_a_later_write_does_not_overwrite_the_models_being_served(
        self, mounted_arm_world, robot
    ):
        """
        The viewer may be reading a model over HTTP while the world is written again.
        """
        models = GeneratedWorldModels()

        first = models.write(
            world=mounted_arm_world, robot=robot, drawn_as_objects=set()
        )
        second = models.write(
            world=mounted_arm_world, robot=robot, drawn_as_objects=set()
        )

        assert {source.path for source in first}.isdisjoint(
            source.path for source in second
        )
        assert all(Path(source.path).is_file() for source in first + second)
