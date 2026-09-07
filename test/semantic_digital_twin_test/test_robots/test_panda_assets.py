from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typing_extensions import Iterator

from semantic_digital_twin.exceptions import MeshDownloadFailed
from semantic_digital_twin.robots.panda_assets import (
    PandaMeshAssets,
    TransientFailureRetries,
)

SCENE_SOURCE = Path(__file__).resolve().parents[1] / "dataset" / "two_mesh_arm.xml"
"""
An MJCF declaring two meshes in an ``assets`` mesh directory, copied next to a temporary
mesh directory by :func:`scene`.
"""

# %% http stand-ins


@dataclass
class QueuedHttpResponse:
    """
    One answer a :class:`QueuedHttpResponses` request is served with.
    """

    status_code: int
    """
    HTTP status of this answer.
    """

    body: bytes
    """
    Payload the answer streams back.
    """

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        """
        Stream the body as a single chunk, whatever chunk size is asked for.
        """
        yield self.body

    def close(self) -> None:
        """
        Release the answer, which a stand-in holds no resources for.
        """


@dataclass
class QueuedHttpResponses:
    """
    Stand-in for an HTTP session that answers every request for a mesh with the next
    status queued for that mesh, repeating the last one once the queue runs down, and
    serves the mesh's own name as the body.
    """

    statuses_by_filename: dict[str, list[int]]
    """
    Statuses to answer with, per mesh file name, oldest first.
    """

    requested_filenames: list[str] = field(default_factory=list)
    """
    Every mesh requested so far, in request order.
    """

    def get(self, url: str, stream: bool, timeout: float) -> QueuedHttpResponse:
        """
        Answer a request for one mesh and record that it was made.
        """
        filename = url.rsplit("/", 1)[-1]
        self.requested_filenames.append(filename)
        statuses = self.statuses_by_filename[filename]
        status = statuses.pop(0) if len(statuses) > 1 else statuses[0]
        return QueuedHttpResponse(status_code=status, body=filename.encode())


# %% fixtures


@pytest.fixture
def scene(tmp_path: Path) -> Path:
    """
    The two-mesh scene, placed so its meshes download into a temporary directory.
    """
    scene_path = tmp_path / SCENE_SOURCE.name
    shutil.copyfile(SCENE_SOURCE, scene_path)
    return scene_path


def assets_with(scene: Path, responses: QueuedHttpResponses) -> PandaMeshAssets:
    """
    Mesh assets for ``scene`` served by ``responses``, retrying without waiting.
    """
    return PandaMeshAssets(
        scene=scene,
        session=responses,
        retries=TransientFailureRetries(attempts=3, first_delay_seconds=0.0),
    )


# %% downloading


def test_transient_server_failure_is_retried_until_the_mesh_arrives(scene: Path):
    responses = QueuedHttpResponses(
        statuses_by_filename={"link0.obj": [503, 200], "link1.obj": [200]}
    )

    directory = assets_with(scene, responses).download_if_missing()

    assert responses.requested_filenames == ["link0.obj", "link0.obj", "link1.obj"]
    assert (directory / "link0.obj").read_bytes() == b"link0.obj"
    assert (directory / "link1.obj").read_bytes() == b"link1.obj"


def test_transient_server_failure_that_never_clears_reports_the_status(scene: Path):
    responses = QueuedHttpResponses(
        statuses_by_filename={"link0.obj": [503], "link1.obj": [200]}
    )
    assets = assets_with(scene, responses)

    with pytest.raises(MeshDownloadFailed) as failure:
        assets.download_if_missing()

    assert failure.value.status_code == 503
    assert failure.value.url.endswith("/link0.obj")
    assert responses.requested_filenames == ["link0.obj"] * 3


def test_a_mesh_the_server_does_not_have_is_not_retried(scene: Path):
    responses = QueuedHttpResponses(
        statuses_by_filename={"link0.obj": [404], "link1.obj": [200]}
    )
    assets = assets_with(scene, responses)

    with pytest.raises(MeshDownloadFailed) as failure:
        assets.download_if_missing()

    assert failure.value.status_code == 404
    assert responses.requested_filenames == ["link0.obj"]


def test_a_mesh_already_downloaded_is_not_requested_again(scene: Path):
    responses = QueuedHttpResponses(
        statuses_by_filename={"link0.obj": [200], "link1.obj": [200]}
    )
    assets = assets_with(scene, responses)
    assets.download_if_missing()

    assets.download_if_missing()

    assert responses.requested_filenames == ["link0.obj", "link1.obj"]


# %% two processes downloading one mesh

OTHER_PROCESS_ID = 424242
"""
Process a mesh is half-downloaded by while the process under test downloads it too.
"""


def test_two_processes_do_not_write_one_mesh_to_the_same_temporary_file(
    scene: Path, monkeypatch: pytest.MonkeyPatch
):
    assets = assets_with(scene, QueuedHttpResponses(statuses_by_filename={}))

    monkeypatch.setattr(os, "getpid", lambda: OTHER_PROCESS_ID)
    elsewhere = assets.partial_path("link0.obj", assets.directory)
    monkeypatch.undo()
    here = assets.partial_path("link0.obj", assets.directory)

    assert here != elsewhere


def test_a_download_leaves_another_processes_half_written_mesh_alone(
    scene: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    A test run splits across processes, and two of them reaching ``parse_panda`` at once
    download the same meshes into the same directory.

    Sharing one temporary name let whichever renamed first take the file out from under
    the other, which then failed on a temporary file that was no longer there.
    """
    responses = QueuedHttpResponses(statuses_by_filename={"link0.obj": [200]})
    assets = assets_with(scene, responses)
    directory = assets.directory
    directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(os, "getpid", lambda: OTHER_PROCESS_ID)
    elsewhere = assets.partial_path("link0.obj", directory)
    elsewhere.write_bytes(b"half a mesh from another process")
    monkeypatch.undo()

    assets.download("link0.obj", directory)

    assert (directory / "link0.obj").read_bytes() == b"link0.obj"
    assert elsewhere.read_bytes() == b"half a mesh from another process"


# %% retry policy


def test_the_delay_between_attempts_doubles():
    retries = TransientFailureRetries(attempts=4, first_delay_seconds=0.5)

    delays = [retries.delay_after_attempt(attempt) for attempt in range(4)]

    assert delays == [0.5, 1.0, 2.0, 4.0]
