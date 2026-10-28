"""
A few rule sets and sections standing in for the ones krrood ships.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.development_tools.agent_rule import AgentRule, Section
from krrood.ormatic.utils import classproperty

# %% rule sets


@dataclass(frozen=True)
class DatasetRule(AgentRule):
    """
    A rule of a rule set standing in for the ones krrood ships.
    """


@dataclass(frozen=True)
class AdditionalDatasetRule(AgentRule):
    """
    A rule of a second rule set, sharing the sections of :class:`DatasetRule`.
    """


# %% sections


class DesignPrinciplesRules(Section):
    """
    A section listing rules and holding a subsection.
    """

    KEEP_DESIGNS_SIMPLE = DatasetRule("A rule about design")


class ErrorsRules(Section):
    """
    A subsection whose first rule is spelled out by details and whose last rule belongs
    to another rule set.
    """

    @classproperty
    def parent(cls) -> type[Section]:
        return DesignPrinciplesRules

    RAISE_ERRORS = DatasetRule(
        "A rule about errors", ("A first detail", "A second detail")
    )

    NAME_ERRORS = DatasetRule("Another rule about errors")

    WRAP_ERRORS = AdditionalDatasetRule("A rule about errors of another rule set")


class TestingRules(Section):
    """
    A section listing rules only in its subsection.
    """


class AssertionsRules(Section):
    """
    The subsection of a section without rules of its own.
    """

    @classproperty
    def parent(cls) -> type[Section]:
        return TestingRules

    ASSERT_EXACTLY = DatasetRule("A rule about assertions")


class DeploymentRules(Section):
    """
    A section without rules of the rule set it belongs to.
    """


class ReleasesThroughCIRules(Section):
    """
    A subsection whose name ends in an acronym.
    """

    @classproperty
    def parent(cls) -> type[Section]:
        return DeploymentRules
