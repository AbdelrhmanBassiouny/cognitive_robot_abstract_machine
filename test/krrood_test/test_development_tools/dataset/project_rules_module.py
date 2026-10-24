"""
A repository's own rules module, standing in for the one a repository declares.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import AgentRule, ProjectRules, Section
from krrood.development_tools.rules.sections import RunningTests
from krrood.ormatic.utils import classproperty

# %% sections


class OwnRules(Section):
    """
    The sections of the repository's own rules.
    """

    @classproperty
    def title(cls) -> str:
        return "Own Rules"


class Deployment(OwnRules):
    """
    The repository's rules on deploying.
    """

    @classproperty
    def title(cls) -> str:
        return "Deployment"


# %% rules


class OwnRunningTests(RunningTests, ProjectRules):
    """
    The repository's rules in a shared section.
    """

    RUN_TESTS_IN_CONTAINERS = AgentRule("A project rule about running tests")


class DeploymentRules(Deployment, ProjectRules):
    """
    The repository's rules in a section of its own.
    """

    DEPLOY_FROM_TAGS = AgentRule(
        "A project rule about deploying", ("A first detail", "A second detail")
    )
