"""
A repository's own rules module, standing in for the one a repository declares.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import (
    ProjectRule,
    RuleCatalogue,
    RuleSection,
    SectionHeading,
    SectionHeadings,
)


class OwnSection(SectionHeadings):
    """
    The sections of the repository's own rules.
    """

    OWN_RULES = SectionHeading("Own Rules", 1)
    DEPLOYMENT = SectionHeading("Deployment", 2)


class OwnRules(RuleCatalogue):
    """
    One rule in a shared section and one in the repository's own section.
    """

    RUN_TESTS_IN_CONTAINERS = ProjectRule(
        RuleSection.RUNNING_TESTS, "A project rule about running tests"
    )
    DEPLOY_FROM_TAGS = ProjectRule(
        OwnSection.DEPLOYMENT, "A project rule about deploying"
    )
