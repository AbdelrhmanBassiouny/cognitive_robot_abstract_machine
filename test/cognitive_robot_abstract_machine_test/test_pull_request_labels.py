"""
Tests that the pull request labels match the repository.
"""

from __future__ import annotations

from cognitive_robot_abstract_machine.orm_interfaces import REPOSITORY_ROOT
from cognitive_robot_abstract_machine.pull_request_labels import FrameworkLabel

# %% framework labels


def test_every_framework_label_names_a_directory_at_the_repository_root():
    missing = [
        label
        for label in FrameworkLabel
        if not (REPOSITORY_ROOT / label.directory).is_dir()
    ]
    assert missing == []
