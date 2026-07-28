"""Live mode: stream a RUNNING coraplex demo into the web viewer.

Two ways to use it:

1. As the run wrapper (e.g. a PyCharm run configuration):

       cram-viz-live path/to/demo.py

2. As a one-liner at the TOP of a demo file:

       from cram_viz import live; live.start()

Either way an HTTP bridge starts on port 8765 (LIVE_VIZ_PORT to change); while
it is reachable the viewer shows a "Live" button that renders the running world
instead of the recording, and dragging an object writes its pose back into the
demo's world.
"""

from cram_viz.live import hooks as _hooks
from cram_viz.live.bridge import BRIDGE
from cram_viz.live.http import PORT, serve


def start(world=None, port=PORT):
    """Start the live bridge. Call once, ideally at the top of a demo."""
    _hooks._install_mesh_hook()    # before the demo parses its objects
    _hooks._install_plan_hooks()
    if world is not None:
        BRIDGE.world = world
        BRIDGE._bind()
        BRIDGE.snapshot()          # single-threaded here, before execution starts
    _hooks._install_tick_hook()
    server = serve(port)
    print("[cram_viz.live] bridge on http://localhost:%d  (viewer shows a Live button while this runs)" % port,
          flush=True)
    return server
