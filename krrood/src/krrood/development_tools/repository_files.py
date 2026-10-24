"""
The files the development tools read and write in a repository.
"""

from __future__ import annotations

from enum import StrEnum


class RepositoryInstructionsFile(StrEnum):
    """
    The agent instruction files at a repository's root, by name.
    """

    AGENTS = "AGENTS.md"
    """
    The instructions agents read, holding the block of generated rules.
    """

    PROJECT_RULES = "agent_rules.py"
    """
    The module declaring the repository's own rules as subclasses of
    :class:`~krrood.development_tools.agent_rule.ProjectRules`.
    """
