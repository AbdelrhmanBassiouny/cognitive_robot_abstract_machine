"""
A repository's own rules module, standing in for the one a repository declares.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import ProjectRule, Section


class DeploymentRules(Section):
    """
    The repository's rules on deploying.
    """

    DEPLOY_FROM_TAGS = ProjectRule("A project rule about deploying")
