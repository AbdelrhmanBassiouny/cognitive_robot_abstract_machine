"""
Tests for generating the experiments package's ORM interface.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .dataset import generate_orm_without_ros_messages

# %% generating without the ROS overlay


def test_generation_needs_no_ros_message_package():
    """
    The generator maps the package in an interpreter that cannot import ``json_msgs``.
    """
    launcher = Path(generate_orm_without_ros_messages.__file__)
    run = subprocess.run(
        [sys.executable, str(launcher)],
        cwd=generate_orm_without_ros_messages.GENERATOR.parent,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-3000:]
    assert generate_orm_without_ros_messages.GENERATOR.exists()
