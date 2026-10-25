"""
A small rule set standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import RuleSet, Subsection

# %% rule set


class DatasetRules(RuleSet):
    """
    A rule set standing in for the ones krrood ships.
    """


# %% sections


class DesignPrinciples(Subsection[DatasetRules]):
    """
    A section listing rules and holding a subsection.
    """

    KEEP_DESIGNS_SIMPLE = "A rule about design"


class Errors(Subsection[DesignPrinciples]):
    """
    A subsection whose first rule is spelled out by details.
    """

    RAISE_ERRORS = ("A rule about errors", ("A first detail", "A second detail"))

    NAME_ERRORS = "Another rule about errors"


class Testing(Subsection[DatasetRules]):
    """
    A section listing rules only in its subsection.
    """


class Assertions(Subsection[Testing]):
    """
    The subsection of a section without rules of its own.
    """

    ASSERT_EXACTLY = "A rule about assertions"


class Deployment(Subsection[DatasetRules]):
    """
    A section without rules.
    """


class ReleasesThroughCI(Subsection[Deployment]):
    """
    A subsection whose name ends in an acronym.
    """
