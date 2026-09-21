from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from time import sleep
from xml.etree import ElementTree

import requests

from semantic_digital_twin.exceptions import MeshDownloadFailed

logger = logging.getLogger(__name__)

MENAGERIE_ASSET_URL = (
    "https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie"
    "/{revision}/franka_emika_panda/assets/{filename}"
)
"""
Template for one Panda mesh in the ``mujoco_menagerie`` repository.
"""

TRANSIENT_STATUS_CODES = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)
"""
Statuses that say the host is momentarily unwilling to serve a mesh it does have,
so the same request stands a chance of succeeding later.
"""


@dataclass
class TransientFailureRetries:
    """
    How persistently a mesh download is repeated while the host reports a
    transient failure.
    """

    attempts: int = 5
    """
    How many times one mesh is requested before the download is given up on.
    """

    first_delay_seconds: float = 1.0
    """
    Seconds to wait after the first failure, doubling with each further one.
    """

    def delay_after_attempt(self, attempt: int) -> float:
        """
        Seconds to wait before repeating a request, backing off the longer the
        host has been failing.

        :param attempt: Zero-based index of the attempt that just failed.
        :return: The delay to observe.
        """
        return self.first_delay_seconds * 2**attempt


@dataclass
class PandaMeshAssets:
    """
    The Panda meshes a scene needs, downloaded from ``mujoco_menagerie`` on
    first use.

    The meshes are several tens of megabytes, so they are fetched on demand
    rather than committed alongside the scene that references them.
    """

    scene: Path
    """
    The MJCF scene whose mesh references decide what has to be downloaded.
    """

    revision: str = "main"
    """
    Git revision of ``mujoco_menagerie`` to download from.

    Pin this to a commit to keep a scene reproducible against upstream changes.
    """

    timeout: float = 60.0
    """
    Seconds to allow for a single mesh download.
    """

    session: requests.Session = field(default_factory=requests.Session)
    """
    Connection pool reused across the individual mesh downloads.
    """

    retries: TransientFailureRetries = field(default_factory=TransientFailureRetries)
    """
    How a host that is momentarily refusing to serve a mesh is waited out.
    """

    @property
    def directory(self) -> Path:
        """
        Where the meshes belong, taken from the scene's own ``meshdir`` so the
        two cannot disagree about it.
        """
        compiler = ElementTree.parse(self.scene).getroot().find("compiler")
        mesh_directory = compiler.get("meshdir")
        return self.scene.parent / mesh_directory

    def required_filenames(self) -> list[str]:
        """
        The mesh files the scene refers to, in the order it declares them.
        """
        root = ElementTree.parse(self.scene).getroot()
        filenames = [mesh.get("file") for mesh in root.iter("mesh")]
        return sorted({filename for filename in filenames if filename})

    def download_if_missing(self) -> Path:
        """
        Download whichever of the scene's meshes are not present yet.

        :return: The directory holding the meshes.
        """
        directory = self.directory
        directory.mkdir(parents=True, exist_ok=True)

        missing = [
            filename
            for filename in self.required_filenames()
            if not (directory / filename).exists()
        ]
        if not missing:
            return directory

        logger.info(
            "Downloading %d Panda meshes from mujoco_menagerie@%s into %s",
            len(missing),
            self.revision,
            directory,
        )
        for filename in missing:
            self.download(filename, directory)

        return directory

    def download(self, filename: str, directory: Path) -> None:
        """
        Download one mesh into ``directory``.

        :param filename: Name of the mesh as the scene refers to it.
        :param directory: Where the mesh is written.
        :raises MeshDownloadFailed: If the host does not serve the mesh.
        """
        url = MENAGERIE_ASSET_URL.format(revision=self.revision, filename=filename)
        response = self.request_while_failing_transiently(url)
        if response.status_code != HTTPStatus.OK:
            raise MeshDownloadFailed(url=url, status_code=response.status_code)

        partial = self.partial_path(filename, directory)
        with partial.open("wb") as mesh_file:
            for chunk in response.iter_content(chunk_size=8192):
                mesh_file.write(chunk)
        partial.rename(directory / filename)

    @staticmethod
    def partial_path(filename: str, directory: Path) -> Path:
        """
        Where a mesh is written while it is still arriving.

        A mesh is written under a temporary name first, so an interrupted download
        cannot leave a truncated file that later runs take for complete. The name
        carries the process that is writing it, because a test run split across
        processes has several of them downloading the same mesh into the same
        directory at once: sharing one temporary name let whichever finished first
        rename the file out from under the others.

        :param filename: Name of the mesh being downloaded.
        :param directory: Where the mesh is written.
        """
        return directory / f"{filename}.{os.getpid()}.partial"

    def request_while_failing_transiently(self, url: str) -> requests.Response:
        """
        Request ``url`` until the host answers with something other than a
        transient failure, or until the attempts are used up.

        :param url: Address of the mesh to request.
        :return: The last answer received, whether or not it carries the mesh.
        """
        attempts_made = 0
        while True:
            response = self.session.get(url, stream=True, timeout=self.timeout)
            if response.status_code not in TRANSIENT_STATUS_CODES:
                return response
            # The answer carries no mesh, so the connection goes back to the pool
            # unread; the status stays readable on the closed answer.
            response.close()
            attempts_made += 1
            if attempts_made == self.retries.attempts:
                return response
            delay = self.retries.delay_after_attempt(attempts_made - 1)
            logger.warning(
                "mujoco_menagerie answered HTTP %d for %s, retrying in %.1f s "
                "(attempt %d of %d)",
                response.status_code,
                url,
                delay,
                attempts_made + 1,
                self.retries.attempts,
            )
            sleep(delay)
