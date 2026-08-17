"""
Serializing a :class:`~semantic_digital_twin.world.World` as a self-contained URDF.

Any adapter that resolves a robot description into a :class:`World` (Gazebo/SDF, MJCF,
...) can bundle it by parsing it and handing the result to
:meth:`UrdfDocument.of_world`; this module walks the kinematic tree and serializes it,
it has no notion of the source format.

Where the meshes a document references end up is :class:`MeshFileReferences`' decision:
a scene bundle copies them in so it stands on its own, while a document served out of
the running process points at the files that process already loaded.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ElementTree
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from coraplex.datastructures.enums import JointType
from scipy.spatial.transform import Rotation
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
from typing_extensions import ClassVar, Dict, Iterable, List, Type

from cramera.onboard.bundle_urdf import BundledAssets, BundleReport


class DisconnectedBranch(Exception):
    """
    Raised when a branch to serialize does not hang off a single root body.
    """

    def __init__(self, name: str, root_names: List[str]) -> None:
        """
        Report which bodies of the branch turned out to be roots.

        :param name: Name of the model being serialized.
        :param root_names: Names of the bodies found without a parent in the branch.
        """
        super().__init__(
            "%s is not one branch: %d bodies have no parent in it (%s)"
            % (name, len(root_names), ", ".join(root_names) or "none")
        )


# %% where a serialized mesh reference points
@dataclass
class MeshFileReferences(ABC):
    """
    How a document names the mesh files its geometry references.
    """

    assets: BundledAssets
    """
    Records what was written, and which references resolved to no file.
    """

    @abstractmethod
    def reference_for(self, mesh_file_path: str) -> str:
        """
        The ``filename`` a mesh's geometry element is written with.

        :param mesh_file_path: Path the world's mesh shape was loaded from.
        """


@dataclass
class BundledMeshFiles(MeshFileReferences):
    """
    Copies every referenced mesh into the bundle and names the copy, so the bundle
    stands on its own once the world that produced it is gone.
    """

    output_directory: str
    """
    Directory the bundle's ``meshes/`` tree goes into.
    """

    mesh_subdirectory: str
    """
    Directory bundled meshes nest under, so meshes from different source formats or
    models cannot collide.
    """

    @classmethod
    def into(cls, output_directory: str, mesh_subdirectory: str) -> BundledMeshFiles:
        """
        Copy into a bundle, writing nothing outside it.

        :param output_directory: Directory the bundle's ``meshes/`` tree goes into.
        :param mesh_subdirectory: Directory bundled meshes nest under.
        """
        return cls(
            assets=BundledAssets(bundle_root=output_directory),
            output_directory=output_directory,
            mesh_subdirectory=mesh_subdirectory,
        )

    def reference_for(self, mesh_file_path: str) -> str:
        """
        Copy the mesh, with the side assets it references, and name the copy relative
        to the URDF.

        :param mesh_file_path: Path the world's mesh shape was loaded from.
        """
        relative_path = os.path.join(
            self.mesh_subdirectory,
            os.path.basename(os.path.dirname(mesh_file_path)),
            os.path.basename(mesh_file_path),
        )
        bundled = os.path.join(self.output_directory, "meshes", relative_path)
        if self.assets.copy(mesh_file_path, bundled):
            self.assets.copy_side_assets(mesh_file_path, bundled)
        return "meshes/" + relative_path.replace(os.sep, "/")


@dataclass
class OriginalMeshFiles(MeshFileReferences):
    """
    Names every mesh where it already lies, copying nothing.

    For a document served straight out of the process that built the world: the files
    it points at are the ones that process loaded, so copying tens of megabytes of them
    would buy nothing.
    """

    @classmethod
    def in_place(cls) -> OriginalMeshFiles:
        """
        Reference the world's own mesh files.
        """
        return cls(assets=BundledAssets())

    def reference_for(self, mesh_file_path: str) -> str:
        """
        The mesh's own absolute path.

        :param mesh_file_path: Path the world's mesh shape was loaded from.
        """
        if not os.path.isfile(mesh_file_path):
            self.assets.missing.append(mesh_file_path)
        return mesh_file_path


@dataclass
class UrdfDocument:
    """
    A URDF document being assembled from a world's kinematic tree.
    """

    CONNECTION_JOINT_TYPES: ClassVar[Dict[Type[Connection], JointType]] = {
        FixedConnection: JointType.FIXED,
        RevoluteConnection: JointType.REVOLUTE,
        PrismaticConnection: JointType.PRISMATIC,
        Connection6DoF: JointType.FLOATING,
    }
    """
    The joint type a connection class becomes.

    A :class:`RevoluteConnection` additionally becomes :attr:`JointType.CONTINUOUS` when its degree of freedom has no position
    limits.
    """

    SYNTHESIZED_ROOT_LINK: ClassVar[str] = "world_root"
    """
    Name of the link :meth:`of_bodies` roots its document in, which belongs to no body
    of the world it serializes part of.
    """

    COORDINATE_PRECISION: ClassVar[int] = 6
    """
    Decimal places a bundled numeric attribute keeps.
    """

    AXIS_JOINT_TYPES: ClassVar[frozenset] = frozenset(
        {JointType.REVOLUTE, JointType.CONTINUOUS, JointType.PRISMATIC}
    )
    """
    Joint types that carry an ``axis`` element.
    """

    LIMITED_JOINT_TYPES: ClassVar[frozenset] = frozenset(
        {JointType.REVOLUTE, JointType.PRISMATIC}
    )
    """
    Joint types that carry a ``limit`` element when their degree of freedom is limited.
    """

    output_directory: str
    """
    Directory the URDF is written to.
    """

    mesh_files: MeshFileReferences
    """
    Where the ``filename`` of a serialized mesh points.
    """

    root_element: ElementTree.Element
    """
    The document's ``robot`` element, which every link and joint is added to.
    """

    joint_names: List[str] = field(default_factory=list)
    """
    Names of the joints added so far, in document order.
    """

    movable_joint_names: List[str] = field(default_factory=list)
    """
    Names of the added joints that are not fixed.
    """

    @classmethod
    def of_world(
        cls,
        world: World,
        name: str,
        output_directory: str,
        mesh_files: MeshFileReferences,
    ) -> BundleReport:
        """
        Serialize a parsed world, with every mesh it references, as a URDF.

        :param world: The world to serialize, already resolved to concrete shapes and
            poses by whichever adapter parsed it.
        :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
        :param output_directory: Directory the URDF goes into.
        :param mesh_files: Where the ``filename`` of a serialized mesh points.
        """
        document = cls._empty(name, output_directory, mesh_files)
        bodies = world.bodies_topologically_sorted
        document.add_bodies(bodies)
        return document.write(name, bodies)

    @classmethod
    def of_branch(
        cls,
        bodies: List[Body],
        name: str,
        output_directory: str,
        mesh_files: MeshFileReferences,
    ) -> BundleReport:
        """
        Serialize one kinematic branch of a world as a URDF in the branch root's own
        frame.

        The branch root becomes the document's root link at identity, so whatever
        drives the model from outside -- a live bridge publishing the robot's base
        pose, say -- places the whole branch by placing that link.

        :param bodies: The branch's bodies, in the order they should appear.
        :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
        :param output_directory: Directory the URDF goes into.
        :param mesh_files: Where the ``filename`` of a serialized mesh points.
        :raises DisconnectedBranch: If the bodies do not hang off exactly one root.
        """
        document = cls._empty(name, output_directory, mesh_files)
        roots = document.add_bodies(bodies)
        if len(roots) != 1:
            raise DisconnectedBranch(name, [str(body.name) for body in roots])
        return document.write(name, bodies)

    @classmethod
    def of_bodies(
        cls,
        bodies: List[Body],
        name: str,
        output_directory: str,
        mesh_files: MeshFileReferences,
    ) -> BundleReport:
        """
        Serialize part of a world -- the bodies no parsed source describes -- as a URDF.

        Connections *within* the subset are kept, so a drawer stays prismatic and keeps
        following its recorded positions. A body whose parent lies outside the subset
        has no joint to inherit and is fixed to :attr:`SYNTHESIZED_ROOT_LINK` at the
        pose it holds in the world, which is also what leaves the document with a single
        root.

        :param bodies: The bodies to serialize, in the order they should appear.
        :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
        :param output_directory: Directory the URDF goes into.
        :param mesh_files: Where the ``filename`` of a serialized mesh points.
        """
        document = cls._empty(name, output_directory, mesh_files)
        ElementTree.SubElement(
            document.root_element, "link", {"name": cls.SYNTHESIZED_ROOT_LINK}
        )
        for body in document.add_bodies(bodies):
            document.graft_onto_root(body)
        return document.write(name, bodies)

    @classmethod
    def _empty(
        cls, name: str, output_directory: str, mesh_files: MeshFileReferences
    ) -> UrdfDocument:
        """
        An empty document ready to be filled, with its output directory in place.

        :param name: The model name the ``robot`` element carries.
        :param output_directory: Directory the URDF goes into.
        :param mesh_files: Where the ``filename`` of a serialized mesh points.
        """
        os.makedirs(output_directory, exist_ok=True)
        return cls(
            output_directory=output_directory,
            mesh_files=mesh_files,
            root_element=ElementTree.Element("robot", {"name": name}),
        )

    def add_bodies(self, bodies: List[Body]) -> List[Body]:
        """
        Add a link per body, and a joint per connection whose parent is also present.

        :param bodies: The bodies to serialize, in the order they should appear.
        :return: The bodies whose parent lies outside the given ones, which the caller
            decides how to root.
        """
        serialized = {str(body.name) for body in bodies}
        roots: List[Body] = []
        for body in bodies:
            self.add_link(body)
            connection = body.parent_connection
            if connection is not None and str(connection.parent.name) in serialized:
                self.add_joint(connection)
            else:
                roots.append(body)
        return roots

    def graft_onto_root(self, body: Body) -> None:
        """
        Fix a body to :attr:`SYNTHESIZED_ROOT_LINK` at the pose it holds in its world.

        :param body: The body to attach, whose own parent this document does not
            contain.
        """
        joint_element = ElementTree.SubElement(
            self.root_element,
            "joint",
            {
                "name": "%s_to_%s" % (self.SYNTHESIZED_ROOT_LINK, str(body.name)),
                "type": JointType.FIXED.name.lower(),
            },
        )
        ElementTree.SubElement(
            joint_element, "parent", {"link": self.SYNTHESIZED_ROOT_LINK}
        )
        ElementTree.SubElement(joint_element, "child", {"link": str(body.name)})
        self._set_origin(joint_element, body.global_pose)
        self.joint_names.append(joint_element.attrib["name"])

    def write(self, name: str, bodies: Iterable[Body]) -> BundleReport:
        """
        Write the assembled document to disk and report what it contains.

        :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
        :param bodies: The bodies serialized into the document.
        """
        urdf_out = os.path.join(self.output_directory, "%s.urdf" % name)
        ElementTree.indent(self.root_element)
        ElementTree.ElementTree(self.root_element).write(
            urdf_out, encoding="utf-8", xml_declaration=True
        )
        return BundleReport(
            name=name,
            urdf=urdf_out,
            source=urdf_out,
            links=[str(body.name) for body in bodies],
            joints=self.joint_names,
            movable_joints=self.movable_joint_names,
            meshes_copied=len(self.mesh_files.assets.copied),
            mesh_suffixes=self.mesh_files.assets.mesh_suffixes,
            references_rewritten=len(self.mesh_files.assets.copied),
            missing=self.mesh_files.assets.missing,
        )

    # %% links
    def add_link(self, body: Body) -> None:
        """
        Add a ``link`` element for a body, with one ``visual`` per shape it carries.

        :param body: The body the link describes.
        """
        link_element = ElementTree.SubElement(
            self.root_element, "link", {"name": str(body.name)}
        )
        for shape in body.visual.shapes:
            visual_element = ElementTree.SubElement(link_element, "visual")
            self._set_origin(visual_element, shape.origin)
            self._add_geometry(visual_element, shape)
            self._add_material(visual_element, shape)

    def _add_geometry(self, visual_element: ElementTree.Element, shape: Shape) -> None:
        """
        Add the ``geometry`` a shape describes, naming a mesh's file through
        :attr:`mesh_files` if the shape is one.

        :param visual_element: The ``visual`` element the geometry belongs to.
        :param shape: The shape to describe.
        :raises TypeError: If the shape is of a type this bundler does not support.
        """
        geometry_element = ElementTree.SubElement(visual_element, "geometry")
        if isinstance(shape, Box):
            ElementTree.SubElement(
                geometry_element,
                "box",
                {"size": self._format_numbers(shape.scale.to_np())},
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

        ElementTree.SubElement(
            geometry_element,
            "mesh",
            {
                "filename": self.mesh_files.reference_for(shape.filename),
                "scale": self._format_numbers(shape.scale.to_np()),
            },
        )

    def _add_material(self, visual_element: ElementTree.Element, shape: Shape) -> None:
        """
        Add the ``material`` a shape's colour describes.

        :param visual_element: The ``visual`` element the material belongs to.
        :param shape: The shape whose colour is described.
        """
        material_element = ElementTree.SubElement(
            visual_element, "material", {"name": ""}
        )
        color = shape.color
        ElementTree.SubElement(
            material_element,
            "color",
            {"rgba": self._format_numbers([color.R, color.G, color.B, color.A])},
        )

    # %% joints
    def add_joint(self, connection: Connection) -> None:
        """
        Add a ``joint`` element for a connection.

        :param connection: The connection the joint describes.
        """
        joint_type = self._joint_type(connection)
        joint_element = ElementTree.SubElement(
            self.root_element,
            "joint",
            {"name": str(connection.name), "type": joint_type.name.lower()},
        )
        ElementTree.SubElement(
            joint_element, "parent", {"link": str(connection.parent.name)}
        )
        ElementTree.SubElement(
            joint_element, "child", {"link": str(connection.child.name)}
        )
        self._set_origin(joint_element, self._joint_origin(connection, joint_type))

        if joint_type in self.AXIS_JOINT_TYPES:
            ElementTree.SubElement(
                joint_element,
                "axis",
                {"xyz": self._format_numbers(connection.axis.to_np()[:3])},
            )
        if (
            joint_type in self.LIMITED_JOINT_TYPES
            and connection.dof.has_position_limits()
        ):
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
        self.joint_names.append(str(connection.name))
        if joint_type is not JointType.FIXED:
            self.movable_joint_names.append(str(connection.name))

    @classmethod
    def _joint_origin(
        cls, connection: Connection, joint_type: JointType
    ) -> HomogeneousTransformationMatrix:
        """
        The parent-to-child pose a joint's ``origin`` states.

        URDF reads a joint as its origin followed by the joint's own displacement, so a
        joint whose displacement is supplied from outside -- the axis-driven types,
        which a recording or a live bridge drives -- must be written at its zero. Its
        :attr:`Connection.origin` is the pose at the *current* value, which would bake
        that value in and have the supplied one applied on top of it. Every other joint
        type carries no value of its own, so its full origin is the only thing placing
        its child.

        :param connection: The connection the joint describes.
        :param joint_type: The joint type the connection becomes.
        """
        if joint_type in cls.AXIS_JOINT_TYPES:
            return connection.parent_T_connection_expression
        return connection.origin

    @classmethod
    def _joint_type(cls, connection: Connection) -> JointType:
        """
        The joint type a connection becomes.

        :param connection: The connection to classify.
        :raises TypeError: If the connection is of a type this bundler does not support.
        """
        if (
            isinstance(connection, RevoluteConnection)
            and not connection.dof.has_position_limits()
        ):
            return JointType.CONTINUOUS
        for connection_type, joint_type in cls.CONNECTION_JOINT_TYPES.items():
            if isinstance(connection, connection_type):
                return joint_type
        raise TypeError(
            "Unsupported connection type for bundling: %s" % type(connection)
        )

    # %% numeric formatting
    @classmethod
    def _set_origin(
        cls, element: ElementTree.Element, pose: HomogeneousTransformationMatrix
    ) -> None:
        """
        Add an ``origin`` child expressing a pose as URDF does: a translation plus a
        fixed-axis (extrinsic) roll-pitch-yaw rotation.

        :param element: The element the origin belongs to.
        :param pose: The pose to express, relative to the frame the element implies.
        """
        matrix = pose.to_np()
        roll, pitch, yaw = Rotation.from_matrix(matrix[:3, :3]).as_euler("xyz")
        ElementTree.SubElement(
            element,
            "origin",
            {
                "xyz": cls._format_numbers(matrix[:3, 3]),
                "rpy": cls._format_numbers([roll, pitch, yaw]),
            },
        )

    @classmethod
    def _format_numbers(cls, values: Iterable[float]) -> str:
        """
        Numbers as the space-separated attribute value a URDF carries.

        :param values: The numbers to format.
        """
        return " ".join(
            str(round(float(value), cls.COORDINATE_PRECISION)) for value in values
        )
