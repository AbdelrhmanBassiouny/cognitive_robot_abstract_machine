"""
Browser-based visualization for the CRAM architecture.

.. note:: Configuring logging is left to the entry points (:func:`cram_viz.server.main`
   and friends). Calling :func:`logging.basicConfig` here would install a root handler
   at import time, which silently turns their own ``basicConfig`` calls into no-ops.
"""

import logging

__version__ = "1.0.0"

logger = logging.getLogger(__name__)
