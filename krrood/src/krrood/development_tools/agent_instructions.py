"""
Generates a repository's ``AGENTS.md`` from the rules krrood ships and the rules the
repository declares.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from krrood.code_generation.generator import CodeGenerator
from krrood.development_tools.agent_rule import Section
from krrood.development_tools.repository_files import RepositoryInstructionsFile

# imported to declare the sections of the shipped rules
from krrood.development_tools import shipped_rules  # noqa: F401
from krrood.patterns.path_enumeration import PathEnumeration

# %% file contents


class TemplateFile(PathEnumeration):
    """
    The templates the generated files are rendered from.
    """

    AGENTS = Path(__file__).parent / "templates" / "agents.md.jinja"
    """
    The content of ``AGENTS.md``: rules under the headings of their sections.
    """


# %% generation


@dataclass
class AgentsInstructions:
    """
    The ``AGENTS.md`` of one repository, listing the rules of the given sections.
    """

    repository_root: Path
    """
    The directory holding the repository's ``AGENTS.md``.
    """

    sections: list[type[Section]]
    """
    The top-level sections the file lists, each with the sections nested under it.
    """

    @classmethod
    def from_repository(cls, repository_root: Path) -> AgentsInstructions:
        """
        :param repository_root: The directory holding the repository's ``AGENTS.md``.
        :return: The file listing every section declared: the ones krrood ships, then
            the repository's own.
        """
        cls.import_project_rules(repository_root)
        return cls(repository_root, Section.top_level)

    @classmethod
    def import_project_rules(cls, repository_root: Path) -> ModuleType | None:
        """
        Import the repository's rules module, once per process, which declares the
        repository's own sections.

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

    @property
    def path(self) -> Path:
        """
        The path of the repository's ``AGENTS.md``.
        """
        return self.repository_root / RepositoryInstructionsFile.AGENTS

    @property
    def text(self) -> str:
        """
        The content ``AGENTS.md`` must have: the rules of :attr:`sections`, under their
        headings, in the order they are declared.
        """
        return CodeGenerator(str(TemplateFile.AGENTS.parent)).render(
            TemplateFile.AGENTS.name,
            sections=self.sections,
        )

    def is_current(self) -> bool:
        """
        :return: Whether ``AGENTS.md`` exists and equals :attr:`text`.
        """
        if not self.path.is_file():
            return False
        return self.path.read_text(encoding="utf-8") == self.text

    def write(self) -> bool:
        """
        Write ``AGENTS.md``, replacing whatever it held.

        :return: Whether the file changed.
        """
        if self.is_current():
            return False
        self.path.write_text(self.text, encoding="utf-8")
        return True
