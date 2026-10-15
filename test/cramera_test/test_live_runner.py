"""
Unit tests for the live runner: the library entry point and the demo wrapper CLI.
"""

from __future__ import annotations

import os
import runpy
import signal
import sys
from dataclasses import dataclass

from semantic_digital_twin.world import World
from typing_extensions import Any, Dict, List, Self

import pytest

from coraplex.datastructures.enums import VisualizationBackend, VisualizationOption
from cramera.live import runner, visualization

# %% serving a world


@dataclass
class VisualizationRecordingItsStart:
    """
    A visualization recording the world it was started on.
    """

    port: int
    """
    The port it was asked to serve on.
    """

    started_world: World | None = None
    """
    The world it was started on, if it was.
    """

    def start(self, world: World) -> Self:
        """
        Record `world` as started.

        :param world: The world to serve.
        :return: This visualization.
        """
        self.started_world = world
        return self


class TestStart:
    def test_start_serves_the_given_world(self, monkeypatch):
        monkeypatch.setattr(
            visualization, "LiveVisualization", VisualizationRecordingItsStart
        )
        world = World()

        result = runner.start(world, port=1234)

        assert isinstance(result, VisualizationRecordingItsStart)
        assert result.started_world is world
        assert result.port == 1234


# %% running a demo


@pytest.fixture(autouse=True)
def interrupted_inspection(monkeypatch) -> List[str]:
    """
    End the inspection after a demo as if Ctrl-C was pressed at once, leaving the signal
    mask of the test process alone.

    :return: Records ``"inspected"`` for every inspection that waited for Ctrl-C.
    """
    inspections: List[str] = []
    monkeypatch.setattr(signal, "pthread_sigmask", lambda how, mask: set())
    monkeypatch.setattr(
        signal, "sigwait", lambda signals: inspections.append("inspected")
    )
    return inspections


class TestMain:
    def test_main_preselects_the_cramera_backend_and_runs_the_demo(self, monkeypatch):
        run_calls: List[Dict[str, Any]] = []
        # main() preselects the backend by writing the real environment, and monkeypatch
        # records an undo only for a variable that was there: setting it first, then
        # deleting it, leaves the test with none and still restores that afterwards
        monkeypatch.setenv(VisualizationOption.BACKEND, "restored-on-teardown")
        monkeypatch.delenv(VisualizationOption.BACKEND)
        monkeypatch.setattr(sys, "argv", ["cramera-live", "/demos/demo.py"])
        monkeypatch.setattr(
            runpy,
            "run_path",
            lambda path, run_name: run_calls.append(
                {"path": path, "run_name": run_name}
            ),
        )

        runner.main()

        assert os.environ[VisualizationOption.BACKEND] == VisualizationBackend.CRAMERA
        assert run_calls == [{"path": "/demos/demo.py", "run_name": "__main__"}]
        assert "/demos" in sys.path

    def test_main_keeps_an_explicit_backend_choice(self, monkeypatch):
        """
        ``CORAPLEX_VISUALIZATION=rerun cramera-live demo.py`` is a deliberate override
        and must survive.
        """
        monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.RERUN)
        monkeypatch.setattr(sys, "argv", ["cramera-live", "/demos/demo.py"])
        monkeypatch.setattr(runpy, "run_path", lambda path, run_name: None)

        runner.main()

        assert os.environ[VisualizationOption.BACKEND] == VisualizationBackend.RERUN

    def test_main_keeps_the_viewer_up_after_the_demo_until_interrupted(
        self, monkeypatch, interrupted_inspection
    ):
        events: List[str] = interrupted_inspection
        monkeypatch.setattr(sys, "argv", ["cramera-live", "/demos/demo.py"])
        monkeypatch.setattr(
            runpy, "run_path", lambda path, run_name: events.append("ran")
        )

        runner.main()

        assert events == ["ran", "inspected"]
