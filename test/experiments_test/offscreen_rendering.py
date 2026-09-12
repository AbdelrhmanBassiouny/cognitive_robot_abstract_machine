"""
Whether this run can draw a MuJoCo picture at all.

Shared by every test that renders one, so the condition a render is skipped under is
written once rather than once per test module.
"""

from __future__ import annotations

import os

import pytest

from semantic_digital_twin.adapters.multi_sim import (
    MUJOCO_RENDERING_BACKEND_VARIABLE,
    MujocoRenderingBackend,
)


def can_draw_without_a_screen() -> bool:
    """
    Whether this run named a backend MuJoCo can draw offscreen through.

    MuJoCo locks its backend at the moment it is imported, so a run that has to draw
    without a window names one in the environment it starts from; a run that named none
    falls back to the windowed backend and aborts the render.
    """
    return os.environ.get(MUJOCO_RENDERING_BACKEND_VARIABLE, "").lower() in tuple(
        MujocoRenderingBackend
    )


needs_a_renderer = pytest.mark.skipif(
    not can_draw_without_a_screen(),
    reason="%s names no offscreen backend, so nothing can be drawn"
    % MUJOCO_RENDERING_BACKEND_VARIABLE,
)
"""
Skips a test that has to draw a picture where this run cannot draw one.
"""
