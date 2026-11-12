from __future__ import annotations

import pytest

from .dataset.frames import NamedFrame, Room

# %% Cartesian frames


@pytest.fixture
def table_frame() -> NamedFrame:
    return NamedFrame("table")


@pytest.fixture
def camera_frame() -> NamedFrame:
    return NamedFrame("camera")


@pytest.fixture
def gripper_frame() -> NamedFrame:
    return NamedFrame("gripper")


# %% the space frames chart


@pytest.fixture
def room() -> Room:
    return Room()
