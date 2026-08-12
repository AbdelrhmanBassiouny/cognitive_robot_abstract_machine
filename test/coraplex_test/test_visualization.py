"""
Tests for the canonical coraplex visualization entry point: backend selection from the
environment and end-to-end Rerun recording of a performed plan.
"""

import pytest

from coraplex.datastructures.enums import VisualizationBackend
from coraplex.exceptions import UnknownVisualizationOption
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.visualization import (
    RERUN_MODE_VARIABLE,
    RERUN_TARGET_VARIABLE,
    VISUALIZATION_BACKEND_VARIABLE,
    WorldVisualization,
)
from semantic_digital_twin.adapters.rerun import RerunAdapter, RerunMode
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.world import World


# %% backend selection from the environment


def test_from_environment_selects_backend(monkeypatch) -> None:
    """
    The environment variables select the backend, the Rerun mode, and the Rerun target.
    """
    monkeypatch.setenv(VISUALIZATION_BACKEND_VARIABLE, "rerun")
    monkeypatch.setenv(RERUN_MODE_VARIABLE, "save")
    monkeypatch.setenv(RERUN_TARGET_VARIABLE, "/some/recording.rrd")

    visualization = WorldVisualization.from_environment(World())

    assert visualization.backend == VisualizationBackend.RERUN
    assert visualization.rerun_mode == RerunMode.SAVE
    assert visualization.rerun_target == "/some/recording.rrd"


def test_from_environment_uses_defaults_without_variables(monkeypatch) -> None:
    """
    Without any environment variables set, the given default backend is used with a
    spawned viewer and no target.
    """
    monkeypatch.delenv(VISUALIZATION_BACKEND_VARIABLE, raising=False)
    monkeypatch.delenv(RERUN_MODE_VARIABLE, raising=False)
    monkeypatch.delenv(RERUN_TARGET_VARIABLE, raising=False)

    visualization = WorldVisualization.from_environment(
        World(), default_backend=VisualizationBackend.RERUN
    )

    assert visualization.backend == VisualizationBackend.RERUN
    assert visualization.rerun_mode == RerunMode.SPAWN
    assert visualization.rerun_target is None


def test_from_environment_rejects_unknown_backend(monkeypatch) -> None:
    """
    A value that names no backend raises an exception listing the valid values.
    """
    monkeypatch.setenv(VISUALIZATION_BACKEND_VARIABLE, "hologram")

    with pytest.raises(UnknownVisualizationOption):
        WorldVisualization.from_environment(World())


# %% inert NONE backend


def test_none_backend_registers_nothing() -> None:
    """
    Starting the NONE backend adds no world callbacks and creates no adapter or node.
    """
    world = World()
    state_callbacks_before = len(world.state.state_change_callbacks)

    visualization = WorldVisualization(world=world).start()

    assert len(world.state.state_change_callbacks) == state_callbacks_before
    assert visualization.rerun_adapter is None
    assert visualization.ros_node is None
    visualization.stop()


# %% end-to-end recording


def test_rerun_save_records_plan_events(immutable_model_world, tmp_path) -> None:
    """
    Performing a plan under a SAVE-mode Rerun visualization records both the world's
    bodies and the plan's events into the ``.rrd``.
    """
    world, robot_view, context = immutable_model_world
    recording_file_path = tmp_path / "demo.rrd"
    visualization = WorldVisualization(
        world=world,
        backend=VisualizationBackend.RERUN,
        rerun_mode=RerunMode.SAVE,
        rerun_target=str(recording_file_path),
    ).start()
    plan = sequential([MoveTorsoAction(TorsoState.HIGH)], context=context).plan
    visualization.attach_plan(plan)

    with simulated_robot:
        plan.perform()
    timeline = visualization.rerun_adapter.timeline
    visualization.stop()

    recorded = RerunAdapter.read_recording_entities(
        str(recording_file_path), timeline=timeline
    )
    assert any(path.startswith("/world/") for path in recorded)
    assert any(path.startswith("/plan/") for path in recorded)
