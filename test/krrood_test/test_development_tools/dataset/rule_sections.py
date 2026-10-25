"""
A small rule set standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import NestedIn, RuleSet, Section

# %% rule set


class DatasetRules(RuleSet):
    """
    A rule set standing in for the ones krrood ships.
    """


# %% sections


class DesignPrinciples(NestedIn[DatasetRules], Section):
    """
    A section listing rules and holding a subsection.
    """

    KEEP_DESIGNS_SIMPLE = "A rule about design"


class Errors(NestedIn[DesignPrinciples], Section):
    """
    A subsection whose first rule is spelled out by details.
    """

    RAISE_ERRORS = ("A rule about errors", ("A first detail", "A second detail"))

    NAME_ERRORS = "Another rule about errors"


class Testing(NestedIn[DatasetRules], Section):
    """
    A section listing rules only in its subsection.
    """


class Assertions(NestedIn[Testing], Section):
    """
    The subsection of a section without rules of its own.
    """

    ASSERT_EXACTLY = "A rule about assertions"


class Deployment(NestedIn[DatasetRules], Section):
    """
    A section without rules.
    """


class ReleasesThroughCI(NestedIn[Deployment], Section):
    """
    A subsection whose name ends in an acronym.
    """
