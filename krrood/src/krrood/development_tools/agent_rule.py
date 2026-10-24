"""
The rules agents follow, the sections of ``AGENTS.md`` that declare them and the rule
sets those sections form.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from typing_extensions import Any, Callable

from krrood.development_tools.exceptions import SectionWithoutTitle
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


# %% sections


class Section:
    """
    A section of ``AGENTS.md``, listing the rules declared as its class attributes. A
    subclass of a section is a subsection nested under it.
    """

    @classproperty
    def title(cls) -> str:
        """
        The text of the section's heading.
        """
        raise SectionWithoutTitle(cls)

    @classproperty
    def rules(cls) -> list[AgentRule]:
        """
        The rules the section lists directly, in declaration order.
        """
        return [rule for rule in vars(cls).values() if isinstance(rule, AgentRule)]

    @classproperty
    def subsections(cls) -> list[type[Section]]:
        """
        The sections nested directly under this one, in definition order.
        """
        return cls.__subclasses__()

    @classproperty
    def has_rules(cls) -> bool:
        """
        Whether the section lists any rule, directly or in a subsection.
        """
        return bool(cls.rules) or any(
            subsection.has_rules for subsection in cls.subsections
        )

    @classproperty
    def heading(cls) -> str:
        """
        The section's heading as a line of Markdown, one level deeper than the section
        it is nested under.

        :raises SectionWithoutTitle: If the section declares no title of its own.
        """
        if "title" not in vars(cls):
            raise SectionWithoutTitle(cls)
        level = sum(
            1
            for base in cls.__mro__
            if issubclass(base, Section) and base not in (Section, RuleSet)
        )
        return f"{'#' * level} {cls.title}"

    @classproperty
    def source_path(cls) -> Path:
        """
        The path of the module declaring the section, relative to the directory its
        top-level package or module lies in.
        """
        return Path(*cls.__module__.split(".")).with_suffix(".py")


# %% rule sets


class RuleSet(Section):
    """
    A set of rules a repository adopts as a whole: a top-level section of
    ``AGENTS.md``. The rule sets are the subsections of this class.
    """

    @classproperty
    def command_line_name(cls) -> str:
        """
        The name the command line chooses the rule set by.
        """
        return cls.__name__.removesuffix("Rules").lower()


class PythonRules(RuleSet):
    """
    The rule set for any Python repository.
    """

    @classproperty
    def title(cls) -> str:
        return "Python Rules"


class KrroodRules(RuleSet):
    """
    The rule set for a repository built on krrood, naming the krrood API it uses.
    """

    @classproperty
    def title(cls) -> str:
        return "krrood Rules"


class ProjectRules(RuleSet):
    """
    The rule set of one repository only, whose sections the repository declares in its
    :attr:`~krrood.development_tools.repository_files.RepositoryInstructionsFile.PROJECT_RULES`
    or in modules that one imports.
    """

    @classproperty
    def title(cls) -> str:
        return "Project Rules"

    @classmethod
    def import_from(cls, repository_root: Path) -> ModuleType | None:
        """
        Import the repository's rules module, once per process, which declares the
        repository's sections.

        :param repository_root: The directory holding the module.
        :return: The module; none if the repository has no such module.
        """
        path = repository_root / RepositoryInstructionsFile.PROJECT_RULES
        if not path.is_file():
            return None
        module_name = path.stem
        if module_name in sys.modules:
            return sys.modules[module_name]
        specification = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        specification.loader.exec_module(module)
        return module
