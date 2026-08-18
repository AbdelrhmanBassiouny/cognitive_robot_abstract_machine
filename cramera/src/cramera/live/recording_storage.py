"""
Managing an already-finalized live-recording bundle on disk.

Deliberately free of :mod:`cramera.live.bridge`/``semantic_digital_twin`` — once a
recording has been written to disk (by :func:`cramera.live.recording_bundle.
finalize_recording`, whether from an explicit ``/recording/stop`` or its exit-time
safety net), discarding or saving it is a pure filesystem operation that works whether
or not the demo process that produced it is still running. This is what lets
:mod:`cramera.server` (the always-on viewer process, on a different port than the live
bridge) offer the same actions as a fallback once that process is gone.
"""

from __future__ import annotations

import json
import shutil
from enum import StrEnum
from pathlib import Path

from cramera import paths
from cramera.generated_json import write_json_atomically
from cramera.live.frame_range import FrameRange, InvalidFrameRange
from cramera.live.recording_segments import clip_segment_payloads
from cramera.onboard.scene_index import validate_scene_name, write_scene_index


class NoSavedRecording(Exception):
    """
    Raised by :func:`save_recording_bundle` when no finalized ``__recording__`` bundle
    exists on disk to save.
    """


class SceneNameTaken(Exception):
    """
    Raised by :func:`save_recording_bundle` when the requested name already names a
    scene in a shared or local scenes root.
    """


def has_saveable_recording() -> bool:
    """
    Whether a finalized ``__recording__`` bundle currently exists on disk.
    """
    return (
        paths.local_scenes_directory() / paths.RECORDING_SCENE_NAME / "scene.json"
    ).is_file()


def discard_recording_bundle() -> None:
    """
    Delete the unsaved ``__recording__`` bundle from disk, if one exists.
    """
    shutil.rmtree(
        paths.local_scenes_directory() / paths.RECORDING_SCENE_NAME, ignore_errors=True
    )


class SharedScenesUnavailable(Exception):
    """
    Raised when a scene is to be shared but no shared scenes root is configured, so
    sharing it would quietly be an ordinary local save.
    """


class SceneDestination(StrEnum):
    """
    Which scenes root a saved recording is written to.
    """

    LOCAL = "local"
    """
    The user's own data directory: the recording stays on this machine.
    """

    SHARED = "shared"
    """
    The scenes root others read too — a ``cram-scenes`` checkout, when one is set up.
    """

    def directory(self) -> Path:
        """
        The scenes root this destination writes into.
        """
        if self is SceneDestination.LOCAL:
            return paths.local_scenes_directory()
        return paths.scenes_directory()


def save_recording_bundle(
    name: str, destination: SceneDestination = SceneDestination.LOCAL
) -> str:
    """
    Promote the finalized ``__recording__`` bundle to a permanent, saved scene.

    Sharing only moves files: the scene appears in the shared checkout's working tree,
    and committing it there stays a deliberate act.

    :param name: Name to save the recording under.
    :param destination: Which scenes root to save it into.
    :raises cramera.onboard.scene_index.InvalidSceneName: If ``name`` is unsafe or
        reserved.
    :raises NoSavedRecording: If no finalized ``__recording__`` bundle exists on disk.
    :raises SceneNameTaken: If ``name`` already names a scene in any scenes root.
    :raises SharedScenesUnavailable: If sharing is asked for without a shared root
        distinct from the local one.
    """
    validate_scene_name(name)
    root = destination.directory()
    if (
        destination is SceneDestination.SHARED
        and root == paths.local_scenes_directory()
    ):
        raise SharedScenesUnavailable(
            "no shared scenes root: initialize the cramera/scenes submodule or set "
            "CRAMERA_SCENES"
        )
    source = paths.local_scenes_directory() / paths.RECORDING_SCENE_NAME
    if not (source / "scene.json").is_file():
        raise NoSavedRecording("no finalized recording to save")
    if any((existing / name).is_dir() for existing in paths.scene_roots()):
        raise SceneNameTaken("a scene named '%s' already exists" % name)
    scene_directory = root / name
    shutil.move(str(source), str(scene_directory))
    scene_path = scene_directory / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    scene["name"] = name
    write_json_atomically(scene_path, scene, indent=1)
    write_scene_index(root / "index.json", name)
    return name


# %% cutting a finalized bundle down before it is saved


def trim_recording_bundle(frame_range: FrameRange) -> None:
    """
    Cut the unsaved ``__recording__`` bundle down to the frames a range keeps.

    Everything a replay reads is derived from frame indices, so the trim rewrites all
    three together: the trajectory keeps only the selected ticks, the timeline segments
    are rebased on them (see
    :func:`cramera.live.recording_segments.clip_segment_payloads`), and each object
    spawns where the kept stretch starts rather than where the cut-away run did.

    :param frame_range: The stretch of the run to keep.
    :raises NoSavedRecording: If no finalized bundle exists on disk.
    :raises cramera.live.recording.InvalidFrameRange: If the range reaches past the
        bundled run.
    """
    bundle = paths.local_scenes_directory() / paths.RECORDING_SCENE_NAME
    scene_path, trajectory_path = bundle / "scene.json", bundle / "trajectory.json"
    if not scene_path.is_file() or not trajectory_path.is_file():
        raise NoSavedRecording("no finalized recording to trim")
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    if frame_range.last >= len(trajectory["frames"]):
        raise InvalidFrameRange(
            "frame %d is past the recording's %d frames"
            % (frame_range.last, len(trajectory["frames"]))
        )
    kept = slice(frame_range.first, frame_range.last + 1)
    for track in ("frames", "base", "objects"):
        trajectory[track] = trajectory[track][kept]
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    scene["segments"] = clip_segment_payloads(scene["segments"], frame_range)
    for entry in scene["objects"]:
        spawn = trajectory["objects"][0].get(entry["key"])
        if spawn is not None:
            entry["spawn"] = spawn
    write_json_atomically(trajectory_path, trajectory)
    write_json_atomically(scene_path, scene, indent=1)
