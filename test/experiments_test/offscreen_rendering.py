"""
Whether this run can draw a picture at all.

Shared by every test that draws one, so the condition a drawing is skipped under is
written once rather than once per test module.
"""

from __future__ import annotations

import os

import pytest

from semantic_digital_twin.adapters.picture import (
    OFFSCREEN_PLATFORM_VARIABLE,
    OffscreenPlatform,
)


def can_draw_without_a_screen() -> bool:
    """
    Whether this run draws through a platform that needs no window.

    The picture module asks for one itself unless the run named a platform of its own,
    so this is false only for a run that named a windowed one.
    """
    return os.environ.get(OFFSCREEN_PLATFORM_VARIABLE, "").lower() in tuple(
        OffscreenPlatform
    )


needs_a_renderer = pytest.mark.skipif(
    not can_draw_without_a_screen(),
    reason="%s names a windowed platform, so nothing can be drawn without a screen"
    % OFFSCREEN_PLATFORM_VARIABLE,
)
"""
Skips a test that has to draw a picture where this run cannot draw one.
"""
