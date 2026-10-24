"""
The rules agents follow, the sections ``AGENTS.md`` groups them under and the rule sets
they belong to.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType

from typing_extensions import Any, Callable

from krrood.development_tools.exceptions import (
    CatalogueWithoutSection,
    SectionWithoutTitle,
)
from krrood.development_tools.repository_files import RepositoryInstructionsFile
from krrood.ormatic.utils import classproperty

# %% code named by rules


@dataclass(frozen=True)
class CodeReference:
    """
    A module, class or function a rule names, rendered as inline Markdown code, so the
    rule follows a rename of it.
    """

    target: ModuleType | type | Callable[..., Any]
    """
    The object the rule names.
    """

    public_module: ModuleType | None = None
    """
    The module the object is imported from, where that is not the module defining it.
    """

    @property
    def path(self) -> str:
        """
        The import path of the object, as inline code.
        """
        if isinstance(self.target, ModuleType):
            return f"`{self.target.__name__}`"
        module = self.public_module or self.target
        module_name = (
            module.__name__ if isinstance(module, ModuleType) else module.__module__
        )
        return f"`{module_name}.{self.target.__qualname__}`"

    @property
    def name(self) -> str:
        """
        The object's own name, as inline code.
        """
        return f"`{self.target.__name__}`"


# %% sections


class Section:
    """
    A section of the rules in ``AGENTS.md``. A subclass of a section is a subsection
    nested under it, unless it is a :class:`RuleCatalogue`, which holds rules of the
    section instead.
    """

    @classproperty
    def title(cls) -> str:
        """
        The text of the section's heading.
        """
        raise SectionWithoutTitle(cls)

    @classproperty
    def subsections(cls) -> list[type[Section]]:
        """
        The sections nested directly under this one, in definition order.
        """
        return [
            subclass
            for subclass in cls.__subclasses__()
            if not issubclass(subclass, RuleCatalogue)
        ]

    @classproperty
    def heading(cls) -> str:
        """
        The section's heading as a line of Markdown, one level deeper than the section
        it is nested under.
        """
        level = sum(
            1
            for base in cls.__mro__
            if issubclass(base, Section) and base is not Section
        )
        return f"{'#' * level} {cls.title}"


# %% rules


@dataclass(frozen=True)
class AgentRule:
    """
    One rule agents follow, rendered as a Markdown list item.
    """

    statement: str
    """
    The rule itself.
    """

    details: tuple[str, ...] = ()
    """
    The points that spell the rule out, rendered as a nested list below it.
    """


class RuleCatalogue(Enum):
    """
    The rules of one rule set in one section, one member per rule, each member's value
    being its :class:`AgentRule`. A catalogue subclasses its rule set and the
    :class:`Section` its rules belong to.
    """

    @classproperty
    def section(cls) -> type[Section]:
        """
        The section the catalogue's rules belong to.
        """
        sections = [
            base
            for base in cls.__mro__
            if issubclass(base, Section) and not issubclass(base, RuleCatalogue)
        ]
        if not sections:
            raise CatalogueWithoutSection(cls)
        return sections[0]

    @classproperty
    def source_path(cls) -> Path:
        """
        The path of the module declaring the catalogue, relative to the directory of
        its top-level package.
        """
        return Path(*cls.__module__.split(".")).with_suffix(".py")


# %% rule sets


class PythonRules(RuleCatalogue):
    """
    The rule set for any Python repository.
    """


class KrroodRules(RuleCatalogue):
    """
    The rule set for a repository built on krrood, naming the krrood API it uses.
    """


class ProjectRules(RuleCatalogue):
    """
    The rule set of one repository only, declared in that repository's
    :attr:`~krrood.development_tools.repository_files.RepositoryInstructionsFile.PROJECT_RULES`.
    """

    @classproperty
    def source_path(cls) -> Path:
        """
        The repository's rules module, relative to the repository root.
        """
        return Path(RepositoryInstructionsFile.PROJECT_RULES)
