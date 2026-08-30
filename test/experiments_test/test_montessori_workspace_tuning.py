"""
Cutting the workspace down to the table by eye.

The sliders themselves are OpenCV's, so what is tested here is what the tuner draws for
a given set of edges, what it hands back when the windows are quit, and that a run over
the captures afterwards searches the workspace it was left at.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    WIDEST_WORKSPACE,
    perception_pipeline,
    searched_workspace,
)
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


# %% keeping the region the edges were left at


def test_a_region_is_read_back_from_file_as_it_was_written(tmp_path: Path):
    region = replace(WIDEST_WORKSPACE, maximum_x=WIDEST_WORKSPACE.maximum_x - 0.2)
    path = tmp_path / "workspace.json"

    region.save(path)

    assert WorkspaceRegion.load(path) == region


def test_the_setup_searches_the_workspace_that_was_tuned_for_it(tmp_path: Path):
    region = replace(WIDEST_WORKSPACE, maximum_y=WIDEST_WORKSPACE.maximum_y - 0.3)
    path = tmp_path / "workspace.json"
    region.save(path)

    assert searched_workspace(path) == region


def test_the_whole_workspace_is_searched_where_none_has_been_tuned(tmp_path: Path):
    assert searched_workspace(tmp_path / "never_written.json") == WIDEST_WORKSPACE


def test_the_pipeline_the_setup_builds_searches_the_tuned_workspace():
    pipeline = perception_pipeline()

    assert pipeline.table.region == searched_workspace()
    assert pipeline.lid.region == searched_workspace()


def test_the_workspace_tuned_for_this_setup_lies_inside_the_whole_one():
    tuned = searched_workspace()

    assert tuned.minimum_x >= WIDEST_WORKSPACE.minimum_x
    assert tuned.maximum_x <= WIDEST_WORKSPACE.maximum_x
    assert tuned.minimum_y >= WIDEST_WORKSPACE.minimum_y
    assert tuned.maximum_y <= WIDEST_WORKSPACE.maximum_y
