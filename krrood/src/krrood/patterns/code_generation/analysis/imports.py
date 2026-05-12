"""
Import analyzer: inspects a :class:`libcst.Module` and produces
:class:`ImportSpec` values for all names that need imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import libcst

from krrood.patterns.code_generation.analysis.base import (
    AnalysisContext,
    CodeAnalyzer,
)
from krrood.patterns.code_generation.specs.specs import ImportSpec


# ── CST visitors for name collection ─────────────────────────────────


class NameCollector(libcst.CSTVisitor):
    """Collects all ``Name`` node values encountered during a CST traversal.

    Parameter names are explicitly excluded: only annotations and default
    expressions are visited, not the parameter name itself.
    """

    def __init__(self):
        self.names: set[str] = set()

    def visit_Param(self, node: libcst.Param) -> bool:
        if node.annotation is not None:
            node.annotation.visit(self)
        if node.default is not None:
            node.default.visit(self)
        return False

    def visit_Name(self, node: libcst.Name) -> None:
        self.names.add(node.value)


class RuntimeNameCollector(libcst.CSTVisitor):
    """Collects names that appear inside decorator expressions."""

    def __init__(self):
        self.names: set[str] = set()

    def visit_Decorator(self, node: libcst.Decorator) -> None:
        collector = NameCollector()
        node.visit(collector)
        self.names.update(collector.names)


class BaseClassNameCollector(libcst.CSTVisitor):
    """Collects names that appear in class base-class expressions."""

    def __init__(self):
        self.names: set[str] = set()

    def visit_ClassDef(self, node: libcst.ClassDef) -> None:
        collector = NameCollector()
        for arg in node.bases:
            arg.value.visit(collector)
        self.names.update(collector.names)


# ── ImportAnalyzer ───────────────────────────────────────────────────


@dataclass
class ImportAnalyzer(CodeAnalyzer):
    """Analyzes a :class:`libcst.Module` and produces a list of :class:`ImportSpec`.

    Uses CST visitors to collect names used in type annotations, decorators,
    and base-class expressions, then resolves each name to its source module
    via the :class:`~krrood.patterns.code_generation.import_name_resolver.ImportNameResolver`
    in the :class:`AnalysisContext`.
    """

    _non_importable: frozenset[str] = field(default_factory=lambda: frozenset({
        "typing", "typing_extensions", "builtins",
    }))
    _excluded_names: frozenset[str] = field(default_factory=lambda: frozenset({
        "dataclass", "field", "ABC", "abstractmethod", "TYPE_CHECKING",
    }))

    def analyze(
        self, target: libcst.Module, context: AnalysisContext
    ) -> list[ImportSpec]:
        """Collect imports needed by *target*.

        :param target: The CST module to analyze for import needs.
        :param context: Shared analysis context with a resolver.
        :return: A list of :class:`ImportSpec` objects.
        """
        # Collect names from the AST
        name_collector = NameCollector()
        target.visit(name_collector)

        runtime_collector = RuntimeNameCollector()
        target.visit(runtime_collector)

        base_collector = BaseClassNameCollector()
        target.visit(base_collector)

        # Resolve each name to its module
        imports: dict[str, set[str]] = {}  # module -> names
        for name in (
            name_collector.names
            | runtime_collector.names
            | base_collector.names
        ):
            if name in self._excluded_names:
                continue
            module = context.resolver.resolve(name)
            if module is None or module in self._non_importable:
                continue
            imports.setdefault(module, set()).add(name)

        return [
            ImportSpec(module=mod, names=frozenset(names))
            for mod, names in imports.items()
        ]
