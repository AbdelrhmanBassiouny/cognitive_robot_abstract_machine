"""
The pipeline that reads the captures taken off the real camera.

Perception reads its surfaces from the world the robot publishes, which a test has no
robot to fetch, so the pipeline is built here from
:mod:`~experiments.montessori.perception.recorded_setup` instead -- the same two surfaces
the recordings were taken over.
"""

from __future__ import annotations

import pytest

from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import perception_pipeline


@pytest.fixture
def capture_pipeline() -> MontessoriPerceptionPipeline:
    """
    The pipeline that reads the shipped captures, over the surfaces they were taken on.
    """
    return perception_pipeline()
