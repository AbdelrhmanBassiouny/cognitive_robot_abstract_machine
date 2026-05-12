"""
Abstract base classes for code analysis.

Analyzers produce pure-data specification dataclasses (see
:mod:`krrood.patterns.code_generation.specs`).  They know nothing about
:class:`Action` classes — that coupling lives in the planner layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from krrood.class_diagrams.class_diagram import ClassDiagram
from krrood.patterns.code_generation.import_name_resolver import ImportNameResolver
from krrood.patterns.code_generation.type_normaliser import TypeNormaliser


@dataclass
class AnalysisContext:
    """Shared context passed to all analyzers for a single module transformation.

    Attributes:
        class_diagram: The class diagram covering all relevant classes.
        resolver: Import name resolver for type-to-module mapping.
        normaliser: Type-to-string converter.
        already_covered_bases: Base classes whose members are already covered
            by a parent mixin and should be excluded from delegation.
        pd_only_delegatees: Delegatee types used by non-Role PropertyDelegator
            subclasses — these get DelegatorFor mixins but not HasRoles.
        module_name: The dotted name of the module being analyzed.
        source_module: The live :class:`ModuleType` of the module being analyzed.
    """

    class_diagram: ClassDiagram
    resolver: ImportNameResolver
    normaliser: TypeNormaliser
    already_covered_bases: set[type] = field(default_factory=set)
    pd_only_delegatees: set[type] = field(default_factory=set)
    module_name: str = ""
    source_module: ModuleType | None = None


class CodeAnalyzer(ABC):
    """Abstract base for all code analyzers.

    Each subclass implements :meth:`analyze`, which takes a target (e.g. a
    :class:`~krrood.class_diagrams.class_diagram.WrappedClass` or a
    :class:`libcst.Module`) and an :class:`AnalysisContext`, and returns a
    spec dataclass from :mod:`krrood.patterns.code_generation.specs`.
    """

    @abstractmethod
    def analyze(self, target: Any, context: AnalysisContext) -> Any:
        """Produce a spec dataclass describing what transformations are needed.

        :param target: The input to analyze (class, module, etc.).
        :param context: Shared analysis context with diagram, resolver, etc.
        :return: A spec dataclass (e.g. :class:`DelegationSpec`).
        """
