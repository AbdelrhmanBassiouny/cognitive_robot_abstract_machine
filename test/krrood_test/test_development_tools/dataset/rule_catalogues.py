"""
Small rule catalogues standing in for the ones krrood ships.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import (
    KrroodRule,
    PythonRule,
    RuleCatalogue,
    RuleSection,
)


class ErrorRules(RuleCatalogue):
    """
    A catalogue with one rule on errors, spelled out by details.
    """

    RAISE_ERRORS = PythonRule(
        RuleSection.ERRORS,
        "A Python rule about errors",
        ("A first detail", "A second detail"),
    )


class ErrorAndStructuredDataRules(RuleCatalogue):
    """
    A catalogue with two rules on errors and one on structured data.
    """

    NAME_ERRORS = KrroodRule(RuleSection.ERRORS, "A krrood rule about errors")
    STRUCTURE_DATA = KrroodRule(
        RuleSection.STRUCTURED_DATA, "A krrood rule about structured data"
    )
    DOCUMENT_ERRORS = KrroodRule(RuleSection.ERRORS, "Another krrood rule about errors")
