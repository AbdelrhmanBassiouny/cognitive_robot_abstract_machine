"""
A small rule set standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import AgentRule, RuleSet
from krrood.ormatic.utils import classproperty

# %% rule set


class DatasetRules(RuleSet):
    """
    A rule set standing in for the ones krrood ships.
    """

    @classproperty
    def title(cls) -> str:
        return "Dataset Rules"


# %% sections


class DesignPrinciples(DatasetRules):
    """
    A section listing rules and holding a subsection.
    """

    @classproperty
    def title(cls) -> str:
        return "Design Principles"

    KEEP_DESIGNS_SIMPLE = AgentRule("A rule about design")


class Errors(DesignPrinciples):
    """
    A subsection whose first rule is spelled out by details.
    """

    @classproperty
    def title(cls) -> str:
        return "Errors"

    RAISE_ERRORS = AgentRule(
        "A rule about errors", ("A first detail", "A second detail")
    )

    NAME_ERRORS = AgentRule("Another rule about errors")


class Testing(DatasetRules):
    """
    A section listing rules only in its subsection.
    """

    @classproperty
    def title(cls) -> str:
        return "Testing"


class Assertions(Testing):
    """
    The subsection of a section without rules of its own.
    """

    @classproperty
    def title(cls) -> str:
        return "Assertions"

    ASSERT_EXACTLY = AgentRule("A rule about assertions")


class Deployment(DatasetRules):
    """
    A section without rules.
    """

    @classproperty
    def title(cls) -> str:
        return "Deployment"


# %% misdeclarations


class UntitledSubsection(DesignPrinciples):
    """
    A subsection that declares no title of its own.
    """
