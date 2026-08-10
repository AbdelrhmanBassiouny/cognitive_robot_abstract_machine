"""
Serialize a :class:`~semantic_digital_twin.world.World` as a self-contained URDF, in the
same format :mod:`cramera.onboard.bundle_urdf` produces, so the web viewer renders it
with the identical pipeline it already knows how to load.

Any adapter that resolves a robot description into a :class:`World` (Gazebo/SDF, MJCF,
...) can bundle it by parsing it and handing the result to :func:`write_world_as_urdf`;
this module only walks the kinematic tree and serializes it, it has no notion of the
source format.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ElementTree

from scipy.spatial.transform import Rotation
from typing_extensions import Dict, List, Type

from cramera.onboard.bundle_urdf import BundleReport, BundledAssets, FIXED_JOINT_TYPE
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection,
    Connection6DoF,
    FixedConnection,
    PrismaticConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.geometry import (
    Box,
    Cylinder,
    Mesh,
    Shape,
    Sphere,
)
from semantic_digital_twin.world_description.world_entity import Body

#: the URDF joint type a connection class becomes; RevoluteConnection additionally maps
#: to "continuous" when its degree of freedom has no position limits, see _joint_type
CONNECTION_JOINT_TYPES: Dict[Type[Connection], str] = {
    FixedConnection: FIXED_JOINT_TYPE,
    RevoluteConnection: "revolute",
    PrismaticConnection: "prismatic",
    Connection6DoF: "floating",
}

#: how many decimal places a bundled numeric attribute keeps
COORDINATE_PRECISION = 6


# %% numeric formatting
def _format_numbers(values) -> str:
    """
    :param values: The numbers to format.
    :return: The numbers as a space separated attribute value.
    """
    return " ".join(str(round(float(value), COORDINATE_PRECISION)) for value in values)


def _set_origin(
    element: ElementTree.Element, pose: HomogeneousTransformationMatrix
) -> None:
    """
    Adds an ``origin`` child expressing a pose as URDF expects: a translation and a
    fixed-axis (extrinsic) roll-pitch-yaw rotation.

    :param element: The element the origin belongs to.
    :param pose: The pose to express, relative to whatever frame the element implies.
    """
    matrix = pose.to_np()
    roll, pitch, yaw = Rotation.from_matrix(matrix[:3, :3]).as_euler("xyz")
    ElementTree.SubElement(
        element,
        "origin",
        {
            "xyz": _format_numbers(matrix[:3, 3]),
            "rpy": _format_numbers([roll, pitch, yaw]),
        },
    )


# %% geometry
def _add_geometry(
    visual_element: ElementTree.Element,
    shape: Shape,
    output_directory: str,
    mesh_subdirectory: str,
    assets: BundledAssets,
) -> None:
    """
    Adds the ``geometry`` a shape describes to a ``visual`` element, copying a mesh's
    file into the bundle first if the shape is one.

    :param visual_element: The ``visual`` element the geometry belongs to.
    :param shape: The shape to describe.
    :param output_directory: Directory the bundle is written to.
    :param mesh_subdirectory: Directory bundled meshes nest under, so meshes from
        different source formats or models cannot collide.
    :param assets: Collects the files copied into the bundle.
    """
    geometry_element = ElementTree.SubElement(visual_element, "geometry")
    if isinstance(shape, Box):
        ElementTree.SubElement(
            geometry_element, "box", {"size": _format_numbers(shape.scale.to_np())}
        )
        return
    if isinstance(shape, Sphere):
        ElementTree.SubElement(
            geometry_element, "sphere", {"radius": str(shape.radius)}
        )
        return
    if isinstance(shape, Cylinder):
        ElementTree.SubElement(
            geometry_element,
            "cylinder",
            {"radius": str(shape.radius), "length": str(shape.height)},
        )
        return
    if not isinstance(shape, Mesh):
        raise TypeError("Unsupported shape type for bundling: %s" % type(shape))

    relative_path = os.path.join(
        mesh_subdirectory,
        os.path.basename(os.path.dirname(shape.filename)),
        os.path.basename(shape.filename),
    )
    bundled = os.path.join(output_directory, "meshes", relative_path)
    if assets.copy(shape.filename, bundled):
        assets.copy_side_assets(shape.filename, bundled)
    ElementTree.SubElement(
        geometry_element,
        "mesh",
        {
            "filename": "meshes/" + relative_path.replace(os.sep, "/"),
            "scale": _format_numbers(shape.scale.to_np()),
        },
    )


def _add_material(visual_element: ElementTree.Element, shape: Shape) -> None:
    """
    Adds the ``material`` a shape's color describes to a ``visual`` element.

    :param visual_element: The ``visual`` element the material belongs to.
    :param shape: The shape whose color is described.
    """
    material_element = ElementTree.SubElement(visual_element, "material", {"name": ""})
    color = shape.color
    ElementTree.SubElement(
        material_element,
        "color",
        {"rgba": _format_numbers([color.R, color.G, color.B, color.A])},
    )


# %% links
def _add_link(
    root_element: ElementTree.Element,
    body: Body,
    output_directory: str,
    mesh_subdirectory: str,
    assets: BundledAssets,
) -> None:
    """
    Adds a ``link`` element for a body, with one ``visual`` per shape it carries.

    :param root_element: The ``robot`` element the link belongs to.
    :param body: The body the link describes.
    :param output_directory: Directory the bundle is written to.
    :param mesh_subdirectory: Directory bundled meshes nest under.
    :param assets: Collects the files copied into the bundle.
    """
    link_element = ElementTree.SubElement(
        root_element, "link", {"name": str(body.name)}
    )
    for shape in body.visual.shapes:
        visual_element = ElementTree.SubElement(link_element, "visual")
        _set_origin(visual_element, shape.origin)
        _add_geometry(
            visual_element, shape, output_directory, mesh_subdirectory, assets
        )
        _add_material(visual_element, shape)


# %% joints
def _joint_type(connection: Connection) -> str:
    """
    :param connection: The connection to classify.
    :return: The URDF joint type the connection becomes.
    :raises TypeError: If the connection is of a type this bundler does not support.
    """
    if (
        isinstance(connection, RevoluteConnection)
        and not connection.dof.has_position_limits()
    ):
        return "continuous"
    for connection_type, joint_type in CONNECTION_JOINT_TYPES.items():
        if isinstance(connection, connection_type):
            return joint_type
    raise TypeError("Unsupported connection type for bundling: %s" % type(connection))


def _add_joint(root_element: ElementTree.Element, connection: Connection) -> str:
    """
    Adds a ``joint`` element for a connection.

    :param root_element: The ``robot`` element the joint belongs to.
    :param connection: The connection the joint describes.
    :return: The name of the added joint.
    """
    joint_type = _joint_type(connection)
    joint_element = ElementTree.SubElement(
        root_element, "joint", {"name": str(connection.name), "type": joint_type}
    )
    ElementTree.SubElement(
        joint_element, "parent", {"link": str(connection.parent.name)}
    )
    ElementTree.SubElement(joint_element, "child", {"link": str(connection.child.name)})
    _set_origin(joint_element, connection.origin)

    if joint_type in ("revolute", "continuous", "prismatic"):
        ElementTree.SubElement(
            joint_element, "axis", {"xyz": _format_numbers(connection.axis.to_np()[:3])}
        )
    if joint_type in ("revolute", "prismatic") and connection.dof.has_position_limits():
        limits = connection.dof.limits
        ElementTree.SubElement(
            joint_element,
            "limit",
            {
                "lower": str(limits.lower.position),
                "upper": str(limits.upper.position),
                "velocity": str(limits.upper.velocity or 0.0),
                "effort": "0.0",
            },
        )
    return str(connection.name)


# %% serialization
def write_world_as_urdf(
    world: World, name: str, output_directory: str, mesh_subdirectory: str
) -> BundleReport:
    """
    Serializes a parsed world, with every mesh it references, as a self-contained URDF.

    :param world: The world to serialize, already resolved to concrete shapes and poses
        by whichever adapter parsed it.
    :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
    :param output_directory: Directory the URDF and its ``meshes/`` tree are written to.
    :param mesh_subdirectory: Directory bundled meshes nest under, so meshes from
        different source formats or models cannot collide.
    :return: A report of what was written, the same one :func:`bundle_urdf` returns.
    """
    os.makedirs(output_directory, exist_ok=True)

    root_element = ElementTree.Element("robot", {"name": name})
    assets = BundledAssets(bundle_root=output_directory)
    joint_names: List[str] = []
    movable_joint_names: List[str] = []

    for body in world.bodies_topologically_sorted:
        _add_link(root_element, body, output_directory, mesh_subdirectory, assets)
        connection = body.parent_connection
        if connection is None:
            continue
        joint_name = _add_joint(root_element, connection)
        joint_names.append(joint_name)
        if not isinstance(connection, FixedConnection):
            movable_joint_names.append(joint_name)

    urdf_out = os.path.join(output_directory, "%s.urdf" % name)
    ElementTree.indent(root_element)
    ElementTree.ElementTree(root_element).write(
        urdf_out, encoding="utf-8", xml_declaration=True
    )
    return BundleReport(
        name=name,
        urdf=urdf_out,
        source=urdf_out,
        links=[str(body.name) for body in world.bodies_topologically_sorted],
        joints=joint_names,
        movable_joints=movable_joint_names,
        meshes_copied=len(assets.copied),
        mesh_suffixes=assets.mesh_suffixes,
        references_rewritten=len(assets.copied),
        missing=assets.missing,
    )
