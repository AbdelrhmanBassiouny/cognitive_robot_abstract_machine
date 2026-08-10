"""
Bundle a Gazebo/SDF or MJCF source into the same self-contained URDF format
:mod:`cramera.onboard.bundle_urdf` produces, so the web viewer renders it with the
identical pipeline it already knows how to load.

Where :func:`cramera.onboard.bundle_urdf.bundle_urdf` rewrites the mesh references of an
existing URDF file, these bundlers build a URDF from scratch: the adapter has already
resolved every shape and pose into a :class:`~semantic_digital_twin.world.World`, so
bundling only has to hand that world to
:func:`cramera.onboard.world_to_urdf.write_world_as_urdf`.
"""

from __future__ import annotations

import dataclasses
import os

from semantic_digital_twin.adapters.gazebo import GazeboParser
from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.world import World
from typing_extensions import Callable, Dict, Optional

from cramera.onboard.bundle_urdf import BundleReport, resolve_uri
from cramera.onboard.world_to_urdf import write_world_as_urdf

#: directory a bundled Gazebo mesh's own source directory nests under, so meshes from
#: differently named models cannot collide
GAZEBO_MESH_DIRECTORY = "gazebo"

#: the same, for MJCF sources
MJCF_MESH_DIRECTORY = "mjcf"


def _bundle_parsed_world(
    source: str,
    name: str,
    output_directory: str,
    hints: Optional[Dict[str, str]],
    parse: Callable[[str], World],
    mesh_subdirectory: str,
    format_name: str,
) -> BundleReport:
    """
    Resolve a source file, parse it into a world and serialize that world as a URDF.

    :param source: Path or URI of the file to bundle.
    :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
    :param output_directory: Directory the URDF and its ``meshes/`` tree are written to.
    :param hints: Resolutions recorded while a demo ran.
    :param parse: Turns the resolved source path into a world.
    :param mesh_subdirectory: Directory bundled meshes nest under.
    :param format_name: The source format, used in the not-found message.
    :raises FileNotFoundError: If the source itself cannot be found.
    """
    source_path = resolve_uri(source, hints=hints) or source
    if not os.path.isfile(source_path):
        raise FileNotFoundError(
            "%s source not found: %s (from %s)" % (format_name, source_path, source)
        )
    report = write_world_as_urdf(
        parse(source_path), name, output_directory, mesh_subdirectory
    )
    return dataclasses.replace(report, source=source_path)


def bundle_gazebo_world(
    source: str,
    name: str,
    output_directory: str,
    hints: Optional[Dict[str, str]] = None,
) -> BundleReport:
    """
    Bundle one Gazebo/SDF world or model, with every mesh it references.

    :param source: Path or URI of the world/model file to bundle.
    :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
    :param output_directory: Directory the URDF and its ``meshes/`` tree are written to.
    :param hints: Resolutions recorded while a demo ran.
    """
    return _bundle_parsed_world(
        source,
        name,
        output_directory,
        hints,
        lambda path: GazeboParser.from_file(path).parse(),
        GAZEBO_MESH_DIRECTORY,
        "Gazebo",
    )


def bundle_mjcf(
    source: str,
    name: str,
    output_directory: str,
    hints: Optional[Dict[str, str]] = None,
) -> BundleReport:
    """
    Bundle one MJCF robot or scene, with every mesh it references.

    :param source: Path or URI of the MJCF file to bundle.
    :param name: Output model name, used for ``<output_directory>/<name>.urdf``.
    :param output_directory: Directory the URDF and its ``meshes/`` tree are written to.
    :param hints: Resolutions recorded while a demo ran.
    """
    return _bundle_parsed_world(
        source,
        name,
        output_directory,
        hints,
        lambda path: MJCFParser(path).parse(),
        MJCF_MESH_DIRECTORY,
        "MJCF",
    )
