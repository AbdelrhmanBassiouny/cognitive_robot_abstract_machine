"""
Which graphics backend MuJoCo is asked for when something draws with no window.

Both a video recorder and a camera in the twin render offscreen, and both would abort
with no OpenGL context on a machine with no display, so the choice is made in one place
and these are the three cases it has to get right.
"""

from __future__ import annotations

import os

import pytest

from semantic_digital_twin.adapters.multi_sim import (
    MUJOCO_RENDERING_BACKEND_VARIABLE,
    MujocoRenderingBackend,
    select_offscreen_rendering_backend,
)

WINDOWED_BACKEND = "glfw"
"""
MuJoCo's own default where a display is present, which an offscreen render cannot use.
"""


@pytest.fixture
def forgotten_rendering_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Leave MuJoCo's backend unset, so each test states the one it is about.
    """
    monkeypatch.delenv(MUJOCO_RENDERING_BACKEND_VARIABLE, raising=False)


def test_a_backend_is_chosen_where_none_was_asked_for(
    forgotten_rendering_backend: None,
) -> None:
    """
    Something drawing with no window gets a backend that can, rather than being left to
    MuJoCo's windowed default.
    """
    select_offscreen_rendering_backend()

    assert os.environ[MUJOCO_RENDERING_BACKEND_VARIABLE] == MujocoRenderingBackend.EGL


@pytest.mark.parametrize("asked_for", tuple(MujocoRenderingBackend))
def test_a_backend_that_can_already_draw_with_no_window_is_left_alone(
    forgotten_rendering_backend: None, asked_for: MujocoRenderingBackend
) -> None:
    """
    A caller that named a headless backend keeps it: which of them draws best is the
    machine's affair rather than this choice's.
    """
    os.environ[MUJOCO_RENDERING_BACKEND_VARIABLE] = asked_for

    select_offscreen_rendering_backend()

    assert os.environ[MUJOCO_RENDERING_BACKEND_VARIABLE] == asked_for


def test_a_windowed_backend_is_overruled(forgotten_rendering_backend: None) -> None:
    """
    A backend needing a display is not one an offscreen render can use, so it is
    replaced rather than left to abort with no context.
    """
    os.environ[MUJOCO_RENDERING_BACKEND_VARIABLE] = WINDOWED_BACKEND

    select_offscreen_rendering_backend()

    assert os.environ[MUJOCO_RENDERING_BACKEND_VARIABLE] == MujocoRenderingBackend.EGL
