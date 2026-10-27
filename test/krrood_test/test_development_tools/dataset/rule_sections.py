"""
A few rule sets and sections standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import RuleSet, Section
from krrood.ormatic.utils import classproperty

# %% rule sets


class DatasetRules(RuleSet):
    """
    A rule set standing in for the ones krrood ships.
    """


class AdditionalDatasetRules(RuleSet):
    """
    A second rule set, some of whose rules are in the sections of :class:`DatasetRules`.
    """


# %% sections


class DesignPrinciples(Section):
    """
    A section listing rules and holding a subsection.
    """

    @classproperty
    def default_rule_set(cls) -> type[RuleSet]:
        return DatasetRules

    KEEP_DESIGNS_SIMPLE = "A rule about design"


class Errors(Section):
    """
    A subsection whose first rule is spelled out by details and whose last rule belongs
    to another rule set.
    """

    @classproperty
    def parent(cls) -> type[Section]:
        return DesignPrinciples

    RAISE_ERRORS = ("A rule about errors", ("A first detail", "A second detail"))

    NAME_ERRORS = "Another rule about errors"

    WRAP_ERRORS = "A rule about errors of another rule set", (), AdditionalDatasetRules


class Testing(Section):
    """
    A section listing rules only in its subsection.
    """

    @classproperty
    def default_rule_set(cls) -> type[RuleSet]:
        return DatasetRules


class Assertions(Section):
    """
    The subsection of a section without rules of its own.
    """

    @classproperty
    def parent(cls) -> type[Section]:
        return Testing

    ASSERT_EXACTLY = "A rule about assertions"


class Deployment(Section):
    """
    A section without rules of the rule set it belongs to.
    """

    @classproperty
    def default_rule_set(cls) -> type[RuleSet]:
        return DatasetRules


class ReleasesThroughCI(Section):
    """
    A subsection whose name ends in an acronym.
    """

    @classproperty
    def parent(cls) -> type[Section]:
        return Deployment
