"""
The rules agents follow, the sections ``AGENTS.md`` groups them under and the catalogues
that hold them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# %% sections


@dataclass(frozen=True)
class SectionHeading:
    """
    The Markdown heading of one section of the rules.
    """

    title: str
    """
    The text of the heading.
    """

    level: int
    """
    The heading level, 1 for a top-level heading.
    """

    @property
    def markdown(self) -> str:
        """
        The heading as a line of Markdown.
        """
        return f"{'#' * self.level} {self.title}"


class SectionHeadings(Enum):
    """
    The sections of a set of rules, in the order ``AGENTS.md`` lists them, each member's
    value being its :class:`SectionHeading`.
    """

    @property
    def subsections(self) -> list[SectionHeadings]:
        """
        The sections of the same set nested under this one, at any depth.
        """
        sections = list(type(self))
        nested = []
        for section in sections[sections.index(self) + 1 :]:
            if section.value.level <= self.value.level:
                break
            nested.append(section)
        return nested


class RuleSection(SectionHeadings):
    """
    The sections of the shared rules, listed before any repository's own sections.
    """

    CODE_QUALITY_RULES = SectionHeading("Code Quality Rules", 1)
    APPLYING_THESE_RULES = SectionHeading("Applying These Rules", 2)
    ASK_THE_DEVELOPER = SectionHeading("Ask the Developer", 2)
    TESTING = SectionHeading("Testing", 2)
    WRITING_TESTS = SectionHeading("Writing Tests", 3)
    ASSERTIONS = SectionHeading("Assertions", 3)
    EXTERNAL_SERVICES_AND_CI = SectionHeading("External Services and CI", 3)
    RUNNING_TESTS = SectionHeading("Running Tests", 3)
    CODE_STYLE = SectionHeading("Code Style", 2)
    NAMING = SectionHeading("Naming", 3)
    IMPORTS = SectionHeading("Imports", 2)
    DESIGN_PRINCIPLES = SectionHeading("Design Principles", 2)
    METHODS = SectionHeading("Methods", 3)
    ERRORS = SectionHeading("Errors", 3)
    CONSTANTS_AND_CLASS_LEVEL_VALUES = SectionHeading(
        "Constants and Class-Level Values", 3
    )
    STRUCTURED_DATA = SectionHeading("Structured Data", 3)
    TYPE_HINTS = SectionHeading("Type Hints", 2)
    DOCUMENTATION = SectionHeading("Documentation", 2)
    VERSION_CONTROL = SectionHeading("Version Control", 2)
    MISC = SectionHeading("Misc", 2)


# %% rules


@dataclass(frozen=True)
class AgentRule:
    """
    One rule agents follow, rendered as a Markdown list item.
    """

    section: SectionHeadings
    """
    The section ``AGENTS.md`` lists the rule under, a shared :class:`RuleSection` or one
    of the repository's own.
    """

    statement: str
    """
    The rule itself.
    """

    details: tuple[str, ...] = ()
    """
    The points that spell the rule out, rendered as a nested list below it.
    """

    @property
    def markdown(self) -> str:
        """
        The rule as a Markdown list item, followed by its details.
        """
        return "\n".join(
            [f"- {self.statement}", *(f"  - {detail}" for detail in self.details)]
        )


@dataclass(frozen=True)
class PythonRule(AgentRule):
    """
    A rule for any Python repository.
    """


@dataclass(frozen=True)
class KrroodRule(AgentRule):
    """
    A rule for a repository built on krrood, naming the krrood API it uses.
    """


@dataclass(frozen=True)
class ProjectRule(AgentRule):
    """
    A rule for one repository only, declared in that repository's rules file.
    """


class RuleCatalogue(Enum):
    """
    A set of rules, one member per rule, each member's value being its
    :class:`AgentRule`.
    """

    @classmethod
    def rules_in(cls, section: SectionHeadings) -> list[AgentRule]:
        """
        :param section: The section to collect.
        :return: The catalogue's rules for ``section``, in declaration order.
        """
        return [member.value for member in cls if member.value.section is section]
