"""
Statechart execution preserves its final state in a Cramera recording.
"""

from unittest.mock import Mock

from coraplex.plans.executors import SimulatedPlanExecutor
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from cramera.live import visualization as visualization_module
from cramera.live.bridge import Bridge
from cramera.live.chart_observer import ChartObserver
from cramera.live.recording import Recording
from cramera.live.visualization import LiveVisualization
from cramph.composites import Sequence
from cramph.data_types import LifeCycleValues
from semantic_digital_twin.datastructures.definitions import TorsoState
from ...plan_running import statechart_of


# %% recording execution
def test_motion_recording_retains_completed_chart(
    pr2_apartment_context, monkeypatch
) -> None:
    """
    A real torso motion records its final chart, which the recording holds once the
    visualization is stopped, and releases its observer.
    """
    world, robot, extensions = pr2_apartment_context
    finalized: list[Recording] = []
    monkeypatch.setattr(visualization_module, "serve", Mock())
    monkeypatch.setattr(
        visualization_module.RosMarkerListener,
        "start_if_available",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        visualization_module,
        "finalize_recording",
        lambda bridge, recording: finalized.append(recording),
    )
    plan = Sequence(nodes=[MoveTorsoAction(torso_state=TorsoState.HIGH)])
    bridge = Bridge()
    live = LiveVisualization(bridge=bridge)
    executor = SimulatedPlanExecutor(
        world, context_extensions=extensions, extensions=[live]
    )

    executor.compile(statechart_of(executor, plan))
    executor.execute()
    live.stop()

    [recording] = finalized
    frames = recording.stop()
    assert plan.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert frames
    chart = plan.statechart
    expected = ChartObserver(title=bridge.chart_state.title).snapshot(chart)
    assert frames[-1].statechart == expected
    assert bridge.chart_state == expected
    assert all(observer is not live.publishing for observer in chart.history.observers)
