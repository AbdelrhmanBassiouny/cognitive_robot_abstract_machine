"""
The sections of the rules krrood ships, nested as ``AGENTS.md`` lists them.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import Section
from krrood.ormatic.utils import classproperty


class CodeQualityRules(Section):
    """
    The rules on writing code of any repository.
    """

    @classproperty
    def title(cls) -> str:
        return "Code Quality Rules"


class ApplyingTheseRules(CodeQualityRules):
    """
    The rules on when and how far the other rules apply.
    """

    @classproperty
    def title(cls) -> str:
        return "Applying These Rules"


class AskTheDeveloper(CodeQualityRules):
    """
    The rules on what to ask the developer instead of deciding.
    """

    @classproperty
    def title(cls) -> str:
        return "Ask the Developer"


class Testing(CodeQualityRules):
    """
    The rules on tests.
    """

    @classproperty
    def title(cls) -> str:
        return "Testing"


class WritingTests(Testing):
    """
    The rules on writing tests.
    """

    @classproperty
    def title(cls) -> str:
        return "Writing Tests"


class Assertions(Testing):
    """
    The rules on what a test asserts.
    """

    @classproperty
    def title(cls) -> str:
        return "Assertions"


class ExternalServicesAndCI(Testing):
    """
    The rules on tests that reach external services, and on tests in CI.
    """

    @classproperty
    def title(cls) -> str:
        return "External Services and CI"


class RunningTests(Testing):
    """
    The rules on running tests.
    """

    @classproperty
    def title(cls) -> str:
        return "Running Tests"


class CodeStyle(CodeQualityRules):
    """
    The rules on the shape of code.
    """

    @classproperty
    def title(cls) -> str:
        return "Code Style"


class Naming(CodeStyle):
    """
    The rules on naming.
    """

    @classproperty
    def title(cls) -> str:
        return "Naming"


class Imports(CodeQualityRules):
    """
    The rules on imports.
    """

    @classproperty
    def title(cls) -> str:
        return "Imports"


class DesignPrinciples(CodeQualityRules):
    """
    The rules on the design of classes and modules.
    """

    @classproperty
    def title(cls) -> str:
        return "Design Principles"


class Methods(DesignPrinciples):
    """
    The rules on methods.
    """

    @classproperty
    def title(cls) -> str:
        return "Methods"


class Errors(DesignPrinciples):
    """
    The rules on raising and declaring exceptions.
    """

    @classproperty
    def title(cls) -> str:
        return "Errors"


class ConstantsAndClassLevelValues(DesignPrinciples):
    """
    The rules on constants and values shared by a class.
    """

    @classproperty
    def title(cls) -> str:
        return "Constants and Class-Level Values"


class StructuredData(DesignPrinciples):
    """
    The rules on representing data with structure instead of bare literals.
    """

    @classproperty
    def title(cls) -> str:
        return "Structured Data"


class TypeHints(CodeQualityRules):
    """
    The rules on type hints.
    """

    @classproperty
    def title(cls) -> str:
        return "Type Hints"


class Documentation(CodeQualityRules):
    """
    The rules on docstrings and comments.
    """

    @classproperty
    def title(cls) -> str:
        return "Documentation"


class VersionControl(CodeQualityRules):
    """
    The rules on commits, pushes and pull requests.
    """

    @classproperty
    def title(cls) -> str:
        return "Version Control"


class Misc(CodeQualityRules):
    """
    The rules that fit no other section.
    """

    @classproperty
    def title(cls) -> str:
        return "Misc"
