"""
A repository's own rules module, standing in for the one a repository declares.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import ProjectRules, Subsection


class Deployment(Subsection[ProjectRules]):
    """
    The repository's rules on deploying.
    """

    DEPLOY_FROM_TAGS = "A project rule about deploying"
