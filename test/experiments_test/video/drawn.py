"""
Keeping a test's drawing out of the checkout.

Manim writes the pictures it makes of a piece of text beside wherever it is run from, as
soon as the text is built rather than when a scene is rendered. A test that builds any
text therefore has to send that writing somewhere of its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="module")
def drawing_kept_out_of_the_checkout(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """
    Point Manim's writing at a directory of the test run's own.
    """
    from manim import config

    written_to = tmp_path_factory.mktemp("manim_media")
    config.media_dir = str(written_to)
    return written_to
