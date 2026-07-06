__version__ = "0.7.2"

import logging

logger = logging.Logger("rdr")
logger.setLevel(logging.INFO)


def get_qt_app():
    """Return the global QApplication instance, creating it lazily on first call.

    Previously the QApplication was created at import time, which is a side
    effect that breaks headless environments and test isolation.
    """
    global get_qt_app
    try:
        from PyQt6.QtWidgets import QApplication
        import sys

        app = QApplication(sys.argv)
    except ImportError:
        app = None

    def get_qt_app():
        return app

    return app


# Re-exports used by generated RDR Python files (``from krrood.ripple_down_rules import *``).
from .predicates import Predicate, IsA, Has, DependsOn, isA, has, dependsOn  # noqa: E402, F401
from .datastructures.tracked_object import TrackedObjectMixin  # noqa: E402, F401
from .datastructures.dataclasses import CaseQuery  # noqa: E402, F401
from .rdr_decorators import RDRDecorator  # noqa: E402, F401
from .rdr import MultiClassRDR, SingleClassRDR, GeneralRDR  # noqa: E402, F401

# Optional meta-package integration.
try:
    import ripple_down_rules_meta._apply_overrides  # noqa: F401
except ImportError:
    pass
