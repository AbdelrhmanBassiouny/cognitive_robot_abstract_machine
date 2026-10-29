"""
The labels of pull requests on this repository.
"""

from __future__ import annotations

from enum import StrEnum

# %% labels


class PullRequestLabel(StrEnum):
    """
    A label of a pull request on this repository, whose value is the label's text.
    """


class ChangeKindLabel(PullRequestLabel):
    """
    A label naming a kind of change a pull request makes.
    """

    API_BREAK = "api-break"
    """
    The change can break code that already uses it.
    """

    NEW_FEATURE = "new-feature"
    """
    The change adds public API or user-visible behaviour.
    """

    BUG_FIX = "bug-fix"
    """
    The change makes existing behaviour match its contract.
    """

    DOCUMENTATION = "documentation"
    """
    The change is made for its documentation.
    """

    DEV_TOOLS = "dev-tools"
    """
    The change modifies the tools contributors work with.
    """

    MAINTENANCE = "maintenance"
    """
    The change modifies code without changing its behaviour or API.
    """


class FrameworkLabel(PullRequestLabel):
    """
    A label naming a framework of this repository a pull request changes.

    A member is named after the framework's directory.
    """

    KRROOD = "KRROOD"
    """
    The label of ``krrood``.
    """

    SEMANTIC_DIGITAL_TWIN = "semDT"
    """
    The label of ``semantic_digital_twin``.
    """

    CORAPLEX = "CoraPlex"
    """
    The label of ``coraplex``.
    """

    GISKARDPY = "Giskard"
    """
    The label of ``giskardpy``.
    """

    SEGMIND = "segmind"
    """
    The label of ``segmind``.
    """

    EXPERIMENTS = "Experiment"
    """
    The label of ``experiments``.
    """

    ROBOKUDO = "Robokudo"
    """
    The label of ``robokudo``.
    """

    CRAMERA = "cramera"
    """
    The label of ``cramera``.
    """

    @property
    def directory(self) -> str:
        """
        The framework's directory at the repository root.
        """
        return self.name.lower()
