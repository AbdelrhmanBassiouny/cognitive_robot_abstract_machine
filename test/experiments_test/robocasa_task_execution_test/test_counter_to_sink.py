import mujoco
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
    RoboCasaObjectName,
)
from coraplex.datastructures.enums import ExecutionType
from coraplex.execution_environment import ExecutionEnvironment
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


# %% composing the episode


def test_episodes_composed_with_the_same_seed_put_the_same_object_in_the_same_place():
    if not RoboCasaDatasetLoader().directory.exists():
        pytest.skip(
            "RoboCasa assets not downloaded. Run "
            "'python -m robocasa.scripts.download_kitchen_assets' first."
        )
    first, second = (
        CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=7)
        for _ in range(2)
    )

    assert (
        first.environment.objects[RoboCasaObjectName.TARGET].mjcf_path
        == second.environment.objects[RoboCasaObjectName.TARGET].mjcf_path
    )
    assert (
        first.target_object.root.global_pose.to_np().tolist()
        == second.target_object.root.global_pose.to_np().tolist()
    )


# %% where the PR2 starts


def test_the_pr2_starts_clear_of_the_kitchen(episode):
    assert not episode.robot.is_in_collision


def test_the_pr2_drives_its_base_with_servos(episode):
    """
    A physical simulation moves the base of the PR2 only through the servos of its
    drive.
    """
    drive = episode.robot.drive
    driven = {
        degree_of_freedom
        for actuator in episode.task.world.actuators
        for degree_of_freedom in actuator.dofs
    }

    assert {drive.x, drive.y, drive.yaw} <= driven


# %% judging where the object is


def test_an_object_still_on_the_counter_is_not_in_the_sink(episode):
    assert episode.outcome() == CounterToSinkOutcome(
        object_in_sink=False, object_released=True
    )


def test_an_object_let_go_of_at_the_placement_pose_is_above_the_sink(episode):
    episode.target_object.root.parent_connection.origin = (
        episode.placement_pose().homogeneous_matrix
    )

    assert episode.outcome() == CounterToSinkOutcome(
        object_in_sink=False, object_released=True
    )


def test_an_object_let_go_of_at_the_placement_pose_falls_into_the_sink(episode):
    episode.target_object.root.parent_connection.origin = (
        episode.placement_pose().homogeneous_matrix
    )

    episode.let_the_target_object_fall()

    assert episode.outcome() == CounterToSinkOutcome(
        object_in_sink=True, object_released=True
    )


# %% performing the task


def test_the_pr2_puts_the_object_into_the_sink(episode):
    assert episode.perform().succeeded


# %% placing into the basin


@pytest.fixture
def episode_holding_the_target_object() -> CounterToSinkEpisode:
    if not RoboCasaDatasetLoader().directory.exists():
        pytest.skip(
            "RoboCasa assets not downloaded. Run "
            "'python -m robocasa.scripts.download_kitchen_assets' first."
        )
    episode = CounterToSinkEpisode.compose(
        LayoutType.LAYOUT001, StyleType.STYLE001, seed=10
    )
    with ExecutionEnvironment(ExecutionType.KINEMATICALLY_SIMULATED):
        episode.pick_up_plan(sampling_seed=42).perform()
    return episode


def test_placing_lets_go_of_the_object_just_above_the_basin_floor(
    episode_holding_the_target_object,
):
    episode = episode_holding_the_target_object
    placing = episode.placing_into_the_sink()

    with ExecutionEnvironment(ExecutionType.KINEMATICALLY_SIMULATED):
        placing.plan().perform()

    lowest_point = (
        placing.held_object.collision.as_bounding_box_collection_in_frame(
            episode.task.world.root
        )
        .bounding_box()
        .min_z
    )
    assert lowest_point == pytest.approx(
        placing.basin.floor_height + placing.release_height, abs=0.01
    )


def test_an_object_placed_into_the_basin_comes_to_rest_in_the_sink(
    episode_holding_the_target_object,
):
    episode = episode_holding_the_target_object

    with ExecutionEnvironment(ExecutionType.KINEMATICALLY_SIMULATED):
        episode.placing_into_the_sink().plan().perform()
    episode.let_the_target_object_fall()

    assert episode.outcome() == CounterToSinkOutcome(
        object_in_sink=True, object_released=True
    )


# %% performing the task in physics


def test_the_physical_simulation_resolves_friction_for_holding_objects(episode):
    """
    An object held by friction slips out of fingers whose contacts resolve friction in
    pyramids at MuJoCo's default impedance ratio.
    """
    simulation = episode.start_physical_simulation(impedance_ratio=7.0)
    options = simulation.simulator._mj_model.opt
    simulation.stop_simulation()

    assert options.cone == mujoco.mjtCone.mjCONE_ELLIPTIC
    assert options.impratio == pytest.approx(7.0)
