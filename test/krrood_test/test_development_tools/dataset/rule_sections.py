"""
A small rule set standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import AgentRule, RuleSet

# %% rule set


class DatasetRules(RuleSet):
    """
    A rule set standing in for the ones krrood ships.
    """


# %% sections


class DesignPrinciples(DatasetRules):
    """
    A section listing rules and holding a subsection.
    """

    KEEP_DESIGNS_SIMPLE = AgentRule("A rule about design")


class Errors(DesignPrinciples):
    """
    A subsection whose first rule is spelled out by details.
    """

    RAISE_ERRORS = AgentRule(
        "A rule about errors", ("A first detail", "A second detail")
    )

    NAME_ERRORS = AgentRule("Another rule about errors")


class Testing(DatasetRules):
    """
    A section listing rules only in its subsection.
    """


class Assertions(Testing):
    """
    The subsection of a section without rules of its own.
    """

    ASSERT_EXACTLY = AgentRule("A rule about assertions")


class Deployment(DatasetRules):
    """
    A section without rules.
    """


class ReleasesThroughCI(Deployment):
    """
    A subsection whose name ends in an acronym.
    """
