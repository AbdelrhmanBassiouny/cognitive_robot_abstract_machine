"""
Every command the builder answers.

The families are imported here rather than beside the base they subclass:
:func:`commands_of` finds a command by its class existing, so something has to
have imported each family, and the base cannot import what imports it.
"""

from __future__ import annotations

from command_line import commands_of

from integration_build_commands import BuildCommand  # noqa: F401
from integration_candidate_commands import OpenCandidateCommand  # noqa: F401
from integration_resolution_commands import StageConflictCommand  # noqa: F401
from integration_run import IntegrationCommand

COMMANDS: tuple[IntegrationCommand, ...] = commands_of(IntegrationCommand)
"""
Every command this builder answers, found from the subclasses themselves so a command
cannot exist without being reachable, in the order they are defined.
"""
