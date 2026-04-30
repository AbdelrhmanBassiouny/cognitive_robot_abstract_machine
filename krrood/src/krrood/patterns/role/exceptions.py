"""
Exceptions for the role transformer subsystem.
"""

from __future__ import annotations


class RoleTransformerError(ValueError):
    """Raised when a parsed node has an unexpected type during role transformation."""
