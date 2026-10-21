"""
Starting the live viewer as a library call.
"""

from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from cramera.live.http import DEFAULT_PORT
from cramera.live import visualization

# %% starting the viewer

if TYPE_CHECKING:
    from semantic_digital_twin.world import World

    from cramera.live.visualization import LiveVisualization


def start(world: World, port: int = DEFAULT_PORT) -> LiveVisualization:
    """
    Serve a world to the browser viewer until the returned visualization is stopped.

    To show the runs of an executor instead, add a
    :class:`~cramera.live.visualization.LiveVisualization` to its extensions.

    :param world: The world to serve.
    :param port: Port of the bridge's HTTP endpoints.
    :return: The started visualization.
    """
    return visualization.LiveVisualization(port=port).start(world)
