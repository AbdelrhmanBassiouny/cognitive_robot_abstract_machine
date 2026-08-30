"""
Cutting the workspace down to the table by eye.

The sliders themselves are OpenCV's, so what is tested here is what the tuner draws for
a given set of edges and what it hands back when the windows are quit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.tune_workspace import (
    WorkspaceControls,
    WorkspaceTuner,
)
from experiments.montessori.perception.viewer import (
    CameraFrameViewer,
    PerceptionWindow,
    QuitKey,
)

from .dataset import montessori_scene_fixtures
from .dataset.montessori_scene_renderer import MontessoriSceneRenderer, PlacedPiece
from .test_montessori_viewer import KeyPressingDisplay

pytest_plugins = [montessori_scene_fixtures.__name__]

# %% edges that stay where they are put


@dataclass
class SetControls(WorkspaceControls):
    """
    Stands in for the sliders, holding the edges wherever a test put them.
    """

    region: WorkspaceRegion
    """
    Where the edges stand.
    """

    def read(self) -> WorkspaceRegion:
        return self.region


@pytest.fixture
def frame(
    renderer: MontessoriSceneRenderer, placed_pieces: list[PlacedPiece]
) -> RgbdFrame:
    return renderer.render(placed_pieces)


def tuner_for(
    frame: RgbdFrame,
    pipeline: MontessoriPerceptionPipeline,
    region: WorkspaceRegion,
    display: KeyPressingDisplay,
) -> WorkspaceTuner:
    """
    A tuner whose edges are already set where a test wants them.

    :param frame: The look at the scene to draw.
    :param pipeline: The pipeline whose workspace is being cut down.
    :param region: Where the edges stand.
    :param display: The screen the windows are drawn on.
    """
    return WorkspaceTuner(
        frame=frame,
        pipeline=pipeline,
        controls=SetControls(region=region),
        viewer=CameraFrameViewer(display=display),
    )


# %% what a set of edges draws


def test_the_workspace_is_shown_in_all_three_windows_as_it_is_cut_down(
    frame: RgbdFrame, pipeline: MontessoriPerceptionPipeline
):
    brought_in = replace(
        pipeline.table.region, maximum_x=pipeline.table.region.maximum_x - 0.1
    )
    display = KeyPressingDisplay()
    tuner = tuner_for(frame, pipeline, brought_in, display)

    tuner.show(brought_in)
    tuner.viewer.refresh()

    assert set(display.drawn) == set(PerceptionWindow)


def test_a_region_the_edges_have_collapsed_is_not_drawn(
    frame: RgbdFrame, pipeline: MontessoriPerceptionPipeline
):
    collapsed = replace(
        pipeline.table.region, maximum_x=pipeline.table.region.minimum_x
    )
    display = KeyPressingDisplay()
    tuner = tuner_for(frame, pipeline, collapsed, display)

    tuner.show(collapsed)
    tuner.viewer.refresh()

    assert display.drawn == {}


def test_tuning_ends_at_the_region_the_edges_were_left_at(
    frame: RgbdFrame, pipeline: MontessoriPerceptionPipeline
):
    region = replace(
        pipeline.table.region, maximum_y=pipeline.table.region.maximum_y - 0.05
    )
    display = KeyPressingDisplay(key_presses=[None, QuitKey.Q])

    left_at = tuner_for(frame, pipeline, region, display).tune()

    assert left_at == region
