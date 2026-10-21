from __future__ import annotations

import pytest

from .dataset.frames import NamedFrame

# %% reference frames


@pytest.fixture
def table_frame() -> NamedFrame:
    return NamedFrame("table")


@pytest.fixture
def camera_frame() -> NamedFrame:
    return NamedFrame("camera")
