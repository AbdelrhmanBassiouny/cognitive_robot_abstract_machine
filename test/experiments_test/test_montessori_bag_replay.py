"""
Running the pipeline over a whole recording, watching it as it goes.

This is the one test that reads a rosbag rather than a capture, so it needs the
recordings themselves -- gigabytes the repository does not carry. It is therefore
skipped wherever they are not on disk, which is every run but a developer's own with the
recordings beside the checkout, and it opens windows, so it is skipped without a screen
as well. The captures are what continuous integration measures detection on; this is
what a person watches before trusting them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from experiments.montessori.perception.recorded_setup import perception_pipeline
from experiments.montessori.perception.recordings import (
    REFERENCE_FRAME,
    RecordedCamera,
)
from experiments.montessori.perception.viewer import CameraFrameViewer
from experiments.montessori.perception.watch_bag import BagReplay

# %% what this test needs to be there

ROSBAG_DIRECTORY = Path(__file__).parents[2] / "rosbags"
"""
Where the recordings lie in a checkout that has them.
"""

DEMO_RECORDING = "tracy_pickup_demo_20260828_173800"
"""
The recording of the pick-up demo, which carries the transform tree as well as the
camera.
"""

LOOKS_TO_PLAY = 5
"""
How many frames of the recording this test runs the pipeline on.

Enough to show the windows updating rather than a single still, and few enough that a
developer watching it does not have to sit through the whole demo.
"""

SCREEN_VARIABLES = ("DISPLAY", "WAYLAND_DISPLAY")
"""
The environment variables that say a window can be opened.
"""

demo_recording = ROSBAG_DIRECTORY / DEMO_RECORDING

pytestmark = [
    pytest.mark.skipif(
        not demo_recording.is_dir(),
        reason=f"{demo_recording} is not in this checkout; recordings are not committed",
    ),
    pytest.mark.skipif(
        not any(os.environ.get(variable) for variable in SCREEN_VARIABLES),
        reason="no screen to open the viewer's windows on",
    ),
]


# %% replaying it


def test_the_demo_recording_plays_through_the_pipeline_into_the_windows() -> None:
    """
    Every frame of the recording is detected on and drawn, and the board -- which stands
    on the table for the whole demo -- is found in each of them.
    """
    viewer = CameraFrameViewer()
    replay = BagReplay(
        camera=RecordedCamera(bag=demo_recording, reference_frame=REFERENCE_FRAME),
        pipeline=perception_pipeline(),
        viewer=viewer,
    )
    try:
        replay.play(limit=LOOKS_TO_PLAY)
    finally:
        viewer.close()
    assert len(replay.scenes) == LOOKS_TO_PLAY
    assert all(scene.board is not None for scene in replay.scenes)
