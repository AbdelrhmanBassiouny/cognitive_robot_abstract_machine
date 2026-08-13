"""
Which bodies of a world count as loose objects, and what key each is published under.

The recorder and the live bridge both have to answer this the same way, or a live
attach overlays its poses onto keys the recording filed its objects under differently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Any, List

from cramera.loose_objects import LooseObjects


# %% a world to ask about
@dataclass
class RobotOwningBodies:
    """
    A robot annotation, of which only the bodies it owns are read here.
    """

    bodies: List[Any] = field(default_factory=list)


@pytest.fixture()
def world_with_bodies():
    """
    A world whose root carries one free-floating body, one fixed body named after a mesh
    file, and one fixed body that names no mesh at all.
    """
    world = World()
    root = Body(name=PrefixedName("root", prefix="world"))
    floating = Body(name=PrefixedName("cube", prefix="montessori"))
    mesh_named = Body(name=PrefixedName("milk.stl", prefix="montessori"))
    furniture = Body(name=PrefixedName("table", prefix="montessori"))
    with world.modify_world():
        world.add_body(root)
        degrees_of_freedom = [
            DegreeOfFreedom(name=PrefixedName(component))
            for component in ("x", "y", "z", "qx", "qy", "qz", "qw")
        ]
        for degree_of_freedom in degrees_of_freedom:
            world.add_degree_of_freedom(degree_of_freedom)
        x, y, z, qx, qy, qz, qw = degrees_of_freedom
        world.add_connection(
            Connection6DoF(
                parent=root, child=floating, x=x, y=y, z=z, qx=qx, qy=qy, qz=qz, qw=qw
            )
        )
        world.add_connection(FixedConnection(parent=root, child=mesh_named))
        world.add_connection(FixedConnection(parent=root, child=furniture))
    return world


class TestObjectKey:
    def test_the_key_drops_the_world_prefix(self):
        body = Body(name=PrefixedName("cube", prefix="montessori"))
        assert LooseObjects.key_of(body) == "cube"


class TestWhatCountsAsALooseObject:
    def test_a_free_floating_body_is_loose_however_it_is_named(self, world_with_bodies):
        """
        A world built in code names its objects after themselves, not after a mesh file;
        letting a body move freely is how that world says the body is loose.
        """
        loose = LooseObjects(world=world_with_bodies)
        assert sorted(loose.keyed_bodies()) == ["cube", "milk.stl"]

    def test_a_fixed_body_naming_no_mesh_is_furniture(self, world_with_bodies):
        assert "table" not in LooseObjects(world=world_with_bodies).keyed_bodies()

    def test_a_fixed_body_named_after_a_mesh_file_is_still_loose(
        self, world_with_bodies
    ):
        """
        The convention a mesh-loading demo relies on: the body carries its mesh's own
        file name, whether or not the world lets it move.
        """
        loose = LooseObjects(world=world_with_bodies)
        assert "milk.stl" in loose.keyed_bodies()

    def test_the_robots_own_free_floating_base_is_not_an_object(self, world_with_bodies):
        """
        A mobile base is free-floating too, and belongs to the robot rather than to the
        objects on the table.
        """
        robot = RobotOwningBodies(
            bodies=[body for body in world_with_bodies.bodies if body.name.name == "cube"]
        )
        loose = LooseObjects(world=world_with_bodies, robot=robot)
        assert "cube" not in loose.keyed_bodies()

    def test_each_key_maps_to_the_body_it_names(self, world_with_bodies):
        bodies = LooseObjects(world=world_with_bodies).keyed_bodies()
        assert str(bodies["cube"].name) == "montessori/cube"
