from copy import deepcopy

import numpy as np
import pytest

from semantic_digital_twin.robots.description_corrections import (
    ReplaceConnection,
    ReplaceSection,
    SectionAttachment,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Vector3
from semantic_digital_twin.specifications.connections import (
    FixedConnectionSpecification,
    PrismaticConnectionSpecification,
)
from semantic_digital_twin.specifications.kinematic_structure_entities import (
    BodySpecification,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    FixedConnection,
    PrismaticConnection,
)
from semantic_digital_twin.world_description.geometry import Scale

LINK = Scale(0.1, 0.1, 0.1)
"""
The extents of every link of the test chains.
"""


@pytest.fixture
def empty_world() -> World:
    return World.create_with_root_body()


def spawn_lift(world: World) -> None:
    """
    Spawn a chain under the root of `world`: a ``lift`` that slides ``carriage`` up and
    down, a ``mount`` fixed on the carriage, and a ``hand`` fixed on the mount.
    """
    BodySpecification.box(
        "carriage",
        LINK,
        parent_T_self=HomogeneousTransformationMatrix.from_xyz_rpy(z=0.5),
        connection_specification=PrismaticConnectionSpecification(
            name="lift", axis=Vector3.Z()
        ),
        child_specifications=[
            BodySpecification.box(
                "mount",
                LINK,
                parent_T_self=HomogeneousTransformationMatrix.from_xyz_rpy(z=0.2),
                child_specifications=[
                    BodySpecification.box(
                        "hand",
                        LINK,
                        parent_T_self=HomogeneousTransformationMatrix.from_xyz_rpy(
                            x=0.3
                        ),
                    )
                ],
            )
        ],
    ).spawn(world)


def root_T(world: World, name: str) -> np.ndarray:
    """
    :return: The pose of the body named `name` relative to the root of `world`.
    """
    return world.compute_forward_kinematics_np(world.root, world.get_body_by_name(name))


# %% replacing a connection


def test_a_replaced_connection_keeps_its_bodies_where_they_are(empty_world: World):
    spawn_lift(empty_world)
    empty_world.get_connection_by_name("lift").position = 0.1
    hand_before = root_T(empty_world, "hand")

    with empty_world.modify_world():
        ReplaceConnection(
            connection_name="lift", replacement=FixedConnectionSpecification()
        ).apply(empty_world, empty_world.root)

    lift = empty_world.get_connection_by_name("lift")
    assert isinstance(lift, FixedConnection)
    assert lift.child is empty_world.get_body_by_name("carriage")
    np.testing.assert_allclose(root_T(empty_world, "hand"), hand_before)


def test_a_replaced_connection_stays_replaced_in_a_copy(empty_world: World):
    spawn_lift(empty_world)

    with empty_world.modify_world():
        ReplaceConnection(
            connection_name="lift", replacement=FixedConnectionSpecification()
        ).apply(empty_world, empty_world.root)

    assert isinstance(
        deepcopy(empty_world).get_connection_by_name("lift"), FixedConnection
    )


# %% replacing a section


def test_a_replaced_section_leaves_the_attached_bodies_where_they_were(
    empty_world: World,
):
    """
    The carriage and its mount are replaced by a single fixed body, and the hand that
    hung from the mount hangs from that body afterwards.
    """
    spawn_lift(empty_world)
    carriage_before = root_T(empty_world, "carriage")
    hand_before = root_T(empty_world, "hand")

    with empty_world.modify_world():
        ReplaceSection(
            section_root_name="carriage",
            replacement=BodySpecification.box("column", LINK),
            attachments=[SectionAttachment(body_name="hand", new_parent_name="column")],
        ).apply(empty_world, empty_world.root)

    names = {body.name.name for body in empty_world.bodies}
    assert "carriage" not in names and "mount" not in names
    assert not any(
        isinstance(connection, PrismaticConnection)
        for connection in empty_world.connections
    )
    column = empty_world.get_body_by_name("column")
    hand = empty_world.get_body_by_name("hand")
    assert column.parent_connection.parent is empty_world.root
    assert hand.parent_connection.parent is column
    np.testing.assert_allclose(root_T(empty_world, "column"), carriage_before)
    np.testing.assert_allclose(root_T(empty_world, "hand"), hand_before)
