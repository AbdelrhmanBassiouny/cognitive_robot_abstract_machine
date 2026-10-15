"""
Starting the live viewer: as a library call or as the demo wrapper CLI.
"""

from __future__ import annotations

import logging
import os
import runpy
import signal
import sys
from pathlib import Path

from typing_extensions import TYPE_CHECKING
from coraplex.datastructures.enums import VisualizationBackend, VisualizationOption

from cramera.live.http import DEFAULT_PORT
from cramera.live import visualization
from cramera.logging_setup import get_logger

if TYPE_CHECKING:
    from semantic_digital_twin.world import World

    from cramera.live.visualization import LiveVisualization

logger = get_logger(__name__)


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


def main() -> None:
    """
    ``cramera-live path/to/demo.py`` — run a demo with the browser viewer.

    Selects the cramera backend through ``CORAPLEX_VISUALIZATION`` and runs the demo
    unchanged: the visualizations the demo selects through the environment pick the
    backend up. The demo's directory is put on ``sys.path`` so it can import its local
    helper modules, exactly as if it were started directly. After the demo finishes the
    viewer stays up for inspection until Ctrl-C.
    """
    logging.basicConfig(level=logging.INFO, force=True)
    if len(sys.argv) < 2:
        sys.exit("usage: cramera-live path/to/demo.py")
    demo = Path(sys.argv[1]).resolve()
    os.environ.setdefault(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA)
    sys.path.insert(0, str(demo.parent))
    logger.info("running demo: %s", demo)
    runpy.run_path(str(demo), run_name="__main__")
    logger.info("demo finished — viewer stays up for inspection (Ctrl-C to quit)")
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    signal.sigwait({signal.SIGINT})


if __name__ == "__main__":
    main()
