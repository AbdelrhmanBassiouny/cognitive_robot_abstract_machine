"""
Abstract base class for action planners.

Planners convert pure-data specs into :class:`ActionPlan` objects.  They
know about CST generation (via :class:`LibCSTNodeFactory`) but know nothing
about MRO walking or type classification — that belongs to the analysis layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from krrood.patterns.code_generation.actions import ActionPlan
from krrood.patterns.code_generation.import_name_resolver import ImportNameResolver
from krrood.patterns.code_generation.libcst_node_factory import LibCSTNodeFactory
from krrood.patterns.code_generation.type_normaliser import TypeNormaliser


@dataclass
class PlanningContext:
    """Shared context passed to all planners for a single module transformation.

    Attributes:
        factory: CST node factory for building AST nodes.
        normaliser: Type-to-string converter for annotations.
        resolver: Import name resolver for type-to-module mapping.
        delegatee_attr: Attribute name used to access the delegatee instance
            (e.g. ``"delegatee"``).
        file_name_prefix: Prefix applied to generated file names.
        module: The live :class:`ModuleType` being processed.
    """

    factory: LibCSTNodeFactory
    normaliser: TypeNormaliser
    resolver: ImportNameResolver
    delegatee_attr: str = "delegatee"
    file_name_prefix: str = ""
    module: ModuleType | None = None


class ActionPlanner(ABC):
    """Abstract base for all action planners.

    Each subclass implements :meth:`plan`, which takes a spec dataclass and a
    :class:`PlanningContext`, and returns an :class:`ActionPlan`.
    """

    @abstractmethod
    def plan(self, spec: Any, context: PlanningContext) -> ActionPlan:
        """Convert a spec into an :class:`ActionPlan`.

        :param spec: A spec dataclass from :mod:`krrood.patterns.code_generation.specs`.
        :param context: Shared planning context with factory, resolver, etc.
        :return: An :class:`ActionPlan` ready for execution.
        """
