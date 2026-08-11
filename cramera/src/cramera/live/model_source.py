"""
Serves a live world's own robot/environment URDF geometry to the viewer.

Unlike :mod:`cramera.onboard.bundle_urdf`, nothing is copied to disk: mesh references
are resolved and streamed on request, the same way loose-object meshes are already
served via ``/objects`` + ``/mesh?key=``. Models and their mesh references are
addressed by position, never by a client-supplied path, so a request can never read a
file the live world did not itself load.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import Dict, List, Optional

from semantic_digital_twin.adapters.urdf import URDFParser

from cramera.mesh_format import MeshFormat
from cramera.onboard.bundle_urdf import BundleReport, MeshReference
from cramera.robot_parts import model_identity

PREFIX_PROBE_LINKS = 12
"""
How many of a model's links are probed to find its prefix in the composed world.
"""


@dataclass(frozen=True)
class LiveModel:
    """
    One URDF/xacro model the live world was built from.
    """

    source: str
    """
    Absolute path of the URDF/xacro source file.
    """

    prefix: str
    """
    The model's world-instance prefix, empty if the world is unprefixed.
    """

    robot: bool
    """
    Whether this model's links include the live robot's base link.
    """


@dataclass
class LiveModelCatalog:
    """
    URDF/xacro sources a running demo loaded, servable without a bundle.
    """

    sources: List[str] = field(default_factory=list)
    """
    Absolute source paths, in load order.
    """

    _text_cache: Dict[str, str] = field(default_factory=dict)
    """
    Source path to its already-read/expanded text, so a slow xacro expansion (the PR2
    description takes seconds) runs once per source rather than once per request.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards :attr:`sources` and :attr:`_text_cache`.

    Deliberately a lock of its own, never :class:`~cramera.live.bridge.Bridge`'s —
    the tick hook holds that one while publishing every snapshot, and a cache-miss
    xacro expansion can take seconds; sharing a lock would stall the running demo for
    that long every time a browser attaches live.
    """

    def remember(self, file_path: str) -> None:
        """
        Remember a URDF/xacro source the world was built from, at most once.

        :param file_path: Absolute path of the source file.
        """
        with self._lock:
            if file_path not in self.sources:
                self.sources.append(file_path)

    def models(
        self, world_body_names: List[str], base_body: Optional[str]
    ) -> List[LiveModel]:
        """
        Every tracked source, flagged with its prefix and whether it is the robot.

        :param world_body_names: Every body name in the composed world.
        :param base_body: The robot's base link name, unprefixed, or None when no
            robot is bound.
        """
        with self._lock:
            sources = list(self.sources)
        result = []
        for source in sources:
            links = self._links(source)
            prefix, is_robot = model_identity(
                links=links,
                world_body_names=world_body_names,
                base_body=base_body,
                probe_link_count=PREFIX_PROBE_LINKS,
            )
            result.append(LiveModel(source=source, prefix=prefix, robot=is_robot))
        return result

    def urdf_text(self, index: int) -> Optional[str]:
        """
        A tracked source's URDF text, with mesh references rewritten to servable URLs.

        :param index: Position of the source in :attr:`sources`.
        """
        source = self._source_at(index)
        if source is None:
            return None
        text = self._read(source)
        if text is None:
            return None
        for reference_index, reference in enumerate(self._references(text)):
            mesh_format = MeshFormat.of_path(reference)
            text = text.replace(
                '"%s"' % reference,
                '"%s"' % model_mesh_url(index, reference_index, mesh_format),
            )
        return text

    def mesh_path(self, index: int, reference_index: int) -> Optional[str]:
        """
        Absolute path a model's mesh reference resolves to.

        :param index: Position of the source in :attr:`sources`.
        :param reference_index: Position of the reference within that source's own
            sorted, deduplicated mesh references, as :meth:`urdf_text` numbered them.
        """
        source = self._source_at(index)
        if source is None:
            return None
        text = self._read(source)
        if text is None:
            return None
        references = self._references(text)
        if not 0 <= reference_index < len(references):
            return None
        return MeshReference(references[reference_index]).resolve(
            base_directory=os.path.dirname(source)
        )

    def _source_at(self, index: int) -> Optional[str]:
        """
        The tracked source at a position, or None if the index is out of range.

        :param index: Position of the source in :attr:`sources`.
        """
        with self._lock:
            return self.sources[index] if 0 <= index < len(self.sources) else None

    def _links(self, source: str) -> List[str]:
        """
        A source's link names, in document order.

        :param source: Absolute path of a tracked source file.
        """
        text = self._read(source)
        return BundleReport.LINK_PATTERN.findall(text) if text is not None else []

    @staticmethod
    def _references(text: str) -> List[str]:
        """
        A URDF's mesh references, sorted and deduplicated.

        Every ``filename="..."`` attribute matches the same pattern regardless of the
        tag it belongs to, so a plugin (``.so``) or other non-geometry reference is
        excluded here rather than mistaken for a mesh.

        :param text: The URDF text to read references out of.
        """
        references = set(BundleReport.MESH_REFERENCE_PATTERN.findall(text))
        return sorted(
            reference
            for reference in references
            if MeshFormat.of_path(reference) is not None
        )

    def _read(self, source: str) -> Optional[str]:
        """
        A source's URDF text, cached after the first read.

        :param source: Absolute path of a tracked source file.
        """
        with self._lock:
            if source not in self._text_cache:
                text = self._parse(source)
                if text is None:
                    return None
                self._text_cache[source] = text
            return self._text_cache[source]

    @staticmethod
    def _parse(source: str) -> Optional[str]:
        """
        A source's URDF text, expanding it first if it is a xacro file.

        :param source: Absolute path of a tracked source file.
        """
        if source.endswith(".xacro"):
            return URDFParser.from_xacro(source).urdf
        if not os.path.isfile(source):
            return None
        return Path(source).read_text(encoding="utf-8", errors="replace")


def model_mesh_url(index: int, reference_index: int, mesh_format: MeshFormat) -> str:
    """
    The servable URL :meth:`LiveModelCatalog.urdf_text` rewrites a reference to.

    Two constraints on the shape of this URL, both learned from a live bug:

    - Relative, not root-relative: the vendored URDFLoader resolves a non-
      ``package://`` reference by string-concatenating it onto the URDF's own
      directory URL (which already ends in ``/``), not through standard browser URL
      resolution — a leading ``/`` here produces a double-slash URL that 404s.
    - The real extension has to be the URL's own trailing characters: the same
      loader dispatches to STL/COLLADA/OBJ by regex-matching the end of the URL
      string, not by any query parameter, so the extension is a path segment here
      rather than e.g. ``?ref=0``.

    :param index: Position of the source in a catalog's tracked sources.
    :param reference_index: Position of the reference within that source's own
        sorted, deduplicated mesh references.
    :param mesh_format: The reference's own mesh format, kept as the URL's suffix.
    """
    return "model_mesh/%d/%d%s" % (index, reference_index, mesh_format.value)
