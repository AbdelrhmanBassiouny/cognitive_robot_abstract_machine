"""
A module applying ``@rdr`` the way a user does - at import time, above a ``def``.

Kept apart from the tests so importing it *is* the exercise: the decorator runs while
this module is still executing its own body, which is the moment the model file has to be
readable although the decorated name is not bound yet.
"""

from __future__ import annotations

import os
import tempfile

from krrood.entity_query_language.rdr.decorator import rdr

MODEL_FILE: str = os.path.join(tempfile.mkdtemp(), "grasp_force_rdr.py")
"""
Where this module's model is kept, outside the source tree so importing it writes nothing
beside this file.
"""

FALLBACK_FORCE: float = 5.0
"""
The grasp force :func:`predict_force` falls back to before any rule is fitted.
"""


@rdr(MODEL_FILE)
def predict_force(weight: float, material: str) -> float:
    """
    Predict the force needed to grasp an object.

    :param weight: How heavy the object is, in kilograms.
    :param material: What the object is made of.
    :return: The grasp force in Newtons.
    """
    return FALLBACK_FORCE
