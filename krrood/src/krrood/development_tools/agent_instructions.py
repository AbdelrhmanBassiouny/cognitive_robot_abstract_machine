"""
Keeps the block of generated rules in a repository's ``AGENTS.md`` equal to the rules krrood
ships and the rules the repository declares.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from enum import Enum, StrEnum
from functools import cached_property
from pathlib import Path
from types import ModuleType

import jinja2

from krrood.development_tools.agent_rule import (
    KrroodRules,
    ProjectRules,
    PythonRules,
    RuleCatalogue,
    Section,
)
from krrood.development_tools.exceptions import MalformedRulesBlock
from krrood.development_tools.repository_files import RepositoryInstructionsFile
# imported to declare the catalogues of the shipped rule sets
from krrood.development_tools.rules import krrood_rules, python_rules  # noqa: F401
from krrood.patterns.path_enumeration import PathEnumeration
from krrood.utils import recursive_subclasses

# %% file contents


class RulesBlockMarker(StrEnum):
    """
    The lines that enclose the block of generated rules in ``AGENTS.md``.
    """

    BEGIN = (
        "<!-- BEGIN generated rules: written by `krrood agents-md`. Never edit inside "
        "this block; change a rule in the module named above it, then regenerate. -->"
    )
    """
    The line that opens the block.
    """

    END = "<!-- END generated rules -->"
    """
    The line that closes the block.
    """


class TemplateFile(PathEnumeration):
    """
    The templates the generated text is rendered from.
    """

    RULES = Path(__file__).parent / "templates" / "rules.md.jinja"
    """
    The rules of the block, under the headings of their sections.
    """


# %% rule sets


class RuleSet(Enum):
    """
    The rule sets krrood ships, each member's value being the rule set's class.
    """

    PYTHON = PythonRules
    """
    The rules for any Python repository.
    """

    KRROOD = KrroodRules
    """
    The rules for a repository built on krrood.
    """

    @property
    def command_line_name(self) -> str:
        """
        The name the command line chooses the rule set by.
        """
        return self._name_.lower()

    @property
    def catalogues(self) -> list[type[RuleCatalogue]]:
        """
        The catalogues of the rule set, one per section, in declaration order.
        """
        return self.value.__subclasses__()


# %% project rules


@dataclass
class ProjectRulesModule:
    """
    The module of one repository that declares the repository's own rules.
    """

    repository_root: Path
    """
    The directory holding the module.
    """

    @cached_property
    def module(self) -> ModuleType | None:
        """
        The module, loaded once per process; none if the repository has no such module.
        """
        path = (
            self.repository_root / RepositoryInstructionsFile.PROJECT_RULES
        ).resolve()
        if not path.is_file():
            return None
        module_name = str(path)
        if module_name in sys.modules:
            return sys.modules[module_name]
        specification = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        specification.loader.exec_module(module)
        return module

    @property
    def catalogues(self) -> list[type[RuleCatalogue]]:
        """
        The catalogues of :class:`~krrood.development_tools.agent_rule.ProjectRules` the
        module declares, in declaration order.
        """
        if self.module is None:
            return []
        return [
            catalogue
            for catalogue in recursive_subclasses(ProjectRules)
            if catalogue.__module__ == self.module.__name__
        ]


# %% generation


@dataclass
class SectionContent:
    """
    The rules one section lists, directly and in its subsections.
    """

    section: type[Section]
    """
    The section listing the rules.
    """

    catalogues: list[type[RuleCatalogue]]
    """
    The catalogues whose rules the section lists directly, in the order it lists them.
    """

    subsections: list[SectionContent]
    """
    The content of the subsections that list any rules.
    """


@dataclass
class AgentsInstructions:
    """
    The ``AGENTS.md`` of one repository, whose block of generated rules holds the rules
    of the chosen catalogues and whose text around that block is written by hand.
    """

    repository_root: Path
    """
    The directory holding the repository's ``AGENTS.md``.
    """

    catalogues: list[type[RuleCatalogue]]
    """
    The catalogues whose rules the block contains; a section lists them in this order.
    """

    @classmethod
    def of_repository(
        cls, repository_root: Path, rule_sets: tuple[RuleSet, ...] = tuple(RuleSet)
    ) -> AgentsInstructions:
        """
        :param repository_root: The directory holding the repository's ``AGENTS.md``.
        :param rule_sets: The shipped rule sets the block contains.
        :return: The instructions holding the rules of ``rule_sets``, followed in each
            section by the repository's own rules.
        """
        return cls(
            repository_root,
            [
                *(
                    catalogue
                    for rule_set in rule_sets
                    for catalogue in rule_set.catalogues
                ),
                *ProjectRulesModule(repository_root).catalogues,
            ],
        )

    @property
    def path(self) -> Path:
        """
        The path of the repository's ``AGENTS.md``.
        """
        return self.repository_root / RepositoryInstructionsFile.AGENTS

    def contents_of(self, sections: list[type[Section]]) -> list[SectionContent]:
        """
        :param sections: The sections to collect.
        :return: The content of each of ``sections`` that lists any of the chosen rules,
            directly or in a subsection.
        """
        contents = [
            SectionContent(
                section,
                [
                    catalogue
                    for catalogue in self.catalogues
                    if catalogue.section is section
                ],
                self.contents_of(section.subsections),
            )
            for section in sections
        ]
        return [
            content for content in contents if content.catalogues or content.subsections
        ]

    @property
    def rules_text(self) -> str:
        """
        The rules of the chosen catalogues, under the headings of the sections that list
        any.
        """
        environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TemplateFile.RULES.parent),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        return environment.get_template(TemplateFile.RULES.name).render(
            sections=self.contents_of(Section.subsections)
        )

    @property
    def rules_block(self) -> str:
        """
        The block of generated rules, from its opening to its closing marker line.
        """
        return f"{RulesBlockMarker.BEGIN}\n\n{self.rules_text}{RulesBlockMarker.END}"

    def render(self) -> str:
        """
        Compose the content ``AGENTS.md`` must have.

        :return: The current file with its block of generated rules replaced, the block
            followed by the current file if it has no block yet, or the block alone if
            there is no file yet.
        :raises MalformedRulesBlock: If the file holds a marker line, but not exactly
            one block.
        """
        if not self.path.is_file():
            return f"{self.rules_block}\n"
        content = self.path.read_text(encoding="utf-8")
        if (
            RulesBlockMarker.BEGIN not in content
            and RulesBlockMarker.END not in content
        ):
            return f"{self.rules_block}\n\n{content}"
        before_block, _, from_block = content.partition(RulesBlockMarker.BEGIN)
        _, _, after_block = from_block.partition(RulesBlockMarker.END)
        has_one_block = (
            content.count(RulesBlockMarker.BEGIN) == 1
            and content.count(RulesBlockMarker.END) == 1
            and RulesBlockMarker.END in from_block
        )
        if not has_one_block:
            raise MalformedRulesBlock(
                self.path, RulesBlockMarker.BEGIN, RulesBlockMarker.END
            )
        return f"{before_block}{self.rules_block}{after_block}"

    def is_current(self) -> bool:
        """
        :return: Whether ``AGENTS.md`` exists and its block of generated rules equals the
            rules it must hold.
        :raises MalformedRulesBlock: If the file holds a marker line, but not exactly
            one block.
        """
        if not self.path.is_file():
            return False
        return self.path.read_text(encoding="utf-8") == self.render()

    def write(self) -> bool:
        """
        Write ``AGENTS.md`` with the block of generated rules it must hold, keeping the text
        around the block.

        :return: Whether the file changed.
        :raises MalformedRulesBlock: If the file holds a marker line, but not exactly
            one block.
        """
        if self.is_current():
            return False
        self.path.write_text(self.render(), encoding="utf-8")
        return True
