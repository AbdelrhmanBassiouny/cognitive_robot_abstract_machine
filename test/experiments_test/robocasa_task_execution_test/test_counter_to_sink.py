import pytest

from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import (
    robocasa_version_assertions_relaxed,
)

with robocasa_version_assertions_relaxed():
    pytest.importorskip("robocasa", reason="robocasa is not installed")
pytest.importorskip("robosuite", reason="robosuite is not installed")

from experiments.robocasa_task_execution.counter_to_sink import (
    CounterToSinkEpisode,
    CounterToSinkOutcome,
)
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.robocasa_dataset.loader import (
    RoboCasaDatasetLoader,
)


@pytest.fixture
def episode() -> CounterToSinkEpisode:
    if not RoboCasaDatasetLoader().directory.exists():
        pytest.skip(
            "RoboCasa assets not downloaded. Run "
            "'python -m robocasa.scripts.download_kitchen_assets' first."
        )
    return CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001)


# %% where the PR2 starts


def test_the_pr2_starts_clear_of_the_kitchen(episode):
    assert not episode.robot.is_in_collision


# %% judging where the object is


def test_an_object_still_on_the_counter_is_not_in_the_sink(episode):
    assert episode.outcome() == CounterToSinkOutcome(
        object_in_sink=False, object_released=True
    )


def test_an_object_put_down_at_the_placement_pose_is_in_the_sink(episode):
    episode.target_object.root.parent_connection.origin = (
        episode.placement_pose().homogeneous_matrix
    )

    assert episode.outcome() == CounterToSinkOutcome(
        object_in_sink=True, object_released=True
    )


# %% performing the task


def test_the_pr2_puts_the_object_into_the_sink(episode):
    assert episode.perform().succeeded
