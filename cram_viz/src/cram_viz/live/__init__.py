"""
Live mode: stream a running coraplex demo into the web viewer.

Two ways to use it:

1. As the run wrapper (e.g. a PyCharm run configuration)::

       cram-viz-live path/to/demo.py

2. As a one-liner at the top of a demo file::

       from cram_viz.live.runner import start; start()

Either way an HTTP bridge starts on port 8765 (``LIVE_VIZ_PORT`` to change);
while it is reachable the viewer shows a *Live* button that renders the
running world instead of the recording, and dragging an object writes its
pose back into the demo's world.

.. note:: This ``__init__`` intentionally imports nothing: the runner pulls in
   coraplex and giskardpy, which only exist in a demo environment, while
   :mod:`cram_viz.live.bridge` must stay importable everywhere (tests, the
   plain viewer).
"""
