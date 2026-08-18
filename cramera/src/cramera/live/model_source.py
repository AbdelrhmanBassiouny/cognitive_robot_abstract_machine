"""
Serves a live world's own robot/environment URDF geometry to the viewer.

Two kinds of model are served the same way. A *parsed* one is a URDF/xacro file the
demo built its world from, which the source hook remembered; a *generated* one is
written from the running world itself, for a demo whose world came from another format
(MJCF, say) or was built in code and so has no URDF of its own.

Unlike :mod:`cramera.onboard.bundle_urdf`, nothing is copied to disk: mesh references
are resolved and streamed on request, the same way loose-object meshes are already
served via ``/objects`` + ``/mesh?key=``. Models and their mesh references are
addressed by position, never by a client-supplied path, so a request can never read a
file the live world did not itself load.
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
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
    One URDF model of the live world, as the viewer is told about it.
    """

    source: str
    """
    Absolute path of the URDF file.
    """

    prefix: str
    """
    The model's world-instance prefix, empty if the world is unprefixed.
    """

    robot: bool
    """
    Whether this model describes the live robot.
    """


@dataclass(frozen=True)
class ModelSource(ABC):
    """
    One URDF file the bridge can serve, and how it knows what that file describes.
    """

    path: str
    """
    Absolute path of the URDF file.
    """

    @abstractmethod
    def identify(
        self, links: List[str], world_body_names: List[str], base_body: Optional[str]
    ) -> LiveModel:
        """
        The model this source serves.

        :param links: The source's own link names, in document order.
        :param world_body_names: Every body name in the composed world.
        :param base_body: The robot's base link name, unprefixed, or None when no robot
            is bound.
        """


@dataclass(frozen=True)
class ParsedModelSource(ModelSource):
    """
    A URDF/xacro file the demo parsed its world from, whose identity has to be read
    back out of the composed world's own body names.
    """

    def identify(
        self, links: List[str], world_body_names: List[str], base_body: Optional[str]
    ) -> LiveModel:
        """
        The model, with its prefix and robot flag inferred from its links.

        :param links: The source's own link names, in document order.
        :param world_body_names: Every body name in the composed world.
        :param base_body: The robot's base link name, unprefixed, or None when no robot
            is bound.
        """
        prefix, is_robot = model_identity(
            links=links,
            world_body_names=world_body_names,
            base_body=base_body,
            probe_link_count=PREFIX_PROBE_LINKS,
        )
        return LiveModel(source=self.path, prefix=prefix, robot=is_robot)


@dataclass(frozen=True)
class GeneratedModelSource(ModelSource):
    """
    A URDF written from the running world, which therefore already knows what it
    describes: its links are world body names, so it carries no prefix of its own.
    """

    robot: bool
    """
    Whether this model describes the live robot.
    """

    def identify(
        self, links: List[str], world_body_names: List[str], base_body: Optional[str]
    ) -> LiveModel:
        """
        The model, as it was written.

        :param links: The source's own link names, in document order.
        :param world_body_names: Every body name in the composed world.
        :param base_body: The robot's base link name, unprefixed, or None when no robot
            is bound.
        """
        return LiveModel(source=self.path, prefix="", robot=self.robot)


@dataclass
class LiveModelCatalog:
    """
    The URDF models of a running demo's world, servable without a bundle.
    """

    sources: List[ModelSource] = field(default_factory=list)
    """
    The servable models, in the order the viewer is told about them.
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
            if not any(source.path == file_path for source in self.sources):
                self.sources.append(ParsedModelSource(path=file_path))

    @property
    def describes_a_parsed_world(self) -> bool:
        """
        Whether any source the world was parsed from is tracked.
        """
        with self._lock:
            return any(isinstance(source, ParsedModelSource) for source in self.sources)

    def replace_generated(self, generated: List[GeneratedModelSource]) -> None:
        """
        Serve these models of the running world in place of the ones written before.

        :param generated: The models written from the world as it stands now.
        """
        with self._lock:
            self.sources = [
                source
                for source in self.sources
                if not isinstance(source, GeneratedModelSource)
            ] + list(generated)

    def models(
        self, world_body_names: List[str], base_body: Optional[str]
    ) -> List[LiveModel]:
        """
        Every tracked model, flagged with its prefix and whether it is the robot.

        :param world_body_names: Every body name in the composed world.
        :param base_body: The robot's base link name, unprefixed, or None when no
            robot is bound.
        """
        with self._lock:
            sources = list(self.sources)
        return [
            source.identify(self._links(source.path), world_body_names, base_body)
            for source in sources
        ]

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
        Path of the tracked source at a position, or None if the index is out of range.

        :param index: Position of the source in :attr:`sources`.
        """
        with self._lock:
            if not 0 <= index < len(self.sources):
                return None
            return self.sources[index].path

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
