"""
A repository's own rules module, standing in for the one a repository declares.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import ProjectRules, RuleSet, Section
from krrood.ormatic.utils import classproperty


class Deployment(Section):
    """
    The repository's rules on deploying.
    """

    @classproperty
    def default_rule_set(cls) -> type[RuleSet]:
        return ProjectRules

    DEPLOY_FROM_TAGS = "A project rule about deploying"
