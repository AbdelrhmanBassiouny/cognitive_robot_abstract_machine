"""
Small rule catalogues standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import AgentRule, RuleCatalogue, Section
from krrood.development_tools.rules.sections import Errors, StructuredData

# %% rule set


class DatasetRules(RuleCatalogue):
    """
    A rule set standing in for the ones krrood ships.
    """


# %% catalogues


class DatasetErrors(Errors, DatasetRules):
    """
    A catalogue with one rule on errors, spelled out by details.
    """

    RAISE_ERRORS = AgentRule(
        "A rule about errors", ("A first detail", "A second detail")
    )


class OtherDatasetErrors(Errors, DatasetRules):
    """
    A second catalogue with rules on errors.
    """

    NAME_ERRORS = AgentRule("Another rule about errors")


class DatasetStructuredData(StructuredData, DatasetRules):
    """
    A catalogue with one rule on structured data.
    """

    STRUCTURE_DATA = AgentRule("A rule about structured data")


# %% misdeclarations


class SectionlessRules(DatasetRules):
    """
    A catalogue that subclasses no section.
    """

    STRAY_RULE = AgentRule("A rule without a section")


class UntitledSection(Section):
    """
    A section that declares no title.
    """
