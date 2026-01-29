import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
from uuid import UUID

import giskardpy_bullet_bindings as pb
import numpy as np
import trimesh
from platformdirs import user_cache_dir
from trimesh import Trimesh

from giskardpy.utils.utils import create_path
from ..utils import suppress_stdout_stderr
from ..world_description.geometry import (
    Shape,
    Box,
    Sphere,
    Cylinder,
    Scale,
    TriangleMesh,
    FileMesh,
    Mesh,
)
from ..world_description.world_entity import Body

logger = logging.getLogger(__name__)

CollisionObject = pb.CollisionObject


PKG_NAME = __package__.split(".", 1)[0]

CACHE_DIR = Path(user_cache_dir(PKG_NAME)) / "convex_decompositions"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_key(mesh_bytes: bytes, params: dict, algo_version: str) -> str:
    h = hashlib.sha256()
    h.update(mesh_bytes)
    h.update(json.dumps(params, sort_keys=True).encode())
    h.update(algo_version.encode())
    return h.hexdigest()


def trimesh_quantized_hash(mesh, decimals: int = 6, digest_size: int = 16) -> str:
    """
    Hash tolerant to tiny float differences by rounding vertices.
    Still order-sensitive (vertex/face order changes -> different hash).
    """
    h = hashlib.blake2b(digest_size=digest_size)

    v = np.asarray(mesh.vertices, dtype=np.float64)
    f = np.ascontiguousarray(mesh.faces)

    vq = np.round(v, decimals=decimals)
    vq = np.ascontiguousarray(vq)

    h.update(str(vq.shape).encode("utf-8"))
    h.update(str(vq.dtype).encode("utf-8"))
    h.update(vq.tobytes())

    h.update(str(f.shape).encode("utf-8"))
    h.update(str(f.dtype).encode("utf-8"))
    h.update(f.tobytes())

    return h.hexdigest()


def create_cube_shape(extents: Tuple[float, float, float]) -> pb.BoxShape:
    out = (
        pb.BoxShape(pb.Vector3(*[extents[x] * 0.5 for x in range(3)]))
        if type(extents) is not pb.Vector3
        else pb.BoxShape(extents)
    )
    out.margin = 0.001
    return out


def create_cylinder_shape(diameter: float, height: float) -> pb.CylinderShape:
    out = pb.CylinderShapeZ(pb.Vector3(diameter / 2, diameter / 2, height))
    out.margin = 0.001
    return out


def create_sphere_shape(diameter: float) -> pb.SphereShape:
    out = pb.SphereShape(0.5 * diameter)
    out.margin = 0.001
    return out


def create_shape_from_geometry(geometry: Shape) -> pb.CollisionShape:
    if isinstance(geometry, Box):
        shape = create_cube_shape(
            (geometry.scale.x, geometry.scale.y, geometry.scale.z)
        )
    elif isinstance(geometry, Sphere):
        shape = create_sphere_shape(geometry.radius * 2)
    elif isinstance(geometry, Cylinder):
        shape = create_cylinder_shape(diameter=geometry.width, height=geometry.height)
    elif isinstance(geometry, TriangleMesh):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".obj")
        with open(f.name, "w") as fd:
            fd.write(trimesh.exchange.obj.export_obj(geometry.mesh))
        shape = load_convex_mesh_shape(
            mesh=geometry,
            single_shape=False,
            scale=geometry.scale,
        )
    elif isinstance(geometry, FileMesh):
        shape = load_convex_mesh_shape(
            mesh=geometry,
            single_shape=False,
            scale=geometry.scale,
        )
    else:
        raise NotImplementedError()
    return shape


def create_shape_from_link(body: Body) -> pb.CollisionObject:
    shapes = []
    for collision_id, geometry in enumerate(body.collision):
        shape = create_shape_from_geometry(geometry=geometry)
        link_T_geometry = pb.Transform.from_np(geometry.origin.to_np())
        shapes.append((link_T_geometry, shape))
    compouned_shape = create_compound_shape(shapes_poses=shapes)
    return create_object(body.id, compouned_shape, pb.Transform.identity())


def create_compound_shape(
    shapes_poses: List[Tuple[pb.Transform, pb.CollisionShape]] = None,
) -> pb.CompoundShape:
    out = pb.CompoundShape()
    for t, s in shapes_poses:
        out.add_child(t, s)
    return out


def cache_file(file_name: str):
    # key = cache_key(mesh_bytes, params, algo_version)
    return f"{CACHE_DIR} / {file_name}"


def load_convex_mesh_shape(
    mesh: Mesh, single_shape: bool, scale: Scale
) -> pb.ConvexShape:
    if not mesh.mesh.is_convex:
        obj_pkg_filename = convert_to_decomposed_obj_and_save_in_tmp(mesh=mesh.mesh)
    else:
        obj_pkg_filename = mesh.file_name
    return pb.load_convex_shape(
        obj_pkg_filename,
        single_shape=single_shape,
        scaling=pb.Vector3(scale.x, scale.y, scale.z),
    )


def clear_cache():
    for file in CACHE_DIR.iterdir():
        file.unlink()


def convert_to_decomposed_obj_and_save_in_tmp(
    mesh: Trimesh, log_path="/tmp/giskardpy/vhacd.log"
) -> str:
    file_hash = trimesh_quantized_hash(mesh)
    obj_file_name = str(CACHE_DIR / f"{file_hash}.obj")
    if not os.path.exists(obj_file_name):
        obj_str = trimesh.exchange.obj.export_obj(mesh)
        create_path(obj_file_name)
        with open(obj_file_name, "w") as f:
            f.write(obj_str)
        if not mesh.is_convex:
            with suppress_stdout_stderr():
                pb.vhacd(obj_file_name, obj_file_name, log_path)
            logging.info(f'Saved convex decomposition to "{obj_file_name}".')
        else:
            logging.info(f'Saved obj to "{obj_file_name}".')
    return obj_file_name


def create_object(
    name: UUID,
    shape: pb.CollisionShape,
    transform: Optional[pb.Transform] = None,
) -> pb.CollisionObject:
    if transform is None:
        transform = pb.Transform.identity()
    out = pb.CollisionObject(name)
    out.collision_shape = shape
    out.collision_flags = pb.CollisionObject.KinematicObject
    out.transform = transform
    return out
