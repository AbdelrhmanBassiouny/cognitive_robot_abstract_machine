"""
Unit tests for the live runner: the library entry point and the demo wrapper CLI.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.world import World
from typing_extensions import Self


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
