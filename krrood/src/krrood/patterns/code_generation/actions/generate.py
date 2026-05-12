"""
Generation actions that create new code artifacts.

Each action is atomic and reversible: :meth:`Action.apply` creates the
artifact, :meth:`Action.reverse` deletes or restores it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import libcst

from krrood.patterns.code_generation.actions.base import GenerationAction
from krrood.patterns.code_generation.specs.specs import BaseClassSpec


# ── helpers ───────────────────────────────────────────────────────────


def _make_arg(name: str) -> libcst.Arg:
    return libcst.Arg(value=libcst.Name(name))


def _find_class_in_module(
    module: libcst.Module, class_name: str
) -> tuple[int, libcst.ClassDef] | None:
    for i, stmt in enumerate(module.body):
        if isinstance(stmt, libcst.ClassDef) and stmt.name.value == class_name:
            return i, stmt
    return None


# ── concrete generation actions ───────────────────────────────────────


@dataclass
class CreateClass(GenerationAction):
    """Create a new class definition and add it to a module.

    Reverse operation removes the class from the module.
    """

    class_name: str
    """The name of the class to create."""

    bases: list[BaseClassSpec] = field(default_factory=list)
    """Base classes for the new class."""

    body: list[libcst.BaseStatement] = field(default_factory=list)
    """The body statements of the new class."""

    decorators: list[libcst.Decorator] = field(default_factory=list)
    """Decorators to apply to the class."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        bases_args = [_make_arg(b.name) for b in self.bases]
        class_def = libcst.ClassDef(
            name=libcst.Name(self.class_name),
            bases=bases_args,
            body=libcst.IndentedBlock(body=self.body),
            decorators=self.decorators,
        )
        return module.with_changes(
            body=list(module.body) + [class_def]
        )

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class_in_module(module, self.class_name)
        if found is None:
            return module
        idx, _ = found
        new_body = list(module.body)
        new_body.pop(idx)
        return module.with_changes(body=new_body)

    @property
    def description(self) -> str:
        return f"Create class {self.class_name}"


@dataclass
class CreateModule(GenerationAction):
    """Create a new :class:`libcst.Module` from a list of statements.

    This is typically the first action in a plan that generates a brand-new
    module.  Reverse returns an empty module.
    """

    body: list[libcst.BaseStatement] = field(default_factory=list)
    """Top-level statements for the new module."""

    _previous_module: libcst.Module | None = field(
        default=None, init=False, repr=False
    )

    def apply(self, module: libcst.Module) -> libcst.Module:
        self._previous_module = module
        return libcst.Module(body=self.body)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        if self._previous_module is not None:
            return self._previous_module
        return libcst.Module(body=[])

    @property
    def description(self) -> str:
        return "Create new module"


@dataclass
class WriteModule(GenerationAction):
    """Write a module's source code to a file on disk.

    Reverse restores the original file from backup, or deletes the file if
    it was newly created by this action.
    """

    file_path: Path
    """The path to write to."""

    source: str
    """The source code to write."""

    _backup: str | None = field(default=None, init=False, repr=False)
    """Original file content before writing, or ``None`` for new files."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        # Backup original if it exists
        if self.file_path.exists():
            self._backup = self.file_path.read_text()
        else:
            self._backup = None
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(self.source)
        return module

    def reverse(self, module: libcst.Module) -> libcst.Module:
        if self._backup is not None:
            self.file_path.write_text(self._backup)
        elif self.file_path.exists():
            self.file_path.unlink()
        return module

    @property
    def description(self) -> str:
        return f"Write module to {self.file_path}"
